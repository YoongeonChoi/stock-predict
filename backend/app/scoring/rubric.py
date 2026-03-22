"""Single source of truth for all scoring thresholds and criteria.

Every score in this system traces back to a definition here.
Quantitative thresholds are computed deterministically.
Qualitative criteria are passed to the LLM as structured guidelines.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Threshold:
    """Maps a numeric value to a score via breakpoints.
    breakpoints: [(upper_bound, score), ...] evaluated in order.
    The first range where value < upper_bound wins. Last entry is catch-all.
    """
    name: str
    max_score: float
    breakpoints: tuple[tuple[float, float], ...]
    higher_is_better: bool = True

    def score(self, value: float | None) -> float:
        if value is None:
            return self.max_score * 0.5
        for bound, pts in self.breakpoints:
            if self.higher_is_better and value >= bound:
                return pts
            if not self.higher_is_better and value <= bound:
                return pts
        return self.breakpoints[-1][1]


# ── STOCK FUNDAMENTAL (25 pts) ────────────────────────────

REVENUE_GROWTH = Threshold(
    name="Revenue Growth (YoY %)",
    max_score=5,
    breakpoints=((20, 5), (10, 4), (5, 3), (0, 2), (-999, 1)),
    higher_is_better=True,
)

OPERATING_MARGIN = Threshold(
    name="Operating Margin (%)",
    max_score=5,
    breakpoints=((25, 5), (15, 4), (10, 3), (5, 2), (-999, 1)),
    higher_is_better=True,
)

ROE = Threshold(
    name="ROE (%)",
    max_score=5,
    breakpoints=((20, 5), (15, 4), (10, 3), (5, 2), (-999, 1)),
    higher_is_better=True,
)

DEBT_TO_EQUITY = Threshold(
    name="Debt/Equity (%)",
    max_score=5,
    breakpoints=((30, 5), (60, 4), (100, 3), (200, 2), (9999, 1)),
    higher_is_better=False,
)

FCF_YIELD = Threshold(
    name="FCF Yield (%)",
    max_score=5,
    breakpoints=((8, 5), (5, 4), (3, 3), (1, 2), (-999, 1)),
    higher_is_better=True,
)

# ── STOCK VALUATION (20 pts) ─────────────────────────────

PE_VS_PEERS = Threshold(
    name="P/E vs Peers (% diff)",
    max_score=5,
    breakpoints=((-20, 5), (-10, 4), (10, 3), (20, 2), (9999, 1)),
    higher_is_better=False,
)

PB_VS_PEERS = Threshold(
    name="P/B vs Peers (% diff)",
    max_score=5,
    breakpoints=((-20, 5), (-10, 4), (10, 3), (20, 2), (9999, 1)),
    higher_is_better=False,
)

EV_EBITDA_VS_PEERS = Threshold(
    name="EV/EBITDA vs Peers (% diff)",
    max_score=5,
    breakpoints=((-20, 5), (-10, 4), (10, 3), (20, 2), (9999, 1)),
    higher_is_better=False,
)

PEG_RATIO = Threshold(
    name="PEG Ratio",
    max_score=5,
    breakpoints=((0.5, 5), (1.0, 4), (1.5, 3), (2.5, 2), (9999, 1)),
    higher_is_better=False,
)

# ── STOCK GROWTH / MOMENTUM (20 pts) ─────────────────────

EPS_GROWTH = Threshold(
    name="EPS Growth (YoY %)",
    max_score=5,
    breakpoints=((25, 5), (15, 4), (5, 3), (0, 2), (-999, 1)),
    higher_is_better=True,
)

REVENUE_GROWTH_MOMENTUM = Threshold(
    name="Revenue Growth Momentum (%)",
    max_score=5,
    breakpoints=((20, 5), (10, 4), (5, 3), (0, 2), (-999, 1)),
    higher_is_better=True,
)

EARNINGS_SURPRISE = Threshold(
    name="Earnings Surprise (%)",
    max_score=5,
    breakpoints=((5, 5), (2, 4), (0, 3), (-2, 2), (-999, 1)),
    higher_is_better=True,
)

PRICE_MOMENTUM_3M = Threshold(
    name="3M Price Return (%)",
    max_score=5,
    breakpoints=((15, 5), (5, 4), (0, 3), (-10, 2), (-999, 1)),
    higher_is_better=True,
)

# ── STOCK ANALYST (15 pts) ───────────────────────────────

BUY_RATIO = Threshold(
    name="Analyst Buy Ratio (%)",
    max_score=5,
    breakpoints=((80, 5), (60, 4), (40, 3), (20, 2), (-1, 1)),
    higher_is_better=True,
)

TARGET_UPSIDE = Threshold(
    name="Target Price Upside (%)",
    max_score=5,
    breakpoints=((30, 5), (15, 4), (5, 3), (-5, 2), (-999, 1)),
    higher_is_better=True,
)

ANALYST_COVERAGE = Threshold(
    name="Analyst Coverage (count)",
    max_score=5,
    breakpoints=((20, 5), (10, 4), (5, 3), (1, 2), (-1, 1)),
    higher_is_better=True,
)

CONSENSUS_STRENGTH = Threshold(
    name="Consensus Strength (majority %)",
    max_score=5,
    breakpoints=((70, 5), (60, 4), (50, 3), (40, 2), (-1, 1)),
    higher_is_better=True,
)

# Estimate revision is qualitative → scored by LLM (0-5)
ESTIMATE_REVISION_MAX = 5

# ── STOCK RISK (20 pts) ──────────────────────────────────

BETA_SCORE = Threshold(
    name="Beta",
    max_score=5,
    breakpoints=((1.0, 5), (1.2, 4), (1.5, 3), (2.0, 2), (9999, 1)),
    higher_is_better=False,
)

VOLATILITY_ANNUAL = Threshold(
    name="Annualized Volatility (%)",
    max_score=5,
    breakpoints=((15, 5), (25, 4), (35, 3), (50, 2), (9999, 1)),
    higher_is_better=False,
)

MAX_DRAWDOWN_3M = Threshold(
    name="3M Max Drawdown (%)",
    max_score=5,
    breakpoints=((5, 5), (10, 4), (20, 3), (30, 2), (9999, 1)),
    higher_is_better=False,
)

LIQUIDITY = Threshold(
    name="Avg Volume Ratio (%)",
    max_score=5,
    breakpoints=((120, 5), (100, 4), (80, 3), (50, 2), (-1, 1)),
    higher_is_better=True,
)


# ── COUNTRY SCORE (qualitative thresholds for LLM) ──────

COUNTRY_CRITERIA = {
    "monetary_policy": {
        "max_score": 20,
        "guidelines": (
            "20: Actively easing (rate cuts, QE in progress)\n"
            "16-19: Transition to easing (pause with cut guidance)\n"
            "11-15: Neutral / on hold\n"
            "6-10: Transition to tightening\n"
            "1-5: Actively tightening (rate hikes, QT)"
        ),
    },
    "economic_growth": {
        "max_score": 20,
        "guidelines": (
            "20: GDP well above trend, PMI expanding, strong employment\n"
            "16-19: GDP at/above trend, PMI stable-to-expanding\n"
            "11-15: GDP near trend, mixed signals\n"
            "6-10: GDP below trend, PMI contracting\n"
            "1-5: Recession signals, rising unemployment"
        ),
    },
    "market_valuation": {
        "max_score": 15,
        "guidelines": (
            "13-15: Market P/E well below historical avg, Buffett indicator < 100%\n"
            "10-12: P/E slightly below average, ERP attractive\n"
            "7-9: P/E near average\n"
            "4-6: P/E above average, stretched valuations\n"
            "1-3: P/E well above average, bubble territory"
        ),
    },
    "earnings_momentum": {
        "max_score": 15,
        "guidelines": (
            "13-15: Broad upward revisions, strong earnings beat rate\n"
            "10-12: Mostly positive revisions\n"
            "7-9: Mixed revisions\n"
            "4-6: Mostly negative revisions\n"
            "1-3: Broad downward revisions, earnings collapse"
        ),
    },
    "institutional_consensus": {
        "max_score": 15,
        "guidelines": (
            "13-15: 3+ institutions agree, policy-sellside aligned, assumptions match data\n"
            "10-12: Mostly aligned, minor disagreements\n"
            "7-9: Mixed views, some alignment\n"
            "4-6: Significant disagreements\n"
            "1-3: Contradictory views, policy vs sellside divergence"
        ),
    },
    "risk_assessment": {
        "max_score": 15,
        "guidelines": (
            "13-15: Low VIX, stable FX, no geopolitical risk, tight spreads\n"
            "10-12: Slightly elevated but manageable\n"
            "7-9: Moderate risk, some uncertainties\n"
            "4-6: Elevated risk, rising volatility\n"
            "1-3: Crisis-level volatility, severe geopolitical risk"
        ),
    },
}

# ── SECTOR SCORE (qualitative thresholds for LLM) ───────

SECTOR_CRITERIA = {
    "earnings_growth": {
        "max_score": 20,
        "guidelines": (
            "18-20: Sector EPS growth >15%, expanding margins, strong revenue\n"
            "14-17: EPS growth 5-15%, stable margins\n"
            "10-13: EPS growth 0-5%, mixed signals\n"
            "5-9: Negative EPS growth, margin compression\n"
            "1-4: Severe earnings decline"
        ),
    },
    "institutional_consensus": {
        "max_score": 20,
        "guidelines": (
            "18-20: Strong overweight consensus from 3+ firms\n"
            "14-17: Moderate overweight, mostly positive\n"
            "10-13: Neutral weight, mixed views\n"
            "5-9: Underweight from most firms\n"
            "1-4: Strong underweight consensus"
        ),
    },
    "valuation_attractiveness": {
        "max_score": 15,
        "guidelines": (
            "13-15: Sector P/E well below 5yr avg and market avg\n"
            "10-12: Slightly below average, PEG attractive\n"
            "7-9: At average valuations\n"
            "4-6: Above average\n"
            "1-3: Significantly overvalued"
        ),
    },
    "policy_impact": {
        "max_score": 15,
        "guidelines": (
            "13-15: Strong tailwinds (subsidies, deregulation, govt spending)\n"
            "10-12: Moderate tailwinds\n"
            "7-9: Neutral policy environment\n"
            "4-6: Moderate headwinds (regulation, tax)\n"
            "1-3: Severe headwinds (bans, heavy regulation)"
        ),
    },
    "technical_momentum": {
        "max_score": 15,
        "guidelines": (
            "13-15: Strong uptrend, above all MAs, positive money flow\n"
            "10-12: Moderate uptrend, above 50DMA\n"
            "7-9: Sideways, mixed signals\n"
            "4-6: Below key MAs, weakening\n"
            "1-3: Strong downtrend, heavy outflows"
        ),
    },
    "risk_adjusted_return": {
        "max_score": 15,
        "guidelines": (
            "13-15: Beta 0.5-1.0, low downside vol, low market correlation\n"
            "10-12: Beta near 1.0, moderate risk\n"
            "7-9: Slightly elevated risk\n"
            "4-6: High beta, high volatility\n"
            "1-3: Very high risk, max drawdown territory"
        ),
    },
}


# ── BUY/SELL GUIDE PARAMETERS ─────────────────────────────

BUY_ZONE_DISCOUNT = 0.12
SELL_ZONE_PREMIUM = 0.18

VALUATION_WEIGHTS = {
    "dcf": 0.35,
    "multiples": 0.35,
    "analyst_target": 0.30,
}

CONFIDENCE_THRESHOLDS = {
    "A": 0.10,
    "B": 0.20,
    "C": 1.00,
}


# ── FEAR & GREED THRESHOLDS ──────────────────────────────

def fear_greed_label(score: float) -> str:
    if score >= 80:
        return "Extreme Greed"
    if score >= 60:
        return "Greed"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Fear"
    return "Extreme Fear"
