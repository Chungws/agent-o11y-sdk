"""Agent Observability SDK."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import ExplicitBucketHistogramAggregation, View
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

from agent_obs.context import ExperimentContext
from agent_obs.metrics import AgentMetrics
from agent_obs.tracing import Run, Episode, Step
from agent_obs.artifacts import ArtifactStore

__all__ = [
    "init",
    "ExperimentContext",
    "Run",
    "Episode",
    "Step",
    "ArtifactStore",
]


def _new_id() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


@contextmanager
def init(
    ctx: ExperimentContext,
    *,
    otlp_endpoint: str = "http://localhost:4317",
    artifact_dir: str = "./artifacts",
) -> Generator[Run, None, None]:
    """Initialize SDK, yield a Run, and flush on exit.

    Usage::

        ctx = ExperimentContext(run_id="run-1", prompt_version="v1")
        with agent_obs.init(ctx) as run:
            with run.episode("task-1") as ep:
                with ep.step("llm_call") as step:
                    step.log("calling LLM")
                    step.record_tokens(input_tokens=100, output_tokens=50)
    """
    resource = ctx.to_resource()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=5000,
    )
    _DURATION_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30]
    _TOKEN_BUCKETS = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
    _SCORE_BUCKETS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    _STEP_COUNT_BUCKETS = [1, 2, 5, 10, 20, 50, 100]

    views = [
        View(
            instrument_name="agent_step_duration_seconds",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=_DURATION_BUCKETS
            ),
        ),
        View(
            instrument_name="agent_episode_duration_seconds",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=_DURATION_BUCKETS
            ),
        ),
        View(
            instrument_name="agent_token_usage",
            aggregation=ExplicitBucketHistogramAggregation(boundaries=_TOKEN_BUCKETS),
        ),
        View(
            instrument_name="agent_episode_steps",
            aggregation=ExplicitBucketHistogramAggregation(
                boundaries=_STEP_COUNT_BUCKETS
            ),
        ),
        View(
            instrument_name="agent_custom_score",
            aggregation=ExplicitBucketHistogramAggregation(boundaries=_SCORE_BUCKETS),
        ),
    ]
    meter_provider = MeterProvider(
        resource=resource, metric_readers=[metric_reader], views=views
    )

    tracer = tracer_provider.get_tracer("agent-obs")
    meter = meter_provider.get_meter("agent-obs")
    metrics = AgentMetrics(meter)
    artifacts = ArtifactStore(artifact_dir)

    run_id = ctx.run_id or _new_id()

    with tracer.start_as_current_span(
        f"run.{run_id}",
        attributes={"run_id": run_id},
    ) as span:
        run = Run(
            span,
            run_id,
            tracer=tracer,
            metrics=metrics,
            artifacts=artifacts,
        )
        try:
            yield run
        finally:
            tracer_provider.force_flush()
            tracer_provider.shutdown()
            meter_provider.force_flush()
            meter_provider.shutdown()
