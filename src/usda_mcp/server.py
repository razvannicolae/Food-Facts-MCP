from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from usda_mcp.repository import FoodRepository


SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-11-25"}
DEFAULT_PROTOCOL_VERSION = "2025-11-25"

DEFAULT_ALLOWED_ORIGIN_HOSTS = {
    "localhost",
    "127.0.0.1",
    "chat.openai.com",
    "chatgpt.com",
    "www.chatgpt.com",
}

TOOLS = [
    {
        "name": "search_foods",
        "description": "Search USDA foods by description. Use source='api' for Branded, SR Legacy, or Survey/FNDDS data. If data_types is provided, the server will prefer the live USDA API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Food name or phrase to search for."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                "source": {
                    "type": "string",
                    "enum": ["local", "api"],
                    "default": "local",
                    "description": "Use the local SQLite subset or the live USDA API.",
                },
                "data_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional USDA API data types like Branded, Foundation, SR Legacy, or Survey (FNDDS).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_food_nutrients",
        "description": "Return core nutrient values for a USDA food. Use source='api' for Branded, SR Legacy, or Survey/FNDDS data. If data_types is provided, the server will prefer the live USDA API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_query": {"type": "string", "description": "Food description text or FDC ID."},
                "nutrients": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional nutrient filters like protein, iron, or potassium.",
                },
                "source": {
                    "type": "string",
                    "enum": ["local", "api"],
                    "default": "local",
                    "description": "Use the local SQLite subset or the live USDA API.",
                },
                "data_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional USDA API data type filters when source=api.",
                },
            },
            "required": ["food_query"],
        },
    },
    {
        "name": "compare_foods",
        "description": "Compare a nutrient value between two USDA foods. Use source='api' for Branded, SR Legacy, or Survey/FNDDS data. If data_types is provided, the server will prefer the live USDA API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_a": {"type": "string"},
                "food_b": {"type": "string"},
                "nutrient": {"type": "string"},
                "source": {
                    "type": "string",
                    "enum": ["local", "api"],
                    "default": "local",
                    "description": "Use the local SQLite subset or the live USDA API.",
                },
                "data_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional USDA API data type filters when source=api.",
                },
            },
            "required": ["food_a", "food_b", "nutrient"],
        },
    },
    {
        "name": "list_foods_by_nutrient",
        "description": "Rank foods in the local Foundation subset by a given nutrient amount per 100g.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nutrient": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10},
                "source": {
                    "type": "string",
                    "enum": ["local", "api"],
                    "default": "local",
                    "description": "API mode is not supported for global ranking in this mini build.",
                },
            },
            "required": ["nutrient"],
        },
    },
    {
        "name": "get_food_source_metadata",
        "description": "Return source and citation metadata for a USDA food. Use source='api' for Branded, SR Legacy, or Survey/FNDDS data. If data_types is provided, the server will prefer the live USDA API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "food_query": {"type": "string"},
                "source": {
                    "type": "string",
                    "enum": ["local", "api"],
                    "default": "local",
                    "description": "Use the local SQLite subset or the live USDA API.",
                },
                "data_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional USDA API data type filters when source=api.",
                },
            },
            "required": ["food_query"],
        },
    },
]


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


