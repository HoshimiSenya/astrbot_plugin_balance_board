"""Discover balance accounts from AstrBot's configured model providers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .constants import MAX_ACCOUNTS
from .providers import PROVIDERS, ProviderSpec, detect_provider
from .security import normalize_api_key


@dataclass(frozen=True)
class Account:
    """One provider credential that can be queried for a balance."""

    provider: str
    api_key: str
    base_url: str
    label: str = ""

    @property
    def spec(self) -> ProviderSpec:
        return PROVIDERS[self.provider]

    @property
    def host(self) -> str:
        return urlsplit(self.base_url).netloc

    @property
    def cache_key(self) -> str:
        digest = hashlib.sha256(f"{self.base_url}\n{self.api_key}".encode()).hexdigest()
        return digest


@dataclass
class Discovery:
    """Result of scanning AstrBot's provider list."""

    accounts: list[Account] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.accounts)


def balance_base_url(api_base: Any, spec: ProviderSpec) -> str:
    """Return the root URL that hosts the provider's balance endpoint.

    AstrBot provider base URLs include OpenAI-style paths such as ``/v1`` or
    ``/api/paas/v4``; the balance endpoints live at the host root. ModelScope's
    balance API only exists on the community site, so it always uses the
    canonical host even when the chat endpoint points at ``api-inference``.
    """

    if spec.id == "modelscope":
        return spec.default_base_url

    raw = str(api_base or "").strip()
    if not raw:
        return spec.default_base_url
    if "://" not in raw:
        raw = f"https://{raw}"

    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return spec.default_base_url
    if any(character.isspace() for character in parts.netloc):
        return spec.default_base_url

    return f"{parts.scheme}://{parts.netloc}"


def discover_accounts(providers: Iterable[Any] | None) -> Discovery:
    """Build de-duplicated accounts from AstrBot provider instances.

    Each provider contributes one account per configured API key, identified by
    ``(api_key, balance base URL)``. Unsupported providers are reported in
    ``unsupported`` so the caller can log them once per query.
    """

    discovery = Discovery()
    seen: set[tuple[str, str]] = set()
    accounts: list[Account] = []

    for provider in providers or ():
        config = _provider_config(provider)
        if not config:
            continue

        api_base = _first_string(config, ("api_base", "api_base_url", "base_url", "url"))
        spec = detect_provider(
            api_base=api_base,
            type_name=_first_string(config, ("type", "provider_type")),
            provider_name=_first_string(config, ("provider", "source")),
            provider_id=_first_string(config, ("id", "name")),
        )
        if spec is None:
            display = _provider_display(config)
            if display and display not in discovery.unsupported:
                discovery.unsupported.append(display)
            continue

        keys, key_warnings = _provider_keys(provider, config)
        discovery.warnings.extend(key_warnings)
        if not keys:
            discovery.warnings.append(f"{_provider_display(config)}：未找到 API Key，已跳过。")
            continue

        label = _provider_label(config)
        base_url = balance_base_url(api_base, spec)

        for key in keys:
            dedupe_key = (key, base_url.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            if len(accounts) >= MAX_ACCOUNTS:
                message = f"账号数量超过上限 {MAX_ACCOUNTS}，其余条目已忽略。"
                if message not in discovery.warnings:
                    discovery.warnings.append(message)
                break

            accounts.append(Account(provider=spec.id, api_key=key, base_url=base_url, label=label))

    discovery.accounts = _assign_labels(accounts)
    discovery.warnings = _unique(discovery.warnings)
    return discovery


def _provider_config(provider: Any) -> dict[str, Any]:
    """Read the configuration mapping from a provider instance or mapping."""

    for attribute in ("provider_config", "config"):
        config = _as_mapping(getattr(provider, attribute, None))
        if config:
            return config
    return _as_mapping(provider)


_CONFIG_FIELDS = (
    "id",
    "name",
    "title",
    "remark",
    "nickname",
    "type",
    "provider_type",
    "provider",
    "source",
    "api_base",
    "api_base_url",
    "base_url",
    "url",
    "key",
    "api_key",
    "api_keys",
)


def _as_mapping(value: Any) -> dict[str, Any]:
    """Best-effort conversion of dict-like provider configs to a plain dict."""

    if isinstance(value, Mapping):
        return dict(value)
    getter = getattr(value, "get", None)
    if not callable(getter):
        return {}

    config: dict[str, Any] = {}
    for name in _CONFIG_FIELDS:
        try:
            item = getter(name)
        except Exception:  # pragma: no cover - defensive around AstrBot internals
            continue
        if item is not None:
            config[name] = item
    return config


def _first_string(config: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = config.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _provider_keys(provider: Any, config: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Collect every usable API key of one provider."""

    raw: list[Any] = []
    for name in ("key", "api_key", "api_keys"):
        value = config.get(name)
        if isinstance(value, str):
            raw.append(value)
        elif isinstance(value, (list, tuple, set)):
            raw.extend(value)

    getter = getattr(provider, "get_current_key", None)
    if callable(getter):
        try:
            current = getter()
        except Exception:  # pragma: no cover - defensive around AstrBot internals
            current = None
        if isinstance(current, str) and current.strip():
            raw.append(current)

    keys: list[str] = []
    local_seen: set[str] = set()
    warnings: list[str] = []

    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            key = normalize_api_key(item)
        except ValueError as exc:
            message = f"{_provider_display(config)}：{exc} 已跳过。"
            if message not in warnings:
                warnings.append(message)
            continue

        if key not in local_seen:
            local_seen.add(key)
            keys.append(key)

    return keys, warnings


def _provider_label(config: Mapping[str, Any]) -> str:
    """Use an explicit display name when the provider config provides one."""

    for name in ("name", "title", "remark", "nickname"):
        value = config.get(name)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:40]
    return ""


def _provider_display(config: Mapping[str, Any]) -> str:
    """Short provider identifier used in warnings and logs (never a key)."""

    provider_id = _first_string(config, ("id",))
    if provider_id:
        prefix = provider_id.split("/", 1)[0].strip()
        return prefix or provider_id
    return _first_string(config, ("type", "provider", "name")) or "未知供应商"


def _assign_labels(accounts: list[Account]) -> list[Account]:
    """Give duplicate display names a stable ``#n`` suffix."""

    counts: dict[str, int] = {}
    for account in accounts:
        base = account.label or account.spec.label
        counts[base] = counts.get(base, 0) + 1

    seen: dict[str, int] = {}
    labelled: list[Account] = []
    for account in accounts:
        name = account.label or account.spec.label
        if counts[name] > 1:
            seen[name] = seen.get(name, 0) + 1
            name = f"{name} #{seen[name]}"
        labelled.append(
            Account(
                provider=account.provider,
                api_key=account.api_key,
                base_url=account.base_url,
                label=name,
            )
        )
    return labelled


def _unique(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique
