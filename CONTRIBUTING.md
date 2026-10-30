# Contributing

Thanks for your interest in improving **余额看板**! This document describes how
to set up the project, run checks, and submit a pull request.

## Before you start

- Search existing [issues](https://github.com/HoshimiSenya/astrbot_plugin_balance_board/issues)
  before opening a new one.
- For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
- Never paste a real API key into an issue, PR, test, log or screenshot.

## Development setup

```bash
git clone https://github.com/HoshimiSenya/astrbot_plugin_balance_board
cd astrbot_plugin_balance_board

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements-dev.txt
```

The unit tests only import `src/`, not AstrBot itself, so you can run them
without installing the bot:

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Provider discovery is covered with fake provider objects; when changing it,
verify the shape of AstrBot's `provider_config` (`id`, `type`, `api_base`,
`key`) against a real AstrBot version.

If you change platform-specific behavior, please also test in a real AstrBot
instance with the relevant adapter.

## Project layout

| Path | Purpose |
|---|---|
| `main.py` | AstrBot entry point, provider discovery and concurrent queries |
| `src/accounts.py` | Provider discovery, key extraction, endpoint normalisation, dedupe |
| `src/client.py` | Shared HTTP client, retries and error mapping |
| `src/providers.py` | Provider detection, specs and response parsers |
| `src/render.py` | Pillow image rendering |
| `src/format.py` | Plain-text fallback |
| `src/security.py` | Key validation, masking and log sanitising |
| `src/cache.py` | TTL cache |
| `src/constants.py` | Version and plugin constants |
| `src/errors.py` | User-facing error types |
| `tests/` | Standard-library `unittest` suite |

## Adding a provider

1. Add a `ProviderSpec` entry to `PROVIDERS` in `src/providers.py`, including
   the balance path, currency, unit label and console URL.
2. Add a host marker to `_HOST_MARKERS` (and a name marker to `_NAME_MARKERS`
   if the provider can be configured without a base URL).
3. Implement a parser that returns `ParsedBalance` and register it in `PARSERS`.
4. Add a colour to `PROVIDER_COLORS` in `src/render.py`.
5. Add detection and parser tests in `tests/test_discovery.py` and
   `tests/test_providers.py`.
6. Update the provider table in `README.md` and `README_EN.md`.

## Coding guidelines

- Target Python 3.10+.
- Keep `src/` independent of AstrBot imports where possible so it stays testable.
- Use `astrbot.api.logger` in `main.py`; never log raw API keys.
- Keep user-facing fallback text in `src/format.py`.
- Add or update tests for behavior changes.
- Keep error messages actionable: say what failed and what the user can do.

## Commit messages

Conventional Commits are appreciated:

```text
feat: discover keys from a new provider config shape
fix: dedupe equivalent balance endpoints with trailing paths
docs: update provider key links
test: cover modelscope available balance
chore: polish rendered card footer
```

## Pull requests

1. Fork the repository and create a topic branch.
2. Make focused changes; avoid unrelated formatting churn.
3. Run the checks above.
4. Fill in the PR template, including how you tested the change.
5. Confirm that no real API key appears in the diff.

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).