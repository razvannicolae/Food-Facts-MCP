"""Unit tests for FatSecret tools — all API calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sample API responses (v1 search + v2 food.get)
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
                "food_description": "Per 1 sandwich - Calories: 440kcal | Fat: 19.00g | Carbs: 40.00g | Protein: 28.00g",
            },
            {
                "food_id": "12345",
                "food_name": "Subway Footlong Cookie",
                "food_type": "Brand",
                "brand_name": "Subway",
                "food_url": "https://www.fatsecret.com/calories-nutrition/subway/footlong-cookie",
                "food_description": "Per 1 cookie - Calories: 220kcal | Fat: 10.00g | Carbs: 31.00g | Protein: 3.00g",
            },
        ],
    }
}

SEARCH_SINGLE_RESULT = {
    "foods": {
        "total_results": "1",
        "page_number": "0",
        "max_results": "20",
        # single result returned as dict, not list
        "food": {
            "food_id": "99",
            "food_name": "McChicken",
            "food_type": "Brand",
            "brand_name": "McDonald's",
            "food_url": "https://www.fatsecret.com/calories-nutrition/mcdonalds/mcchicken",
            "food_description": "Per 1 sandwich - Calories: 400kcal | Fat: 17.00g | Carbs: 42.00g | Protein: 14.00g",
        },
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
            "serving": {
                "serving_id": "30644",
                "serving_description": "1 sandwich",
                "metric_serving_amount": "185",
                "metric_serving_unit": "g",
                "number_of_units": "1.000",
                "measurement_description": "sandwich",
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
        },
    }
}

FOOD_DETAIL_MULTI_SERVING = {
    "food": {
        "food_id": "12345",
        "food_name": "Subway Footlong Cookie",
        "food_type": "Brand",
        "brand_name": "Subway",
        "food_url": "https://www.fatsecret.com/calories-nutrition/subway/footlong-cookie",
        "servings": {
            "serving": [
                {
                    "serving_id": "111",
                    "serving_description": "1 cookie",
                    "calories": "220",
                    "protein": "3",
                    "carbohydrate": "31",
                    "fat": "10",
                    "sodium": "160",
                    "fiber": "1",
                    "sugar": "18",
                },
                {
                    "serving_id": "112",
                    "serving_description": "100g",
                    "calories": "450",
                    "protein": "6",
                    "carbohydrate": "64",
                    "fat": "20",
                },
            ]
        },
    }
}


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


def test_search_parses_food_description():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_RESPONSE)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="chicken sandwich")

    first = result["foods"][0]
    assert first["foodId"] == "36421"
    assert first["foodName"] == "Chick-fil-A Chicken Sandwich"
    assert first["brandName"] == "Chick-fil-A"
    assert first["calories"] == 440.0
    assert first["fat"] == 19.0
    assert first["carbohydrate"] == 40.0
    assert first["protein"] == 28.0
    assert first["servingDescription"] == "Per 1 sandwich"


def test_search_subway_cookie():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_RESPONSE)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="subway footlong cookie")

    second = result["foods"][1]
    assert second["foodName"] == "Subway Footlong Cookie"
    assert second["calories"] == 220.0
    assert second["carbohydrate"] == 31.0


def test_search_handles_single_result_as_dict():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(search_return=SEARCH_SINGLE_RESULT)
        from food_facts_mcp.tools import search_fatsecret_foods
        result = search_fatsecret_foods(query="mcchicken")

    assert len(result["foods"]) == 1
    assert result["foods"][0]["calories"] == 400.0


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
# _parse_food_description
# ---------------------------------------------------------------------------

def test_parse_food_description_standard():
    from food_facts_mcp.tools import _parse_food_description
    desc = "Per 1 serving - Calories: 220kcal | Fat: 10.00g | Carbs: 31.00g | Protein: 3.00g"
    parsed = _parse_food_description(desc)
    assert parsed["calories"] == 220.0
    assert parsed["fat"] == 10.0
    assert parsed["carbohydrate"] == 31.0
    assert parsed["protein"] == 3.0
    assert parsed["servingDescription"] == "Per 1 serving"


def test_parse_food_description_empty():
    from food_facts_mcp.tools import _parse_food_description
    assert _parse_food_description("") == {}
    assert _parse_food_description("No dash here") == {}


def test_parse_food_description_per_100g():
    from food_facts_mcp.tools import _parse_food_description
    desc = "Per 100g - Calories: 489kcal | Fat: 28.57g | Carbs: 0.00g | Protein: 57.14g"
    parsed = _parse_food_description(desc)
    assert parsed["servingDescription"] == "Per 100g"
    assert parsed["calories"] == 489.0
    assert parsed["protein"] == 57.14


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
    assert len(result["servings"]) == 1
    assert "citation" in result


def test_get_food_single_serving_as_dict():
    """food.get.v2 returns serving as dict (not list) when only one serving."""
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="36421")

    serving = result["servings"][0]
    assert serving["servingDescription"] == "1 sandwich"
    assert serving["nutrients"]["calories"] == 440.0
    assert serving["nutrients"]["protein"] == 28.0
    assert serving["nutrients"]["sodium"] == 1350.0
    assert serving["nutrients"]["saturated_fat"] == 3.5


def test_get_food_multi_serving():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_MULTI_SERVING)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="12345")

    assert len(result["servings"]) == 2
    assert result["servings"][0]["nutrients"]["calories"] == 220.0
    assert result["servings"][1]["nutrients"]["calories"] == 450.0


def test_get_food_empty_response():
    """Silently empty API response returns error dict, not crash."""
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return={})
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="999")

    assert "error" in result


def test_get_food_citation_fields():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        mock_get.return_value = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        from food_facts_mcp.tools import get_fatsecret_food
        result = get_fatsecret_food(food_id="36421")

    assert result["citation"]["source"] == "FatSecret Platform API"
    assert result["citation"]["foodId"] == "36421"


def test_get_food_passes_food_id():
    with patch("food_facts_mcp.tools._get_fs") as mock_get:
        client = _make_fs_mock(food_return=FOOD_DETAIL_RESPONSE)
        mock_get.return_value = client
        from food_facts_mcp.tools import get_fatsecret_food
        get_fatsecret_food(food_id="36421")

    client.get_food.assert_called_once_with(food_id="36421")


# ---------------------------------------------------------------------------
# _parse_serving
# ---------------------------------------------------------------------------

def test_parse_serving_skips_none_nutrients():
    from food_facts_mcp.tools import _parse_serving
    serving = {"serving_description": "1 cup", "calories": "100", "protein": None}
    parsed = _parse_serving(serving)
    assert parsed["nutrients"]["calories"] == 100.0
    assert "protein" not in parsed["nutrients"]


def test_parse_serving_string_floats():
    from food_facts_mcp.tools import _parse_serving
    serving = {"calories": "440.5", "fat": "19.2", "sodium": "1350"}
    parsed = _parse_serving(serving)
    assert parsed["nutrients"]["calories"] == 440.5
    assert parsed["nutrients"]["fat"] == 19.2
    assert parsed["nutrients"]["sodium"] == 1350.0


def test_parse_serving_measurement_fields():
    from food_facts_mcp.tools import _parse_serving
    serving = {
        "serving_id": "111",
        "serving_description": "1 sandwich",
        "metric_serving_amount": "185",
        "metric_serving_unit": "g",
        "number_of_units": "1.000",
        "measurement_description": "sandwich",
        "calories": "440",
    }
    parsed = _parse_serving(serving)
    assert parsed["servingId"] == "111"
    assert parsed["metricServingAmount"] == "185"
    assert parsed["metricServingUnit"] == "g"
    assert parsed["numberOfUnits"] == "1.000"
    assert parsed["measurementDescription"] == "sandwich"
