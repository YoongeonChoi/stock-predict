import unittest
from unittest.mock import AsyncMock, patch

from app.models.forecast import ForecastScenario, NextDayForecast
from app.models.market import MarketRegime, TradePlan
from app.models.stock import BuySellGuide, TechnicalIndicators
from app.services import portfolio_service, research_service


def _sample_price_history(days: int = 25) -> list[dict]:
    rows = []
    for i in range(days):
        close = 100 + i
        rows.append(
            {
                "date": f"2026-03-{i + 1:02d}",
                "open": close - 1,
                "high": close + 1,
                "low": close - 2,
                "close": close,
                "volume": 1_000_000 + i * 1_000,
            }
        )
    return rows


class ResearchAndPortfolioTests(unittest.IsolatedAsyncioTestCase):
    async def test_prediction_lab_normalizes_breakdowns(self):
        with (
            patch("app.services.research_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.research_service.cache.set", new=AsyncMock()),
            patch("app.services.research_service.archive_service.refresh_prediction_accuracy", new=AsyncMock()),
            patch(
                "app.services.research_service.db.prediction_stats",
                new=AsyncMock(
                    return_value={
                        "stored_predictions": 12,
                        "pending_predictions": 2,
                        "total_predictions": 10,
                        "within_range": 7,
                        "within_range_rate": 0.7,
                        "direction_hits": 6,
                        "direction_accuracy": 0.6,
                        "avg_error_pct": 1.8,
                        "avg_confidence": 63.0,
                    }
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_recent",
                new=AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "scope": "stock",
                            "symbol": "AAPL",
                            "country_code": "US",
                            "target_date": "2026-03-20",
                            "reference_date": "2026-03-19",
                            "reference_price": 100.0,
                            "predicted_close": 101.0,
                            "predicted_low": 99.5,
                            "predicted_high": 102.0,
                            "actual_close": 101.5,
                            "direction": "up",
                            "confidence": 67.0,
                            "up_probability": 61.0,
                            "model_version": "signal-v2.1",
                            "created_at": 1.0,
                            "evaluated_at": 2.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_daily_trend",
                new=AsyncMock(
                    return_value=[
                        {
                            "target_date": "2026-03-20",
                            "total": 3,
                            "evaluated_total": 3,
                            "direction_hits": 2,
                            "within_range": 2,
                            "avg_abs_error": 0.013,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_country_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "US",
                            "total": 6,
                            "direction_hits": 4,
                            "within_range": 5,
                            "avg_abs_error": 0.011,
                            "avg_confidence": 62.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_scope_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "stock",
                            "total": 8,
                            "direction_hits": 5,
                            "within_range": 6,
                            "avg_abs_error": 0.012,
                            "avg_confidence": 61.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_model_breakdown",
                new=AsyncMock(
                    return_value=[
                        {
                            "label": "signal-v2.1",
                            "total": 10,
                            "direction_hits": 6,
                            "within_range": 7,
                            "avg_abs_error": 0.018,
                            "avg_confidence": 63.0,
                        }
                    ]
                ),
            ),
            patch(
                "app.services.research_service.db.prediction_confidence_buckets",
                new=AsyncMock(
                    return_value=[
                        {
                            "bucket": "65-74",
                            "total": 5,
                            "avg_confidence": 68.0,
                            "realized_up_rate": 60.0,
                            "direction_accuracy": 64.0,
                            "avg_error_pct": 1.4,
                        }
                    ]
                ),
            ),
        ):
            result = await research_service.get_prediction_lab(limit_recent=20, refresh=True)

        self.assertEqual(result["accuracy"]["total_predictions"], 10)
        self.assertEqual(result["breakdown"]["by_country"][0]["label"], "US")
        self.assertEqual(result["recent_records"][0]["direction_hit"], True)
        self.assertTrue(result["insights"])

    async def test_portfolio_empty_snapshot(self):
        with (
            patch("app.services.portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.portfolio_service.cache.set", new=AsyncMock()),
            patch("app.services.portfolio_service.db.portfolio_list", new=AsyncMock(return_value=[])),
        ):
            result = await portfolio_service.get_portfolio()

        self.assertEqual(result["summary"]["holding_count"], 0)
        self.assertEqual(result["risk"]["overall_label"], "empty")
        self.assertTrue(result["risk"]["playbook"])

    async def test_portfolio_surfaces_execution_mix_and_action_queue(self):
        index_forecast = NextDayForecast(
            target_date="2026-03-30",
            reference_date="2026-03-27",
            reference_price=3000.0,
            direction="down",
            up_probability=38.0,
            predicted_open=2980.0,
            predicted_close=2960.0,
            predicted_high=3005.0,
            predicted_low=2945.0,
            predicted_return_pct=-1.3,
            confidence=71.0,
            scenarios=[
                ForecastScenario(name="Bull", price=3025.0, probability=18.0, description=""),
                ForecastScenario(name="Base", price=2960.0, probability=44.0, description=""),
                ForecastScenario(name="Bear", price=2910.0, probability=38.0, description=""),
            ],
            risk_flags=["지수 변동성이 높아졌습니다."],
            execution_bias="reduce_risk",
            execution_note="지수 차원에서 방어가 우선입니다.",
        )
        stock_forecast = NextDayForecast(
            target_date="2026-03-30",
            reference_date="2026-03-27",
            reference_price=101.0,
            direction="down",
            up_probability=34.0,
            predicted_open=100.2,
            predicted_close=98.8,
            predicted_high=101.2,
            predicted_low=97.9,
            predicted_return_pct=-2.1,
            confidence=78.0,
            scenarios=[
                ForecastScenario(name="Bull", price=103.5, probability=16.0, description=""),
                ForecastScenario(name="Base", price=98.8, probability=41.0, description=""),
                ForecastScenario(name="Bear", price=95.4, probability=43.0, description=""),
            ],
            risk_flags=["하방 시나리오 확률이 높습니다.", "거래량 확인이 약합니다."],
            execution_bias="capital_preservation",
            execution_note="신규 매수보다 방어가 우선입니다.",
        )
        market_regime = MarketRegime(
            label="Risk-Off",
            stance="risk_off",
            trend="downtrend",
            volatility="high",
            breadth="weak",
            score=32.0,
            conviction=74.0,
            summary="Defensive tape.",
            playbook=["Keep risk tight."],
            warnings=["Breadth is weak."],
        )
        trade_plan = TradePlan(
            setup_label="Risk Reduction",
            action="reduce_risk",
            conviction=76.0,
            stop_loss=97.0,
            take_profit_1=104.0,
            take_profit_2=107.0,
            thesis=["Execution layer prefers capital preservation."],
            invalidation="Only reassess on a strong reclaim.",
        )
        buy_sell = BuySellGuide(
            buy_zone_low=95.0,
            buy_zone_high=98.0,
            fair_value=102.0,
            sell_zone_low=107.0,
            sell_zone_high=110.0,
            risk_reward_ratio=1.5,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        technical = TechnicalIndicators(
            ma_20=[],
            ma_60=[],
            rsi_14=[],
            macd=[],
            macd_signal=[],
            macd_hist=[],
            dates=[],
        )

        with (
            patch("app.services.portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.portfolio_service.cache.set", new=AsyncMock()),
            patch(
                "app.services.portfolio_service.db.portfolio_list",
                new=AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "ticker": "TEST",
                            "name": "Test Corp",
                            "country_code": "US",
                            "buy_price": 100.0,
                            "quantity": 12.0,
                            "buy_date": "2026-03-01",
                        }
                    ]
                ),
            ),
            patch(
                "app.services.portfolio_service.yfinance_client.get_price_history",
                new=AsyncMock(side_effect=[_sample_price_history(), _sample_price_history()]),
            ),
            patch(
                "app.services.portfolio_service.yfinance_client.get_stock_info",
                new=AsyncMock(return_value={"current_price": 101.0, "name": "Test Corp", "sector": "Tech"}),
            ),
            patch("app.services.portfolio_service.yfinance_client.get_analyst_ratings", new=AsyncMock(return_value={})),
            patch("app.services.portfolio_service.forecast_next_day", side_effect=[index_forecast, stock_forecast]),
            patch("app.services.portfolio_service.build_market_regime", return_value=market_regime),
            patch("app.services.portfolio_service.build_quick_buy_sell", return_value=buy_sell),
            patch("app.services.portfolio_service._calc_technicals", return_value=technical),
            patch("app.services.portfolio_service.build_trade_plan", return_value=trade_plan),
            patch("app.services.portfolio_service._annualized_volatility", return_value=26.5),
            patch("app.services.portfolio_service._max_drawdown", return_value=12.4),
            patch("app.services.portfolio_service._beta", return_value=1.18),
        ):
            result = await portfolio_service.get_portfolio()

        self.assertEqual(result["holdings"][0]["execution_bias"], "capital_preservation")
        self.assertEqual(result["holdings"][0]["bear_probability"], 43.0)
        self.assertTrue(result["holdings"][0]["risk_flags"])
        self.assertGreater(result["risk"]["downside_watch_weight"], 0)
        self.assertGreater(result["risk"]["bearish_scenario_exposure"], 0)
        self.assertTrue(result["risk"]["execution_mix"])
        self.assertEqual(result["risk"]["action_queue"][0]["execution_bias"], "capital_preservation")
