"""Quantitative stock scorer using rubric thresholds."""

import numpy as np
import pandas as pd
from ta.trend import SMAIndicator, EMAIndicator, MACD, ADXIndicator, CCIIndicator
from ta.momentum import RSIIndicator, StochasticOscillator, WilliamsRIndicator
from ta.volatility import BollingerBands
from app.scoring import rubric
from app.models.score import ScoreItem, StockScore, StockScoreDetail, CompositeScore


def score_stock(
    info: dict,
    peers_avg: dict | None = None,
    price_hist: list[dict] | None = None,
    analyst_counts: dict | None = None,
) -> StockScore:
    peers = peers_avg or {}
    prices = price_hist or []

    fundamental = _score_fundamental(info)
    valuation = _score_valuation(info, peers)
    growth = _score_growth(info, prices)
    analyst = _score_analyst(info, analyst_counts)
    risk = _score_risk(info, prices)

    total = fundamental.total + valuation.total + growth.total + analyst.total + risk.total
    return StockScore(
        total=round(total, 1),
        fundamental=fundamental,
        valuation=valuation,
        growth_momentum=growth,
        analyst=analyst,
        risk=risk,
    )


def score_technical(prices: list[dict]) -> StockScoreDetail:
    """Score based on technical indicators. 25 points max."""
    if len(prices) < 20:
        return StockScoreDetail(
            total=12.5, max_score=25,
            items=[ScoreItem(name="Technical", score=12.5, max_score=25, description="Insufficient data")],
        )

    df = pd.DataFrame(prices)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    current_price = float(close.iloc[-1])

    buy_count = 0
    sell_count = 0
    total_signals = 0
    items: list[ScoreItem] = []

    for period in [5, 10, 20, 50, 100, 200]:
        if len(close) < period:
            continue
        sma_val = float(SMAIndicator(close, window=period).sma_indicator().iloc[-1])
        ema_val = float(EMAIndicator(close, window=period).ema_indicator().iloc[-1])
        for name, val in [(f"SMA({period})", sma_val), (f"EMA({period})", ema_val)]:
            total_signals += 1
            if current_price > val:
                buy_count += 1
            else:
                sell_count += 1

    osc_signals = []

    rsi_val = float(RSIIndicator(close, window=14).rsi().iloc[-1])
    osc_signals.append(("RSI", rsi_val, "Buy" if rsi_val < 30 else ("Sell" if rsi_val > 70 else "Neutral")))

    macd_ind = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_v = float(macd_ind.macd().iloc[-1])
    macd_s = float(macd_ind.macd_signal().iloc[-1])
    osc_signals.append(("MACD", macd_v, "Buy" if macd_v > macd_s else "Sell"))

    if len(close) >= 14:
        stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = float(stoch.stoch().iloc[-1])
        osc_signals.append(("Stoch", stoch_k, "Buy" if stoch_k < 20 else ("Sell" if stoch_k > 80 else "Neutral")))

    if len(close) >= 20:
        cci_val = float(CCIIndicator(high, low, close, window=20).cci().iloc[-1])
        osc_signals.append(("CCI", cci_val, "Buy" if cci_val < -100 else ("Sell" if cci_val > 100 else "Neutral")))

    if len(close) >= 14:
        adx_ind = ADXIndicator(high, low, close, window=14)
        adx_val = float(adx_ind.adx().iloc[-1])
        price_rising = close.iloc[-1] > close.iloc[-5] if len(close) >= 5 else True
        adx_sig = "Neutral"
        if adx_val > 25:
            adx_sig = "Buy" if price_rising else "Sell"
        osc_signals.append(("ADX", adx_val, adx_sig))

    if len(close) >= 14:
        wr_val = float(WilliamsRIndicator(high, low, close, lbp=14).williams_r().iloc[-1])
        osc_signals.append(("W%R", wr_val, "Buy" if wr_val < -80 else ("Sell" if wr_val > -20 else "Neutral")))

    if len(close) >= 20:
        bb = BollingerBands(close, window=20, window_dev=2)
        bb_u = float(bb.bollinger_hband().iloc[-1])
        bb_l = float(bb.bollinger_lband().iloc[-1])
        osc_signals.append(("BB", float(current_price), "Buy" if current_price < bb_l else ("Sell" if current_price > bb_u else "Neutral")))

    osc_buy = sum(1 for _, _, s in osc_signals if s == "Buy")
    osc_sell = sum(1 for _, _, s in osc_signals if s == "Sell")
    osc_total = len(osc_signals) or 1

    buy_count += osc_buy
    sell_count += osc_sell
    total_signals += osc_total

    total_signals = max(total_signals, 1)
    ma_score = round(buy_count / total_signals * 25, 1)

    items.append(ScoreItem(
        name="MA Signals",
        score=round((buy_count - osc_buy) / max(total_signals - osc_total, 1) * 12.5, 1),
        max_score=12.5,
        description=f"{buy_count - osc_buy} Buy / {sell_count - osc_sell} Sell",
    ))
    items.append(ScoreItem(
        name="Oscillator Signals",
        score=round(osc_buy / osc_total * 12.5, 1),
        max_score=12.5,
        description=f"{osc_buy} Buy / {osc_sell} Sell",
    ))

    total_pts = round(items[0].score + items[1].score, 1)
    return StockScoreDetail(total=total_pts, max_score=25, items=items)


