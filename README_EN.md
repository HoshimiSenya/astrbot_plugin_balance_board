<div align="center">

<img src="logo.png" width="120" alt="Balance Board Logo">

# Balance Board

**Reads AstrBot's model providers automatically — every balance in one clean image**

[![AstrBot](https://img.shields.io/badge/AstrBot-%E2%89%A54.5-5865f2?style=flat-square)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-1.1.0-22c55e?style=flat-square)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-3b82f6?style=flat-square)](LICENSE)

[简体中文](README.md) · English

</div>

> Unofficial community plugin, not affiliated with DeepSeek, Zhipu AI, ModelScope, Kimi, MiniMax, Ollama, 302.AI or PPIO.  
> The plugin only reads balance data; it never checks in, tops up or spends any credits.

## Features

- 🔑 **No keys in the plugin**: API keys and base URLs are read directly from AstrBot's configured model providers
- 🧾 **All providers at once**: every supported provider configured in AstrBot is queried with one `/余额` command
- 🔁 **Automatic de-duplication**: provider entries sharing the same API key and balance endpoint are queried once and shown once
- 🖼 **Image output**: results are rendered as a clean PNG card — the big text shows the platform's Chinese name, the small line shows its English name and balance endpoint
- 💎 **Provider-aware units**: DeepSeek, Zhipu AI, Kimi, 302.AI, PPIO and Ollama Cloud show account balance, ModelScope shows available magicubes, and MiniMax Token Plan shows 5-hour / weekly remaining quota
- 📊 **Quota windows**: MiniMax Token Plan and legacy Ollama Cloud plans show 5-hour / weekly remaining percentages, with a summary line when both windows exist
- 🛡 **Safe matching**: keys are only sent when the base URL points at a supported provider's official host; custom OpenAI-compatible proxies are skipped
- ⚡ **Concurrency, cache and retries**: providers are queried concurrently, successes are cached with a TTL, and timeouts / 429 / 5xx are retried with backoff
- 🧠 **Privacy first**: keys are only sent to their own provider and are masked in messages and logs
- 📱 **Two adapters**: `aiocqhttp` (OneBot v11) and `qq_official` (QQ official bot)
- 🧩 **No backend**: the plugin calls the provider APIs directly

## Supported providers

| Provider | Displayed | Endpoint |
|---|---|---|
| [DeepSeek](https://platform.deepseek.com) | Account balance (`¥`) | `GET /user/balance` |
| [Zhipu AI](https://open.bigmodel.cn) | Account balance (`¥`) | `GET /api/biz/account/query-customer-account-report` |
| [ModelScope](https://modelscope.cn) | Available magicubes (魔粒) | `GET /openapi/v1/magicubes/balance` |
| [Kimi](https://platform.moonshot.cn) | Account balance (CN site `¥` / global site `$`) | `GET /v1/users/me/balance` |
| [MiniMax Token Plan](https://platform.minimaxi.com) | 5h / weekly remaining quota (`%`) | `GET /v1/token_plan/remains` |
| [Ollama Cloud](https://ollama.com) | Account balance (`$`) / legacy 5h and weekly quota | `GET /api/balance` |
| [302.AI](https://302.ai) | Account balance (`$`) | `GET /dashboard/balance` |
| [PPIO](https://ppio.com) | Account balance (`¥`) | `GET /openapi/v1/billing/balance/detail` |

| Messaging platform | Adapter | Status |
|---|---|---|
| OneBot v11 | `aiocqhttp` | ✅ Supported |
| QQ official bot | `qq_official` | ✅ Supported |

> The plugin sends an image (falling back to plain text if rendering fails) and uses no Markdown, buttons or platform-specific message segments, so both adapters behave identically.

## Install

### Plugin marketplace

Search for **“余额看板”** in the AstrBot plugin marketplace.

### Manual

```bash
cd AstrBot/data/plugins
git clone https://github.com/HoshimiSenya/astrbot_plugin_balance_board
pip install -r astrbot_plugin_balance_board/requirements.txt
```

Restart AstrBot and enable the plugin.

> Requires **AstrBot 4.5+ (4.x series)**. Registration is handled automatically via `metadata.yaml`; the deprecated `@register` decorator is not used.  
> Image rendering uses Pillow, already listed in `requirements.txt`.

## Configure providers in AstrBot

The plugin stores no keys. Everything comes from AstrBot's **service providers**:

1. Open the AstrBot admin panel → **Providers** → **Add provider**.
2. Pick a platform (DeepSeek / Zhipu / ModelScope / Kimi / MiniMax / Ollama / 302.AI / PPIO) or an OpenAI-compatible provider, then enter the API key.
3. Save and send `/余额` in chat.

| Provider | Console | Notes |
|---|---|---|
| DeepSeek | <https://platform.deepseek.com/api_keys> | Keys look like `sk-...`; base URL is usually `https://api.deepseek.com` or `.../v1` |
| Zhipu AI | <https://open.bigmodel.cn/usercenter/apikeys> | Base URL is usually `https://open.bigmodel.cn/api/paas/v4` |
| ModelScope | <https://modelscope.cn/my/myaccesstoken> | Tokens look like `ms-...`; chat base can be `https://api-inference.modelscope.cn/v1` |
| Kimi | <https://platform.moonshot.cn/console/api-keys> | Base URL is usually `https://api.moonshot.cn/v1`; the global site uses `https://api.moonshot.ai/v1` |
| MiniMax Token Plan | <https://platform.minimaxi.com/console/plan> | Only subscription Token Plan keys (`sk-cp-...`) are supported, not pay-as-you-go balance; base URL is usually `https://api.minimaxi.com/anthropic` |
| Ollama Cloud | <https://ollama.com/settings/keys> | Only the `ollama.com` cloud host is recognized; local `127.0.0.1:11434` is skipped |
| 302.AI | <https://302.ai> | Base URL is usually `https://api.302.ai/v1` |
| PPIO | <https://ppio.com> | Base URL can be `https://api.ppinfra.com/v3/openai` or `https://api.ppio.com/openai` |

> ⚠️ Keys are provider-specific. Add one provider per platform and do not paste a key into another provider's entry.

## Detection rules

The plugin primarily identifies the balance platform from the base URL host:

| Base URL contains | Detected as | Card display |
|---|---|---|
| `deepseek.com` | DeepSeek | Big text `DeepSeek`, small line `DeepSeek · endpoint` |
| `bigmodel.cn` / `zhipuai.cn` | Zhipu AI | Big text `智谱`, small line `Zhipu AI · endpoint` |
| `modelscope.cn` / `modelscope.ai` | ModelScope | Big text `魔搭`, small line `ModelScope · www.modelscope.cn` |
| `moonshot.cn` / `moonshot.ai` / `kimi.com` / `kimi.ai` | Kimi | Big text `Kimi`, small line `Kimi / Moonshot · endpoint` |
| MiniMax Token Plan type/id + `minimax.io` / `minimaxi.com` / `minimax.cn` | MiniMax Token Plan | Big text `MiniMax`, small line `Token Plan · endpoint` |
| `ollama.com` | Ollama Cloud | Big text `Ollama`, small line `Ollama Cloud · ollama.com` |
| `302.ai` / `302ai.com` | 302.AI | Big text `302.AI`, small line `302.AI · endpoint` |
| `ppio.com` / `ppinfra.com` | PPIO | Big text `PPIO`, small line `PPIO · api.ppio.com` |

- When a provider has no base URL, the provider type/id keywords (`deepseek`, `zhipu`, `modelscope`, `kimi`, `302ai`, `ppio`, …) are used as a hint.
- MiniMax is only recognized as Token Plan when the provider type/id explicitly contains `token_plan` / `token-plan`; regular pay-as-you-go MiniMax providers are skipped.
- Ollama is only recognized on the cloud host `ollama.com`; local Ollama (`127.0.0.1:11434`) has no balance endpoint and is skipped.
- **Custom OpenAI-compatible proxies** (e.g. `https://proxy.example.com/v1`) are skipped on purpose: their balance endpoint is unknown and sending the key to an official host would be unsafe.
- Unsupported platforms (OpenAI, Gemini, local Ollama, …) are skipped silently and never affect other providers.

## Commands

The default AstrBot command prefix is `/`. Commands are **admin-only** by default.

| Command | Aliases | Description |
|---|---|---|
| `/余额` | `/余额查询`, `/查余额`, `/模型余额`, `/余额看板`, `/balance` | Query every supported provider and send the rendered board |

The provider list is re-read on every query, so newly added or removed providers take effect immediately without reloading the plugin.

### Output

<div align="center">

![Rendered board](https://cdn.jsdelivr.net/gh/HoshimiSenya/astrbot_plugin_balance_board@main/docs/preview.png)

</div>

- One row per wallet: the coloured bar marks the provider, the big text is its Chinese name, and the small line shows the English name and balance host.
- Amounts are right-aligned; ModelScope rows show **available magicubes**, other money providers show **balance**, and MiniMax Token Plan / legacy Ollama Cloud plans show **5h remaining** or **weekly remaining** percentages.
- When both 5-hour and weekly quotas exist, a smaller summary line such as `5h: 75% · 周: 40%` is added under the row.
- Multiple distinct keys on one platform are numbered `#1`, `#2`.
- Failed accounts are shown in red with a short reason and do not affect the other rows.
- If rendering fails, the plugin falls back to a plain-text card.

## Plugin configuration

AstrBot admin panel → Plugins → **余额看板** → Config. There is **no API key field** — only query behaviour:

| Key | Default | Description |
|---|---|---|
| `cache_ttl` | `60` | Cache TTL in seconds; `0` disables the cache |
| `user_cooldown` | `5` | Per-user cooldown in seconds; `0` disables it |
| `request_timeout` | `10` | Per-request timeout in seconds |
| `proxy` | empty | Optional HTTP proxy, e.g. `http://127.0.0.1:7890` |
| `max_retries` | `2` | Retries for timeout / 429 / 5xx; authentication failures are never retried |

### De-duplication rules

- Identity is **API key + balance endpoint**. Provider names and model names are ignored.
- The same key appearing in several provider entries, or base URLs that differ only by `/v1`-style paths, count as one wallet.
- Every distinct key of a provider is queried; identical keys are collapsed.
- The same key on different balance hosts is treated as two accounts.
- At most 30 accounts are queried; extra entries are ignored and logged.

## How it works

```mermaid
flowchart LR
    A[/余额] --> B[Read AstrBot providers]
    B --> C[Detect platform by base URL]
    C --> D[Collect API keys]
    D --> E[Deduplicate by key + endpoint]
    E --> F[Query balance endpoints concurrently]
    F --> G[Parse results]
    G --> H[Render PNG board]
    H --> I[Send image]
```

| Provider | Parsed fields |
|---|---|
| DeepSeek | `balance_infos[].total_balance` (prefers `CNY`) |
| Zhipu AI | `data.availableBalance`, falling back to `balance` / `availBalance` |
| ModelScope | `data.available_balance` |
| Kimi | `data.available_balance`, falling back to `balance` / `available` |
| MiniMax Token Plan | `model_remains[].current_interval_remaining_percent` / `current_weekly_remaining_percent` |
| Ollama Cloud | `included.balance_usd` + `purchased.balance_usd`; legacy `included.session` / `included.weekly` `remaining_percent` |
| 302.AI | `data.balance`, falling back to `available_balance` |
| PPIO | `availableBalance` (unit: 1/10000 CNY, converted to `¥`) |

- Kimi's balance API does not return a currency; the CN site is shown as `¥` and the global site as `$`.
- Successes are reused within `cache_ttl`.
- Authentication failures are not retried; timeouts, 429 and 5xx use exponential backoff.
- Keys are masked before being shown, e.g. `sk-0123…cdef`.

## Security

- Keys are read from AstrBot's provider configuration; the plugin does not create or store a second copy.
- Requests are only made to supported providers' official hosts. Custom proxies and unsupported platforms are never contacted.
- No user data is stored.
- Keys are masked in every message and log line.
- Keys are stored as plain text in AstrBot's provider configuration. Restrict access to the data directory.
- Rotate a key immediately if it leaks.

## QQ official bot notes

- QQ official bots have a reply deadline. Increase `request_timeout` if provider APIs are slow.
- Image delivery depends on AstrBot's image support; the plugin falls back to plain text on failure.
- Commands are admin-only by default; adjust further in AstrBot's command management if needed.

## FAQ

<details>
<summary><b>“未在 AstrBot 的模型供应商中找到可查询余额的配置”</b></summary>

Add a DeepSeek, Zhipu AI, ModelScope, Kimi, MiniMax Token Plan, Ollama Cloud, 302.AI or PPIO
provider in AstrBot's **Providers** page with an API key. Only the platforms in the
supported-provider table above are recognized.
</details>

<details>
<summary><b>Why are only some providers shown?</b></summary>

- Unsupported platforms (OpenAI, Gemini, local Ollama, …) are skipped.
- Providers pointing at custom proxy hosts are skipped on purpose.
- Providers sharing the same key and endpoint are de-duplicated.
- Check the AstrBot log for the “skipped providers without a recognized balance endpoint” message.
</details>

<details>
<summary><b>Why does one platform show only one account?</b></summary>

Accounts are de-duplicated by **API key + balance endpoint**. If two provider entries use the
same key, they refer to the same wallet and are shown once.
</details>

<details>
<summary><b>HTTP 401 / invalid API key</b></summary>

- Check that the key in AstrBot's provider configuration is complete and has no surrounding spaces.
- Check that the key belongs to the configured platform.
- Confirm the key is still active in the provider console, then update the provider.
</details>

<details>
<summary><b>Why does ModelScope show magicubes?</b></summary>

ModelScope credits are called magicubes (魔粒), so the card shows available magicubes; other
platforms show the account balance.
</details>

<details>
<summary><b>Why is MiniMax missing?</b></summary>

Only the MiniMax **Token Plan** subscription quota is supported, not the regular pay-as-you-go
balance. Add a MiniMax Token Plan provider whose type/id contains `token_plan` or `token-plan`
and use the subscription key (usually starting with `sk-cp-`). Regular MiniMax providers are
skipped for safety.
</details>

<details>
<summary><b>Why is Ollama missing?</b></summary>

Only Ollama **Cloud** (`ollama.com`) is queried. Local Ollama has no balance endpoint, so
providers pointing at `127.0.0.1:11434` are skipped. For cloud models, set the base URL to
`https://ollama.com/v1` and enter an Ollama Cloud API key.
</details>

<details>
<summary><b>The image is not delivered</b></summary>

Check the AstrBot logs for rendering or upload errors. The plugin falls back to plain text when
rendering fails; also verify that Pillow and a CJK font are available on the server.
</details>

## Development

```bash
python -m venv .venv
pip install -r requirements-dev.txt

python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

The test suite does not require AstrBot to be installed.

### Layout

```text
main.py             AstrBot entry point, provider discovery and concurrent queries
src/accounts.py     Provider discovery, key extraction, endpoint normalisation, dedupe
src/client.py       Shared HTTP client, retries and error mapping
src/providers.py    Provider detection, specs and response parsers
src/render.py       Pillow image rendering
src/format.py       Plain-text fallback
src/security.py     Key validation and masking
tests/              Standard-library unittest suite
```

## License

[MIT](LICENSE)

## Disclaimer

This is an unofficial community project. Providers may change their APIs at any time.
Please follow each provider's terms of service and avoid excessive requests.