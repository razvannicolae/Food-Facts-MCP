"""Unit tests for tools.py — all API calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

SEARCH_RESPONSE = {
    "totalHits": 2,
    "currentPage": 1,
    "totalPages": 1,
    "foods": [
        {
            "fdcId": 747448,
            "description": "Broccoli, raw",
            "dataType": "Foundation",
            "brandOwner": None,
            "publishedDate": "2019-04-01",
            "foodNutrients": [
                {"nutrientName": "Protein", "value": 2.82},
                {"nutrientName": "Iron, Fe", "value": 0.73},
            ],
        },
        {
            "fdcId": 170379,
            "description": "Broccoli, cooked",
            "dataType": "SR Legacy",
            "brandOwner": None,
            "publishedDate": "2019-04-01",
            "foodNutrients": [],
        },
    ],
}

FOOD_DETAIL = {
    "fdcId": 747448,
    "description": "Broccoli, raw",
    "dataType": "Foundation",
    "publicationDate": "2019-04-01",
    "brandOwner": None,
    "ndbNumber": None,
    "servingSize": 100,
    "servingSizeUnit": "g",
    "ingredients": None,
    "foodCategory": {"description": "Vegetables and Vegetable Products"},
    "foodNutrients": [
        {"nutrient": {"number": "203", "name": "Protein", "unitName": "g"}, "amount": 2.82},
        {"nutrient": {"number": "208", "name": "Energy", "unitName": "kcal"}, "amount": 34},
        {"nutrient": {"number": "303", "name": "Iron, Fe", "unitName": "mg"}, "amount": 0.73},
    ],
}


def test_search_foods_returns_structure():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.search_foods.return_value = SEARCH_RESPONSE
        mock_get.return_value = client

        from food_facts_mcp.tools import search_foods
        result = search_foods(query="broccoli")

    assert result["totalHits"] == 2
    assert len(result["foods"]) == 2
    assert result["foods"][0]["fdcId"] == 747448
    assert result["source"] == "USDA FoodData Central"
    assert "citation" not in result["foods"][0]


def test_search_foods_passes_data_type():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.search_foods.return_value = {"totalHits": 0, "currentPage": 1, "totalPages": 1, "foods": []}
        mock_get.return_value = client

        from food_facts_mcp.tools import search_foods
        search_foods(query="beef", data_type=["Foundation"], page_size=10)

    client.search_foods.assert_called_once_with(
        query="beef", data_type=["Foundation"], brand_owner=None,
        page_size=10, page_number=1,
    )


def test_get_food_returns_structure():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from food_facts_mcp.tools import get_food
        result = get_food(fdc_id=747448)

    assert result["fdcId"] == 747448
    assert "citation" in result
    assert result["source"] == "USDA FoodData Central"


def test_get_food_nutrients_sorted():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from food_facts_mcp.tools import get_food_nutrients
        result = get_food_nutrients(fdc_id=747448)

    numbers = [int(n["number"]) for n in result["nutrients"] if n["number"]]
    assert numbers == sorted(numbers)
    assert "citation" in result


def test_get_multiple_foods():
    multi = [FOOD_DETAIL, {**FOOD_DETAIL, "fdcId": 170379}]
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.get_multiple_foods.return_value = multi
        mock_get.return_value = client

        from food_facts_mcp.tools import get_multiple_foods
        result = get_multiple_foods(fdc_ids=[747448, 170379])

    assert len(result) == 2
    assert "citation" in result[0]


def test_compare_foods_structure():
    food_b = {
        **FOOD_DETAIL,
        "fdcId": 170379,
        "description": "Spinach, raw",
        "dataType": "SR Legacy",
        "foodNutrients": [
            {"nutrient": {"number": "203", "name": "Protein", "unitName": "g"}, "amount": 2.86},
            {"nutrient": {"number": "303", "name": "Iron, Fe", "unitName": "mg"}, "amount": 2.71},
        ],
    }
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.get_food.side_effect = [FOOD_DETAIL, food_b]
        mock_get.return_value = client

        from food_facts_mcp.tools import compare_foods
        result = compare_foods(fdc_id_a=747448, fdc_id_b=170379)

    iron = next(r for r in result["comparison"] if "Iron" in r["nutrient"])
    assert iron["higher"] == "Spinach, raw"


def test_list_foods():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.list_foods.return_value = [{"fdcId": 100, "description": "Apple", "dataType": "Foundation"}]
        mock_get.return_value = client

        from food_facts_mcp.tools import list_foods
        result = list_foods(page_size=10)

    assert result["pageSize"] == 10
    assert len(result["foods"]) == 1


def test_get_food_citation():
    with patch("food_facts_mcp.tools._get_fdc") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from food_facts_mcp.tools import get_food_citation
        result = get_food_citation(fdc_id=747448)

    assert "apa" in result
    assert "mla" in result
    assert "FDC ID: 747448" in result["apa"]
