"""Experiment context metadata, injected as OTel Resource attributes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opentelemetry.sdk.resources import Resource


@dataclass(frozen=True)
class ExperimentContext:
    """Immutable experiment metadata attached to all signals."""

    run_id: str
    prompt_version: str
    model: str = ""
    task_type: str = ""
    branch: str = ""
    commit_sha: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def to_resource(self) -> Resource:
        attrs: dict[str, Any] = {
            "service.name": "agent-obs",
            "run_id": self.run_id,
            "prompt_version": self.prompt_version,
        }
        if self.model:
            attrs["model"] = self.model
        if self.task_type:
            attrs["task_type"] = self.task_type
        if self.branch:
            attrs["branch"] = self.branch
        if self.commit_sha:
            attrs["commit_sha"] = self.commit_sha
        attrs.update(self.extra)
        return Resource.create(attrs)
