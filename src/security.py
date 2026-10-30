"""API key validation, masking and log sanitising helpers."""

from __future__ import annotations

import re

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{8,512}$")
_SECRET_TOKEN_RE = re.compile(r"\b(?:sk|ms)-[A-Za-z0-9._~-]{6,}")


def normalize_api_key(raw: str) -> str:
    """Validate and normalise an API key.

    Keys are only allowed to contain characters that are safe inside an HTTP
    header, so a pasted value can never inject extra headers.

    Raises:
        ValueError: if the key is empty or contains unexpected characters.
    """

    key = (raw or "").strip()
    if key.lower().startswith("bearer "):
        key = key[7:].strip()

    if not key:
        raise ValueError("API Key 不能为空。")

    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError(
            "API Key 格式不正确：只能包含字母、数字、点、下划线、波浪线和短横线（8-512 个字符）。"
        )

    return key


def mask_key(key: str) -> str:
    """Return a safe, recognisable representation of a secret."""

    if not key:
        return "（未配置）"

    if len(key) <= 8:
        if len(key) <= 2:
            return "*" * len(key)
        return f"{key[0]}{'*' * (len(key) - 2)}{key[-1]}"

    return f"{key[:4]}…{key[-4:]}"


def sanitize_text(text: str, secret: str = "", limit: int = 160) -> str:
    """Strip secrets from an upstream message and cap its length."""

    text = str(text or "")
    if secret:
        text = text.replace(secret, mask_key(secret))
    text = _SECRET_TOKEN_RE.sub(lambda match: mask_key(match.group(0)), text)
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text
