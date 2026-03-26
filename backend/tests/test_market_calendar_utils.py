import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from app.utils import market_calendar


class MarketCalendarUtilsTests(unittest.TestCase):
    def test_latest_closed_trading_day_uses_schedule_close(self):
        schedule = pd.DataFrame(
            {
                "market_open": [
                    pd.Timestamp("2026-03-23T00:00:00Z"),
                    pd.Timestamp("2026-03-24T00:00:00Z"),
                ],
                "market_close": [
                    pd.Timestamp("2026-03-23T06:30:00Z"),
                    pd.Timestamp("2026-03-24T06:30:00Z"),
                ],
            },
            index=pd.to_datetime(["2026-03-23", "2026-03-24"]),
        )

        with patch("app.utils.market_calendar._get_calendar") as mocked:
            mocked.return_value.schedule.return_value = schedule
            latest = market_calendar.latest_closed_trading_day(
                "KR",
                datetime(2026, 3, 24, 7, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(latest.isoformat(), "2026-03-24")

    def test_market_session_cache_token_marks_open_session(self):
        schedule = pd.DataFrame(
            {
                "market_open": [
                    pd.Timestamp("2026-03-23T00:00:00Z"),
                    pd.Timestamp("2026-03-24T00:00:00Z"),
                ],
                "market_close": [
                    pd.Timestamp("2026-03-23T06:30:00Z"),
                    pd.Timestamp("2026-03-24T06:30:00Z"),
                ],
            },
            index=pd.to_datetime(["2026-03-23", "2026-03-24"]),
        )

        with patch("app.utils.market_calendar._get_calendar") as mocked:
            mocked.return_value.schedule.return_value = schedule
            token = market_calendar.market_session_cache_token(
                country_code="KR",
                reference_time=datetime(2026, 3, 24, 2, 0, tzinfo=timezone.utc),
            )

        self.assertEqual(token, "2026-03-23:open")


if __name__ == "__main__":
    unittest.main()
