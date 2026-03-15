"""Unit tests for agent_obs.init (the top-level entry point)."""

from __future__ import annotations

from unittest.mock import patch

import agent_obs
from agent_obs import ExperimentContext


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
