"""OTel metric instruments for agent observability."""

from __future__ import annotations

from opentelemetry.metrics import Histogram, Counter, Meter


class AgentMetrics:
    """Pre-defined metric instruments. Created once per SDK init."""

    def __init__(self, meter: Meter) -> None:
        self.step_duration: Histogram = meter.create_histogram(
            name="agent_step_duration_seconds",
            description="Step execution duration",
            unit="s",
        )
        self.step_count: Counter = meter.create_counter(
            name="agent_step_count",
            description="Total steps executed",
        )
        self.step_errors: Counter = meter.create_counter(
            name="agent_step_errors",
            description="Total step failures",
        )
        self.token_usage: Histogram = meter.create_histogram(
            name="agent_token_usage",
            description="Token usage per LLM call",
            unit="tokens",
        )
        self.episode_duration: Histogram = meter.create_histogram(
            name="agent_episode_duration_seconds",
            description="Episode execution duration",
            unit="s",
        )
        self.episode_steps: Histogram = meter.create_histogram(
            name="agent_episode_steps",
            description="Number of steps per episode",
        )
        self.custom_score: Histogram = meter.create_histogram(
            name="agent_custom_score",
            description="User-defined score",
        )