@dataclass
class MCPApplication:
    db_path: Path
    endpoint: str = "/mcp"
    allowed_origin_hosts: set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_ORIGIN_HOSTS))
    sessions: dict[str, str] = field(default_factory=dict)

    def _open_repo(self) -> FoodRepository:
        return FoodRepository(self.db_path)

    def handle_jsonrpc(
        self,
        request: dict[str, Any],
        *,
        session_id: str | None = None,
        protocol_version: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})
        negotiated_protocol = self._negotiate_protocol(protocol_version, params)

        if method == "initialize":
            new_session_id = uuid4().hex
            self.sessions[new_session_id] = negotiated_protocol
            return (
                success(
                    request_id,
                    {
                        "protocolVersion": negotiated_protocol,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "usda-foundation-mini", "version": "0.2.0"},
                    },
                ),
                new_session_id,
            )

        if method == "notifications/initialized":
            return None, session_id

        if method == "ping":
            return success(request_id, {}), session_id

        if method == "tools/list":
            return success(request_id, {"tools": TOOLS}), session_id

        if method == "tools/call":
            name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                with self._open_repo() as repo:
                    result = self._invoke_tool(repo, name, arguments)
            except Exception as exc:  # pragma: no cover - exercised via integration flow
                return (
                    success(
                        request_id,
                        {
                            "content": [{"type": "text", "text": str(exc)}],
                            "structuredContent": {"error": str(exc)},
                            "isError": True,
                        },
                    ),
                    session_id,
                )
            return success(request_id, tool_result(result)), session_id

        if request_id is None:
            return None, session_id

        return error(request_id, -32601, f"Unknown method '{method}'."), session_id

    def _invoke_tool(self, repo: FoodRepository, name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        source = self._pick_source(repo, arguments)
        data_types = arguments.get("data_types")
        if name == "search_foods":
            return repo.search_foods(
                arguments["query"],
                int(arguments.get("limit", 10)),
                source=source,
                data_types=data_types,
            )
        if name == "get_food_nutrients":
            return repo.get_food_nutrients(
                arguments["food_query"],
                arguments.get("nutrients"),
                source=source,
                data_types=data_types,
            )
        if name == "compare_foods":
            return repo.compare_foods(
                arguments["food_a"],
                arguments["food_b"],
                arguments["nutrient"],
                source=source,
                data_types=data_types,
            )
        if name == "list_foods_by_nutrient":
            return repo.list_foods_by_nutrient(
                arguments["nutrient"],
                int(arguments.get("limit", 10)),
                source=source,
            )
        if name == "get_food_source_metadata":
            return repo.get_food_source_metadata(
                arguments["food_query"],
                source=source,
                data_types=data_types,
            )
        raise ValueError(f"Unknown tool '{name}'.")

    @staticmethod
    def _pick_source(repo: FoodRepository, arguments: dict[str, Any]) -> str:
        requested = arguments.get("source")
        if requested in {"local", "api"}:
            return requested
        if arguments.get("data_types"):
            return "api"
        if not repo.db_path.exists() and os.environ.get("USDA_API_KEY"):
            return "api"
        return "local"

    def validate_session(self, session_id: str | None, method: str | None) -> tuple[bool, str | None]:
        if method == "initialize":
            return True, None
        if session_id is None:
            return True, None
        if session_id in self.sessions:
            return True, self.sessions[session_id]
        return False, None

    def delete_session(self, session_id: str | None) -> bool:
        if session_id and session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def is_origin_allowed(self, origin: str | None) -> bool:
        if not origin:
            return True
        parsed = urlparse(origin)
        if not parsed.scheme or not parsed.hostname:
            return False
        return parsed.hostname in self.allowed_origin_hosts

    @staticmethod
    def _negotiate_protocol(protocol_header: str | None, params: dict[str, Any]) -> str:
        candidate = params.get("protocolVersion") or protocol_header or DEFAULT_PROTOCOL_VERSION
        if candidate not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(
                f"Unsupported MCP protocol version '{candidate}'. "
                f"Supported versions: {sorted(SUPPORTED_PROTOCOL_VERSIONS)}"
            )
        return candidate


def create_http_handler(app: MCPApplication) -> type[BaseHTTPRequestHandler]:
    class MCPRequestHandler(BaseHTTPRequestHandler):
        server_version = "USDAFoundationMiniMCP/0.2.0"

        def do_OPTIONS(self) -> None:  # noqa: N802
            if self.path != app.endpoint:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not app.is_origin_allowed(self.headers.get("Origin")):
                self._send_forbidden_origin()
                return
            self.send_response(HTTPStatus.NO_CONTENT)
            self._send_cors_headers()
            self.send_header("Allow", "POST, GET, DELETE, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/":
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "name": "usda-foundation-mini",
                        "status": "ok",
                        "endpoint": app.endpoint,
                        "transport": "streamable-http-json",
                    },
                )
                return
            if self.path != app.endpoint:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not app.is_origin_allowed(self.headers.get("Origin")):
                self._send_forbidden_origin()
                return
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self._send_cors_headers()
            self.send_header("Allow", "POST, OPTIONS, DELETE")
            self.end_headers()

        def do_DELETE(self) -> None:  # noqa: N802
            if self.path != app.endpoint:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if not app.is_origin_allowed(self.headers.get("Origin")):
                self._send_forbidden_origin()
                return
            deleted = app.delete_session(self.headers.get("MCP-Session-Id"))
            status = HTTPStatus.NO_CONTENT if deleted else HTTPStatus.METHOD_NOT_ALLOWED
            self.send_response(status)
            self._send_cors_headers()
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802
            if self.path != app.endpoint:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            origin = self.headers.get("Origin")
            if not app.is_origin_allowed(origin):
                self._send_forbidden_origin()
                return
            if not self._accepts_mcp_post():
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    error(None, -32000, "Accept header must support application/json."),
                )
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            try:
                request = json.loads(self.rfile.read(content_length).decode("utf-8"))
            except json.JSONDecodeError:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    error(None, -32700, "Invalid JSON in request body."),
                )
                return

            method = request.get("method")
            session_id = self.headers.get("MCP-Session-Id")
            is_valid_session, negotiated_protocol = app.validate_session(session_id, method)
            if not is_valid_session:
                self._send_json(HTTPStatus.NOT_FOUND, error(request.get("id"), -32001, "Unknown session."))
                return

            protocol_header = self.headers.get("MCP-Protocol-Version") or negotiated_protocol
            try:
                response, maybe_new_session_id = app.handle_jsonrpc(
                    request,
                    session_id=session_id,
                    protocol_version=protocol_header,
                )
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, error(request.get("id"), -32002, str(exc)))
                return

            final_session_id = maybe_new_session_id or session_id
            if response is None:
                self.send_response(HTTPStatus.ACCEPTED)
                self._send_cors_headers()
                self._send_mcp_headers(final_session_id, protocol_header or DEFAULT_PROTOCOL_VERSION)
                self.end_headers()
                return

            self._send_json(
                HTTPStatus.OK,
                response,
                session_id=final_session_id,
                protocol_version=self._response_protocol_version(response, protocol_header),
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            sys.stderr.write(f"{self.address_string()} - {format % args}\n")

        def _accepts_mcp_post(self) -> bool:
            accept = self.headers.get("Accept", "")
            if not accept:
                return False
            accepted_types = {item.split(";")[0].strip() for item in accept.split(",")}
            return "application/json" in accepted_types or "*/*" in accepted_types

        def _response_protocol_version(
            self, response: dict[str, Any], fallback: str | None
        ) -> str:
            result = response.get("result")
            if isinstance(result, dict) and "protocolVersion" in result:
                return result["protocolVersion"]
            if fallback in SUPPORTED_PROTOCOL_VERSIONS:
                return fallback
            return DEFAULT_PROTOCOL_VERSION

        def _send_forbidden_origin(self) -> None:
            self._send_json(
                HTTPStatus.FORBIDDEN,
                error(None, -32003, "Origin header is not allowed for this MCP server."),
            )

        def _send_json(
            self,
            status: HTTPStatus,
            payload: dict[str, Any],
            *,
            session_id: str | None = None,
            protocol_version: str | None = None,
        ) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self._send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self._send_mcp_headers(session_id, protocol_version)
            self.end_headers()
            self.wfile.write(encoded)

        def _send_mcp_headers(self, session_id: str | None, protocol_version: str | None) -> None:
            if session_id:
                self.send_header("MCP-Session-Id", session_id)
            if protocol_version:
                self.send_header("MCP-Protocol-Version", protocol_version)

        def _send_cors_headers(self) -> None:
            origin = self.headers.get("Origin")
            if origin and app.is_origin_allowed(origin):
                self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, GET, DELETE, OPTIONS")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Accept, Content-Type, MCP-Protocol-Version, MCP-Session-Id, Last-Event-ID",
            )
            self.send_header("Vary", "Origin")

    return MCPRequestHandler


