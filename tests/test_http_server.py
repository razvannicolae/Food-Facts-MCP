from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from usda_mcp.builder import build_database
from usda_mcp.server import MCPApplication, create_http_server


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "data/raw/FoodData_Central_foundation_food_json_2025-12-18.zip"


class HttpServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "mini.sqlite"
        build_database(ZIP_PATH, cls.db_path)

        cls.app = MCPApplication(db_path=cls.db_path)
        cls.server = create_http_server(cls.app, host="127.0.0.1", port=0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp_dir.cleanup()

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
