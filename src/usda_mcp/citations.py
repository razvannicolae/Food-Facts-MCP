"""Shared citation-formatting utilities for all USDA FDC tools."""

from __future__ import annotations

from datetime import date
from typing import Optional


def build_citation(
    fdc_id: int,
    description: str,
    data_type: str,
    publication_date: Optional[str] = None,
    brand_owner: Optional[str] = None,
    ndb_number: Optional[str | int] = None,
) -> dict:
    """Return the standard citation block included in every tool response."""
    return {
        "source": "USDA FoodData Central",
        "dataset": data_type,
        "fdcId": fdc_id,
        "description": description,
        "url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
        "publicationDate": publication_date,
        "brandOwner": brand_owner,
        "ndbNumber": ndb_number,
        "accessedDate": date.today().isoformat(),
    }


def citation_from_food(food: dict) -> dict:
    """Build a citation dict from a raw FDC food object."""
    return build_citation(
        fdc_id=food.get("fdcId"),
        description=food.get("description", ""),
        data_type=food.get("dataType", ""),
        publication_date=food.get("publicationDate") or food.get("modifiedDate"),
        brand_owner=food.get("brandOwner"),
        ndb_number=food.get("ndbNumber"),
    )


def format_apa_citation(food: dict) -> str:
    """Return an APA-style citation string for a FDC food record."""
    fdc_id = food.get("fdcId")
    description = food.get("description", "Unknown food")
    data_type = food.get("dataType", "")
    pub_date = food.get("publicationDate") or food.get("modifiedDate") or "n.d."
    url = f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients"

    return (
        f"U.S. Department of Agriculture, Agricultural Research Service. "
        f"({pub_date}). {description} [FDC ID: {fdc_id}]. "
        f"FoodData Central, {data_type} dataset. {url}"
    )


def format_mla_citation(food: dict) -> str:
    """Return an MLA-style citation string for a FDC food record."""
    fdc_id = food.get("fdcId")
    description = food.get("description", "Unknown food")
    data_type = food.get("dataType", "")
    pub_date = food.get("publicationDate") or food.get("modifiedDate") or "n.d."
    url = f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients"

    return (
        f'United States Department of Agriculture, Agricultural Research Service. '
        f'"{description}." FoodData Central, {data_type} dataset, {pub_date}. '
        f"FDC ID {fdc_id}. {url}."
    )
