from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from usda_mcp.usda_api import SUPPORTED_API_DATA_TYPES, USDAAPIClient, normalize_api_data_types


DEFAULT_DB_PATH = Path("data/derived/usda_foundation_mini.sqlite")

DEFAULT_NUTRIENTS = [
    "Energy",
    "Protein",
    "Total lipid (fat)",
    "Carbohydrate, by difference",
    "Fiber, total dietary",
    "Total Sugars",
    "Calcium, Ca",
    "Iron, Fe",
    "Potassium, K",
    "Vitamin C, total ascorbic acid",
]

NUTRIENT_ALIASES = {
    "calories": "Energy",
    "energy": "Energy",
    "protein": "Protein",
    "fat": "Total lipid (fat)",
    "total fat": "Total lipid (fat)",
    "carbs": "Carbohydrate, by difference",
    "carbohydrates": "Carbohydrate, by difference",
    "fiber": "Fiber, total dietary",
    "fibre": "Fiber, total dietary",
    "sugar": "Total Sugars",
    "sugars": "Total Sugars",
    "calcium": "Calcium, Ca",
    "iron": "Iron, Fe",
    "potassium": "Potassium, K",
    "vitamin c": "Vitamin C, total ascorbic acid",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _query_variants(query: str) -> list[str]:
    normalized = _normalize(query)
    variants = {normalized}
    if normalized.endswith("es"):
        variants.add(normalized[:-2])
    elif normalized.endswith("s"):
        variants.add(normalized[:-1])
    else:
        variants.add(f"{normalized}s")
        variants.add(f"{normalized}es")
    return [item for item in variants if item]


def _food_match_sort_key(query: str, description: str) -> tuple[int, int, str]:
    normalized_query = _normalize(query)
    normalized_description = _normalize(description)
    variants = _query_variants(query)
    description_words = normalized_description.split()
    penalty = _description_penalty(normalized_query, normalized_description)

    if normalized_description in variants:
        return (0, penalty, normalized_description)
    if description_words and description_words[0] in variants:
        return (1, penalty, normalized_description)
    if any(normalized_description.startswith(variant + " ") for variant in variants):
        return (2, penalty, normalized_description)
    if any(f" {variant} " in f" {normalized_description} " for variant in variants):
        return (3, penalty, normalized_description)
    if normalized_query in normalized_description:
        return (4, penalty, normalized_description)
    return (5, penalty, normalized_description)


def _description_penalty(normalized_query: str, normalized_description: str) -> int:
    penalty = 0
    penalty_terms = {
        "juice": 3,
        "concentrate": 3,
        "refrigerated": 2,
        "pulp": 2,
        "pepper": 4,
        "peppers": 4,
        "bell": 2,
        "canned": 2,
        "frozen": 2,
        "cooked": 2,
        "fried": 2,
        "dried": 2,
    }
    for term, value in penalty_terms.items():
        if term in normalized_description and term not in normalized_query:
            penalty += value
    if "raw" in normalized_description:
        penalty -= 1
    return penalty


@dataclass
class FoodRepository:
    db_path: Path = DEFAULT_DB_PATH
    api_client: USDAAPIClient | None = None
    connection: sqlite3.Connection | None = field(init=False, default=None)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def __enter__(self) -> "FoodRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def metadata(self) -> dict[str, str]:
        rows = self._connection().execute("SELECT key, value FROM metadata").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def search_foods(
        self,
        query: str,
        limit: int = 10,
        *,
        source: str = "local",
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if source == "api":
            client = self._require_api_client()
            return self._search_foods_api(
                client,
                query,
                limit=limit,
                data_types=normalize_api_data_types(data_types),
            )

        normalized = query.strip().lower()
        rows = self._connection().execute(
            """
            SELECT fdc_id, description, data_type, food_category, publication_date
            FROM foods
            WHERE lower(description) LIKE '%' || ? || '%'
            ORDER BY
                CASE
                    WHEN lower(description) = ? THEN 0
                    WHEN lower(description) LIKE ? || '%' THEN 1
                    ELSE 2
                END,
                length(description),
                description
            LIMIT ?
            """,
            (normalized, normalized, normalized, limit),
        ).fetchall()
        return {
            "query": query,
            "results": [self._serialize_food_row(row) for row in rows],
            "source": self.metadata(),
        }

    def get_food_nutrients(
        self,
        food_query: str,
        nutrients: list[str] | None = None,
        *,
        source: str = "local",
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if source == "api":
            client = self._require_api_client()
            return self._get_food_nutrients_api(
                client,
                food_query,
                nutrients=nutrients,
                data_types=normalize_api_data_types(data_types),
            )

        nutrient_names = [self._resolve_nutrient_name_local(item) for item in (nutrients or DEFAULT_NUTRIENTS)]
        preferred_nutrient = nutrient_names[0] if nutrients else None
        food = self._resolve_food_local(food_query, preferred_nutrient)
        placeholders = ", ".join("?" for _ in nutrient_names)
        rows = self._connection().execute(
            f"""
            SELECT nutrient_id, nutrient_number, nutrient_name, unit_name, amount, rank
            FROM nutrients
            WHERE food_id = ? AND nutrient_name IN ({placeholders})
            ORDER BY rank, nutrient_name
            """,
            [food["fdc_id"], *nutrient_names],
        ).fetchall()
        found_names = {row["nutrient_name"] for row in rows}
        return {
            "food": self._food_with_citation(food),
            "nutrients": [self._serialize_nutrient_row(row) for row in rows],
            "missing_nutrients": [name for name in nutrient_names if name not in found_names],
        }

    def compare_foods(
        self,
        food_a: str,
        food_b: str,
        nutrient: str,
        *,
        source: str = "local",
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if source == "api":
            client = self._require_api_client()
            return self._compare_foods_api(
                client,
                food_a,
                food_b,
                nutrient,
                data_types=normalize_api_data_types(data_types),
            )

        nutrient_name = self._resolve_nutrient_name_local(nutrient)
        left = self._resolve_food_local(food_a, nutrient_name)
        right = self._resolve_food_local(food_b, nutrient_name)
        left_value = self._get_food_nutrient_value_local(left["fdc_id"], nutrient_name)
        right_value = self._get_food_nutrient_value_local(right["fdc_id"], nutrient_name)
        winner = None
        if left_value["amount"] > right_value["amount"]:
            winner = left["description"]
        elif right_value["amount"] > left_value["amount"]:
            winner = right["description"]
        return {
            "nutrient": nutrient_name,
            "food_a": self._food_with_citation(left),
            "food_b": self._food_with_citation(right),
            "food_a_value": left_value,
            "food_b_value": right_value,
            "difference": round(left_value["amount"] - right_value["amount"], 4),
            "winner": winner,
        }

    def list_foods_by_nutrient(
        self,
        nutrient: str,
        limit: int = 10,
        *,
        source: str = "local",
    ) -> dict[str, Any]:
        if source == "api":
            raise ValueError(
                "Live USDA API mode does not support global nutrient ranking in this mini build. "
                "Use search_foods + get_food_nutrients for API-backed queries."
            )

        nutrient_name = self._resolve_nutrient_name_local(nutrient)
        rows = self._connection().execute(
            """
            SELECT foods.fdc_id, foods.description, foods.food_category, nutrients.amount, nutrients.unit_name
            FROM nutrients
            JOIN foods ON foods.fdc_id = nutrients.food_id
            WHERE nutrients.nutrient_name = ?
            ORDER BY nutrients.amount DESC, foods.description
            LIMIT ?
            """,
            (nutrient_name, limit),
        ).fetchall()
        return {
            "nutrient": nutrient_name,
            "results": [
                {
                    "fdc_id": row["fdc_id"],
                    "description": row["description"],
                    "food_category": row["food_category"],
                    "amount_per_100g": row["amount"],
                    "unit": row["unit_name"],
                }
                for row in rows
            ],
            "source": self.metadata(),
        }

    def get_food_source_metadata(
        self,
        food_query: str,
        *,
        source: str = "local",
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if source == "api":
            client = self._require_api_client()
            food = self._resolve_food_api(
                client,
                food_query,
                data_types=normalize_api_data_types(data_types),
            )
            return self._api_food_with_citation(food)

        food = self._resolve_food_local(food_query)
        return self._food_with_citation(food)

    def _search_foods_api(
        self,
        client: USDAAPIClient,
        query: str,
        *,
        limit: int,
        data_types: list[str] | None,
    ) -> dict[str, Any]:
        response = client.search_foods(query, page_size=limit, data_types=data_types)
        return {
            "query": query,
            "results": [self._serialize_api_food(food) for food in response.get("foods", [])],
            "source": self._api_source_metadata(data_types),
            "total_hits": response.get("totalHits"),
            "current_page": response.get("currentPage"),
        }

    def _get_food_nutrients_api(
        self,
        client: USDAAPIClient,
        food_query: str,
        *,
        nutrients: list[str] | None,
        data_types: list[str] | None,
    ) -> dict[str, Any]:
        nutrient_names = [self._resolve_nutrient_name_api(client, item) for item in (nutrients or DEFAULT_NUTRIENTS)]
        preferred_nutrient = nutrient_names[0] if nutrients else None
        food = self._resolve_food_api(client, food_query, nutrient_name=preferred_nutrient, data_types=data_types)
        nutrient_rows = self._extract_api_nutrients(food)
        selected = [row for row in nutrient_rows if row["name"] in nutrient_names]
        found_names = {row["name"] for row in selected}
        return {
            "food": self._api_food_with_citation(food),
            "nutrients": selected,
            "missing_nutrients": [name for name in nutrient_names if name not in found_names],
        }

    def _compare_foods_api(
        self,
        client: USDAAPIClient,
        food_a: str,
        food_b: str,
        nutrient: str,
        *,
        data_types: list[str] | None,
    ) -> dict[str, Any]:
        nutrient_name = self._resolve_nutrient_name_api(client, nutrient)
        left = self._resolve_food_api(client, food_a, nutrient_name=nutrient_name, data_types=data_types)
        right = self._resolve_food_api(client, food_b, nutrient_name=nutrient_name, data_types=data_types)
        left_value = self._get_api_food_nutrient_value(left, nutrient_name)
        right_value = self._get_api_food_nutrient_value(right, nutrient_name)
        winner = None
        if left_value["amount"] > right_value["amount"]:
            winner = left.get("description")
        elif right_value["amount"] > left_value["amount"]:
            winner = right.get("description")
        return {
            "nutrient": nutrient_name,
            "food_a": self._api_food_with_citation(left),
            "food_b": self._api_food_with_citation(right),
            "food_a_value": left_value,
            "food_b_value": right_value,
            "difference": round(left_value["amount"] - right_value["amount"], 4),
            "winner": winner,
        }

    def _resolve_food_local(self, query: str, nutrient_name: str | None = None) -> sqlite3.Row:
        if query.isdigit():
            row = self._connection().execute(
                "SELECT * FROM foods WHERE fdc_id = ?",
                (int(query),),
            ).fetchone()
            if row and (nutrient_name is None or self._food_has_nutrient_local(row["fdc_id"], nutrient_name)):
                return row

        normalized = query.strip().lower()
        if nutrient_name is None:
            row = self._connection().execute(
                """
                SELECT *
                FROM foods
                WHERE lower(description) LIKE '%' || ? || '%'
                ORDER BY
                    CASE
                        WHEN lower(description) = ? THEN 0
                        WHEN lower(description) LIKE ? || '%' THEN 1
                        ELSE 2
                    END,
                    length(description),
                    description
                LIMIT 1
                """,
                (normalized, normalized, normalized),
            ).fetchone()
        else:
            row = self._connection().execute(
                """
                SELECT foods.*
                FROM foods
                JOIN nutrients
                    ON foods.fdc_id = nutrients.food_id
                   AND nutrients.nutrient_name = ?
                WHERE lower(foods.description) LIKE '%' || ? || '%'
                GROUP BY foods.fdc_id
                ORDER BY
                    CASE
                        WHEN lower(foods.description) = ? THEN 0
                        WHEN lower(foods.description) LIKE ? || '%' THEN 1
                        ELSE 2
                    END,
                    length(foods.description),
                    foods.description
                LIMIT 1
                """,
                (nutrient_name, normalized, normalized, normalized),
            ).fetchone()
        if row is None:
            if nutrient_name is None:
                raise ValueError(f"No USDA Foundation food matched '{query}'.")
            raise ValueError(
                f"No USDA Foundation food matched '{query}' with nutrient '{nutrient_name}'."
            )
        return row

    def _resolve_food_api(
        self,
        client: USDAAPIClient,
        query: str,
        *,
        nutrient_name: str | None = None,
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        if query.isdigit():
            food = client.get_food_details(int(query))
            if nutrient_name is None or self._api_food_has_nutrient(food, nutrient_name):
                return food

        response = client.search_foods(query, page_size=25, data_types=data_types)
        foods = sorted(
            response.get("foods", []),
            key=lambda item: _food_match_sort_key(query, item.get("description", "")),
        )
        if not foods:
            raise ValueError(f"No USDA API food matched '{query}'.")

        if nutrient_name is None:
            return self._fetch_first_detail_candidate(client, foods, query)

        detail_errors = []
        for item in foods:
            if not self._api_food_mentions_nutrient(item, nutrient_name):
                continue
            try:
                detail = client.get_food_details(item["fdcId"])
            except ValueError as exc:
                detail_errors.append(str(exc))
                if self._api_food_has_nutrient(item, nutrient_name):
                    return item
                continue
            if self._api_food_has_nutrient(detail, nutrient_name):
                return detail

        if detail_errors:
            raise ValueError(
                f"No USDA API food matched '{query}' with nutrient '{nutrient_name}'. "
                f"Detail lookup errors included: {detail_errors[0]}"
            )
        raise ValueError(f"No USDA API food matched '{query}' with nutrient '{nutrient_name}'.")

    @staticmethod
    def _fetch_first_detail_candidate(
        client: USDAAPIClient,
        foods: list[dict[str, Any]],
        query: str,
    ) -> dict[str, Any]:
        detail_errors = []
        for item in foods:
            try:
                return client.get_food_details(item["fdcId"])
            except ValueError as exc:
                detail_errors.append(str(exc))
                return item
        if detail_errors:
            raise ValueError(
                f"USDA API search found matches for '{query}', but all detail lookups failed. "
                f"First error: {detail_errors[0]}"
            )
        raise ValueError(f"No USDA API food matched '{query}'.")

    def _resolve_nutrient_name_local(self, query: str) -> str:
        normalized = _normalize(query)
        aliased = NUTRIENT_ALIASES.get(normalized)
        if aliased:
            return aliased

        rows = self._connection().execute(
            "SELECT DISTINCT nutrient_name, COALESCE(rank, 999999) AS rank FROM nutrients"
        ).fetchall()
        candidates = []
        for row in rows:
            normalized_name = _normalize(row["nutrient_name"])
            if normalized == normalized_name:
                candidates.append((0, row["rank"], row["nutrient_name"]))
            elif normalized_name.startswith(normalized):
                candidates.append((1, row["rank"], row["nutrient_name"]))
            elif normalized in normalized_name:
                candidates.append((2, row["rank"], row["nutrient_name"]))
        if not candidates:
            raise ValueError(f"No nutrient matched '{query}'.")
        candidates.sort()
        return candidates[0][2]

    def _resolve_nutrient_name_api(self, client: USDAAPIClient, query: str) -> str:
        normalized = _normalize(query)
        aliased = NUTRIENT_ALIASES.get(normalized)
        if aliased:
            return aliased

        nutrient_names = client.search_nutrient_names(query)
        candidates = []
        for name in nutrient_names:
            normalized_name = _normalize(name)
            if normalized == normalized_name:
                candidates.append((0, name))
            elif normalized_name.startswith(normalized):
                candidates.append((1, name))
            elif normalized in normalized_name:
                candidates.append((2, name))
        if not candidates:
            raise ValueError(f"No nutrient matched '{query}' in USDA API results.")
        candidates.sort()
        return candidates[0][1]

    def _get_food_nutrient_value_local(self, food_id: int, nutrient_name: str) -> dict[str, Any]:
        row = self._connection().execute(
            """
            SELECT nutrient_id, nutrient_number, nutrient_name, amount, unit_name
            FROM nutrients
            WHERE food_id = ? AND nutrient_name = ?
            """,
            (food_id, nutrient_name),
        ).fetchone()
        if row is None:
            raise ValueError(f"Food {food_id} does not contain '{nutrient_name}' in this USDA subset.")
        return self._serialize_nutrient_row(row)

    def _get_api_food_nutrient_value(self, food: dict[str, Any], nutrient_name: str) -> dict[str, Any]:
        for nutrient in self._extract_api_nutrients(food):
            if nutrient["name"] == nutrient_name:
                return nutrient
        raise ValueError(
            f"Food {food.get('fdcId')} does not contain '{nutrient_name}' in the USDA API response."
        )

    def _food_has_nutrient_local(self, food_id: int, nutrient_name: str) -> bool:
        row = self._connection().execute(
            """
            SELECT 1
            FROM nutrients
            WHERE food_id = ? AND nutrient_name = ?
            LIMIT 1
            """,
            (food_id, nutrient_name),
        ).fetchone()
        return row is not None

    def _api_food_has_nutrient(self, food: dict[str, Any], nutrient_name: str) -> bool:
        return any(nutrient["name"] == nutrient_name for nutrient in self._extract_api_nutrients(food))

    @staticmethod
    def _api_food_mentions_nutrient(food: dict[str, Any], nutrient_name: str) -> bool:
        for item in food.get("foodNutrients", []):
            nutrient = item.get("nutrient") or {}
            name = nutrient.get("name") or item.get("nutrientName") or item.get("name")
            if name == nutrient_name:
                return True
        return False

    def _food_with_citation(self, row: sqlite3.Row) -> dict[str, Any]:
        serialized = self._serialize_food_row(row)
        metadata = self.metadata()
        serialized["portions"] = json.loads(row["portions_json"])
        serialized["citation"] = {
            "source": metadata.get("source_name"),
            "dataset": metadata.get("source_dataset"),
            "release": metadata.get("source_release"),
            "archive": metadata.get("source_archive"),
            "food_description": row["description"],
            "fdc_id": row["fdc_id"],
            "publication_date": row["publication_date"],
        }
        return serialized

    def _api_food_with_citation(self, food: dict[str, Any]) -> dict[str, Any]:
        serialized = self._serialize_api_food(food)
        serialized["portions"] = food.get("foodPortions", [])
        serialized["citation"] = {
            "source": "USDA FoodData Central API",
            "dataset": food.get("dataType") or "Multiple USDA data types",
            "fdc_id": food.get("fdcId"),
            "food_description": food.get("description"),
            "publication_date": food.get("publicationDate"),
            "data_type": food.get("dataType"),
        }
        return serialized

    def _api_source_metadata(self, data_types: list[str] | None) -> dict[str, str]:
        return {
            "source_name": "USDA FoodData Central API",
            "source_dataset": ", ".join(data_types) if data_types else "All USDA API data types",
            "source_mode": "live_api",
        }

    @staticmethod
    def available_api_data_types() -> list[str]:
        return list(SUPPORTED_API_DATA_TYPES)

    def _connection(self) -> sqlite3.Connection:
        if self.connection is None:
            if not self.db_path.exists():
                raise FileNotFoundError(
                    f"Local USDA SQLite database not found at {self.db_path}. "
                    "Build it first or use source='api' with USDA_API_KEY set."
                )
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
        return self.connection

    def _require_api_client(self) -> USDAAPIClient:
        if self.api_client is None:
            self.api_client = USDAAPIClient.from_env()
        return self.api_client

    @staticmethod
    def _serialize_food_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "fdc_id": row["fdc_id"],
            "description": row["description"],
            "data_type": row["data_type"],
            "food_category": row["food_category"],
            "publication_date": row["publication_date"],
        }

    @staticmethod
    def _serialize_nutrient_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "nutrient_id": row["nutrient_id"],
            "number": row["nutrient_number"],
            "name": row["nutrient_name"],
            "amount": row["amount"],
            "unit": row["unit_name"],
        }

    @staticmethod
    def _serialize_api_food(food: dict[str, Any]) -> dict[str, Any]:
        category = food.get("foodCategory")
        if isinstance(category, dict):
            category = category.get("description")
        return {
            "fdc_id": food.get("fdcId"),
            "description": food.get("description"),
            "data_type": food.get("dataType"),
            "food_category": category,
            "publication_date": food.get("publicationDate"),
            "brand_owner": food.get("brandOwner"),
            "gtin_upc": food.get("gtinUpc"),
        }

    @staticmethod
    def _extract_api_nutrients(food: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for item in food.get("foodNutrients", []):
            nutrient = item.get("nutrient") or {}
            nutrient_id = nutrient.get("id") or item.get("nutrientId")
            nutrient_number = nutrient.get("number") or item.get("number")
            nutrient_name = nutrient.get("name") or item.get("nutrientName") or item.get("name")
            unit_name = nutrient.get("unitName") or item.get("unitName")
            amount = item.get("amount") or item.get("value")
            if nutrient_name is None or amount is None:
                continue
            results.append(
                {
                    "nutrient_id": nutrient_id,
                    "number": nutrient_number,
                    "name": nutrient_name,
                    "amount": amount,
                    "unit": unit_name,
                }
            )
        return results
