import sqlite3
import unittest
from contextlib import asynccontextmanager
from unittest.mock import patch

from app.database import Database


class DatabaseCacheResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = Database()

    async def test_cache_get_returns_none_when_cache_db_is_locked(self):
        @asynccontextmanager
        async def _locked_connect():
            raise sqlite3.OperationalError("database is locked")
            yield

        with patch.object(self.db, "_connect_cache", _locked_connect):
            self.assertIsNone(await self.db.cache_get("locked-key"))

    async def test_cache_set_and_invalidate_ignore_lock_errors(self):
        @asynccontextmanager
        async def _locked_connect():
            raise sqlite3.OperationalError("database is locked")
            yield

        with patch.object(self.db, "_connect_cache", _locked_connect):
            await self.db.cache_set("locked-key", {"ok": True}, 60)
            await self.db.cache_invalidate("locked-%")

    async def test_research_report_status_returns_empty_summary_when_public_read_db_is_locked(self):
        @asynccontextmanager
        async def _locked_connect():
            raise sqlite3.OperationalError("database is locked")
            yield

        with patch.object(self.db, "_connect_public_read", _locked_connect):
            status = await self.db.research_report_status("2026-03-29")

        self.assertEqual(status["total_reports"], 0)
        self.assertEqual(status["source_count"], 0)
        self.assertEqual(status["todays_reports"], 0)
        self.assertEqual(status["regions"], [])
        self.assertEqual(status["sources"], [])

    async def test_prediction_public_read_methods_fallback_when_db_is_locked(self):
        @asynccontextmanager
        async def _locked_connect():
            raise sqlite3.OperationalError("database is locked")
            yield

        with patch.object(self.db, "_connect_public_read", _locked_connect):
            stats = await self.db.prediction_stats("next_day")
            recent = await self.db.prediction_recent("next_day", 5)
            calibration = await self.db.prediction_confidence_buckets("next_day")

        self.assertEqual(stats["total_predictions"], 0)
        self.assertEqual(stats["stored_predictions"], 0)
        self.assertEqual(recent, [])
        self.assertEqual(calibration, [])


if __name__ == "__main__":
    unittest.main()
