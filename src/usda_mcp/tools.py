"""All 8 tool implementations for the USDA FDC MCP Server."""

from __future__ import annotations

from typing import Optional

from .citations import citation_from_food, format_apa_citation, format_mla_citation
from .fdc_client import FDCClient

# Module-level singleton so the API key is read once.
_client: Optional[FDCClient] = None


def _get_client() -> FDCClient:
    global _client
    if _client is None:
        _client = FDCClient()
    return _client


# ---------------------------------------------------------------------------
# Tool 1 — search_foods
# ---------------------------------------------------------------------------

def search_foods(
    query: str,
    data_type: Optional[list[str]] = None,
    brand_owner: Optional[str] = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    """Search USDA FoodData Central by keyword."""
    result = _get_client().search_foods(
        query=query,
        data_type=data_type,
        brand_owner=brand_owner,
        page_size=page_size,
        page_number=page_number,
    )
    foods = result.get("foods", [])
    return {
        "totalHits": result.get("totalHits", 0),
        "currentPage": result.get("currentPage", 1),
        "totalPages": result.get("totalPages", 1),
        # Omit per-item citation here to keep response compact — call
        # get_food_citation(fdcId) for full citation on a specific item.
        "foods": [
            {
                "fdcId": f.get("fdcId"),
                "description": f.get("description"),
                "dataType": f.get("dataType"),
                "brandOwner": f.get("brandOwner"),
                "publishedDate": f.get("publishedDate"),
            }
            for f in foods
        ],
    }


# ---------------------------------------------------------------------------
# Tool 2 — get_food
# ---------------------------------------------------------------------------

def get_food(
    fdc_id: int,
    nutrients: Optional[list[int]] = None,
    format: Optional[str] = None,
) -> dict:
    """Get full details for a single food item by FDC ID."""
    food = _get_client().get_food(fdc_id=fdc_id, nutrients=nutrients, format=format)

    # Flatten foodNutrients to name/amount/unit only, and drop null amounts.
    flat_nutrients = []
    for n in food.get("foodNutrients", []):
        amount = n.get("amount")
        if amount is None:
            continue
        info = n.get("nutrient", {})
        flat_nutrients.append({
            "name": info.get("name") or n.get("name") or n.get("nutrientName", ""),
            "amount": amount,
            "unit": info.get("unitName") or n.get("unitName", ""),
        })

    return {
        "fdcId": food.get("fdcId"),
        "description": food.get("description"),
        "dataType": food.get("dataType"),
        "publicationDate": food.get("publicationDate"),
        "brandOwner": food.get("brandOwner"),
        "ingredients": food.get("ingredients"),
        "servingSize": food.get("servingSize"),
        "servingSizeUnit": food.get("servingSizeUnit"),
        "foodNutrients": flat_nutrients,
        "foodCategory": food.get("foodCategory", {}).get("description") if isinstance(food.get("foodCategory"), dict) else food.get("foodCategory"),
        "citation": citation_from_food(food),
    }


# ---------------------------------------------------------------------------
# Tool 3 — get_multiple_foods
# ---------------------------------------------------------------------------

def get_multiple_foods(
    fdc_ids: list[int],
    nutrients: Optional[list[int]] = None,
) -> list[dict]:
    """Get details for up to 20 foods by FDC ID in one request."""
    foods = _get_client().get_multiple_foods(fdc_ids=fdc_ids, nutrients=nutrients)
    return [
        {
            "fdcId": f.get("fdcId"),
            "description": f.get("description"),
            "dataType": f.get("dataType"),
            "publicationDate": f.get("publicationDate"),
            "brandOwner": f.get("brandOwner"),
            "foodNutrients": f.get("foodNutrients", []),
            "citation": citation_from_food(f),
        }
        for f in (foods if isinstance(foods, list) else [])
    ]


# ---------------------------------------------------------------------------
# Tool 4 — get_food_nutrients
# ---------------------------------------------------------------------------

def get_food_nutrients(fdc_id: int) -> dict:
    """Fetch a food and return a human-readable nutrient table with citation."""
    food = _get_client().get_food(fdc_id=fdc_id)

    rows = []
    for n in food.get("foodNutrients", []):
        amount = n.get("amount")
        if amount is None:
            continue  # skip nutrients with no measured value
        nutrient_info = n.get("nutrient", {})
        name = nutrient_info.get("name") or n.get("name") or n.get("nutrientName", "Unknown")
        number = nutrient_info.get("number") or n.get("nutrientNumber")
        unit = nutrient_info.get("unitName") or n.get("unitName", "")
        rows.append(
            {
                "name": name,
                "number": number,
                "amount": amount,
                "unit": unit,
                "percentDailyValue": n.get("percentDailyValue"),
            }
        )

    # Sort by nutrient number for a consistent, readable order.
    def _sort_key(r: dict) -> int:
        try:
            return int(r["number"]) if r["number"] is not None else 9999
        except (TypeError, ValueError):
            return 9999

    rows.sort(key=_sort_key)

    return {
        "fdcId": food.get("fdcId"),
        "description": food.get("description"),
        "dataType": food.get("dataType"),
        "servingSize": food.get("servingSize"),
        "servingSizeUnit": food.get("servingSizeUnit"),
        "nutrients": rows,
        "citation": citation_from_food(food),
    }


# ---------------------------------------------------------------------------
# Tool 5 — compare_foods
# ---------------------------------------------------------------------------

def compare_foods(fdc_id_a: int, fdc_id_b: int) -> dict:
    """Side-by-side nutrient comparison of two FDC foods."""
    food_a = _get_client().get_food(fdc_id=fdc_id_a)
    food_b = _get_client().get_food(fdc_id=fdc_id_b)

    def _nutrient_map(food: dict) -> dict[str, dict]:
        result: dict[str, dict] = {}
        for n in food.get("foodNutrients", []):
            info = n.get("nutrient", {})
            name = info.get("name") or n.get("name") or n.get("nutrientName", "Unknown")
            result[name] = {
                "amount": n.get("amount"),
                "unit": info.get("unitName") or n.get("unitName", ""),
            }
        return result

    map_a = _nutrient_map(food_a)
    map_b = _nutrient_map(food_b)
    all_nutrients = sorted(set(list(map_a.keys()) + list(map_b.keys())))

    comparison = []
    for nutrient_name in all_nutrients:
        a_data = map_a.get(nutrient_name, {})
        b_data = map_b.get(nutrient_name, {})
        a_amount = a_data.get("amount")
        b_amount = b_data.get("amount")

        # Skip rows where neither food has a measured value.
        if a_amount is None and b_amount is None:
            continue

        unit = a_data.get("unit") or b_data.get("unit", "")
        difference = None
        higher = None
        if a_amount is not None and b_amount is not None:
            try:
                diff = round(float(a_amount) - float(b_amount), 4)
                difference = diff
                higher = food_a.get("description") if diff > 0 else food_b.get("description")
            except (TypeError, ValueError):
                pass

        comparison.append(
            {
                "nutrient": nutrient_name,
                "unit": unit,
                "foodA_amount": a_amount,
                "foodB_amount": b_amount,
                "difference_a_minus_b": difference,
                "higher": higher,
            }
        )

    return {
        "foodA": {
            "fdcId": food_a.get("fdcId"),
            "description": food_a.get("description"),
            "dataType": food_a.get("dataType"),
            "citation": citation_from_food(food_a),
        },
        "foodB": {
            "fdcId": food_b.get("fdcId"),
            "description": food_b.get("description"),
            "dataType": food_b.get("dataType"),
            "citation": citation_from_food(food_b),
        },
        "comparison": comparison,
    }


# ---------------------------------------------------------------------------
# Tool 6 — list_foods
# ---------------------------------------------------------------------------

def list_foods(
    data_type: Optional[list[str]] = None,
    page_size: int = 50,
    page_number: int = 1,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
) -> dict:
    """Browse all foods with pagination and optional filtering."""
    foods = _get_client().list_foods(
        data_type=data_type,
        page_size=page_size,
        page_number=page_number,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {
        "pageNumber": page_number,
        "pageSize": page_size,
        "foods": [
            {
                "fdcId": f.get("fdcId"),
                "description": f.get("description"),
                "dataType": f.get("dataType"),
                "publicationDate": f.get("publicationDate"),
                "brandOwner": f.get("brandOwner"),
            }
            for f in (foods if isinstance(foods, list) else [])
        ],
    }


# ---------------------------------------------------------------------------
# Tool 7 — list_foods_by_nutrient
# ---------------------------------------------------------------------------

# Maps nutrient names to food-category search terms.
# This avoids searching for the nutrient name itself, which returns fortified
# products (e.g. "vitamin C" matches "Orange drink with added vitamin C powder").
# Instead we search for the natural foods that are known sources of each nutrient.
_NUTRIENT_TO_FOOD_QUERY: dict[str, str] = {
    "vitamin c": "citrus orange strawberry kiwi pepper broccoli",
    "ascorbic acid": "citrus orange strawberry kiwi pepper broccoli",
    "iron": "beef liver spinach lentil oyster",
    "iron, fe": "beef liver spinach lentil oyster",
    "protein": "chicken beef fish egg",
    "calcium": "milk cheese yogurt sardine",
    "calcium, ca": "milk cheese yogurt sardine",
    "potassium": "banana potato avocado bean",
    "potassium, k": "banana potato avocado bean",
    "sodium": "salt cheese processed",
    "sodium, na": "salt cheese processed",
    "vitamin d": "salmon tuna mackerel egg",
    "vitamin d (d2 + d3)": "salmon tuna mackerel egg",
    "vitamin a": "liver carrot sweet potato spinach kale",
    "vitamin a, iu": "liver carrot sweet potato spinach kale",
    "vitamin e": "almond sunflower seed avocado olive",
    "vitamin e (alpha-tocopherol)": "almond sunflower seed avocado olive",
    "vitamin k": "kale spinach broccoli cabbage",
    "vitamin k (phylloquinone)": "kale spinach broccoli cabbage",
    "folate": "lentil bean spinach asparagus",
    "folate, total": "lentil bean spinach asparagus",
    "folic acid": "lentil bean spinach asparagus",
    "vitamin b-12": "beef liver fish egg dairy",
    "vitamin b12": "beef liver fish egg dairy",
    "vitamin b-6": "chicken fish banana potato",
    "thiamin": "pork sunflower seed legume",
    "riboflavin": "beef liver dairy egg almond",
    "niacin": "chicken tuna beef peanut",
    "zinc": "oyster beef pumpkin seed",
    "zinc, zn": "oyster beef pumpkin seed",
    "magnesium": "almond spinach pumpkin seed cashew",
    "magnesium, mg": "almond spinach pumpkin seed cashew",
    "fiber": "bean lentil oat apple broccoli",
    "fiber, total dietary": "bean lentil oat apple broccoli",
    "dietary fiber": "bean lentil oat apple broccoli",
    "omega-3": "salmon sardine mackerel flaxseed",
    "cholesterol": "egg shrimp beef liver",
    "saturated fat": "butter cheese beef coconut",
    "fatty acids, total saturated": "butter cheese beef coconut",
    "choline": "egg beef liver chicken",
    "choline, total": "egg beef liver chicken",
    "selenium": "brazil nut tuna egg beef",
    "selenium, se": "brazil nut tuna egg beef",
}


def list_foods_by_nutrient(
    nutrient_name: str,
    top_n: int = 10,
    data_type: Optional[list[str]] = None,
) -> dict:
    """Return top N foods ranked highest for a given nutrient."""
    whole_foods_mode = data_type is not None and set(data_type).issubset(
        {"Foundation", "SR Legacy"}
    )

    if whole_foods_mode:
        # Use food-category terms instead of the nutrient name so we don't
        # accidentally match fortified products named after the nutrient.
        search_query = _NUTRIENT_TO_FOOD_QUERY.get(
            nutrient_name.lower().strip(), nutrient_name
        )
    else:
        search_query = nutrient_name

    result = _get_client().search_foods(
        query=search_query,
        data_type=data_type,
        page_size=50,
    )
    foods = result.get("foods", [])

    scored: list[dict] = []
    for f in foods:
        food_nutrients = f.get("foodNutrients", [])
        amount = None
        matched_nutrient = nutrient_name
        for n in food_nutrients:
            n_name = n.get("nutrientName", "")
            if nutrient_name.lower() in n_name.lower():
                amount = n.get("value")
                matched_nutrient = n_name
                break
        if amount is not None:
            scored.append(
                {
                    "fdcId": f.get("fdcId"),
                    "description": f.get("description"),
                    "dataType": f.get("dataType"),
                    "nutrientName": matched_nutrient,
                    "nutrientAmount": amount,
                    "citation": citation_from_food(f),
                }
            )

    scored.sort(key=lambda x: float(x["nutrientAmount"] or 0), reverse=True)

    return {
        "nutrient": nutrient_name,
        "searchQuery": search_query,
        "dataTypes": data_type,
        "topFoods": scored[:top_n],
        "totalSearched": len(foods),
    }


# ---------------------------------------------------------------------------
# Tool 8 — get_food_citation
# ---------------------------------------------------------------------------

def get_food_citation(fdc_id: int) -> dict:
    """Return citation-ready metadata for a food item."""
    food = _get_client().get_food(fdc_id=fdc_id, format="abridged")
    return {
        "fdcId": food.get("fdcId"),
        "description": food.get("description"),
        "dataType": food.get("dataType"),
        "publicationDate": food.get("publicationDate"),
        "brandOwner": food.get("brandOwner"),
        "ndbNumber": food.get("ndbNumber"),
        "url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
        "citation": citation_from_food(food),
        "apa": format_apa_citation(food),
        "mla": format_mla_citation(food),
    }
