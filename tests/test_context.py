"""Unit tests for ExperimentContext."""

from __future__ import annotations

from agent_obs.context import ExperimentContext


class TestExperimentContext:
    def test_minimal_resource_has_required_attrs(self) -> None:
        ctx = ExperimentContext(run_id="r1", prompt_version="v1")
        resource = ctx.to_resource()
        attrs = dict(resource.attributes)
        assert attrs["run_id"] == "r1"
        assert attrs["prompt_version"] == "v1"
        assert attrs["service.name"] == "agent-obs"
        assert "model" not in attrs
        assert "task_type" not in attrs
        assert "branch" not in attrs
        assert "commit_sha" not in attrs

    def test_all_optional_fields_included(self) -> None:
        ctx = ExperimentContext(
            run_id="r1",
            prompt_version="v1",
            model="gpt-4",
            task_type="qa",
            branch="main",
            commit_sha="abc123",
            extra={"env": "test"},
        )
        resource = ctx.to_resource()
        attrs = dict(resource.attributes)
        assert attrs["model"] == "gpt-4"
        assert attrs["task_type"] == "qa"
        assert attrs["branch"] == "main"
        assert attrs["commit_sha"] == "abc123"
        assert attrs["env"] == "test"

    def test_frozen(self) -> None:
        ctx = ExperimentContext(run_id="r1", prompt_version="v1")
        try:
            ctx.run_id = "r2"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
