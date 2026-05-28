from __future__ import annotations

import json
from datetime import datetime

from app.database import db


def _direction_label(value: str | None) -> str:
    return {"up": "상승", "down": "하락", "flat": "보합"}.get(str(value or ""), "없음")


def _parse_json_dict(raw_value) -> dict:
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _outcome_label(outcome: str | None) -> str:
    return {
        "target_zone_touched": "목표 구간 도달",
        "stop_loss_touched": "손절 구간 접촉",
        "target_and_stop_touched_order_unknown": "목표·손절 모두 접촉",
        "entry_touched": "매수 구간 접촉",
        "not_triggered": "진입 미발생",
    }.get(str(outcome or ""), "평가 대기")


def _weekly_plan_from_row(row: dict) -> dict:
    execution = _parse_json_dict(row.get("execution_json"))
    calibration = _parse_json_dict(row.get("calibration_json"))
    plan = execution if execution else calibration.get("weekly_trade_plan") if isinstance(calibration.get("weekly_trade_plan"), dict) else {}
    if not plan:
        return {}
    outcome = execution.get("outcome") if execution else None
    return {
        "target_date": row["target_date"],
        "reference_date": row.get("reference_date"),
        "action": plan.get("action"),
        "buy_price": plan.get("buy_price"),
        "buy_zone_low": plan.get("buy_zone_low"),
        "buy_zone_high": plan.get("buy_zone_high"),
        "sell_price": plan.get("sell_price"),
        "sell_zone_low": plan.get("sell_zone_low"),
        "sell_zone_high": plan.get("sell_zone_high"),
        "stop_loss": plan.get("stop_loss"),
        "window_low": execution.get("window_low") or row.get("actual_window_low"),
        "window_high": execution.get("window_high") or row.get("actual_window_high"),
        "actual_close": row.get("actual_close"),
        "buy_zone_touched": execution.get("buy_zone_touched"),
        "buy_price_touched": execution.get("buy_price_touched"),
        "sell_zone_touched": execution.get("sell_zone_touched"),
        "sell_price_touched": execution.get("sell_price_touched"),
        "stop_loss_touched": execution.get("stop_loss_touched"),
        "actual_return_pct": execution.get("actual_return_pct"),
        "outcome": outcome,
        "outcome_label": _outcome_label(outcome),
        "confidence": round(float(row.get("confidence") or plan.get("confidence") or 0.0), 2),
        "up_probability": round(float(row.get("up_probability") or plan.get("p_up") or 0.0), 2),
        "model_version": row.get("model_version") or "unknown",
        "created_at": row.get("created_at"),
    }


def _weekly_plan_summary(history: list[dict]) -> dict:
    history = [item for item in history if item]
    if not history:
        return {
            "available": False,
            "message": "이 종목의 5거래일 실행 판단 검증 이력이 아직 부족합니다.",
            "history": [],
        }
    evaluated = [item for item in history if item.get("outcome")]
    target_hits = [item for item in evaluated if item.get("sell_zone_touched")]
    stop_hits = [item for item in evaluated if item.get("stop_loss_touched")]
    return {
        "available": True,
        "evaluated_count": len(evaluated),
        "target_hit_rate": round(len(target_hits) / len(evaluated) * 100.0, 1) if evaluated else None,
        "stop_hit_rate": round(len(stop_hits) / len(evaluated) * 100.0, 1) if evaluated else None,
        "message": (
            f"최근 5거래일 실행안 {len(evaluated)}건 중 목표 구간 도달 {len(target_hits)}건, 손절 접촉 {len(stop_hits)}건을 기록했습니다."
            if evaluated
            else "5거래일 실행안은 저장됐지만 아직 target date가 지나지 않아 평가 대기 중입니다."
        ),
        "history": history,
    }


async def get_stock_forecast_delta(ticker: str, limit: int = 8) -> dict:
    rows = await db.prediction_symbol_history(
        symbol=ticker.upper(),
        scope="stock",
        prediction_type="next_day",
        limit=max(3, min(limit, 20)),
    )
    weekly_rows = await db.prediction_symbol_history(
        symbol=ticker.upper(),
        scope="stock",
        prediction_type="distributional_5d",
        limit=max(3, min(limit, 20)),
    )
    weekly_plan = _weekly_plan_summary([_weekly_plan_from_row(row) for row in weekly_rows])
    if not rows:
        return {
            "generated_at": datetime.now().isoformat(),
            "ticker": ticker.upper(),
            "history": [],
            "weekly_plan": weekly_plan,
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
        "weekly_plan": weekly_plan,
    }
