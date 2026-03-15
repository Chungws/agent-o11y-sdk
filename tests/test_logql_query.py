"""Unit tests for logql_query.py."""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

import logql_query


class TestQueryRange:
    def test_calls_loki_api(self, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={
                "status": "success",
                "data": {
                    "resultType": "streams",
                    "result": [
                        {
                            "stream": {"service_name": "agent-obs"},
                            "values": [["1710000000000000000", "test log"]],
                        }
                    ],
                },
            }
        )
        with patch.object(httpx, "get", return_value=resp) as mock_get:
            result = logql_query.query_range(
                "http://loki:3100",
                '{service_name="agent-obs"}',
                "2024-01-01T00:00:00",
                "2024-01-01T01:00:00",
                100,
            )

        mock_get.assert_called_once()
        assert result["data"]["result"][0]["values"][0][1] == "test log"


class TestFormatLogs:
    def test_no_results(self) -> None:
        data = {"data": {"result": []}}
        assert logql_query.format_logs(data) == "No results."

    def test_formats_stream(self) -> None:
        data = {
            "data": {
                "result": [
                    {
                        "stream": {"service_name": "agent-obs", "run_id": "r1"},
                        "values": [["1710000060000000000", "step completed"]],
                    }
                ]
            }
        }
        output = logql_query.format_logs(data)
        assert "step completed" in output
        assert 'service_name="agent-obs"' in output


class TestParseDuration:
    def test_minutes(self) -> None:
        assert logql_query._parse_duration("30m").total_seconds() == 1800

    def test_hours(self) -> None:
        assert logql_query._parse_duration("2h").total_seconds() == 7200

    def test_days(self) -> None:
        assert logql_query._parse_duration("1d").total_seconds() == 86400

    def test_unknown_unit_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown duration unit"):
            logql_query._parse_duration("5x")


class TestMain:
    def test_default_output(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "streams", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            logql_query.main(['{service_name="agent-obs"}'])

        assert "No results" in capsys.readouterr().out

    def test_json_output(self, capsys, mock_httpx_response) -> None:
        resp = mock_httpx_response(
            json={"status": "success", "data": {"resultType": "streams", "result": []}}
        )
        with patch.object(httpx, "get", return_value=resp):
            logql_query.main(["--json", '{service_name="agent-obs"}'])

        parsed = json.loads(capsys.readouterr().out)
        assert parsed["status"] == "success"
