"""All structured prompts for the LLM analysis engine.

Each prompt is a function returning (system_prompt, user_prompt).
The LLM returns structured JSON following the scoring rubric.
"""

from app.scoring.rubric import COUNTRY_CRITERIA, SECTOR_CRITERIA


def country_report_prompt(
    country_name: str,
    country_code: str,
    institutions: list[str],
    economic_data: dict,
    news_by_institution: dict[str, list[dict]],
    market_data: dict,
) -> tuple[str, str]:
    criteria_text = "\n".join(
        f"- {k}: max {v['max_score']} pts\n  {v['guidelines']}"
        for k, v in COUNTRY_CRITERIA.items()
    )

    news_text = ""
    for inst, articles in news_by_institution.items():
        headlines = "\n".join(f"  - {a['title']} ({a['source']})" for a in articles[:5])
        news_text += f"\n[{inst}]\n{headlines}\n"

    ticker_guide = {
        "US": "US tickers use plain symbols (e.g. AAPL, MSFT, NVDA, TSLA, AMZN)",
        "KR": "Korean tickers MUST use Yahoo Finance format: 6-digit number + .KS (e.g. 005930.KS for Samsung, 000660.KS for SK Hynix, 051910.KS for LG Chem, 035420.KS for NAVER)",
        "JP": "Japanese tickers MUST use Yahoo Finance format: 4-digit number + .T (e.g. 7203.T for Toyota, 6758.T for Sony, 9984.T for SoftBank)",
    }.get(country_code, "Use Yahoo Finance ticker symbols")

    system = (
        "You are a senior equity strategist analyzing a country's stock market.\n"
        "You MUST respond with valid JSON only.\n"
        "Follow the scoring rubric EXACTLY. Each score must be justified.\n"
        "Cross-validate: check if 3+ institutions agree, if policy vs sell-side align,\n"
        "and if assumptions match the latest data provided.\n\n"
        f"CRITICAL: For top_5_tickers, {ticker_guide}.\n"
        "NEVER use company names or local-language names as tickers."
    )

    user = f"""Analyze the {country_name} ({country_code}) stock market.

## Economic Data
{_format_dict(economic_data)}

## Market Data
{_format_dict(market_data)}

## Research Institution News (recent 30 days)
{news_text}

## Scoring Rubric
{criteria_text}

## Required JSON Output
{{
  "market_summary": "2-3 paragraph market overview in Korean",
  "scores": {{
    "monetary_policy": {{"score": <number>, "description": "<1-2 sentences>"}},
    "economic_growth": {{"score": <number>, "description": "<1-2 sentences>"}},
    "market_valuation": {{"score": <number>, "description": "<1-2 sentences>"}},
    "earnings_momentum": {{"score": <number>, "description": "<1-2 sentences>"}},
    "institutional_consensus": {{"score": <number>, "description": "<1-2 sentences>"}},
    "risk_assessment": {{"score": <number>, "description": "<1-2 sentences>"}}
  }},
  "institutional_analysis": {{
    "policy_institutions": [
      {{"name": "<institution>", "stance": "<bullish/neutral/bearish>", "key_points": ["..."]}}
    ],
    "sell_side": [
      {{"name": "<institution>", "stance": "<bullish/neutral/bearish>", "key_points": ["..."]}}
    ],
    "policy_sellside_aligned": <true/false>,
    "consensus_count": <number of institutions agreeing>,
    "consensus_summary": "<summary in Korean>"
  }},
  "top_5_tickers": ["<ticker1>", "<ticker2>", "<ticker3>", "<ticker4>", "<ticker5>"],
  "top_5_reasons": ["<reason1>", "<reason2>", "<reason3>", "<reason4>", "<reason5>"]
}}"""

    return system, user


def sector_report_prompt(
    sector_name: str,
    country_code: str,
    stock_data: list[dict],
    institution_news: str,
) -> tuple[str, str]:
    criteria_text = "\n".join(
        f"- {k}: max {v['max_score']} pts\n  {v['guidelines']}"
        for k, v in SECTOR_CRITERIA.items()
    )

    stocks_text = "\n".join(
        f"- {s.get('ticker')}: {s.get('name')}, Price={s.get('current_price')}, "
        f"PE={s.get('pe_ratio')}, Score={s.get('quant_score', 'N/A')}"
        for s in stock_data[:15]
    )

    system = (
        "You are a senior sector analyst.\n"
        "You MUST respond with valid JSON only.\n"
        "Score the sector using the rubric. Rank stocks by investment merit."
    )

    user = f"""Analyze the {sector_name} sector in {country_code}.

## Stocks in Sector
{stocks_text}

## Research Institution Commentary
{institution_news}

## Scoring Rubric
{criteria_text}

## Required JSON Output
{{
  "summary": "2-3 paragraph sector analysis in Korean",
  "scores": {{
    "earnings_growth": {{"score": <number>, "description": "<1-2 sentences>"}},
    "institutional_consensus": {{"score": <number>, "description": "<1-2 sentences>"}},
    "valuation_attractiveness": {{"score": <number>, "description": "<1-2 sentences>"}},
    "policy_impact": {{"score": <number>, "description": "<1-2 sentences>"}},
    "technical_momentum": {{"score": <number>, "description": "<1-2 sentences>"}},
    "risk_adjusted_return": {{"score": <number>, "description": "<1-2 sentences>"}}
  }},
  "top_10": [
    {{
      "rank": 1,
      "ticker": "<ticker>",
      "name": "<name>",
      "pros": ["<pro1>", "<pro2>"],
      "cons": ["<con1>", "<con2>"],
      "buy_price": <number or null>,
      "sell_price": <number or null>
    }}
  ]
}}"""

    return system, user


