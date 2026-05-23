import os
import sys
from pathlib import Path
from unittest import mock
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import llm_client  # noqa: E402


class LLMClientConfigTests(unittest.TestCase):
    def test_llm_environment_names_take_precedence(self):
        env = {
            "LLM_API_KEY": "llm-key",
            "LLM_BASE_URL": "https://chat.ecnu.edu.cn/open/api/v1/",
            "LLM_MODEL_ID": "ecnu-plus",
            "DEEPSEEK_API_KEY": "deepseek-key",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_MODEL": "deepseek-chat",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = llm_client._resolve_llm_config()

        self.assertEqual(config.api_key, "llm-key")
        self.assertEqual(config.base_url, "https://chat.ecnu.edu.cn/open/api/v1")
        self.assertEqual(config.model, "ecnu-plus")

    def test_deepseek_environment_names_remain_supported(self):
        env = {
            "DEEPSEEK_API_KEY": "deepseek-key",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com/",
            "DEEPSEEK_MODEL": "deepseek-chat",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            config = llm_client._resolve_llm_config()

        self.assertEqual(config.api_key, "deepseek-key")
        self.assertEqual(config.base_url, "https://api.deepseek.com")
        self.assertEqual(config.model, "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
