# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-30

### Added

- Automatic discovery of AstrBot model providers: API keys and base URLs are
  read from AstrBot's service provider configuration, so no key is entered or
  stored in the plugin config.
- Multi-provider balance board covering DeepSeek, Zhipu AI and ModelScope.
- Host-based provider detection for `deepseek.com`, `bigmodel.cn` /
  `zhipuai.cn` and `modelscope.cn` / `modelscope.ai`, with provider type/id
  hints when no base URL is configured.
- Safe skipping of custom OpenAI-compatible proxy hosts and unsupported
  platforms, so keys are only sent to the matching official balance endpoint.
- Automatic de-duplication by API key plus balance endpoint, so providers that
  share a wallet never appear twice; multiple distinct keys are kept and
  numbered.
- PNG report rendering with Pillow: provider-grouped rows with the platform's
  Chinese name as the headline, English name plus endpoint in the detail line,
  coloured accents, right-aligned amounts, failure reasons and an update
  timestamp.
- Provider-specific units: monetary balance for DeepSeek and Zhipu AI;
  available magicubes for ModelScope.
- Concurrent queries, TTL cache, per-user cooldown and retries with exponential
  backoff for timeouts, 429 and 5xx responses.
- Admin-only `/余额` command with `/余额查询`, `/查余额`, `/模型余额`,
  `/余额看板` and `/balance` aliases.
- Plain-text fallback when image rendering or delivery is unavailable.
- API key masking in every message and log line.
- `aiocqhttp` and `qq_official` platform support.
- Unit tests, Ruff configuration and GitHub Actions CI.

### Changed

- The project moved from a single-platform ModelScope magicube viewer to the
  auto-discovering multi-provider balance board described above.
- The plugin no longer exposes an `accounts`/API key configuration section; the
  provider list is re-read on every `/余额` query.
- The plugin description (`metadata.yaml` `desc`) is kept to a single short
  line so AstrBot's plugin-load log stays short.
- Version stays at 1.0.0 as the first release of the new layout.

[Unreleased]: https://github.com/HoshimiSenya/astrbot_plugin_balance_board/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/HoshimiSenya/astrbot_plugin_balance_board/releases/tag/v1.0.0