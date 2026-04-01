from __future__ import annotations

from app.models.market import MarketRegime


def regime_tailwind_label(stance: str) -> str:
    if stance == "risk_on":
        return "tailwind"
    if stance == "risk_off":
        return "headwind"
    return "mixed"


def build_placeholder_market_regime(
    *,
    country_code: str,
    index_name: str,
    note: str,
) -> MarketRegime:
    return MarketRegime(
        label=f"{country_code} 빠른 스냅샷",
        stance="neutral",
        trend="range",
        volatility="normal",
        breadth="mixed",
        score=50.0,
        conviction=38.0,
        summary=note,
        playbook=[
            f"{index_name} 정밀 국면 계산이 완료되기 전까지 1차 시세 스캔 후보를 우선 제공합니다.",
            "이번 응답에서는 사용 가능한 후보 스냅샷을 만들지 못했습니다. 잠시 뒤 다시 열어 fresh quick 스냅샷을 다시 시도해 주세요.",
        ],
        warnings=["이번 응답은 사용 가능한 후보를 만들지 못해 시장 국면만 먼저 표시합니다."],
        signals=[],
    )

