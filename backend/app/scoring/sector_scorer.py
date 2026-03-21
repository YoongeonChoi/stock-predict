"""Sector scorer: LLM qualitative scores mapped through rubric criteria."""

from app.models.score import ScoreItem, SectorScore


def build_sector_score(llm_scores: dict) -> SectorScore:
    """Build SectorScore from LLM-provided qualitative scores.

    llm_scores keys: earnings_growth, institutional_consensus,
                     valuation_attractiveness, policy_impact,
                     technical_momentum, risk_adjusted_return
    """
    from app.scoring.rubric import SECTOR_CRITERIA

    items = {}
    for key, criteria in SECTOR_CRITERIA.items():
        llm = llm_scores.get(key, {})
        score = min(float(llm.get("score", criteria["max_score"] * 0.5)), criteria["max_score"])
        items[key] = ScoreItem(
            name=key.replace("_", " ").title(),
            score=round(score, 1),
            max_score=criteria["max_score"],
            description=llm.get("description", ""),
        )

    total = sum(item.score for item in items.values())
    return SectorScore(
        total=round(total, 1),
        earnings_growth=items["earnings_growth"],
        institutional_consensus=items["institutional_consensus"],
        valuation_attractiveness=items["valuation_attractiveness"],
        policy_impact=items["policy_impact"],
        technical_momentum=items["technical_momentum"],
        risk_adjusted_return=items["risk_adjusted_return"],
    )
