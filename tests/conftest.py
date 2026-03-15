"""Test configuration."""

from __future__ import annotations

import httpx
import pytest


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
