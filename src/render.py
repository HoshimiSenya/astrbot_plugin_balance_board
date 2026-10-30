"""Render the multi-provider balance report as a clean PNG card."""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import AccountResult
from .providers import PROVIDER_ORDER

TITLE = "余额看板"
WIDTH = 720
PAGE_PAD = 26
CARD_PAD_X = 34
CARD_RADIUS = 28
HEADER_HEIGHT = 118
ROW_HEIGHT = 82
FOOTER_HEIGHT = 40

BG_TOP = (243, 246, 250)
BG_BOTTOM = (229, 234, 242)
CARD = (255, 255, 255)
CARD_BORDER = (230, 234, 240)
INK = (23, 26, 32)
MUTED = (138, 145, 157)
LINE = (238, 241, 246)
DANGER = (217, 64, 72)

PROVIDER_COLORS = {
    "deepseek": (77, 107, 254),
    "zhipu": (14, 116, 233),
    "modelscope": (255, 122, 0),
}

CURRENCY_SYMBOLS = {"CNY": "¥", "USD": "$", "EUR": "€", "HKD": "HK$", "JPY": "¥"}

_TEMP_PREFIX = "astrbot-balance-board-"


@dataclass(frozen=True)
class Row:
    """One display row of the balance card."""

    label: str
    value: str
    metric: str
    color: tuple[int, int, int]
    detail: str = ""
    failed: bool = False


def format_money(amount: Decimal, currency: str) -> str:
    """Format a currency amount with two decimals and thousands separators."""

    symbol = CURRENCY_SYMBOLS.get(currency.upper(), f"{currency.upper()} ")
    try:
        value = amount.quantize(Decimal("0.01"))
    except (ArithmeticError, ValueError):  # pragma: no cover - defensive
        value = amount
    return f"{symbol}{value:,.2f}"


def format_units(amount: Decimal) -> str:
    """Format a non-monetary amount without trailing zeros."""

    if amount == amount.to_integral_value():
        return f"{amount:.0f}"
    return format(amount.normalize(), "f")


def build_rows(results: list[AccountResult]) -> list[Row]:
    """Convert query results into display rows, grouped by provider."""

    order = {provider: index for index, provider in enumerate(PROVIDER_ORDER)}
    ordered = sorted(
        enumerate(results),
        key=lambda item: (order.get(item[1].account.provider, len(order)), item[0]),
    )

    rows: list[Row] = []
    for _, result in ordered:
        account = result.account
        color = PROVIDER_COLORS.get(account.provider, (120, 128, 140))

        if result.balance is not None:
            balance = result.balance
            if balance.metric == "魔粒":
                value = format_units(balance.available)
            else:
                value = format_money(balance.available, balance.currency)
            rows.append(
                Row(
                    label=account.label,
                    value=value,
                    metric=account.spec.metric_display,
                    color=color,
                    detail=f"{account.spec.short_label} · {account.host}",
                )
            )
            continue

        message = result.error.message if result.error is not None else "查询失败。"
        rows.append(
            Row(
                label=account.label,
                value="查询失败",
                metric=account.spec.metric_display,
                color=(178, 186, 197),
                detail=message,
                failed=True,
            )
        )
    return rows


@lru_cache(maxsize=32)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if bold:
        candidates: list[tuple[str, int]] = [
            ("C:/Windows/Fonts/msyhbd.ttc", 0),
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("/System/Library/Fonts/PingFang.ttc", 1),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 1),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf", 0),
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
            ("DejaVuSans-Bold.ttf", 0),
        ]
    else:
        candidates = [
            ("C:/Windows/Fonts/msyh.ttc", 0),
            ("/System/Library/Fonts/PingFang.ttc", 0),
            ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
            ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf", 0),
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
            ("DejaVuSans.ttf", 0),
        ]

    for path, index in candidates:
        try:
            return ImageFont.truetype(path, size, index=index)
        except (OSError, TypeError):
            continue

    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - Pillow < 10.1
        return ImageFont.load_default()


def _ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: float,
) -> str:
    if max_width <= 0 or draw.textlength(text, font=font) <= max_width:
        return text

    trimmed = text
    while trimmed and draw.textlength(f"{trimmed}…", font=font) > max_width:
        trimmed = trimmed[:-1]
    return f"{trimmed}…"


def _vertical_gradient(size: tuple[int, int]) -> Image.Image:
    width, height = size
    top, bottom = BG_TOP, BG_BOTTOM
    strip = Image.new("RGB", (1, height))
    pixels = strip.load()
    assert pixels is not None
    for y in range(height):
        ratio = y / max(1, height - 1)
        pixels[0, y] = tuple(
            round(top[channel] + (bottom[channel] - top[channel]) * ratio) for channel in range(3)
        )
    return strip.resize((width, height))


