"""Tests for provider response parsers."""

from __future__ import annotations

import unittest
from decimal import Decimal

from src.errors import AuthError, UpstreamError
from src.providers import (
    kimi_currency,
    parse_302ai,
    parse_deepseek,
    parse_kimi,
    parse_minimax_token_plan,
    parse_modelscope,
    parse_ollama,
    parse_ppio,
    parse_zhipu,
)


class DeepSeekParserTests(unittest.TestCase):
    def test_reads_cny_balance(self) -> None:
        payload = {
            "balance_infos": [
                {"currency": "USD", "total_balance": "1.00"},
                {"currency": "CNY", "total_balance": "126.80"},
            ]
        }

        parsed = parse_deepseek(payload)

        self.assertEqual(parsed.available, Decimal("126.80"))
        self.assertEqual(parsed.currency, "CNY")
        self.assertEqual(parsed.metric, "余额")

    def test_falls_back_to_first_entry(self) -> None:
        payload = {"balance_infos": [{"currency": "USD", "total_balance": "2.50"}]}

        parsed = parse_deepseek(payload)

        self.assertEqual(parsed.available, Decimal("2.50"))
        self.assertEqual(parsed.currency, "USD")

    def test_missing_infos_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_deepseek({})


class ZhipuParserTests(unittest.TestCase):
    def test_reads_available_balance(self) -> None:
        payload = {"code": 200, "success": True, "data": {"availableBalance": "320.50"}}

        parsed = parse_zhipu(payload)

        self.assertEqual(parsed.available, Decimal("320.50"))
        self.assertEqual(parsed.metric, "余额")

    def test_failure_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_zhipu({"code": 500, "message": "server error"})


class ModelScopeParserTests(unittest.TestCase):
    def test_reads_only_available_balance(self) -> None:
        payload = {
            "success": True,
            "data": {
                "total_balance": 500.0,
                "available_balance": 249.5,
                "frozen_amount": 12.0,
            },
        }

        parsed = parse_modelscope(payload)

        self.assertEqual(parsed.available, Decimal("249.5"))
        self.assertEqual(parsed.currency, "魔粒")
        self.assertEqual(parsed.metric, "魔粒")

    def test_success_false_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_modelscope({"success": False, "message": "unknown"})

    def test_invalid_token_raises_auth_error(self) -> None:
        with self.assertRaises(AuthError):
            parse_modelscope({"success": False, "code": "401", "message": "unauthorized token"})

    def test_missing_available_field_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_modelscope({"success": True, "data": {"total_balance": 1}})


class KimiParserTests(unittest.TestCase):
    def test_reads_available_balance(self) -> None:
        payload = {
            "data": {
                "available_balance": "88.80",
                "voucher_balance": "20.00",
                "cash_balance": "68.80",
            }
        }

        parsed = parse_kimi(payload)

        self.assertEqual(parsed.available, Decimal("88.80"))
        self.assertEqual(parsed.currency, "CNY")
        self.assertEqual(parsed.metric, "余额")

    def test_error_payload_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_kimi({"error": {"message": "quota service unavailable"}})

    def test_missing_balance_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_kimi({"data": {}})

    def test_in_band_failure_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_kimi({"code": 40100, "status": False, "data": {}})

    def test_currency_depends_on_region_host(self) -> None:
        self.assertEqual(kimi_currency("https://api.moonshot.cn/v1"), "CNY")
        self.assertEqual(kimi_currency("https://api.moonshot.ai/v1"), "USD")
        self.assertEqual(kimi_currency("https://api.kimi.ai/v1"), "USD")


