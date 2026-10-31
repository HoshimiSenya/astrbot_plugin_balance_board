"""Tests for provider detection and account discovery."""

from __future__ import annotations

import unittest

from src.accounts import balance_base_url, discover_accounts
from src.providers import PROVIDERS, detect_provider


class FakeProvider:
    """Minimal stand-in for an AstrBot provider instance."""

    def __init__(self, config: dict, current_key: str | None = None, raises: bool = False):
        self.provider_config = config
        self._current_key = current_key
        self._raises = raises

    def get_current_key(self) -> str:
        if self._raises:
            raise RuntimeError("provider not ready")
        return self._current_key or ""


class DetectProviderTests(unittest.TestCase):
    def test_detects_by_host(self) -> None:
        cases = {
            "https://api.deepseek.com/v1": "deepseek",
            "https://open.bigmodel.cn/api/paas/v4": "zhipu",
            "https://api-inference.modelscope.cn/v1": "modelscope",
            "https://api.moonshot.cn/v1": "kimi",
            "https://api.moonshot.ai/v1": "kimi",
            "https://api.kimi.ai/v1": "kimi",
            "https://ollama.com/v1": "ollama",
            "https://api.302.ai/v1": "302ai",
            "https://api.ppinfra.com/v3/openai": "ppio",
        }

        for api_base, expected in cases.items():
            with self.subTest(api_base=api_base):
                spec = detect_provider(api_base=api_base)
                self.assertIsNotNone(spec)
                assert spec is not None
                self.assertEqual(spec.id, expected)

    def test_custom_proxy_host_is_not_guessed(self) -> None:
        spec = detect_provider(
            api_base="https://proxy.example.com/v1",
            type_name="openai_chat_completion",
            provider_id="deepseek/default",
        )

        self.assertIsNone(spec)

    def test_falls_back_to_type_and_id_without_base_url(self) -> None:
        self.assertEqual(
            detect_provider(type_name="openai_chat_completion", provider_id="deepseek/default").id,
            "deepseek",
        )
        self.assertEqual(detect_provider(type_name="zhipu_chat_completion").id, "zhipu")
        self.assertEqual(detect_provider(provider_id="modelscope/qwen").id, "modelscope")
        self.assertEqual(detect_provider(provider_id="moonshot/kimi-k2").id, "kimi")
        self.assertEqual(detect_provider(type_name="302ai_chat_completion").id, "302ai")
        self.assertEqual(detect_provider(provider_id="ppio/deepseek-v3").id, "ppio")
        self.assertEqual(detect_provider(type_name="minimax_token_plan").id, "minimax_token_plan")

    def test_generic_openai_provider_is_unsupported(self) -> None:
        self.assertIsNone(detect_provider(type_name="openai_chat_completion", provider_id="gpt-4o"))

    def test_minimax_token_plan_requires_identity(self) -> None:
        spec = detect_provider(
            api_base="https://api.minimaxi.com/anthropic",
            type_name="minimax_token_plan",
            provider_name="minimax-token-plan",
            provider_id="minimax-token-plan",
        )

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.id, "minimax_token_plan")

    def test_regular_minimax_provider_is_skipped(self) -> None:
        self.assertIsNone(
            detect_provider(
                api_base="https://api.minimaxi.com/v1",
                type_name="minimax_chat_completion",
                provider_id="minimax/default",
            )
        )

    def test_local_ollama_is_skipped(self) -> None:
        self.assertIsNone(
            detect_provider(
                api_base="http://127.0.0.1:11434/v1",
                type_name="ollama_chat_completion",
                provider_id="ollama/default",
            )
        )


