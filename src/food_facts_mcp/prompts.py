"""Reusable LLM prompt templates for Food Facts MCP."""

from __future__ import annotations

PROMPT_DEFINITIONS: list[dict] = [
    {
        "name": "analyze_food_nutrition",
        "description": "Fetch nutrition data for a food from USDA FDC and produce a structured analysis with citations.",
        "arguments": [
            {"name": "food_name", "description": "Name of the food to analyze", "required": True},
            {"name": "health_goal", "description": "Optional health goal (e.g., weight loss, muscle gain)", "required": False},
        ],
    },
    {
        "name": "compare_foods_for_goal",
        "description": "Compare two foods for a specific health or dietary goal using FDC data.",
        "arguments": [
            {"name": "food_a", "description": "First food to compare", "required": True},
            {"name": "food_b", "description": "Second food to compare", "required": True},
            {"name": "goal", "description": "Health/dietary goal (e.g., 'high protein', 'low sodium')", "required": True},
        ],
    },
    {
        "name": "dietary_advice",
        "description": "Evidence-based dietary advice anchored to specific USDA food data with citations.",
        "arguments": [
            {"name": "query", "description": "The dietary question or concern", "required": True},
            {"name": "dietary_restrictions", "description": "Optional dietary restrictions", "required": False},
        ],
    },
    {
        "name": "meal_nutrition_summary",
        "description": "Break a meal into components, fetch each from USDA FDC, and produce a combined nutrition summary.",
        "arguments": [
            {"name": "meal_description", "description": "Description of the meal", "required": True},
        ],
    },
]


def get_prompt_messages(name: str, arguments: dict) -> list[dict]:
    if name == "analyze_food_nutrition":
        food_name = arguments.get("food_name", "")
        health_goal = arguments.get("health_goal", "")
        goal_text = f" with a focus on **{health_goal}**" if health_goal else ""

        text = (
            f"Please analyze the nutrition profile of **{food_name}**{goal_text}.\n\n"
            "**Instructions:**\n"
            f"1. Use `search_foods` (USDA FDC) to find the best match.\n"
            "   Prefer Foundation or SR Legacy for whole/natural foods; use Branded for packaged items.\n"
            "2. Select the most relevant result and note its fdcId.\n"
            "3. Use `get_food_nutrients` to get the full nutrient table.\n"
            "4. Present a structured analysis:\n"
            "   - **Macronutrients**: protein, fat, carbohydrates, fiber, calories\n"
            "   - **Key micronutrients**: top vitamins and minerals\n"
        )
        if health_goal:
            text += f"   - **{health_goal} relevance**: which nutrients support or hinder this goal\n"
        text += (
            "5. Include the citation (source, fdcId, dataset, URL).\n\n"
            "Only use values returned by the tools — do not guess nutrient amounts."
        )
        return [{"role": "user", "content": {"type": "text", "text": text}}]

    elif name == "compare_foods_for_goal":
        food_a = arguments.get("food_a", "")
        food_b = arguments.get("food_b", "")
        goal = arguments.get("goal", "")

        text = (
            f"Compare **{food_a}** vs **{food_b}** for the goal: **{goal}**\n\n"
            "**Instructions:**\n"
            f"1. Search for '{food_a}' using `search_foods`.\n"
            f"2. Search for '{food_b}' using `search_foods`.\n"
            "3. Use `compare_foods` with the two fdcIds, or fetch nutrients individually.\n"
            f"4. Analyze which food better supports **{goal}**:\n"
            "   - Identify key nutrients relevant to this goal.\n"
            "   - Declare a winner with specific nutrient evidence (values and units).\n"
            "   - Note meaningful trade-offs.\n"
            "5. Include citations for both foods.\n\n"
            "Prefer Foundation or SR Legacy data for natural foods; use Branded for packaged items."
        )
        return [{"role": "user", "content": {"type": "text", "text": text}}]

    elif name == "dietary_advice":
        query = arguments.get("query", "")
        restrictions = arguments.get("dietary_restrictions", "")
        restriction_text = f"\n**Dietary restrictions**: {restrictions}" if restrictions else ""

        text = (
            f"Provide evidence-based dietary advice for: **{query}**{restriction_text}\n\n"
            "**Instructions:**\n"
            "1. Use `search_foods` to find 2–3 specific foods relevant to this query.\n"
            "   For whole/natural foods use data_type=['Foundation', 'SR Legacy'].\n"
            "   For packaged/branded products use data_type=['Branded'].\n"
            "2. Use `get_food_nutrients` to get actual nutrient data.\n"
            "3. Base all advice on specific data — not general nutritional knowledge.\n"
            "4. Structure: Background → Recommended Foods → Key Nutrients → Citations\n\n"
            "Do not make health claims beyond what the nutrient data supports."
        )
        return [{"role": "user", "content": {"type": "text", "text": text}}]

    elif name == "meal_nutrition_summary":
        meal = arguments.get("meal_description", "")

        text = (
            f"Create a nutrition summary for this meal: **{meal}**\n\n"
            "**Instructions:**\n"
            "1. Break the meal into individual food components.\n"
            "2. For each component, use `search_foods` + `get_food_nutrients` (USDA FDC).\n"
            "   Prefer Foundation or SR Legacy for whole ingredients; Branded for packaged items.\n"
            "3. Scale nutrients by estimated portion size.\n"
            "4. Present a **Combined Nutrition Summary**:\n"
            "   - Total calories, protein, fat, carbohydrates, fiber\n"
            "   - Notable micronutrients\n"
            "   - Per-component breakdown\n"
            "5. List all citations (source, fdcId, dataset, URL).\n\n"
            "If an exact match is unavailable, use the closest equivalent and note it."
        )
        return [{"role": "user", "content": {"type": "text", "text": text}}]

    else:
        raise ValueError(f"Unknown prompt: {name!r}")
