"""Resource handlers for the USDA FDC MCP Server.

URI scheme:
  usda://food/{fdcId}          — live food item JSON from FDC
  usda://nutrients/reference   — static list of standard nutrient numbers
  usda://datasets/info         — descriptions of each FDC data type
  usda://server/metadata       — server version, rate limits, key status
"""

from __future__ import annotations

import os

from .fdc_client import FDCClient

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

NUTRIENT_REFERENCE: list[dict] = [
    {"number": "203", "name": "Protein", "unit": "g"},
    {"number": "204", "name": "Total lipid (fat)", "unit": "g"},
    {"number": "205", "name": "Carbohydrate, by difference", "unit": "g"},
    {"number": "208", "name": "Energy", "unit": "kcal"},
    {"number": "269", "name": "Sugars, total including NLEA", "unit": "g"},
    {"number": "291", "name": "Fiber, total dietary", "unit": "g"},
    {"number": "301", "name": "Calcium, Ca", "unit": "mg"},
    {"number": "303", "name": "Iron, Fe", "unit": "mg"},
    {"number": "304", "name": "Magnesium, Mg", "unit": "mg"},
    {"number": "305", "name": "Phosphorus, P", "unit": "mg"},
    {"number": "306", "name": "Potassium, K", "unit": "mg"},
    {"number": "307", "name": "Sodium, Na", "unit": "mg"},
    {"number": "309", "name": "Zinc, Zn", "unit": "mg"},
    {"number": "312", "name": "Copper, Cu", "unit": "mg"},
    {"number": "317", "name": "Selenium, Se", "unit": "µg"},
    {"number": "318", "name": "Vitamin A, IU", "unit": "IU"},
    {"number": "323", "name": "Vitamin E (alpha-tocopherol)", "unit": "mg"},
    {"number": "324", "name": "Vitamin D (D2 + D3)", "unit": "IU"},
    {"number": "401", "name": "Vitamin C, total ascorbic acid", "unit": "mg"},
    {"number": "404", "name": "Thiamin", "unit": "mg"},
    {"number": "405", "name": "Riboflavin", "unit": "mg"},
    {"number": "406", "name": "Niacin", "unit": "mg"},
    {"number": "410", "name": "Pantothenic acid", "unit": "mg"},
    {"number": "415", "name": "Vitamin B-6", "unit": "mg"},
    {"number": "417", "name": "Folate, total", "unit": "µg"},
    {"number": "418", "name": "Vitamin B-12", "unit": "µg"},
    {"number": "421", "name": "Choline, total", "unit": "mg"},
    {"number": "430", "name": "Vitamin K (phylloquinone)", "unit": "µg"},
    {"number": "601", "name": "Cholesterol", "unit": "mg"},
    {"number": "605", "name": "Fatty acids, total trans", "unit": "g"},
    {"number": "606", "name": "Fatty acids, total saturated", "unit": "g"},
]

DATASET_INFO: dict[str, dict] = {
    "Foundation": {
        "name": "Foundation Foods",
        "description": (
            "Analytical data for a limited number of high-priority foods. "
            "Provides extensive analytical values with supporting metadata including "
            "sampling protocols and analytical methods."
        ),
        "coverage": "Core commodity foods: raw/basic ingredients",
        "best_for": "Research requiring precise analytical data with full documentation",
        "update_frequency": "Periodic updates as new analyses are completed",
        "sample_foods": [
            "Beef, ground, 85% lean meat / 15% fat, raw",
            "Broccoli, raw",
            "Almonds, dry roasted, without salt added",
        ],
    },
    "SR Legacy": {
        "name": "Standard Reference Legacy",
        "description": (
            "The final release of USDA's Standard Reference database (~8,600 foods). "
            "The most comprehensive single-dataset option for general nutrition analysis."
        ),
        "coverage": "Wide variety of raw, processed, and prepared foods",
        "best_for": "General nutrition analysis; broadest food coverage",
        "update_frequency": "Legacy — no longer updated after SR28",
        "sample_foods": [
            "Chicken, broilers or fryers, breast, meat only, cooked, roasted",
        ],
    },
    "Branded": {
        "name": "Branded Foods",
        "description": (
            "Nutrient data for branded food products provided by food companies "
            "and aggregated from public label databases."
        ),
        "coverage": "Commercial branded products — packaged foods, fast food",
        "best_for": "Specific product queries, nutrition label verification",
        "update_frequency": "Continuously updated as companies submit data",
        "sample_foods": ["Cheerios (General Mills)", "Campbell's Tomato Soup"],
    },
    "Survey (FNDDS)": {
        "name": "Survey (FNDDS)",
        "description": (
            "Food and Nutrient Database for Dietary Studies. Foods and beverages "
            "reported in NHANES dietary surveys, as typically consumed."
        ),
        "coverage": "Foods in prepared/cooked forms as reported by survey respondents",
        "best_for": "Population dietary studies and epidemiological research",
        "update_frequency": "Updated to align with NHANES survey cycles",
        "sample_foods": ["Oatmeal, cooked, fat added in cooking"],
    },
}

# ---------------------------------------------------------------------------
# Resource handler functions
# ---------------------------------------------------------------------------


def get_food_resource(fdc_id: int) -> dict:
    """Live food item JSON from FDC (usda://food/{fdcId})."""
    client = FDCClient()
    return client.get_food(fdc_id=fdc_id)


def get_nutrients_reference() -> list[dict]:
    """Static nutrient reference list (usda://nutrients/reference)."""
    return NUTRIENT_REFERENCE


def get_datasets_info() -> dict[str, dict]:
    """Dataset descriptions (usda://datasets/info)."""
    return DATASET_INFO


def get_server_metadata() -> dict:
    """Server metadata and API key status (usda://server/metadata)."""
    api_key = os.environ.get("USDA_FDC_API_KEY", "")
    configured = bool(api_key and api_key != "DEMO_KEY")
    return {
        "name": "USDA FoodData Central MCP Server",
        "version": "0.1.0",
        "apiBaseUrl": "https://api.nal.usda.gov/fdc/v1",
        "rateLimit": {
            "registeredKey": "1 000 req/hr",
            "demoKey": "30 req/hr per IP",
            "notes": "Register a free key at https://api.data.gov/signup/",
        },
        "apiKeyConfigured": configured,
        "apiKeyStatus": "configured" if configured else "using DEMO_KEY (limited rate)",
        "supportedDataTypes": list(DATASET_INFO.keys()),
        "mcpCapabilities": {
            "tools": 8,
            "resources": 4,
            "prompts": 4,
            "sampling": 2,
        },
    }
