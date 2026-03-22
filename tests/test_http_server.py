"""Integration tests for the HTTP transport layer (CORS + health check).

Starts the real uvicorn/FastMCP app on a random port in a background thread
so we can make actual HTTP requests against it.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.request
import urllib.error
from http.client import HTTPConnection

import pytest


# ---------------------------------------------------------------------------
# Helpers to start/stop the server in a background thread
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int, extra_origins: list[str] | None = None) -> threading.Event:
    """Start the HTTP app in a daemon thread. Returns a ready Event."""
    import uvicorn
    from food_facts_mcp.server import _build_http_app

    ready = threading.Event()
    app = _build_http_app(extra_origins or [])

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    # Patch startup to signal readiness
    original_startup = server.startup

    async def patched_startup(sockets=None):
        await original_startup(sockets)
        ready.set()

    server.startup = patched_startup

    def run():
        asyncio.run(server.serve())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return ready


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def server_url():
    port = _find_free_port()
    ready = _start_server(port)
    assert ready.wait(timeout=10), "HTTP server did not start in time"
    return f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _get(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        return resp.status, dict(resp.headers), resp.read()


def _post(url: str, body: dict, headers: dict | None = None) -> tuple[int, dict, bytes]:
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _options(base_url: str, path: str, origin: str) -> tuple[int, dict]:
    conn = HTTPConnection(base_url.removeprefix("http://"))
    conn.request(
        "OPTIONS", path,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    resp = conn.getresponse()
    return resp.status, dict(resp.getheaders())


def test_health_check(server_url):
    status, _, body = _get(server_url + "/")
    assert status == 200
    data = json.loads(body)
    assert data["status"] == "ok"
    assert data["name"] == "Food Facts MCP"
    assert "endpoint" in data


def test_cors_preflight(server_url):
    status, headers = _options(server_url, "/mcp", "https://chat.openai.com")
    # CORSMiddleware responds to OPTIONS with 200 and CORS headers
    acao = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
    assert acao in ("https://chat.openai.com", "*"), (
        f"Expected CORS header, got headers: {headers}"
    )


def test_cors_header_on_post(server_url):
    """A POST from an allowed origin should have CORS header in the response."""
    status, headers, _ = _post(
        server_url + "/mcp",
        body={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05",
                         "capabilities": {},
                         "clientInfo": {"name": "test", "version": "0"}}},
        headers={"Origin": "https://chat.openai.com"},
    )
    acao = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
    assert acao is not None, f"Missing CORS header. Response status={status}, headers={headers}"


def test_custom_origin_allowed_on_post():
    port = _find_free_port()
    ready = _start_server(port, ["https://hoohacks26ui.vercel.app"])
    assert ready.wait(timeout=10), "HTTP server did not start in time"

    status, headers, _ = _post(
        f"http://127.0.0.1:{port}/mcp",
        body={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05",
                         "capabilities": {},
                         "clientInfo": {"name": "test", "version": "0"}}},
        headers={"Origin": "https://hoohacks26ui.vercel.app"},
    )
    acao = headers.get("access-control-allow-origin") or headers.get("Access-Control-Allow-Origin")
    assert status == 200, f"Expected successful initialize for trusted origin, got {status}"
    assert acao == "https://hoohacks26ui.vercel.app"


def test_mcp_initialize(server_url):
    status, _, body = _post(
        server_url + "/mcp",
        body={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05",
                         "capabilities": {},
                         "clientInfo": {"name": "pytest", "version": "0"}}},
    )
    assert status == 200
    # FastMCP's streamable-http returns SSE; body may be an event-stream chunk
    # Just assert we got a non-empty response with no server error
    assert len(body) > 0
