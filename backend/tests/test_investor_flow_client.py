import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd

from app.data import investor_flow_client


class _FakeBeforeCloseDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 7, 15, 30, tzinfo=tz)


class _FakeAfterCloseDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 4, 7, 18, 30, tzinfo=tz)


class InvestorFlowClientTests(unittest.TestCase):
    def test_krx_flow_status_marks_intraday_as_eod_pending(self):
        with patch("app.data.investor_flow_client.datetime", _FakeBeforeCloseDateTime):
            self.assertEqual(
                investor_flow_client._flow_data_status(datetime(2026, 4, 7).date()),
                "eod_pending",
            )

    def test_krx_flow_status_marks_after_18kst_as_fresh_eod(self):
        with patch("app.data.investor_flow_client.datetime", _FakeAfterCloseDateTime):
            self.assertEqual(
                investor_flow_client._flow_data_status(datetime(2026, 4, 7).date()),
                "fresh_eod",
            )

    def test_safe_sum_returns_recent_window_total(self):
        df = pd.DataFrame({"외국인합계": [100.0, -30.0, 40.0, 10.0, -5.0, 15.0]})

        self.assertEqual(investor_flow_client._safe_sum(df, "외국인합계", window=5), 30.0)
        self.assertEqual(investor_flow_client._safe_sum(df, "외국인합계", window=1), 15.0)
        self.assertIsNone(investor_flow_client._safe_sum(df, "기관합계", window=5))


if __name__ == "__main__":
    unittest.main()
