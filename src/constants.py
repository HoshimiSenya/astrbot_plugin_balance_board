"""Plugin-wide constants."""

from __future__ import annotations

PLUGIN_NAME = "astrbot_plugin_balance_board"
PLUGIN_DISPLAY_NAME = "余额看板"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "星见千夜"
REPO_URL = "https://github.com/HoshimiSenya/astrbot_plugin_balance_board"

MAX_RESPONSE_BYTES = 256 * 1024
MAX_ACCOUNTS = 30

USER_AGENT = f"{PLUGIN_NAME}/{PLUGIN_VERSION} (+{REPO_URL})"
