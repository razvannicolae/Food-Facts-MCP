"""Unit tests for cache.py — uses in-memory SQLite (no files written)."""

from __future__ import annotations

import json
import time

import pytest

from food_facts_mcp.cache import FoodCache


@pytest.fixture
def cache():
    """Fresh in-memory FoodCache for each test."""
    c = FoodCache(db_path=":memory:", ttl_days=None)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# make_key
# ---------------------------------------------------------------------------

def test_make_key_is_deterministic():
    k1 = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    k2 = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    assert k1 == k2


def test_make_key_differs_by_tool():
    k1 = FoodCache.make_key("get_food", fdc_id=747448)
    k2 = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    assert k1 != k2


def test_make_key_differs_by_args():
    k1 = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    k2 = FoodCache.make_key("get_food_nutrients", fdc_id=170379)
    assert k1 != k2


def test_make_key_kwargs_order_irrelevant():
    k1 = FoodCache.make_key("search_foods", query="broccoli", page_size=25)
    k2 = FoodCache.make_key("search_foods", page_size=25, query="broccoli")
    assert k1 == k2


# ---------------------------------------------------------------------------
# get / set basic flow
# ---------------------------------------------------------------------------

def test_miss_returns_none(cache):
    key = FoodCache.make_key("get_food_nutrients", fdc_id=1)
    assert cache.get("usda_fdc", key) is None


def test_set_then_get_returns_data(cache):
    data = {"fdcId": 747448, "description": "Broccoli, raw", "nutrients": []}
    key = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    cache.set("usda_fdc", "get_food_nutrients", key, data)
    result = cache.get("usda_fdc", key)
    assert result == data


def test_hit_count_increments(cache):
    data = {"fdcId": 1}
    key = FoodCache.make_key("get_food", fdc_id=1)
    cache.set("usda_fdc", "get_food", key, data)
    cache.get("usda_fdc", key)
    cache.get("usda_fdc", key)
    row = cache._conn.execute(
        "SELECT hit_count FROM cache_entries WHERE cache_key=?", (key,)
    ).fetchone()
    assert row[0] == 2


def test_set_upserts_existing_key(cache):
    key = FoodCache.make_key("get_food", fdc_id=1)
    cache.set("usda_fdc", "get_food", key, {"v": 1})
    cache.set("usda_fdc", "get_food", key, {"v": 2})
    result = cache.get("usda_fdc", key)
    assert result == {"v": 2}
    count = cache._conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
    assert count == 1


def test_different_sources_independent(cache):
    key = FoodCache.make_key("get_food_nutrients", fdc_id=1)
    cache.set("usda_fdc", "get_food_nutrients", key, {"source": "fdc"})
    cache.set("open_food_facts", "get_food_nutrients", key, {"source": "off"})
    assert cache.get("usda_fdc", key)["source"] == "fdc"
    assert cache.get("open_food_facts", key)["source"] == "off"


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

def test_expired_entry_returns_none():
    """TTL of 0 days should expire immediately."""
    c = FoodCache(db_path=":memory:", ttl_days=0)
    key = FoodCache.make_key("get_food", fdc_id=1)
    c.set("usda_fdc", "get_food", key, {"fdcId": 1})
    assert c.get("usda_fdc", key) is None
    c.close()


def test_no_ttl_never_expires(cache):
    key = FoodCache.make_key("get_food", fdc_id=1)
    cache.set("usda_fdc", "get_food", key, {"fdcId": 1})
    assert cache.get("usda_fdc", key) is not None


# ---------------------------------------------------------------------------
# food_index / list_foods
# ---------------------------------------------------------------------------

def test_food_indexed_on_set(cache):
    data = {"fdcId": 747448, "description": "Broccoli, raw", "dataType": "Foundation",
            "source": "USDA FoodData Central"}
    key = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    cache.set("usda_fdc", "get_food_nutrients", key, data)
    foods = cache.list_foods()
    assert any(f["fdcId"] == 747448 for f in foods)


