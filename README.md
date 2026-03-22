# Food Facts MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives AI assistants real-time access to nutrition data from two sources: **USDA FoodData Central** (whole foods, branded products, restaurant items) and **FatSecret** (extensive branded and fast-food coverage). Built for HooHacks 2026.

---

## The problem

AI assistants like Claude and ChatGPT know a lot about nutrition in general, but they cannot reliably answer specific nutrition questions without this server. Three concrete failure modes:

**1. Hallucinated numbers.** Ask Claude "how much protein is in a Chick-fil-A Deluxe Sandwich?" without live data access and it will produce a plausible-sounding number from training data — which may be wrong, outdated, or for a different serving size. There is no way for the model to know it's wrong.

**2. No citations.** Any nutrition claim an AI makes from memory is uncitable. For dietary tracking, research, or anything that matters, you need a traceable source. Without this server, LLMs cannot point you to a specific USDA FDC record or FatSecret entry — it can only say "according to general knowledge."

**3. Stale data.** Restaurant menus and product formulations change. An AI's training data has a cutoff; it has no way to reflect a menu item that was reformulated last quarter. This server fetches live data every time (and caches it), so the numbers are current.

This MCP server solves all three by connecting the AI directly to authoritative, live databases — USDA FoodData Central (the US government's official nutrition database) and FatSecret (2.3M+ branded and restaurant foods) — and attaching a citation to every response.

---

## What it does

Ask Claude (or any MCP-compatible AI) questions like:

- *"What are the nutrition facts for a Chick-fil-A chicken sandwich?"*
- *"Compare broccoli and spinach for iron content."*
- *"What are the top 10 foods highest in vitamin C?"*
- *"Give me an APA citation for USDA data on raw almonds."*

The server fetches live data, caches results locally in SQLite, and returns structured responses with citations.

---

## Tools (13 total)

### USDA FoodData Central (8 tools)

| Tool | Description |
|------|-------------|
| `search_foods` | Keyword search with dataset and brand filters |
| `get_food` | Full food details by FDC ID |
| `get_multiple_foods` | Batch lookup — up to 20 IDs at once |
| `get_food_nutrients` | Human-readable nutrient table sorted by nutrient number |
| `compare_foods` | Side-by-side nutrient comparison of two foods |
| `list_foods` | Browse all foods with pagination |
| `list_foods_by_nutrient` | Top N foods ranked by a given nutrient |
| `get_food_citation` | Citation-ready metadata (APA + MLA formats) |

### FatSecret (2 tools)

| Tool | Description |
|------|-------------|
| `search_fatsecret_foods` | Search branded and restaurant foods (McDonald's, Chick-fil-A, Subway, etc.) |
| `get_fatsecret_food` | Full nutrition breakdown by FatSecret food ID — all serving sizes |

### Cache Management (3 tools)

| Tool | Description |
|------|-------------|
| `get_cache_stats` | Cache health — total entries, size, breakdown by source and tool |
| `list_cached_foods` | Browse which foods are already cached (filterable by source or name) |
| `clear_cache` | Wipe all or selectively by source/tool |

---

## Data Sources

| Source | Coverage | Rate Limit |
|--------|----------|------------|
| [USDA FoodData Central](https://fdc.nal.usda.gov) | 2M+ foods across Foundation, SR Legacy, Branded, Survey datasets | 1 000 req/hr (registered key) |
| [FatSecret Platform API](https://platform.fatsecret.com) | 2.3M+ foods — strong restaurant and branded coverage | 5 000 req/day (free tier) |

### USDA Dataset Types

| Type | Best for |
|------|----------|
| **Foundation** | Raw commodity foods — most precise analytical data |
| **SR Legacy** | ~8 600 foods (raw, processed, prepared) — broad general use |
| **Branded** | Packaged and branded products |
| **Survey (FNDDS)** | Foods as consumed in NHANES surveys |

---

## Setup

### 1. Get API keys

- **USDA FDC** — free at [api.data.gov/signup](https://api.data.gov/signup/) — 1 000 req/hr
- **FatSecret** — free at [platform.fatsecret.com](https://platform.fatsecret.com) — 5 000 req/day

### 2. Install

```bash
pip install -e .
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```env
USDA_FDC_API_KEY=your_fdc_key
FATSECRET_CLIENT_ID=your_fatsecret_id
FATSECRET_CLIENT_SECRET=your_fatsecret_secret

# Optional cache settings
CACHE_DB_PATH=          # default: ~/.cache/food_facts_mcp/food_facts.db
CACHE_TTL_DAYS=         # default: no expiry
CACHE_ENABLED=true      # set false to disable caching
```

---

## Usage

### Claude Desktop (stdio)

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "food-facts": {
      "command": "python",
      "args": ["-m", "food_facts_mcp.server"],
      "cwd": "/path/to/HooHacks2026",
      "env": {
        "USDA_FDC_API_KEY": "your_key",
        "FATSECRET_CLIENT_ID": "your_id",
        "FATSECRET_CLIENT_SECRET": "your_secret"
      }
    }
  }
}
```

Restart Claude Desktop — the server appears under the MCP tools icon.

### HTTP server

```bash
food-facts-server --transport streamable-http --port 8000
```

MCP endpoint: `http://127.0.0.1:8000/mcp`
Health check: `http://127.0.0.1:8000/`

### MCP Inspector (for testing without Claude Desktop)

```bash
npx @modelcontextprotocol/inspector food-facts-server
```

---

## Caching

Responses are cached in SQLite after the first API call. Subsequent calls for the same food/query return instantly with no network request.

```
First call:   search_foods("broccoli")  →  ~1-2s  (USDA API)
Second call:  search_foods("broccoli")  →  <1ms   (SQLite cache)
```

The cache is source-agnostic — USDA FDC and FatSecret responses are stored in the same DB under separate source keys. Use `get_cache_stats` to inspect, `list_cached_foods` to browse, and `clear_cache` to reset.

---

## Deployment

### Public HTTPS with Caddy + DuckDNS

**1.** Register a free domain at [duckdns.org](https://www.duckdns.org)

**2.** Start the MCP server:

```bash
food-facts-server --transport streamable-http --host 127.0.0.1 --port 8000
```

**3.** Create a `Caddyfile`:

```
yourdomain.duckdns.org {
    reverse_proxy 127.0.0.1:8000
}
```

**4.** Run Caddy (handles TLS automatically via Let's Encrypt):

```bash
caddy run --config Caddyfile
```

**5.** MCP endpoint is now live at `https://yourdomain.duckdns.org/mcp`

### ChatGPT Connector

In ChatGPT → Settings → Connectors, point to `https://yourdomain.duckdns.org/mcp`.

### Extra CORS origins

```bash
food-facts-server --transport streamable-http \
  --allow-origin https://myapp.com
```

---

## Development

```bash
pip install -e .
python -m pytest tests/ -v   # 69 tests
```

### Project structure

```
src/food_facts_mcp/
  server.py            — FastMCP server, tool/resource/prompt registration
  tools.py             — All tool implementations (FDC + FatSecret)
  fdc_client.py        — USDA FoodData Central API client
  fatsecret_client.py  — FatSecret OAuth2 API client
  cache.py             — SQLite cache layer (FoodCache)
  citations.py         — APA + MLA citation builders
  resources.py         — MCP resource handlers + static data
  prompts.py           — Prompt template definitions
  sampling.py          — Sampling request builders
tests/
  test_tools.py        — FDC tool unit tests (mocked)
  test_fatsecret.py    — FatSecret tool unit tests (mocked)
  test_cache.py        — SQLite cache unit tests (in-memory)
  test_resources.py    — Resource + citation tests
  test_http_server.py  — HTTP transport + CORS tests
```

---

## API References

- [USDA FDC API Guide](https://fdc.nal.usda.gov/api-guide/)
- [FDC OpenAPI Spec](https://fdc.nal.usda.gov/api-spec/fdc_api.html)
- [FatSecret Platform API Docs](https://platform.fatsecret.com/docs)
- [Model Context Protocol](https://modelcontextprotocol.io)
