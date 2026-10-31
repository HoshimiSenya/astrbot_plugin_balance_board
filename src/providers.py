"""Provider definitions and response parsers for every supported platform."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit

from .errors import AuthError, UpstreamError
from .security import sanitize_text


@dataclass(frozen=True)
class ProviderSpec:
    """Static information about one balance provider."""

    id: str
    label: str
    short_label: str
    default_base_url: str
    balance_path: str
    metric: str
    currency: str
    console_url: str
    metric_display: str = "余额"


PROVIDER_ORDER: tuple[str, ...] = (
    "deepseek",
    "zhipu",
    "modelscope",
    "kimi",
    "minimax_token_plan",
    "ollama",
    "302ai",
    "ppio",
)


@dataclass(frozen=True)
class ParsedBalance:
    """Normalised balance returned by a provider parser.

    Money-like providers only need ``available`` / ``currency`` / ``metric``.
    Quota providers (MiniMax Token Plan, legacy Ollama Cloud plans) additionally
    set ``value_text`` (for example ``75%``), ``metric_text`` (``5h 剩余``) and
    an optional ``secondary`` line summarising every visible window.
    """

    available: Decimal
    currency: str
    metric: str
    value_text: str = ""
    metric_text: str = ""
    secondary: str = ""


PROVIDERS: dict[str, ProviderSpec] = {
    "deepseek": ProviderSpec(
        id="deepseek",
        label="DeepSeek",
        short_label="DeepSeek",
        default_base_url="https://api.deepseek.com",
        balance_path="/user/balance",
        metric="余额",
        currency="CNY",
        console_url="https://platform.deepseek.com",
    ),
    "zhipu": ProviderSpec(
        id="zhipu",
        label="智谱",
        short_label="Zhipu AI",
        default_base_url="https://open.bigmodel.cn",
        balance_path="/api/biz/account/query-customer-account-report",
        metric="余额",
        currency="CNY",
        console_url="https://open.bigmodel.cn",
    ),
    "modelscope": ProviderSpec(
        id="modelscope",
        label="魔搭",
        short_label="ModelScope",
        default_base_url="https://www.modelscope.cn",
        balance_path="/openapi/v1/magicubes/balance",
        metric="魔粒",
        currency="魔粒",
        console_url="https://modelscope.cn",
        metric_display="可用魔粒",
    ),
    "kimi": ProviderSpec(
        id="kimi",
        label="Kimi",
        short_label="Kimi / Moonshot",
        default_base_url="https://api.moonshot.cn",
        balance_path="/v1/users/me/balance",
        metric="余额",
        currency="CNY",
        console_url="https://platform.moonshot.cn",
    ),
    "minimax_token_plan": ProviderSpec(
        id="minimax_token_plan",
        label="MiniMax",
        short_label="Token Plan",
        default_base_url="https://api.minimaxi.com",
        balance_path="/v1/token_plan/remains",
        metric="5h 剩余",
        currency="%",
        console_url="https://platform.minimaxi.com",
        metric_display="5h 剩余",
    ),
    "ollama": ProviderSpec(
        id="ollama",
        label="Ollama",
        short_label="Ollama Cloud",
        default_base_url="https://ollama.com",
        balance_path="/api/balance",
        metric="余额",
        currency="USD",
        console_url="https://ollama.com",
    ),
    "302ai": ProviderSpec(
        id="302ai",
        label="302.AI",
        short_label="302.AI",
        default_base_url="https://api.302.ai",
        balance_path="/dashboard/balance",
        metric="余额",
        currency="USD",
        console_url="https://302.ai",
    ),
    "ppio": ProviderSpec(
        id="ppio",
        label="PPIO",
        short_label="PPIO",
        default_base_url="https://api.ppio.com",
        balance_path="/openapi/v1/billing/balance/detail",
        metric="余额",
        currency="CNY",
        console_url="https://ppio.com",
    ),
}

_ALIASES: dict[str, str] = {
    "deepseek": "deepseek",
    "deep-seek": "deepseek",
    "zhipu": "zhipu",
    "bigmodel": "zhipu",
    "glm": "zhipu",
    "智谱": "zhipu",
    "modelscope": "modelscope",
    "model-scope": "modelscope",
    "魔搭": "modelscope",
    "kimi": "kimi",
    "moonshot": "kimi",
    "月之暗面": "kimi",
    "minimax": "minimax_token_plan",
    "minimax_token_plan": "minimax_token_plan",
    "minimax-token-plan": "minimax_token_plan",
    "minimax token plan": "minimax_token_plan",
    "ollama": "ollama",
    "ollama-cloud": "ollama",
    "ollama_cloud": "ollama",
    "302ai": "302ai",
    "302.ai": "302ai",
    "302-ai": "302ai",
    "ppio": "ppio",
    "ppinfra": "ppio",
}

_AUTH_MARKERS = (
    "auth",
    "api key",
    "apikey",
    "credential",
    "token",
    "unauthorized",
    "鉴权",
    "令牌",
    "未登录",
)

_MINIMAX_HOSTS = ("minimax.io", "minimaxi.com", "minimax.cn")
_MINIMAX_TOKEN_MARKERS = (
    "token_plan",
    "token-plan",
    "token plan",
    "tokenplan",
    "m-plan",
    "m_plan",
)

_HOST_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deepseek", ("deepseek.com",)),
    ("zhipu", ("bigmodel.cn", "zhipuai.cn")),
    ("modelscope", ("modelscope.cn", "modelscope.ai")),
    ("kimi", ("moonshot.cn", "moonshot.ai", "kimi.com", "kimi.ai")),
    ("ollama", ("ollama.com",)),
    ("302ai", ("302.ai", "302ai.com")),
    ("ppio", ("ppio.com", "ppinfra.com")),
)

_NAME_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deepseek", ("deepseek",)),
    ("zhipu", ("zhipu", "bigmodel", "chatglm", "glm", "智谱")),
    ("modelscope", ("modelscope", "magicube", "魔搭")),
    ("kimi", ("kimi", "moonshot", "月之暗面")),
    ("ollama", ("ollama-cloud", "ollama_cloud", "ollama cloud")),
    ("302ai", ("302ai", "302.ai")),
    ("ppio", ("ppio", "ppinfra")),
)


def _host_of(api_base: str) -> str:
    raw = str(api_base or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if any(character.isspace() for character in parts.netloc):
        return ""
    return parts.netloc.lower()


def _match_marker(text: str, markers: tuple[tuple[str, tuple[str, ...]], ...]) -> str:
    haystack = text.lower()
    for provider_id, words in markers:
        if any(word in haystack for word in words):
            return provider_id
    return ""


def _is_minimax_token_plan(identity: str) -> bool:
    haystack = identity.lower()
    return "minimax" in haystack and any(marker in haystack for marker in _MINIMAX_TOKEN_MARKERS)


def _identity_parts(type_name: str, provider_name: str, provider_id: str) -> tuple[str, str, str]:
    """Split provider identity into fields that can be matched safely.

    AstrBot provider ids often look like ``ppio/deepseek-v3``. Matching the whole
    string would mistake the model name for the platform, so the provider prefix
    is preferred over the full id.
    """

    primary = " ".join((type_name, provider_name)).strip()
    identifier = provider_id.strip()
    prefix = identifier.split("/", 1)[0].strip() if "/" in identifier else identifier
    return primary, prefix, identifier


def detect_provider(
    *,
    api_base: str = "",
    type_name: str = "",
    provider_name: str = "",
    provider_id: str = "",
) -> ProviderSpec | None:
    """Match an AstrBot provider configuration to a balance provider.

    The configured ``api_base`` host is authoritative: a provider pointing at a
    custom OpenAI-compatible proxy is skipped rather than sending its key to an
    official host it was not meant for. When no base URL is configured, the
    provider type/id is used as a hint.

    MiniMax is special-cased: the Token Plan remains endpoint is only used when
    the provider identity explicitly mentions a token plan. A regular MiniMax
    pay-as-you-go provider must not be queried with a subscription key.
    """

    host = _host_of(api_base)
    primary, prefix, identifier = _identity_parts(type_name, provider_name, provider_id)

    if any(_is_minimax_token_plan(text) for text in (primary, prefix)):
        if not host or any(marker in host for marker in _MINIMAX_HOSTS):
            return PROVIDERS["minimax_token_plan"]
        return None

    if host:
        matched = _match_marker(host, _HOST_MARKERS)
        return PROVIDERS.get(matched) if matched else None

    for text in (primary, prefix):
        matched = _match_marker(text, _NAME_MARKERS)
        if matched:
            return PROVIDERS[matched]

    if "/" not in identifier:
        matched = _match_marker(identifier, _NAME_MARKERS)
        if matched:
            return PROVIDERS[matched]

    return None


def resolve_provider(value: Any) -> ProviderSpec | None:
    """Map a provider id or alias to its specification."""

    if not isinstance(value, str):
        return None
    return PROVIDERS.get(_ALIASES.get(value.strip().lower(), ""))


def _first(mapping: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        value = mapping.get(name)
        if value is not None and value != "":
            return value
    return None


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise UpstreamError(f"响应字段 {field} 缺失或类型异常。")

    text = str(value).strip().replace(",", "")
    for symbol in ("$", "¥", "￥"):
        if text.startswith(symbol):
            text = text[len(symbol) :].strip()
            break

    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise UpstreamError(f"响应字段 {field} 不是有效数字。") from exc

    if not amount.is_finite():
        raise UpstreamError(f"响应字段 {field} 不是有限数字。")

    return amount


def _format_percent(amount: Decimal) -> str:
    if amount == amount.to_integral_value():
        return f"{amount:.0f}%"
    return f"{format(amount.normalize(), 'f')}%"


def _status_number(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _window_text(
    percent_value: Any,
    status_value: Any,
    field: str,
) -> tuple[str, Decimal | None]:
    """Return a display string and numeric value for one quota window.

    ``status`` values follow MiniMax conventions: ``0`` means the window is not
    active, ``1`` normal, ``2`` exhausted and ``3`` unlimited. A missing status
    is treated as active when a percentage is present.
    """

    status = _status_number(status_value)
    if status == 0:
        return "", None
    if status == 3:
        return "无限", None

    if percent_value is None or percent_value == "":
        if status == 2:
            return "0%", Decimal("0")
        return "", None

    percent = _decimal(percent_value, field)
    return _format_percent(percent), percent


def _quota_balance(
    interval_text: str,
    interval_value: Decimal | None,
    weekly_text: str,
    weekly_value: Decimal | None,
) -> ParsedBalance | None:
    if interval_text and weekly_text:
        return ParsedBalance(
            available=interval_value if interval_value is not None else Decimal("0"),
            currency="%",
            metric="5h 剩余",
            value_text=interval_text,
            metric_text="5h 剩余",
            secondary=f"5h: {interval_text} · 周: {weekly_text}",
        )

    if interval_text:
        return ParsedBalance(
            available=interval_value if interval_value is not None else Decimal("0"),
            currency="%",
            metric="5h 剩余",
            value_text=interval_text,
            metric_text="5h 剩余",
        )

    if weekly_text:
        return ParsedBalance(
            available=weekly_value if weekly_value is not None else Decimal("0"),
            currency="%",
            metric="周剩余",
            value_text=weekly_text,
            metric_text="周剩余",
        )

    return None


def _payload_message(payload: dict[str, Any], fallback: str) -> str:
    for key in ("message", "msg", "error", "detail", "Message", "error_msg"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return sanitize_text(value)
    return fallback


def _looks_like_auth(message: str, code: str) -> bool:
    haystack = f"{message} {code}".lower()
    return any(marker in haystack for marker in _AUTH_MARKERS)


def parse_deepseek(payload: dict[str, Any]) -> ParsedBalance:
    infos = payload.get("balance_infos")
    if not isinstance(infos, list) or not infos:
        raise UpstreamError("DeepSeek 响应中没有余额信息。")

    info = next(
        (
            item
            for item in infos
            if isinstance(item, dict) and str(item.get("currency", "")).upper() == "CNY"
        ),
        infos[0],
    )
    if not isinstance(info, dict):
        raise UpstreamError("DeepSeek 响应格式异常。")

    available = _decimal(
        _first(info, ("total_balance", "totalBalance", "balance")),
        "total_balance",
    )
    currency = str(info.get("currency") or "CNY").upper()
    return ParsedBalance(available=available, currency=currency, metric="余额")


def parse_zhipu(payload: dict[str, Any]) -> ParsedBalance:
    code = str(payload.get("code") if payload.get("code") is not None else "")
    success = payload.get("success")

    if success is False or (code and code not in {"0", "200"}):
        message = _payload_message(payload, "智谱 AI 返回异常。")
        if _looks_like_auth(message, code):
            raise AuthError("API Key 无效或无权访问。", code=code, hint=message)
        raise UpstreamError(message, code=code)

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    value = _first(data, ("availableBalance", "balance", "availBalance"))
    if value is None:
        raise UpstreamError("智谱 AI 响应中没有余额字段。")

    return ParsedBalance(available=_decimal(value, "balance"), currency="CNY", metric="余额")


def parse_modelscope(payload: dict[str, Any]) -> ParsedBalance:
    success = payload.get("success")
    if success is False or str(success).strip().lower() in {"false", "0"}:
        code = str(payload.get("code") or "")
        message = _payload_message(payload, "魔搭 ModelScope 返回失败。")
        if _looks_like_auth(message, code):
            raise AuthError("API Key 无效或已过期。", code=code, hint=message)
        raise UpstreamError(message, code=code)

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    value = _first(data, ("available_balance", "availableBalance", "available"))
    if value is None:
        raise UpstreamError("魔搭响应中没有可用魔粒字段。")

    return ParsedBalance(
        available=_decimal(value, "available_balance"),
        currency="魔粒",
        metric="魔粒",
    )


def kimi_currency(api_base: str) -> str:
    """Kimi's balance response has no currency field; the host decides it."""

    host = _host_of(api_base)
    if any(host == domain or host.endswith(f".{domain}") for domain in ("moonshot.ai", "kimi.ai")):
        return "USD"
    return "CNY"


