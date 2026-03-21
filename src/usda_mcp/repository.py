from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


@dataclass
class FoodRepository:
    db_path: Path = DEFAULT_DB_PATH

    def __post_init__(self) -> None:
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "FoodRepository":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def metadata(self) -> dict[str, str]:
        rows = self.connection.execute("SELECT key, value FROM metadata").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def search_foods(self, query: str, limit: int = 10) -> dict[str, Any]:
        normalized = query.strip().lower()
        rows = self.connection.execute(
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
    ) -> dict[str, Any]:
        nutrient_names = [self._resolve_nutrient_name(item) for item in (nutrients or DEFAULT_NUTRIENTS)]
        preferred_nutrient = nutrient_names[0] if nutrients else None
        food = self._resolve_food(food_query, preferred_nutrient)
        placeholders = ", ".join("?" for _ in nutrient_names)
        rows = self.connection.execute(
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

    def compare_foods(self, food_a: str, food_b: str, nutrient: str) -> dict[str, Any]:
        nutrient_name = self._resolve_nutrient_name(nutrient)
        left = self._resolve_food(food_a, nutrient_name)
        right = self._resolve_food(food_b, nutrient_name)
        left_value = self._get_food_nutrient_value(left["fdc_id"], nutrient_name)
        right_value = self._get_food_nutrient_value(right["fdc_id"], nutrient_name)
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

    def list_foods_by_nutrient(self, nutrient: str, limit: int = 10) -> dict[str, Any]:
        nutrient_name = self._resolve_nutrient_name(nutrient)
        rows = self.connection.execute(
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

    def get_food_source_metadata(self, food_query: str) -> dict[str, Any]:
        food = self._resolve_food(food_query)
        return self._food_with_citation(food)

    def _resolve_food(self, query: str, nutrient_name: str | None = None) -> sqlite3.Row:
        if query.isdigit():
            row = self.connection.execute(
                "SELECT * FROM foods WHERE fdc_id = ?",
                (int(query),),
            ).fetchone()
            if row and (nutrient_name is None or self._food_has_nutrient(row["fdc_id"], nutrient_name)):
                return row

        normalized = query.strip().lower()
        if nutrient_name is None:
            row = self.connection.execute(
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
            row = self.connection.execute(
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

    def _resolve_nutrient_name(self, query: str) -> str:
        normalized = _normalize(query)
        aliased = NUTRIENT_ALIASES.get(normalized)
        if aliased:
            return aliased

        rows = self.connection.execute(
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

    def _get_food_nutrient_value(self, food_id: int, nutrient_name: str) -> dict[str, Any]:
        row = self.connection.execute(
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

    def _food_has_nutrient(self, food_id: int, nutrient_name: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM nutrients
            WHERE food_id = ? AND nutrient_name = ?
            LIMIT 1
            """,
            (food_id, nutrient_name),
        ).fetchone()
        return row is not None

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
