"""Test configuration."""

import sys
from pathlib import Path

import httpx
import pytest

# Add scripts/ to sys.path so tests can import query scripts directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


@pytest.fixture()
def mock_httpx_response():
    """Factory for httpx.Response with a request attached (needed for raise_for_status)."""

    def _make(status_code: int = 200, *, json: dict | None = None) -> httpx.Response:
        return httpx.Response(
            status_code,
            json=json,
            request=httpx.Request("GET", "http://test"),
        )

    return _make
