"""AstrBot plugin: show every configured model provider's balance at a glance."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

from .src.accounts import Account, Discovery, discover_accounts
from .src.cache import ImageCache, TTLCache
from .src.client import BalanceClient
from .src.constants import IMAGE_CACHE_SIZE, PLUGIN_DISPLAY_NAME
from .src.errors import BalanceError
from .src.format import (
    format_cooldown,
    format_internal_error,
    format_no_accounts,
    format_report,
)
from .src.models import AccountResult, BalanceSnapshot
from .src.render import render_report


class BalanceBoardPlugin(Star):
    """Read AstrBot's model providers and render one balance card."""

    def __init__(self, context: Context, config: AstrBotConfig | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        self.client = BalanceClient(
            timeout=self._cfg_float("request_timeout", 10.0),
            retries=self._cfg_int("max_retries", 2),
            proxy=str(self.config.get("proxy", "") or ""),
        )
        self.cache = TTLCache(self._cfg_float("cache_ttl", 60.0))
        self.image_cache = ImageCache(
            IMAGE_CACHE_SIZE if self._cfg_bool("image_cache", True) else 0
        )
        self._last_query: dict[str, float] = {}

    # ─────────────────────────── commands ───────────────────────────

    @filter.command("余额", alias={"余额查询", "查余额", "模型余额", "余额看板", "balance"})
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_balance(self, event: AstrMessageEvent):
        """查询 AstrBot 中所有已配置模型供应商的余额。"""

        event.stop_event()

        identity = self._identity(event)
        cooldown_left = self._cooldown_left(identity)
        if cooldown_left > 0:
            yield event.plain_result(format_cooldown(cooldown_left))
            return
        self._last_query[identity] = time.monotonic()
        self._prune_state()

        discovery = self._discover()
        self._log_discovery(discovery)
        if not discovery.accounts:
            yield event.plain_result(format_no_accounts())
            return

        try:
            results = await self._collect(discovery.accounts)
        except Exception:
            logger.exception("[%s] 查询时发生未预期的错误。", PLUGIN_DISPLAY_NAME)
            yield event.plain_result(format_internal_error())
            return

        try:
            image_path = await asyncio.to_thread(render_report, results, cache=self.image_cache)
        except Exception:
            logger.exception("[%s] 图片渲染失败，改为发送文本结果。", PLUGIN_DISPLAY_NAME)
            yield event.plain_result(format_report(results))
            return

        yield event.image_result(image_path)

    async def terminate(self) -> None:
        """Release the shared HTTP session when the plugin is disabled."""

        await self.client.close()

    # ─────────────────────────── discovery ───────────────────────────

    def _discover(self) -> Discovery:
        """Read AstrBot's model providers and map them to balance accounts."""

        try:
            return discover_accounts(self._get_providers())
        except Exception:
            logger.exception("[%s] 解析模型供应商配置失败。", PLUGIN_DISPLAY_NAME)
            return Discovery()

    def _get_providers(self) -> list[Any]:
        """Return provider instances from the AstrBot context."""

        getter = getattr(self.context, "get_all_providers", None)
        if callable(getter):
            try:
                providers = getter()
            except Exception:
                logger.exception("[%s] 读取模型供应商列表失败。", PLUGIN_DISPLAY_NAME)
            else:
                if providers:
                    return list(providers)

        manager = getattr(self.context, "provider_manager", None)
        inst_map = getattr(manager, "inst_map", None)
        if isinstance(inst_map, Mapping):
            return list(inst_map.values())
        return []

    def _log_discovery(self, discovery: Discovery) -> None:
        for warning in discovery.warnings:
            logger.warning("[%s] %s", PLUGIN_DISPLAY_NAME, warning)

        if discovery.unsupported:
            logger.info(
                "[%s] 已跳过无法识别余额接口的供应商：%s",
                PLUGIN_DISPLAY_NAME,
                "、".join(discovery.unsupported),
            )
        if discovery.accounts:
            logger.debug(
                "[%s] 从 AstrBot 模型供应商中识别到 %d 个可查询账号。",
                PLUGIN_DISPLAY_NAME,
                len(discovery.accounts),
            )

    # ─────────────────────────── querying ───────────────────────────

    async def _collect(self, accounts: list[Account]) -> list[AccountResult]:
        """Query every account concurrently, reusing cached successes."""

        results: dict[str, AccountResult] = {}
        pending: list[Account] = []

        for account in accounts:
            cached = self.cache.get(account.cache_key)
            if isinstance(cached, BalanceSnapshot):
                results[account.cache_key] = AccountResult(account=account, balance=cached)
            else:
                pending.append(account)

        if pending:
            outcomes = await asyncio.gather(*(self._query_one(account) for account in pending))
            for outcome in outcomes:
                results[outcome.account.cache_key] = outcome
                if outcome.balance is not None:
                    self.cache.set(outcome.account.cache_key, outcome.balance)

        return [results[account.cache_key] for account in accounts]

    async def _query_one(self, account: Account) -> AccountResult:
        try:
            balance = await self.client.query(account)
        except BalanceError as exc:
            logger.warning(
                "[%s] 查询失败 provider=%s host=%s code=%s status=%s",
                PLUGIN_DISPLAY_NAME,
                account.provider,
                account.host,
                exc.code or "-",
                exc.status or "-",
            )
            return AccountResult(account=account, error=exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "[%s] 查询异常 provider=%s host=%s",
                PLUGIN_DISPLAY_NAME,
                account.provider,
                account.host,
            )
            return AccountResult(
                account=account,
                error=BalanceError(f"插件内部错误：{type(exc).__name__}"),
            )

        logger.info(
            "[%s] 查询成功 provider=%s host=%s metric=%s",
            PLUGIN_DISPLAY_NAME,
            account.provider,
            account.host,
            balance.metric,
        )
        return AccountResult(account=account, balance=balance)

    # ─────────────────────────── helpers ───────────────────────────

    @staticmethod
    def _identity(event: AstrMessageEvent) -> str:
        platform = event.get_platform_name() or "unknown"
        user_id = event.get_sender_id()
        if not user_id:
            session_id = getattr(event, "session_id", "")
            user_id = session_id if isinstance(session_id, str) else ""
        return f"{platform}:{user_id or 'unknown'}"

    def _cooldown_left(self, identity: str) -> float:
        cooldown = max(0.0, self._cfg_float("user_cooldown", 5.0))
        if cooldown <= 0:
            return 0.0

        last = self._last_query.get(identity)
        if last is None:
            return 0.0

        return max(0.0, cooldown - (time.monotonic() - last))

    def _prune_state(self) -> None:
        if len(self._last_query) < 4096:
            return

        cutoff = time.monotonic() - 3600
        self._last_query = {
            user_id: timestamp
            for user_id, timestamp in self._last_query.items()
            if timestamp >= cutoff
        }

    def _cfg_int(self, name: str, default: int) -> int:
        value = self.config.get(name, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _cfg_float(self, name: str, default: float) -> float:
        value = self.config.get(name, default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _cfg_bool(self, name: str, default: bool) -> bool:
        value = self.config.get(name, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if value is None:
            return default
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            return default
