"""Async HTTP client that queries every supported provider."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import aiohttp

from .accounts import Account
from .constants import MAX_RESPONSE_BYTES, USER_AGENT
from .errors import (
    AuthError,
    BalanceError,
    NetworkError,
    RateLimitError,
    UnsupportedError,
    UpstreamError,
)
from .models import BalanceSnapshot
from .providers import PARSERS, ProviderSpec, kimi_currency
from .security import sanitize_text


class BalanceClient:
    """Shared-session HTTP client with timeout and retry support."""

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        proxy: str = "",
        user_agent: str = USER_AGENT,
    ) -> None:
        self.timeout = max(1.0, float(timeout))
        self.retries = min(5, max(0, int(retries)))
        self.proxy = proxy.strip() or None
        self.user_agent = user_agent
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is not None and not self._session.closed:
            return self._session

        async with self._session_lock:
            if self._session is None or self._session.closed:
                connector = aiohttp.TCPConnector(limit=8, ttl_dns_cache=300)
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    connector=connector,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "application/json",
                    },
                )
        return self._session

    async def query(self, account: Account) -> BalanceSnapshot:
        """Query one account, retrying transient failures with backoff."""

        attempts = self.retries + 1
        last_error: BalanceError | None = None

        for attempt in range(attempts):
            try:
                return await self._query_once(account)
            except BalanceError as exc:
                last_error = exc
                if not exc.retryable or attempt >= attempts - 1:
                    raise
                await asyncio.sleep(min(0.6 * (2**attempt), 3.0))

        if last_error is not None:  # pragma: no cover - defensive
            raise last_error
        raise NetworkError("查询失败：未知网络错误。")  # pragma: no cover

    async def _query_once(self, account: Account) -> BalanceSnapshot:
        spec = account.spec
        url = f"{account.base_url}{spec.balance_path}"
        headers = self._headers(account, spec)

        try:
            session = await self._get_session()
            async with session.get(
                url,
                headers=headers,
                allow_redirects=True,
                proxy=self.proxy,
            ) as response:
                status = response.status
                body = await response.read()
        except asyncio.TimeoutError as exc:
            raise NetworkError(
                f"{spec.label} 请求超时。",
                retryable=True,
                hint="请检查服务器网络，或在插件配置中适当增大请求超时时间。",
            ) from exc
        except (aiohttp.ClientError, OSError) as exc:
            raise NetworkError(
                f"无法连接 {spec.label}。",
                retryable=True,
                hint="请检查服务器网络、DNS 或代理设置。",
            ) from exc

        if len(body) > MAX_RESPONSE_BYTES:
            raise UpstreamError("响应数据过大，已中止解析。")

        text = body.decode("utf-8", errors="replace")
        payload: Any = None
        if text.strip():
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None

        payload_dict = payload if isinstance(payload, dict) else None

        if status >= 400:
            raise _error_for_status(account, status, payload_dict, text)

        if payload_dict is None:
            raise UpstreamError(
                f"{spec.label} 返回了非 JSON 响应。",
                status=status,
                retryable=status >= 500,
            )

        parsed = PARSERS[account.provider](payload_dict)
        currency = (
            kimi_currency(account.base_url) if account.provider == "kimi" else parsed.currency
        )

        return BalanceSnapshot(
            account=account,
            available=parsed.available,
            currency=currency,
            metric=parsed.metric,
            value_text=parsed.value_text,
            metric_text=parsed.metric_text,
            secondary=parsed.secondary,
        )

    @staticmethod
    def _headers(account: Account, spec: ProviderSpec) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {account.api_key}",
            "Referer": spec.console_url,
        }
        if account.provider == "modelscope":
            # ModelScope accepts the token from either the bearer header or the
            # web session cookie; send both for compatibility.
            headers["Cookie"] = f"m_session_id={account.api_key}"
        return headers

    async def close(self) -> None:
        """Close the shared HTTP session."""

        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None


def _error_for_status(
    account: Account,
    status: int,
    payload: dict[str, Any] | None,
    text: str,
) -> BalanceError:
    spec = account.spec
    message = ""
    code = ""
    if isinstance(payload, dict):
        message = str(
            payload.get("message")
            or payload.get("msg")
            or payload.get("error")
            or payload.get("detail")
            or ""
        )
        code = str(payload.get("code") or payload.get("error_code") or payload.get("Code") or "")

    message = sanitize_text(message or text[:200], account.api_key)

    if status in {401, 403}:
        return AuthError(
            f"{spec.label}：API Key 无效或无权访问。",
            code=code or f"HTTP_{status}",
            status=status,
            hint=message or "请检查 Key 是否属于该平台，以及是否已被吊销。",
        )

    if status == 410:
        return UnsupportedError(
            f"{spec.label} 已下线余额接口。",
            code=code or f"HTTP_{status}",
            status=status,
            hint=f"请到 {spec.console_url} 查看余额。",
        )

    if status == 429:
        return RateLimitError(
            f"{spec.label}：请求过于频繁。",
            code=code or "HTTP_429",
            status=status,
            retryable=True,
            hint="可以适当增大插件配置中的缓存时间或查询冷却时间。",
        )

    if status >= 500:
        return UpstreamError(
            f"{spec.label} 服务暂时不可用。",
            code=code or f"HTTP_{status}",
            status=status,
            retryable=True,
            hint="请稍后重试。",
        )

    return UpstreamError(
        message or f"{spec.label} 返回 HTTP {status}。",
        code=code or f"HTTP_{status}",
        status=status,
    )
