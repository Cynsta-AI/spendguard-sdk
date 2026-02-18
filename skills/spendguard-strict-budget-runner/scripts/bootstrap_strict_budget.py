#!/usr/bin/env python3
"""Bootstrap strict-budget SpendGuard agent setup."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _extract_detail(raw: str) -> str:
    if not raw:
        return "request failed"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(data, dict) and isinstance(data.get("detail"), str):
        return data["detail"]
    return raw


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {_extract_detail(err_body)}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc

    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("Expected JSON object response")
    return parsed


def _headers(api_key: str | None) -> dict[str, str]:
    out = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        out["x-api-key"] = api_key
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap strict-budget SpendGuard setup.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("CAP_BASE_URL", "http://127.0.0.1:8787"),
        help="SpendGuard base URL",
    )
    parser.add_argument("--name", default="strict-budget-agent", help="Agent name")
    parser.add_argument("--limit", required=True, type=_parse_positive_int, help="Hard limit cents")
    parser.add_argument(
        "--topup",
        type=_parse_positive_int,
        default=None,
        help="Topup cents (defaults to --limit)",
    )
    parser.add_argument("--api-key", default=os.getenv("CAP_API_KEY"), help="Hosted mode API key")
    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip /health check before provisioning",
    )
    parser.add_argument(
        "--create-run",
        action="store_true",
        help="Create run and include run_id in output",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    base_url = args.base_url.rstrip("/")
    headers = _headers(args.api_key)
    topup = args.topup if args.topup is not None else args.limit

    if not args.skip_health_check:
        health = _request_json(
            method="GET",
            url=f"{base_url}/health",
            headers={"Accept": "application/json"},
        )
        if health.get("status") != "ok":
            raise RuntimeError("Health check failed: /health did not return status=ok")

    agent = _request_json(
        method="POST",
        url=f"{base_url}/v1/agents",
        headers=headers,
        payload={"name": args.name},
    )
    agent_id = agent.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise RuntimeError("Agent creation did not return agent_id")

    budget = _request_json(
        method="POST",
        url=f"{base_url}/v1/agents/{agent_id}/budget",
        headers=headers,
        payload={"hard_limit_cents": args.limit, "topup_cents": topup},
    )

    run: dict[str, Any] | None = None
    if args.create_run:
        run = _request_json(
            method="POST",
            url=f"{base_url}/v1/agents/{agent_id}/runs",
            headers=headers,
            payload={},
        )

    output = {
        "base_url": base_url,
        "agent_id": agent_id,
        "budget": budget,
        "run": run,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0

    print(f"agent_id={agent_id}")
    print(f"hard_limit_cents={budget.get('hard_limit_cents')}")
    print(f"remaining_cents={budget.get('remaining_cents')}")
    if run and isinstance(run.get("run_id"), str):
        print(f"run_id={run['run_id']}")
    print(f"export_SPENDGUARD_AGENT_ID={agent_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
