"""Unit tests for FatSecret tools — all API calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sample API responses
# ---------------------------------------------------------------------------

SEARCH_RESPONSE = {
    "foods": {
        "total_results": "2",
        "page_number": "0",
        "max_results": "20",
        "food": [
            {
                "food_id": "36421",
                "food_name": "Chick-fil-A Chicken Sandwich",
                "food_type": "Brand",
                "brand_name": "Chick-fil-A",
                "food_url": "https://www.fatsecret.com/calories-nutrition/chick-fil-a/chicken-sandwich",
                "food_servings": {
                    "serving": [
                        {
                            "serving_id": "30644",
                            "serving_description": "1 sandwich",
                            "is_default": "1",
                            "calories": "440",
                            "protein": "28",
                            "carbohydrate": "40",
                            "fat": "19",
                        }
                    ]
                },
            },
            {
                "food_id": "12345",
                "food_name": "McChicken",
                "food_type": "Brand",
                "brand_name": "McDonald's",
                "food_url": "https://www.fatsecret.com/calories-nutrition/mcdonalds/mcchicken",
                "food_servings": {
                    "serving": {
                        "serving_id": "99999",
                        "serving_description": "1 sandwich",
                        "is_default": "1",
                        "calories": "400",
                    }
                },
            },
        ],
    }
}

FOOD_DETAIL_RESPONSE = {
    "food": {
        "food_id": "36421",
        "food_name": "Chick-fil-A Chicken Sandwich",
        "food_type": "Brand",
        "brand_name": "Chick-fil-A",
        "food_url": "https://www.fatsecret.com/calories-nutrition/chick-fil-a/chicken-sandwich",
        "servings": {
            "serving": [
                {
                    "serving_id": "30644",
                    "serving_description": "1 sandwich",
                    "metric_serving_amount": "185",
                    "metric_serving_unit": "g",
                    "is_default": "1",
                    "calories": "440",
                    "protein": "28",
                    "carbohydrate": "40",
                    "fat": "19",
                    "saturated_fat": "3.5",
                    "trans_fat": "0",
                    "cholesterol": "65",
                    "sodium": "1350",
                    "potassium": "340",
                    "fiber": "1",
                    "sugar": "5",
                    "vitamin_a": "2",
                    "vitamin_c": "0",
                    "calcium": "15",
                    "iron": "15",
                }
            ]
        },
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fs_mock(search_return=None, food_return=None):
    client = MagicMock()
    if search_return is not None:
        client.search_foods.return_value = search_return
    if food_return is not None:
        client.get_food.return_value = food_return
    return client


# ---------------------------------------------------------------------------
# search_fatsecret_foods
# ---------------------------------------------------------------------------

def test_search_returns_structure():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_RESPONSE)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="chicken sandwich")

    assert result["source"] == "FatSecret"
    assert result["query"] == "chicken sandwich"
    assert result["totalResults"] == 2
    assert len(result["foods"]) == 2


def test_search_food_fields():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_RESPONSE)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="chicken sandwich")

    first = result["foods"][0]
    assert first["foodId"] == "36421"
    assert first["foodName"] == "Chick-fil-A Chicken Sandwich"
    assert first["brandName"] == "Chick-fil-A"
    assert first["foodType"] == "Brand"
    assert first["calories"] == 440.0


def test_search_handles_single_serving_as_dict():
    """serving dict (not list) when only one serving — must not crash."""
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_RESPONSE)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="mcchicken")

    second = result["foods"][1]
    assert second["foodId"] == "12345"
    assert second["calories"] == 400.0


def test_search_passes_params():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        client = _make_fs_mock(search_return=SEARCH_RESPONSE)
        mock_get.return_value = client
        from food_facts_mcp.tools import search_fatsecret_foods
        search_fatsecret_foods(query="burger", max_results=10, page_number=2)

    client.search_foods.assert_called_once_with(
        query="burger", max_results=10, page_number=2
    )


# ---------------------------------------------------------------------------
# get_fatsecret_food
# ---------------------------------------------------------------------------

def test_get_food_returns_structure():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="36421")

    assert result["source"] == "FatSecret"
    assert result["foodId"] == "36421"
    assert result["foodName"] == "Chick-fil-A Chicken Sandwich"
    assert result["brandName"] == "Chick-fil-A"
    assert "servings" in result
    assert "citation" in result


def test_get_food_nutrients_parsed():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="36421")

    serving = result["servings"][0]
    assert serving["servingDescription"] == "1 sandwich"
    assert serving["isDefault"] is True
    assert serving["metricServingAmount"] == "185"
    nuts = serving["nutrients"]
    assert nuts["calories"] == 440.0
    assert nuts["protein"] == 28.0
    assert nuts["sodium"] == 1350.0
    assert nuts["saturated_fat"] == 3.5


def test_get_food_citation_fields():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="36421")

    assert result["citation"]["source"] == "FatSecret Platform API"
    assert result["citation"]["foodId"] == "36421"
    assert "fatsecret.com" in result["citation"]["url"]


def test_get_food_passes_food_id():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        client = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        mock_get.return_value = client
        from food_facts_mcp.tools import get_fatsecret_food
        get_fatsecret_food(food_id="36421")

    client.get_food.assert_called_once_with(food_id="36421")


# ---------------------------------------------------------------------------
# _parse_serving helper
# ---------------------------------------------------------------------------

def test_parse_serving_skips_missing_nutrients():
    from food_facts_mcp.tools import _parse_serving
    serving = {"serving_description": "1 cup", "calories": "100", "protein": None}
    parsed = _parse_serving(serving)
    assert parsed["nutrients"]["calories"] == 100.0
    assert "protein" not in parsed["nutrients"]


def test_parse_serving_handles_string_floats():
    from food_facts_mcp.tools import _parse_serving
    serving = {"calories": "440.5", "fat": "19.2"}
    parsed = _parse_serving(serving)
    assert parsed["nutrients"]["calories"] == 440.5
    assert parsed["nutrients"]["fat"] == 19.2
