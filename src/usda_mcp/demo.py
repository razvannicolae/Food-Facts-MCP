from __future__ import annotations

import json

from usda_mcp.repository import FoodRepository


def main() -> None:
    with FoodRepository() as repo:
        demo = {
            "search_foods('banana')": repo.search_foods("banana", limit=3),
            "get_food_nutrients('salmon')": repo.get_food_nutrients("salmon"),
            "compare_foods('banana', 'avocado', 'potassium')": repo.compare_foods(
                "banana", "avocado", "potassium"
            ),
            "list_foods_by_nutrient('protein')": repo.list_foods_by_nutrient("protein", limit=5),
        }
    print(json.dumps(demo, indent=2))


if __name__ == "__main__":
    main()
