"""All tool implementations — USDA FoodData Central (8 tools) + FatSecret (2 tools)."""

from __future__ import annotations

from typing import Optional

from .cache import FoodCache, get_cache
from .citations import (
    citation_from_food,
    format_apa_citation,
    format_mla_citation,
)
from .fdc_client import FDCClient
from .fatsecret_client import FatSecretClient

_fdc: Optional[FDCClient] = None
_fs: Optional[FatSecretClient] = None

# Known restaurant/brand names whose foods appear in USDA as "Food, Brand"
_KNOWN_BRANDS = frozenset({
    "mcdonald's", "mcdonalds", "chick-fil-a", "chick fil a", "chickfila",
    "popeyes", "popeye's", "subway", "burger king", "taco bell",
    "wendy's", "wendys", "kfc", "chipotle", "dominos", "domino's",
    "pizza hut", "starbucks", "dunkin", "panera", "five guys",
    "shake shack", "sonic", "dairy queen", "arby's", "arbys",
    "panda express", "olive garden", "applebees", "applebee's",
    "ihop", "dennys", "denny's", "red lobster", "hardees", "hardee's",
    "carl's jr", "carls jr", "jack in the box", "whataburger",
    "raising cane's", "raising canes", "zaxby's", "zaxbys",
    "wingstop", "buffalo wild wings", "bdubs", "checkers",
    "del taco", "in-n-out", "little caesars",
})


def _rewrite_brand_first_query(query: str) -> str:
    """Rewrite 'Brand Food' to 'Food, Brand' to match USDA naming convention.

    USDA stores restaurant items as e.g. 'Coleslaw, Popeyes' so a query like
    'Popeyes coleslaw' won't match well without this rewrite.
    """
    words = query.strip().split()
    if len(words) < 2:
        return query

    # Check single-word brand (e.g. "Popeyes coleslaw")
    if words[0].lower() in _KNOWN_BRANDS:
        brand = words[0]
        food = " ".join(words[1:])
        return f"{food}, {brand}"

    # Check two-word brand (e.g. "Burger King fries")
    if len(words) >= 3 and " ".join(words[:2]).lower() in _KNOWN_BRANDS:
        brand = " ".join(words[:2])
        food = " ".join(words[2:])
        return f"{food}, {brand}"

    return query


def _query_variants(query: str) -> list[str]:
    """Return query variants to handle USDA 'Food, qualifier' naming convention.

    USDA stores foods as e.g. 'Salmon, raw', 'Chicken, fried', 'Coleslaw, Popeyes'.
    Users query in natural order: 'raw salmon', 'fried chicken', 'popeyes coleslaw'.
    If the brand rewrite already reordered the query we use that alone; otherwise
    we also try moving the first word to the end (covers 2-3 word queries only).
    """
    primary = _rewrite_brand_first_query(query)
    variants = [primary]

    # Only add generic reversal when brand rewrite didn't already change the order
    if primary.lower() == query.lower():
        words = query.strip().split()
        if 2 <= len(words) <= 3:
            reversed_variant = " ".join(words[1:]) + ", " + words[0]
            if reversed_variant.lower() != primary.lower():
                variants.append(reversed_variant)

    return variants


# Terms that indicate a processed/supplement form — penalised when absent from query
_PROCESSING_TERMS = frozenset({
    "oil", "extract", "supplement", "softgel", "capsule",
    "powder", "concentrate", "tablet", "tincture", "gel",
})


# USDA dataset preference scores.
# Restaurant meals live in SR Legacy / Survey (FNDDS), not Branded.
# Branded covers packaged goods with nutrition labels (chips, protein bars, etc.).
_DATASET_BASE_SCORE: dict[str, int] = {
    "Foundation": 8,
    "SR Legacy": 6,
    "Survey (FNDDS)": 4,
    "Branded": 0,
}
# Extra boost given to SR Legacy for known restaurant brand queries.
_RESTAURANT_SR_LEGACY_BOOST = 20


