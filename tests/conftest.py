"""Pytest configuration — disable the SQLite cache for all tool tests."""

import os
import pytest


@pytest.fixture(autouse=True)
def disable_cache(monkeypatch):
    """Disable the response cache so tool tests always hit the mocked FDC client."""
    monkeypatch.setenv("CACHE_ENABLED", "false")
    # Reset the module-level singleton so changes take effect mid-session
    import food_facts_mcp.cache as _cache_mod
    monkeypatch.setattr(_cache_mod, "_instance", None)
    yield
    monkeypatch.setattr(_cache_mod, "_instance", None)
