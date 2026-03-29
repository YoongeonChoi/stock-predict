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
    def test_sample_universe_pairs_round_robins_across_sectors(self):
        pairs = market_service._sample_universe_pairs(
            {
                "A": ["A1", "A2"],
                "B": ["B1", "B2"],
                "C": ["C1"],
            },
            5,
        )

        self.assertEqual(
            pairs,
            [("A", "A1"), ("B", "B1"), ("C", "C1"), ("A", "A2"), ("B", "B2")],
        )

    async def test_get_market_opportunities_uses_cached_payload_before_heavy_prework(self):
        cached_payload = {
            "country_code": "KR",
            "generated_at": "2026-03-27T00:00:00",
            "market_regime": None,
            "universe_size": 201,
            "total_scanned": 201,
            "quote_available_count": 201,
            "detailed_scanned_count": 0,
            "actionable_count": 12,
            "bullish_count": 6,
            "universe_source": "fallback",
            "universe_note": "cached payload",
            "opportunities": [],
        }

        async def _cached_only(_key, _fetcher, ttl=None):
            return cached_payload

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_cached_only)),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(side_effect=AssertionError("heavy prework should not run on cached response")),
            ),
        ):
            result = await market_service.get_market_opportunities("KR", limit=12)

        self.assertEqual(result, cached_payload)

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
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"Information Technology": ["005930.KS", "000660.KS", "035420.KS"]},
                        source="fallback",
                        note="test universe",
                    )
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(
                    return_value={
                        "005930.KS": {"ticker": "005930.KS", "current_price": 101.0, "prev_close": 99.2, "change_pct": 1.8, "session_date": "2026-03-26"},
                        "000660.KS": {"ticker": "000660.KS", "current_price": 87.0, "prev_close": 86.57, "change_pct": 0.5, "session_date": "2026-03-26"},
                        "035420.KS": {"ticker": "035420.KS", "current_price": 195.0, "prev_close": 195.59, "change_pct": -0.3, "session_date": "2026-03-26"},
                    }
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
        self.assertIn("snapshot_id", result)
        self.assertEqual(result["fallback_tier"], "full")
        self.assertEqual(result["universe_size"], 3)
        self.assertEqual(result["total_scanned"], 3)
        self.assertEqual(result["quote_available_count"], 3)
        self.assertEqual(result["detailed_scanned_count"], 1)
        self.assertEqual(len(result["opportunities"]), 1)
        self.assertEqual(result["opportunities"][0]["ticker"], "005930.KS")
        self.assertGreater(result["opportunities"][0]["predicted_return_pct"], 0.0)

    async def test_get_market_opportunities_falls_back_to_quote_screen_candidates(self):
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

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"Information Technology": ["005930.KS", "000660.KS"]},
                        source="fallback",
                        note="test universe",
                    )
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(
                    return_value={
                        "005930.KS": {"ticker": "005930.KS", "current_price": 101.0, "prev_close": 99.8, "change_pct": 1.2, "session_date": "2026-03-26"},
                        "000660.KS": {"ticker": "000660.KS", "current_price": 87.0, "prev_close": 86.48, "change_pct": 0.6, "session_date": "2026-03-26"},
                    }
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=asyncio.TimeoutError()),
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
            patch("app.services.market_service.gather_limited", new=_gather_sequential),
        ):
            result = await market_service.get_market_opportunities("KR", limit=2, max_candidates=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertIn("snapshot_id", result)
        self.assertEqual(result["fallback_tier"], "full")
        self.assertEqual(result["universe_size"], 2)
        self.assertEqual(result["total_scanned"], 2)
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertEqual(result["opportunities"][0]["setup_label"], "전수 1차 스캔")
        self.assertGreater(result["actionable_count"], 0)
        self.assertIn("기본 종목군 2개", result["universe_note"])

    async def test_get_market_opportunities_quick_returns_quote_only_response(self):
        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.cache.get",
                new=AsyncMock(
                    return_value={
                        "sectors": {"Information Technology": ["005930.KS", "000660.KS"]},
                        "total": 2,
                    }
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(
                    return_value={
                        "005930.KS": {
                            "ticker": "005930.KS",
                            "name": "삼성전자",
                            "current_price": 70100.0,
                            "prev_close": 69300.0,
                            "change_pct": 1.15,
                            "market_cap": 420000000000.0,
                        },
                        "000660.KS": {
                            "ticker": "000660.KS",
                            "name": "SK하이닉스",
                            "current_price": 201000.0,
                            "prev_close": 198500.0,
                            "change_pct": 1.26,
                            "market_cap": 146000000000.0,
                        },
                    }
                ),
            ),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertIn("snapshot_id", result)
        self.assertEqual(result["fallback_tier"], "quick")
        self.assertEqual(result["universe_size"], 2)
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("1차 시세 스캔 후보", result["universe_note"])

    async def test_get_market_opportunities_quick_falls_back_to_curated_universe_when_krx_quotes_are_empty(self):
        fallback_selection = market_service.UniverseSelection(
            sectors={"Information Technology": ["005930.KS", "000660.KS"]},
            source="fallback",
            note="검증된 한국 기본 종목군으로 추천 중입니다.",
        )
        fallback_screen = {
            "universe_size": 2,
            "scanned_count": 2,
            "quote_available_count": 2,
            "ranked": [
                {"sector": "Information Technology", "ticker": "005930.KS", "current_price": 70100.0, "change_pct": 1.15},
                {"sector": "Information Technology", "ticker": "000660.KS", "current_price": 201000.0, "change_pct": 1.26},
            ],
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.cache.get",
                new=AsyncMock(
                    return_value={
                        "sectors": {"전자부품 제조업": ["111111.KS", "222222.KS"]},
                        "total": 2,
                    }
                ),
            ),
            patch("app.services.market_service.resolve_universe", new=AsyncMock(return_value=fallback_selection)),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(
                    side_effect=[
                        {"universe_size": 2, "scanned_count": 2, "quote_available_count": 0, "ranked": []},
                        fallback_screen,
                    ]
                ),
            ),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(result["universe_source"], "fallback")
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("즉시 전환", result["universe_note"])

    async def test_get_market_opportunities_quick_caps_large_kr_quote_screen(self):
        tickers = [f"{index:06d}.KS" for index in range(240)]
        capped_tickers = tickers[: market_service.QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP]
        batch_quotes = {
            ticker: {
                "ticker": ticker,
                "name": ticker,
                "current_price": 100.0 + index,
                "prev_close": 99.0 + index,
                "change_pct": round(0.3 + index * 0.01, 2),
                "market_cap": 1000000000.0 + index,
            }
            for index, ticker in enumerate(capped_tickers)
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.cache.get",
                new=AsyncMock(
                    return_value={
                        "sectors": {"Information Technology": tickers},
                        "total": len(tickers),
                    }
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(return_value=batch_quotes),
            ) as bulk_quotes_mock,
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=5)

        requested_tickers = bulk_quotes_mock.await_args.args[0]
        self.assertEqual(len(requested_tickers), market_service.QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP)
        self.assertEqual(result["universe_size"], 240)
        self.assertEqual(result["total_scanned"], market_service.QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP)
        self.assertEqual(result["quote_available_count"], market_service.QUICK_OPPORTUNITY_QUOTE_SCREEN_CAP)
        self.assertIn("대표 1차 스캔 120개", result["universe_note"])

    async def test_get_cached_market_opportunities_quick_reuses_other_limit_when_usable(self):
        cached_payload = {
            "country_code": "KR",
            "snapshot_id": "KR:quick:20260329T120000",
            "generated_at": "2026-03-29T12:00:00",
            "fallback_tier": "quick",
            "market_regime": {
                "label": "KR 빠른 스냅샷",
                "stance": "neutral",
                "trend": "range",
                "volatility": "normal",
                "breadth": "mixed",
                "score": 50.0,
                "conviction": 38.0,
                "summary": "대표 후보 기준 빠른 응답입니다.",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 210,
            "total_scanned": 120,
            "quote_available_count": 84,
            "detailed_scanned_count": 0,
            "actionable_count": 6,
            "bullish_count": 5,
            "universe_source": "fallback",
            "universe_note": "대표 후보 cache",
            "opportunities": [
                {"ticker": "000001.KS", "action": "accumulate", "up_probability": 61.0},
                {"ticker": "000002.KS", "action": "breakout_watch", "up_probability": 58.0},
                {"ticker": "000003.KS", "action": "hold", "up_probability": 54.0},
                {"ticker": "000004.KS", "action": "reduce_risk", "up_probability": 47.0},
                {"ticker": "000005.KS", "action": "avoid", "up_probability": 38.0},
                {"ticker": "000006.KS", "action": "stay_selective", "up_probability": 56.0},
            ],
        }

        async def _cache_get(key: str):
            if key == market_service._quick_opportunity_cache_key("KR", 8):
                return cached_payload
            return None

        with patch("app.services.market_service.cache.get", new=AsyncMock(side_effect=_cache_get)):
            result = await market_service.get_cached_market_opportunities_quick("KR", limit=5)

        self.assertIsNotNone(result)
        self.assertEqual(len(result["opportunities"]), 5)
        self.assertEqual(result["actionable_count"], 4)
        self.assertEqual(result["bullish_count"], 2)
        self.assertIn("최근 usable quick 후보", result["universe_note"])
        self.assertEqual(result["quote_available_count"], 84)

    async def test_resolve_quick_opportunity_universe_uses_curated_kr_fallback_before_dynamic_fetch(self):
        with (
            patch("app.services.market_service.cache.get", new=AsyncMock(return_value=None)),
            patch(
                "app.services.market_service.resolve_universe",
                new=AsyncMock(side_effect=AssertionError("quick KR fallback should not wait for resolve_universe")),
            ),
        ):
            selection = await market_service._resolve_quick_opportunity_universe("KR")

        self.assertEqual(selection.source, "fallback")
        self.assertTrue(selection.sectors)
        self.assertIn("KRX 상장사 목록 캐시가 아직 준비되지 않아", selection.note)

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

    async def test_get_market_opportunities_skips_detailed_scan_for_large_kr_fallback_universe(self):
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
        tickers = [f"{index:06d}.KS" for index in range(130)]
        batch_quotes = {
            ticker: {
                "ticker": ticker,
                "current_price": 100.0 + index,
                "prev_close": 99.0 + index,
                "change_pct": round(0.2 + index * 0.01, 2),
                "session_date": "2026-03-26",
            }
            for index, ticker in enumerate(tickers)
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"Information Technology": tickers},
                        source="fallback",
                        note="test universe",
                    )
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(return_value=batch_quotes),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=AssertionError("detailed scan should be skipped")),
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
        ):
            result = await market_service.get_market_opportunities("KR", limit=12)

        self.assertEqual(result["universe_size"], 130)
        self.assertEqual(result["total_scanned"], 130)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 12)
        self.assertGreater(result["actionable_count"], 0)
        self.assertEqual(result["opportunities"][0]["setup_label"], "전수 1차 스캔")
        self.assertIn("운영 환경에서는 응답 안정성을 위해 1차 스캔 상위 후보를 우선 반환합니다.", result["universe_note"])

    async def test_get_market_opportunities_uses_full_krx_listing_universe_for_kr(self):
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
        tickers = [f"{index:06d}.KS" for index in range(2000, 2130)]
        batch_quotes = {
            ticker: {
                "ticker": ticker,
                "current_price": 100.0 + index,
                "prev_close": 99.0 + index,
                "change_pct": round(0.4 + index * 0.01, 2),
                "session_date": "2026-03-26",
            }
            for index, ticker in enumerate(tickers)
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"전자부품 제조업": tickers},
                        source="krx_listing",
                        note="KRX 상장사 목록 기준 전종목 130개를 1차 스캔합니다.",
                    )
                ),
            ),
            patch(
                "app.services.market_service.kr_market_quote_client.get_kr_bulk_quotes",
                new=AsyncMock(return_value=batch_quotes),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=AssertionError("detailed scan should be skipped for large KRX universe")),
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
        ):
            result = await market_service.get_market_opportunities("KR", limit=12)

        self.assertEqual(result["universe_source"], "krx_listing")
        self.assertEqual(result["universe_size"], 130)
        self.assertEqual(result["total_scanned"], 130)
        self.assertEqual(result["quote_available_count"], 130)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 12)
        self.assertGreater(result["actionable_count"], 0)
        self.assertIn("KRX 상장사 목록 기준 전종목", result["universe_note"])

    async def test_get_market_opportunities_falls_back_to_curated_universe_when_krx_quotes_are_empty(self):
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
        fallback_selection = SimpleNamespace(
            sectors={"Information Technology": ["005930.KS", "000660.KS"]},
            source="fallback",
            note="검증된 한국 기본 종목군으로 추천 중입니다.",
        )

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"전자부품 제조업": ["111111.KS", "222222.KS"]},
                        source="krx_listing",
                        note="KRX 상장사 목록 기준 전종목 2개를 1차 스캔합니다.",
                    )
                ),
            ),
            patch("app.services.market_service.resolve_universe", new=AsyncMock(return_value=fallback_selection)),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(
                    side_effect=[
                        {"universe_size": 2, "scanned_count": 2, "quote_available_count": 0, "ranked": []},
                        {
                            "universe_size": 2,
                            "scanned_count": 2,
                            "quote_available_count": 2,
                            "ranked": [
                                {"sector": "Information Technology", "ticker": "005930.KS", "current_price": 70100.0, "change_pct": 1.15},
                                {"sector": "Information Technology", "ticker": "000660.KS", "current_price": 201000.0, "change_pct": 1.26},
                            ],
                        },
                    ]
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=asyncio.TimeoutError()),
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
            patch("app.services.market_service.gather_limited", new=_gather_sequential),
        ):
            result = await market_service.get_market_opportunities("KR", limit=2, max_candidates=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(result["universe_source"], "fallback")
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("즉시 전환", result["universe_note"])

    async def test_get_market_opportunities_recovers_with_sampled_fallback_quote_screen(self):
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
        fallback_selection = SimpleNamespace(
            sectors={
                "Information Technology": ["005930.KS", "000660.KS"],
                "Communication Services": ["035420.KS", "051910.KS"],
            },
            source="fallback",
            note="검증된 한국 기본 종목군으로 추천 중입니다.",
        )

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service.resolve_opportunity_universe",
                new=AsyncMock(
                    return_value=SimpleNamespace(
                        sectors={"전자부품 제조업": ["111111.KS", "222222.KS"]},
                        source="krx_listing",
                        note="KRX 상장사 목록 기준 전종목 2개를 1차 스캔합니다.",
                    )
                ),
            ),
            patch("app.services.market_service.resolve_universe", new=AsyncMock(return_value=fallback_selection)),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(
                    side_effect=[
                        {"universe_size": 2, "scanned_count": 2, "quote_available_count": 0, "ranked": []},
                        {"universe_size": 4, "scanned_count": 4, "quote_available_count": 0, "ranked": []},
                        {
                            "universe_size": 4,
                            "scanned_count": 4,
                            "quote_available_count": 2,
                            "ranked": [
                                {"sector": "Information Technology", "ticker": "005930.KS", "current_price": 70100.0, "change_pct": 1.15},
                                {"sector": "Communication Services", "ticker": "035420.KS", "current_price": 197000.0, "change_pct": 0.82},
                            ],
                        },
                    ]
                ),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_price_history",
                new=AsyncMock(return_value=_sample_prices(90, 3000.0)),
            ),
            patch(
                "app.services.market_service.yfinance_client.get_market_snapshot",
                new=AsyncMock(side_effect=asyncio.TimeoutError()),
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
            patch("app.services.market_service.gather_limited", new=_gather_sequential),
        ):
            result = await market_service.get_market_opportunities("KR", limit=2, max_candidates=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(result["universe_source"], "fallback")
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("분산 샘플링", result["universe_note"])


if __name__ == "__main__":
    unittest.main()
