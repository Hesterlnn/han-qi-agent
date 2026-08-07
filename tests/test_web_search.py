import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


APP_DIR = Path(__file__).resolve().parents[1] / "assets" / "api-app"
sys.path.insert(0, str(APP_DIR))

import server  # noqa: E402


def deepseek_config() -> dict:
    return {
        "name": "deepseek",
        "provider": {
            "base_url": "https://api.deepseek.com",
            "api_key_env": "DEEPSEEK_TEST_KEY",
            "model": "deepseek-v4-flash",
            "protocol": "responses",
        },
        "system_prompt": "You are a helpful assistant.",
        "knowledge": "",
    }


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class NativeWebSearchTests(unittest.TestCase):
    def test_deepseek_responses_uses_existing_provider_key(self):
        config = deepseek_config()
        with patch.dict(os.environ, {"DEEPSEEK_TEST_KEY": "test-only"}, clear=True):
            settings = server.web_search_settings(config)
        self.assertEqual(settings["provider"], "native")
        self.assertTrue(settings["configured"])
        self.assertEqual(settings["api_key"], "")

    def test_native_web_search_is_sent_and_citations_are_returned(self):
        response_payload = {
            "output": [
                {
                    "type": "reasoning",
                    "summary": [{"type": "summary_text", "text": "先核对官方资料，再整理结论。"}],
                    "content": [{"type": "reasoning_text", "text": "不应展示的原始推理"}],
                },
                {"type": "web_search_call", "status": "completed"},
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "已完成联网核实。",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "title": "DeepSeek API Docs",
                                    "url": "https://api-docs.deepseek.com/guides/responses_api/",
                                }
                            ],
                        }
                    ],
                },
            ]
        }
        handler = server.Handler.__new__(server.Handler)
        handler.server = SimpleNamespace(config=deepseek_config())
        fake_response = FakeResponse(response_payload)

        with patch.dict(os.environ, {"DEEPSEEK_TEST_KEY": "test-only"}, clear=True):
            with patch("urllib.request.urlopen", return_value=fake_response) as mocked_urlopen:
                answer, sources, reasoning_summary = handler.call_provider(
                    [{"role": "user", "content": "请联网核实"}],
                    "自动",
                    "自动",
                    [],
                    [],
                    True,
                )

        request = mocked_urlopen.call_args.args[0]
        request_payload = json.loads(request.data)
        self.assertEqual(request_payload["tools"], [{"type": "web_search"}])
        self.assertEqual(request_payload["tool_choice"], {"type": "web_search"})
        self.assertEqual(answer, "已完成联网核实。")
        self.assertEqual(reasoning_summary, "先核对官方资料，再整理结论。")
        self.assertNotIn("不应展示", reasoning_summary)
        self.assertEqual(
            sources,
            [
                {
                    "title": "DeepSeek API Docs",
                    "url": "https://api-docs.deepseek.com/guides/responses_api/",
                }
            ],
        )

    def test_local_citations_are_deduplicated_and_only_show_used_files(self):
        retrieved = server.unique_local_sources(
            [
                {"path": "史料/安阳集.md", "chunk": 1},
                {"path": "史料/安阳集.md", "chunk": 2},
                {"path": "年谱.pdf", "chunk": 1},
            ]
        )
        cited = server.cited_local_sources("根据《安阳集》的相关记载……（史料/安阳集.md）", retrieved)
        self.assertEqual(retrieved, [{"path": "史料/安阳集.md"}, {"path": "年谱.pdf"}])
        self.assertEqual(cited, [{"path": "史料/安阳集.md", "name": "安阳集.md"}])

    def test_fallback_reasoning_describes_observable_steps(self):
        reasoning = server.reasoning_for_display("", [{"path": "安阳集.md"}], True)
        self.assertEqual(reasoning["kind"], "activity_summary")
        self.assertIn("已查阅 1 份本地文献", reasoning["summary"])
        self.assertIn("已完成联网检索", reasoning["summary"])


if __name__ == "__main__":
    unittest.main()
