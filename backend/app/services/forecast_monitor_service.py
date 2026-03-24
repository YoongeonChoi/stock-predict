from __future__ import annotations

from datetime import datetime

from app.database import db


def _direction_label(value: str | None) -> str:
    return {"up": "상승", "down": "하락", "flat": "보합"}.get(str(value or ""), "없음")


async def get_stock_forecast_delta(ticker: str, limit: int = 8) -> dict:
    rows = await db.prediction_symbol_history(
        symbol=ticker.upper(),
        scope="stock",
        prediction_type="next_day",
        limit=max(3, min(limit, 20)),
    )
    if not rows:
        return {
            "generated_at": datetime.now().isoformat(),
            "ticker": ticker.upper(),
            "history": [],
            "summary": {
                "available": False,
                "message": "이 종목의 저장된 예측 이력이 아직 부족합니다.",
            },
        }

    history = []
    for row in rows:
        direction_hit = None
        if row.get("actual_close") is not None and row.get("reference_price"):
            actual_close = float(row["actual_close"])
            reference_price = float(row["reference_price"])
            direction_hit = (
                (row.get("direction") == "up" and actual_close > reference_price)
                or (row.get("direction") == "down" and actual_close < reference_price)
                or (row.get("direction") == "flat" and abs(actual_close - reference_price) / reference_price <= 0.001)
            )
        history.append(
            {
                "target_date": row["target_date"],
                "reference_date": row.get("reference_date"),
                "reference_price": float(row.get("reference_price") or 0.0),
                "predicted_close": float(row.get("predicted_close") or 0.0),
                "predicted_low": row.get("predicted_low"),
                "predicted_high": row.get("predicted_high"),
                "up_probability": round(float(row.get("up_probability") or 0.0), 2),
                "confidence": round(float(row.get("confidence") or 0.0), 2),
                "direction": row.get("direction"),
                "direction_label": _direction_label(row.get("direction")),
                "actual_close": row.get("actual_close"),
                "direction_hit": direction_hit,
                "model_version": row.get("model_version") or "unknown",
                "created_at": row.get("created_at"),
            }
        )

    latest = history[0]
    previous = history[1] if len(history) > 1 else None
    up_probability_delta = round(latest["up_probability"] - previous["up_probability"], 2) if previous else 0.0
    confidence_delta = round(latest["confidence"] - previous["confidence"], 2) if previous else 0.0
    predicted_close_delta_pct = 0.0
    if previous and previous["predicted_close"]:
        predicted_close_delta_pct = round(
            (latest["predicted_close"] - previous["predicted_close"]) / previous["predicted_close"] * 100.0,
            2,
        )

    evaluated = [item for item in history if item.get("direction_hit") is not None]
    hit_rate = round(sum(1 for item in evaluated if item["direction_hit"]) / len(evaluated) * 100.0, 1) if evaluated else None

    summary = {
        "available": True,
        "current_direction": latest["direction"],
        "current_direction_label": latest["direction_label"],
        "up_probability_delta": up_probability_delta,
        "confidence_delta": confidence_delta,
        "predicted_close_delta_pct": predicted_close_delta_pct,
        "direction_changed": bool(previous and latest["direction"] != previous["direction"]),
        "hit_rate": hit_rate,
        "message": (
            f"직전 저장값 대비 상방 확률은 {up_probability_delta:+.2f}pt, 예측 종가는 {predicted_close_delta_pct:+.2f}% 변했습니다."
            if previous
            else "저장된 예측 이력이 아직 1건뿐이라 변화량 비교는 다음 스냅샷부터 제공됩니다."
        ),
    }
    return {
        "generated_at": datetime.now().isoformat(),
        "ticker": ticker.upper(),
        "summary": summary,
        "history": history,
    }