def run_stdio_server(app: MCPApplication) -> None:
    while True:
        request = read_message()
        if request is None:
            break
        try:
            response, _ = app.handle_jsonrpc(request)
        except ValueError as exc:
            request_id = request.get("id") if isinstance(request, dict) else None
            response = error(request_id, -32002, str(exc))
        if response is not None:
            write_message(response)


def create_http_server(
    app: MCPApplication,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> HTTPServer:
    handler = create_http_handler(app)
    return HTTPServer((host, port), handler)


def run_http_server(app: MCPApplication, host: str, port: int) -> None:
    server = create_http_server(app, host=host, port=port)
    print(f"Serving USDA MCP over HTTP at http://{host}:{port}{app.endpoint}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a mini USDA Foundation Foods MCP server.")
    parser.add_argument("--db-path", type=Path, default=Path("data/derived/usda_foundation_mini.sqlite"))
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="Run as a local stdio MCP server or a remote HTTP MCP endpoint.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host to bind when using --transport http.")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port to bind when using --transport http.")
    parser.add_argument(
        "--endpoint",
        default="/mcp",
        help="HTTP MCP endpoint path when using --transport http.",
    )
    parser.add_argument(
        "--allow-origin-host",
        action="append",
        default=[],
        help="Additional allowed Origin hostnames for HTTP mode, e.g. your tunnel domain.",
    )
    args = parser.parse_args()

    allowed_origins = set(DEFAULT_ALLOWED_ORIGIN_HOSTS)
    allowed_origins.update(args.allow_origin_host)
    app = MCPApplication(db_path=args.db_path, endpoint=args.endpoint, allowed_origin_hosts=allowed_origins)

    if args.transport == "http":
        run_http_server(app, host=args.host, port=args.port)
        return

    run_stdio_server(app)


if __name__ == "__main__":
    main()