class BalanceBaseUrlTests(unittest.TestCase):
    def test_strips_openai_paths(self) -> None:
        self.assertEqual(
            balance_base_url("https://api.deepseek.com/v1", PROVIDERS["deepseek"]),
            "https://api.deepseek.com",
        )
        self.assertEqual(
            balance_base_url("https://open.bigmodel.cn/api/paas/v4", PROVIDERS["zhipu"]),
            "https://open.bigmodel.cn",
        )

    def test_modelscope_uses_canonical_balance_host(self) -> None:
        self.assertEqual(
            balance_base_url("https://api-inference.modelscope.cn/v1", PROVIDERS["modelscope"]),
            "https://www.modelscope.cn",
        )

    def test_kimi_keeps_region_host(self) -> None:
        self.assertEqual(
            balance_base_url("https://api.moonshot.ai/v1", PROVIDERS["kimi"]),
            "https://api.moonshot.ai",
        )
        self.assertEqual(
            balance_base_url("https://api.moonshot.cn/v1", PROVIDERS["kimi"]),
            "https://api.moonshot.cn",
        )

    def test_minimax_token_plan_strips_anthropic_path(self) -> None:
        self.assertEqual(
            balance_base_url(
                "https://api.minimaxi.com/anthropic",
                PROVIDERS["minimax_token_plan"],
            ),
            "https://api.minimaxi.com",
        )

    def test_ollama_uses_cloud_host(self) -> None:
        self.assertEqual(
            balance_base_url("https://ollama.com/v1", PROVIDERS["ollama"]),
            "https://ollama.com",
        )

    def test_ppio_uses_canonical_billing_host(self) -> None:
        self.assertEqual(
            balance_base_url("https://api.ppinfra.com/v3/openai", PROVIDERS["ppio"]),
            "https://api.ppio.com",
        )

    def test_empty_or_invalid_url_uses_default(self) -> None:
        self.assertEqual(
            balance_base_url("", PROVIDERS["zhipu"]),
            PROVIDERS["zhipu"].default_base_url,
        )
        self.assertEqual(
            balance_base_url("not a url", PROVIDERS["zhipu"]),
            PROVIDERS["zhipu"].default_base_url,
        )


