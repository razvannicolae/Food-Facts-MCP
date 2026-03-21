from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
API_DATA_TYPE_ALIASES = {
    "foundation": "Foundation",
    "foundation foods": "Foundation",
    "branded": "Branded",
    "branded foods": "Branded",
    "sr legacy": "SR Legacy",
    "standard reference": "SR Legacy",
    "standard reference legacy": "SR Legacy",
    "survey": "Survey",
    "fndds": "Survey",
    "food and nutrient database for dietary studies": "Survey",
    "experimental": "Experimental",
    "experimental foods": "Experimental",
}
SUPPORTED_API_DATA_TYPES = ["Foundation", "Branded", "SR Legacy", "Survey", "Experimental"]


@dataclass
class USDAAPIClient:
    api_key: str
    base_url: str = DEFAULT_BASE_URL

    @classmethod
    def from_env(cls) -> "USDAAPIClient":
        api_key = os.environ.get("USDA_API_KEY")
        if not api_key:
            raise ValueError(
                "USDA_API_KEY is not set. Export it in your shell instead of hardcoding the key."
            )
        return cls(api_key=api_key)

    def search_foods(
        self,
        query: str,
        *,
        page_size: int = 10,
        page_number: int = 1,
        data_types: list[str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "pageSize": page_size,
            "pageNumber": page_number,
        }
        if data_types:
            payload["dataType"] = normalize_api_data_types(data_types)
        return self._request_json("POST", "/foods/search", payload=payload)

    def get_food_details(self, fdc_id: int) -> dict[str, Any]:
        return self._request_json("GET", f"/food/{fdc_id}")

    def search_nutrient_names(self, query: str) -> list[str]:
        response = self.search_foods(query, page_size=25)
        nutrient_names: set[str] = set()
        for food in response.get("foods", []):
            for item in food.get("foodNutrients", []):
                name = item.get("nutrientName") or item.get("name")
                if name:
                    nutrient_names.add(name)
        return sorted(nutrient_names)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        query_string = urlencode({"api_key": self.api_key})
        url = f"{self.base_url}{path}?{query_string}"
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")

        request = Request(url, data=body, headers=headers, method=method)
        with urlopen(request) as response:  # noqa: S310 - official USDA API endpoint
            return json.loads(response.read().decode("utf-8"))


def normalize_api_data_types(data_types: list[str] | None) -> list[str] | None:
    if not data_types:
        return None
    normalized = []
    for item in data_types:
        key = item.strip().lower()
        value = API_DATA_TYPE_ALIASES.get(key)
        if value is None:
            allowed = ", ".join(SUPPORTED_API_DATA_TYPES)
            raise ValueError(
                f"Unsupported USDA API data type '{item}'. Supported values: {allowed}."
            )
        if value not in normalized:
            normalized.append(value)
    return normalized
