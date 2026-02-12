from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _parse_iso(ts: str) -> dt.datetime:
    # Accept timestamps like 2026-02-10T01:02:03+00:00 or ...Z
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return dt.datetime.fromisoformat(ts)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


@dataclass(frozen=True)
class LedgerRow:
    provider: str
    model: str
    created_at: str
    realized_microcents: int
    realized_cents: int


def _load_sqlite_ledger(db_path: Path, start: dt.datetime, end: dt.datetime) -> list[LedgerRow]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "select provider, model, created_at, realized_cents, meta_json from cap_usage_ledger where created_at >= ? and created_at <= ?",
            (start.isoformat(), end.isoformat()),
        )
        out: list[LedgerRow] = []
        for provider, model, created_at, realized_cents, meta_json in cur.fetchall():
            microcents = 0
            try:
                meta = json.loads(meta_json) if isinstance(meta_json, str) else (meta_json or {})
                bb = meta.get("billing_breakdown") or {}
                totals = bb.get("totals") or {}
                microcents = int(totals.get("realized_microcents") or 0)
            except Exception:
                microcents = 0
            out.append(
                LedgerRow(
                    provider=str(provider),
                    model=str(model),
                    created_at=str(created_at),
                    realized_microcents=microcents,
                    realized_cents=int(realized_cents),
                )
            )
        return out
    finally:
        conn.close()


def _sum_microcents_by_provider_model(rows: list[LedgerRow]) -> dict[tuple[str, str], int]:
    sums: dict[tuple[str, str], int] = {}
    for r in rows:
        key = (r.provider, r.model)
        sums[key] = sums.get(key, 0) + int(r.realized_microcents)
    return sums


def _usd_to_microcents(usd: float) -> int:
    # 1 USD = 100 cents = 100 * 1e6 microcents
    return int(round(usd * 100 * 1_000_000))


def _load_openai_csv(path: Path) -> dict[tuple[str, str], int]:
    # Expect columns: model, cost_usd
    # This is intentionally minimal; adapt mapping per your export format.
    sums: dict[tuple[str, str], int] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = (row.get("model") or "").strip()
            cost = (row.get("cost_usd") or "").strip()
            if not model or not cost:
                continue
            usd = float(cost)
            key = ("openai", model)
            sums[key] = sums.get(key, 0) + _usd_to_microcents(usd)
    return sums


def _load_anthropic_csv(path: Path) -> dict[tuple[str, str], int]:
    # Expect columns: model, cost_usd
    sums: dict[tuple[str, str], int] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = (row.get("model") or "").strip()
            cost = (row.get("cost_usd") or "").strip()
            if not model or not cost:
                continue
            usd = float(cost)
            key = ("anthropic", model)
            sums[key] = sums.get(key, 0) + _usd_to_microcents(usd)
    return sums


def _load_gemini_csv(path: Path) -> dict[tuple[str, str], int]:
    # Expect columns: model, cost_usd
    sums: dict[tuple[str, str], int] = {}
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            model = (row.get("model") or "").strip()
            cost = (row.get("cost_usd") or "").strip()
            if not model or not cost:
                continue
            usd = float(cost)
            key = ("gemini", model)
            sums[key] = sums.get(key, 0) + _usd_to_microcents(usd)
    return sums


def _format_usd_from_microcents(microcents: int) -> str:
    usd = microcents / (100 * 1_000_000)
    return f"{usd:.6f}"


def main() -> int:
    p = argparse.ArgumentParser(description="Reconcile SpendGuard ledger totals vs provider CSV exports.")
    p.add_argument("--sqlite", type=str, required=True, help="Path to sidecar sqlite DB (cap_usage_ledger).")
    p.add_argument("--start", type=str, default=None, help="UTC ISO start timestamp (inclusive).")
    p.add_argument("--end", type=str, default=None, help="UTC ISO end timestamp (inclusive).")
    p.add_argument("--openai-csv", type=str, default=None, help="OpenAI export CSV with columns model,cost_usd.")
    p.add_argument("--anthropic-csv", type=str, default=None, help="Anthropic export CSV with columns model,cost_usd.")
    p.add_argument("--gemini-csv", type=str, default=None, help="Gemini export CSV with columns model,cost_usd.")
    args = p.parse_args()

    end = _parse_iso(args.end) if args.end else _utc_now()
    start = _parse_iso(args.start) if args.start else (end - dt.timedelta(hours=1))

    ledger_rows = _load_sqlite_ledger(Path(args.sqlite), start, end)
    ledger_sums = _sum_microcents_by_provider_model(ledger_rows)

    provider_sums: dict[tuple[str, str], int] = {}
    if args.openai_csv:
        provider_sums.update(_load_openai_csv(Path(args.openai_csv)))
    if args.anthropic_csv:
        provider_sums.update(_load_anthropic_csv(Path(args.anthropic_csv)))
    if args.gemini_csv:
        provider_sums.update(_load_gemini_csv(Path(args.gemini_csv)))

    keys = sorted(set(ledger_sums.keys()) | set(provider_sums.keys()))
    print(f"Window UTC: {start.isoformat()} .. {end.isoformat()}")
    print(f"Ledger rows: {len(ledger_rows)}")
    print("")
    print("provider,model,ledger_usd,provider_usd,diff_usd")
    for provider, model in keys:
        l = int(ledger_sums.get((provider, model)) or 0)
        pr = int(provider_sums.get((provider, model)) or 0)
        diff = l - pr
        print(
            f"{provider},{model},{_format_usd_from_microcents(l)},{_format_usd_from_microcents(pr)},{_format_usd_from_microcents(diff)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