class DiscoverAccountsTests(unittest.TestCase):
    def test_discovers_supported_provider(self) -> None:
        provider = FakeProvider(
            {
                "id": "deepseek/default",
                "type": "openai_chat_completion",
                "api_base": "https://api.deepseek.com/v1",
                "key": ["sk-abcdefgh"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 1)
        account = discovery.accounts[0]
        self.assertEqual(account.provider, "deepseek")
        self.assertEqual(account.base_url, "https://api.deepseek.com")
        self.assertEqual(account.label, "DeepSeek")
        self.assertEqual(discovery.warnings, [])

    def test_deduplicates_same_key_and_base(self) -> None:
        configs = [
            {
                "id": "deepseek/default",
                "api_base": "https://api.deepseek.com",
                "key": ["sk-abcdefgh"],
            },
            {
                "id": "deepseek/second-model",
                "api_base": "https://api.deepseek.com/v1",
                "key": ["sk-abcdefgh"],
            },
        ]

        discovery = discover_accounts([FakeProvider(config) for config in configs])

        self.assertEqual(len(discovery.accounts), 1)

    def test_same_key_on_different_hosts_is_kept(self) -> None:
        configs = [
            {
                "id": "zhipu/main",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "key": ["aaaaaaaa.bbbbbbbb"],
            },
            {
                "id": "zhipu/alt",
                "api_base": "https://zhipuai.cn/api/paas/v4",
                "key": ["aaaaaaaa.bbbbbbbb"],
            },
        ]

        discovery = discover_accounts([FakeProvider(config) for config in configs])

        self.assertEqual(len(discovery.accounts), 2)
        self.assertEqual(
            [account.label for account in discovery.accounts],
            ["智谱 #1", "智谱 #2"],
        )

    def test_multiple_keys_become_multiple_accounts(self) -> None:
        provider = FakeProvider(
            {
                "id": "zhipu/default",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "key": ["aaaaaaaa.bbbbbbbb", "cccccccc.dddddddd"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 2)
        self.assertEqual(
            [account.label for account in discovery.accounts],
            ["智谱 #1", "智谱 #2"],
        )

    def test_current_key_is_included(self) -> None:
        provider = FakeProvider(
            {"id": "modelscope/default", "api_base": "https://api-inference.modelscope.cn/v1"},
            current_key="ms-abcdefgh",
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 1)
        self.assertEqual(discovery.accounts[0].provider, "modelscope")
        self.assertEqual(discovery.accounts[0].base_url, "https://www.modelscope.cn")

    def test_discovers_kimi_provider(self) -> None:
        provider = FakeProvider(
            {
                "id": "moonshot/default",
                "type": "moonshot_chat_completion",
                "api_base": "https://api.moonshot.cn/v1",
                "key": ["sk-abcdefgh"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 1)
        self.assertEqual(discovery.accounts[0].provider, "kimi")
        self.assertEqual(discovery.accounts[0].base_url, "https://api.moonshot.cn")

    def test_discovers_minimax_token_plan_provider(self) -> None:
        provider = FakeProvider(
            {
                "id": "minimax-token-plan/default",
                "type": "minimax_token_plan",
                "provider": "minimax-token-plan",
                "api_base": "https://api.minimaxi.com/anthropic",
                "key": ["sk-abcdefgh"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 1)
        self.assertEqual(discovery.accounts[0].provider, "minimax_token_plan")
        self.assertEqual(discovery.accounts[0].base_url, "https://api.minimaxi.com")

    def test_explicit_name_is_used_as_label(self) -> None:
        provider = FakeProvider(
            {
                "id": "deepseek/default",
                "name": "主账号",
                "api_base": "https://api.deepseek.com",
                "key": ["sk-abcdefgh"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(discovery.accounts[0].label, "主账号")

    def test_unsupported_providers_are_reported(self) -> None:
        provider = FakeProvider(
            {
                "id": "openai/gpt-4o",
                "type": "openai_chat_completion",
                "api_base": "https://api.openai.com/v1",
                "key": ["sk-abcdefgh"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(discovery.accounts, [])
        self.assertEqual(discovery.unsupported, ["openai"])

    def test_provider_without_key_is_reported(self) -> None:
        provider = FakeProvider(
            {"id": "deepseek/default", "api_base": "https://api.deepseek.com", "key": []}
        )

        discovery = discover_accounts([provider])

        self.assertEqual(discovery.accounts, [])
        self.assertTrue(any("未找到 API Key" in warning for warning in discovery.warnings))

    def test_invalid_key_is_skipped(self) -> None:
        provider = FakeProvider(
            {
                "id": "deepseek/default",
                "api_base": "https://api.deepseek.com",
                "key": ["bad key with spaces"],
            }
        )

        discovery = discover_accounts([provider])

        self.assertEqual(discovery.accounts, [])
        self.assertTrue(discovery.warnings)

    def test_mapping_provider_and_config_attribute(self) -> None:
        plain = {
            "id": "modelscope/default",
            "api_base": "https://www.modelscope.cn",
            "api_key": "ms-abcdefgh",
        }

        class ConfigProvider:
            config = plain

        discovery = discover_accounts([plain, ConfigProvider()])

        self.assertEqual(len(discovery.accounts), 1)
        self.assertEqual(discovery.accounts[0].provider, "modelscope")

    def test_broken_get_current_key_is_ignored(self) -> None:
        provider = FakeProvider(
            {
                "id": "deepseek/default",
                "api_base": "https://api.deepseek.com",
                "key": ["sk-abcdefgh"],
            },
            raises=True,
        )

        discovery = discover_accounts([provider])

        self.assertEqual(len(discovery.accounts), 1)

    def test_bad_entries_are_ignored(self) -> None:
        discovery = discover_accounts([None, "not-a-provider", 42])  # type: ignore[list-item]

        self.assertEqual(discovery.accounts, [])


if __name__ == "__main__":
    unittest.main()
