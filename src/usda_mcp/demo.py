from __future__ import annotations

import json

from usda_mcp.repository import FoodRepository


def main() -> None:
    with FoodRepository() as repo:
        demo = {
            "search_foods_api('banana')": repo.search_foods("banana", limit=3, source="api"),
            "get_food_nutrients_api('salmon')": repo.get_food_nutrients(
                "salmon", source="api", data_types=["Foundation"]
            ),
            "compare_foods_api('banana', 'orange', 'potassium')": repo.compare_foods(
                "banana",
                "orange",
                "potassium",
                source="api",
                data_types=["Foundation"],
            ),
            "list_available_data_types()": {"api_supported_data_types": repo.available_api_data_types()},
        }
    print(json.dumps(demo, indent=2))


if __name__ == "__main__":
    main()
