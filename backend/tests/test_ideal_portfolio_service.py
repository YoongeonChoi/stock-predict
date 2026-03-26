import unittest
from datetime import datetime
from datetime import date
from unittest.mock import AsyncMock, patch

from app.services import ideal_portfolio_service


def _radar_response(country_code: str, stance: str, opportunities: list[dict]) -> dict:
    return {
        "country_code": country_code,
        "generated_at": "2026-03-23T09:00:00",
        "market_regime": {
            "label": f"{country_code} regime",
            "stance": stance,
            "conviction": 68.0,
            "summary": "regime summary",
        },
        "total_scanned": 12,
        "actionable_count": len([item for item in opportunities if item["action"] in {"accumulate", "breakout_watch"}]),
        "bullish_count": len([item for item in opportunities if item["up_probability"] >= 55.0]),
        "opportunities": opportunities,
    }


def _opportunity(
    *,
    ticker: str,
    country_code: str,
    sector: str,
    score: float,
    up_probability: float,
    predicted_return_pct: float,
    execution_bias: str,
    action: str,
) -> dict:
    return {
        "rank": 1,
        "ticker": ticker,
        "name": f"{ticker} Corp",
        "sector": sector,
        "country_code": country_code,
        "current_price": 100.0,
        "change_pct": 1.1,
        "opportunity_score": score,
        "quant_score": 72.0,
        "up_probability": up_probability,
        "confidence": 68.0,
        "predicted_return_pct": predicted_return_pct,
        "target_horizon_days": 20,
        "target_date_20d": "2026-04-21",
        "expected_return_pct_20d": predicted_return_pct,
        "expected_excess_return_pct_20d": round(predicted_return_pct - 0.9, 2),
        "median_return_pct_20d": round(predicted_return_pct - 0.2, 2),
        "forecast_volatility_pct_20d": 7.4,
        "up_probability_20d": up_probability,
        "flat_probability_20d": 22.0,
        "down_probability_20d": 15.0,
        "distribution_confidence_20d": 71.0,
        "price_q25_20d": 98.0,
        "price_q50_20d": 102.0,
        "price_q75_20d": 106.0,
        "bull_case_price": 104.0,
        "base_case_price": 102.0,
        "bear_case_price": 97.0,
        "bull_probability": 30.0,
        "base_probability": 46.0,
        "bear_probability": 24.0,
        "setup_label": "Constructive Pullback",
        "action": action,
        "execution_bias": execution_bias,
        "execution_note": "execution note",
        "regime_tailwind": "tailwind",
        "entry_low": 99.0,
        "entry_high": 101.0,
        "stop_loss": 96.0,
        "take_profit_1": 104.0,
        "take_profit_2": 106.0,
        "risk_reward_estimate": 2.1,
        "thesis": ["momentum is improving"],
        "risk_flags": [],
        "forecast_date": "2026-03-24",
    }


class IdealPortfolioServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_snapshot_selects_kr_positions(self):
        kr = _radar_response(
            "KR",
            "risk_on",
            [
                _opportunity(
                    ticker="005930.KS",
                    country_code="KR",
                    sector="Information Technology",
                    score=82.0,
                    up_probability=63.0,
                    predicted_return_pct=2.4,
                    execution_bias="press_long",
                    action="accumulate",
                )
            ],
        )

        with patch(
            "app.services.ideal_portfolio_service.market_service.get_market_opportunities",
            new=AsyncMock(return_value=kr),
        ), patch(
            "app.services.ideal_portfolio_service.trading_days_forward",
            side_effect=lambda country_code, reference_date, count: [date(2026, 4, 21)],
        ), patch(
            "app.services.ideal_portfolio_service.yfinance_client.get_price_history",
            new=AsyncMock(
                return_value=[
                    {"date": "2026-03-17", "close": 96.0},
                    {"date": "2026-03-18", "close": 97.0},
                    {"date": "2026-03-19", "close": 98.5},
                    {"date": "2026-03-20", "close": 99.5},
                    {"date": "2026-03-21", "close": 100.2},
                    {"date": "2026-03-22", "close": 101.0},
                    {"date": "2026-03-23", "close": 102.0},
                ]
            ),
        ):
            snapshot = await ideal_portfolio_service._build_snapshot("2026-03-23")

        self.assertTrue(snapshot["positions"])
        self.assertEqual(snapshot["reference_date"], "2026-03-23")
        self.assertGreater(snapshot["summary"]["predicted_portfolio_return_pct"], 0)
        self.assertGreater(snapshot["summary"]["expected_excess_return_pct_20d"], 0)
        self.assertGreater(snapshot["summary"]["turnover_pct"], 0)
        self.assertGreater(snapshot["risk_budget"]["recommended_equity_pct"], 0.0)
        self.assertAlmostEqual(
            snapshot["risk_budget"]["recommended_equity_pct"] + snapshot["risk_budget"]["cash_buffer_pct"],
            100.0,
            places=2,
        )
        self.assertIn("KR", [item["country_code"] for item in snapshot["positions"]])
        self.assertTrue(snapshot["playbook"])

    async def test_evaluate_pending_snapshots_records_realized_performance(self):
        pending_rows = [
            {
                "reference_date": "2026-03-23",
                "portfolio": {
                    "positions": [
                        {
                            "ticker": "000660.KS",
                            "target_date": "2026-03-24",
                            "reference_price": 100.0,
                            "target_weight_pct": 20.0,
                            "predicted_return_pct": 2.0,
                            "bull_case_price": 104.0,
                            "bear_case_price": 97.0,
                        }
                    ]
                },
                "evaluation": None,
            }
        ]

        with (
            patch("app.services.ideal_portfolio_service.db.ideal_portfolio_pending", new=AsyncMock(return_value=pending_rows)),
            patch(
                "app.services.ideal_portfolio_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=[{"date": "2026-03-24", "close": 102.0}]),
            ),
            patch("app.services.ideal_portfolio_service.db.ideal_portfolio_set_evaluation", new=AsyncMock()) as set_eval,
        ):
            await ideal_portfolio_service._evaluate_pending_snapshots("2026-03-25")

        set_eval.assert_awaited_once()
        _, evaluation = set_eval.await_args.args
        self.assertEqual(evaluation["portfolio_return_pct"], 0.4)
        self.assertEqual(evaluation["win_rate"], 100.0)
        self.assertEqual(evaluation["direction_accuracy"], 100.0)

    async def test_get_daily_ideal_portfolio_uses_stored_snapshot(self):
        today = datetime.now().date().isoformat()
        snapshot = {
            "reference_date": today,
            "generated_at": f"{today}T09:00:00",
            "objective": "daily ideal portfolio",
            "target_dates": [{"country_code": "KR", "target_date": "2026-03-24"}],
            "risk_budget": {
                "style": "balanced",
                "style_label": "균형형",
                "recommended_equity_pct": 86.0,
                "cash_buffer_pct": 14.0,
                "target_position_count": 6,
                "max_single_weight_pct": 14.5,
                "max_country_weight_pct": 40.0,
                "max_sector_weight_pct": 26.0,
            },
            "market_view": [],
            "summary": {
                "selected_count": 1,
                "predicted_portfolio_return_pct": 1.2,
                "portfolio_up_probability": 58.0,
            },
            "allocation": {"by_country": [], "by_sector": []},
            "positions": [],
            "playbook": ["note"],
        }

        with (
            patch("app.services.ideal_portfolio_service._evaluate_pending_snapshots", new=AsyncMock()),
            patch("app.services.ideal_portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.ideal_portfolio_service.cache.set", new=AsyncMock()),
            patch(
                "app.services.ideal_portfolio_service.db.ideal_portfolio_get",
                new=AsyncMock(return_value={"reference_date": today, "portfolio": snapshot, "evaluation": None}),
            ),
            patch(
                "app.services.ideal_portfolio_service.db.ideal_portfolio_list",
                new=AsyncMock(return_value=[{"reference_date": today, "portfolio": snapshot, "evaluation": None}]),
            ),
            patch("app.services.ideal_portfolio_service._build_snapshot", new=AsyncMock()) as build_snapshot,
        ):
            result = await ideal_portfolio_service.get_daily_ideal_portfolio(force_refresh=False, history_limit=5)

        build_snapshot.assert_not_awaited()
        self.assertEqual(result["reference_date"], today)
        self.assertEqual(len(result["history"]), 1)
