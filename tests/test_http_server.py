from __future__ import annotations

import json
import threading
import unittest
import urllib.request

from usda_mcp.repository import FoodRepository
from usda_mcp.server import MCPApplication, create_http_server
from tests.test_api_repository import FakeUSDAAPIClient


class HttpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = MCPApplication(repo_factory=lambda: FoodRepository(api_client=FakeUSDAAPIClient()))
        cls.server = create_http_server(cls.app, host="127.0.0.1", port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_initialize_and_tool_list_over_http(self) -> None:
        initialize_request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/mcp",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2025-11-25"},
                }
            ).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(initialize_request) as response:
            payload = json.loads(response.read().decode("utf-8"))
            session_id = response.headers.get("MCP-Session-Id")

        self.assertEqual(payload["result"]["protocolVersion"], "2025-11-25")
        self.assertTrue(session_id)

        tools_request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/mcp",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                }
            ).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Session-Id": session_id,
                "MCP-Protocol-Version": "2025-11-25",
            },
        )
        with urllib.request.urlopen(tools_request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payload["result"]["tools"][0]["name"], "search_foods")


if __name__ == "__main__":
    unittest.main()
