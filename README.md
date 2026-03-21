# USDA Foundation Foods Mini MCP

This repo is a small, hackathon-ready version of your idea: it turns the USDA FoodData Central Foundation Foods download into a local SQLite database and exposes it through a minimal MCP server.

It is intentionally scoped as a mini build:

- `Foundation Foods` only, not the full USDA corpus
- Python standard library only
- SQLite-backed
- simple MCP tools for search, nutrient lookup, comparisons, and citation metadata

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

## Repo Layout

- `src/usda_mcp/builder.py`: ingests the USDA zip into SQLite
- `src/usda_mcp/repository.py`: query layer for foods and nutrients
- `src/usda_mcp/server.py`: minimal stdio MCP server
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

## MCP Server

Run the stdio MCP server with:

```bash
PYTHONPATH=src python3 -m usda_mcp.server
```

If you prefer package scripts:

```bash
python3 -m pip install -e .
usda-mini-build
usda-mini-demo
usda-mini-server
```

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
