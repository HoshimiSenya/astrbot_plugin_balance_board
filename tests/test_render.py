"""Tests for row building, image rendering and the plain-text fallback."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from decimal import Decimal

from PIL import Image

from src.accounts import Account
from src.cache import ImageCache
from src.errors import AuthError
from src.format import format_report
from src.models import AccountResult, BalanceSnapshot
from src.render import (
    build_rows,
    data_fetched_at,
    format_money,
    format_units,
    render_report,
    render_rows,
    report_footer,
)


def _account(provider: str, base_url: str, label: str) -> Account:
    return Account(provider=provider, api_key="sk-abcdefgh", base_url=base_url, label=label)


def _success(
    provider: str,
    base_url: str,
    label: str,
    amount: str,
    currency: str,
    metric: str,
    fetched_at: float | None = None,
):
    account = _account(provider, base_url, label)
    fetched: dict[str, float] = {} if fetched_at is None else {"fetched_at": fetched_at}
    return AccountResult(
        account=account,
        balance=BalanceSnapshot(
            account=account,
            available=Decimal(amount),
            currency=currency,
            metric=metric,
            **fetched,
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


class FooterTests(unittest.TestCase):
    """The footer reports when the data was fetched, not when it was drawn."""

    @staticmethod
    def _at(text: str) -> float:
        return time.mktime(time.strptime(text, "%Y-%m-%d %H:%M"))

    def test_newest_fetch_time_wins(self) -> None:
        results = [
            _success(
                "deepseek",
                "https://api.deepseek.com",
                "DeepSeek",
                "1",
                "CNY",
                "余额",
                fetched_at=self._at("2026-01-02 03:04"),
            ),
            _success(
                "zhipu",
                "https://open.bigmodel.cn",
                "智谱",
                "2",
                "CNY",
                "余额",
                fetched_at=self._at("2026-01-02 05:06"),
            ),
        ]

        self.assertEqual(data_fetched_at(results), self._at("2026-01-02 05:06"))
        self.assertEqual(
            report_footer(results),
            "更新于 2026-01-02 05:06 · 数据来自各平台官方余额接口",
        )

    def test_explicit_now_overrides_fetch_times(self) -> None:
        results = [
            _success(
                "deepseek",
                "https://api.deepseek.com",
                "DeepSeek",
                "1",
                "CNY",
                "余额",
                fetched_at=self._at("2026-01-02 03:04"),
            )
        ]

        pinned = self._at("2027-07-08 09:10")

        self.assertEqual(data_fetched_at(results, now=pinned), pinned)
        self.assertIn("更新于 2027-07-08 09:10", report_footer(results, now=pinned))

    def test_failed_results_fall_back_to_the_current_time(self) -> None:
        account = _account("deepseek", "https://api.deepseek.com", "DeepSeek")
        results = [AccountResult(account=account, error=AuthError("API Key 无效。", code="401"))]

        self.assertLessEqual(abs(data_fetched_at(results) - time.time()), 5.0)


class ReportCacheTests(unittest.TestCase):
    """The rendered PNG is reused while the query results stay identical."""

    def setUp(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self._cache = ImageCache(4)
        self._rendered: list[str] = []
        self._now = time.mktime(time.strptime("2026-01-02 03:04", "%Y-%m-%d %H:%M"))

    def tearDown(self) -> None:
        for path in self._rendered:
            if os.path.exists(path):
                os.unlink(path)

    def _results(self, amount: str = "126.80") -> list[AccountResult]:
        return [
            _success("deepseek", "https://api.deepseek.com", "DeepSeek", amount, "CNY", "余额"),
            _success("modelscope", "https://www.modelscope.cn", "魔搭", "249.5", "魔粒", "魔粒"),
        ]

    def _render(self, results: list[AccountResult], cache: ImageCache | None = None) -> str:
        path = render_report(results, now=self._now, cache=self._cache if cache is None else cache)
        self._rendered.append(path)
        return path

    def test_identical_results_reuse_the_previous_image(self) -> None:
        first = self._render(self._results())
        second = self._render(self._results())

        self.assertEqual(first, second)
        self.assertEqual(len(self._cache), 1)

    def test_changed_balance_renders_a_new_image(self) -> None:
        first = self._render(self._results("126.80"))
        second = self._render(self._results("100.00"))

        self.assertNotEqual(first, second)
        self.assertEqual(len(self._cache), 2)

    def test_changed_failure_reason_renders_a_new_image(self) -> None:
        results = self._results()
        failed = [
            AccountResult(
                account=results[0].account,
                error=AuthError("API Key 无效或无权访问。", code="401"),
            ),
            results[1],
        ]

        first = self._render(results)
        second = self._render(failed)

        self.assertNotEqual(first, second)

    def test_deleted_image_is_rendered_again(self) -> None:
        first = self._render(self._results())
        os.unlink(first)

        second = self._render(self._results())

        self.assertTrue(os.path.exists(second))
        self.assertNotEqual(first, second)

    def test_disabled_cache_renders_every_time(self) -> None:
        disabled = ImageCache(0)

        first = self._render(self._results(), cache=disabled)
        second = self._render(self._results(), cache=disabled)

        self.assertNotEqual(first, second)
        self.assertEqual(len(disabled), 0)

    def test_later_fetch_time_renders_a_new_image(self) -> None:
        fetched_at = time.mktime(time.strptime("2026-01-02 03:04", "%Y-%m-%d %H:%M"))

        def result(stamp: float) -> list[AccountResult]:
            return [
                _success(
                    "deepseek",
                    "https://api.deepseek.com",
                    "DeepSeek",
                    "126.80",
                    "CNY",
                    "余额",
                    fetched_at=stamp,
                )
            ]

        first = render_report(result(fetched_at), cache=self._cache)
        second = render_report(result(fetched_at + 60), cache=self._cache)
        self._rendered.extend([first, second])

        self.assertNotEqual(first, second)

    def test_explicit_output_is_never_replaced_by_a_hit(self) -> None:
        target = os.path.join(self._directory.name, "explicit.png")
        rows = build_rows(self._results())

        written = render_rows(rows, footer="固定页脚", output=target, cache=self._cache)

        self.assertEqual(written, target)
        self.assertTrue(os.path.exists(target))
        self.assertEqual(len(self._cache), 0)


if __name__ == "__main__":
    unittest.main()
