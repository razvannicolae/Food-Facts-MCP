"""Food Facts MCP Server.

Data sources:
  USDA FoodData Central — 8 tools, 4 resources, 4 prompts
  FatSecret              — 2 tools (restaurant & branded foods)
  Cache management       — 3 tools (stats, browse, clear)

Transport options (--transport flag):
  stdio               — default, used by Claude Desktop / Claude Code
  streamable-http     — HTTP server on 127.0.0.1:8000 (or --port N)
"""

from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

load_dotenv()

from mcp.server.fastmcp import FastMCP

from . import tools as _tools
from . import resources as _resources
from . import prompts as _prompts
from .cache import get_cache
from .resources import NUTRIENT_REFERENCE, SOURCES_INFO

mcp = FastMCP(
    "Food Facts MCP",
    instructions=(
        "This server provides nutrition data from USDA FoodData Central (FDC).\n\n"
        "DATASET SELECTION:\n"
        "- Natural/whole foods → data_type=['Foundation', 'SR Legacy']\n"
        "- Packaged/branded grocery items → data_type=['Branded']\n"
        "- Foods as eaten in meals → data_type=['Survey (FNDDS)']\n"
        "- No filter = all datasets (Branded will dominate results)\n\n"
        "NUTRIENT RANKING (list_foods_by_nutrient): always set prefer_whole_foods=True "
        "unless the user specifically wants processed/fortified products. This prevents "
        "fortified cereals and supplements from flooding the results.\n\n"
        "All tool responses include a 'citation' block with source, fdcId, dataset, and URL.\n\n"
        "FATSECRET (restaurant & branded foods):\n"
        "- Use search_fatsecret_foods to find fast food items (McDonald's, Chick-fil-A, etc.)\n"
        "- Then get_fatsecret_food with the returned food_id for full nutrition breakdown\n"
        "- food_type='Brand' = branded/restaurant, food_type='Generic' = generic"
    ),
)


# ===========================================================================
# Tools
# ===========================================================================


