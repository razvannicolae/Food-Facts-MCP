"""Unit tests for resources.py, prompts.py, sampling.py, and citations.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# citations.py
# ---------------------------------------------------------------------------

def test_build_fdc_citation_fields():
    from food_facts_mcp.citations import build_fdc_citation
    c = build_fdc_citation(fdc_id=747448, description="Broccoli, raw",
                           data_type="Foundation", publication_date="2019-04-01")
    assert c["source"] == "USDA FoodData Central"
    assert c["fdcId"] == 747448
    assert c["url"] == "https://fdc.nal.usda.gov/food-details/747448/nutrients"
    assert "accessedDate" in c


def test_citation_from_food():
    from food_facts_mcp.citations import citation_from_food
    food = {"fdcId": 747448, "description": "Broccoli, raw", "dataType": "Foundation",
            "publicationDate": "2019-04-01"}
    c = citation_from_food(food)
    assert c["fdcId"] == 747448
    assert c["dataset"] == "Foundation"


def test_format_apa_citation():
    from food_facts_mcp.citations import format_apa_citation
    food = {"fdcId": 747448, "description": "Broccoli, raw",
            "dataType": "Foundation", "publicationDate": "2019-04-01"}
    apa = format_apa_citation(food)
    assert "747448" in apa and "Foundation" in apa


def test_format_mla_citation():
    from food_facts_mcp.citations import format_mla_citation
    food = {"fdcId": 747448, "description": "Broccoli, raw",
            "dataType": "Foundation", "publicationDate": "2019-04-01"}
    assert "747448" in format_mla_citation(food)


# ---------------------------------------------------------------------------
# resources.py
# ---------------------------------------------------------------------------

def test_get_nutrients_reference():
    from food_facts_mcp.resources import get_nutrients_reference
    nutrients = get_nutrients_reference()
    assert len(nutrients) > 10
    for n in nutrients:
        assert "number" in n and "name" in n and "unit" in n


def test_get_sources_info_keys():
    from food_facts_mcp.resources import get_sources_info
    info = get_sources_info()
    assert "USDA FoodData Central — Foundation" in info
    assert "USDA FoodData Central — Branded" in info


def test_get_server_metadata():
    from food_facts_mcp.resources import get_server_metadata
    meta = get_server_metadata()
    assert meta["name"] == "Food Facts MCP"
    assert meta["tools"] == 8
    assert "usdaFDC" in meta["dataSources"]


def test_get_fdc_food_resource():
    with patch("food_facts_mcp.resources.FDCClient") as MockClient:
        instance = MagicMock()
        instance.get_food.return_value = {"fdcId": 747448}
        MockClient.return_value = instance
        from food_facts_mcp.resources import get_fdc_food_resource
        result = get_fdc_food_resource(747448)
    assert result["fdcId"] == 747448


# ---------------------------------------------------------------------------
# prompts.py
# ---------------------------------------------------------------------------

def test_analyze_food_nutrition_prompt():
    from food_facts_mcp.prompts import get_prompt_messages
    msgs = get_prompt_messages("analyze_food_nutrition", {"food_name": "almonds"})
    text = msgs[0]["content"]["text"]
    assert "almonds" in text.lower()
    assert "search_foods" in text


def test_compare_foods_prompt():
    from food_facts_mcp.prompts import get_prompt_messages
    msgs = get_prompt_messages("compare_foods_for_goal",
                               {"food_a": "chicken", "food_b": "tofu", "goal": "high protein"})
    text = msgs[0]["content"]["text"]
    assert "chicken" in text and "tofu" in text and "high protein" in text


def test_dietary_advice_prompt():
    from food_facts_mcp.prompts import get_prompt_messages
    msgs = get_prompt_messages("dietary_advice",
                               {"query": "increase iron", "dietary_restrictions": "vegan"})
    text = msgs[0]["content"]["text"]
    assert "iron" in text.lower() and "vegan" in text


def test_meal_nutrition_summary_prompt():
    from food_facts_mcp.prompts import get_prompt_messages
    msgs = get_prompt_messages("meal_nutrition_summary", {"meal_description": "salmon with rice"})
    text = msgs[0]["content"]["text"]
    assert "salmon" in text and "get_food_nutrients" in text


def test_unknown_prompt_raises():
    from food_facts_mcp.prompts import get_prompt_messages
    with pytest.raises(ValueError, match="Unknown prompt"):
        get_prompt_messages("nonexistent", {})


def test_prompt_definitions_complete():
    from food_facts_mcp.prompts import PROMPT_DEFINITIONS
    names = {p["name"] for p in PROMPT_DEFINITIONS}
    assert names == {"analyze_food_nutrition", "compare_foods_for_goal",
                     "dietary_advice", "meal_nutrition_summary"}


# ---------------------------------------------------------------------------
# sampling.py
# ---------------------------------------------------------------------------

def test_nutrition_summary_request():
    from food_facts_mcp.sampling import create_nutrition_summary_request
    req = create_nutrition_summary_request({
        "description": "Broccoli, raw",
        "nutrients": [{"name": "Protein", "amount": 2.82, "unit": "g"}],
    })
    assert req["method"] == "sampling/createMessage"
    assert "Broccoli" in req["params"]["messages"][0]["content"]["text"]


def test_citation_text_request():
    from food_facts_mcp.sampling import create_citation_text_request
    req = create_citation_text_request({
        "fdcId": 747448, "description": "Broccoli, raw",
        "dataType": "Foundation", "publicationDate": "2019-04-01",
    })
    text = req["params"]["messages"][0]["content"]["text"]
    assert "747448" in text and "APA" in text
