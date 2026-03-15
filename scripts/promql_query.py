#!/usr/bin/env python3
"""PromQL query helper — wraps Prometheus HTTP API.

Usage:
    python scripts/promql_query.py 'agent_step_count_total{prompt_version="v1"}'
    python scripts/promql_query.py --range --start 1h 'rate(agent_step_count_total[5m])'
    python scripts/promql_query.py --json 'agent_step_count_total'
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import httpx

DEFAULT_ENDPOINT = "http://localhost:9090"


def instant_query(endpoint: str, query: str) -> dict:
    resp = httpx.get(f"{endpoint}/api/v1/query", params={"query": query}, timeout=10)
    resp.raise_for_status()
    return resp.json()


def range_query(endpoint: str, query: str, start: str, end: str, step: str) -> dict:
    resp = httpx.get(
        f"{endpoint}/api/v1/query_range",
        params={"query": query, "start": start, "end": end, "step": step},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_duration(s: str) -> timedelta:
    """Parse simple duration like '1h', '30m', '2d'."""
    unit = s[-1]
    val = int(s[:-1])
    if unit == "m":
        return timedelta(minutes=val)
    if unit == "h":
        return timedelta(hours=val)
    if unit == "d":
        return timedelta(days=val)
    raise ValueError(f"Unknown duration unit: {unit}")


def format_instant(data: dict) -> str:
    results = data["data"]["result"]
    if not results:
        return "No results."
    lines = []
    for r in results:
        labels = ", ".join(
            f'{k}="{v}"' for k, v in r["metric"].items() if k != "__name__"
        )
        name = r["metric"].get("__name__", "")
        ts = datetime.fromtimestamp(r["value"][0], tz=timezone.utc).strftime("%H:%M:%S")
        val = r["value"][1]
        lines.append(f"{name}{{{labels}}} @ {ts} = {val}")
    return "\n".join(lines)


def format_range(data: dict) -> str:
    results = data["data"]["result"]
    if not results:
        return "No results."
    lines = []
    for r in results:
        labels = ", ".join(
            f'{k}="{v}"' for k, v in r["metric"].items() if k != "__name__"
        )
        name = r["metric"].get("__name__", "")
        lines.append(f"--- {name}{{{labels}}} ---")
        for ts, val in r["values"]:
            t = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
            lines.append(f"  {t}  {val}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query Prometheus via PromQL")
    parser.add_argument("query", help="PromQL expression")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Prometheus URL")
    parser.add_argument(
        "--range", action="store_true", dest="is_range", help="Range query"
    )
    parser.add_argument(
        "--start", default="1h", help="Lookback duration (e.g. 1h, 30m)"
    )
    parser.add_argument("--end", default="now", help="End time (default: now)")
    parser.add_argument("--step", default="15s", help="Query step (default: 15s)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args(argv)

    if args.is_range:
        now = datetime.now(tz=timezone.utc)
        end = now if args.end == "now" else datetime.fromisoformat(args.end)
        start = end - _parse_duration(args.start)
        data = range_query(
            args.endpoint,
            args.query,
            start.isoformat(),
            end.isoformat(),
            args.step,
        )
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_range(data))
    else:
        data = instant_query(args.endpoint, args.query)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(format_instant(data))


if __name__ == "__main__":
    main()
