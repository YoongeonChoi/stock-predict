import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import db
from app.errors import AppError
from app.routers import country, sector, stock, watchlist, compare, archive, calendar, export, screener, portfolio, system, research
from app.runtime import get_runtime_state, reset_runtime_state, upsert_startup_task
from app.services import archive_service
from app.version import APP_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

startup_log = logging.getLogger("stock_predict.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_runtime_state()
    upsert_startup_task("database_initialize", "running", "Initializing SQLite database.")
    await db.initialize()
    upsert_startup_task("database_initialize", "ok", "Database initialization complete.")

    upsert_startup_task("prediction_accuracy_refresh", "running", "Refreshing stored next-day prediction accuracy.")
    try:
        await asyncio.wait_for(
            archive_service.refresh_prediction_accuracy(limit=100),
            timeout=20,
        )
    except Exception as exc:
        startup_log.warning("Prediction accuracy refresh failed during startup: %s", exc, exc_info=True)
        upsert_startup_task(
            "prediction_accuracy_refresh",
            "warning",
            f"Startup continued without accuracy refresh: {exc}",
        )
    else:
        upsert_startup_task("prediction_accuracy_refresh", "ok", "Prediction accuracy refresh completed.")
    yield


app = FastAPI(
    title="Stock Predict API",
    description="AI-powered stock market analysis for US, KR, JP markets",
    version=APP_VERSION,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log = logging.getLogger("stock_predict.unhandled")
    log.error(f"[SP-9999] Unhandled: {request.url.path} -> {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "SP-9999",
            "message": "Unexpected server error",
            "detail": str(exc)[:300],
        },
    )


app.include_router(country.router)
app.include_router(sector.router)
app.include_router(stock.router)
app.include_router(watchlist.router)
app.include_router(compare.router)
app.include_router(archive.router)
app.include_router(calendar.router)
app.include_router(export.router)
app.include_router(screener.router)
app.include_router(portfolio.router)
app.include_router(system.router)
app.include_router(research.router)


@app.get("/api/health")
async def health():
    runtime_state = get_runtime_state()
    return {
        "status": runtime_state["status"],
        "version": APP_VERSION,
        "startup_tasks": runtime_state["startup_tasks"],
    }
