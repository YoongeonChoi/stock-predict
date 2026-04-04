import unittest
from unittest.mock import AsyncMock, patch

from app.services import watchlist_tracking_service


class WatchlistTrackingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_tracking_detail_returns_inactive_onboarding_payload(self):
        with (
            patch(
                "app.services.watchlist_tracking_service.supabase_client.watchlist_get",
                new=AsyncMock(
                    return_value={
                        "id": 1,
                        "ticker": "005930.KS",
                        "country_code": "KR",
                        "added_at": "2026-04-04T00:00:00",
                        "tracking_enabled": False,
                        "tracking_started_at": None,
                        "tracking_updated_at": None,
                    }
                ),
            ),
            patch(
                "app.services.watchlist_tracking_service.forecast_monitor_service.get_stock_forecast_delta",
                new=AsyncMock(
                    return_value={
                        "generated_at": "2026-04-04T00:00:00",
                        "ticker": "005930.KS",
                        "summary": {"available": False, "message": "이력이 아직 부족합니다."},
                        "history": [],
                    }
                ),
            ),
            patch(
                "app.services.watchlist_tracking_service.get_cached_stock_detail",
                new=AsyncMock(
                    return_value={
                        "ticker": "005930.KS",
                        "name": "삼성전자",
                        "country_code": "KR",
                        "current_price": 72000,
                        "public_summary": {"summary": "현재 판단 근거", "confidence_note": "신뢰도 메모"},
                        "trade_plan": {"setup_label": "눌림목", "action": "accumulate"},
                        "market_regime": {"label": "중립"},
                    }
                ),
            ),
        ):
            payload = await watchlist_tracking_service.get_tracking_detail("user-123", "005930", "KR")

        self.assertEqual(payload["tracking_state"], "inactive")
        self.assertEqual(payload["panel_states"]["prediction_history"], "inactive")
        self.assertTrue(payload["latest_snapshot"]["available"])
        self.assertTrue(payload["current_context_summary"]["available"])

    async def test_get_tracking_detail_summarizes_accuracy_when_history_exists(self):
        with (
            patch(
                "app.services.watchlist_tracking_service.supabase_client.watchlist_get",
                new=AsyncMock(
                    return_value={
                        "id": 1,
                        "ticker": "005930.KS",
                        "country_code": "KR",
                        "added_at": "2026-04-04T00:00:00",
                        "tracking_enabled": True,
                        "tracking_started_at": "2026-04-04T00:00:00",
                        "tracking_updated_at": "2026-04-04T00:00:00",
                    }
                ),
            ),
            patch(
                "app.services.watchlist_tracking_service.forecast_monitor_service.get_stock_forecast_delta",
                new=AsyncMock(
                    return_value={
                        "generated_at": "2026-04-04T00:00:00",
                        "ticker": "005930.KS",
                        "summary": {
                            "available": True,
                            "current_direction": "up",
                            "current_direction_label": "상승",
                            "message": "상방 확률이 확대됐습니다.",
                        },
                        "history": [
                            {
                                "target_date": "2026-04-07",
                                "reference_price": 70000,
                                "predicted_close": 72100,
                                "predicted_low": 69000,
                                "predicted_high": 73000,
                                "up_probability": 61.2,
                                "confidence": 58.3,
                                "direction": "up",
                                "direction_label": "상승",
                                "actual_close": 71800,
                                "direction_hit": True,
                                "created_at": "2026-04-04T00:00:00",
                            },
                            {
                                "target_date": "2026-04-06",
                                "reference_price": 69000,
                                "predicted_close": 68800,
                                "predicted_low": 68000,
                                "predicted_high": 70000,
                                "up_probability": 47.0,
                                "confidence": 45.0,
                                "direction": "flat",
                                "direction_label": "보합",
                                "actual_close": 68400,
                                "direction_hit": False,
                                "created_at": "2026-04-03T00:00:00",
                            },
                        ],
                    }
                ),
            ),
            patch(
                "app.services.watchlist_tracking_service.get_cached_stock_detail",
                new=AsyncMock(
                    return_value={
                        "ticker": "005930.KS",
                        "name": "삼성전자",
                        "country_code": "KR",
                        "current_price": 72000,
                        "next_day_forecast": {
                            "target_date": "2026-04-07",
                            "predicted_close": 72100,
                            "predicted_low": 69000,
                            "predicted_high": 73000,
                            "direction": "up",
                            "up_probability": 61.2,
                            "confidence": 58.3,
                            "confidence_note": "보조 지표가 우호적입니다.",
                        },
                        "public_summary": {"summary": "현재 판단 근거", "confidence_note": "신뢰도 메모"},
                        "trade_plan": {"setup_label": "눌림목", "action": "accumulate"},
                        "market_regime": {"label": "중립"},
                    }
                ),
            ),
        ):
            payload = await watchlist_tracking_service.get_tracking_detail("user-123", "005930", "KR")

        self.assertEqual(payload["tracking_state"], "active")
        self.assertTrue(payload["realized_accuracy_summary"]["available"])
        self.assertEqual(payload["realized_accuracy_summary"]["direction_hit_rate"], 50.0)
        self.assertTrue(payload["prediction_change_summary"]["available"])
        self.assertEqual(payload["panel_states"]["prediction_history"], "ready")


if __name__ == "__main__":
    unittest.main()
