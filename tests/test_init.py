"""Unit tests for agent_obs.init (the top-level entry point)."""

from __future__ import annotations

from unittest.mock import patch

import agent_obs
from agent_obs import ExperimentContext

from opentelemetry.sdk.metrics.export import InMemoryMetricReader


class TestInit:
    def test_auto_generates_run_id_when_empty(self) -> None:
        ctx = ExperimentContext(run_id="", prompt_version="v1")
        with (
            patch("agent_obs.OTLPSpanExporter") as mock_span_exp,
            patch("agent_obs.OTLPMetricExporter") as mock_metric_exp,
        ):
            mock_span_exp.return_value = mock_span_exp
            mock_metric_exp.return_value = mock_metric_exp
            with agent_obs.init(ctx, otlp_endpoint="http://localhost:4317") as run:
                assert len(run.run_id) == 16

    def test_histogram_buckets_applied(self) -> None:
        """Verify that custom histogram buckets produce accurate percentiles."""
        ctx = ExperimentContext(run_id="bucket-test", prompt_version="v1")
        reader = InMemoryMetricReader()

        with (
            patch("agent_obs.OTLPSpanExporter") as mock_span_exp,
            patch("agent_obs.OTLPMetricExporter"),
            patch("agent_obs.PeriodicExportingMetricReader", return_value=reader),
        ):
            mock_span_exp.return_value = mock_span_exp
            with agent_obs.init(ctx) as run:
                with run.episode("ep") as ep:
                    with ep.step("llm_call") as step:
                        step.record_tokens(input_tokens=150, output_tokens=75)

        data = reader.get_metrics_data()
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for m in sm.metrics:
                    if m.name == "agent_step_duration_seconds":
                        boundaries = list(m.data.data_points[0].explicit_bounds)
                        assert 0.01 in boundaries
                        assert 0.25 in boundaries
                        assert 0.5 in boundaries
                    elif m.name == "agent_token_usage":
                        boundaries = list(m.data.data_points[0].explicit_bounds)
                        assert 100 in boundaries
                        assert 1000 in boundaries