def render_rows(
    rows: list[Row],
    *,
    title: str = TITLE,
    subtitle: str = "",
    footer: str = "",
    output: str | os.PathLike[str] | None = None,
) -> str:
    """Draw *rows* into a PNG file and return its path."""

    subtitle = subtitle or f"共 {len(rows)} 个账号"
    card_height = HEADER_HEIGHT + ROW_HEIGHT * len(rows) + FOOTER_HEIGHT
    image_height = card_height + PAGE_PAD * 2

    image = _vertical_gradient((WIDTH, image_height))

    left = PAGE_PAD
    top = PAGE_PAD
    right = WIDTH - PAGE_PAD
    bottom = image_height - PAGE_PAD

    # Soft drop shadow behind the card.
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    for offset, alpha in ((10, 14), (6, 20), (3, 28)):
        shadow_draw.rounded_rectangle(
            (left, top + offset, right, bottom + offset),
            radius=CARD_RADIUS,
            fill=(32, 42, 58, alpha),
        )
    image = Image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=CARD_RADIUS,
        fill=CARD,
        outline=CARD_BORDER,
        width=1,
    )

    x0 = left + CARD_PAD_X
    x1 = right - CARD_PAD_X

    draw.text((x0, top + 26), title, font=_font(34, bold=True), fill=INK)
    draw.text((x0, top + 78), subtitle, font=_font(15), fill=MUTED)

    divider_y = top + HEADER_HEIGHT
    draw.line((x0, divider_y, x1, divider_y), fill=LINE, width=1)

    y = divider_y
    for index, row in enumerate(rows):
        name_font = _font(23)
        detail_font = _font(13)
        metric_font = _font(13)

        draw.rounded_rectangle(
            (x0, y + 23, x0 + 5, y + 59),
            radius=3,
            fill=row.color,
        )

        label_left = x0 + 22
        label_max = (x1 - 250) - label_left
        label = _ellipsize(draw, row.label, name_font, label_max)
        draw.text((label_left, y + 15), label, font=name_font, fill=INK)

        if row.detail:
            detail = _ellipsize(draw, row.detail, detail_font, label_max)
            draw.text(
                (label_left, y + 48),
                detail,
                font=detail_font,
                fill=DANGER if row.failed else MUTED,
            )

        metric_width = draw.textlength(row.metric, font=metric_font)
        draw.text((x1 - metric_width, y + 14), row.metric, font=metric_font, fill=MUTED)

        value_max = 236
        value = row.value
        value_font = _font(27, bold=True)
        for size in (27, 24, 21):
            candidate = _font(size, bold=True)
            if draw.textlength(value, font=candidate) <= value_max:
                value_font = candidate
                break
        else:
            value_font = _font(21, bold=True)
            value = _ellipsize(draw, value, value_font, value_max)
        value_width = draw.textlength(value, font=value_font)
        draw.text(
            (x1 - value_width, y + 36),
            value,
            font=value_font,
            fill=DANGER if row.failed else INK,
        )

        if index < len(rows) - 1:
            draw.line((x0 + 22, y + ROW_HEIGHT, x1, y + ROW_HEIGHT), fill=LINE, width=1)
        y += ROW_HEIGHT

    footer = footer or "数据来自各平台官方余额接口，仅供参考"
    footer_font = _font(12)
    footer_width = draw.textlength(footer, font=footer_font)
    draw.text(
        ((WIDTH - footer_width) / 2, y + 13),
        footer,
        font=footer_font,
        fill=MUTED,
    )

    if output is None:
        fd, temp_name = tempfile.mkstemp(prefix=_TEMP_PREFIX, suffix=".png")
        os.close(fd)
        output = temp_name
        _prune_temp_files(Path(temp_name).parent)

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")
    return str(path)


def _prune_temp_files(directory: Path, max_age: float = 3600.0) -> None:
    """Best-effort cleanup of images rendered by previous runs."""

    now = time.time()
    for candidate in directory.glob(f"{_TEMP_PREFIX}*.png"):
        try:
            if now - candidate.stat().st_mtime > max_age:
                candidate.unlink()
        except OSError:
            continue


def render_report(results: list[AccountResult], *, now: float | None = None) -> str:
    """Render a full report (used by the plugin) and return the image path."""

    failed = sum(1 for result in results if not result.ok)
    providers = {result.account.provider for result in results}
    subtitle = f"{len(providers)} 个平台 · {len(results)} 个账号"
    if failed:
        subtitle += f" · {failed} 个查询失败"

    timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    footer = f"更新于 {timestamp} · 数据来自各平台官方余额接口"
    return render_rows(build_rows(results), subtitle=subtitle, footer=footer)
