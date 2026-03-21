"""Thin httpx wrapper around the FatSecret Platform REST API."""

from __future__ import annotations

import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

FS_TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
FS_BASE_URL = "https://platform.fatsecret.com/rest"


class FatSecretError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"FatSecret API error {status_code}: {message}")


class FatSecretClient:
    """Synchronous FatSecret API client with automatic OAuth2 token management."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or os.environ.get("FATSECRET_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("FATSECRET_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                FS_TOKEN_URL,
                data={"grant_type": "client_credentials", "scope": "basic"},
                auth=(self.client_id, self.client_secret),
            )
            if r.status_code == 401:
                raise FatSecretError(401, "Invalid FatSecret credentials — check FATSECRET_CLIENT_ID/SECRET")
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 86400)
            return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    def _handle_response(self, response: httpx.Response) -> dict:
        if response.status_code == 401:
            raise FatSecretError(401, "Unauthorized — token may have expired")
        if response.status_code == 404:
            raise FatSecretError(404, "Food not found")
        if response.status_code == 429:
            raise FatSecretError(429, "Rate limit exceeded (5 000 req/day)")
        response.raise_for_status()
        data = response.json()
        # FatSecret returns HTTP 200 even for API-level errors
        if "error" in data:
            err = data["error"]
            raise FatSecretError(
                err.get("code", 0),
                err.get("message", "Unknown FatSecret API error"),
            )
        return data

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------

    def search_foods(
        self,
        query: str,
        page_number: int = 0,
        max_results: int = 20,
    ) -> dict:
        """Search the FatSecret food database (v1 — free tier compatible).

        Returns food_description string per item:
        "Per 1 serving - Calories: 220kcal | Fat: 10.00g | Carbs: 31.00g | Protein: 3.00g"
        """
        params = {
            "method": "foods.search",
            "search_expression": query,
            "page_number": page_number,
            "max_results": min(max(1, max_results), 50),
            "format": "json",
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.get(FS_BASE_URL + "/server.api", params=params,
                           headers=self._headers())
            return self._handle_response(r)

    def get_food(self, food_id: str) -> dict:
        """Get full nutrition details for a FatSecret food by ID (v2 — free tier compatible)."""
        params = {
            "method": "food.get.v2",
            "food_id": food_id,
            "format": "json",
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.get(FS_BASE_URL + "/server.api", params=params,
                           headers=self._headers())
            return self._handle_response(r)
