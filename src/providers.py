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


PROVIDER_ORDER: tuple[str, ...] = ("deepseek", "zhipu", "modelscope")


@dataclass(frozen=True)
class ParsedBalance:
    """Normalised balance returned by a provider parser."""

    available: Decimal
    currency: str
    metric: str


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

_HOST_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deepseek", ("deepseek.com",)),
    ("zhipu", ("bigmodel.cn", "zhipuai.cn")),
    ("modelscope", ("modelscope.cn", "modelscope.ai")),
)

_NAME_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("deepseek", ("deepseek",)),
    ("zhipu", ("zhipu", "bigmodel", "chatglm", "glm", "智谱")),
    ("modelscope", ("modelscope", "magicube", "魔搭")),
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
    """

    host = _host_of(api_base)
    if host:
        matched = _match_marker(host, _HOST_MARKERS)
        return PROVIDERS.get(matched) if matched else None

    identity = " ".join((type_name, provider_name, provider_id)).strip()
    matched = _match_marker(identity, _NAME_MARKERS)
    return PROVIDERS.get(matched) if matched else None


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

    try:
        amount = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise UpstreamError(f"响应字段 {field} 不是有效数字。") from exc

    if not amount.is_finite():
        raise UpstreamError(f"响应字段 {field} 不是有限数字。")

    return amount


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


PARSERS = {
    "deepseek": parse_deepseek,
    "zhipu": parse_zhipu,
    "modelscope": parse_modelscope,
}
