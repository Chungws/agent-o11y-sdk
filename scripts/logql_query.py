#!/usr/bin/env python3
"""LogQL query helper — wraps Loki HTTP API.

Usage:
    python scripts/logql_query.py '{service_name="agent-obs"}'
    python scripts/logql_query.py --start 1h '{service_name="agent-obs"} |= "error"'
    python scripts/logql_query.py --json '{service_name="agent-obs"}'
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

import httpx

DEFAULT_ENDPOINT = "http://localhost:3100"


def query_range(endpoint: str, query: str, start: str, end: str, limit: int) -> dict:
    resp = httpx.get(
        f"{endpoint}/loki/api/v1/query_range",
        params={"query": query, "start": start, "end": end, "limit": limit},
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


def format_logs(data: dict) -> str:
    results = data["data"]["result"]
    if not results:
        return "No results."
    lines = []
    for stream in results:
        labels = stream["stream"]
        label_str = ", ".join(f'{k}="{v}"' for k, v in labels.items())
        lines.append(f"--- {{{label_str}}} ---")
        for ts_ns, msg in stream["values"]:
            ts = datetime.fromtimestamp(int(ts_ns) / 1e9, tz=timezone.utc)
            t = ts.strftime("%H:%M:%S.%f")[:-3]
            lines.append(f"  [{t}] {msg}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Query Loki via LogQL")
    parser.add_argument("query", help="LogQL expression")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="Loki URL")
    parser.add_argument(
        "--start", default="1h", help="Lookback duration (e.g. 1h, 30m)"
    )
    parser.add_argument("--end", default="now", help="End time (default: now)")
    parser.add_argument("--limit", type=int, default=100, help="Max log lines")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args(argv)

    now = datetime.now(tz=timezone.utc)
    end = now if args.end == "now" else datetime.fromisoformat(args.end)
    start = end - _parse_duration(args.start)

    data = query_range(
        args.endpoint,
        args.query,
        start.isoformat(),
        end.isoformat(),
        args.limit,
    )

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print(format_logs(data))


if __name__ == "__main__":
    main()
