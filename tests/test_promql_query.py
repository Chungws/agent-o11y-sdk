"""Unit tests for promql_query.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from agent_obs import promql_query


class TestInstantQuery:
    def test_calls_prometheus_api(self, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [
                        {
                            "metric": {
                                "__name__": "agent_step_count_total",
                                "step_type": "llm_call",
                            },
                            "value": [1710000000, "42"],
                        }
                    ],
                },
            }
        )
        with patch.object(httpx, "get", return_value=resp) as mock_get:
            result = promql_query.instant_query(
                "http://prom:9090", "agent_step_count_total"
            )

        mock_get.assert_called_once()
        assert result["data"]["result"][0]["value"][1] == "42"


class TestRangeQuery:
    def test_calls_query_range_api(self, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"__name__": "rate_metric"},
                            "values": [[1710000000, "1.5"], [1710000015, "2.0"]],
                        }
                    ],
                },
            }
        )
        with patch.object(httpx, "get", return_value=resp):
            result = promql_query.range_query(
                "http://prom:9090",
                "rate(x[5m])",
                "2024-01-01T00:00:00",
                "2024-01-01T01:00:00",
                "15s",
            )

        assert len(result["data"]["result"][0]["values"]) == 2


class TestFormatInstant:
    def test_no_results(self) -> None:
        data = {"data": {"result": []}}
        assert promql_query.format_instant(data) == "No results."

    def test_formats_metric_line(self) -> None:
        data = {
            "data": {
                "result": [
                    {
                        "metric": {
                            "__name__": "agent_step_count_total",
                            "run_id": "r1",
                        },
                        "value": [1710000000.0, "42"],
                    }
                ]
            }
        }
        output = promql_query.format_instant(data)
        assert "agent_step_count_total" in output
        assert "42" in output
        assert 'run_id="r1"' in output


class TestFormatRange:
    def test_no_results(self) -> None:
        data = {"data": {"result": []}}
        assert promql_query.format_range(data) == "No results."

    def test_formats_series(self) -> None:
        data = {
            "data": {
                "result": [
                    {
                        "metric": {"__name__": "m1"},
                        "values": [[1710000000, "1.0"], [1710000015, "2.0"]],
                    }
                ]
            }
        }
        output = promql_query.format_range(data)
        assert "m1" in output
        assert "1.0" in output
        assert "2.0" in output


class TestParseDuration:
    def test_minutes(self) -> None:
        assert promql_query._parse_duration("30m").total_seconds() == 1800

    def test_hours(self) -> None:
        assert promql_query._parse_duration("2h").total_seconds() == 7200

    def test_days(self) -> None:
        assert promql_query._parse_duration("1d").total_seconds() == 86400

    def test_unknown_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown duration unit"):
            promql_query._parse_duration("5x")


class TestMain:
    def test_instant_query_cli(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "vector", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            promql_query.main(["agent_step_count_total"])

        assert "No results" in capsys.readouterr().out

    def test_range_query_cli(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "matrix", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            promql_query.main(["--range", "--start", "1h", "rate(x[5m])"])

        assert "No results" in capsys.readouterr().out

    def test_json_output(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "vector", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            promql_query.main(["--json", "agent_step_count_total"])

        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "success"

    def test_range_json_output(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "matrix", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            promql_query.main(["--range", "--json", "rate(x[5m])"])

        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "success"
