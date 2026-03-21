# Food Facts MCP Server

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
- `food://fdc/{fdcId}` — live food item JSON
- `food://nutrients/reference` — all standard USDA nutrient numbers, names, and units
- `food://sources/info` — descriptions of Foundation, SR Legacy, Branded, Survey datasets
- `food://server/metadata` — version, rate limits, API key status

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

### With Claude Desktop (stdio)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "food-facts": {
      "command": "python",
      "args": ["-m", "food_facts_mcp.server"],
      "cwd": "/path/to/HooHacks2026",
      "env": {
        "USDA_FDC_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop — you'll see the server listed under the MCP tools icon.

### Standalone HTTP server (local)

```bash
food-facts-server --transport streamable-http --port 8000
```

The MCP endpoint is at `http://127.0.0.1:8000/mcp`. A health check is available at `http://127.0.0.1:8000/`.

## Deployment

### Public HTTPS with Caddy + DuckDNS

This mirrors ethan's deployment setup. Caddy handles TLS automatically; DuckDNS provides a free public domain.

**1. Register a free domain at [duckdns.org](https://www.duckdns.org)**

**2. Start the MCP server (binds to localhost only — Caddy proxies inbound)**

```bash
USDA_FDC_API_KEY=your_key food-facts-server --transport streamable-http --host 127.0.0.1 --port 8000
```

**3. Install [Caddy](https://caddyserver.com/docs/install) and create a `Caddyfile`**

```
yourdomain.duckdns.org {
    reverse_proxy 127.0.0.1:8000
}
```

**4. Run Caddy**

```bash
caddy run --config Caddyfile
```

Caddy automatically obtains a Let's Encrypt certificate. Forward ports 80 and 443 to the machine in your router if running at home.

**5. MCP endpoint is now public at**

```
https://yourdomain.duckdns.org/mcp
```

### ChatGPT connector

In ChatGPT settings → Connectors, point to:

```
https://yourdomain.duckdns.org/mcp
```

### Extra allowed CORS origins

By default the server allows `localhost`, `127.0.0.1`, `chat.openai.com`, `chatgpt.com`, and `www.chatgpt.com`. Add more with `--allow-origin`:

```bash
food-facts-server --transport streamable-http \
  --allow-origin https://myapp.com \
  --allow-origin https://staging.myapp.com
```

### Direct public binding (no reverse proxy)

If you don't use Caddy and want the server publicly reachable directly (HTTP only):

```bash
food-facts-server --transport streamable-http --host 0.0.0.0 --port 8000
```

> Note: Direct binding serves plain HTTP. Use Caddy for HTTPS in production.

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
python -m pytest tests/ -v   # 28 tests (24 unit + 4 HTTP integration)
```

## Sources

- [USDA FDC API Guide](https://fdc.nal.usda.gov/api-guide/)
- [FDC OpenAPI Spec](https://fdc.nal.usda.gov/api-spec/fdc_api.html)
