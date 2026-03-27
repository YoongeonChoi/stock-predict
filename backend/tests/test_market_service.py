import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.forecast import ForecastScenario, NextDayForecast
from app.models.market import MarketRegime, MarketRegimeSignal, TradePlan
from app.models.stock import BuySellGuide, TechnicalIndicators, ValuationMethod
from app.services import market_service


def _sample_prices(days: int = 80, start: float = 100.0) -> list[dict]:
    prices = []
    for index in range(days):
        close = start + index * 0.35
        prices.append(
            {
                "date": f"2026-01-{(index % 28) + 1:02d}",
                "open": round(close - 0.4, 2),
                "high": round(close + 0.8, 2),
                "low": round(close - 0.9, 2),
                "close": round(close, 2),
                "volume": 1000000 + index * 500,
            }
        )
    return prices


async def _gather_sequential(items, worker, limit=6):
    return [await worker(item) for item in items]


async def _return_fetcher(key, fetcher, ttl=None):
    return await fetcher()


class MarketServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_market_opportunities_returns_distributional_signal_profile(self):
        forecast = NextDayForecast(
            target_date="2026-03-27",
            reference_date="2026-03-26",
            reference_price=100.0,
            direction="up",
            up_probability=61.0,
            predicted_open=100.4,
            predicted_close=102.5,
            predicted_high=104.0,
            predicted_low=99.0,
            predicted_return_pct=2.5,
            confidence=68.0,
            scenarios=[
                ForecastScenario(name="Bull", price=106.0, probability=28.0, description="상방"),
                ForecastScenario(name="Base", price=102.5, probability=49.0, description="기준"),
                ForecastScenario(name="Bear", price=97.5, probability=23.0, description="하방"),
            ],
            execution_bias="lean_long",
            execution_note="추세 우위",
            risk_flags=["변동성 주의"],
        )
        market_regime = MarketRegime(
            label="위험 선호",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=72.0,
            conviction=64.0,
            summary="시장 참여가 안정적입니다.",
            playbook=["강세 우위"],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.7, signal="bullish", detail="breadth strong")],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=95.0,
            buy_zone_high=101.0,
            fair_value=108.0,
            sell_zone_low=112.0,
            sell_zone_high=118.0,
            risk_reward_ratio=2.1,
            confidence_grade="A",
            methodology=[ValuationMethod(name="blend", value=108.0, weight=1.0, details="test")],
            summary="저평가 구간",
        )
        technical = TechnicalIndicators(
            ma_20=[99.0],
            ma_60=[95.0],
            rsi_14=[56.0],
            macd=[0.5],
            macd_signal=[0.4],
            macd_hist=[0.1],
            dates=["2026-03-26"],
        )
        trade_plan = TradePlan(
            setup_label="추세 추종",
            action="accumulate",
            conviction=63.0,
            entry_low=100.0,
            entry_high=101.5,
            stop_loss=96.5,
            take_profit_1=106.0,
            take_profit_2=110.0,
            expected_holding_days=10,
            risk_reward_estimate=2.4,
            thesis=["실적 추정 상향"],
            invalidation="수급 약화",
        )

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"Information Technology": ["005930.KS"]},
                        source="fallback",
                        note="test universe",
                    )
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(side_effect=[_sample_prices(90, 3000.0), _sample_prices(90, 100.0)]),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(
                    return_value={"valid": True, "current_price": 101.0, "name": "삼성전자"}
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_stock_info",
                new=AsyncMock(
                    return_value={
                        "name": "삼성전자",
                        "current_price": 101.0,
                        "prev_close": 100.0,
                        "target_mean": 110.0,
                        "target_median": 109.0,
                        "target_high": 120.0,
                        "target_low": 95.0,
                    }
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_analyst_ratings",
                new=AsyncMock(return_value={"buy": 8, "hold": 2, "sell": 1}),
            ),
            patch(
                "app.services.market_service.score_stock",
                return_value=SimpleNamespace(total=72.0),
            ),
            patch("app.services.market_service.build_quick_buy_sell", return_value=buy_sell),
            patch("app.services.market_service._calc_technicals", return_value=technical),
            patch("app.services.market_service.forecast_next_day", return_value=forecast),
            patch("app.services.market_service.build_trade_plan", return_value=trade_plan),
            patch("app.services.market_service.build_market_regime", return_value=market_regime),
            patch(
                "app.services.market_service.ecos_client.get_kr_economic_snapshot",
                new=AsyncMock(return_value={"consumer_sentiment": 101.2}),
            ),
            patch(
                "app.services.market_service.kosis_client.get_kr_macro_snapshot",
                new=AsyncMock(return_value={"employment": 62.1}),
            ),
            patch("app.services.market_service.gather_limited", new=_gather_sequential),
        ):
            result = await market_service.get_market_opportunities("KR", limit=1, max_candidates=1)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(result["total_scanned"], 1)
        self.assertEqual(len(result["opportunities"]), 1)
        self.assertEqual(result["opportunities"][0]["ticker"], "005930.KS")
        self.assertGreater(result["opportunities"][0]["predicted_return_pct"], 0.0)

    async def test_get_market_opportunities_falls_back_to_lightweight_scan_on_timeout(self):
        market_regime = MarketRegime(
            label="중립",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=55.0,
            conviction=48.0,
            summary="중립 장세",
            playbook=["선별 대응"],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.0, signal="neutral", detail="mixed breadth")],
        )

        async def _slow_scan(*args, **kwargs):
            await asyncio.sleep(0.05)
            return []

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"Information Technology": ["005930.KS", "000660.KS"]},
                        source="fallback",
                        note="test universe",
                    )
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(
                    side_effect=[
                        {"valid": True, "current_price": 3200.0, "name": "KOSPI"},
                        {"valid": True, "current_price": 101.0, "change_pct": 1.2, "market_cap": 400000000000.0, "name": "삼성전자"},
                        {"valid": True, "current_price": 87.0, "change_pct": 0.6, "market_cap": 210000000000.0, "name": "SK hynix"},
                    ]
                ),
            ),
            patch(
                "app.services.market_service.ecos_client.get_kr_economic_snapshot",
                new=AsyncMock(return_value={}),
            ),
            patch(
                "app.services.market_service.kosis_client.get_kr_macro_snapshot",
                new=AsyncMock(return_value={}),
            ),
            patch("app.services.market_service.build_market_regime", return_value=market_regime),
            patch("app.services.market_service.gather_limited", new=AsyncMock(side_effect=_slow_scan)),
            patch("app.services.market_service.OPPORTUNITY_SCAN_TIMEOUT_SECONDS", 0.01),
            patch(
                "app.services.market_service._build_lightweight_opportunities",
                new=AsyncMock(
                    return_value=[
                        market_service._build_lightweight_opportunity_item(
                            rank=1,
                            sector="Information Technology",
                            ticker="005930.KS",
                            snapshot={"current_price": 101.0, "change_pct": 1.2, "market_cap": 400000000000.0, "name": "삼성전자"},
                            country_code="KR",
                            market_regime=market_regime,
                        ),
                        market_service._build_lightweight_opportunity_item(
                            rank=2,
                            sector="Information Technology",
                            ticker="000660.KS",
                            snapshot={"current_price": 87.0, "change_pct": 0.6, "market_cap": 210000000000.0, "name": "SK hynix"},
                            country_code="KR",
                            market_regime=market_regime,
                        ),
                    ]
                ),
            ),
        ):
            result = await market_service.get_market_opportunities("KR", limit=2, max_candidates=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertEqual(result["opportunities"][0]["setup_label"], "축약 스캔")

    async def test_lightweight_opportunities_cap_candidate_budget(self):
        market_regime = MarketRegime(
            label="중립",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=55.0,
            conviction=48.0,
            summary="중립 장세",
            playbook=["선별 대응"],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.0, signal="neutral", detail="mixed breadth")],
        )
        candidates = [("Information Technology", f"{index:06d}.KS") for index in range(10)]
        seen: list[str] = []

        async def _snapshot(ticker: str, period: str = "3mo"):
            seen.append(ticker)
            return {
                "valid": True,
                "current_price": 100.0,
                "change_pct": 1.2,
                "market_cap": 1000000000.0,
                "name": ticker,
            }

        with patch(
            "app.services.market_service.yfinance_client.get_market_snapshot",
            new=AsyncMock(side_effect=_snapshot),
        ):
            result = await market_service._build_lightweight_opportunities(
                candidates=candidates,
                country_code="KR",
                market_regime=market_regime,
                limit=12,
            )

        self.assertLessEqual(len(seen), market_service.LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES)
        self.assertLessEqual(len(result), market_service.LIGHTWEIGHT_OPPORTUNITY_MAX_CANDIDATES)


if __name__ == "__main__":
    unittest.main()
