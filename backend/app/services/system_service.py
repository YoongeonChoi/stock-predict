"""System diagnostics and readiness summary."""

from __future__ import annotations

from app.analysis.next_day_forecast import MODEL_VERSION
from app.config import get_settings
from app.runtime import get_runtime_state
from app.services import archive_service
from app.version import APP_VERSION


def _configured(value: str) -> bool:
    return bool(str(value or "").strip())


def _source(name: str, configured: bool, purpose: str, note: str, status: str | None = None) -> dict:
    resolved_status = status or ("configured" if configured else "missing")
    return {
        "name": name,
        "configured": configured,
        "status": resolved_status,
        "purpose": purpose,
        "note": note,
    }


async def get_diagnostics() -> dict:
    settings = get_settings()
    runtime_state = get_runtime_state()

    accuracy = None
    accuracy_error = None
    try:
        accuracy = await archive_service.get_accuracy(refresh=False)
    except Exception as exc:
        accuracy_error = str(exc)

    data_sources = [
        _source(
            "OpenAI",
            _configured(settings.openai_api_key),
            "Narrative summaries and institution synthesis",
            "Missing key does not break the app, but explanations become fallback-heavy.",
        ),
        _source(
            "Financial Modeling Prep",
            _configured(settings.fmp_api_key),
            "Screeners, peers, analyst context, and market breadth",
            "When unavailable, the app falls back to smaller static universes and Yahoo data.",
        ),
        _source(
            "FRED",
            _configured(settings.fred_api_key),
            "US macro and rates context",
            "Missing key weakens US macro inputs for country analysis.",
        ),
        _source(
            "ECOS",
            _configured(settings.ecos_api_key),
            "Korean macro data",
            "Missing key weakens KR macro inputs for country analysis.",
        ),
        _source(
            "Yahoo Finance",
            True,
            "Core price history, index levels, and fallback fundamentals",
            "Primary runtime backbone for price series.",
            status="available",
        ),
        _source(
            "PyKRX",
            True,
            "Best-effort KR investor flow",
            "Only affects KR foreign/institution flow features. When data is empty, the model neutralizes the signal.",
            status="best_effort",
        ),
    ]

    status = runtime_state["status"]
    if accuracy_error and status == "ok":
        status = "degraded"

    return {
        "status": status,
        "version": APP_VERSION,
        "started_at": runtime_state["started_at"],
        "startup_tasks": runtime_state["startup_tasks"],
        "data_sources": data_sources,
        "forecast_models": [
            {
                "name": "next_day",
                "version": MODEL_VERSION,
                "markets": ["US", "KR", "JP"],
                "signals": [
                    "momentum",
                    "trend",
                    "mean_reversion",
                    "macd",
                    "volume",
                    "news_sentiment",
                    "analyst_skew",
                    "investor_flow_best_effort",
                ],
                "notes": [
                    "KR investor flow is strongest where PyKRX has coverage.",
                    "Prediction accuracy tracking is based on archived next-day forecasts.",
                ],
            }
        ],
        "prediction_accuracy": accuracy,
        "prediction_accuracy_error": accuracy_error,
    }
