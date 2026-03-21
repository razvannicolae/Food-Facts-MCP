from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from usda_mcp.repository import FoodRepository


TOOLS = [
    {
        "name": "search_foods",
        "description": "Search USDA Foundation Foods by description.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Food name or phrase to search for."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_food_nutrients",
        "description": "Return core nutrient values for a USDA Foundation food.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_query": {"type": "string", "description": "Food description text or FDC ID."},
                "nutrients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional nutrient filters like protein, iron, or potassium.",
                },
            },
            "required": ["food_query"],
        },
    },
    {
        "name": "compare_foods",
        "description": "Compare a nutrient value between two USDA foods.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_a": {"type": "string"},
                "food_b": {"type": "string"},
                "nutrient": {"type": "string"},
            },
            "required": ["food_a", "food_b", "nutrient"],
        },
    },
    {
        "name": "list_foods_by_nutrient",
        "description": "Rank USDA foods by a given nutrient amount per 100g.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nutrient": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
            },
            "required": ["nutrient"],
        },
    },
    {
        "name": "get_food_source_metadata",
        "description": "Return source and citation metadata for a USDA Foundation food.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_query": {"type": "string"},
            },
            "required": ["food_query"],
        },
    },
]


def read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode("utf-8").split(":", 1)
        headers[key.strip().lower()] = value.strip()

    content_length = int(headers["content-length"])
    payload = sys.stdin.buffer.read(content_length)
    return json.loads(payload.decode("utf-8"))


def write_message(message: dict[str, Any]) -> None:
    encoded = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def success(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def handle_request(repo: FoodRepository, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        protocol_version = params.get("protocolVersion", "2024-11-05")
        return success(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "usda-foundation-mini", "version": "0.1.0"},
            },
        )

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return success(request_id, {})

    if method == "tools/list":
        return success(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {})
        try:
            if name == "search_foods":
                result = repo.search_foods(arguments["query"], int(arguments.get("limit", 10)))
            elif name == "get_food_nutrients":
                result = repo.get_food_nutrients(arguments["food_query"], arguments.get("nutrients"))
            elif name == "compare_foods":
                result = repo.compare_foods(
                    arguments["food_a"], arguments["food_b"], arguments["nutrient"]
                )
            elif name == "list_foods_by_nutrient":
                result = repo.list_foods_by_nutrient(
                    arguments["nutrient"], int(arguments.get("limit", 10))
                )
            elif name == "get_food_source_metadata":
                result = repo.get_food_source_metadata(arguments["food_query"])
            else:
                return error(request_id, -32601, f"Unknown tool '{name}'.")
        except Exception as exc:  # pragma: no cover - exercised via integration flow
            return success(
                request_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "structuredContent": {"error": str(exc)},
                    "isError": True,
                },
            )
        return success(request_id, tool_result(result))

    return error(request_id, -32601, f"Unknown method '{method}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a mini USDA Foundation Foods MCP server.")
    parser.add_argument("--db-path", type=Path, default=Path("data/derived/usda_foundation_mini.sqlite"))
    args = parser.parse_args()

    with FoodRepository(args.db_path) as repo:
        while True:
            request = read_message()
            if request is None:
                break
            response = handle_request(repo, request)
            if response is not None:
                write_message(response)


if __name__ == "__main__":
    main()