def test_list_foods_filter_by_query(cache):
    key1 = FoodCache.make_key("get_food_nutrients", fdc_id=747448)
    key2 = FoodCache.make_key("get_food_nutrients", fdc_id=170379)
    cache.set("usda_fdc", "get_food_nutrients", key1,
              {"fdcId": 747448, "description": "Broccoli, raw"})
    cache.set("usda_fdc", "get_food_nutrients", key2,
              {"fdcId": 170379, "description": "Broccoli, cooked"})
    foods = cache.list_foods(query="raw")
    assert len(foods) == 1
    assert foods[0]["fdcId"] == 747448


def test_list_foods_filter_by_source(cache):
    key = FoodCache.make_key("get_food_nutrients", fdc_id=1)
    cache.set("usda_fdc", "get_food_nutrients", key, {"fdcId": 1, "description": "Apple"})
    cache.set("open_food_facts", "get_food_nutrients", key, {"fdcId": 1, "description": "Apple"})
    foods = cache.list_foods(source="usda_fdc")
    assert all(f["source"] == "usda_fdc" for f in foods)


def test_list_foods_limit(cache):
    for i in range(10):
        k = FoodCache.make_key("get_food", fdc_id=i)
        cache.set("usda_fdc", "get_food", k, {"fdcId": i, "description": f"Food {i}"})
    foods = cache.list_foods(limit=3)
    assert len(foods) == 3


def test_list_foods_indexes_list_response(cache):
    data = [
        {"fdcId": 1, "description": "Food A", "dataType": "Foundation"},
        {"fdcId": 2, "description": "Food B", "dataType": "SR Legacy"},
    ]
    key = FoodCache.make_key("get_multiple_foods", fdc_ids=[1, 2])
    cache.set("usda_fdc", "get_multiple_foods", key, data)
    foods = cache.list_foods()
    fdc_ids = {f["fdcId"] for f in foods}
    assert {1, 2}.issubset(fdc_ids)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def test_stats_empty(cache):
    s = cache.stats()
    assert s["totalEntries"] == 0
    assert s["bySource"] == {}
    assert s["byTool"] == {}


def test_stats_after_inserts(cache):
    for i, tool in enumerate(["get_food", "get_food", "search_foods"]):
        k = FoodCache.make_key(tool, fdc_id=i)
        cache.set("usda_fdc", tool, k, {"fdcId": i})
    s = cache.stats()
    assert s["totalEntries"] == 3
    assert s["bySource"]["usda_fdc"] == 3
    assert s["byTool"]["get_food"] == 2
    assert s["byTool"]["search_foods"] == 1


def test_stats_db_size_positive(cache):
    k = FoodCache.make_key("get_food", fdc_id=1)
    cache.set("usda_fdc", "get_food", k, {"fdcId": 1})
    assert cache.stats()["dbSizeKb"] > 0


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------

def test_clear_all(cache):
    for i in range(5):
        k = FoodCache.make_key("get_food", fdc_id=i)
        cache.set("usda_fdc", "get_food", k, {"fdcId": i})
    deleted = cache.clear()
    assert deleted == 5
    assert cache.stats()["totalEntries"] == 0


def test_clear_by_source(cache):
    for i in range(3):
        k = FoodCache.make_key("get_food", fdc_id=i)
        cache.set("usda_fdc", "get_food", k, {"fdcId": i})
        cache.set("open_food_facts", "get_food", k, {"fdcId": i})
    deleted = cache.clear(source="usda_fdc")
    assert deleted == 3
    assert cache.stats()["totalEntries"] == 3


def test_clear_by_tool(cache):
    for i in range(2):
        k = FoodCache.make_key("get_food", fdc_id=i)
        cache.set("usda_fdc", "get_food", k, {"fdcId": i})
    k2 = FoodCache.make_key("search_foods", query="apple")
    cache.set("usda_fdc", "search_foods", k2, {"foods": []})
    deleted = cache.clear(tool_name="get_food")
    assert deleted == 2
    assert cache.stats()["totalEntries"] == 1


def test_clear_by_source_and_tool(cache):
    k = FoodCache.make_key("get_food", fdc_id=1)
    cache.set("usda_fdc", "get_food", k, {"fdcId": 1})
    cache.set("open_food_facts", "get_food", k, {"fdcId": 1})
    deleted = cache.clear(source="usda_fdc", tool_name="get_food")
    assert deleted == 1
    assert cache.stats()["bySource"].get("open_food_facts") == 1


def test_clear_nonexistent_returns_zero(cache):
    assert cache.clear(source="nonexistent") == 0
