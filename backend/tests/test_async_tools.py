import asyncio
import unittest

from app.utils.async_tools import GatheredBaseExceptionError, gather_limited, is_async_failure_result


class AsyncToolsTests(unittest.IsolatedAsyncioTestCase):
    async def test_gather_limited_wraps_cancelled_results(self):
        async def worker(item: str) -> str:
            if item == "cancel":
                raise asyncio.CancelledError()
            return item.upper()

        results = await gather_limited(["cancel", "ok"], worker, limit=2)

        self.assertIsInstance(results[0], GatheredBaseExceptionError)
        self.assertTrue(is_async_failure_result(results[0]))
        self.assertIsInstance(results[0].original, asyncio.CancelledError)
        self.assertEqual(results[1], "OK")


if __name__ == "__main__":
    unittest.main()