def score_composite(
    info: dict,
    peers_avg: dict | None = None,
    price_hist: list[dict] | None = None,
    price_hist_6mo: list[dict] | None = None,
    analyst_counts: dict | None = None,
) -> CompositeScore:
    """Build composite score: 6 categories, 125 raw -> 100 scaled."""
    peers = peers_avg or {}
    prices = price_hist or []
    prices_6mo = price_hist_6mo or prices

    fundamental = _score_fundamental(info)
    valuation = _score_valuation(info, peers)
    growth = _score_growth_composite(info, prices)
    analyst = _score_analyst(info, analyst_counts)
    risk = _score_risk(info, prices)
    technical = score_technical(prices_6mo)

    raw_total = (
        fundamental.total + valuation.total + growth.total +
        analyst.total + risk.total + technical.total
    )
    max_raw = 125.0
    scaled = round(raw_total / max_raw * 100, 1)

    return CompositeScore(
        total=scaled,
        total_raw=round(raw_total, 1),
        max_raw=max_raw,
        fundamental=fundamental,
        valuation=valuation,
        growth_momentum=growth,
        analyst=analyst,
        risk=risk,
        technical=technical,
    )


# ── Fundamental (25 pts) ─────────────────────────────────

def _score_fundamental(info: dict) -> StockScoreDetail:
    rev_g = (info.get("revenue_growth") or 0) * 100
    op_m = (info.get("operating_margins") or 0) * 100
    roe_val = (info.get("roe") or 0) * 100
    dte = info.get("debt_to_equity") or 0
    mc = info.get("market_cap") or 1
    fcf = info.get("free_cashflow") or 0
    fcf_y = (fcf / mc * 100) if mc > 0 else 0

    items = [
        ScoreItem(name="Revenue Growth", score=rubric.REVENUE_GROWTH.score(rev_g),
                  max_score=5, description=f"{rev_g:.1f}%"),
        ScoreItem(name="Operating Margin", score=rubric.OPERATING_MARGIN.score(op_m),
                  max_score=5, description=f"{op_m:.1f}%"),
        ScoreItem(name="ROE", score=rubric.ROE.score(roe_val),
                  max_score=5, description=f"{roe_val:.1f}%"),
        ScoreItem(name="Debt/Equity", score=rubric.DEBT_TO_EQUITY.score(dte),
                  max_score=5, description=f"{dte:.0f}%"),
        ScoreItem(name="FCF Yield", score=rubric.FCF_YIELD.score(fcf_y),
                  max_score=5, description=f"{fcf_y:.1f}%"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=25, items=items)


# ── Valuation (20 pts) ───────────────────────────────────

def _score_valuation(info: dict, peers: dict) -> StockScoreDetail:
    pe = info.get("pe_ratio")
    pb = info.get("pb_ratio")
    ev_eb = info.get("ev_ebitda")
    peg = info.get("peg_ratio")

    peer_pe = peers.get("pe_avg")
    peer_pb = peers.get("pb_avg")
    peer_ev = peers.get("ev_ebitda_avg")

    pe_diff = _pct_diff(pe, peer_pe)
    pb_diff = _pct_diff(pb, peer_pb)
    ev_diff = _pct_diff(ev_eb, peer_ev)

    items = [
        ScoreItem(name="P/E vs Peers", score=rubric.PE_VS_PEERS.score(pe_diff),
                  max_score=5, description=f"{pe_diff:+.1f}%" if pe_diff is not None else "N/A"),
        ScoreItem(name="P/B vs Peers", score=rubric.PB_VS_PEERS.score(pb_diff),
                  max_score=5, description=f"{pb_diff:+.1f}%" if pb_diff is not None else "N/A"),
        ScoreItem(name="EV/EBITDA vs Peers", score=rubric.EV_EBITDA_VS_PEERS.score(ev_diff),
                  max_score=5, description=f"{ev_diff:+.1f}%" if ev_diff is not None else "N/A"),
        ScoreItem(name="PEG Ratio", score=rubric.PEG_RATIO.score(peg),
                  max_score=5, description=f"{peg:.2f}" if peg else "N/A"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=20, items=items)


# ── Growth / Momentum (20 pts for StockScore, 15 pts for Composite) ──

def _score_growth(info: dict, prices: list[dict]) -> StockScoreDetail:
    eps_g = (info.get("earnings_growth") or 0) * 100
    rev_g = (info.get("revenue_growth") or 0) * 100
    surprise = None
    momentum_3m = _calc_return(prices)

    items = [
        ScoreItem(name="EPS Growth", score=rubric.EPS_GROWTH.score(eps_g),
                  max_score=5, description=f"{eps_g:.1f}%"),
        ScoreItem(name="Revenue Growth", score=rubric.REVENUE_GROWTH_MOMENTUM.score(rev_g),
                  max_score=5, description=f"{rev_g:.1f}%"),
        ScoreItem(name="Earnings Surprise", score=rubric.EARNINGS_SURPRISE.score(surprise),
                  max_score=5, description=f"{surprise:.1f}%" if surprise else "N/A"),
        ScoreItem(name="Price Momentum 3M", score=rubric.PRICE_MOMENTUM_3M.score(momentum_3m),
                  max_score=5, description=f"{momentum_3m:+.1f}%" if momentum_3m is not None else "N/A"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=20, items=items)


def _score_growth_composite(info: dict, prices: list[dict]) -> StockScoreDetail:
    """Growth for composite: 15 pts (3 items x 5pts). No Price Momentum (covered by Technical)."""
    eps_g = (info.get("earnings_growth") or 0) * 100
    rev_g = (info.get("revenue_growth") or 0) * 100
    surprise = None

    items = [
        ScoreItem(name="EPS Growth", score=rubric.EPS_GROWTH.score(eps_g),
                  max_score=5, description=f"{eps_g:.1f}%"),
        ScoreItem(name="Revenue Growth", score=rubric.REVENUE_GROWTH_MOMENTUM.score(rev_g),
                  max_score=5, description=f"{rev_g:.1f}%"),
        ScoreItem(name="Earnings Surprise", score=rubric.EARNINGS_SURPRISE.score(surprise),
                  max_score=5, description=f"{surprise:.1f}%" if surprise else "N/A"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=15, items=items)


# ── Analyst (20 pts for composite, 15 pts legacy) ─────────

def _score_analyst(info: dict, analyst_counts: dict | None = None) -> StockScoreDetail:
    target_mean = info.get("target_mean")
    price = info.get("current_price") or info.get("regularMarketPrice", 0)
    upside = ((target_mean - price) / price * 100) if target_mean and price else None

    counts = analyst_counts or {}
    buy = counts.get("buy", 0)
    hold = counts.get("hold", 0)
    sell = counts.get("sell", 0)
    total_analysts = buy + hold + sell

    if total_analysts > 0:
        buy_ratio = buy / total_analysts * 100
        majority_pct = max(buy, hold, sell) / total_analysts * 100
    else:
        num = info.get("num_analysts") or 0
        if num > 0:
            rec = info.get("recommendation", "")
            if "buy" in str(rec).lower() or "strong" in str(rec).lower():
                buy_ratio = 75
            elif "hold" in str(rec).lower():
                buy_ratio = 45
            else:
                buy_ratio = 25
            majority_pct = buy_ratio
            total_analysts = num
        else:
            buy_ratio = None
            majority_pct = None
            total_analysts = 0

    items = [
        ScoreItem(name="Buy Ratio", score=rubric.BUY_RATIO.score(buy_ratio),
                  max_score=5, description=f"{buy_ratio:.0f}%" if buy_ratio is not None else "N/A"),
        ScoreItem(name="Target Upside", score=rubric.TARGET_UPSIDE.score(upside),
                  max_score=5, description=f"{upside:+.1f}%" if upside is not None else "N/A"),
        ScoreItem(name="Coverage", score=rubric.ANALYST_COVERAGE.score(total_analysts),
                  max_score=5, description=f"{total_analysts} analysts"),
        ScoreItem(name="Consensus Strength", score=rubric.CONSENSUS_STRENGTH.score(majority_pct),
                  max_score=5, description=f"{majority_pct:.0f}%" if majority_pct is not None else "N/A"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=20, items=items)


# ── Risk (20 pts) ────────────────────────────────────────

def _score_risk(info: dict, prices: list[dict]) -> StockScoreDetail:
    beta = info.get("beta")
    vol = _calc_volatility(prices)
    dd = _calc_max_drawdown(prices)

    items = [
        ScoreItem(name="Beta", score=rubric.BETA_SCORE.score(beta),
                  max_score=5, description=f"{beta:.2f}" if beta else "N/A"),
        ScoreItem(name="Volatility", score=rubric.VOLATILITY_ANNUAL.score(vol),
                  max_score=5, description=f"{vol:.1f}%" if vol is not None else "N/A"),
        ScoreItem(name="Max Drawdown 3M", score=rubric.MAX_DRAWDOWN_3M.score(dd),
                  max_score=5, description=f"{dd:.1f}%" if dd is not None else "N/A"),
        ScoreItem(name="Liquidity", score=rubric.LIQUIDITY.score(100),
                  max_score=5, description="Normal"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=20, items=items)


# ── Helpers ──────────────────────────────────────────────

def _pct_diff(val, ref) -> float | None:
    if val is None or ref is None or ref == 0:
        return None
    return round((val - ref) / ref * 100, 1)


def _calc_return(prices: list[dict]) -> float | None:
    if len(prices) < 2:
        return None
    start = prices[0]["close"]
    end = prices[-1]["close"]
    if start == 0:
        return None
    return round((end - start) / start * 100, 2)


def _calc_volatility(prices: list[dict]) -> float | None:
    if len(prices) < 10:
        return None
    closes = [p["close"] for p in prices]
    returns = np.diff(np.log(closes))
    return round(float(np.std(returns) * np.sqrt(252) * 100), 1)


def _calc_max_drawdown(prices: list[dict]) -> float | None:
    if len(prices) < 2:
        return None
    closes = [p["close"] for p in prices]
    peak = closes[0]
    max_dd = 0
    for c in closes:
        if c > peak:
            peak = c
        dd = (peak - c) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 1)
