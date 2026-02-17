from __future__ import annotations

import io
import json
import unittest
from unittest import mock

from spendguard_sdk import SpendGuardClient


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class SpendGuardClientTests(unittest.TestCase):
    def test_create_agent_sends_expected_request(self) -> None:
        seen: list[tuple[str, str, dict]] = []

        def _fake_urlopen(req, timeout=30):  # type: ignore[no-untyped-def]
            body = req.data.decode("utf-8") if req.data else "{}"
            seen.append((req.method, req.full_url, json.loads(body)))
            return _FakeResponse({"agent_id": "a1"})

        client = SpendGuardClient("http://localhost:8787")
        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            result = client.create_agent("agent-1")

        self.assertEqual(result["agent_id"], "a1")
        self.assertEqual(seen[0][0], "POST")
        self.assertEqual(seen[0][1], "http://localhost:8787/v1/agents")
        self.assertEqual(seen[0][2]["name"], "agent-1")

    def test_get_budget_uses_path(self) -> None:
        seen_urls: list[str] = []

        def _fake_urlopen(req, timeout=30):  # type: ignore[no-untyped-def]
            seen_urls.append(req.full_url)
            return _FakeResponse({"remaining_cents": 123})

        client = SpendGuardClient("https://example.com")
        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = client.get_budget("agent-abc")

        self.assertEqual(out["remaining_cents"], 123)
        self.assertEqual(seen_urls[0], "https://example.com/v1/agents/agent-abc/budget")

    def test_create_run_uses_path(self) -> None:
        seen: list[tuple[str, str, dict]] = []

        def _fake_urlopen(req, timeout=30):  # type: ignore[no-untyped-def]
            body = req.data.decode("utf-8") if req.data else "{}"
            seen.append((req.method, req.full_url, json.loads(body)))
            return _FakeResponse({"run_id": "run-1"})

        client = SpendGuardClient("https://example.com")
        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = client.create_run("agent-abc")

        self.assertEqual(out["run_id"], "run-1")
        self.assertEqual(seen[0][0], "POST")
        self.assertEqual(seen[0][1], "https://example.com/v1/agents/agent-abc/runs")
        self.assertEqual(seen[0][2], {})

    def test_grok_responses_uses_expected_path(self) -> None:
        seen: list[tuple[str, str, dict]] = []

        def _fake_urlopen(req, timeout=30):  # type: ignore[no-untyped-def]
            body = req.data.decode("utf-8") if req.data else "{}"
            seen.append((req.method, req.full_url, json.loads(body)))
            return _FakeResponse({"id": "resp_1"})

        payload = {"model": "grok-3", "input": "hello"}
        client = SpendGuardClient("https://example.com")
        with mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = client.grok_responses("agent-abc", "run-xyz", payload)

        self.assertEqual(out["id"], "resp_1")
        self.assertEqual(seen[0][0], "POST")
        self.assertEqual(
            seen[0][1],
            "https://example.com/v1/agents/agent-abc/runs/run-xyz/grok/responses",
        )
        self.assertEqual(seen[0][2], payload)


if __name__ == "__main__":
    unittest.main()
