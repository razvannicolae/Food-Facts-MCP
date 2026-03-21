# USDA FoodData Central MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives AI agents real-time access to the [USDA FoodData Central](https://fdc.nal.usda.gov) database. Search any food, retrieve full nutrient tables, compare foods side-by-side, and get properly formatted citations — all backed by the live FDC REST API.

## Features

**8 Tools**
| Tool | What it does |
|------|-------------|
| `search_foods` | Keyword search with optional data type / brand filter |
| `get_food` | Full food details by FDC ID |
| `get_multiple_foods` | Batch lookup — up to 20 IDs at once |
| `get_food_nutrients` | Human-readable nutrient table with citation |
| `compare_foods` | Side-by-side nutrient comparison of two foods |
| `list_foods` | Browse all foods with pagination |
| `list_foods_by_nutrient` | Top N foods ranked by a given nutrient |
| `get_food_citation` | Citation-ready metadata (APA + MLA) |

Every tool response includes a `citation` block:
```json
{
  "source": "USDA FoodData Central",
  "dataset": "Foundation",
  "fdcId": 747448,
  "url": "https://fdc.nal.usda.gov/food-details/747448/nutrients",
  "publicationDate": "2019-04-01"
}
```

**4 Resources** (URI-addressed read-only data)
- `usda://food/{fdcId}` — live food item JSON
- `usda://nutrients/reference` — all standard USDA nutrient numbers, names, and units
- `usda://datasets/info` — descriptions of Foundation, SR Legacy, Branded, Survey datasets
- `usda://server/metadata` — version, rate limits, API key status

**4 Prompt Templates**
- `analyze_food_nutrition` — structured nutrition analysis with citations
- `compare_foods_for_goal` — goal-oriented food comparison
- `dietary_advice` — evidence-based dietary advice anchored to FDC data
- `meal_nutrition_summary` — combined nutrition breakdown for a full meal

## Setup

### 1. Get a free API key

Register at [api.data.gov/signup](https://api.data.gov/signup/) to get a key with 1 000 req/hr (vs. 30/hr for the demo key).

### 2. Install

```bash
pip install -e .
```

### 3. Configure your API key

```bash
cp .env.example .env
# Edit .env and set USDA_FDC_API_KEY=your_key_here
```

## Usage

### With Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "usda-fdc": {
      "command": "/Users/razvannicolae/.pyenv/versions/3.10.18/bin/python",
      "args": ["-m", "usda_mcp.server"],
      "cwd": "/Users/razvannicolae/Code/HooHacks2026",
      "env": {
        "USDA_FDC_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop — you'll see the server listed under the MCP tools icon.

### With Claude Code (this CLI)

Add to your project's `.claude/settings.json` or run:

```bash
claude mcp add usda-fdc -- python -m usda_mcp.server
```

Or manually in `.claude/settings.json`:
```json
{
  "mcpServers": {
    "usda-fdc": {
      "command": "python",
      "args": ["-m", "usda_mcp.server"],
      "cwd": "/Users/razvannicolae/Code/HooHacks2026",
      "env": {
        "USDA_FDC_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Standalone HTTP server

```bash
usda-mcp-server --transport streamable-http --port 8000
# or
python -m usda_mcp.server --transport streamable-http --port 8000
```

## Data Types

| Type | Coverage | Best for |
|------|----------|----------|
| **Foundation** | Core commodity foods (raw ingredients) | Research — most precise analytical data |
| **SR Legacy** | ~8 600 foods (raw, processed, prepared) | General nutrition analysis |
| **Branded** | Commercial products (packaged, fast food) | Specific product label verification |
| **Survey (FNDDS)** | Foods as consumed in NHANES surveys | Epidemiological / population studies |

## Development

```bash
pip install -e .
python -m pytest tests/ -v   # 25 unit tests, all mocked
```

## Sources

- [USDA FDC API Guide](https://fdc.nal.usda.gov/api-guide/)
- [FDC OpenAPI Spec](https://fdc.nal.usda.gov/api-spec/fdc_api.html)
