from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_ZIP_PATH = Path("data/raw/FoodData_Central_foundation_food_json_2025-12-18.zip")
DEFAULT_DB_PATH = Path("data/derived/usda_foundation_mini.sqlite")


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS foods (
    fdc_id INTEGER PRIMARY KEY,
    description TEXT NOT NULL,
    data_type TEXT,
    food_class TEXT,
    food_category TEXT,
    publication_date TEXT,
    ndb_number INTEGER,
    is_historical_reference INTEGER NOT NULL DEFAULT 0,
    portions_json TEXT NOT NULL,
    source_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nutrients (
    food_id INTEGER NOT NULL,
    nutrient_id INTEGER NOT NULL,
    nutrient_number TEXT,
    nutrient_name TEXT NOT NULL,
    unit_name TEXT,
    amount REAL,
    rank REAL,
    derivation_code TEXT,
    derivation_description TEXT,
    PRIMARY KEY (food_id, nutrient_id),
    FOREIGN KEY (food_id) REFERENCES foods(fdc_id)
);

CREATE INDEX IF NOT EXISTS idx_foods_description ON foods(description);
CREATE INDEX IF NOT EXISTS idx_nutrients_food_id ON nutrients(food_id);
CREATE INDEX IF NOT EXISTS idx_nutrients_name ON nutrients(nutrient_name);
"""


def _load_foundation_foods(zip_path: Path) -> tuple[str, list[dict]]:
    with zipfile.ZipFile(zip_path) as archive:
        json_name = archive.namelist()[0]
        with archive.open(json_name) as handle:
            payload = json.load(handle)
    foods = payload.get("FoundationFoods", [])
    return json_name, foods


def build_database(zip_path: Path = DEFAULT_ZIP_PATH, db_path: Path = DEFAULT_DB_PATH) -> Path:
    if not zip_path.exists():
        raise FileNotFoundError(
            f"USDA archive not found at {zip_path}. Download the Foundation Foods JSON zip first."
        )

    json_name, foods = _load_foundation_foods(zip_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(SCHEMA)
        connection.execute("DELETE FROM metadata")
        connection.execute("DELETE FROM nutrients")
        connection.execute("DELETE FROM foods")

        built_at = datetime.now(UTC).isoformat()
        metadata_rows = [
            ("source_name", "USDA FoodData Central"),
            ("source_dataset", "Foundation Foods"),
            ("source_release", "2025-12-18"),
            ("source_archive", zip_path.name),
            ("source_json", json_name),
            ("built_at_utc", built_at),
            ("food_count", str(len(foods))),
        ]
        connection.executemany("INSERT INTO metadata(key, value) VALUES(?, ?)", metadata_rows)

        food_rows: list[tuple] = []
        nutrient_rows: list[tuple] = []

        for food in foods:
            food_rows.append(
                (
                    food["fdcId"],
                    food["description"],
                    food.get("dataType"),
                    food.get("foodClass"),
                    (food.get("foodCategory") or {}).get("description"),
                    food.get("publicationDate"),
                    food.get("ndbNumber"),
                    int(bool(food.get("isHistoricalReference"))),
                    json.dumps(food.get("foodPortions", []), ensure_ascii=True),
                    json.dumps(
                        {
                            "inputFoods": food.get("inputFoods", []),
                            "foodAttributes": food.get("foodAttributes", []),
                            "nutrientConversionFactors": food.get("nutrientConversionFactors", []),
                        },
                        ensure_ascii=True,
                    ),
                )
            )

            for nutrient in food.get("foodNutrients", []):
                nutrient_info = nutrient.get("nutrient") or {}
                derivation = nutrient.get("foodNutrientDerivation") or {}
                nutrient_rows.append(
                    (
                        food["fdcId"],
                        nutrient_info.get("id"),
                        nutrient_info.get("number"),
                        nutrient_info.get("name"),
                        nutrient_info.get("unitName"),
                        nutrient.get("amount"),
                        nutrient_info.get("rank"),
                        derivation.get("code"),
                        derivation.get("description"),
                    )
                )

        connection.executemany(
            """
            INSERT INTO foods(
                fdc_id, description, data_type, food_class, food_category,
                publication_date, ndb_number, is_historical_reference,
                portions_json, source_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            food_rows,
        )
        connection.executemany(
            """
            INSERT INTO nutrients(
                food_id, nutrient_id, nutrient_number, nutrient_name, unit_name,
                amount, rank, derivation_code, derivation_description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            nutrient_rows,
        )
        connection.commit()
    finally:
        connection.close()

    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a mini USDA Foundation Foods SQLite database.")
    parser.add_argument("--zip-path", type=Path, default=DEFAULT_ZIP_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    db_path = build_database(args.zip_path, args.db_path)
    print(f"Built USDA mini database at {db_path}")


if __name__ == "__main__":
    main()
