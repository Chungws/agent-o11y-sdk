"""Run / Episode / Step hierarchy as OTel spans."""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.trace import Span, StatusCode

from agent_obs.metrics import AgentMetrics
from agent_obs.artifacts import ArtifactStore


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class Step:
    """Wraps a child span representing a single agent action."""

    def __init__(
        self,
        span: Span,
        step_id: str,
        step_type: str,
        *,
        metrics: AgentMetrics,
        artifacts: ArtifactStore,
        run_id: str,
        episode_id: str,
    ) -> None:
        self._span = span
        self.step_id = step_id
        self.step_type = step_type
        self._metrics = metrics
        self._artifacts = artifacts
        self._run_id = run_id
        self._episode_id = episode_id
        self._start = time.monotonic()

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def log(self, message: str, **kwargs: Any) -> None:
        self._span.add_event(message, attributes=kwargs)

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        attrs = {"step_type": self.step_type}
        if input_tokens:
            self._metrics.token_usage.record(
                input_tokens, {**attrs, "direction": "input"}
            )
        if output_tokens:
            self._metrics.token_usage.record(
                output_tokens, {**attrs, "direction": "output"}
            )

    def save_artifact(self, name: str, data: Any) -> str:
        path = self._artifacts.save(
            self._run_id, self._episode_id, self.step_id, name, data
        )
        self._span.set_attribute(f"artifact.{name}", path)
        return path

    def record_score(self, name: str, value: float) -> None:
        self._metrics.custom_score.record(
            value, {"score_name": name, "step_type": self.step_type}
        )

    def _finish(self, error: BaseException | None = None) -> float:
        duration = time.monotonic() - self._start
        attrs = {"step_type": self.step_type}
        self._metrics.step_duration.record(duration, attrs)
        self._metrics.step_count.add(1, attrs)
        if error:
            self._metrics.step_errors.add(
                1, {**attrs, "error_type": type(error).__name__}
            )
            self._span.set_status(StatusCode.ERROR, str(error))
            self._span.record_exception(error)
        else:
            self._span.set_status(StatusCode.OK)
        return duration


class Episode:
    """Wraps a parent span representing a single task execution."""

    def __init__(
        self,
        span: Span,
        episode_id: str,
        *,
        tracer: trace.Tracer,
        metrics: AgentMetrics,
        artifacts: ArtifactStore,
        run_id: str,
    ) -> None:
        self._span = span
        self.episode_id = episode_id
        self._tracer = tracer
        self._metrics = metrics
        self._artifacts = artifacts
        self._run_id = run_id
        self._start = time.monotonic()
        self._step_count = 0

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def log(self, message: str, **kwargs: Any) -> None:
        self._span.add_event(message, attributes=kwargs)

    @contextmanager
    def step(
        self, step_type: str, name: str = "", **attrs: Any
    ) -> Generator[Step, None, None]:
        step_id = _new_id()
        span_name = name or f"step.{step_type}"
        with self._tracer.start_as_current_span(
            span_name,
            attributes={"step_type": step_type, "step_id": step_id, **attrs},
        ) as span:
            s = Step(
                span,
                step_id,
                step_type,
                metrics=self._metrics,
                artifacts=self._artifacts,
                run_id=self._run_id,
                episode_id=self.episode_id,
            )
            try:
                yield s
            except Exception as exc:
                s._finish(error=exc)
                raise
            else:
                s._finish()
            finally:
                self._step_count += 1

    def _finish(self, error: BaseException | None = None) -> None:
        duration = time.monotonic() - self._start
        self._metrics.episode_duration.record(duration)
        self._metrics.episode_steps.record(self._step_count)
        if error:
            self._span.set_status(StatusCode.ERROR, str(error))
            self._span.record_exception(error)
        else:
            self._span.set_status(StatusCode.OK)


class Run:
    """Top-level trace representing an experiment run."""

    def __init__(
        self,
        span: Span,
        run_id: str,
        *,
        tracer: trace.Tracer,
        metrics: AgentMetrics,
        artifacts: ArtifactStore,
    ) -> None:
        self._span = span
        self.run_id = run_id
        self._tracer = tracer
        self._metrics = metrics
        self._artifacts = artifacts

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    @contextmanager
    def episode(self, name: str = "", **attrs: Any) -> Generator[Episode, None, None]:
        episode_id = _new_id()
        span_name = name or f"episode.{episode_id}"
        with self._tracer.start_as_current_span(
            span_name,
            attributes={"episode_id": episode_id, **attrs},
        ) as span:
            ep = Episode(
                span,
                episode_id,
                tracer=self._tracer,
                metrics=self._metrics,
                artifacts=self._artifacts,
                run_id=self.run_id,
            )
            try:
                yield ep
            except Exception as exc:
                ep._finish(error=exc)
                raise
            else:
                ep._finish()
