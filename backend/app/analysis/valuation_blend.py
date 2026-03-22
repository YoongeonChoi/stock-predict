"""Reusable deterministic valuation anchors."""

from __future__ import annotations

from app.models.stock import BuySellGuide, ValuationMethod


def build_quick_buy_sell(info: dict) -> BuySellGuide:
    current_price = float(info.get("current_price") or 0)
    target_mean = float(info.get("target_mean") or 0)
    week52_high = float(info.get("52w_high") or 0)
    week52_low = float(info.get("52w_low") or 0)

    fair_inputs = [current_price] if current_price else []
    if target_mean > 0:
        fair_inputs.append(target_mean)
    if week52_high > 0 and week52_low > 0:
        fair_inputs.append((week52_high + week52_low) / 2.0)
    fair_value = sum(fair_inputs) / len(fair_inputs) if fair_inputs else current_price
    if fair_value <= 0:
        fair_value = current_price

    buy_zone_high = fair_value * 0.97
    buy_zone_low = buy_zone_high * 0.96
    sell_zone_low = max(fair_value * 1.06, current_price * 1.03)
    sell_zone_high = max(fair_value * 1.12, sell_zone_low * 1.05)
    rr = ((sell_zone_low - current_price) / max(current_price - buy_zone_high, 1e-6)) if current_price > buy_zone_high else 0.0

    methods = [
        ValuationMethod(
            name="Current Price Anchor",
            value=round(current_price, 2),
            weight=0.4,
            details="Baseline anchor from latest market price.",
        ),
    ]
    if target_mean > 0:
        methods.append(
            ValuationMethod(
                name="Analyst Mean Target",
                value=round(target_mean, 2),
                weight=0.4,
                details="Consensus sell-side target.",
            )
        )
    if week52_high > 0 and week52_low > 0:
        methods.append(
            ValuationMethod(
                name="52-Week Midpoint",
                value=round((week52_high + week52_low) / 2.0, 2),
                weight=0.2,
                details="Mid-cycle anchor from the 52-week trading range.",
            )
        )

    confidence_grade = "B" if target_mean > 0 and week52_high > 0 and week52_low > 0 else "C"
    return BuySellGuide(
        buy_zone_low=round(buy_zone_low, 2),
        buy_zone_high=round(buy_zone_high, 2),
        fair_value=round(fair_value, 2),
        sell_zone_low=round(sell_zone_low, 2),
        sell_zone_high=round(sell_zone_high, 2),
        risk_reward_ratio=round(max(rr, 0.0), 2),
        confidence_grade=confidence_grade,
        methodology=methods,
        summary="Deterministic valuation blend based on current price, analyst target, and 52-week range.",
    )
