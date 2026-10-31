"""Plain-text fallback used when image rendering is unavailable."""

from __future__ import annotations

from .models import AccountResult
from .render import format_money, format_units

_DIVIDER = "━━━━━━━━━━━━━━━"


def format_report(results: list[AccountResult]) -> str:
    """Build a short text card mirroring the rendered image."""

    lines = ["🧩 余额看板", _DIVIDER]

    for result in results:
        account = result.account
        metric = account.spec.metric_display
        if result.balance is not None:
            balance = result.balance
            if balance.value_text:
                label = balance.metric_text or metric
                value = f"{label} {balance.value_text}"
                if balance.secondary:
                    value += f"（{balance.secondary}）"
            elif account.provider == "modelscope":
                value = f"{metric} {format_units(balance.available)}"
            else:
                value = f"{metric} {format_money(balance.available, balance.currency)}"
            lines.append(f"{account.label}：{value}")
        else:
            message = result.error.message if result.error is not None else "查询失败。"
            lines.append(f"{account.label}：查询失败（{message}）")

    lines.append(_DIVIDER)
    lines.append("数据来自各平台官方余额接口，仅供参考。")
    return "\n".join(lines)


def format_no_accounts() -> str:
    return "\n".join(
        [
            "🧩 余额看板",
            _DIVIDER,
            "未在 AstrBot 的「模型供应商」中找到可查询余额的配置。",
            "",
            "自动支持：DeepSeek、智谱 AI、魔搭 ModelScope、Kimi、MiniMax Token Plan、",
            "Ollama Cloud、302.AI、PPIO。",
            "请先在 AstrBot 管理面板 → 服务提供商 中添加对应平台并填写 API Key，",
            "然后重新发送 /余额。",
        ]
    )


def format_cooldown(seconds: float) -> str:
    return f"⏳ 查询太频繁，请 {seconds:.1f} 秒后再试。"


def format_internal_error() -> str:
    return "❌ 查询失败：插件内部错误，请查看 AstrBot 日志。"
