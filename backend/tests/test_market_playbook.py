import unittest
from datetime import date, timedelta
from types import SimpleNamespace

from app.analysis.market_regime import build_market_regime
from app.analysis.trade_planner import build_short_horizon_trade_plan, build_trade_plan, build_weekly_trade_plan
from app.models.forecast import NextDayForecast
from app.models.market import MarketRegime
from app.models.stock import BuySellGuide, PricePoint, TechnicalIndicators


def _price_series(days: int = 80, start: float = 100.0, drift: float = 0.4) -> list[dict]:
    results = []
    current = start
    day = date(2026, 1, 1)
    for idx in range(days):
        current *= 1 + (drift / 100.0)
        results.append(
            {
                "date": (day + timedelta(days=idx)).isoformat(),
                "open": round(current * 0.995, 2),
                "high": round(current * 1.01, 2),
                "low": round(current * 0.99, 2),
                "close": round(current, 2),
                "volume": 1_000_000 + idx * 1000,
            }
        )
    return results


class MarketPlaybookTests(unittest.TestCase):
    def test_market_regime_detects_uptrend(self):
        regime = build_market_regime(
            country_code="KR",
            name="KOSPI",
            price_history=_price_series(),
            breadth_ratio=0.8,
        )
        self.assertEqual(regime.stance, "risk_on")
        self.assertEqual(regime.trend, "uptrend")
        self.assertGreater(regime.score, 55)

    def test_trade_plan_builds_actionable_setup(self):
        history = [PricePoint(**row) for row in _price_series()]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [126.0],
            ma_60=[None] * 79 + [118.0],
            rsi_14=[None] * 79 + [48.0],
            macd=[None] * 79 + [1.2],
            macd_signal=[None] * 79 + [0.9],
            macd_hist=[None] * 79 + [0.3],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=120.0,
            buy_zone_high=124.0,
            fair_value=132.0,
            sell_zone_low=138.0,
            sell_zone_high=142.0,
            risk_reward_ratio=2.0,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        forecast = NextDayForecast(
            target_date="2026-03-23",
            reference_date="2026-03-20",
            reference_price=123.0,
            direction="up",
            up_probability=64.0,
            predicted_open=123.5,
            predicted_close=125.0,
            predicted_high=127.0,
            predicted_low=122.0,
            predicted_return_pct=1.6,
            confidence=68.0,
            confidence_note="",
            news_sentiment=0.2,
            raw_signal=0.4,
            flow_signal=None,
            drivers=[],
            model_version="signal-v2.1",
        )
        regime = MarketRegime(
            label="Risk-On Trend",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=68.0,
            conviction=71.0,
            summary="",
            playbook=[],
            warnings=[],
            signals=[],
        )

        plan = build_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            next_day_forecast=forecast,
            market_regime=regime,
        )

        self.assertIn(plan.action, {"accumulate", "breakout_watch"})
        self.assertIsNotNone(plan.stop_loss)
        self.assertIsNotNone(plan.take_profit_1)

    def test_trade_plan_prefers_reduce_risk_in_risk_off_premium_setup(self):
        history = [PricePoint(**row) for row in _price_series(drift=0.18)]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [124.0],
            ma_60=[None] * 79 + [121.0],
            rsi_14=[None] * 79 + [54.0],
            macd=[None] * 79 + [0.2],
            macd_signal=[None] * 79 + [0.25],
            macd_hist=[None] * 79 + [-0.1],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=116.0,
            buy_zone_high=119.0,
            fair_value=120.0,
            sell_zone_low=125.0,
            sell_zone_high=128.0,
            risk_reward_ratio=1.3,
            confidence_grade="C",
            methodology=[],
            summary="",
        )
        forecast = NextDayForecast(
            target_date="2026-03-23",
            reference_date="2026-03-20",
            reference_price=127.0,
            direction="down",
            up_probability=42.0,
            predicted_open=126.5,
            predicted_close=124.8,
            predicted_high=127.2,
            predicted_low=123.9,
            predicted_return_pct=-1.7,
            confidence=71.0,
            confidence_note="",
            news_sentiment=-0.2,
            raw_signal=-0.5,
            flow_signal=None,
            drivers=[],
            model_version="signal-v2.1",
        )
        regime = MarketRegime(
            label="Risk-Off",
            stance="risk_off",
            trend="downtrend",
            volatility="high",
            breadth="weak",
            score=36.0,
            conviction=76.0,
            summary="",
            playbook=[],
            warnings=[],
            signals=[],
        )

        plan = build_trade_plan(
            ticker="TEST",
            current_price=127.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            next_day_forecast=forecast,
            market_regime=regime,
        )

        self.assertEqual(plan.action, "reduce_risk")
        self.assertEqual(plan.setup_label, "리스크 축소")
        self.assertTrue(any("시장 국면" in item for item in plan.thesis))
        self.assertIn("재평가", plan.invalidation)

    def test_short_horizon_trade_plan_sets_one_day_risk_bounds(self):
        history = [PricePoint(**row) for row in _price_series()]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [126.0],
            ma_60=[None] * 79 + [118.0],
            rsi_14=[None] * 79 + [52.0],
            macd=[None] * 79 + [1.0],
            macd_signal=[None] * 79 + [0.7],
            macd_hist=[None] * 79 + [0.3],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=120.0,
            buy_zone_high=124.0,
            fair_value=132.0,
            sell_zone_low=138.0,
            sell_zone_high=142.0,
            risk_reward_ratio=2.0,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        forecast = NextDayForecast(
            target_date="2026-03-23",
            reference_date="2026-03-20",
            reference_price=123.0,
            direction="up",
            up_probability=66.0,
            predicted_open=123.4,
            predicted_close=125.2,
            predicted_high=126.6,
            predicted_low=122.2,
            predicted_return_pct=1.8,
            confidence=70.0,
            confidence_note="",
            news_sentiment=0.3,
            raw_signal=0.5,
            flow_signal=None,
            drivers=[],
            model_version="signal-v2.1",
        )
        regime = MarketRegime(
            label="Risk-On Trend",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=68.0,
            conviction=71.0,
            summary="",
            playbook=[],
            warnings=[],
            signals=[],
        )

        plan = build_short_horizon_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            next_day_forecast=forecast,
            market_regime=regime,
        )

        self.assertEqual(plan.expected_holding_days, 1)
        self.assertIn(plan.action, {"accumulate", "breakout_watch"})
        self.assertIsNotNone(plan.entry_low)
        self.assertIsNotNone(plan.stop_loss)
        self.assertIsNotNone(plan.take_profit_1)
        self.assertGreater(plan.take_profit_1, plan.stop_loss)

    def test_weekly_trade_plan_changes_with_bullish_and_bearish_5d_inputs(self):
        history = [PricePoint(**row) for row in _price_series()]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [126.0],
            ma_60=[None] * 79 + [118.0],
            rsi_14=[None] * 79 + [52.0],
            macd=[None] * 79 + [1.0],
            macd_signal=[None] * 79 + [0.7],
            macd_hist=[None] * 79 + [0.3],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=120.0,
            buy_zone_high=124.0,
            fair_value=132.0,
            sell_zone_low=128.0,
            sell_zone_high=138.0,
            risk_reward_ratio=2.0,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        regime = MarketRegime(
            label="Risk-On Trend",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=68.0,
            conviction=71.0,
            summary="시장 국면이 우호적입니다.",
            playbook=[],
            warnings=[],
            signals=[],
        )
        bullish_horizon = SimpleNamespace(
            target_date="2026-03-27",
            price_q10=119.0,
            price_q25=122.0,
            price_q50=124.0,
            price_q75=130.0,
            price_q90=134.0,
            mean_return_raw=0.035,
            mean_return_excess=0.02,
            p_up=66.0,
            p_flat=18.0,
            p_down=16.0,
            confidence=72.0,
        )
        bearish_horizon = SimpleNamespace(
            target_date="2026-03-27",
            price_q10=112.0,
            price_q25=116.0,
            price_q50=119.0,
            price_q75=122.0,
            price_q90=125.0,
            mean_return_raw=-0.028,
            mean_return_excess=-0.035,
            p_up=34.0,
            p_flat=20.0,
            p_down=46.0,
            confidence=64.0,
        )

        bullish = build_weekly_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            weekly_horizon=bullish_horizon,
            market_regime=regime,
            reference_date="2026-03-20",
        )
        bearish = build_weekly_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            weekly_horizon=bearish_horizon,
            market_regime=regime,
            reference_date="2026-03-20",
        )

        self.assertIn(bullish.action, {"accumulate", "breakout_watch", "wait_pullback"})
        self.assertIn(bearish.action, {"avoid", "reduce_risk"})
        self.assertGreater(bullish.sell_price or 0, bullish.buy_price or 0)
        self.assertLess(bearish.expected_return_pct or 0, bullish.expected_return_pct or 0)
        self.assertGreaterEqual(bullish.risk_reward_estimate, 0)
        self.assertLessEqual(bearish.sell_zone_low or 0, bearish.sell_price or 0)
        self.assertGreaterEqual(bearish.sell_zone_high or 0, bearish.sell_price or 0)

    def test_weekly_trade_plan_does_not_consume_llm_numeric_fields(self):
        history = [PricePoint(**row) for row in _price_series()]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [126.0],
            ma_60=[None] * 79 + [118.0],
            rsi_14=[None] * 79 + [52.0],
            macd=[None] * 79 + [1.0],
            macd_signal=[None] * 79 + [0.7],
            macd_hist=[None] * 79 + [0.3],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=120.0,
            buy_zone_high=124.0,
            fair_value=132.0,
            sell_zone_low=128.0,
            sell_zone_high=138.0,
            risk_reward_ratio=2.0,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        fake_llm_numbers = {"buy_price": 1.0, "sell_price": 9999.0, "stop_loss": 0.5}
        horizon = SimpleNamespace(
            target_date="2026-03-27",
            price_q10=119.0,
            price_q25=122.0,
            price_q50=124.0,
            price_q75=130.0,
            price_q90=134.0,
            mean_return_raw=0.03,
            mean_return_excess=0.02,
            p_up=62.0,
            p_flat=20.0,
            p_down=18.0,
            confidence=70.0,
        )

        plan = build_weekly_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            weekly_horizon=horizon,
            reference_date="2026-03-20",
        )

        self.assertNotEqual(plan.buy_price, fake_llm_numbers["buy_price"])
        self.assertNotEqual(plan.sell_price, fake_llm_numbers["sell_price"])
        self.assertGreater(plan.buy_price or 0, 100.0)
        self.assertLess(plan.sell_price or 0, 150.0)

    def test_weekly_trade_plan_uses_official_research_metadata_as_guardrail(self):
        history = [PricePoint(**row) for row in _price_series()]
        technical = TechnicalIndicators(
            ma_20=[None] * 79 + [126.0],
            ma_60=[None] * 79 + [118.0],
            rsi_14=[None] * 79 + [52.0],
            macd=[None] * 79 + [1.0],
            macd_signal=[None] * 79 + [0.7],
            macd_hist=[None] * 79 + [0.3],
            dates=[row.date for row in history],
        )
        buy_sell = BuySellGuide(
            buy_zone_low=120.0,
            buy_zone_high=124.0,
            fair_value=132.0,
            sell_zone_low=128.0,
            sell_zone_high=138.0,
            risk_reward_ratio=2.0,
            confidence_grade="B",
            methodology=[],
            summary="",
        )
        horizon = SimpleNamespace(
            target_date="2026-03-27",
            price_q10=119.0,
            price_q25=122.0,
            price_q50=124.0,
            price_q75=130.0,
            price_q90=134.0,
            mean_return_raw=0.04,
            mean_return_excess=0.03,
            p_up=70.0,
            p_flat=16.0,
            p_down=14.0,
            confidence=74.0,
        )
        regime = MarketRegime(
            label="Risk-On Trend",
            stance="risk_on",
            trend="uptrend",
            volatility="normal",
            breadth="strong",
            score=68.0,
            conviction=71.0,
            summary="시장 국면이 우호적입니다.",
            playbook=[],
            warnings=[],
            signals=[],
        )

        plan = build_weekly_trade_plan(
            ticker="TEST",
            current_price=123.0,
            price_history=history,
            technical=technical,
            buy_sell_guide=buy_sell,
            weekly_horizon=horizon,
            market_regime=regime,
            research_context=[
                {"title": "반도체 수출 둔화 리스크 점검", "signal": "bearish"},
                {"title": "AI 투자 불확실성 확대", "signal": "bearish"},
            ],
            reference_date="2026-03-20",
        )

        self.assertEqual(plan.action, "wait_pullback")
        self.assertTrue(any(item.key == "official_research" for item in plan.evidence))
        self.assertIn("공식 리서치 메타데이터", plan.data_quality)
