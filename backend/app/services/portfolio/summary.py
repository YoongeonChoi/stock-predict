from __future__ import annotations


def build_asset_summary(
    *,
    profile: dict,
    total_invested: float,
    total_current: float,
    total_pnl: float,
    holding_count: int,
) -> dict[str, float | int]:
    tracked_total_assets = float(profile.get("total_assets") or 0.0)
    cash_balance = float(profile.get("cash_balance") or 0.0)
    monthly_budget = float(profile.get("monthly_budget") or 0.0)

    total_assets = max(tracked_total_assets, total_current + cash_balance)
    other_assets = max(total_assets - total_current - cash_balance, 0.0)
    total_pnl_pct = (total_pnl / total_invested * 100.0) if total_invested else 0.0
    stock_ratio_pct = (total_current / total_assets * 100.0) if total_assets else 0.0
    cash_ratio_pct = (cash_balance / total_assets * 100.0) if total_assets else 0.0
    other_assets_ratio_pct = (other_assets / total_assets * 100.0) if total_assets else 0.0
    asset_gap = tracked_total_assets - (total_current + cash_balance)

    return {
        "total_invested": round(total_invested, 2),
        "total_current": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "holding_count": holding_count,
        "total_assets": round(total_assets, 2),
        "cash_balance": round(cash_balance, 2),
        "other_assets": round(other_assets, 2),
        "stock_ratio_pct": round(stock_ratio_pct, 2),
        "cash_ratio_pct": round(cash_ratio_pct, 2),
        "other_assets_ratio_pct": round(other_assets_ratio_pct, 2),
        "monthly_budget": round(monthly_budget, 2),
        "deployable_cash": round(cash_balance + monthly_budget, 2),
        "asset_gap": round(asset_gap, 2),
        "unrealized_pnl_pct_of_assets": round((total_pnl / total_assets * 100.0) if total_assets else 0.0, 2),
    }


def execution_mix(holdings: list[dict]) -> list[dict]:
    ordering = [
        "press_long",
        "lean_long",
        "stay_selective",
        "reduce_risk",
        "capital_preservation",
    ]
    grouped: dict[str, dict] = {}
    for holding in holdings:
        bias = holding.get("execution_bias") or "stay_selective"
        bucket = grouped.setdefault(bias, {"bias": bias, "count": 0, "weight": 0.0})
        bucket["count"] += 1
        bucket["weight"] += float(holding.get("weight_pct") or 0.0)

    results = []
    for bias in ordering:
        if bias in grouped:
            item = grouped[bias]
            item["weight"] = round(item["weight"], 2)
            results.append(item)
    return results
