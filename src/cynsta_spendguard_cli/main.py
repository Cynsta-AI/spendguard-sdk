from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class CliError(Exception):
    pass


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _mode() -> str:
    return (os.getenv("CAP_MODE") or "sidecar").strip().lower()


def _base_url(value: str | None) -> str:
    raw = value or os.getenv("CAP_BASE_URL") or "http://localhost:8787"
    return raw.rstrip("/")


def _headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _extract_detail(raw_body: str) -> str:
    if not raw_body:
        return "request failed"
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body
    if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str):
        return parsed["detail"]
    return raw_body


def _request_json(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise CliError(f"HTTP {exc.code}: {_extract_detail(error_body)}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"Request failed: {exc.reason}") from exc

    if not response_body:
        return {}
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise CliError("Server response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise CliError("Server response must be a JSON object")
    return parsed


def _resolve_api_key(args: argparse.Namespace) -> str | None:
    mode = _mode()
    api_key = getattr(args, "api_key", None) or os.getenv("CAP_API_KEY")
    if mode == "hosted" and not api_key:
        raise CliError("Hosted mode requires API key via --api-key or CAP_API_KEY")
    return api_key


def _print_budget(data: dict[str, Any], fallback_agent_id: str | None = None) -> None:
    if fallback_agent_id:
        print(f"agent_id={data.get('agent_id', fallback_agent_id)}")
    elif "agent_id" in data:
        print(f"agent_id={data['agent_id']}")
    for key in (
        "hard_limit_cents",
        "remaining_cents",
        "locked_cents",
        "locked_run_id",
        "locked_expires_at",
    ):
        if key in data:
            print(f"{key}={data[key]}")


def _cmd_agent_create(args: argparse.Namespace) -> int:
    api_key = _resolve_api_key(args)
    endpoint = f"{_base_url(args.base_url)}/v1/agents"
    payload: dict[str, Any] = {}
    if args.name:
        payload["name"] = args.name
    data = _request_json(method="POST", url=endpoint, payload=payload, headers=_headers(api_key))

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    if "agent_id" in data:
        print(f"agent_id={data['agent_id']}")
    else:
        print(json.dumps(data, sort_keys=True))
    return 0


def _cmd_agent_list(args: argparse.Namespace) -> int:
    api_key = _resolve_api_key(args)
    endpoint = f"{_base_url(args.base_url)}/v1/agents"
    data = _request_json(method="GET", url=endpoint, headers=_headers(api_key))

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    rows = data.get("agents")
    if not isinstance(rows, list):
        raise CliError("Server response missing agents list")
    if not rows:
        print("(no agents)")
        return 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        agent_id = row.get("agent_id", "")
        name = row.get("name")
        created_at = row.get("created_at", "")
        line = f"agent_id={agent_id}"
        if name:
            line += f" name={name}"
        if created_at:
            line += f" created_at={created_at}"
        print(line)
    return 0


def _cmd_budget_set(args: argparse.Namespace) -> int:
    api_key = _resolve_api_key(args)

    endpoint = f"{_base_url(args.base_url)}/v1/agents/{urllib.parse.quote(args.agent, safe='')}/budget"
    payload = {"hard_limit_cents": args.limit, "topup_cents": args.topup}
    data = _request_json(method="POST", url=endpoint, payload=payload, headers=_headers(api_key))

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    _print_budget(data, fallback_agent_id=args.agent)
    return 0


def _cmd_budget_get(args: argparse.Namespace) -> int:
    api_key = _resolve_api_key(args)
    endpoint = f"{_base_url(args.base_url)}/v1/agents/{urllib.parse.quote(args.agent, safe='')}/budget"
    data = _request_json(method="GET", url=endpoint, headers=_headers(api_key))

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
        return 0

    _print_budget(data, fallback_agent_id=args.agent)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cynsta SpendGuard CLI")
    subparsers = parser.add_subparsers(dest="command")

    agent_parser = subparsers.add_parser("agent", help="Agent operations")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")

    agent_create = agent_subparsers.add_parser("create", help="Create a SpendGuard agent")
    agent_create.add_argument("--name", default=None, help="Optional agent name")
    agent_create.add_argument("--base-url", default=None, help="SpendGuard base URL")
    agent_create.add_argument("--api-key", default=None, help="Hosted mode API key")
    agent_create.add_argument("--json", action="store_true", help="Print raw JSON response")
    agent_create.set_defaults(handler=_cmd_agent_create)

    agent_list = agent_subparsers.add_parser("list", help="List SpendGuard agents")
    agent_list.add_argument("--base-url", default=None, help="SpendGuard base URL")
    agent_list.add_argument("--api-key", default=None, help="Hosted mode API key")
    agent_list.add_argument("--json", action="store_true", help="Print raw JSON response")
    agent_list.set_defaults(handler=_cmd_agent_list)

    budget_parser = subparsers.add_parser("budget", help="Budget operations")
    budget_subparsers = budget_parser.add_subparsers(dest="budget_command")

    budget_get = budget_subparsers.add_parser("get", help="Get budget for an agent")
    budget_get.add_argument("--agent", required=True, help="SpendGuard agent_id")
    budget_get.add_argument("--base-url", default=None, help="SpendGuard base URL")
    budget_get.add_argument("--api-key", default=None, help="Hosted mode API key")
    budget_get.add_argument("--json", action="store_true", help="Print raw JSON response")
    budget_get.set_defaults(handler=_cmd_budget_get)

    budget_set = budget_subparsers.add_parser("set", help="Set/top up budget for an agent")
    budget_set.add_argument("--agent", required=True, help="SpendGuard agent_id")
    budget_set.add_argument("--limit", required=True, type=_non_negative_int, help="Hard limit in cents")
    budget_set.add_argument("--topup", default=0, type=_non_negative_int, help="Top-up in cents")
    budget_set.add_argument("--base-url", default=None, help="SpendGuard base URL")
    budget_set.add_argument("--api-key", default=None, help="Hosted mode API key")
    budget_set.add_argument("--json", action="store_true", help="Print raw JSON response")
    budget_set.set_defaults(handler=_cmd_budget_set)

    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


def main() -> int:
    try:
        return run()
    except CliError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
