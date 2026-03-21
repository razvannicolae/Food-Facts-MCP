"""Reusable LLM prompt templates for USDA FDC nutrition analysis."""

from __future__ import annotations

PROMPT_DEFINITIONS: list[dict] = [
    {
        "name": "analyze_food_nutrition",
        "description": "Fetch USDA FDC data for a food and produce a structured nutrition analysis with citations.",
        "arguments": [
            {"name": "food_name", "description": "Name of the food to analyze", "required": True},
            {
                "name": "health_goal",
                "description": "Optional health goal (e.g., weight loss, muscle gain, heart health)",
                "required": False,
            },
        ],
    },
    {
        "name": "compare_foods_for_goal",
        "description": "Compare two foods side-by-side for a specific health or dietary goal using FDC data.",
        "arguments": [
            {"name": "food_a", "description": "First food to compare", "required": True},
            {"name": "food_b", "description": "Second food to compare", "required": True},
            {
                "name": "goal",
                "description": "Health/dietary goal (e.g., 'high protein', 'low sodium', 'weight loss')",
                "required": True,
            },
        ],
    },
    {
        "name": "dietary_advice",
        "description": "Evidence-based dietary advice anchored to specific USDA FDC food items with citations.",
        "arguments": [
            {"name": "query", "description": "The dietary question or concern", "required": True},
            {
                "name": "dietary_restrictions",
                "description": "Optional dietary restrictions (e.g., vegan, gluten-free, low-sodium)",
                "required": False,
            },
        ],
    },
    {
        "name": "meal_nutrition_summary",
        "description": "Break a meal into components, fetch each from FDC, and produce a combined nutrition summary.",
        "arguments": [
            {
                "name": "meal_description",
                "description": "Description of the meal (e.g., 'grilled chicken breast with brown rice and broccoli')",
                "required": True,
            },
        ],
    },
]


def get_prompt_messages(name: str, arguments: dict) -> list[dict]:
    """Return the messages array for a named prompt with the given arguments."""

    if name == "analyze_food_nutrition":
        food_name = arguments.get("food_name", "")
        health_goal = arguments.get("health_goal", "")
        goal_text = f" with a focus on **{health_goal}**" if health_goal else ""

        text = (
            f"Please analyze the nutrition profile of **{food_name}**{goal_text}.\n\n"
            "**Instructions:**\n"
            f"1. Use `search_foods` to find '{food_name}' in USDA FoodData Central. "
            "Prefer **Foundation** or **SR Legacy** data types for accuracy.\n"
            "2. Select the most relevant result and note its `fdcId`.\n"
            "3. Use `get_food_nutrients` with that `fdcId` to retrieve the full nutrient table.\n"
            "4. Present a structured analysis:\n"
            "   - **Macronutrients**: protein, fat, carbohydrates, fiber, calories\n"
            "   - **Key micronutrients**: top 5–8 vitamins and minerals\n"
        )
        if health_goal:
            text += f"   - **{health_goal} relevance**: which nutrients support or hinder this goal\n"
        text += (
            "5. Include the USDA FDC citation:\n"
            "   - `fdcId`, description, dataset type, publication date\n"
            "   - URL: `https://fdc.nal.usda.gov/food-details/{fdcId}/nutrients`\n\n"
            "Do not guess nutrient values — only use data returned by the tools."
        )

        return [{"role": "user", "content": {"type": "text", "text": text}}]

    elif name == "compare_foods_for_goal":
        food_a = arguments.get("food_a", "")
        food_b = arguments.get("food_b", "")
        goal = arguments.get("goal", "")

        text = (
            f"Compare **{food_a}** vs **{food_b}** for the goal: **{goal}**\n\n"
            "**Instructions:**\n"
            f"1. Use `search_foods` to find '{food_a}', note the `fdcId`.\n"
            f"2. Use `search_foods` to find '{food_b}', note the `fdcId`.\n"
            "3. Use `compare_foods` with both `fdcId` values for a side-by-side comparison.\n"
            f"4. Analyze which food better supports **{goal}**:\n"
            "   - Identify the key nutrients relevant to this goal.\n"
            "   - Declare a winner with specific nutrient evidence (values and units).\n"
            "   - Note any meaningful trade-offs.\n"
            "5. Include USDA FDC citations for both foods.\n\n"
            "Prefer Foundation or SR Legacy data for accuracy. "
            "If only Branded data is available, note that."
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
            "2. Use `get_food_nutrients` for each food to retrieve actual USDA data.\n"
            "3. Base all advice on specific FDC data — not general nutritional knowledge.\n"
            "4. Structure your response as:\n"
            "   - **Background**: brief evidence context\n"
            "   - **Recommended Foods**: 2–3 specific USDA-verified foods\n"
            "   - **Key Nutrients**: which nutrients from the data support the recommendation\n"
            "   - **Citations**: fdcId, description, dataset, publication date, URL for each food\n\n"
            "Do not make health claims beyond what the nutrient data supports. "
            "Recommend consulting a healthcare professional for medical dietary needs."
        )

        return [{"role": "user", "content": {"type": "text", "text": text}}]

    elif name == "meal_nutrition_summary":
        meal = arguments.get("meal_description", "")

        text = (
            f"Create a nutrition summary for this meal: **{meal}**\n\n"
            "**Instructions:**\n"
            "1. Break the meal into individual food components (ingredients/dishes).\n"
            "2. For each component:\n"
            "   a. Use `search_foods` to find it in USDA FDC (prefer Foundation or SR Legacy).\n"
            "   b. Use `get_food_nutrients` to retrieve per-100g nutrient data.\n"
            "3. Scale nutrients by estimated portion size.\n"
            "4. Aggregate and present a **Combined Nutrition Summary**:\n"
            "   - Total calories\n"
            "   - Total protein, fat, carbohydrates, fiber\n"
            "   - Notable micronutrients (highlight any that are especially high or low)\n"
            "   - Per-component breakdown table\n"
            "5. List all **USDA FDC citations** (fdcId, description, dataset, URL).\n\n"
            "If an exact match is unavailable, use the closest equivalent and note the substitution."
        )

        return [{"role": "user", "content": {"type": "text", "text": text}}]

    else:
        raise ValueError(f"Unknown prompt: {name!r}")
