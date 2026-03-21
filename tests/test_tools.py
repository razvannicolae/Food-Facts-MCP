"""Unit tests for tools.py — all FDC API calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Patch the FDCClient at the module level so no real HTTP calls are made.
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
            "description": "Broccoli, cooked, boiled, drained, without salt",
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
        {
            "nutrient": {"number": "203", "name": "Protein", "unitName": "g"},
            "amount": 2.82,
        },
        {
            "nutrient": {"number": "208", "name": "Energy", "unitName": "kcal"},
            "amount": 34,
        },
        {
            "nutrient": {"number": "303", "name": "Iron, Fe", "unitName": "mg"},
            "amount": 0.73,
        },
    ],
}


# ---------------------------------------------------------------------------
# search_foods
# ---------------------------------------------------------------------------


def test_search_foods_returns_structure():
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.search_foods.return_value = SEARCH_RESPONSE
        mock_get.return_value = client

        from usda_mcp.tools import search_foods

        result = search_foods(query="broccoli")

    assert result["totalHits"] == 2
    assert len(result["foods"]) == 2
    first = result["foods"][0]
    assert first["fdcId"] == 747448
    assert first["description"] == "Broccoli, raw"
    # search_foods omits per-item citation to keep response compact;
    # use get_food_citation(fdcId) for citation on a specific item.
    assert "citation" not in first


def test_search_foods_passes_data_type():
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.search_foods.return_value = {"totalHits": 0, "currentPage": 1, "totalPages": 1, "foods": []}
        mock_get.return_value = client

        from usda_mcp.tools import search_foods

        search_foods(query="beef", data_type=["Foundation"], page_size=10)

    client.search_foods.assert_called_once_with(
        query="beef",
        data_type=["Foundation"],
        brand_owner=None,
        page_size=10,
        page_number=1,
    )


# ---------------------------------------------------------------------------
# get_food
# ---------------------------------------------------------------------------


def test_get_food_returns_structure():
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from usda_mcp.tools import get_food

        result = get_food(fdc_id=747448)

    assert result["fdcId"] == 747448
    assert result["description"] == "Broccoli, raw"
    assert "citation" in result
    assert len(result["foodNutrients"]) == 3


# ---------------------------------------------------------------------------
# get_food_nutrients
# ---------------------------------------------------------------------------


def test_get_food_nutrients_sorted():
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from usda_mcp.tools import get_food_nutrients

        result = get_food_nutrients(fdc_id=747448)

    assert result["fdcId"] == 747448
    nutrients = result["nutrients"]
    # Verify sorted by nutrient number (203 < 208 < 303)
    numbers = [int(n["number"]) for n in nutrients if n["number"]]
    assert numbers == sorted(numbers)
    assert "citation" in result


# ---------------------------------------------------------------------------
# get_multiple_foods
# ---------------------------------------------------------------------------


def test_get_multiple_foods():
    multi_response = [FOOD_DETAIL, {**FOOD_DETAIL, "fdcId": 170379, "description": "Broccoli cooked"}]
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.get_multiple_foods.return_value = multi_response
        mock_get.return_value = client

        from usda_mcp.tools import get_multiple_foods

        result = get_multiple_foods(fdc_ids=[747448, 170379])

    assert len(result) == 2
    assert result[0]["fdcId"] == 747448
    assert "citation" in result[0]


# ---------------------------------------------------------------------------
# compare_foods
# ---------------------------------------------------------------------------


def test_compare_foods_structure():
    food_b = {
        **FOOD_DETAIL,
        "fdcId": 170379,
        "description": "Spinach, raw",
        "dataType": "SR Legacy",
        "foodNutrients": [
            {
                "nutrient": {"number": "203", "name": "Protein", "unitName": "g"},
                "amount": 2.86,
            },
            {
                "nutrient": {"number": "303", "name": "Iron, Fe", "unitName": "mg"},
                "amount": 2.71,
            },
        ],
    }
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.get_food.side_effect = [FOOD_DETAIL, food_b]
        mock_get.return_value = client

        from usda_mcp.tools import compare_foods

        result = compare_foods(fdc_id_a=747448, fdc_id_b=170379)

    assert result["foodA"]["fdcId"] == 747448
    assert result["foodB"]["fdcId"] == 170379
    assert len(result["comparison"]) > 0

    # Iron: broccoli 0.73, spinach 2.71 → spinach higher
    iron_row = next((r for r in result["comparison"] if "Iron" in r["nutrient"]), None)
    assert iron_row is not None
    assert iron_row["higher"] == "Spinach, raw"


# ---------------------------------------------------------------------------
# list_foods
# ---------------------------------------------------------------------------


def test_list_foods():
    list_response = [
        {"fdcId": 100, "description": "Apple, raw", "dataType": "Foundation", "publicationDate": "2020-01-01"},
    ]
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.list_foods.return_value = list_response
        mock_get.return_value = client

        from usda_mcp.tools import list_foods

        result = list_foods(page_size=10)

    assert result["pageSize"] == 10
    assert len(result["foods"]) == 1


# ---------------------------------------------------------------------------
# get_food_citation
# ---------------------------------------------------------------------------


def test_get_food_citation():
    with patch("usda_mcp.tools._get_client") as mock_get:
        client = MagicMock()
        client.get_food.return_value = FOOD_DETAIL
        mock_get.return_value = client

        from usda_mcp.tools import get_food_citation

        result = get_food_citation(fdc_id=747448)

    assert result["fdcId"] == 747448
    assert "citation" in result
    assert "apa" in result
    assert "mla" in result
    assert "FDC ID: 747448" in result["apa"]
    assert "fdc.nal.usda.gov" in result["url"]
