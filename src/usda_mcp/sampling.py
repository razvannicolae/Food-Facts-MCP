"""Sampling helpers — server-initiated LLM completion requests.

These functions build `sampling/createMessage` request payloads.
The caller (server.py) is responsible for sending them to the connected
MCP client when the client advertises sampling capability.
"""

from __future__ import annotations


def create_nutrition_summary_request(food_data: dict) -> dict:
    """Build a sampling request that asks the LLM for a plain-language nutrition summary.

    Triggered after `get_food_nutrients` returns data.
    """
    description = food_data.get("description", "unknown food")
    nutrients = food_data.get("nutrients") or food_data.get("foodNutrients", [])

    # Build a concise nutrient list (top 10 by position for brevity).
    lines: list[str] = []
    for n in nutrients[:10]:
        name = n.get("name") or n.get("nutrientName", "")
        amount = n.get("amount") or n.get("value", "")
        unit = n.get("unit") or n.get("unitName", "")
        if name and amount is not None:
            lines.append(f"  {name}: {amount} {unit}")

    nutrient_text = "\n".join(lines) if lines else "  (no nutrient data available)"

    return {
        "method": "sampling/createMessage",
        "params": {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            f"Write a 2–3 sentence plain-language nutrition summary for: "
                            f"{description}\n\n"
                            f"Key nutrients per 100 g:\n{nutrient_text}\n\n"
                            "Use specific numbers from the data. "
                            "Focus on what makes this food nutritionally notable. "
                            "Keep the tone accessible and factual."
                        ),
                    },
                }
            ],
            "maxTokens": 150,
            "temperature": 0.3,
            "systemPrompt": (
                "You are a precise nutrition communicator. "
                "Only use the data provided — do not add information not present in the numbers."
            ),
        },
    }


def create_citation_text_request(food_data: dict) -> dict:
    """Build a sampling request that asks the LLM to format APA and MLA citations.

    Triggered after any food lookup that returns FDC metadata.
    """
    fdc_id = food_data.get("fdcId")
    description = food_data.get("description", "Unknown food")
    data_type = food_data.get("dataType", "")
    pub_date = (
        food_data.get("publicationDate")
        or food_data.get("modifiedDate")
        or "n.d."
    )
    url = f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients"

    return {
        "method": "sampling/createMessage",
        "params": {
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Format proper APA and MLA citations for this USDA food data source:\n\n"
                            f"  Food: {description}\n"
                            f"  FDC ID: {fdc_id}\n"
                            f"  Dataset: {data_type}\n"
                            f"  Publication Date: {pub_date}\n"
                            f"  URL: {url}\n"
                            f"  Publisher: U.S. Department of Agriculture, "
                            f"Agricultural Research Service\n\n"
                            "Provide both APA (7th ed.) and MLA (9th ed.) formats."
                        ),
                    },
                }
            ],
            "maxTokens": 200,
            "temperature": 0.1,
        },
    }
