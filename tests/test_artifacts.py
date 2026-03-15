"""Unit tests for ArtifactStore."""

from __future__ import annotations

import json

from agent_obs.artifacts import ArtifactStore


class TestArtifactStore:
    def test_save_string(self, tmp_path: str) -> None:
        store = ArtifactStore(tmp_path)
        path = store.save("r", "e", "s", "note.txt", "hello")
        assert path == "r/e/s/note.txt"
        assert (tmp_path / "r" / "e" / "s" / "note.txt").read_text() == "hello"

    def test_save_bytes(self, tmp_path: str) -> None:
        store = ArtifactStore(tmp_path)
        path = store.save("r", "e", "s", "data.bin", b"\x00\x01")
        assert path == "r/e/s/data.bin"
        assert (tmp_path / "r" / "e" / "s" / "data.bin").read_bytes() == b"\x00\x01"

    def test_save_dict_as_json(self, tmp_path: str) -> None:
        store = ArtifactStore(tmp_path)
        payload = {"key": "value", "num": 42}
        path = store.save("r", "e", "s", "data.json", payload)
        assert path == "r/e/s/data.json"
        saved = json.loads((tmp_path / "r" / "e" / "s" / "data.json").read_text())
        assert saved == payload