def _relevance_score(description: str, query: str, data_type: str = "") -> int:
    """Score how well a food description matches the query intent.

    Higher is better. Boosts exact/prefix matches; penalises processing terms
    that appear in the description but not in the query (e.g. returns 'salmon,
    raw' above 'salmon fish oil' for the query 'salmon').
    Also boosts SR Legacy over Branded for restaurant brand queries, since USDA
    stores restaurant meal items in SR Legacy, not in the Branded dataset.
    """
    desc = description.lower()
    q = query.lower().strip()
    q_words = set(q.split())

    score = 0
    # Exact match
    if desc == q:
        score += 100
    # Description starts with the query
    elif desc.startswith(q):
        score += 80
    # First comma-segment equals query (e.g. "Salmon, raw" → "salmon")
    elif desc.split(",")[0].strip() == q:
        score += 70
    # Query appears within the first 50 chars
    elif q in desc[:50]:
        score += 40

    # Penalise each processing term present in description but absent from query
    for term in _PROCESSING_TERMS:
        if term in desc and term not in q_words:
            score -= 30

    # Dataset preference
    if data_type:
        score += _DATASET_BASE_SCORE.get(data_type, 0)
        # Extra boost: restaurant brand queries → strongly prefer SR Legacy
        is_restaurant_query = any(q.startswith(b) or b in q for b in _KNOWN_BRANDS)
        if is_restaurant_query and data_type == "SR Legacy":
            score += _RESTAURANT_SR_LEGACY_BOOST

    return score


def _get_fdc() -> FDCClient:
    global _fdc
    if _fdc is None:
        _fdc = FDCClient()
    return _fdc


def _get_fs() -> FatSecretClient:
    global _fs
    if _fs is None:
        _fs = FatSecretClient()
    return _fs


# ===========================================================================
# USDA FoodData Central tools (8)
# ===========================================================================

# ---------------------------------------------------------------------------
# Tool 1 — search_foods
# ---------------------------------------------------------------------------

_RELEVANCE_FALLBACK_THRESHOLD = 40  # below this score, try the next query variant


def _fetch_search_variant(
    variant: str,
    data_type: Optional[list[str]],
    brand_owner: Optional[str],
    page_size: int,
    page_number: int,
    cache,
) -> tuple[list[dict], int]:
    """Fetch (or cache-hit) one query variant. Returns (food list, totalHits)."""
    key = FoodCache.make_key("search_foods", query=variant,
                             data_type=sorted(data_type) if data_type else None,
                             brand_owner=brand_owner, page_size=page_size,
                             page_number=page_number)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit.get("foods", []), hit.get("totalHits", 0)

    result = _get_fdc().search_foods(
        query=variant,
        data_type=data_type,
        brand_owner=brand_owner,
        page_size=page_size,
        page_number=page_number,
    )
    foods = [
        {
            "fdcId": f.get("fdcId"),
            "description": f.get("description"),
            "dataType": f.get("dataType"),
            "brandOwner": f.get("brandOwner"),
            "publishedDate": f.get("publishedDate"),
        }
        for f in result.get("foods", [])
    ]
    if cache:
        cache.set("usda_fdc", "search_foods", key, {
            "source": "USDA FoodData Central",
            "totalHits": result.get("totalHits", 0),
            "currentPage": result.get("currentPage", 1),
            "totalPages": result.get("totalPages", 1),
            "foods": foods,
        })
    return foods, result.get("totalHits", 0)


def search_foods(
    query: str,
    data_type: Optional[list[str]] = None,
    brand_owner: Optional[str] = None,
    page_size: int = 25,
    page_number: int = 1,
) -> dict:
    variants = _query_variants(query)
    cache = get_cache()

    seen_ids: dict[int, dict] = {}
    best_total_hits = 0

    for i, variant in enumerate(variants):
        foods, total_hits = _fetch_search_variant(
            variant, data_type, brand_owner, page_size, page_number, cache
        )
        for f in foods:
            fdc_id = f.get("fdcId")
            if fdc_id and fdc_id not in seen_ids:
                seen_ids[fdc_id] = f
        best_total_hits = max(best_total_hits, total_hits)

        # After the first variant, skip fallback if top result is already relevant
        if i == 0 and len(variants) > 1:
            top_score = max(
                (_relevance_score(f.get("description", ""), query, f.get("dataType", ""))
                 for f in seen_ids.values()),
                default=0,
            )
            if top_score >= _RELEVANCE_FALLBACK_THRESHOLD:
                break

    merged = list(seen_ids.values())
    merged.sort(
        key=lambda f: _relevance_score(f.get("description", ""), query, f.get("dataType", "")),
        reverse=True,
    )

    return {
        "source": "USDA FoodData Central",
        "totalHits": best_total_hits,
        "currentPage": page_number,
        "totalPages": 1,
        "foods": merged,
    }


# ---------------------------------------------------------------------------
# Tool 2 — get_food
# ---------------------------------------------------------------------------

