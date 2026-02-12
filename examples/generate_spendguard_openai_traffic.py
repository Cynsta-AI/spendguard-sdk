from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} {method} {url}: {raw}") from e


def main() -> int:
    p = argparse.ArgumentParser(
        description="Generate real OpenAI traffic through SpendGuard, then print a window for reconciliation."
    )
    p.add_argument("--base-url", type=str, default="http://localhost:8787", help="SpendGuard base URL.")
    p.add_argument("--model", type=str, default="gpt-5.2-pro", help="OpenAI model name (must be priced by SpendGuard).")
    p.add_argument("--n", type=int, default=1, help="Number of requests to send.")
    p.add_argument("--max-output-tokens", type=int, default=128, help="Requested max_output_tokens.")
    p.add_argument("--sleep-seconds", type=float, default=0.5, help="Delay between requests.")
    p.add_argument("--hard-limit-cents", type=int, default=500, help="Agent hard limit in cents.")
    p.add_argument("--topup-cents", type=int, default=500, help="Agent top-up in cents.")
    p.add_argument("--agent-name", type=str, default="traffic-test", help="Agent name.")
    p.add_argument(
        "--reasoning-effort",
        type=str,
        default=None,
        help='Optional OpenAI Responses "reasoning.effort" value (e.g. low|medium|high).',
    )
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    if args.n <= 0:
        raise SystemExit("--n must be > 0")
    if args.max_output_tokens <= 0:
        raise SystemExit("--max-output-tokens must be > 0")
    if args.hard_limit_cents <= 0:
        raise SystemExit("--hard-limit-cents must be > 0")
    if args.topup_cents < 0:
        raise SystemExit("--topup-cents must be >= 0")

    start = _utc_now_iso()

    agent = _http_json("POST", f"{base}/v1/agents", {"name": args.agent_name})
    agent_id = agent.get("agent_id") if isinstance(agent, dict) else None
    if not agent_id:
        raise RuntimeError(f"Unexpected /v1/agents response: {agent}")

    _http_json(
        "POST",
        f"{base}/v1/agents/{agent_id}/budget",
        {"hard_limit_cents": int(args.hard_limit_cents), "topup_cents": int(args.topup_cents)},
    )

    for i in range(int(args.n)):
        run = _http_json("POST", f"{base}/v1/agents/{agent_id}/runs", {})
        run_id = run.get("run_id") if isinstance(run, dict) else None
        if not run_id:
            raise RuntimeError(f"Unexpected /v1/agents/{{agent_id}}/runs response: {run}")

        prompt = (
            "Give a concise, correct answer.\n"
            "Task: Return the first 25 prime numbers as a comma-separated list.\n"
            f"Request number: {i+1}\n"
        )

        payload: dict[str, Any] = {
            "model": args.model,
            "input": prompt,
            "max_output_tokens": int(args.max_output_tokens),
        }
        if args.reasoning_effort:
            payload["reasoning"] = {"effort": str(args.reasoning_effort)}

        _http_json("POST", f"{base}/v1/agents/{agent_id}/runs/{run_id}/openai/responses", payload)

        if float(args.sleep_seconds) > 0:
            time.sleep(float(args.sleep_seconds))

    end = _utc_now_iso()

    print("SpendGuard traffic generated.")
    print(f"agent_id: {agent_id}")
    print(f"window_start_utc: {start}")
    print(f"window_end_utc:   {end}")
    print("")
    print("Next: export OpenAI usage/cost for this window, then run reconciliation:")
    print(
        "python scripts\\reconcile_spendguard_billing.py "
        f"--sqlite .\\cynsta-spendguard.db --start {start} --end {end} --openai-csv .\\openai-export.csv"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