def parse_kimi(payload: dict[str, Any]) -> ParsedBalance:
    error = payload.get("error")
    if isinstance(error, dict):
        code = str(error.get("code") or error.get("type") or "")
        message = str(error.get("message") or error.get("type") or "Kimi 返回异常。")
        message = sanitize_text(message)
        if _looks_like_auth(message, code):
            raise AuthError("Kimi API Key 无效或无权访问。", code=code, hint=message)
        raise UpstreamError(message, code=code)

    code = str(payload.get("code") if payload.get("code") is not None else "")
    status = payload.get("status")
    if status is False or (code and code not in {"0", "200"}):
        message = _payload_message(payload, "Kimi 返回异常。")
        if _looks_like_auth(message, code):
            raise AuthError("Kimi API Key 无效或无权访问。", code=code, hint=message)
        raise UpstreamError(message, code=code)

    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    value = _first(data, ("available_balance", "availableBalance", "balance", "available"))
    if value is None:
        raise UpstreamError("Kimi 响应中没有余额字段。")

    currency = str(data.get("currency") or "CNY").upper()
    return ParsedBalance(
        available=_decimal(value, "available_balance"),
        currency=currency,
        metric="余额",
    )


def parse_minimax_token_plan(payload: dict[str, Any]) -> ParsedBalance:
    base_resp = payload.get("base_resp") if isinstance(payload.get("base_resp"), dict) else {}
    raw_code = base_resp.get("status_code")
    if raw_code is None:
        raw_code = payload.get("status_code")
    code = "" if raw_code is None else str(raw_code)
    message = str(base_resp.get("status_msg") or payload.get("status_msg") or "")

    if code and code not in {"0", "200"}:
        hint = sanitize_text(message) if message else ""
        if code in {"1004", "2049"} or _looks_like_auth(message, code):
            raise AuthError(
                "MiniMax Token Plan API Key 无效或无权访问。",
                code=code,
                hint=hint,
            )
        raise UpstreamError(hint or "MiniMax Token Plan 返回异常。", code=code)

    models = payload.get("model_remains")
    if not isinstance(models, list) or not models:
        raise UpstreamError("MiniMax Token Plan 响应中没有额度信息。")

    candidates = [item for item in models if isinstance(item, dict)]
    if not candidates:
        raise UpstreamError("MiniMax Token Plan 响应格式异常。")

    # Prefer the shared "general" pool, then fall back to any model that exposes
    # a usable window.
    candidates.sort(
        key=lambda item: 0 if str(item.get("model_name", "")).lower() == "general" else 1
    )
    for model in candidates:
        interval_text, interval_value = _window_text(
            _first(
                model,
                (
                    "current_interval_remaining_percent",
                    "current_interval_remainingPercent",
                ),
            ),
            model.get("current_interval_status"),
            "current_interval_remaining_percent",
        )
        weekly_text, weekly_value = _window_text(
            _first(
                model,
                (
                    "current_weekly_remaining_percent",
                    "current_weekly_remainingPercent",
                ),
            ),
            model.get("current_weekly_status"),
            "current_weekly_remaining_percent",
        )

        parsed = _quota_balance(interval_text, interval_value, weekly_text, weekly_value)
        if parsed is not None:
            return parsed

    raise UpstreamError("MiniMax Token Plan 响应中没有可用的 5 小时或周额度。")


