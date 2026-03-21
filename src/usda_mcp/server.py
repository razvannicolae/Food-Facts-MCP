"""USDA FoodData Central MCP Server.

Transport options (--transport flag):
  stdio               — default, used by MCP clients like Claude Desktop
  streamable-http     — HTTP server on 0.0.0.0:8000 (or --port N)

Capabilities advertised:
  tools, resources (no subscribe), prompts, sampling
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from . import tools as _tools
from . import resources as _resources
from . import prompts as _prompts
from .prompts import PROMPT_DEFINITIONS
from .resources import NUTRIENT_REFERENCE, DATASET_INFO

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "USDA FoodData Central",
    instructions=(
        "This server gives you real-time access to USDA FoodData Central (FDC). "
        "Use search_foods to find foods by keyword, get_food_nutrients for detailed "
        "nutrient tables, compare_foods for side-by-side analysis, and "
        "get_food_citation for citation-ready metadata. "
        "All tool responses include a 'citation' block with fdcId, dataset, "
        "publication date, and URL pointing to fdc.nal.usda.gov.\n\n"
        "IMPORTANT — choosing the right data_type:\n"
        "- Natural/whole foods (fruits, vegetables, meats, grains as grown/raised): "
        "use data_type=['Foundation', 'SR Legacy']. Foundation has the most precise "
        "analytical data; SR Legacy has the broadest coverage.\n"
        "- Processed/packaged/fortified products (cereals, supplements, branded items): "
        "use data_type=['Branded'].\n"
        "- Foods as typically eaten in meals (cooked, mixed dishes): "
        "use data_type=['Survey (FNDDS)'].\n"
        "- No filter = all datasets mixed; Branded dominates (largest dataset) and "
        "will flood results with fortified/processed products.\n"
        "Always infer the user's intent: questions about 'natural sources of X' or "
        "'whole foods high in Y' should use data_type=['Foundation', 'SR Legacy']. "
        "Questions about specific products or brands should use data_type=['Branded'].\n\n"
        "DEFAULT BEHAVIOR for 'top foods high in X' or 'best sources of X': "
        "ALWAYS call list_foods_by_nutrient with prefer_whole_foods=True unless the "
        "user explicitly asks for packaged, fortified, or branded products. "
        "Never search for the nutrient name with search_foods to rank foods — "
        "use list_foods_by_nutrient instead, which uses food-category terms to avoid "
        "fortified products appearing in results."
    ),
)

# ---------------------------------------------------------------------------
# Tools — 8 total
# ---------------------------------------------------------------------------


@mcp.tool()
def search_foods(
    query: str,
    data_type: list[str] | None = None,
    brand_owner: str | None = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    """Search USDA FoodData Central by keyword.

    Without a data_type filter, results mix all datasets and Branded (packaged/
    fortified products) will dominate. Set data_type based on user intent:
    - Natural/whole foods (fruits, veg, meats, grains) → ["Foundation", "SR Legacy"]
    - Packaged/branded/fortified products → ["Branded"]
    - Foods as eaten in meals (cooked, mixed) → ["Survey (FNDDS)"]

    Args:
        query: Search term (food name, ingredient, brand, etc.)
        data_type: Filter by dataset(s). Options: "Foundation", "SR Legacy",
            "Branded", "Survey (FNDDS)". Omit only when intentionally searching
            across all datasets.
        brand_owner: Optional brand name filter (Branded foods only)
        page_size: Results per page, 1–200 (default 25)
        page_number: Page number, starting at 1
    """
    return _tools.search_foods(
        query=query,
        data_type=data_type,
        brand_owner=brand_owner,
        page_size=page_size,
        page_number=page_number,
    )


@mcp.tool()
def get_food(
    fdc_id: int,
    nutrients: list[int] | None = None,
    format: str | None = None,
) -> dict:
    """Get full details for a single food item by FDC ID.

    Args:
        fdc_id: USDA FoodData Central ID (e.g. 747448)
        nutrients: Optional list of nutrient numbers to include (up to 25)
        format: "abridged" for a smaller response, "full" (default) for all fields
    """
    return _tools.get_food(fdc_id=fdc_id, nutrients=nutrients, format=format)


@mcp.tool()
def get_multiple_foods(
    fdc_ids: list[int],
    nutrients: list[int] | None = None,
) -> list[dict]:
    """Get details for up to 20 foods by FDC ID in a single API call.

    Args:
        fdc_ids: List of FDC IDs (max 20)
        nutrients: Optional list of nutrient numbers to include
    """
    return _tools.get_multiple_foods(fdc_ids=fdc_ids, nutrients=nutrients)


@mcp.tool()
def get_food_nutrients(fdc_id: int) -> dict:
    """Fetch a food and return a human-readable nutrient table with citation.

    Returns nutrients sorted by nutrient number with name, amount, unit,
    and percent daily value where available.

    Args:
        fdc_id: USDA FoodData Central ID
    """
    return _tools.get_food_nutrients(fdc_id=fdc_id)


@mcp.tool()
def compare_foods(fdc_id_a: int, fdc_id_b: int) -> dict:
    """Compare nutrient profiles of two foods side by side.

    Returns a comparison table showing each nutrient, amounts for both foods,
    the difference (A minus B), and which food has more.

    Args:
        fdc_id_a: FDC ID of the first food
        fdc_id_b: FDC ID of the second food
    """
    return _tools.compare_foods(fdc_id_a=fdc_id_a, fdc_id_b=fdc_id_b)


@mcp.tool()
def list_foods(
    data_type: list[str] | None = None,
    page_size: int = 50,
    page_number: int = 1,
    sort_by: str | None = None,
    sort_order: str | None = None,
) -> dict:
    """Browse all foods with pagination and optional filtering.

    Args:
        data_type: Filter by data type(s): Foundation, Branded, SR Legacy,
            Survey (FNDDS)
        page_size: Results per page, 1–200 (default 50)
        page_number: Page number (default 1)
        sort_by: Sort field — "dataType.keyword", "description.keyword",
            "fdcId", or "publishedDate"
        sort_order: "asc" or "desc"
    """
    return _tools.list_foods(
        data_type=data_type,
        page_size=page_size,
        page_number=page_number,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@mcp.tool()
def list_foods_by_nutrient(
    nutrient_name: str,
    top_n: int = 10,
    data_type: list[str] | None = None,
    prefer_whole_foods: bool = False,
) -> dict:
    """Return top N foods ranked highest for a given nutrient.

    ALWAYS set prefer_whole_foods=True (or data_type=["Foundation","SR Legacy"])
    unless the user specifically wants processed/packaged products. Without it,
    results are dominated by Branded foods — fortified cereals, supplement drinks,
    and packaged goods artificially high in the nutrient.

    When prefer_whole_foods=True, the tool uses food-category search terms instead
    of the nutrient name, so "vitamin C" searches "citrus orange strawberry pepper
    broccoli" — returning naturally nutrient-rich whole foods, not fortified products.

    Args:
        nutrient_name: Nutrient to rank by (e.g., "iron", "vitamin C", "protein",
            "folate", "magnesium"). Use the standard USDA name where possible.
        top_n: Number of top results to return (default 10)
        prefer_whole_foods: STRONGLY RECOMMENDED — set True whenever the user asks
            about natural sources, whole foods, or does not specifically request
            processed/packaged products. Restricts to Foundation + SR Legacy and
            uses food-category search to avoid fortified products. Default False.
        data_type: Explicit dataset filter — overrides prefer_whole_foods.
            ["Foundation", "SR Legacy"] = natural/whole foods (same as prefer_whole_foods=True)
            ["Branded"] = packaged/fortified products only
    """
    effective_data_type = data_type
    if prefer_whole_foods and data_type is None:
        effective_data_type = ["Foundation", "SR Legacy"]
    return _tools.list_foods_by_nutrient(
        nutrient_name=nutrient_name, top_n=top_n, data_type=effective_data_type
    )


@mcp.tool()
def get_food_citation(fdc_id: int) -> dict:
    """Return citation-ready metadata for a food item.

    Includes APA and MLA formatted citation strings plus the standard
    citation block with fdcId, dataset, publication date, and URL.

    Args:
        fdc_id: USDA FoodData Central ID
    """
    return _tools.get_food_citation(fdc_id=fdc_id)


# ---------------------------------------------------------------------------
# Resources — 4 total
# ---------------------------------------------------------------------------


@mcp.resource("usda://food/{fdc_id}")
def food_resource(fdc_id: str) -> str:
    """Full food item JSON from the live USDA FDC API.

    Returns the complete FDC food object as pretty-printed JSON.
    """
    data = _resources.get_food_resource(int(fdc_id))
    return json.dumps(data, indent=2)


@mcp.resource("usda://nutrients/reference")
def nutrients_reference_resource() -> str:
    """Static list of all standard USDA nutrient numbers, names, and units."""
    return json.dumps(NUTRIENT_REFERENCE, indent=2)


@mcp.resource("usda://datasets/info")
def datasets_info_resource() -> str:
    """Descriptions of each FDC data type: what they cover and when to use them."""
    return json.dumps(DATASET_INFO, indent=2)


@mcp.resource("usda://server/metadata")
def server_metadata_resource() -> str:
    """Server version, API base URL, rate limit info, and API key status."""
    return json.dumps(_resources.get_server_metadata(), indent=2)


# ---------------------------------------------------------------------------
# Prompts — 4 total
# ---------------------------------------------------------------------------


@mcp.prompt()
def analyze_food_nutrition(food_name: str, health_goal: str = "") -> list[dict]:
    """Analyze nutrition data for a food item with USDA FDC citations.

    Args:
        food_name: Name of the food to analyze
        health_goal: Optional health goal (e.g., weight loss, muscle gain)
    """
    return _prompts.get_prompt_messages(
        "analyze_food_nutrition",
        {"food_name": food_name, "health_goal": health_goal},
    )


@mcp.prompt()
def compare_foods_for_goal(food_a: str, food_b: str, goal: str) -> list[dict]:
    """Compare two foods for a specific health or dietary goal.

    Args:
        food_a: First food to compare
        food_b: Second food to compare
        goal: Health/dietary goal (e.g., 'high protein', 'low sodium')
    """
    return _prompts.get_prompt_messages(
        "compare_foods_for_goal",
        {"food_a": food_a, "food_b": food_b, "goal": goal},
    )


@mcp.prompt()
def dietary_advice(query: str, dietary_restrictions: str = "") -> list[dict]:
    """Evidence-based dietary advice anchored to specific USDA FDC food items.

    Args:
        query: The dietary question or concern
        dietary_restrictions: Optional restrictions (e.g., vegan, gluten-free)
    """
    return _prompts.get_prompt_messages(
        "dietary_advice",
        {"query": query, "dietary_restrictions": dietary_restrictions},
    )


@mcp.prompt()
def meal_nutrition_summary(meal_description: str) -> list[dict]:
    """Break a meal into components and produce a combined nutrition summary.

    Args:
        meal_description: Description of the meal
    """
    return _prompts.get_prompt_messages(
        "meal_nutrition_summary",
        {"meal_description": meal_description},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="USDA FoodData Central MCP Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport to use",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
