"""Artifact storage — local filesystem only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    """Saves artifacts to local filesystem under base_dir/{run}/{episode}/{step}/."""

    def __init__(self, base_dir: str | Path = "./artifacts") -> None:
        self._base_dir = Path(base_dir)

    def save(
        self,
        run_id: str,
        episode_id: str,
        step_id: str,
        name: str,
        data: Any,
    ) -> str:
        """Save artifact and return the relative path."""
        dir_path = self._base_dir / run_id / episode_id / step_id
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / name

        if isinstance(data, bytes):
            file_path.write_bytes(data)
        elif isinstance(data, str):
            file_path.write_text(data, encoding="utf-8")
        else:
            file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        return str(file_path.relative_to(self._base_dir))
