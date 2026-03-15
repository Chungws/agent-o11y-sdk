"""Integration test: SDK → OTel Collector → Prometheus/Loki.

Requires infra running (docker compose up -d in infra/).
"""

from __future__ import annotations

import time
import urllib.request
import json

import pytest

import agent_obs
from agent_obs import ExperimentContext


def _prometheus_query(query: str) -> list:
    url = f"http://localhost:9090/api/v1/query?query={query}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())
    return data["data"]["result"]


def _loki_query(query: str) -> list:
    import urllib.parse

    now = int(time.time())
    params = urllib.parse.urlencode(
        {"query": query, "start": now - 120, "end": now + 60, "limit": 50}
    )
    url = f"http://localhost:3100/loki/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())
    return data["data"]["result"]


@pytest.fixture(scope="module")
def run_id() -> str:
    return f"test-{int(time.time())}"


@pytest.fixture(scope="module", autouse=True)
def execute_run(run_id: str) -> None:
    """Run a sample experiment and wait for export."""
    ctx = ExperimentContext(
        run_id=run_id,
        prompt_version="v1-test",
        model="test-model",
        task_type="integration-test",
    )
    with agent_obs.init(ctx) as run:
        with run.episode("test-episode") as ep:
            with ep.step("llm_call", name="call-gpt") as step:
                step.log("sending prompt", prompt="hello")
                step.record_tokens(input_tokens=100, output_tokens=50)
                step.save_artifact("prompt.txt", "hello world")
                time.sleep(0.05)

            with ep.step("tool_call", name="run-tool") as step:
                step.log("executing tool")
                step.record_score("quality", 0.95)
                time.sleep(0.02)

    # Wait for metrics export (PeriodicExportingMetricReader interval is 5s)
    time.sleep(8)


class TestPrometheusMetrics:
    def test_step_count(self, run_id: str) -> None:
        results = _prometheus_query(f'agent_step_count_total{{run_id="{run_id}"}}')
        assert len(results) > 0
        total = sum(float(r["value"][1]) for r in results)
        assert total == 2  # 2 steps

    def test_step_duration(self, run_id: str) -> None:
        results = _prometheus_query(
            f'agent_step_duration_seconds_count{{run_id="{run_id}"}}'
        )
        assert len(results) > 0

    def test_token_usage(self, run_id: str) -> None:
        results = _prometheus_query(
            f'agent_token_usage_tokens_count{{run_id="{run_id}"}}'
        )
        assert len(results) > 0

    def test_episode_duration(self, run_id: str) -> None:
        results = _prometheus_query(
            f'agent_episode_duration_seconds_count{{run_id="{run_id}"}}'
        )
        assert len(results) > 0

    def test_custom_score(self, run_id: str) -> None:
        results = _prometheus_query(f'agent_custom_score_count{{run_id="{run_id}"}}')
        assert len(results) > 0


class TestArtifacts:
    def test_artifact_saved(self, run_id: str) -> None:
        from pathlib import Path

        artifacts_dir = Path("./artifacts") / run_id
        assert artifacts_dir.exists()
        txt_files = list(artifacts_dir.rglob("prompt.txt"))
        assert len(txt_files) == 1
        assert txt_files[0].read_text() == "hello world"
