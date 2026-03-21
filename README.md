# USDA FoodData MCP

This repo is an MCP server for the USDA FoodData Central API.

It is API-only:

- no local SQLite database
- no USDA dataset ingestion step
- no local Foundation-only mode

The server queries USDA live and exposes food search, nutrient lookup, comparison, and citation metadata through MCP tools.

Public MCP endpoint:

- `https://ethanmathias.duckdns.org/mcp`

## What It Does

This server lets LLMs and apps answer food questions using USDA FoodData Central instead of model memory.

Main use cases:

- search for foods
- get nutrient values
- compare foods by a nutrient
- return source metadata and citation details

For ambiguous food names like `banana` or `orange`, the MCP responses now include top candidate matches so the LLM can inspect multiple USDA results before committing to one interpretation.

## USDA API Coverage

This server supports these USDA API-facing data types:

- `Foundation`
- `Branded`
- `SR Legacy`
- `Survey` (`FNDDS` alias)
- `Experimental`

## Repo Layout

- `src/usda_mcp/repository.py`: API-backed query layer
- `src/usda_mcp/usda_api.py`: USDA API client and data-type normalization
- `src/usda_mcp/server.py`: stdio + HTTP MCP server
- `src/usda_mcp/demo.py`: API demo queries
- `tests/`: API and HTTP transport tests

## Tools Exposed By MCP

Primary tools:

- `search_foods`
- `get_food_nutrients`
- `compare_foods`
- `get_food_source_metadata`
- `list_available_data_types`

Additional explicit API tools:

- `search_foods_api`
- `get_food_nutrients_api`
- `compare_foods_api`
- `get_food_source_metadata_api`

Notes:

- the server is API-only, so all tools use live USDA data
- `list_foods_by_nutrient` is not implemented for global API-wide ranking in this build
- `search_foods` defaults to the top 5 results
- `get_food_nutrients`, `compare_foods`, and `get_food_source_metadata` include top candidate matches in their response payloads

## Setup

You need a USDA/data.gov API key.

Do not hardcode it in the repo.

Set it in the environment instead.

macOS / Linux:

```bash
export USDA_API_KEY="your-key"
```

Windows PowerShell:

```powershell
$env:USDA_API_KEY = "your-key"
```

If you ever pasted a real key into chat or source control, rotate it.

## Running The Demo

macOS / Linux:

```bash
PYTHONPATH=src python3 -m usda_mcp.demo
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m usda_mcp.demo
```

## Running The Server

### Local stdio MCP server

macOS / Linux:

```bash
PYTHONPATH=src python3 -m usda_mcp.server
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m usda_mcp.server
```

### HTTP MCP server

For local testing:

macOS / Linux:

```bash
PYTHONPATH=src python3 -m usda_mcp.server --transport http --host 127.0.0.1 --port 25565
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m usda_mcp.server --transport http --host 127.0.0.1 --port 25565
```

That exposes:

- health route: `http://127.0.0.1:25565/`
- MCP endpoint: `http://127.0.0.1:25565/mcp`

## HTTPS Deployment

ChatGPT connectors require a public HTTPS MCP URL.

This project is deployed with:

- Python MCP server on `127.0.0.1:25565`
- Caddy on public ports `80` and `443`
- public HTTPS endpoint at `https://ethanmathias.duckdns.org/mcp`

Example `Caddyfile`:

```caddy
ethanmathias.duckdns.org {
    reverse_proxy 127.0.0.1:25565
}
```

Run Caddy:

```powershell
caddy run --config Caddyfile
```

Required router/firewall setup:

- forward TCP `80`
- forward TCP `443`
- allow inbound Windows firewall rules for `80` and `443`

## ChatGPT Connector Setup

1. Enable developer mode in ChatGPT.
2. Go to `Settings -> Connectors -> Create`.
3. Use this connector URL:

```text
https://ethanmathias.duckdns.org/mcp
```

4. Start a new chat and attach the connector.

Good test prompts:

- `Use the FoodFacts connector only. Call list_available_data_types.`
- `Use the FoodFacts connector only. Call search_foods_api for banana with data type Foundation.`
- `Use the FoodFacts connector only. Call compare_foods_api to compare potassium in banana vs orange with data type Foundation.`

## Example API Queries

Python:

```python
from usda_mcp.repository import FoodRepository

with FoodRepository() as repo:
    print(repo.search_foods("cheddar cheese", data_types=["Branded"]))
    print(repo.get_food_nutrients("banana", data_types=["Foundation"]))
    print(repo.compare_foods("banana", "orange", "potassium", data_types=["Foundation"]))
```

Example MCP arguments:

```json
{
  "query": "cheddar cheese",
  "data_types": ["Branded"],
  "limit": 5
}
```

## Current Limitations

- `list_foods_by_nutrient` is not implemented for API-wide ranking
- short food names can be ambiguous, so the server uses ranking heuristics to prefer whole/raw foods over peppers, juices, and processed variants
- final results still depend on what the USDA API returns for a given query and data type

## Tests

macOS / Linux:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```
