from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from usda_mcp.builder import build_database
from usda_mcp.repository import FoodRepository


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "data/raw/FoodData_Central_foundation_food_json_2025-12-18.zip"


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "mini.sqlite"
        build_database(ZIP_PATH, cls.db_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_search_foods_returns_matches(self) -> None:
        with FoodRepository(self.db_path) as repo:
            result = repo.search_foods("banana", limit=3)
        self.assertGreaterEqual(len(result["results"]), 1)
        self.assertIn("Bananas", result["results"][0]["description"])

    def test_compare_foods_returns_expected_shape(self) -> None:
        with FoodRepository(self.db_path) as repo:
            result = repo.compare_foods("banana", "avocado", "potassium")
        self.assertEqual(result["nutrient"], "Potassium, K")
        self.assertIn("food_a_value", result)
        self.assertIn("food_b_value", result)


if __name__ == "__main__":
    unittest.main()