def parse_ollama(payload: dict[str, Any]) -> ParsedBalance:
    included = payload.get("included") if isinstance(payload.get("included"), dict) else {}
    purchased = payload.get("purchased") if isinstance(payload.get("purchased"), dict) else {}

    def window(name: str, field: str) -> tuple[str, Decimal | None]:
        item = included.get(name)
        if not isinstance(item, dict):
            return "", None
        return _window_text(item.get("remaining_percent"), None, field)

    interval_text, interval_value = window("session", "included.session.remaining_percent")
    weekly_text, weekly_value = window("weekly", "included.weekly.remaining_percent")
    parsed = _quota_balance(interval_text, interval_value, weekly_text, weekly_value)
    if parsed is not None:
        return parsed

    balances: list[Decimal] = []
    for mapping, field in (
        (included, "included.balance_usd"),
        (purchased, "purchased.balance_usd"),
    ):
        value = _first(mapping, ("balance_usd", "balanceUsd"))
        if value is not None:
            balances.append(_decimal(value, field))

    if balances:
        return ParsedBalance(
            available=sum(balances, Decimal("0")),
            currency="USD",
            metric="余额",
        )

    monthly_text, monthly_value = window("monthly", "included.monthly.remaining_percent")
    if monthly_text:
        return ParsedBalance(
            available=monthly_value if monthly_value is not None else Decimal("0"),
            currency="%",
            metric="月剩余",
            value_text=monthly_text,
            metric_text="月剩余",
        )

    raise UpstreamError("Ollama Cloud 响应中没有余额信息。")


def parse_302ai(payload: dict[str, Any]) -> ParsedBalance:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    value = _first(data, ("balance", "available_balance", "availableBalance"))
    if value is None:
        raise UpstreamError("302.AI 响应中没有余额字段。")

    currency = str(data.get("currency") or "USD").upper()
    return ParsedBalance(
        available=_decimal(value, "balance"),
        currency=currency,
        metric="余额",
    )


def parse_ppio(payload: dict[str, Any]) -> ParsedBalance:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    value = _first(data, ("availableBalance", "available_balance", "balance"))
    if value is None:
        raise UpstreamError("PPIO 响应中没有可用余额字段。")

    amount = _decimal(value, "availableBalance") / Decimal("10000")
    return ParsedBalance(available=amount, currency="CNY", metric="余额")


PARSERS = {
    "deepseek": parse_deepseek,
    "zhipu": parse_zhipu,
    "modelscope": parse_modelscope,
    "kimi": parse_kimi,
    "minimax_token_plan": parse_minimax_token_plan,
    "ollama": parse_ollama,
    "302ai": parse_302ai,
    "ppio": parse_ppio,
}
