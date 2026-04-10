import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.forecast import FlowSignal, ForecastScenario, NextDayForecast
from app.models.market import (
    MarketRegime,
    MarketRegimeSignal,
    ShortTermChartAnalysis,
    ShortTermChartFactor,
    TradePlan,
)
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


async def _return_fetcher(key, fetcher, ttl=None, **kwargs):
    return await fetcher()


def _sample_chart_analysis(
    *,
    score: float = 74.0,
    signal: str = "bullish",
    entry_style: str = "pullback",
    caution_flags: list[str] | None = None,
) -> ShortTermChartAnalysis:
    return ShortTermChartAnalysis(
        score=score,
        signal=signal,
        summary="차트 정렬과 거래량 확인 신호를 함께 반영한 단타 점수입니다.",
        entry_style=entry_style,
        factors=[
            ShortTermChartFactor(
                key="trend_alignment",
                label="추세 정렬",
                signal="bullish",
                score=78.0,
                detail="EMA 정렬이 유지됩니다.",
            ),
            ShortTermChartFactor(
                key="extension_discipline",
                label="과열/변동성",
                signal="neutral",
                score=61.0,
                detail="과열 부담은 보통 수준입니다.",
            ),
        ],
        caution_flags=caution_flags or [],
    )


def _sample_focus_pick() -> market_service.NextDayFocusRecommendation:
    return market_service.NextDayFocusRecommendation(
        ticker="005930.KS",
        name="삼성전자",
        sector="Information Technology",
        country_code="KR",
        radar_rank=1,
        current_price=101.0,
        profit_probability=61.0,
        expected_return_pct=1.4,
        expected_edge_pct=0.85,
        selection_score=1.12,
        selection_summary="상승 확률과 예상 수익률을 함께 본 1일 실행 점수 기준 추천입니다.",
        thesis=["다음 거래일 장중 집중 대응 후보입니다."],
        risk_flags=["변동성 주의"],
        chart_analysis=_sample_chart_analysis(),
        next_day_forecast=NextDayForecast(
            target_date="2026-03-27",
            reference_date="2026-03-26",
            reference_price=101.0,
            direction="up",
            up_probability=61.0,
            predicted_open=101.2,
            predicted_close=102.4,
            predicted_high=103.3,
            predicted_low=100.4,
            predicted_return_pct=1.4,
            confidence=67.0,
            confidence_note="",
            news_sentiment=0.1,
            raw_signal=0.2,
            flow_signal=None,
            drivers=[],
            model_version="signal-v2.1",
        ),
        trade_plan=TradePlan(
            setup_label="다음 거래일 집중 매수",
            action="accumulate",
            conviction=68.0,
            entry_low=100.9,
            entry_high=101.4,
            stop_loss=99.8,
            take_profit_1=102.4,
            take_profit_2=103.3,
            expected_holding_days=1,
            risk_reward_estimate=1.45,
            thesis=["손절과 목표가를 하루 플랜 기준으로 고정합니다."],
            invalidation="장중 손절가를 이탈하면 시나리오 종료입니다.",
        ),
    )


def _focus_source_item(
    *,
    rank: int,
    ticker: str,
    change_pct: float,
    opportunity_score: float,
    action: str = "accumulate",
    risk_reward_estimate: float = 1.4,
) -> market_service.OpportunityItem:
    return market_service.OpportunityItem(
        rank=rank,
        ticker=ticker,
        name=ticker,
        sector="Information Technology",
        country_code="KR",
        current_price=100.0,
        change_pct=change_pct,
        opportunity_score=opportunity_score,
        quant_score=62.0,
        up_probability=58.0,
        confidence=60.0,
        predicted_return_pct=4.0,
        target_horizon_days=20,
        expected_return_pct_20d=4.0,
        up_probability_20d=58.0,
        setup_label="포커스 후보",
        action=action,
        regime_tailwind="tailwind",
        entry_low=99.0,
        entry_high=101.0,
        stop_loss=96.0,
        take_profit_1=104.0,
        take_profit_2=106.0,
        risk_reward_estimate=risk_reward_estimate,
        thesis=["focus"],
        risk_flags=[],
        forecast_date="2026-03-26",
    )


class MarketServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.focus_patch = patch(
            "app.services.market_service._build_next_day_focus_recommendation",
            new=AsyncMock(return_value=None),
        )
        self.focus_patch.start()
        self.addCleanup(self.focus_patch.stop)

    def test_quote_only_scores_preserve_spread_for_hot_kr_names(self):
        market_regime = MarketRegime(
            label="중립",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=50.0,
            conviction=38.0,
            summary="중립 장세",
            playbook=[],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.0, signal="neutral", detail="mixed breadth")],
        )

        items = market_service._build_quote_only_opportunities(
            ranked_quotes=[
                {"sector": "IT", "ticker": "A.KS", "current_price": 100.0, "change_pct": 14.09},
                {"sector": "IT", "ticker": "B.KS", "current_price": 99.0, "change_pct": 13.40},
                {"sector": "IT", "ticker": "C.KS", "current_price": 98.0, "change_pct": 11.39},
            ],
            country_code="KR",
            market_regime=market_regime,
            limit=3,
        )

        scores = [item.opportunity_score for item in items]
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], scores[2])
        self.assertLessEqual(scores[0], 86.0)

    def test_focus_source_selection_penalizes_recent_surges(self):
        hot = _focus_source_item(rank=1, ticker="HOT.KS", change_pct=11.8, opportunity_score=86.0)
        calm = _focus_source_item(rank=6, ticker="CALM.KS", change_pct=2.1, opportunity_score=82.0)

        selected = market_service._select_focus_source_items([hot, calm], limit=2)

        self.assertEqual(selected[0].ticker, "CALM.KS")
        self.assertGreater(
            market_service._focus_source_seed_score(calm),
            market_service._focus_source_seed_score(hot),
        )

    async def test_next_day_focus_can_pick_candidate_outside_initial_top_three(self):
        self.focus_patch.stop()
        market_regime = MarketRegime(
            label="상승 우위",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=72.0,
            conviction=64.0,
            summary="시장 참여가 안정적입니다.",
            playbook=["강한 종목 선별"],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.7, signal="bullish", detail="breadth strong")],
        )
        candidates = [
            _focus_source_item(rank=1, ticker="HOT1.KS", change_pct=12.0, opportunity_score=90.0),
            _focus_source_item(rank=2, ticker="HOT2.KS", change_pct=10.5, opportunity_score=89.0),
            _focus_source_item(rank=3, ticker="HOT3.KS", change_pct=8.7, opportunity_score=88.0),
            _focus_source_item(rank=4, ticker="CALM1.KS", change_pct=2.4, opportunity_score=82.0),
            _focus_source_item(rank=5, ticker="CALM2.KS", change_pct=1.8, opportunity_score=81.5),
        ]
        seen_snapshots: list[str] = []

        async def _snapshot(ticker: str, period: str = "6mo"):
            seen_snapshots.append(ticker)
            return {"valid": True, "current_price": 100.0}

        async def _stock_info(ticker: str):
            return {"name": ticker, "current_price": 100.0}

        def _forecast(*, ticker: str, **kwargs):
            predicted_return = {
                "HOT1.KS": 1.05,
                "HOT2.KS": 1.02,
                "HOT3.KS": 1.0,
                "CALM1.KS": 1.14,
                "CALM2.KS": 1.18,
            }[ticker]
            up_probability = {
                "HOT1.KS": 59.0,
                "HOT2.KS": 58.0,
                "HOT3.KS": 57.0,
                "CALM1.KS": 61.0,
                "CALM2.KS": 62.0,
            }[ticker]
            return NextDayForecast(
                target_date="2026-03-27",
                reference_date="2026-03-26",
                reference_price=100.0,
                direction="up",
                up_probability=up_probability,
                predicted_open=100.1,
                predicted_close=round(100.0 * (1.0 + predicted_return / 100.0), 2),
                predicted_high=round(100.0 * (1.0 + (predicted_return + 0.9) / 100.0), 2),
                predicted_low=99.1,
                predicted_return_pct=predicted_return,
                confidence=66.0,
                confidence_note="",
                news_sentiment=0.0,
                raw_signal=0.0,
                flow_signal=None,
                drivers=[],
                model_version="signal-v2.1",
                execution_bias="lean_long",
                execution_note="다음 거래일 테스트",
            )

        def _trade_plan(*, ticker: str, **kwargs):
            rr = 1.05 if ticker.startswith("HOT") else 1.35
            tp1 = 101.0 if ticker.startswith("HOT") else 101.6
            tp2 = 101.8 if ticker.startswith("HOT") else 102.5
            return TradePlan(
                setup_label="다음 거래일 매수",
                action="accumulate",
                conviction=68.0,
                entry_low=99.7,
                entry_high=100.3,
                stop_loss=98.6,
                take_profit_1=tp1,
                take_profit_2=tp2,
                expected_holding_days=1,
                risk_reward_estimate=rr,
                thesis=["다음 거래일 테스트"],
                invalidation="손절가 이탈 시 종료",
            )

        buy_sell = BuySellGuide(
            buy_zone_low=99.0,
            buy_zone_high=101.0,
            fair_value=105.0,
            sell_zone_low=106.0,
            sell_zone_high=109.0,
            risk_reward_ratio=1.8,
            confidence_grade="A",
            methodology=[ValuationMethod(name="blend", value=105.0, weight=1.0, details="test")],
            summary="테스트",
        )
        technical = TechnicalIndicators(
            ma_20=[99.5],
            ma_60=[97.0],
            rsi_14=[56.0],
            macd=[0.4],
            macd_signal=[0.3],
            macd_hist=[0.1],
            dates=["2026-03-26"],
        )
        gather_errors: list[str] = []
        async def _gather_safe(items, worker, limit=6):
            results = []
            for item in items:
                try:
                    results.append(await worker(item))
                except Exception as exc:  # pragma: no cover - keeps focus selection test deterministic
                    gather_errors.append(repr(exc))
                    results.append(exc)
            return results

        with (
            patch("app.services.market_service.gather_limited", new=AsyncMock(side_effect=_gather_safe)),
            patch("app.services.market_service.yfinance_client.get_market_snapshot", new=AsyncMock(side_effect=_snapshot)),
            patch("app.services.market_service.yfinance_client.get_stock_info", new=AsyncMock(side_effect=_stock_info)),
            patch("app.services.market_service.yfinance_client.get_price_history", new=AsyncMock(return_value=_sample_prices(90, 100.0))),
            patch("app.services.market_service.yfinance_client.get_analyst_ratings", new=AsyncMock(return_value={})),
            patch("app.services.market_service.build_quick_buy_sell", return_value=buy_sell),
            patch("app.services.market_service._calc_technicals", return_value=technical),
            patch("app.services.market_service.forecast_next_day", side_effect=_forecast),
            patch("app.services.market_service.build_short_horizon_trade_plan", side_effect=_trade_plan),
        ):
            focus = await market_service._build_next_day_focus_recommendation(
                source_items=candidates,
                country_code="KR",
                market_regime=market_regime,
            )

        self.assertFalse(gather_errors, gather_errors)
        self.assertGreater(len(seen_snapshots), 3, seen_snapshots)
        self.assertIsNotNone(focus)
        self.assertEqual(focus.ticker, "CALM2.KS")
        self.assertIn("CALM2.KS", seen_snapshots)

    async def test_next_day_focus_weights_chart_analysis_heavily(self):
        self.focus_patch.stop()
        market_regime = MarketRegime(
            label="중립",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=58.0,
            conviction=52.0,
            summary="중립 장세입니다.",
            playbook=[],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.0, signal="neutral", detail="mixed breadth")],
        )
        candidates = [
            _focus_source_item(rank=1, ticker="RET.KS", change_pct=1.7, opportunity_score=84.0),
            _focus_source_item(rank=2, ticker="CHART.KS", change_pct=1.4, opportunity_score=82.0),
        ]

        async def _snapshot(ticker: str, period: str = "6mo"):
            return {"valid": True, "current_price": 100.0}

        async def _stock_info(ticker: str):
            return {"name": ticker, "current_price": 100.0}

        def _forecast(*, ticker: str, **kwargs):
            predicted_return = 2.1 if ticker == "RET.KS" else 1.35
            return NextDayForecast(
                target_date="2026-03-27",
                reference_date="2026-03-26",
                reference_price=100.0,
                direction="up",
                up_probability=61.0 if ticker == "RET.KS" else 59.0,
                predicted_open=100.1,
                predicted_close=round(100.0 * (1.0 + predicted_return / 100.0), 2),
                predicted_high=round(100.0 * (1.0 + (predicted_return + 0.8) / 100.0), 2),
                predicted_low=99.2,
                predicted_return_pct=predicted_return,
                confidence=66.0,
                confidence_note="",
                news_sentiment=0.0,
                raw_signal=0.0,
                flow_signal=None,
                drivers=[],
                model_version="signal-v2.1",
                execution_bias="lean_long",
                execution_note="장중 대응 테스트",
            )

        def _trade_plan(*, ticker: str, **kwargs):
            return TradePlan(
                setup_label="다음 거래일 매수",
                action="accumulate",
                conviction=68.0,
                entry_low=99.8,
                entry_high=100.3,
                stop_loss=98.7,
                take_profit_1=101.7,
                take_profit_2=102.6,
                expected_holding_days=1,
                risk_reward_estimate=1.35,
                thesis=["단타 테스트"],
                invalidation="손절가 이탈 시 종료",
            )

        buy_sell = BuySellGuide(
            buy_zone_low=99.0,
            buy_zone_high=101.0,
            fair_value=105.0,
            sell_zone_low=106.0,
            sell_zone_high=109.0,
            risk_reward_ratio=1.8,
            confidence_grade="A",
            methodology=[ValuationMethod(name="blend", value=105.0, weight=1.0, details="test")],
            summary="테스트",
        )
        technical = TechnicalIndicators(
            ma_20=[99.5],
            ma_60=[97.0],
            rsi_14=[56.0],
            macd=[0.4],
            macd_signal=[0.3],
            macd_hist=[0.1],
            dates=["2026-03-26"],
        )

        async def _gather_safe(items, worker, limit=6):
            results = []
            for item in items:
                results.append(await worker(item))
            return results

        with (
            patch("app.services.market_service.gather_limited", new=AsyncMock(side_effect=_gather_safe)),
            patch("app.services.market_service.yfinance_client.get_market_snapshot", new=AsyncMock(side_effect=_snapshot)),
            patch("app.services.market_service.yfinance_client.get_stock_info", new=AsyncMock(side_effect=_stock_info)),
            patch("app.services.market_service.yfinance_client.get_price_history", new=AsyncMock(return_value=_sample_prices(90, 100.0))),
            patch("app.services.market_service.yfinance_client.get_analyst_ratings", new=AsyncMock(return_value={})),
            patch("app.services.market_service.build_quick_buy_sell", return_value=buy_sell),
            patch("app.services.market_service._calc_technicals", return_value=technical),
            patch("app.services.market_service.forecast_next_day", side_effect=_forecast),
            patch("app.services.market_service.build_short_horizon_trade_plan", side_effect=_trade_plan),
            patch(
                "app.services.market_service.build_short_horizon_chart_analysis",
                side_effect=[
                    _sample_chart_analysis(
                        score=38.0,
                        signal="bearish",
                        entry_style="stand_aside",
                        caution_flags=["과열 부담", "상단 이격 확대"],
                    ),
                    _sample_chart_analysis(
                        score=79.0,
                        signal="bullish",
                        entry_style="pullback",
                    ),
                ],
            ),
        ):
            focus = await market_service._build_next_day_focus_recommendation(
                source_items=candidates,
                country_code="KR",
                market_regime=market_regime,
            )

        self.assertIsNotNone(focus)
        self.assertEqual(focus.ticker, "CHART.KS")
        self.assertGreater(focus.chart_analysis.score, 70.0)

    async def test_next_day_focus_sanitizes_non_finite_forecast_values_for_json(self):
        self.focus_patch.stop()
        market_regime = MarketRegime(
            label="중립",
            stance="neutral",
            trend="range",
            volatility="normal",
            breadth="mixed",
            score=58.0,
            conviction=52.0,
            summary="중립 장세입니다.",
            playbook=[],
            warnings=[],
            signals=[MarketRegimeSignal(name="breadth", value=0.0, signal="neutral", detail="mixed breadth")],
        )
        candidates = [
            _focus_source_item(rank=1, ticker="SANITIZE.KS", change_pct=1.1, opportunity_score=81.0),
        ]

        async def _snapshot(ticker: str, period: str = "6mo"):
            return {"valid": True, "current_price": 100.0}

        async def _stock_info(ticker: str):
            return {"name": ticker, "current_price": 100.0}

        forecast = NextDayForecast(
            target_date="2026-03-27",
            reference_date="2026-03-26",
            reference_price=100.0,
            direction="up",
            up_probability=float("nan"),
            predicted_open=float("nan"),
            predicted_close=101.2,
            predicted_high=102.8,
            predicted_low=99.4,
            predicted_return_pct=float("nan"),
            confidence=float("nan"),
            raw_confidence=float("nan"),
            calibrated_probability=float("nan"),
            probability_edge=float("nan"),
            analog_support=float("nan"),
            regime_support=float("nan"),
            agreement_support=float("nan"),
            data_quality_support=float("nan"),
            volatility_ratio=float("nan"),
            calibration_snapshot={
                "gap": float("nan"),
                "bins": [0.1, float("nan"), 0.3],
            },
            confidence_note="",
            news_sentiment=float("nan"),
            raw_signal=float("nan"),
            scenarios=[
                ForecastScenario(name="Bull", price=float("nan"), probability=float("nan"), description="상방"),
            ],
            flow_signal=FlowSignal(
                available=True,
                source="test",
                market="KR",
                unit="krw",
                foreign_net_buy=float("nan"),
                institutional_net_buy=float("nan"),
                retail_net_buy=float("nan"),
            ),
            drivers=[],
            model_version="signal-v2.1",
            execution_bias="lean_long",
            execution_note="장중 대응 테스트",
        )
        buy_sell = BuySellGuide(
            buy_zone_low=99.0,
            buy_zone_high=101.0,
            fair_value=105.0,
            sell_zone_low=106.0,
            sell_zone_high=109.0,
            risk_reward_ratio=1.8,
            confidence_grade="A",
            methodology=[ValuationMethod(name="blend", value=105.0, weight=1.0, details="test")],
            summary="테스트",
        )
        technical = TechnicalIndicators(
            ma_20=[99.5],
            ma_60=[97.0],
            rsi_14=[56.0],
            macd=[0.4],
            macd_signal=[0.3],
            macd_hist=[0.1],
            dates=["2026-03-26"],
        )
        trade_plan = TradePlan(
            setup_label="다음 거래일 매수",
            action="accumulate",
            conviction=68.0,
            entry_low=99.8,
            entry_high=100.3,
            stop_loss=98.7,
            take_profit_1=101.7,
            take_profit_2=102.6,
            expected_holding_days=1,
            risk_reward_estimate=float("nan"),
            thesis=["단타 테스트"],
            invalidation="손절가 이탈 시 종료",
        )

        async def _gather_safe(items, worker, limit=6):
            results = []
            for item in items:
                results.append(await worker(item))
            return results

        with (
            patch("app.services.market_service.gather_limited", new=AsyncMock(side_effect=_gather_safe)),
            patch("app.services.market_service.yfinance_client.get_market_snapshot", new=AsyncMock(side_effect=_snapshot)),
            patch("app.services.market_service.yfinance_client.get_stock_info", new=AsyncMock(side_effect=_stock_info)),
            patch("app.services.market_service.yfinance_client.get_price_history", new=AsyncMock(return_value=_sample_prices(90, 100.0))),
            patch("app.services.market_service.yfinance_client.get_analyst_ratings", new=AsyncMock(return_value={})),
            patch("app.services.market_service.build_quick_buy_sell", return_value=buy_sell),
            patch("app.services.market_service._calc_technicals", return_value=technical),
            patch("app.services.market_service.forecast_next_day", return_value=forecast),
            patch("app.services.market_service.build_short_horizon_trade_plan", return_value=trade_plan),
            patch(
                "app.services.market_service.build_short_horizon_chart_analysis",
                return_value=_sample_chart_analysis(score=float("nan")),
            ),
        ):
            focus = await market_service._build_next_day_focus_recommendation(
                source_items=candidates,
                country_code="KR",
                market_regime=market_regime,
            )

        self.assertIsNotNone(focus)
        self.assertEqual(focus.expected_return_pct, 0.0)
        self.assertEqual(focus.profit_probability, 0.0)
        self.assertEqual(focus.expected_edge_pct, 0.0)
        self.assertEqual(focus.next_day_forecast.predicted_return_pct, 0.0)
        self.assertEqual(focus.next_day_forecast.up_probability, 0.0)
        self.assertEqual(focus.trade_plan.risk_reward_estimate, 0.0)
        self.assertEqual(focus.chart_analysis.score, 0.0)
        json.dumps(focus.model_dump(), allow_nan=False)

    def test_build_seeded_quote_screen_from_quick_payload_restores_ranked_candidates(self):
        payload = {
            "universe_size": 200,
            "total_scanned": 200,
            "quote_available_count": 72,
            "universe_source": "kr_top200",
            "universe_note": "cached quick",
            "opportunities": [
                {
                    "ticker": "047810.KS",
                    "sector": "항공기/우주선 및 부품 제조업",
                    "current_price": 187900.0,
                    "change_pct": 14.09,
                },
                {
                    "ticker": "005930.KS",
                    "sector": "통신 및 방송 장비 제조업",
                    "current_price": 189600.0,
                    "change_pct": 13.40,
                },
            ],
        }

        result = market_service._build_seeded_quote_screen_from_quick_payload(payload, candidate_limit=4)

        self.assertIsNotNone(result)
        selection, quote_screen = result
        self.assertEqual(selection.source, "kr_top200")
        self.assertIn("seed로 정밀 후보 계산", selection.note)
        self.assertEqual(quote_screen["universe_size"], 200)
        self.assertEqual(quote_screen["quote_available_count"], 72)
        self.assertEqual(len(quote_screen["ranked"]), 2)
        self.assertEqual(quote_screen["ranked"][0]["ticker"], "047810.KS")

    def test_can_reuse_quick_seed_payload_requires_matching_source_size_and_coverage(self):
        payload = {
            "universe_source": "kr_top200",
            "universe_size": 200,
            "total_scanned": 72,
            "quote_available_count": 72,
        }
        selection = SimpleNamespace(
            sectors={"Information Technology": ["005930.KS", "000660.KS"]},
            source="fallback",
            note="test universe",
        )

        self.assertFalse(market_service._can_reuse_quick_seed_payload(payload, selection))

        selection = SimpleNamespace(
            sectors={"Information Technology": ["005930.KS", "000660.KS"]},
            source="kr_top200",
            note="test universe",
        )

        self.assertFalse(market_service._can_reuse_quick_seed_payload(payload, selection))

        tickers = [f"{index:06d}.KS" for index in range(200)]
        selection = SimpleNamespace(
            sectors={"Information Technology": tickers},
            source="kr_top200",
            note="test universe",
        )

        self.assertFalse(market_service._can_reuse_quick_seed_payload(payload, selection))

        payload["total_scanned"] = 200
        payload["quote_available_count"] = 200

        self.assertTrue(market_service._can_reuse_quick_seed_payload(payload, selection))

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

        async def _cached_only(_key, _fetcher, ttl=None, **kwargs):
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
        focus_pick = _sample_focus_pick()
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
                "app.services.market_service._resolve_quick_opportunity_universe",
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
            patch("app.services.market_service._build_next_day_focus_recommendation", new=AsyncMock(return_value=focus_pick)),
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
        self.assertIsNotNone(result["next_day_focus"])
        self.assertEqual(result["next_day_focus"]["ticker"], "005930.KS")
        self.assertEqual(result["next_day_focus"]["trade_plan"]["expected_holding_days"], 1)
        self.assertEqual(result["opportunities"][0]["ticker"], "005930.KS")
        self.assertGreater(result["opportunities"][0]["predicted_return_pct"], 0.0)
        json.dumps(result, allow_nan=False)

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
                "app.services.market_service._resolve_quick_opportunity_universe",
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
        focus_pick = _sample_focus_pick()
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
                "app.services.market_service._resolve_quick_opportunity_universe",
                new=AsyncMock(return_value=fallback_selection),
            ),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(return_value=fallback_screen),
            ),
            patch("app.services.market_service._build_next_day_focus_recommendation", new=AsyncMock(return_value=focus_pick)),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertIn("snapshot_id", result)
        self.assertEqual(result["fallback_tier"], "quick")
        self.assertEqual(result["universe_size"], 2)
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIsNotNone(result["next_day_focus"])
        self.assertEqual(result["next_day_focus"]["trade_plan"]["expected_holding_days"], 1)
        self.assertIn("1차 시세 스캔 후보", result["universe_note"])

    async def test_get_market_opportunities_quick_falls_back_to_curated_universe_when_top200_quotes_are_empty(self):
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
            patch("app.services.market_service._build_kr_radar_quote_screen", new=AsyncMock(return_value=None)),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(return_value=fallback_screen),
            ),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=2)

        self.assertEqual(result["country_code"], "KR")
        self.assertEqual(result["universe_source"], "fallback")
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("190/10 레이더로 다시 전환", result["universe_note"])

    async def test_get_market_opportunities_quick_prefers_top200_quotes_for_kr_before_quote_screen(self):
        top200_selection = SimpleNamespace(
            sectors={
                "Information Technology": ["005930.KS", "000660.KS"],
                "Communication Services": ["035420.KS"],
            },
            source="kr_top200",
            note="코스피 시가총액 상위 190개와 코스닥 상위 10개를 먼저 스캔합니다.",
        )
        radar_quote_screen = {
            "universe_size": 3,
            "scanned_count": 3,
            "quote_available_count": 3,
            "ranked": [
                {"sector": "Information Technology", "ticker": "005930.KS", "current_price": 70100.0, "change_pct": 1.15},
                {"sector": "Communication Services", "ticker": "035420.KS", "current_price": 223000.0, "change_pct": 1.13},
                {"sector": "Information Technology", "ticker": "000660.KS", "current_price": 201000.0, "change_pct": 0.88},
            ],
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service._resolve_quick_opportunity_universe",
                new=AsyncMock(return_value=top200_selection),
            ),
            patch(
                "app.services.market_service._build_kr_radar_quote_screen",
                new=AsyncMock(return_value=(top200_selection, radar_quote_screen)),
            ),
            patch(
                "app.services.market_service._resolve_resilient_quote_screen",
                new=AsyncMock(side_effect=AssertionError("top200 quick path should skip fallback quote screen")),
            ),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=2)

        self.assertEqual(result["universe_source"], "kr_top200")
        self.assertEqual(result["quote_available_count"], 3)
        self.assertEqual(result["total_scanned"], 3)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("코스피 상위 190개와 코스닥 상위 10개", result["universe_note"])
        self.assertEqual(result["opportunities"][0]["ticker"], "005930.KS")

    async def test_get_market_opportunities_quick_uses_full_top200_quote_screen_when_available(self):
        tickers = [f"{index:06d}.KS" for index in range(1, 201)]
        top200_selection = SimpleNamespace(
            sectors={"Information Technology": tickers},
            source="kr_top200",
            note="코스피 시가총액 상위 190개와 코스닥 상위 10개를 먼저 스캔합니다.",
        )
        radar_quote_screen = {
            "universe_size": 200,
            "scanned_count": 200,
            "quote_available_count": 200,
            "ranked": [
                {
                    "sector": "Information Technology",
                    "ticker": ticker,
                    "current_price": 100.0 + index,
                    "change_pct": round(0.3 + index * 0.01, 2),
                }
                for index, ticker in enumerate(tickers)
            ],
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service._resolve_quick_opportunity_universe",
                new=AsyncMock(return_value=top200_selection),
            ),
            patch(
                "app.services.market_service._build_kr_radar_quote_screen",
                new=AsyncMock(return_value=(top200_selection, radar_quote_screen)),
            ),
            patch(
                "app.services.market_service._resolve_resilient_quote_screen",
                new=AsyncMock(side_effect=AssertionError("top200 quick path should not cap to fallback quote screen")),
            ),
        ):
            result = await market_service.get_market_opportunities_quick("KR", limit=5)

        self.assertEqual(result["universe_source"], "kr_top200")
        self.assertEqual(result["universe_size"], 200)
        self.assertEqual(result["total_scanned"], 200)
        self.assertEqual(result["quote_available_count"], 200)
        self.assertIn("코스피 상위 190개와 코스닥 상위 10개", result["universe_note"])

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

    async def test_get_cached_market_opportunities_returns_usable_full_snapshot(self):
        cached_payload = {
            "country_code": "KR",
            "snapshot_id": "KR:full:20260329T120000",
            "generated_at": "2026-03-29T12:00:00",
            "fallback_tier": "full",
            "market_regime": {
                "label": "KR",
                "stance": "neutral",
                "trend": "range",
                "volatility": "normal",
                "breadth": "mixed",
                "score": 50.0,
                "conviction": 40.0,
                "summary": "cached",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 210,
            "total_scanned": 120,
            "quote_available_count": 84,
            "detailed_scanned_count": 12,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "fallback",
            "universe_note": "cached full",
            "opportunities": [{"ticker": "005930.KS"}],
        }

        with patch("app.services.market_service.cache.get", new=AsyncMock(return_value=cached_payload)):
            result = await market_service.get_cached_market_opportunities("KR", limit=12)

        self.assertIsNotNone(result)
        self.assertEqual(result["fallback_tier"], "full")
        self.assertEqual(result["quote_available_count"], 84)

    async def test_get_cached_market_opportunities_ignores_partially_scanned_quote_only_full_snapshot(self):
        cached_payload = {
            "country_code": "KR",
            "snapshot_id": "KR:full:20260329T120500",
            "generated_at": "2026-03-29T12:05:00",
            "fallback_tier": "full",
            "market_regime": {
                "label": "KR",
                "stance": "neutral",
                "trend": "range",
                "volatility": "normal",
                "breadth": "mixed",
                "score": 50.0,
                "conviction": 40.0,
                "summary": "cached",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 200,
            "total_scanned": 72,
            "quote_available_count": 72,
            "detailed_scanned_count": 0,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "kr_top200",
            "universe_note": "cached quick-like full",
            "opportunities": [{"ticker": "005930.KS", "current_price": 70100.0, "change_pct": 4.1}],
        }

        with patch("app.services.market_service.cache.get", new=AsyncMock(return_value=cached_payload)):
            result = await market_service.get_cached_market_opportunities("KR", limit=12)

        self.assertIsNone(result)

    async def test_get_cached_market_opportunities_returns_full_quote_only_snapshot_when_scan_finished(self):
        cached_payload = {
            "country_code": "KR",
            "snapshot_id": "KR:full:20260329T120500",
            "generated_at": "2026-03-29T12:05:00",
            "fallback_tier": "full",
            "market_regime": {
                "label": "KR",
                "stance": "neutral",
                "trend": "range",
                "volatility": "normal",
                "breadth": "mixed",
                "score": 50.0,
                "conviction": 40.0,
                "summary": "cached",
                "playbook": [],
                "warnings": [],
                "signals": [],
            },
            "universe_size": 200,
            "total_scanned": 200,
            "quote_available_count": 72,
            "detailed_scanned_count": 0,
            "actionable_count": 8,
            "bullish_count": 5,
            "universe_source": "kr_top200",
            "universe_note": "cached quote-only full",
            "opportunities": [{"ticker": "005930.KS", "current_price": 70100.0, "change_pct": 4.1}],
        }

        with patch("app.services.market_service.cache.get", new=AsyncMock(return_value=cached_payload)):
            result = await market_service.get_cached_market_opportunities("KR", limit=12)

        self.assertIsNotNone(result)
        self.assertTrue(result["partial"])
        self.assertEqual(result["fallback_reason"], "opportunity_quote_only_full")
        self.assertIn("대표 200종목 1차 스캔 결과", result["universe_note"])

    async def test_resolve_quick_opportunity_universe_uses_kr_top200_when_quotes_exist(self):
        fetched_selection = SimpleNamespace(
            sectors={"Information Technology": ["005930.KS", "000660.KS", "035420.KS"]},
            source="kr_top200",
            note="fetched representative top200",
        )

        with patch(
            "app.services.market_service._build_kr_radar_quote_screen",
            new=AsyncMock(return_value=(fetched_selection, {"ranked": []})),
        ):
            selection = await market_service._resolve_quick_opportunity_universe("KR")

        self.assertEqual(selection.source, "kr_top200")
        self.assertEqual(sum(len(v) for v in selection.sectors.values()), 3)

    async def test_resolve_quick_opportunity_universe_uses_curated_kr_fallback_when_top200_quotes_are_empty(self):
        with (
            patch("app.services.market_service._build_kr_radar_quote_screen", new=AsyncMock(return_value=None)),
        ):
            selection = await market_service._resolve_quick_opportunity_universe("KR")

        self.assertEqual(selection.source, "fallback")
        self.assertTrue(selection.sectors)
        self.assertIn("대표 200종목 시세가 아직 비어", selection.note)

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
                "app.services.market_service._resolve_quick_opportunity_universe",
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

    async def test_get_market_opportunities_uses_top200_universe_for_kr(self):
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
        radar_selection = SimpleNamespace(
            sectors={"전자부품 제조업": tickers},
            source="kr_top200",
            note="코스피 시가총액 상위 190개와 코스닥 상위 10개를 먼저 스캔합니다.",
        )
        radar_quote_screen = {
            "universe_size": 200,
            "scanned_count": 200,
            "quote_available_count": 130,
            "ranked": [
                {
                    "sector": "전자부품 제조업",
                    "ticker": ticker,
                    "current_price": 100.0 + index,
                    "change_pct": round(0.4 + index * 0.01, 2),
                }
                for index, ticker in enumerate(tickers)
            ],
        }

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch("app.services.market_service.cache.get", new=AsyncMock(return_value=None)),
            patch(
                "app.services.market_service._resolve_quick_opportunity_universe",
                new=AsyncMock(return_value=radar_selection),
            ),
            patch(
                "app.services.market_service._build_kr_radar_quote_screen",
                new=AsyncMock(return_value=(radar_selection, radar_quote_screen)),
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
        ):
            result = await market_service.get_market_opportunities("KR", limit=12)

        self.assertEqual(result["universe_source"], "kr_top200")
        self.assertEqual(result["universe_size"], 200)
        self.assertEqual(result["total_scanned"], 200)
        self.assertEqual(result["quote_available_count"], 130)
        self.assertEqual(result["detailed_scanned_count"], 0)
        self.assertEqual(len(result["opportunities"]), 12)
        self.assertGreater(result["actionable_count"], 0)
        self.assertIn("코스피 시가총액 상위 190개와 코스닥 상위 10개", result["universe_note"])

    async def test_get_market_opportunities_falls_back_to_curated_universe_when_top200_quotes_are_empty(self):
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
            note="대표 200종목 시세가 아직 비어 운영용 기본 종목군으로 먼저 1차 스캔합니다.",
        )

        with (
            patch("app.services.market_service.cache.get_or_fetch", new=AsyncMock(side_effect=_return_fetcher)),
            patch(
                "app.services.market_service._resolve_quick_opportunity_universe",
                new=AsyncMock(return_value=fallback_selection),
            ),
            patch(
                "app.services.market_service._build_quote_screen",
                new=AsyncMock(
                    return_value={
                        "universe_size": 2,
                        "scanned_count": 2,
                        "quote_available_count": 2,
                        "ranked": [
                            {"sector": "Information Technology", "ticker": "005930.KS", "current_price": 70100.0, "change_pct": 1.15},
                            {"sector": "Information Technology", "ticker": "000660.KS", "current_price": 201000.0, "change_pct": 1.26},
                        ],
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
        self.assertEqual(result["universe_source"], "fallback")
        self.assertEqual(result["quote_available_count"], 2)
        self.assertEqual(len(result["opportunities"]), 2)
        self.assertIn("대표 200종목 시세가 아직 비어", result["universe_note"])


if __name__ == "__main__":
    unittest.main()
