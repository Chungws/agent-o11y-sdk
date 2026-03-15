"""Unit tests for Run / Episode / Step hierarchy.

Uses OTel InMemorySpanExporter + InMemoryMetricReader to avoid infra dependency.
"""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader

from agent_obs.metrics import AgentMetrics
from agent_obs.artifacts import ArtifactStore
from agent_obs.tracing import Run


class _CollectingExporter(SpanExporter):
    """Minimal in-memory span collector."""

    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self):
        return list(self.spans)


@pytest.fixture()
def setup(tmp_path):
    """Create in-memory OTel providers and return (run, spans, metrics_reader)."""
    span_exporter = _CollectingExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])

    tracer = tracer_provider.get_tracer("test")
    meter = meter_provider.get_meter("test")
    metrics = AgentMetrics(meter)
    artifacts = ArtifactStore(tmp_path)

    with tracer.start_as_current_span("run.test", attributes={"run_id": "r1"}) as span:
        run = Run(span, "r1", tracer=tracer, metrics=metrics, artifacts=artifacts)
        yield run, span_exporter, metric_reader

    tracer_provider.shutdown()
    meter_provider.shutdown()


class TestStep:
    def test_happy_path_records_metrics(self, setup) -> None:
        run, span_exporter, metric_reader = setup
        with run.episode("ep") as ep:
            with ep.step("llm_call") as step:
                step.record_tokens(input_tokens=10, output_tokens=5)
                step.record_score("quality", 0.9)
                step.log("hello", key="val")

        spans = span_exporter.get_finished_spans()
        step_span = next(s for s in spans if s.name == "step.llm_call")
        assert step_span.status.is_ok
        assert step_span.attributes["step_type"] == "llm_call"

    def test_set_attribute(self, setup) -> None:
        run, span_exporter, _ = setup
        with run.episode("ep") as ep:
            with ep.step("tool_call") as step:
                step.set_attribute("tool.name", "search")

        spans = span_exporter.get_finished_spans()
        step_span = next(s for s in spans if s.name == "step.tool_call")
        assert step_span.attributes["tool.name"] == "search"

    def test_custom_step_name(self, setup) -> None:
        run, span_exporter, _ = setup
        with run.episode("ep") as ep:
            with ep.step("llm_call", name="my-step"):
                pass

        spans = span_exporter.get_finished_spans()
        assert any(s.name == "my-step" for s in spans)

    def test_error_sets_span_error_status(self, setup) -> None:
        run, span_exporter, _ = setup
        with pytest.raises(ValueError, match="boom"):
            with run.episode("ep") as ep:
                with ep.step("llm_call") as _step:
                    raise ValueError("boom")

        spans = span_exporter.get_finished_spans()
        step_span = next(s for s in spans if s.name == "step.llm_call")
        assert not step_span.status.is_ok

    def test_save_artifact_sets_span_attribute(self, setup, tmp_path) -> None:
        run, span_exporter, _ = setup
        with run.episode("ep") as ep:
            with ep.step("tool_call") as step:
                path = step.save_artifact("out.txt", "result")

        assert path == f"r1/{ep.episode_id}/{step.step_id}/out.txt"
        spans = span_exporter.get_finished_spans()
        step_span = next(s for s in spans if s.name == "step.tool_call")
        assert step_span.attributes["artifact.out.txt"] == path

    def test_record_tokens_skips_zero(self, setup) -> None:
        run, _, metric_reader = setup
        with run.episode("ep") as ep:
            with ep.step("llm_call") as step:
                step.record_tokens(input_tokens=0, output_tokens=0)

        data = metric_reader.get_metrics_data()
        token_metrics = [
            m
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
            if m.name == "agent_token_usage"
        ]
        if token_metrics:
            total = sum(dp.count for dp in token_metrics[0].data.data_points)
            assert total == 0


class TestEpisode:
    def test_set_attribute(self, setup) -> None:
        run, span_exporter, _ = setup
        with run.episode("ep") as ep:
            ep.set_attribute("task", "coding")

        spans = span_exporter.get_finished_spans()
        ep_span = next(s for s in spans if s.name == "ep")
        assert ep_span.attributes["task"] == "coding"

    def test_log(self, setup) -> None:
        run, span_exporter, _ = setup
        with run.episode("ep") as ep:
            ep.log("starting episode", phase="init")

        spans = span_exporter.get_finished_spans()
        ep_span = next(s for s in spans if s.name == "ep")
        assert any(e.name == "starting episode" for e in ep_span.events)

    def test_error_sets_episode_error_status(self, setup) -> None:
        run, span_exporter, _ = setup
        with pytest.raises(RuntimeError, match="ep-fail"):
            with run.episode("ep") as _ep:
                raise RuntimeError("ep-fail")

        spans = span_exporter.get_finished_spans()
        ep_span = next(s for s in spans if s.name == "ep")
        assert not ep_span.status.is_ok

    def test_step_count_tracked(self, setup) -> None:
        run, _, metric_reader = setup
        with run.episode("ep") as ep:
            with ep.step("a"):
                pass
            with ep.step("b"):
                pass

        data = metric_reader.get_metrics_data()
        ep_steps = [
            m
            for rm in data.resource_metrics
            for sm in rm.scope_metrics
            for m in sm.metrics
            if m.name == "agent_episode_steps"
        ]
        assert len(ep_steps) > 0
        assert ep_steps[0].data.data_points[0].sum == 2


class TestRun:
    def test_set_attribute(self, setup) -> None:
        run, span_exporter, _ = setup
        run.set_attribute("experiment", "ablation-1")
        # The run span is still open (context manager in fixture),
        # so we just verify no error was raised

    def test_episode_error_propagates(self, setup) -> None:
        run, span_exporter, _ = setup
        with pytest.raises(TypeError, match="run-fail"):
            with run.episode("ep"):
                raise TypeError("run-fail")

        spans = span_exporter.get_finished_spans()
        ep_span = next(s for s in spans if s.name == "ep")
        assert not ep_span.status.is_ok
