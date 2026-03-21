"""Unit tests for resources.py, prompts.py, sampling.py, and citations.py."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# citations.py
# ---------------------------------------------------------------------------


def test_build_citation_fields():
    from usda_mcp.citations import build_citation

    c = build_citation(
        fdc_id=747448,
        description="Broccoli, raw",
        data_type="Foundation",
        publication_date="2019-04-01",
    )
    assert c["source"] == "USDA FoodData Central"
    assert c["fdcId"] == 747448
    assert c["url"] == "https://fdc.nal.usda.gov/food-details/747448/nutrients"
    assert c["publicationDate"] == "2019-04-01"
    assert "accessedDate" in c


def test_citation_from_food():
    from usda_mcp.citations import citation_from_food

    food = {
        "fdcId": 747448,
        "description": "Broccoli, raw",
        "dataType": "Foundation",
        "publicationDate": "2019-04-01",
        "brandOwner": None,
        "ndbNumber": None,
    }
    c = citation_from_food(food)
    assert c["fdcId"] == 747448
    assert c["dataset"] == "Foundation"


def test_format_apa_citation():
    from usda_mcp.citations import format_apa_citation

    food = {
        "fdcId": 747448,
        "description": "Broccoli, raw",
        "dataType": "Foundation",
        "publicationDate": "2019-04-01",
    }
    apa = format_apa_citation(food)
    assert "747448" in apa
    assert "Broccoli, raw" in apa
    assert "Foundation" in apa
    assert "2019-04-01" in apa


def test_format_mla_citation():
    from usda_mcp.citations import format_mla_citation

    food = {
        "fdcId": 747448,
        "description": "Broccoli, raw",
        "dataType": "Foundation",
        "publicationDate": "2019-04-01",
    }
    mla = format_mla_citation(food)
    assert "747448" in mla
    assert "Broccoli, raw" in mla


# ---------------------------------------------------------------------------
# resources.py
# ---------------------------------------------------------------------------


def test_get_nutrients_reference_structure():
    from usda_mcp.resources import get_nutrients_reference

    nutrients = get_nutrients_reference()
    assert isinstance(nutrients, list)
    assert len(nutrients) > 10
    # Every entry must have number, name, unit
    for n in nutrients:
        assert "number" in n
        assert "name" in n
        assert "unit" in n


def test_get_datasets_info_keys():
    from usda_mcp.resources import get_datasets_info

    info = get_datasets_info()
    for key in ["Foundation", "SR Legacy", "Branded", "Survey (FNDDS)"]:
        assert key in info
        assert "description" in info[key]
        assert "best_for" in info[key]


def test_get_server_metadata_fields():
    from usda_mcp.resources import get_server_metadata

    meta = get_server_metadata()
    assert "version" in meta
    assert "apiBaseUrl" in meta
    assert "rateLimit" in meta
    assert "apiKeyConfigured" in meta
    assert meta["mcpCapabilities"]["tools"] == 8


def test_get_food_resource_calls_client():
    with patch("usda_mcp.resources.FDCClient") as MockClient:
        instance = MagicMock()
        instance.get_food.return_value = {"fdcId": 747448, "description": "Broccoli, raw"}
        MockClient.return_value = instance

        from usda_mcp.resources import get_food_resource

        result = get_food_resource(747448)

    assert result["fdcId"] == 747448
    instance.get_food.assert_called_once_with(fdc_id=747448)


# ---------------------------------------------------------------------------
# prompts.py
# ---------------------------------------------------------------------------


def test_analyze_food_nutrition_prompt():
    from usda_mcp.prompts import get_prompt_messages

    msgs = get_prompt_messages("analyze_food_nutrition", {"food_name": "almonds"})
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    text = msgs[0]["content"]["text"]
    assert "almonds" in text.lower()
    assert "search_foods" in text
    assert "get_food_nutrients" in text
    assert "citation" in text.lower()


def test_analyze_food_nutrition_with_goal():
    from usda_mcp.prompts import get_prompt_messages

    msgs = get_prompt_messages(
        "analyze_food_nutrition",
        {"food_name": "salmon", "health_goal": "heart health"},
    )
    text = msgs[0]["content"]["text"]
    assert "heart health" in text


def test_compare_foods_prompt():
    from usda_mcp.prompts import get_prompt_messages

    msgs = get_prompt_messages(
        "compare_foods_for_goal",
        {"food_a": "chicken", "food_b": "tofu", "goal": "high protein"},
    )
    text = msgs[0]["content"]["text"]
    assert "chicken" in text
    assert "tofu" in text
    assert "high protein" in text
    assert "compare_foods" in text


def test_dietary_advice_prompt():
    from usda_mcp.prompts import get_prompt_messages

    msgs = get_prompt_messages(
        "dietary_advice",
        {"query": "how to increase iron intake", "dietary_restrictions": "vegan"},
    )
    text = msgs[0]["content"]["text"]
    assert "iron" in text.lower()
    assert "vegan" in text


def test_meal_nutrition_summary_prompt():
    from usda_mcp.prompts import get_prompt_messages

    msgs = get_prompt_messages(
        "meal_nutrition_summary",
        {"meal_description": "grilled salmon with rice"},
    )
    text = msgs[0]["content"]["text"]
    assert "salmon" in text
    assert "get_food_nutrients" in text


def test_unknown_prompt_raises():
    from usda_mcp.prompts import get_prompt_messages

    with pytest.raises(ValueError, match="Unknown prompt"):
        get_prompt_messages("nonexistent_prompt", {})


def test_prompt_definitions_complete():
    from usda_mcp.prompts import PROMPT_DEFINITIONS

    names = {p["name"] for p in PROMPT_DEFINITIONS}
    assert names == {
        "analyze_food_nutrition",
        "compare_foods_for_goal",
        "dietary_advice",
        "meal_nutrition_summary",
    }


# ---------------------------------------------------------------------------
# sampling.py
# ---------------------------------------------------------------------------


def test_nutrition_summary_request_structure():
    from usda_mcp.sampling import create_nutrition_summary_request

    food = {
        "description": "Broccoli, raw",
        "nutrients": [
            {"name": "Protein", "amount": 2.82, "unit": "g"},
            {"name": "Iron, Fe", "amount": 0.73, "unit": "mg"},
        ],
    }
    req = create_nutrition_summary_request(food)
    assert req["method"] == "sampling/createMessage"
    msgs = req["params"]["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    text = msgs[0]["content"]["text"]
    assert "Broccoli" in text
    assert "Protein" in text
    assert req["params"]["maxTokens"] == 150


def test_citation_text_request_structure():
    from usda_mcp.sampling import create_citation_text_request

    food = {
        "fdcId": 747448,
        "description": "Broccoli, raw",
        "dataType": "Foundation",
        "publicationDate": "2019-04-01",
    }
    req = create_citation_text_request(food)
    assert req["method"] == "sampling/createMessage"
    text = req["params"]["messages"][0]["content"]["text"]
    assert "747448" in text
    assert "Foundation" in text
    assert "APA" in text
    assert "MLA" in text
