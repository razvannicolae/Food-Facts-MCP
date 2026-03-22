"""Resource handlers for the Food Facts MCP server.

URI scheme:
  food://fdc/{fdcId}           — live USDA FDC food item JSON
  food://nutrients/reference   — standard USDA nutrient numbers & units
  food://datasets/info         — descriptions of FDC dataset types
  food://server/metadata       — server version, capabilities, key status
"""

from __future__ import annotations

import os

from .fdc_client import FDCClient

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

SOURCES_INFO: dict[str, dict] = {
    "USDA FoodData Central — Foundation": {
        "api": "USDA FoodData Central",
        "description": "Analytical data for high-priority commodity foods with full documentation.",
        "coverage": "Core raw/basic ingredients",
        "best_for": "Research requiring precise analytical data",
        "api_key_required": True,
        "url": "https://fdc.nal.usda.gov",
    },
    "USDA FoodData Central — SR Legacy": {
        "api": "USDA FoodData Central",
        "description": "Final release of USDA's Standard Reference (~8,600 foods). Broadest single dataset.",
        "coverage": "Wide variety of raw, processed, and prepared foods",
        "best_for": "General nutrition analysis",
        "api_key_required": True,
        "url": "https://fdc.nal.usda.gov",
    },
    "USDA FoodData Central — Branded": {
        "api": "USDA FoodData Central",
        "description": "Nutrient data for branded products submitted by food companies.",
        "coverage": "Commercial packaged foods",
        "best_for": "Specific branded product queries",
        "api_key_required": True,
        "url": "https://fdc.nal.usda.gov",
    },
    "USDA FoodData Central — Survey (FNDDS)": {
        "api": "USDA FoodData Central",
        "description": "Foods as consumed in NHANES dietary surveys.",
        "coverage": "Prepared/cooked forms as eaten",
        "best_for": "Population dietary studies",
        "api_key_required": True,
        "url": "https://fdc.nal.usda.gov",
    },
    "FatSecret": {
        "api": "FatSecret Platform API",
        "description": "Large commercial food database with 2.3M+ foods including restaurant chains and branded products.",
        "coverage": "Restaurant/fast food chains, branded packaged foods, generic foods",
        "best_for": "Fast food nutrition (McDonald's, Chick-fil-A, etc.) and branded products",
        "api_key_required": True,
        "url": "https://platform.fatsecret.com",
    },
}


def get_fdc_food_resource(fdc_id: int) -> dict:
    return FDCClient().get_food(fdc_id=fdc_id)


def get_nutrients_reference() -> list[dict]:
    return NUTRIENT_REFERENCE


def get_sources_info() -> dict:
    return SOURCES_INFO


def get_server_metadata() -> dict:
    api_key = os.environ.get("USDA_FDC_API_KEY", "")
    configured = bool(api_key and api_key != "DEMO_KEY")
    return {
        "name": "Food Facts MCP",
        "version": "0.3.0",
        "dataSources": {
            "usdaFDC": {
                "apiBaseUrl": "https://api.nal.usda.gov/fdc/v1",
                "rateLimit": {"registeredKey": "1 000 req/hr", "demoKey": "30 req/hr"},
                "apiKeyConfigured": configured,
                "apiKeyStatus": "configured" if configured else "using DEMO_KEY (limited)",
            },
        },
        "tools": 13,
        "resources": 4,
        "prompts": 4,
    }
