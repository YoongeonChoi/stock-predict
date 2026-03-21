"""Quantitative stock scorer using rubric thresholds."""

import numpy as np
from app.scoring import rubric
from app.models.score import ScoreItem, StockScore, StockScoreDetail


def score_stock(info: dict, peers_avg: dict | None = None, price_hist: list[dict] | None = None) -> StockScore:
    peers = peers_avg or {}
    prices = price_hist or []

    fundamental = _score_fundamental(info)
    valuation = _score_valuation(info, peers)
    growth = _score_growth(info, prices)
    analyst = _score_analyst(info)
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


def _score_analyst(info: dict) -> StockScoreDetail:
    target_mean = info.get("target_mean")
    price = info.get("current_price") or info.get("regularMarketPrice", 0)
    upside = ((target_mean - price) / price * 100) if target_mean and price else None

    num = info.get("num_analysts") or 0
    buy_ratio = None
    if num > 0:
        rec = info.get("recommendation", "")
        if "buy" in str(rec).lower() or "strong" in str(rec).lower():
            buy_ratio = 75
        elif "hold" in str(rec).lower():
            buy_ratio = 45
        else:
            buy_ratio = 25

    items = [
        ScoreItem(name="Buy Ratio", score=rubric.BUY_RATIO.score(buy_ratio),
                  max_score=5, description=f"{buy_ratio:.0f}%" if buy_ratio else "N/A"),
        ScoreItem(name="Target Upside", score=rubric.TARGET_UPSIDE.score(upside),
                  max_score=5, description=f"{upside:+.1f}%" if upside is not None else "N/A"),
        ScoreItem(name="Estimate Revision", score=2.5,
                  max_score=5, description="LLM-assessed"),
    ]
    total = sum(i.score for i in items)
    return StockScoreDetail(total=round(total, 1), max_score=15, items=items)


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
