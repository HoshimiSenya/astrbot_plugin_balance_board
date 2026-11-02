"""Render the multi-provider balance report as a clean PNG card."""

from __future__ import annotations

import hashlib
import os
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .cache import ImageCache
from .models import AccountResult
from .providers import PROVIDER_ORDER

TITLE = "余额看板"
WIDTH = 720
CARD_PAD_X = 34
CARD_RADIUS = 28
HEADER_HEIGHT = 118
ROW_HEIGHT = 82
ROW_HEIGHT_EXTRA = 100

CARD = (255, 255, 255)
INK = (23, 26, 32)
MUTED = (138, 145, 157)
LINE = (238, 241, 246)
DANGER = (217, 64, 72)

PROVIDER_COLORS = {
    "deepseek": (77, 107, 254),
    "zhipu": (14, 116, 233),
    "modelscope": (255, 122, 0),
    "kimi": (91, 101, 245),
    "minimax_token_plan": (239, 68, 68),
    "ollama": (17, 24, 39),
    "302ai": (124, 58, 237),
    "ppio": (16, 185, 129),
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
    extra: str = ""
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
            if balance.value_text:
                value = balance.value_text
                metric = balance.metric_text or account.spec.metric_display
            elif balance.metric == "魔粒":
                value = format_units(balance.available)
                metric = account.spec.metric_display
            else:
                value = format_money(balance.available, balance.currency)
                metric = account.spec.metric_display
            rows.append(
                Row(
                    label=account.label,
                    value=value,
                    metric=metric,
                    color=color,
                    detail=f"{account.spec.short_label} · {account.host}",
                    extra=balance.secondary,
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


def render_signature(rows: list[Row], *, title: str, subtitle: str) -> str:
    """Return a stable fingerprint of everything that ends up in the image."""

    parts = [title, subtitle]
    for row in rows:
        red, green, blue = row.color
        parts.append(
            "\x1e".join(
                (
                    row.label,
                    row.value,
                    row.metric,
                    f"{red},{green},{blue}",
                    row.detail,
                    row.extra,
                    "failed" if row.failed else "ok",
                )
            )
        )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


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


def render_rows(
    rows: list[Row],
    *,
    title: str = TITLE,
    subtitle: str = "",
    output: str | os.PathLike[str] | None = None,
    cache: ImageCache | None = None,
) -> str:
    """Draw *rows* into a transparent, full-bleed PNG card and return its path.

    With a *cache* and no explicit *output*, an image whose content matches an
    earlier render is returned as is, which skips the Pillow drawing entirely.
    """

    subtitle = subtitle or f"共 {len(rows)} 个账号"

    cache_key: str | None = None
    if output is None and cache is not None:
        cache_key = render_signature(rows, title=title, subtitle=subtitle)
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    row_heights = [ROW_HEIGHT_EXTRA if row.extra else ROW_HEIGHT for row in rows]
    image_height = HEADER_HEIGHT + sum(row_heights)

    # The card fills the whole canvas; only the rounded corners stay transparent.
    image = Image.new("RGBA", (WIDTH, image_height), (0, 0, 0, 0))
    scale = 4
    mask = Image.new("L", (WIDTH * scale, image_height * scale), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, WIDTH * scale - 1, image_height * scale - 1),
        radius=CARD_RADIUS * scale,
        fill=255,
    )
    mask = mask.resize((WIDTH, image_height), Image.LANCZOS)
    image.paste(Image.new("RGBA", (WIDTH, image_height), (*CARD, 255)), (0, 0), mask)
    draw = ImageDraw.Draw(image)

    left = 0
    top = 0
    right = WIDTH
    x0 = left + CARD_PAD_X
    x1 = right - CARD_PAD_X

    draw.text((x0, top + 26), title, font=_font(34, bold=True), fill=INK)
    draw.text((x0, top + 78), subtitle, font=_font(15), fill=MUTED)

    divider_y = top + HEADER_HEIGHT
    draw.line((x0, divider_y, x1, divider_y), fill=LINE, width=1)

    y = divider_y
    for index, row in enumerate(rows):
        row_height = row_heights[index]
        name_font = _font(23)
        detail_font = _font(13)
        extra_font = _font(12)
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

        if row.extra:
            extra = _ellipsize(draw, row.extra, extra_font, x1 - label_left)
            draw.text((label_left, y + 66), extra, font=extra_font, fill=MUTED)

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
            draw.line((x0 + 22, y + row_height, x1, y + row_height), fill=LINE, width=1)
        y += row_height

    if output is None:
        fd, temp_name = tempfile.mkstemp(prefix=_TEMP_PREFIX, suffix=".png")
        os.close(fd)
        output = temp_name
        _prune_temp_files(Path(temp_name).parent)

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")

    if cache_key is not None and cache is not None:
        cache.set(cache_key, str(path))
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


def render_report(
    results: list[AccountResult],
    *,
    cache: ImageCache | None = None,
) -> str:
    """Render a full report (used by the plugin) and return the image path."""

    failed = sum(1 for result in results if not result.ok)
    providers = {result.account.provider for result in results}
    subtitle = f"{len(providers)} 个平台 · {len(results)} 个账号"
    if failed:
        subtitle += f" · {failed} 个查询失败"

    return render_rows(build_rows(results), subtitle=subtitle, cache=cache)
