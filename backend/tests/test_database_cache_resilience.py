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

        with patch.object(self.db, "_connect", _locked_connect):
            self.assertIsNone(await self.db.cache_get("locked-key"))

    async def test_cache_set_and_invalidate_ignore_lock_errors(self):
        @asynccontextmanager
        async def _locked_connect():
            raise sqlite3.OperationalError("database is locked")
            yield

        with patch.object(self.db, "_connect", _locked_connect):
            await self.db.cache_set("locked-key", {"ok": True}, 60)
            await self.db.cache_invalidate("locked-%")


if __name__ == "__main__":
    unittest.main()
