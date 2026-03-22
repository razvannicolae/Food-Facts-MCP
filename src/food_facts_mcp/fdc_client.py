"""Thin httpx wrapper around the USDA FoodData Central REST API."""

from __future__ import annotations

import os
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

FDC_BASE_URL = "https://api.nal.usda.gov/fdc/v1"


class FDCError(Exception):
    """Raised when the FDC API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"FDC API error {status_code}: {message}")


class FDCClient:
    """Synchronous FDC API client.  Injects API key on every request."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("USDA_FDC_API_KEY", "DEMO_KEY")
        self.base_url = FDC_BASE_URL

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_response(self, response: httpx.Response) -> dict | list:
        if response.status_code == 400:
            raise FDCError(400, "Bad request — check your parameters")
        if response.status_code == 401:
            raise FDCError(401, "Unauthorized — invalid API key")
        if response.status_code == 404:
            raise FDCError(404, "Food not found")
        if response.status_code == 429:
            raise FDCError(429, "Rate limit exceeded (1 000 req/hr for registered keys)")
        response.raise_for_status()
        return response.json()

    def _api_params(self, **extra) -> dict:
        params: dict = {"api_key": self.api_key}
        params.update({k: v for k, v in extra.items() if v is not None})
        return params

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def search_foods(
        self,
        query: str,
        data_type: Optional[list[str]] = None,
        brand_owner: Optional[str] = None,
        page_size: int = 25,
        page_number: int = 1,
    ) -> dict:
        """POST /v1/foods/search"""
        body: dict = {
            "query": query,
            "pageSize": min(max(1, page_size), 200),
            "pageNumber": max(1, page_number),
        }
        if data_type:
            body["dataType"] = data_type
        if brand_owner:
            body["brandOwner"] = brand_owner

        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{self.base_url}/foods/search",
                params={"api_key": self.api_key},
                json=body,
            )
            return self._handle_response(r)

    def get_food(
        self,
        fdc_id: int,
        nutrients: Optional[list[int]] = None,
        format: Optional[str] = None,
    ) -> dict:
        """GET /v1/food/{fdcId}"""
        params = self._api_params(format=format)
        # httpx encodes list params as repeated keys, which the FDC API expects
        if nutrients:
            params["nutrients"] = nutrients

        with httpx.Client(timeout=30.0) as client:
            r = client.get(f"{self.base_url}/food/{fdc_id}", params=params)
            return self._handle_response(r)

    def get_multiple_foods(
        self,
        fdc_ids: list[int],
        nutrients: Optional[list[int]] = None,
        format: Optional[str] = None,
    ) -> list:
        """POST /v1/foods — up to 20 FDC IDs at once."""
        body: dict = {"fdcIds": fdc_ids[:20]}
        if nutrients:
            body["nutrients"] = nutrients
        if format:
            body["format"] = format

        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{self.base_url}/foods",
                params={"api_key": self.api_key},
                json=body,
            )
            return self._handle_response(r)

    def list_foods(
        self,
        data_type: Optional[list[str]] = None,
        page_size: int = 50,
        page_number: int = 1,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> list:
        """POST /v1/foods/list"""
        body: dict = {
            "pageSize": min(max(1, page_size), 200),
            "pageNumber": max(1, page_number),
        }
        if data_type:
            body["dataType"] = data_type
        if sort_by:
            body["sortBy"] = sort_by
        if sort_order:
            body["sortOrder"] = sort_order

        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{self.base_url}/foods/list",
                params={"api_key": self.api_key},
                json=body,
            )
            return self._handle_response(r)
