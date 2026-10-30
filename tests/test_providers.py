"""Tests for provider response parsers."""

from __future__ import annotations

import unittest
from decimal import Decimal

from src.errors import AuthError, UpstreamError
from src.providers import parse_deepseek, parse_modelscope, parse_zhipu


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


if __name__ == "__main__":
    unittest.main()
