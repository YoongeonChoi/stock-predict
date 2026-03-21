"""Country scorer: combines quantitative market data with LLM qualitative scores."""

from app.models.score import ScoreItem, CountryScore


def build_country_score(llm_scores: dict) -> CountryScore:
    """Build CountryScore from LLM-provided qualitative scores.

    llm_scores keys: monetary_policy, economic_growth, market_valuation,
                     earnings_momentum, institutional_consensus, risk_assessment
    Each value: {"score": float, "description": str}
    """
    from app.scoring.rubric import COUNTRY_CRITERIA

    items = {}
    for key, criteria in COUNTRY_CRITERIA.items():
        llm = llm_scores.get(key, {})
        score = min(float(llm.get("score", criteria["max_score"] * 0.5)), criteria["max_score"])
        items[key] = ScoreItem(
            name=key.replace("_", " ").title(),
            score=round(score, 1),
            max_score=criteria["max_score"],
            description=llm.get("description", ""),
        )

    total = sum(item.score for item in items.values())
    return CountryScore(
        total=round(total, 1),
        monetary_policy=items["monetary_policy"],
        economic_growth=items["economic_growth"],
        market_valuation=items["market_valuation"],
        earnings_momentum=items["earnings_momentum"],
        institutional_consensus=items["institutional_consensus"],
        risk_assessment=items["risk_assessment"],
    )
