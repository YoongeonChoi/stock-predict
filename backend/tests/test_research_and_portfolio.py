import unittest
from unittest.mock import AsyncMock, call, patch

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
    def test_validate_portfolio_holding_input_normalizes_local_tickers(self):
        kr = portfolio_service.validate_portfolio_holding_input(
            "196170",
            120000,
            3,
            "2026-03-24",
            "KR",
        )
        samsung = portfolio_service.validate_portfolio_holding_input(
            "005930.ks",
            70000,
            5,
            "2026-03-24",
            "KR",
        )

        self.assertEqual(kr["ticker"], "196170.KQ")
        self.assertEqual(samsung["ticker"], "005930.KS")

    async def test_portfolio_add_holding_saves_normalized_ticker(self):
        db_add = AsyncMock()
        cache_invalidate = AsyncMock()
        get_stock_info = AsyncMock(return_value={"name": "Samsung Electronics"})

        with (
            patch("app.services.portfolio_service.supabase_client.portfolio_add", new=db_add),
            patch("app.services.portfolio_service.cache.invalidate", new=cache_invalidate),
            patch("app.services.portfolio_service.yfinance_client.get_stock_info", new=get_stock_info),
        ):
            result = await portfolio_service.add_holding("user-123", "005930", 70000, 10, "2026-03-24", "KR")

        self.assertEqual(result["ticker"], "005930.KS")
        self.assertEqual(result["name"], "Samsung Electronics")
        db_add.assert_awaited_once_with(
            "user-123",
            "005930.KS",
            "Samsung Electronics",
            "KR",
            70000.0,
            10.0,
            "2026-03-24",
        )
        self.assertEqual(cache_invalidate.await_count, 2)
        cache_invalidate.assert_has_awaits([call("%:user-123"), call("portfolio_overview:%")])

    async def test_portfolio_update_holding_saves_normalized_ticker(self):
        db_update = AsyncMock()
        cache_invalidate = AsyncMock()
        get_stock_info = AsyncMock(return_value={"name": "Samsung Electronics"})

        with (
            patch("app.services.portfolio_service.supabase_client.portfolio_update", new=db_update),
            patch("app.services.portfolio_service.cache.invalidate", new=cache_invalidate),
            patch("app.services.portfolio_service.yfinance_client.get_stock_info", new=get_stock_info),
        ):
            result = await portfolio_service.update_holding("user-123", 7, "005930", 70000, 4, "2026-03-24", "KR")

        self.assertEqual(result["ticker"], "005930.KS")
        db_update.assert_awaited_once_with(
            "user-123",
            7,
            "005930.KS",
            "Samsung Electronics",
            "KR",
            70000.0,
            4.0,
            "2026-03-24",
        )
        self.assertEqual(cache_invalidate.await_count, 2)
        cache_invalidate.assert_has_awaits([call("%:user-123"), call("portfolio_overview:%")])

    async def test_portfolio_profile_update_normalizes_summary(self):
        with (
            patch(
                "app.services.portfolio_service.supabase_client.portfolio_profile_upsert",
                new=AsyncMock(),
            ),
            patch(
                "app.services.portfolio_service.supabase_client.portfolio_profile_get",
                new=AsyncMock(
                    return_value={
                        "total_assets": 15000000.0,
                        "cash_balance": 2500000.0,
                        "monthly_budget": 500000.0,
                        "updated_at": 123.0,
                    }
                ),
            ),
            patch("app.services.portfolio_service.cache.invalidate", new=AsyncMock()),
        ):
            result = await portfolio_service.update_portfolio_profile("user-123", 15000000, 2500000, 500000)

        self.assertEqual(result["total_assets"], 15000000.0)
        self.assertEqual(result["cash_balance"], 2500000.0)
        self.assertEqual(result["monthly_budget"], 500000.0)

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
                            "symbol": "005930.KS",
                            "country_code": "KR",
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
                            "label": "KR",
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
        self.assertEqual(result["breakdown"]["by_country"][0]["label"], "KR")
        self.assertEqual(result["recent_records"][0]["direction_hit"], True)
        self.assertTrue(result["insights"])

    async def test_portfolio_empty_snapshot(self):
        with (
            patch("app.services.portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.portfolio_service.cache.set", new=AsyncMock()),
            patch("app.services.portfolio_service.supabase_client.portfolio_list", new=AsyncMock(return_value=[])),
            patch(
                "app.services.portfolio_service.supabase_client.portfolio_profile_get",
                new=AsyncMock(
                    return_value={
                        "total_assets": 12000000.0,
                        "cash_balance": 3000000.0,
                        "monthly_budget": 400000.0,
                        "updated_at": 123.0,
                    }
                ),
            ),
        ):
            result = await portfolio_service.get_portfolio("user-123")

        self.assertEqual(result["summary"]["holding_count"], 0)
        self.assertEqual(result["summary"]["total_assets"], 12000000.0)
        self.assertEqual(result["summary"]["cash_balance"], 3000000.0)
        self.assertEqual(result["risk"]["overall_label"], "empty")
        self.assertTrue(result["risk"]["playbook"])
        self.assertIn("model_portfolio", result)
        self.assertTrue(result["model_portfolio"]["notes"])

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
        radar_response = {
            "country_code": "KR",
            "generated_at": "2026-03-29T08:00:00",
            "market_regime": market_regime.model_dump(),
            "total_scanned": 4,
            "actionable_count": 1,
            "bullish_count": 1,
            "opportunities": [
                {
                    "rank": 1,
                    "ticker": "000660.KS",
                    "name": "SK hynix",
                    "sector": "Information Technology",
                    "country_code": "KR",
                    "current_price": 205000.0,
                    "change_pct": 1.2,
                    "opportunity_score": 77.0,
                    "quant_score": 74.0,
                    "up_probability": 62.0,
                    "confidence": 69.0,
                    "predicted_return_pct": 2.3,
                    "bull_case_price": 210000.0,
                    "base_case_price": 208000.0,
                    "bear_case_price": 201000.0,
                    "bull_probability": 31.0,
                    "base_probability": 45.0,
                    "bear_probability": 24.0,
                    "setup_label": "Constructive Pullback",
                    "action": "accumulate",
                    "execution_bias": "lean_long",
                    "execution_note": "추세 재가속을 보는 구간입니다.",
                    "regime_tailwind": "mixed",
                    "entry_low": 202000.0,
                    "entry_high": 205500.0,
                    "stop_loss": 198000.0,
                    "take_profit_1": 212000.0,
                    "take_profit_2": 218000.0,
                    "risk_reward_estimate": 2.1,
                    "thesis": ["실적 모멘텀이 회복되는 흐름입니다."],
                    "risk_flags": [],
                    "forecast_date": "2026-03-30",
                }
            ],
        }
        empty_radar_response = {
            "country_code": "KR",
            "generated_at": "2026-03-29T08:00:00",
            "market_regime": market_regime.model_dump(),
            "total_scanned": 0,
            "actionable_count": 0,
            "bullish_count": 0,
            "opportunities": [],
        }

        with (
            patch("app.services.portfolio_service.cache.get", new=AsyncMock(return_value=None)),
            patch("app.services.portfolio_service.cache.set", new=AsyncMock()),
            patch(
                "app.services.portfolio_service.supabase_client.portfolio_profile_get",
                new=AsyncMock(
                    return_value={
                        "total_assets": 10000.0,
                        "cash_balance": 2000.0,
                        "monthly_budget": 500.0,
                        "updated_at": 123.0,
                    }
                ),
            ),
            patch(
                "app.services.portfolio_service.supabase_client.portfolio_list",
                new=AsyncMock(
                    return_value=[
                        {
                            "id": 1,
                            "ticker": "005930",
                            "name": "Samsung Electronics",
                            "country_code": "KR",
                            "buy_price": 100.0,
                            "quantity": 12.0,
                            "buy_date": "2026-03-01",
                        }
                    ]
                ),
            ),
            patch(
                "app.services.portfolio_service.supabase_client.watchlist_list",
                new=AsyncMock(return_value=[{"ticker": "000660.KS", "country_code": "KR"}]),
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
            patch(
                "app.services.portfolio_service.market_service.get_market_opportunities",
                new=AsyncMock(side_effect=[radar_response, empty_radar_response]),
            ),
        ):
            result = await portfolio_service.get_portfolio("user-123")

        self.assertEqual(result["holdings"][0]["execution_bias"], "capital_preservation")
        self.assertEqual(result["holdings"][0]["bear_probability"], 43.0)
        self.assertTrue(result["holdings"][0]["risk_flags"])
        self.assertGreater(result["risk"]["downside_watch_weight"], 0)
        self.assertGreater(result["risk"]["bearish_scenario_exposure"], 0)
        self.assertTrue(result["risk"]["execution_mix"])
        self.assertEqual(result["risk"]["action_queue"][0]["execution_bias"], "capital_preservation")
        self.assertTrue(result["model_portfolio"]["recommended_holdings"])
        self.assertIn("000660.KS", [item["ticker"] for item in result["model_portfolio"]["recommended_holdings"]])
        self.assertTrue(result["model_portfolio"]["rebalance_actions"])
