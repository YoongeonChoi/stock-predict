import aiosqlite
import json
import time
from pathlib import Path
from app.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at REAL NOT NULL,
    ttl_seconds INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    country_code TEXT NOT NULL,
    added_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS archive_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    country_code TEXT,
    sector_id TEXT,
    ticker TEXT,
    report_json TEXT NOT NULL,
    scores_json TEXT,
    predictions_json TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS forecast_accuracy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER REFERENCES archive_reports(id),
    predicted_price REAL,
    actual_price REAL,
    prediction_date REAL,
    target_date REAL,
    checked_at REAL
);
"""


class Database:
    def __init__(self):
        self.db_path = get_settings().db_path

    async def initialize(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.executescript(_SCHEMA)
            await conn.commit()

    # ── cache ──────────────────────────────────────────────

    async def cache_get(self, key: str):
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT value, created_at, ttl_seconds FROM cache WHERE key = ?",
                (key,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            value, created_at, ttl = row
            if time.time() - created_at > ttl:
                await conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                await conn.commit()
                return None
            return json.loads(value)

    async def cache_set(self, key: str, value, ttl_seconds: int):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, created_at, ttl_seconds) "
                "VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, default=str), time.time(), ttl_seconds),
            )
            await conn.commit()

    async def cache_invalidate(self, pattern: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM cache WHERE key LIKE ?", (pattern,))
            await conn.commit()

    # ── watchlist ──────────────────────────────────────────

    async def watchlist_add(self, ticker: str, country_code: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO watchlist (ticker, country_code, added_at) "
                "VALUES (?, ?, ?)",
                (ticker, country_code, time.time()),
            )
            await conn.commit()

    async def watchlist_remove(self, ticker: str):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM watchlist WHERE ticker = ?", (ticker,))
            await conn.commit()

    async def watchlist_list(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM watchlist ORDER BY added_at DESC"
            )
            return [dict(r) for r in await cur.fetchall()]

    # ── archive ────────────────────────────────────────────

    async def archive_save(
        self,
        report_type: str,
        report_json: dict,
        country_code: str | None = None,
        sector_id: str | None = None,
        ticker: str | None = None,
        scores_json: dict | None = None,
        predictions_json: dict | None = None,
    ) -> int:
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "INSERT INTO archive_reports "
                "(report_type, country_code, sector_id, ticker, "
                "report_json, scores_json, predictions_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_type,
                    country_code,
                    sector_id,
                    ticker,
                    json.dumps(report_json, default=str),
                    json.dumps(scores_json, default=str) if scores_json else None,
                    json.dumps(predictions_json, default=str)
                    if predictions_json
                    else None,
                    time.time(),
                ),
            )
            await conn.commit()
            return cur.lastrowid

    async def archive_list(
        self,
        report_type: str | None = None,
        country_code: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            clauses, params = ["1=1"], []
            if report_type:
                clauses.append("report_type = ?")
                params.append(report_type)
            if country_code:
                clauses.append("country_code = ?")
                params.append(country_code)
            params.append(limit)
            cur = await conn.execute(
                f"SELECT * FROM archive_reports WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC LIMIT ?",
                params,
            )
            return [dict(r) for r in await cur.fetchall()]

    async def archive_get(self, report_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM archive_reports WHERE id = ?", (report_id,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    # ── forecast accuracy ──────────────────────────────────

    async def accuracy_save(
        self, report_id: int, predicted_price: float, prediction_date: float, target_date: float
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO forecast_accuracy "
                "(report_id, predicted_price, prediction_date, target_date) "
                "VALUES (?, ?, ?, ?)",
                (report_id, predicted_price, prediction_date, target_date),
            )
            await conn.commit()

    async def accuracy_update(self, report_id: int, actual_price: float):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "UPDATE forecast_accuracy SET actual_price = ?, checked_at = ? "
                "WHERE report_id = ? AND actual_price IS NULL",
                (actual_price, time.time(), report_id),
            )
            await conn.commit()

    async def accuracy_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN ABS(actual_price - predicted_price) / predicted_price < 0.05 "
                "THEN 1 ELSE 0 END) as within_5pct, "
                "AVG(ABS(actual_price - predicted_price) / predicted_price) as avg_error "
                "FROM forecast_accuracy WHERE actual_price IS NOT NULL"
            )
            row = await cur.fetchone()
            total = row[0] or 0
            return {
                "total_predictions": total,
                "within_5pct": row[1] or 0,
                "accuracy_rate": (row[1] or 0) / total if total > 0 else 0,
                "avg_error_pct": round((row[2] or 0) * 100, 2),
            }


db = Database()
