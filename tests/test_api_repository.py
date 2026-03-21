from __future__ import annotations

import unittest

from usda_mcp.repository import FoodRepository
from usda_mcp.usda_api import normalize_api_data_types


class FakeUSDAAPIClient:
    def __init__(self) -> None:
        self.details = {
            100: {
                "fdcId": 100,
                "description": "Banana, raw",
                "dataType": "Foundation",
                "foodCategory": "Fruits and Fruit Juices",
                "publicationDate": "2025-04-24",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 358},
                    {"nutrient": {"id": 1003, "number": "203", "name": "Protein", "unitName": "g"}, "amount": 1.1},
                ],
                "foodPortions": [],
            },
            150: {
                "fdcId": 150,
                "description": "Peppers, banana or Hungarian wax, seeded, raw",
                "dataType": "Foundation",
                "foodCategory": "Vegetables and Vegetable Products",
                "publicationDate": "2025-12-18",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 177.4},
                ],
                "foodPortions": [],
            },
            200: {
                "fdcId": 200,
                "description": "Avocado, Hass, raw",
                "dataType": "Foundation",
                "foodCategory": "Fruits and Fruit Juices",
                "publicationDate": "2025-04-24",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 485},
                    {"nutrient": {"id": 1003, "number": "203", "name": "Protein", "unitName": "g"}, "amount": 2.0},
                ],
                "foodPortions": [],
            },
            250: {
                "fdcId": 250,
                "description": "Oranges, raw, navels",
                "dataType": "Foundation",
                "foodCategory": "Fruits and Fruit Juices",
                "publicationDate": "2025-04-24",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 181.0},
                ],
                "foodPortions": [],
            },
            260: {
                "fdcId": 260,
                "description": "Peppers, bell, orange, raw",
                "dataType": "Foundation",
                "foodCategory": "Vegetables and Vegetable Products",
                "publicationDate": "2022-04-28",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 200.8},
                ],
                "foodPortions": [],
            },
            270: {
                "fdcId": 270,
                "description": "Orange juice, no pulp, not fortified, from concentrate, refrigerated",
                "dataType": "Foundation",
                "foodCategory": "Fruits and Fruit Juices",
                "publicationDate": "2021-10-28",
                "foodNutrients": [
                    {"nutrient": {"id": 1092, "number": "306", "name": "Potassium, K", "unitName": "mg"}, "amount": 179.5},
                ],
                "foodPortions": [],
            },
        }

    def search_foods(self, query: str, *, page_size: int = 10, page_number: int = 1, data_types=None):
        foods = []
        for item in self.details.values():
            if query.lower() in item["description"].lower():
                foods.append(
                    {
                        "fdcId": item["fdcId"],
                        "description": item["description"],
                        "dataType": item["dataType"],
                        "foodCategory": item["foodCategory"],
                        "publicationDate": item["publicationDate"],
                        "foodNutrients": [
                            {
                                "nutrientName": nutrient["nutrient"]["name"],
                                "value": nutrient["amount"],
                                "unitName": nutrient["nutrient"]["unitName"],
                                "nutrientNumber": nutrient["nutrient"]["number"],
                            }
                            for nutrient in item["foodNutrients"]
                        ],
                    }
                )
        return {"foods": foods[:page_size], "totalHits": len(foods), "currentPage": page_number}

    def get_food_details(self, fdc_id: int):
        return self.details[fdc_id]

    def search_nutrient_names(self, query: str):
        return ["Potassium, K", "Protein"]


class FlakyDetailUSDAAPIClient(FakeUSDAAPIClient):
    def get_food_details(self, fdc_id: int):
        if fdc_id in {100, 250}:
            raise ValueError(f"USDA API request failed with HTTP 404: mock missing detail for {fdc_id}")
        return super().get_food_details(fdc_id)


class APIRepositoryTests(unittest.TestCase):
    def test_search_foods_api_returns_matches(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        result = repo.search_foods("banana", source="api")
        self.assertEqual(result["results"][0]["description"], "Banana, raw")
        self.assertEqual(result["source"]["source_mode"], "live_api")

    def test_get_food_nutrients_api_returns_requested_values(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        result = repo.get_food_nutrients("banana", nutrients=["potassium"], source="api")
        self.assertEqual(result["food"]["fdc_id"], 100)
        self.assertEqual(result["nutrients"][0]["name"], "Potassium, K")
        self.assertGreaterEqual(len(result["candidate_matches"]), 2)
        self.assertEqual(result["candidate_matches"][0]["description"], "Banana, raw")

    def test_compare_foods_api_uses_live_details(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        result = repo.compare_foods("banana", "avocado", "potassium", source="api")
        self.assertEqual(result["winner"], "Avocado, Hass, raw")

    def test_compare_foods_api_prefers_fruit_over_pepper_matches(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        result = repo.compare_foods(
            "banana",
            "orange",
            "potassium",
            source="api",
            data_types=["Foundation"],
        )
        self.assertEqual(result["food_a"]["description"], "Banana, raw")
        self.assertEqual(result["food_b"]["description"], "Oranges, raw, navels")
        self.assertEqual(result["food_a_candidates"][0]["description"], "Banana, raw")
        self.assertEqual(result["food_b_candidates"][0]["description"], "Oranges, raw, navels")

    def test_compare_foods_api_falls_back_to_search_row_when_best_detail_fails(self) -> None:
        repo = FoodRepository(api_client=FlakyDetailUSDAAPIClient())
        result = repo.compare_foods(
            "banana",
            "orange",
            "potassium",
            source="api",
            data_types=["Foundation"],
        )
        self.assertEqual(result["food_a"]["description"], "Banana, raw")
        self.assertEqual(result["food_b"]["description"], "Oranges, raw, navels")

    def test_normalize_api_data_types_supports_fndds_alias(self) -> None:
        self.assertEqual(normalize_api_data_types(["FNDDS", "Branded"]), ["Survey", "Branded"])

    def test_available_api_data_types_includes_experimental(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        self.assertIn("Experimental", repo.available_api_data_types())

    def test_get_food_source_metadata_includes_candidate_matches(self) -> None:
        repo = FoodRepository(api_client=FakeUSDAAPIClient())
        result = repo.get_food_source_metadata("orange", data_types=["Foundation"])
        self.assertGreaterEqual(len(result["candidate_matches"]), 3)
        self.assertEqual(result["candidate_matches"][0]["description"], "Oranges, raw, navels")


if __name__ == "__main__":
    unittest.main()
