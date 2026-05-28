import unittest
from unittest.mock import AsyncMock, patch

from app.services import archive_service


class ArchiveServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_report_persists_next_day_and_multi_horizon_calibration(self):
        report = {
            "next_day_forecast": {
                "target_date": "2026-03-31",
                "reference_date": "2026-03-28",
                "reference_price": 100.0,
                "predicted_close": 101.2,
                "predicted_low": 98.9,
                "predicted_high": 103.1,
                "up_probability": 61.0,
                "confidence": 68.0,
                "direction": "up",
                "drivers": [{"label": "Momentum"}],
                "calibration_snapshot": {"prediction_type": "next_day", "raw_support": 0.72},
                "model_version": "dist-studentt-v3.2",
            },
            "free_kr_forecast": {
                "reference_date": "2026-03-28",
                "reference_price": 100.0,
                "evidence": [{"label": "Macro"}],
                "model_version": "dist-studentt-v3.2",
                "horizons": [
                    {
                        "horizon_days": 5,
                        "target_date": "2026-04-04",
                        "price_q10": 96.0,
                        "price_q50": 103.0,
                        "price_q90": 109.0,
                        "p_up": 58.0,
                        "p_down": 22.0,
                        "p_flat": 20.0,
                        "confidence": 66.0,
                        "calibration_snapshot": {"prediction_type": "distributional_5d", "raw_support": 0.66},
                    },
                    {
                        "horizon_days": 20,
                        "target_date": "2026-04-25",
                        "price_q10": 94.0,
                        "price_q50": 107.0,
                        "price_q90": 116.0,
                        "p_up": 54.0,
                        "p_down": 24.0,
                        "p_flat": 22.0,
                        "confidence": 63.0,
                        "calibration_snapshot": {"prediction_type": "distributional_20d", "raw_support": 0.61},
                    },
                ],
            },
            "weekly_trade_plan": {
                "horizon_days": 5,
                "target_date": "2026-04-04",
                "reference_date": "2026-03-28",
                "action": "accumulate",
                "buy_price": 99.0,
                "buy_zone_low": 98.0,
                "buy_zone_high": 100.0,
                "sell_price": 106.0,
                "sell_zone_low": 105.0,
                "sell_zone_high": 108.0,
                "stop_loss": 95.0,
                "expected_return_pct": 3.0,
                "p_up": 58.0,
                "p_down": 22.0,
                "confidence": 66.0,
                "risk_reward_estimate": 1.5,
                "partial": False,
                "evidence": [{"key": "official_research"}],
                "source_freshness": [{"name": "공식 리서치·IB 메타데이터", "status": "fresh"}],
            },
        }

        with (
            patch("app.services.archive_service.db.archive_save", new=AsyncMock(return_value=42)),
            patch("app.services.archive_service.db.prediction_upsert", new=AsyncMock()) as prediction_upsert,
        ):
            report_id = await archive_service.save_report(
                report_type="stock",
                report=report,
                country_code="KR",
                ticker="005930.KS",
            )

        self.assertEqual(report_id, 42)
        self.assertEqual(prediction_upsert.await_count, 3)
        prediction_types = [item.kwargs["prediction_type"] for item in prediction_upsert.await_args_list]
        self.assertEqual(prediction_types, ["next_day", "distributional_5d", "distributional_20d"])
        self.assertEqual(
            prediction_upsert.await_args_list[1].kwargs["calibration_json"]["prediction_type"],
            "distributional_5d",
        )
        weekly_plan = prediction_upsert.await_args_list[1].kwargs["calibration_json"]["weekly_trade_plan"]
        self.assertEqual(weekly_plan["buy_price"], 99.0)
        self.assertEqual(weekly_plan["sell_price"], 106.0)
        self.assertEqual(weekly_plan["source_statuses"]["공식 리서치·IB 메타데이터"], "fresh")
        self.assertEqual(
            prediction_upsert.await_args_list[2].kwargs["calibration_json"]["prediction_type"],
            "distributional_20d",
        )

    async def test_refresh_prediction_accuracy_records_weekly_execution_window(self):
        pending_rows = [
            {
                "id": 7,
                "scope": "stock",
                "symbol": "005930.KS",
                "prediction_type": "distributional_5d",
                "target_date": "2026-04-04",
                "reference_date": "2026-03-28",
                "reference_price": 100.0,
                "calibration_json": {
                    "prediction_type": "distributional_5d",
                    "weekly_trade_plan": {
                        "action": "accumulate",
                        "buy_price": 99.0,
                        "buy_zone_low": 98.0,
                        "buy_zone_high": 100.0,
                        "sell_price": 106.0,
                        "sell_zone_low": 105.0,
                        "sell_zone_high": 108.0,
                        "stop_loss": 95.0,
                    },
                },
            }
        ]
        prices = [
            {"date": "2026-03-28", "close": 100.0, "low": 99.0, "high": 101.0},
            {"date": "2026-04-01", "close": 102.0, "low": 98.5, "high": 104.0},
            {"date": "2026-04-02", "close": 104.0, "low": 101.0, "high": 105.5},
            {"date": "2026-04-04", "close": 106.5, "low": 103.0, "high": 107.0},
        ]

        with (
            patch("app.services.archive_service.db.prediction_pending", new=AsyncMock(return_value=pending_rows)),
            patch("app.services.archive_service.yfinance_client.get_price_history", new=AsyncMock(return_value=prices)),
            patch("app.services.archive_service.db.prediction_update_actual", new=AsyncMock()) as update_actual,
            patch("app.services.confidence_calibration_service.refresh_empirical_profiles", new=AsyncMock()),
            patch("app.services.archive_service.opportunity_radar_lab_service.refresh_opportunity_radar_accuracy", new=AsyncMock(return_value={})),
        ):
            result = await archive_service.refresh_prediction_accuracy(limit=10)

        self.assertEqual(result["evaluated_count"], 1)
        update_actual.assert_awaited_once()
        kwargs = update_actual.await_args.kwargs
        self.assertEqual(kwargs["actual_window_low"], 98.5)
        self.assertEqual(kwargs["actual_window_high"], 107.0)
        self.assertTrue(kwargs["execution_json"]["buy_zone_touched"])
        self.assertTrue(kwargs["execution_json"]["sell_zone_touched"])
        self.assertFalse(kwargs["execution_json"]["stop_loss_touched"])
        self.assertEqual(kwargs["execution_json"]["outcome"], "target_zone_touched")