def get_food(
    fdc_id: int,
    nutrients: Optional[list[int]] = None,
    format: Optional[str] = None,
) -> dict:
    cache = get_cache()
    key = FoodCache.make_key("get_food", fdc_id=fdc_id,
                             nutrients=sorted(nutrients) if nutrients else None,
                             format=format)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    food = _get_fdc().get_food(fdc_id=fdc_id, nutrients=nutrients, format=format)

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

    response = {
        "source": "USDA FoodData Central",
        "fdcId": food.get("fdcId"),
        "description": food.get("description"),
        "dataType": food.get("dataType"),
        "publicationDate": food.get("publicationDate"),
        "brandOwner": food.get("brandOwner"),
        "ingredients": food.get("ingredients"),
        "servingSize": food.get("servingSize"),
        "servingSizeUnit": food.get("servingSizeUnit"),
        "foodNutrients": flat_nutrients,
        "foodCategory": (
            food.get("foodCategory", {}).get("description")
            if isinstance(food.get("foodCategory"), dict)
            else food.get("foodCategory")
        ),
        "citation": citation_from_food(food),
    }
    if cache:
        cache.set("usda_fdc", "get_food", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 3 — get_multiple_foods
# ---------------------------------------------------------------------------

def get_multiple_foods(
    fdc_ids: list[int],
    nutrients: Optional[list[int]] = None,
) -> list[dict]:
    cache = get_cache()
    key = FoodCache.make_key("get_multiple_foods", fdc_ids=sorted(fdc_ids),
                             nutrients=sorted(nutrients) if nutrients else None)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    foods = _get_fdc().get_multiple_foods(fdc_ids=fdc_ids, nutrients=nutrients)
    response = [
        {
            "source": "USDA FoodData Central",
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
    if cache:
        cache.set("usda_fdc", "get_multiple_foods", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 4 — get_food_nutrients
# ---------------------------------------------------------------------------

def get_food_nutrients(fdc_id: int) -> dict:
    cache = get_cache()
    key = FoodCache.make_key("get_food_nutrients", fdc_id=fdc_id)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    food = _get_fdc().get_food(fdc_id=fdc_id)

    rows = []
    for n in food.get("foodNutrients", []):
        amount = n.get("amount")
        if amount is None:
            continue
        info = n.get("nutrient", {})
        name = info.get("name") or n.get("name") or n.get("nutrientName", "Unknown")
        number = info.get("number") or n.get("nutrientNumber")
        unit = info.get("unitName") or n.get("unitName", "")
        rows.append({"name": name, "number": number, "amount": amount, "unit": unit,
                     "percentDailyValue": n.get("percentDailyValue")})

    def _sort_key(r: dict) -> int:
        try:
            return int(r["number"]) if r["number"] is not None else 9999
        except (TypeError, ValueError):
            return 9999

    rows.sort(key=_sort_key)

    response = {
        "source": "USDA FoodData Central",
        "fdcId": food.get("fdcId"),
        "description": food.get("description"),
        "dataType": food.get("dataType"),
        "servingSize": food.get("servingSize"),
        "servingSizeUnit": food.get("servingSizeUnit"),
        "nutrients": rows,
        "citation": citation_from_food(food),
    }
    if cache:
        cache.set("usda_fdc", "get_food_nutrients", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 5 — compare_foods
# ---------------------------------------------------------------------------

def compare_foods(fdc_id_a: int, fdc_id_b: int) -> dict:
    cache = get_cache()
    key = FoodCache.make_key("compare_foods",
                             fdc_id_a=min(fdc_id_a, fdc_id_b),
                             fdc_id_b=max(fdc_id_a, fdc_id_b))
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    food_a = _get_fdc().get_food(fdc_id=fdc_id_a)
    food_b = _get_fdc().get_food(fdc_id=fdc_id_b)

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
        comparison.append({
            "nutrient": nutrient_name, "unit": unit,
            "foodA_amount": a_amount, "foodB_amount": b_amount,
            "difference_a_minus_b": difference, "higher": higher,
        })

    response = {
        "source": "USDA FoodData Central",
        "foodA": {"fdcId": food_a.get("fdcId"), "description": food_a.get("description"),
                  "dataType": food_a.get("dataType"), "citation": citation_from_food(food_a)},
        "foodB": {"fdcId": food_b.get("fdcId"), "description": food_b.get("description"),
                  "dataType": food_b.get("dataType"), "citation": citation_from_food(food_b)},
        "comparison": comparison,
    }
    if cache:
        cache.set("usda_fdc", "compare_foods", key, response)
    return response


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
    cache = get_cache()
    key = FoodCache.make_key("list_foods",
                             data_type=sorted(data_type) if data_type else None,
                             page_size=page_size, page_number=page_number,
                             sort_by=sort_by, sort_order=sort_order)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    foods = _get_fdc().list_foods(
        data_type=data_type, page_size=page_size, page_number=page_number,
        sort_by=sort_by, sort_order=sort_order,
    )
    response = {
        "source": "USDA FoodData Central",
        "pageNumber": page_number,
        "pageSize": page_size,
        "foods": [
            {"fdcId": f.get("fdcId"), "description": f.get("description"),
             "dataType": f.get("dataType"), "publicationDate": f.get("publicationDate"),
             "brandOwner": f.get("brandOwner")}
            for f in (foods if isinstance(foods, list) else [])
        ],
    }
    if cache:
        cache.set("usda_fdc", "list_foods", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 7 — list_foods_by_nutrient
# ---------------------------------------------------------------------------

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
    cache = get_cache()
    key = FoodCache.make_key("list_foods_by_nutrient",
                             nutrient_name=nutrient_name.lower(),
                             top_n=top_n,
                             data_type=sorted(data_type) if data_type else None)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    whole_foods_mode = data_type is not None and set(data_type).issubset(
        {"Foundation", "SR Legacy"}
    )
    search_query = (
        _NUTRIENT_TO_FOOD_QUERY.get(nutrient_name.lower().strip(), nutrient_name)
        if whole_foods_mode
        else nutrient_name
    )

    result = _get_fdc().search_foods(query=search_query, data_type=data_type, page_size=50)
    foods = result.get("foods", [])

    scored: list[dict] = []
    for f in foods:
        amount = None
        matched_nutrient = nutrient_name
        for n in f.get("foodNutrients", []):
            n_name = n.get("nutrientName", "")
            if nutrient_name.lower() in n_name.lower():
                amount = n.get("value")
                matched_nutrient = n_name
                break
        if amount is not None:
            scored.append({
                "fdcId": f.get("fdcId"), "description": f.get("description"),
                "dataType": f.get("dataType"), "nutrientName": matched_nutrient,
                "nutrientAmount": amount, "citation": citation_from_food(f),
            })

    scored.sort(key=lambda x: float(x["nutrientAmount"] or 0), reverse=True)

    response = {
        "source": "USDA FoodData Central",
        "nutrient": nutrient_name,
        "searchQuery": search_query,
        "dataTypes": data_type,
        "topFoods": scored[:top_n],
        "totalSearched": len(foods),
    }
    if cache:
        cache.set("usda_fdc", "list_foods_by_nutrient", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 8 — get_food_citation
# ---------------------------------------------------------------------------

def get_food_citation(fdc_id: int) -> dict:
    cache = get_cache()
    key = FoodCache.make_key("get_food_citation", fdc_id=fdc_id)
    if cache and (hit := cache.get("usda_fdc", key)):
        return hit
    food = _get_fdc().get_food(fdc_id=fdc_id, format="abridged")
    response = {
        "source": "USDA FoodData Central",
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
    if cache:
        cache.set("usda_fdc", "get_food_citation", key, response)
    return response


# ===========================================================================
# FatSecret tools (2)
# ===========================================================================

def _parse_food_description(desc: str) -> dict:
    """Parse FatSecret food_description string into a nutrient dict.

    Format: "Per 1 serving - Calories: 220kcal | Fat: 10.00g | Carbs: 31.00g | Protein: 3.00g"
    """
    import re
    nutrients: dict = {}
    if not desc or " - " not in desc:
        return nutrients
    serving_part, nutrient_part = desc.split(" - ", 1)
    nutrients["servingDescription"] = serving_part.strip()
    for chunk in nutrient_part.split("|"):
        chunk = chunk.strip()
        if ":" not in chunk:
            continue
        label, value_str = chunk.split(":", 1)
        label = label.strip().lower()
        value_str = value_str.strip()
        # strip unit suffix (kcal, g, mg, µg, iu)
        num = re.sub(r"[a-zµ]+$", "", value_str, flags=re.IGNORECASE).strip()
        try:
            val = float(num)
        except ValueError:
            continue
        key_map = {
            "calories": "calories",
            "fat": "fat",
            "carbs": "carbohydrate",
            "carbohydrates": "carbohydrate",
            "protein": "protein",
            "fiber": "fiber",
            "sugar": "sugar",
            "sodium": "sodium",
            "cholesterol": "cholesterol",
        }
        mapped = key_map.get(label)
        if mapped:
            nutrients[mapped] = val
    return nutrients


def _parse_serving(serving: dict) -> dict:
    """Normalise a FatSecret serving dict (from food.get.v2) into a flat nutrient map."""
    fields = [
        "calories", "carbohydrate", "protein", "fat",
        "saturated_fat", "polyunsaturated_fat", "monounsaturated_fat",
        "trans_fat", "cholesterol", "sodium", "potassium",
        "fiber", "sugar", "added_sugars",
        "vitamin_a", "vitamin_c", "vitamin_d", "calcium", "iron",
    ]
    nutrients = {}
    for f in fields:
        val = serving.get(f)
        if val is not None:
            try:
                nutrients[f] = float(val)
            except (TypeError, ValueError):
                pass
    return {
        "servingId": serving.get("serving_id"),
        "servingDescription": serving.get("serving_description"),
        "metricServingAmount": serving.get("metric_serving_amount"),
        "metricServingUnit": serving.get("metric_serving_unit"),
        "numberOfUnits": serving.get("number_of_units"),
        "measurementDescription": serving.get("measurement_description"),
        "nutrients": nutrients,
    }


# ---------------------------------------------------------------------------
# Tool 9 — search_fatsecret_foods
# ---------------------------------------------------------------------------

def search_fatsecret_foods(
    query: str,
    max_results: int = 3,
    page_number: int = 0,
) -> dict:
    cache = get_cache()
    key = FoodCache.make_key("search_fatsecret_foods", query=query,
                             max_results=max_results, page_number=page_number)
    if cache and (hit := cache.get("fatsecret", key)):
        return hit

    raw = _get_fs().search_foods(query=query, page_number=page_number,
                                 max_results=max_results)
    foods_wrap = raw.get("foods", {})
    total = int(foods_wrap.get("total_results", 0))
    items = foods_wrap.get("food", [])
    if isinstance(items, dict):
        # single result returned as dict, not list
        items = [items]

    items.sort(key=lambda f: _relevance_score(f.get("food_name", ""), query), reverse=True)

    results = []
    for f in items:
        # v1 search returns food_description string, not structured food_servings
        desc = f.get("food_description", "")
        parsed = _parse_food_description(desc)
        results.append({
            "foodId": int(f["food_id"]) if str(f.get("food_id", "")).isdigit() else f.get("food_id"),
            "foodName": f.get("food_name"),
            "foodType": f.get("food_type"),
            "brandName": f.get("brand_name"),
            "foodUrl": f.get("food_url"),
            "foodDescription": desc,
            "servingDescription": parsed.get("servingDescription"),
            "calories": parsed.get("calories"),
            "fat": parsed.get("fat"),
            "carbohydrate": parsed.get("carbohydrate"),
            "protein": parsed.get("protein"),
        })

    response = {
        "source": "FatSecret",
        "query": query,
        "totalResults": total,
        "pageNumber": page_number,
        "foods": results,
    }
    if cache:
        cache.set("fatsecret", "search_fatsecret_foods", key, response)
    return response


# ---------------------------------------------------------------------------
# Tool 10 — get_fatsecret_food
# ---------------------------------------------------------------------------

def get_fatsecret_food(food_id: int) -> dict:
    food_id = str(food_id)
    cache = get_cache()
    key = FoodCache.make_key("get_fatsecret_food", food_id=food_id)
    if cache and (hit := cache.get("fatsecret", key)):
        return hit

    raw = _get_fs().get_food(food_id=food_id)
    food = raw.get("food", {})

    if not food:
        return {"source": "FatSecret", "error": "Food not found", "foodId": food_id}

    servings_raw = food.get("servings", {}) or {}
    serving_list = servings_raw.get("serving", [])
    if isinstance(serving_list, dict):
        # single serving returned as dict, not list
        serving_list = [serving_list]

    parsed_servings = [_parse_serving(s) for s in serving_list]

    response = {
        "source": "FatSecret",
        "foodId": food.get("food_id"),
        "foodName": food.get("food_name"),
        "foodType": food.get("food_type"),
        "brandName": food.get("brand_name"),
        "foodUrl": food.get("food_url"),
        "servings": parsed_servings,
        "citation": {
            "source": "FatSecret Platform API",
            "foodId": food.get("food_id"),
            "url": food.get("food_url"),
        },
    }
    if cache:
        cache.set("fatsecret", "get_fatsecret_food", key, response)
    return response