class MiniMaxTokenPlanParserTests(unittest.TestCase):
    def test_reads_both_windows(self) -> None:
        payload = {
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "model_remains": [
                {
                    "model_name": "general",
                    "current_interval_remaining_percent": 75,
                    "current_interval_status": 1,
                    "current_weekly_remaining_percent": 40,
                    "current_weekly_status": 1,
                }
            ],
        }

        parsed = parse_minimax_token_plan(payload)

        self.assertEqual(parsed.available, Decimal("75"))
        self.assertEqual(parsed.currency, "%")
        self.assertEqual(parsed.value_text, "75%")
        self.assertEqual(parsed.metric_text, "5h 剩余")
        self.assertEqual(parsed.secondary, "5h: 75% · 周: 40%")

    def test_inactive_weekly_window_is_hidden(self) -> None:
        payload = {
            "base_resp": {"status_code": 0},
            "model_remains": [
                {
                    "current_interval_remaining_percent": 80,
                    "current_interval_status": 1,
                    "current_weekly_remaining_percent": 0,
                    "current_weekly_status": 0,
                }
            ],
        }

        parsed = parse_minimax_token_plan(payload)

        self.assertEqual(parsed.value_text, "80%")
        self.assertEqual(parsed.metric_text, "5h 剩余")
        self.assertEqual(parsed.secondary, "")

    def test_exhausted_window_without_percentage_shows_zero(self) -> None:
        payload = {
            "base_resp": {"status_code": 0},
            "model_remains": [
                {
                    "current_interval_status": 2,
                    "current_weekly_status": 0,
                }
            ],
        }

        parsed = parse_minimax_token_plan(payload)

        self.assertEqual(parsed.value_text, "0%")

    def test_auth_status_code_raises_auth_error(self) -> None:
        with self.assertRaises(AuthError):
            parse_minimax_token_plan(
                {"base_resp": {"status_code": 1004, "status_msg": "invalid api key"}}
            )

    def test_empty_model_remains_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_minimax_token_plan({"base_resp": {"status_code": 0}, "model_remains": []})


class OllamaParserTests(unittest.TestCase):
    def test_reads_included_and_purchased_balance(self) -> None:
        payload = {
            "included": {
                "balance_usd": 72.5,
                "allowance_usd": 100,
                "period": {"from": "2026-09-15T09:30:00Z", "until": "2026-10-15T09:30:00Z"},
            },
            "purchased": {"balance_usd": 25},
        }

        parsed = parse_ollama(payload)

        self.assertEqual(parsed.available, Decimal("97.5"))
        self.assertEqual(parsed.currency, "USD")
        self.assertEqual(parsed.metric, "余额")
        self.assertEqual(parsed.value_text, "")

    def test_legacy_session_and_weekly_windows(self) -> None:
        payload = {
            "included": {
                "session": {"remaining_percent": 75},
                "weekly": {"remaining_percent": 40},
            },
            "purchased": {"balance_usd": 25},
        }

        parsed = parse_ollama(payload)

        self.assertEqual(parsed.value_text, "75%")
        self.assertEqual(parsed.metric_text, "5h 剩余")
        self.assertEqual(parsed.secondary, "5h: 75% · 周: 40%")

    def test_monthly_window_is_used_when_no_balance(self) -> None:
        parsed = parse_ollama({"included": {"monthly": {"remaining_percent": 60}}})

        self.assertEqual(parsed.value_text, "60%")
        self.assertEqual(parsed.metric_text, "月剩余")

    def test_empty_payload_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_ollama({})


class OtherProviderParserTests(unittest.TestCase):
    def test_302ai_reads_balance(self) -> None:
        parsed = parse_302ai({"data": {"balance": "12.34"}})

        self.assertEqual(parsed.available, Decimal("12.34"))
        self.assertEqual(parsed.currency, "USD")
        self.assertEqual(parsed.metric, "余额")

    def test_ppio_converts_scaled_cny(self) -> None:
        parsed = parse_ppio({"availableBalance": "123456"})

        self.assertEqual(parsed.available, Decimal("12.3456"))
        self.assertEqual(parsed.currency, "CNY")
        self.assertEqual(parsed.metric, "余额")

    def test_ppio_missing_balance_raises(self) -> None:
        with self.assertRaises(UpstreamError):
            parse_ppio({"cashBalance": "1"})


if __name__ == "__main__":
    unittest.main()