@mcp.tool()
def search_foods(
    query: str,
    data_type: list[str] | None = None,
    brand_owner: str | None = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    """Search USDA FoodData Central by keyword.

    Without a data_type filter, results mix all datasets and Branded dominates.
    Set data_type based on intent:
    - Natural/whole foods → ["Foundation", "SR Legacy"]
    - Packaged/branded → ["Branded"]
    - Foods as eaten in meals → ["Survey (FNDDS)"]

    Args:
        query: Search term (food name, ingredient, brand, etc.)
        data_type: Dataset filter — "Foundation", "SR Legacy", "Branded", "Survey (FNDDS)"
        brand_owner: Brand name filter (Branded foods only)
        page_size: Results per page, 1–200 (default 25)
        page_number: Page number (default 1)
    """
    return _tools.search_foods(
        query=query, data_type=data_type, brand_owner=brand_owner,
        page_size=page_size, page_number=page_number,
    )


@mcp.tool()
def get_food(
    fdc_id: int,
    nutrients: list[int] | None = None,
    format: str | None = None,
) -> dict:
    """Get full details for a single USDA FDC food item by FDC ID.

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
    """Get details for up to 20 USDA FDC foods by FDC ID in one request.

    Args:
        fdc_ids: List of FDC IDs (max 20)
        nutrients: Optional nutrient number filter
    """
    return _tools.get_multiple_foods(fdc_ids=fdc_ids, nutrients=nutrients)


@mcp.tool()
def get_food_nutrients(fdc_id: int) -> dict:
    """Get a human-readable nutrient table for a USDA FDC food item.

    Returns nutrients sorted by nutrient number with name, amount, unit,
    and percent daily value. Null-amount nutrients are excluded.

    Args:
        fdc_id: USDA FoodData Central ID
    """
    return _tools.get_food_nutrients(fdc_id=fdc_id)


@mcp.tool()
def compare_foods(fdc_id_a: int, fdc_id_b: int) -> dict:
    """Compare nutrient profiles of two USDA FDC foods side by side.

    Returns a table with each nutrient, amounts for both foods, difference
    (A minus B), and which food has more.

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
    """Browse USDA FDC foods with pagination and optional filtering.

    Args:
        data_type: Filter by dataset(s)
        page_size: Results per page, 1–200 (default 50)
        page_number: Page number (default 1)
        sort_by: "dataType.keyword", "description.keyword", "fdcId", "publishedDate"
        sort_order: "asc" or "desc"
    """
    return _tools.list_foods(
        data_type=data_type, page_size=page_size, page_number=page_number,
        sort_by=sort_by, sort_order=sort_order,
    )


@mcp.tool()
def list_foods_by_nutrient(
    nutrient_name: str,
    top_n: int = 10,
    data_type: list[str] | None = None,
    prefer_whole_foods: bool = False,
) -> dict:
    """Return top N USDA FDC foods ranked highest for a given nutrient.

    ALWAYS set prefer_whole_foods=True unless the user specifically wants
    processed/fortified products. Without it, results are dominated by
    Branded foods — fortified cereals, supplement drinks, and products
    artificially enriched with the nutrient.

    Args:
        nutrient_name: Nutrient to rank by (e.g., "iron", "vitamin C", "protein")
        top_n: Number of top results to return (default 10)
        prefer_whole_foods: STRONGLY RECOMMENDED — set True for natural food sources.
            Restricts to Foundation + SR Legacy and uses food-category search.
        data_type: Explicit dataset filter — overrides prefer_whole_foods.
    """
    effective_data_type = data_type
    if prefer_whole_foods and data_type is None:
        effective_data_type = ["Foundation", "SR Legacy"]
    return _tools.list_foods_by_nutrient(
        nutrient_name=nutrient_name, top_n=top_n, data_type=effective_data_type,
    )


@mcp.tool()
def get_food_citation(fdc_id: int) -> dict:
    """Return citation-ready metadata for a USDA FDC food item.

    Includes APA and MLA formatted citation strings.

    Args:
        fdc_id: USDA FoodData Central ID
    """
    return _tools.get_food_citation(fdc_id=fdc_id)


# ===========================================================================
# FatSecret tools
# ===========================================================================


@mcp.tool()
def search_fatsecret_foods(
    query: str,
    max_results: int = 3,
    page_number: int = 0,
) -> dict:
    """Search the FatSecret food database — strong coverage of branded and restaurant foods.

    Good for fast food chains (McDonald's, Chick-fil-A, etc.) and packaged products.
    Returns food IDs you can pass to get_fatsecret_food for full nutrition.

    Args:
        query: Food name or restaurant item (e.g. "McChicken", "Chick-fil-A sandwich")
        max_results: Number of results, 1–50 (default 20)
        page_number: Zero-based page offset (default 0)
    """
    return _tools.search_fatsecret_foods(
        query=query, max_results=max_results, page_number=page_number,
    )


@mcp.tool()
def get_fatsecret_food(food_id: int) -> dict:
    """Get full nutrition details for a FatSecret food by its food ID.

    Returns all available servings with a complete nutrient breakdown:
    calories, protein, fat, carbs, fiber, sugar, sodium, cholesterol,
    vitamins A/C/D, calcium, iron, and more.

    Args:
        food_id: FatSecret food ID from search_fatsecret_foods results
    """
    return _tools.get_fatsecret_food(food_id=food_id)


# ===========================================================================
# Cache management tools
# ===========================================================================


@mcp.tool()
def get_cache_stats() -> dict:
    """Return cache health statistics.

    Shows total entries, DB size, breakdown by source and tool name,
    whether caching is enabled, and the configured TTL.
    """
    import os
    cache = get_cache()
    enabled = os.environ.get("CACHE_ENABLED", "true").lower() not in ("false", "0", "no")
    ttl = os.environ.get("CACHE_TTL_DAYS")
    if not enabled or cache is None:
        return {"cacheEnabled": False, "totalEntries": 0, "dbSizeKb": 0,
                "bySource": {}, "byTool": {}, "ttlDays": None}
    stats = cache.stats()
    return {**stats, "cacheEnabled": True, "ttlDays": int(ttl) if ttl else None}


@mcp.tool()
def list_cached_foods(
    source: str | None = None,
    query: str | None = None,
    limit: int = 50,
) -> dict:
    """Browse the food index — shows which foods are already cached.

    Args:
        source: Filter by data source (e.g. "usda_fdc")
        query: Case-insensitive substring filter on food description
        limit: Maximum number of results to return (default 50)
    """
    cache = get_cache()
    if cache is None:
        return {"foods": [], "total": 0, "cacheEnabled": False}
    foods = cache.list_foods(source=source, query=query, limit=limit)
    return {"foods": foods, "total": len(foods), "cacheEnabled": True}


@mcp.tool()
def clear_cache(
    source: str | None = None,
    tool_name: str | None = None,
) -> dict:
    """Clear cached responses, optionally filtered by source or tool name.

    Without arguments, clears the entire cache.

    Args:
        source: Only clear entries for this source (e.g. "usda_fdc")
        tool_name: Only clear entries for this tool (e.g. "search_foods")
    """
    cache = get_cache()
    if cache is None:
        return {"cleared": 0, "message": "Cache is disabled"}
    count = cache.clear(source=source, tool_name=tool_name)
    parts = []
    if source:
        parts.append(f"source={source}")
    if tool_name:
        parts.append(f"tool={tool_name}")
    scope = ", ".join(parts) if parts else "all entries"
    return {"cleared": count, "message": f"Cleared {count} entries ({scope})"}


# ===========================================================================
# Resources
# ===========================================================================


@mcp.resource("food://fdc/{fdc_id}")
def fdc_food_resource(fdc_id: str) -> str:
    """Full USDA FDC food item JSON (live API data)."""
    return json.dumps(_resources.get_fdc_food_resource(int(fdc_id)), indent=2)


@mcp.resource("food://nutrients/reference")
def nutrients_reference_resource() -> str:
    """Static list of all standard USDA nutrient numbers, names, and units."""
    return json.dumps(NUTRIENT_REFERENCE, indent=2)


@mcp.resource("food://sources/info")
def sources_info_resource() -> str:
    """Descriptions of all FDC dataset types and when to use each."""
    return json.dumps(SOURCES_INFO, indent=2)


@mcp.resource("food://server/metadata")
def server_metadata_resource() -> str:
    """Server version, data sources, capabilities, and API key status."""
    return json.dumps(_resources.get_server_metadata(), indent=2)


# ===========================================================================
# Prompts
# ===========================================================================


@mcp.prompt()
def analyze_food_nutrition(food_name: str, health_goal: str = "") -> list[dict]:
    """Analyze nutrition data for a food with citations from USDA FDC."""
    return _prompts.get_prompt_messages(
        "analyze_food_nutrition", {"food_name": food_name, "health_goal": health_goal}
    )


@mcp.prompt()
def compare_foods_for_goal(food_a: str, food_b: str, goal: str) -> list[dict]:
    """Compare two foods for a specific health or dietary goal."""
    return _prompts.get_prompt_messages(
        "compare_foods_for_goal", {"food_a": food_a, "food_b": food_b, "goal": goal}
    )


@mcp.prompt()
def dietary_advice(query: str, dietary_restrictions: str = "") -> list[dict]:
    """Evidence-based dietary advice anchored to specific USDA food data."""
    return _prompts.get_prompt_messages(
        "dietary_advice", {"query": query, "dietary_restrictions": dietary_restrictions}
    )


@mcp.prompt()
def meal_nutrition_summary(meal_description: str) -> list[dict]:
    """Break a meal into components and produce a combined nutrition summary."""
    return _prompts.get_prompt_messages(
        "meal_nutrition_summary", {"meal_description": meal_description}
    )


# ===========================================================================
# Entry point
# ===========================================================================


_DEFAULT_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "https://chat.openai.com",
    "https://chatgpt.com",
    "https://www.chatgpt.com",
]


