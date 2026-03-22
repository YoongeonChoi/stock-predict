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

CREATE TABLE IF NOT EXISTS prediction_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    symbol TEXT NOT NULL,
    country_code TEXT,
    prediction_type TEXT NOT NULL,
    target_date TEXT NOT NULL,
    reference_date TEXT,
    reference_price REAL NOT NULL,
    predicted_close REAL NOT NULL,
    predicted_low REAL,
    predicted_high REAL,
    up_probability REAL,
    confidence REAL,
    direction TEXT,
    drivers_json TEXT,
    model_version TEXT,
    created_at REAL NOT NULL,
    actual_close REAL,
    actual_low REAL,
    actual_high REAL,
    evaluated_at REAL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_records_unique
ON prediction_records(scope, symbol, prediction_type, target_date);

CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    name TEXT DEFAULT '',
    country_code TEXT DEFAULT 'US',
    buy_price REAL NOT NULL,
    quantity REAL NOT NULL,
    buy_date TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

    async def prediction_upsert(
        self,
        *,
        scope: str,
        symbol: str,
        country_code: str | None,
        prediction_type: str,
        target_date: str,
        reference_date: str | None,
        reference_price: float,
        predicted_close: float,
        predicted_low: float | None,
        predicted_high: float | None,
        up_probability: float | None,
        confidence: float | None,
        direction: str | None,
        drivers_json: list[dict] | None,
        model_version: str | None,
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO prediction_records (
                    scope, symbol, country_code, prediction_type, target_date,
                    reference_date, reference_price, predicted_close, predicted_low,
                    predicted_high, up_probability, confidence, direction,
                    drivers_json, model_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope, symbol, prediction_type, target_date)
                DO UPDATE SET
                    country_code = excluded.country_code,
                    reference_date = excluded.reference_date,
                    reference_price = excluded.reference_price,
                    predicted_close = excluded.predicted_close,
                    predicted_low = excluded.predicted_low,
                    predicted_high = excluded.predicted_high,
                    up_probability = excluded.up_probability,
                    confidence = excluded.confidence,
                    direction = excluded.direction,
                    drivers_json = excluded.drivers_json,
                    model_version = excluded.model_version,
                    created_at = excluded.created_at
                """,
                (
                    scope,
                    symbol,
                    country_code,
                    prediction_type,
                    target_date,
                    reference_date,
                    reference_price,
                    predicted_close,
                    predicted_low,
                    predicted_high,
                    up_probability,
                    confidence,
                    direction,
                    json.dumps(drivers_json, default=str) if drivers_json else None,
                    model_version,
                    time.time(),
                ),
            )
            await conn.commit()

    async def prediction_pending(self, target_date_to: str, limit: int = 200) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                """
                SELECT * FROM prediction_records
                WHERE actual_close IS NULL AND target_date <= ?
                ORDER BY target_date ASC, created_at ASC
                LIMIT ?
                """,
                (target_date_to, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def prediction_update_actual(
        self,
        *,
        record_id: int,
        actual_close: float,
        actual_low: float | None,
        actual_high: float | None,
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                """
                UPDATE prediction_records
                SET actual_close = ?, actual_low = ?, actual_high = ?, evaluated_at = ?
                WHERE id = ?
                """,
                (actual_close, actual_low, actual_high, time.time(), record_id),
            )
            await conn.commit()

    async def prediction_stats(self, prediction_type: str = "next_day") -> dict:
        async with aiosqlite.connect(self.db_path) as conn:
            total_cur = await conn.execute(
                """
                SELECT COUNT(*) AS stored_total,
                       SUM(CASE WHEN actual_close IS NULL THEN 1 ELSE 0 END) AS pending_total
                FROM prediction_records
                WHERE prediction_type = ?
                """,
                (prediction_type,),
            )
            total_row = await total_cur.fetchone()

            cur = await conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN actual_close BETWEEN predicted_low AND predicted_high THEN 1 ELSE 0 END) AS within_range,
                    SUM(
                        CASE
                            WHEN direction = 'up' AND actual_close > reference_price THEN 1
                            WHEN direction = 'down' AND actual_close < reference_price THEN 1
                            WHEN direction = 'flat' AND ABS(actual_close - reference_price) / NULLIF(reference_price, 0) <= 0.001 THEN 1
                            ELSE 0
                        END
                    ) AS direction_hits,
                    AVG(ABS(actual_close - predicted_close) / NULLIF(reference_price, 0)) AS avg_abs_error,
                    AVG(confidence) AS avg_confidence
                FROM prediction_records
                WHERE actual_close IS NOT NULL AND prediction_type = ?
                """,
                (prediction_type,),
            )
            row = await cur.fetchone()
            total = row[0] or 0
            within_range = row[1] or 0
            direction_hits = row[2] or 0
            return {
                "stored_predictions": total_row[0] or 0,
                "pending_predictions": total_row[1] or 0,
                "total_predictions": total,
                "within_range": within_range,
                "within_range_rate": round(within_range / total, 4) if total else 0,
                "direction_hits": direction_hits,
                "direction_accuracy": round(direction_hits / total, 4) if total else 0,
                "avg_error_pct": round((row[3] or 0) * 100, 2),
                "avg_confidence": round(row[4] or 0, 2),
            }


    # ── portfolio ────────────────────────────────────────────

    async def portfolio_add(
        self, ticker: str, name: str, country_code: str, buy_price: float, quantity: float, buy_date: str
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT INTO portfolio_holdings (ticker, name, country_code, buy_price, quantity, buy_date) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ticker, name, country_code, buy_price, quantity, buy_date),
            )
            await conn.commit()

    async def portfolio_list(self) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT * FROM portfolio_holdings ORDER BY created_at DESC"
            )
            return [dict(r) for r in await cur.fetchall()]

    async def portfolio_delete(self, holding_id: int):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("DELETE FROM portfolio_holdings WHERE id = ?", (holding_id,))
            await conn.commit()


db = Database()
