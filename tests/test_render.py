"""Tests for row building, image rendering and the plain-text fallback."""

from __future__ import annotations

import os
import unittest
from decimal import Decimal

from PIL import Image

from src.accounts import Account
from src.errors import AuthError
from src.format import format_report
from src.models import AccountResult, BalanceSnapshot
from src.render import build_rows, format_money, format_units, render_report


def _account(provider: str, base_url: str, label: str) -> Account:
    return Account(provider=provider, api_key="sk-abcdefgh", base_url=base_url, label=label)


def _success(provider: str, base_url: str, label: str, amount: str, currency: str, metric: str):
    account = _account(provider, base_url, label)
    return AccountResult(
        account=account,
        balance=BalanceSnapshot(
            account=account,
            available=Decimal(amount),
            currency=currency,
            metric=metric,
        ),
    )


def _quota(
    provider: str,
    base_url: str,
    label: str,
    value_text: str,
    metric_text: str,
    secondary: str = "",
):
    account = _account(provider, base_url, label)
    return AccountResult(
        account=account,
        balance=BalanceSnapshot(
            account=account,
            available=Decimal("75"),
            currency="%",
            metric=metric_text,
            value_text=value_text,
            metric_text=metric_text,
            secondary=secondary,
        ),
    )


class FormattingTests(unittest.TestCase):
    def test_format_money(self) -> None:
        self.assertEqual(format_money(Decimal("1234.5"), "CNY"), "¥1,234.50")
        self.assertEqual(format_money(Decimal("7"), "USD"), "$7.00")

    def test_format_units(self) -> None:
        self.assertEqual(format_units(Decimal("249.50")), "249.5")
        self.assertEqual(format_units(Decimal("0")), "0")


class BuildRowsTests(unittest.TestCase):
    def test_rows_are_grouped_by_provider(self) -> None:
        results = [
            _success("modelscope", "https://www.modelscope.cn", "魔搭", "249.5", "魔粒", "魔粒"),
            _success("zhipu", "https://open.bigmodel.cn", "智谱", "320.50", "CNY", "余额"),
            _success("deepseek", "https://api.deepseek.com", "DeepSeek", "126.80", "CNY", "余额"),
        ]

        rows = build_rows(results)

        self.assertEqual([row.label for row in rows], ["DeepSeek", "智谱", "魔搭"])

    def test_modelscope_only_shows_available_magicubes(self) -> None:
        results = [
            _success("modelscope", "https://www.modelscope.cn", "魔搭", "249.5", "魔粒", "魔粒")
        ]

        row = build_rows(results)[0]

        self.assertEqual(row.metric, "可用魔粒")
        self.assertEqual(row.value, "249.5")
        self.assertNotIn("总余额", row.value)
        self.assertNotIn("冻结", row.value)

    def test_quota_row_shows_percentage_and_window_summary(self) -> None:
        results = [
            _quota(
                "minimax_token_plan",
                "https://api.minimaxi.com",
                "MiniMax",
                "75%",
                "5h 剩余",
                "5h: 75% · 周: 40%",
            )
        ]

        row = build_rows(results)[0]

        self.assertEqual(row.value, "75%")
        self.assertEqual(row.metric, "5h 剩余")
        self.assertEqual(row.extra, "5h: 75% · 周: 40%")

    def test_single_quota_window_has_no_extra_line(self) -> None:
        results = [
            _quota(
                "ollama",
                "https://ollama.com",
                "Ollama",
                "80%",
                "5h 剩余",
            )
        ]

        row = build_rows(results)[0]

        self.assertEqual(row.value, "80%")
        self.assertEqual(row.metric, "5h 剩余")
        self.assertEqual(row.extra, "")

    def test_failed_account_keeps_reason(self) -> None:
        account = _account("deepseek", "https://api.deepseek.com", "DeepSeek")
        results = [
            AccountResult(account=account, error=AuthError("API Key 无效或无权访问。", code="401"))
        ]

        row = build_rows(results)[0]

        self.assertTrue(row.failed)
        self.assertEqual(row.value, "查询失败")
        self.assertEqual(row.detail, "API Key 无效或无权访问。")


class RenderTests(unittest.TestCase):
    def test_render_report_creates_png(self) -> None:
        results = [
            _success("deepseek", "https://api.deepseek.com", "DeepSeek", "126.80", "CNY", "余额"),
            _success("modelscope", "https://www.modelscope.cn", "魔搭", "249.5", "魔粒", "魔粒"),
        ]

        path = render_report(results, now=0)
        try:
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.width, 720)
                self.assertGreater(image.height, 200)
        finally:
            os.unlink(path)

    def test_render_report_with_quota_window(self) -> None:
        results = [
            _quota(
                "minimax_token_plan",
                "https://api.minimaxi.com",
                "MiniMax",
                "75%",
                "5h 剩余",
                "5h: 75% · 周: 40%",
            )
        ]

        path = render_report(results, now=0)
        try:
            self.assertTrue(os.path.exists(path))
            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.width, 720)
        finally:
            os.unlink(path)

    def test_plain_text_fallback_includes_quota_windows(self) -> None:
        results = [
            _quota(
                "minimax_token_plan",
                "https://api.minimaxi.com",
                "MiniMax",
                "75%",
                "5h 剩余",
                "5h: 75% · 周: 40%",
            )
        ]

        text = format_report(results)

        self.assertIn("5h 剩余 75%", text)
        self.assertIn("5h: 75% · 周: 40%", text)

    def test_plain_text_fallback_has_no_frozen_amounts(self) -> None:
        results = [
            _success("modelscope", "https://www.modelscope.cn", "魔搭", "249.5", "魔粒", "魔粒"),
            _success("deepseek", "https://api.deepseek.com", "DeepSeek", "126.80", "CNY", "余额"),
        ]

        text = format_report(results)

        self.assertIn("可用魔粒 249.5", text)
        self.assertIn("余额 ¥126.80", text)
        self.assertNotIn("总余额", text)
        self.assertNotIn("冻结", text)


if __name__ == "__main__":
    unittest.main()