def stock_analysis_prompt(
    ticker: str,
    info: dict,
    financials: list[dict],
    news: list[dict],
    quant_score: dict,
) -> tuple[str, str]:
    news_text = "\n".join(f"- {n['title']} ({n.get('source', '')})" for n in news[:10])
    fin_text = "\n".join(
        f"  {f['period']}: Rev={f.get('revenue')}, OI={f.get('operating_income')}, "
        f"NI={f.get('net_income')}, EBITDA={f.get('ebitda')}, FCF={f.get('free_cash_flow')}"
        for f in financials[:6]
    )

    system = (
        "You are a senior equity research analyst.\n"
        "You MUST respond with valid JSON only.\n"
        "Provide fair value estimate, buy/sell zones, and detailed analysis.\n"
        "Base your valuation on: DCF (if feasible), peer multiples, and analyst targets."
    )

    user = f"""Analyze {ticker} ({info.get('name', '')}).

## Company Info
Sector: {info.get('sector')}, Industry: {info.get('industry')}
Market Cap: {info.get('market_cap')}, Price: {info.get('current_price')}
P/E: {info.get('pe_ratio')}, P/B: {info.get('pb_ratio')}, EV/EBITDA: {info.get('ev_ebitda')}
PEG: {info.get('peg_ratio')}, Beta: {info.get('beta')}
ROE: {info.get('roe')}, Debt/Equity: {info.get('debt_to_equity')}
Dividend Yield: {info.get('dividend_yield')}, Payout Ratio: {info.get('payout_ratio')}
Analyst Target Mean: {info.get('target_mean')}, Median: {info.get('target_median')}

## Quarterly Financials
{fin_text}

## Recent News
{news_text}

## Quantitative Score Breakdown
{_format_dict(quant_score)}

## Required JSON Output
{{
  "analysis_summary": "3-4 paragraph analysis in Korean",
  "fair_value": <number>,
  "buy_zone_low": <number>,
  "buy_zone_high": <number>,
  "sell_zone_low": <number>,
  "sell_zone_high": <number>,
  "confidence_grade": "<A/B/C>",
  "valuation_methods": [
    {{"name": "DCF", "value": <number>, "weight": 0.35, "details": "..."}},
    {{"name": "Peer Multiples", "value": <number>, "weight": 0.35, "details": "..."}},
    {{"name": "Analyst Target", "value": <number>, "weight": 0.30, "details": "..."}}
  ],
  "estimate_revision_score": <0-5>,
  "key_risks": ["<risk1>", "<risk2>"],
  "key_catalysts": ["<catalyst1>", "<catalyst2>"]
}}"""

    return system, user


def index_forecast_prompt(
    index_name: str,
    current_price: float,
    mc_scenarios: dict,
    economic_data: dict,
    news_summary: str,
) -> tuple[str, str]:
    system = (
        "You are a quantitative strategist.\n"
        "You MUST respond with valid JSON only.\n"
        "Adjust the Monte Carlo base scenarios using fundamental analysis.\n"
        "Provide probability-weighted scenarios for 1 month ahead."
    )

    user = f"""Forecast {index_name} for 1 month ahead.

Current Price: {current_price}

## Monte Carlo Base Scenarios (statistical)
Bull (90th pctl): {mc_scenarios.get('bull')}
Base (50th pctl): {mc_scenarios.get('base')}
Bear (10th pctl): {mc_scenarios.get('bear')}

## Economic Context
{_format_dict(economic_data)}

## Recent News Summary
{news_summary}

## Required JSON Output
{{
  "fair_value": <number>,
  "scenarios": [
    {{"name": "Bull", "price": <number>, "probability": <0-100>, "description": "..."}},
    {{"name": "Base", "price": <number>, "probability": <0-100>, "description": "..."}},
    {{"name": "Bear", "price": <number>, "probability": <0-100>, "description": "..."}}
  ],
  "confidence_note": "1-2 sentence explanation in Korean"
}}"""

    return system, user


def sentiment_prompt(headlines: list[str]) -> tuple[str, str]:
    system = (
        "Analyze the sentiment of financial news headlines.\n"
        "Return a JSON object with a 'score' (0.0 = very negative, 1.0 = very positive)\n"
        "and a 'breakdown' array."
    )

    text = "\n".join(f"- {h}" for h in headlines[:30])
    user = f"""Rate the overall market sentiment from these headlines:

{text}

## Required JSON Output
{{
  "score": <0.0-1.0>,
  "breakdown": [
    {{"headline": "<headline>", "sentiment": "<positive/neutral/negative>"}}
  ]
}}"""

    return system, user


def _format_dict(d: dict) -> str:
    lines = []
    for k, v in d.items():
        if isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}: {vv}")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)
