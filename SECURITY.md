# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | ✅ |
| < 1.0 | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Describe the issue, affected versions and reproduction steps.

If private reporting is unavailable, contact the maintainer through the
[GitHub profile](https://github.com/HoshimiSenya) and ask for a private channel.

Please include:

- Plugin version and AstrBot version
- Provider involved (DeepSeek / Zhipu AI / ModelScope)
- Platform adapter (`aiocqhttp` / `qq_official`)
- Steps to reproduce
- Impact assessment
- Any suggested fix

You should receive a response within a few days. Please allow time for a fix
before public disclosure.

## API key handling

This plugin reads the API keys that are already configured in AstrBot's
**service providers**. Please keep the following in mind:

- **Never paste a real key** into an issue, pull request, discussion, log or
  screenshot. Mask it as `sk-0123…cdef` or `ms-0123…cdef`.
- The plugin has **no key field of its own** and stores no key copy. Keys remain
  in AstrBot's provider configuration, which is plain text — restrict access to
  the AstrBot data directory.
- Balance requests are only sent when the provider's base URL points at a
  supported platform's official host. Custom OpenAI-compatible proxies and
  unsupported platforms are skipped, so keys are not forwarded to unintended
  destinations.
- Keys are masked in messages and logs, but **AstrBot or the platform may log
  raw command text**. The plugin never accepts keys as command arguments.
- If a key leaks, revoke it immediately at the provider console:
  - <https://platform.deepseek.com/api_keys>
  - <https://open.bigmodel.cn/usercenter/apikeys>
  - <https://modelscope.cn/my/myaccesstoken>

## Scope

The plugin only sends requests to the balance endpoints of DeepSeek, Zhipu AI
and ModelScope, selected from AstrBot's provider configuration. It does not
send keys to any third-party service. Reports about a provider's own service,
billing or account behavior should go to that provider's support.