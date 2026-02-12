from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

from cynsta_spendguard_cli.main import CliError, main, run


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        _ = exc_type
        _ = exc
        _ = tb
        return False


class SpendguardCliTests(unittest.TestCase):
    def test_budget_get_requires_agent(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run(["budget", "get"])

    def test_budget_set_requires_agent(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run(["budget", "set", "--limit", "5000"])

    def test_budget_set_rejects_negative_limit(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run(["budget", "set", "--agent", "a1", "--limit", "-1"])

    def test_hosted_mode_requires_key(self) -> None:
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"CAP_MODE": "hosted"}, clear=False):
            with mock.patch("urllib.request.urlopen") as urlopen:
                with mock.patch.object(sys, "argv", ["spendguard", "budget", "set", "--agent", "a1", "--limit", "5000"]):
                    with contextlib.redirect_stderr(stderr):
                        rc = main()
        self.assertFalse(urlopen.called)
        self.assertEqual(rc, 1)
        self.assertIn("requires API key", stderr.getvalue())

    def test_hosted_mode_requires_key_for_agent_create(self) -> None:
        with mock.patch.dict(os.environ, {"CAP_MODE": "hosted"}, clear=False):
            with mock.patch("urllib.request.urlopen") as urlopen:
                with self.assertRaises(CliError):
                    run(["agent", "create", "--name", "alpha"])
        self.assertFalse(urlopen.called)

    def test_hosted_mode_requires_key_for_agent_list(self) -> None:
        with mock.patch.dict(os.environ, {"CAP_MODE": "hosted"}, clear=False):
            with mock.patch("urllib.request.urlopen") as urlopen:
                with self.assertRaises(CliError):
                    run(["agent", "list"])
        self.assertFalse(urlopen.called)

    def test_sidecar_mode_does_not_send_api_key(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agent_id": "agent-1",
                    "hard_limit_cents": 5000,
                    "remaining_cents": 5000,
                    "locked_cents": 0,
                }
            )
        )
        with mock.patch.dict(os.environ, {"CAP_MODE": "sidecar"}, clear=False):
            with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(["budget", "set", "--agent", "agent-1", "--limit", "5000"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        header_map = {k.lower(): v for (k, v) in request.header_items()}
        self.assertNotIn("x-api-key", header_map)

    def test_hosted_mode_sends_api_key(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agent_id": "agent-1",
                    "hard_limit_cents": 5000,
                    "remaining_cents": 5000,
                    "locked_cents": 0,
                }
            )
        )
        with mock.patch.dict(os.environ, {"CAP_MODE": "hosted"}, clear=False):
            with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(
                        [
                            "budget",
                            "set",
                            "--agent",
                            "agent-1",
                            "--limit",
                            "5000",
                            "--api-key",
                            "sk_cynsta_test_123",
                        ]
                    )
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        header_map = {k.lower(): v for (k, v) in request.header_items()}
        self.assertEqual(header_map.get("x-api-key"), "sk_cynsta_test_123")

    def test_hosted_mode_reads_api_key_from_env(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agent_id": "agent-1",
                    "hard_limit_cents": 5000,
                    "remaining_cents": 5000,
                    "locked_cents": 0,
                }
            )
        )
        with mock.patch.dict(
            os.environ,
            {"CAP_MODE": "hosted", "CAP_API_KEY": "sk_cynsta_test_env_123"},
            clear=False,
        ):
            with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = run(["budget", "set", "--agent", "agent-1", "--limit", "5000"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        header_map = {k.lower(): v for (k, v) in request.header_items()}
        self.assertEqual(header_map.get("x-api-key"), "sk_cynsta_test_env_123")

    def test_request_path_and_payload(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agent_id": "abc",
                    "hard_limit_cents": 5000,
                    "remaining_cents": 5000,
                    "locked_cents": 0,
                }
            )
        )
        with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = run(["budget", "set", "--agent", "abc", "--limit", "5000", "--topup", "5000"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8787/v1/agents/abc/budget")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"hard_limit_cents": 5000, "topup_cents": 5000})

    def test_budget_get_request_path_and_method(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agent_id": "abc",
                    "hard_limit_cents": 5000,
                    "remaining_cents": 4900,
                    "locked_cents": 0,
                }
            )
        )
        with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = run(["budget", "get", "--agent", "abc"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8787/v1/agents/abc/budget")
        self.assertEqual(request.get_method(), "GET")
        self.assertIsNone(request.data)

    def test_agent_create_request_path_and_payload(self) -> None:
        fake = _FakeResponse(json.dumps({"agent_id": "agent-new"}))
        with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = run(["agent", "create", "--name", "alpha"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8787/v1/agents")
        self.assertEqual(request.get_method(), "POST")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {"name": "alpha"})

    def test_agent_create_default_payload(self) -> None:
        fake = _FakeResponse(json.dumps({"agent_id": "agent-new"}))
        with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = run(["agent", "create"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload, {})

    def test_agent_list_request_path_and_method(self) -> None:
        fake = _FakeResponse(
            json.dumps(
                {
                    "agents": [
                        {"agent_id": "a1", "name": "agent-1", "created_at": "2026-02-12T12:00:00Z"},
                        {"agent_id": "a2", "name": None, "created_at": "2026-02-12T12:01:00Z"},
                    ]
                }
            )
        )
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", return_value=fake) as urlopen:
            with contextlib.redirect_stdout(out):
                rc = run(["agent", "list"])
        self.assertEqual(rc, 0)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8787/v1/agents")
        self.assertEqual(request.get_method(), "GET")
        self.assertIn("agent_id=a1 name=agent-1", out.getvalue())
        self.assertIn("agent_id=a2", out.getvalue())

    def test_agent_list_empty(self) -> None:
        fake = _FakeResponse(json.dumps({"agents": []}))
        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", return_value=fake):
            with contextlib.redirect_stdout(out):
                rc = run(["agent", "list"])
        self.assertEqual(rc, 0)
        self.assertIn("(no agents)", out.getvalue())

    def test_http_error_with_detail_raises_cli_error(self) -> None:
        err = urllib.error.HTTPError(
            url="http://localhost:8787",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"detail":"hard_limit_cents is required (int)"}'),
        )
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(CliError) as ctx:
                run(["budget", "set", "--agent", "abc", "--limit", "5000"])
        self.assertIn("HTTP 400", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
