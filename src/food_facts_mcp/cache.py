"""SQLite-backed response cache for Food Facts MCP tools."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _default_db_path() -> Path:
    cache_dir = Path.home() / ".cache" / "food_facts_mcp"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "food_facts.db"


class FoodCache:
    """SQLite cache for tool responses."""

    def __init__(self, db_path: Optional[str] = None, ttl_days: Optional[int] = None):
        if db_path is None:
            db_path = os.environ.get("CACHE_DB_PATH")
        path = Path(db_path) if db_path else _default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        ttl_env = os.environ.get("CACHE_TTL_DAYS")
        self.ttl_days: Optional[int] = ttl_days if ttl_days is not None else (
            int(ttl_env) if ttl_env else None
        )

        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                source         TEXT NOT NULL,
                tool_name      TEXT NOT NULL,
                cache_key      TEXT NOT NULL,
                response_json  TEXT NOT NULL,
                created_at     TEXT NOT NULL,
                last_accessed  TEXT NOT NULL,
                hit_count      INTEGER DEFAULT 0,
                UNIQUE(source, cache_key)
            );
            CREATE TABLE IF NOT EXISTS food_index (
                fdc_id       INTEGER PRIMARY KEY,
                source       TEXT NOT NULL,
                description  TEXT,
                data_type    TEXT,
                first_cached TEXT NOT NULL
            );
        """)
        self._conn.commit()

    @staticmethod
    def make_key(tool_name: str, **kwargs) -> str:
        payload = json.dumps({"tool": tool_name, **dict(sorted(kwargs.items()))},
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_expired(self, created_at: str) -> bool:
        if self.ttl_days is None:
            return False
        try:
            created = datetime.fromisoformat(created_at)
            age = (datetime.now(timezone.utc) - created).days
            return age >= self.ttl_days
        except (ValueError, TypeError):
            return False

    def get(self, source: str, key: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT response_json, created_at FROM cache_entries WHERE source=? AND cache_key=?",
            (source, key),
        ).fetchone()
        if row is None:
            return None
        response_json, created_at = row
        if self._is_expired(created_at):
            self._conn.execute(
                "DELETE FROM cache_entries WHERE source=? AND cache_key=?", (source, key)
            )
            self._conn.commit()
            return None
        now = self._now()
        self._conn.execute(
            "UPDATE cache_entries SET hit_count=hit_count+1, last_accessed=? "
            "WHERE source=? AND cache_key=?",
            (now, source, key),
        )
        self._conn.commit()
        return json.loads(response_json)

    def set(self, source: str, tool_name: str, key: str, data) -> None:
        now = self._now()
        response_json = json.dumps(data)
        self._conn.execute(
            """INSERT INTO cache_entries (source, tool_name, cache_key, response_json,
               created_at, last_accessed, hit_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)
               ON CONFLICT(source, cache_key) DO UPDATE SET
                 response_json=excluded.response_json,
                 created_at=excluded.created_at,
                 last_accessed=excluded.last_accessed,
                 hit_count=0""",
            (source, tool_name, key, response_json, now, now),
        )
        self._index_food(source, data, now)
        self._conn.commit()

    def _index_food(self, source: str, data, first_cached: str) -> None:
        """Index food items from a tool response into food_index.

        Only indexes items whose fdcId is an integer — FatSecret string IDs
        are intentionally excluded to avoid SQLite INTEGER PRIMARY KEY mismatch.
        """
        items: list[dict] = []
        if isinstance(data, dict):
            fdc_id = data.get("fdcId")
            if isinstance(fdc_id, int):
                items.append(data)
            # list-style responses (compare_foods has foodA/foodB)
            for sub_key in ("foodA", "foodB"):
                sub = data.get(sub_key)
                if isinstance(sub, dict) and isinstance(sub.get("fdcId"), int):
                    items.append(sub)
        elif isinstance(data, list):
            items = [x for x in data if isinstance(x, dict) and isinstance(x.get("fdcId"), int)]

        for item in items:
            fdc_id = item.get("fdcId")
            if not isinstance(fdc_id, int):
                continue
            self._conn.execute(
                """INSERT INTO food_index (fdc_id, source, description, data_type, first_cached)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(fdc_id) DO NOTHING""",
                (fdc_id, source, item.get("description"), item.get("dataType"), first_cached),
            )

    def stats(self) -> dict:
        total = self._conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
        by_source = {
            row[0]: row[1]
            for row in self._conn.execute(
                "SELECT source, COUNT(*) FROM cache_entries GROUP BY source"
            ).fetchall()
        }
        by_tool = {
            row[0]: row[1]
            for row in self._conn.execute(
                "SELECT tool_name, COUNT(*) FROM cache_entries GROUP BY tool_name"
            ).fetchall()
        }
        db_size_bytes = self._conn.execute(
            "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"
        ).fetchone()[0]
        return {
            "totalEntries": total,
            "dbSizeKb": round(db_size_bytes / 1024, 1),
            "bySource": by_source,
            "byTool": by_tool,
        }

    def list_foods(
        self,
        source: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        sql = "SELECT fdc_id, source, description, data_type, first_cached FROM food_index"
        params: list = []
        conditions: list[str] = []
        if source:
            conditions.append("source=?")
            params.append(source)
        if query:
            conditions.append("description LIKE ?")
            params.append(f"%{query}%")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY first_cached DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "fdcId": r[0],
                "source": r[1],
                "description": r[2],
                "dataType": r[3],
                "firstCached": r[4],
            }
            for r in rows
        ]

    def clear(self, source: Optional[str] = None, tool_name: Optional[str] = None) -> int:
        sql = "DELETE FROM cache_entries"
        params: list = []
        conditions: list[str] = []
        if source:
            conditions.append("source=?")
            params.append(source)
        if tool_name:
            conditions.append("tool_name=?")
            params.append(tool_name)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _cache_enabled() -> bool:
    return os.environ.get("CACHE_ENABLED", "true").lower() not in ("false", "0", "no")


_instance: Optional[FoodCache] = None


def get_cache() -> Optional[FoodCache]:
    """Return the singleton FoodCache, or None if caching is disabled."""
    if not _cache_enabled():
        return None
    global _instance
    if _instance is None:
        _instance = FoodCache()
    return _instance
