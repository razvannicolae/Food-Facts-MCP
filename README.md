# USDA Foundation Foods Mini MCP

This repo is a small, hackathon-ready version of your idea: it turns the USDA FoodData Central Foundation Foods download into a local SQLite database and exposes it through a minimal MCP server.

It is intentionally scoped as a mini build:

- `Foundation Foods` only, not the full USDA corpus
- Python standard library only
- SQLite-backed
- simple MCP tools for search, nutrient lookup, comparisons, and citation metadata
- optional live USDA API support for Branded, SR Legacy, FNDDS, and other API-exposed data types

## What It Does

The project takes the USDA Foundation Foods JSON archive and builds a local database with:

- food descriptions
- nutrient values per 100 g
- portion metadata
- source and release metadata

Then it exposes that data through these MCP tools:

- `search_foods`
- `get_food_nutrients`
- `compare_foods`
- `list_foods_by_nutrient`
- `get_food_source_metadata`

The first four work against the local Foundation subset by default. `search_foods`, `get_food_nutrients`, `compare_foods`, and `get_food_source_metadata` can also use the live USDA API by passing `source="api"` and setting `USDA_API_KEY`.

## Repo Layout

- `src/usda_mcp/builder.py`: ingests the USDA zip into SQLite
- `src/usda_mcp/repository.py`: query layer for foods and nutrients
- `src/usda_mcp/server.py`: stdio and HTTP MCP server
- `src/usda_mcp/usda_api.py`: live USDA API client
- `src/usda_mcp/demo.py`: prints a few sample queries
- `tests/test_repository.py`: basic integration tests

## Dataset

This mini version is built around the USDA FoodData Central Foundation Foods JSON release:

- source: `https://fdc.nal.usda.gov/download-datasets/`
- archive used: `FoodData_Central_foundation_food_json_2025-12-18.zip`

The raw download is ignored in git via `.gitignore`, but if you place the USDA zip at:

`data/raw/FoodData_Central_foundation_food_json_2025-12-18.zip`

the build script will pick it up automatically.

## Quickstart

### 1. Create the database

```bash
PYTHONPATH=src python3 -m usda_mcp.builder
```

That writes:

`data/derived/usda_foundation_mini.sqlite`

### 2. Run the demo queries

```bash
PYTHONPATH=src python3 -m usda_mcp.demo
```

### 3. Run the tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Live USDA API Mode

This repo can also query the live USDA FoodData Central API instead of only the local Foundation subset.

Important:

- do not hardcode your USDA/data.gov API key in source code
- set it in the environment instead
- if you have pasted a real key into chat, docs, or a repo, rotate it

### Set the API key

macOS / Linux:

```bash
export USDA_API_KEY="your-real-key-here"
```

Windows PowerShell:

```powershell
$env:USDA_API_KEY = "your-real-key-here"
```

### Example live queries

Python:

```python
from usda_mcp.repository import FoodRepository

with FoodRepository() as repo:
    print(repo.search_foods("cheddar cheese", source="api", data_types=["Branded", "Foundation"]))
    print(repo.get_food_nutrients("cheddar cheese", source="api", data_types=["Branded"]))
```

In MCP calls, you can pass:

- `source: "api"`
- `data_types: ["Branded"]` or `["Foundation", "SR Legacy"]`

The API-facing data types supported by this server are:

- `Foundation`
- `Branded`
- `SR Legacy`
- `Survey` (this is the USDA API name for `FNDDS`)
- `Experimental`

Example tool arguments for `search_foods`:

```json
{
  "query": "cheddar cheese",
  "source": "api",
  "data_types": ["Branded", "Foundation"],
  "limit": 5
}
```

To make ChatGPT prefer the live API path, you can also use the explicit API-only tools:

- `search_foods_api`
- `get_food_nutrients_api`
- `compare_foods_api`
- `get_food_source_metadata_api`
- `list_available_data_types`

### Current API-backed scope

Supported in API mode:

- `search_foods`
- `get_food_nutrients`
- `compare_foods`
- `get_food_source_metadata`

Still local-only in this mini build:

- `list_foods_by_nutrient`

That last operation needs broader pagination and ranking logic to be accurate across the entire USDA API corpus.

## MCP Server

Run the local stdio MCP server with:

```bash
PYTHONPATH=src python3 -m usda_mcp.server
```

Run the HTTP MCP endpoint with:

```bash
PYTHONPATH=src python3 -m usda_mcp.server --transport http --host 127.0.0.1 --port 8000
```

That exposes:

`http://127.0.0.1:8000/mcp`

There is also a small health route at:

`http://127.0.0.1:8000/`

If you prefer package scripts:

```bash
python3 -m pip install -e .
usda-mini-build
usda-mini-demo
usda-mini-server
```

## Expose It Publicly For ChatGPT

ChatGPT Apps expects a public HTTPS MCP URL, so for local development you can tunnel the local HTTP server.

### Option 1: `ngrok`

Start the HTTP MCP server:

```bash
PYTHONPATH=src python3 -m usda_mcp.server --transport http --host 127.0.0.1 --port 8000 --allow-origin-host your-ngrok-host.ngrok-free.app
```

In another terminal:

```bash
ngrok http 8000
```

Use the HTTPS forwarding URL from `ngrok`, and point ChatGPT to:

`https://your-ngrok-host.ngrok-free.app/mcp`

### Option 2: `cloudflared`

Start the HTTP MCP server:

```bash
PYTHONPATH=src python3 -m usda_mcp.server --transport http --host 127.0.0.1 --port 8000 --allow-origin-host your-tunnel-host.trycloudflare.com
```

In another terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Use the HTTPS tunnel URL and append `/mcp`.

### Important note

The server validates the `Origin` header in HTTP mode. If your public tunnel uses a host that is not already allowed, add it with:

```bash
--allow-origin-host your-public-hostname
```

The default allowlist already includes:

- `localhost`
- `127.0.0.1`
- `chat.openai.com`
- `chatgpt.com`
- `www.chatgpt.com`

## Example Use Cases

- “How much protein is in salmon?”
- “Compare potassium in banana vs avocado.”
- “Which foods are highest in iron?”
- “Show the USDA citation metadata for spinach.”

## Why This Is A Good Hackathon MVP

This version proves the core idea without boiling the ocean:

- uses a real USDA download
- grounds answers in structured nutrient data
- returns citation metadata instead of unsupported guesses
- exposes the data in an MCP-friendly way

The next step after the hackathon would be adding more USDA data types like Branded Foods and FNDDS, stronger fuzzy search, and richer citations.