def _build_http_app(extra_origins: list[str]):
    """Wrap FastMCP's ASGI app with CORS middleware and a health check."""
    import uvicorn  # noqa: F401 — ensure importable before we start
    from starlette.datastructures import MutableHeaders
    from starlette.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    origins = list(dict.fromkeys(_DEFAULT_ORIGINS + extra_origins))
    trusted_origin_set = set(origins)

    class OriginRewriteMiddleware:
        """Strip explicitly trusted browser origins before FastMCP validates them.

        FastMCP performs its own origin checks internally. For a reverse-proxied
        public deployment, outer CORS should still see the real browser origin,
        but the inner MCP app should not reject trusted browser requests just
        because they include an Origin header.
        """

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = MutableHeaders(scope=scope)
                origin = headers.get("origin")
                if origin and origin in trusted_origin_set:
                    del headers["origin"]
            await self.app(scope, receive, send)

    class HealthCheck(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method == "GET" and request.url.path == "/":
                return JSONResponse({
                    "name": "Food Facts MCP",
                    "version": "0.3.0",
                    "status": "ok",
                    "endpoint": "/mcp",
                })
            return await call_next(request)

    inner_app = mcp.streamable_http_app()
    inner_app = OriginRewriteMiddleware(inner_app)
    inner_app = HealthCheck(inner_app)
    app = CORSMiddleware(
        inner_app,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    return app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Food Facts MCP Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport", choices=["stdio", "streamable-http"], default="stdio"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--allow-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="Extra allowed CORS origin (repeatable, e.g. https://myapp.com)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn
        app = _build_http_app(args.allow_origin)
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
