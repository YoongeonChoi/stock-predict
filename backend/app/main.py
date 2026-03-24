import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import get_settings
from app.database import db
from app.errors import SP_6009, SP_6010, SP_6011, SP_6012, SP_9999
from app.routers import country, sector, stock, watchlist, compare, archive, calendar, export, screener, portfolio, system, research
from app.runtime import get_runtime_state, reset_runtime_state, upsert_startup_task
from app.services import archive_service, research_archive_service
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

    upsert_startup_task("research_archive_sync", "running", "Syncing curated public research archive.")
    try:
        await asyncio.wait_for(
            research_archive_service.sync_public_research_reports(force=False),
            timeout=35,
        )
    except Exception as exc:
        startup_log.warning("Research archive sync failed during startup: %s", exc, exc_info=True)
        upsert_startup_task(
            "research_archive_sync",
            "warning",
            f"Startup continued without external research refresh: {exc}",
        )
    else:
        upsert_startup_task("research_archive_sync", "ok", "Curated research archive refresh completed.")
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
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log = logging.getLogger("stock_predict.unhandled")
    log.error(f"[SP-9999] Unhandled: {request.url.path} -> {exc}", exc_info=True)
    err = SP_9999(str(exc)[:300])
    return JSONResponse(
        status_code=500,
        content=err.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    detail_parts = []
    for item in exc.errors():
        location = " > ".join(str(part) for part in item.get("loc", []) if part != "body")
        message = item.get("msg", "Invalid input")
        detail_parts.append(f"{location}: {message}" if location else message)
    detail = "; ".join(detail_parts)[:300]

    if request.url.path.startswith("/api/portfolio/holdings"):
        err = SP_6009(detail)
    else:
        err = SP_6010(detail)
    err.log("warning")
    return JSONResponse(status_code=422, content=err.to_dict())


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if not request.url.path.startswith("/api/"):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    if exc.status_code == 404:
        err = SP_6011(request.url.path)
        err.log("warning")
        return JSONResponse(status_code=404, content=err.to_dict())
    if exc.status_code == 405:
        err = SP_6012(f"{request.method} {request.url.path}")
        err.log("warning")
        return JSONResponse(status_code=405, content=err.to_dict())

    err = SP_6010(str(exc.detail)[:300])
    err.log("warning")
    return JSONResponse(status_code=exc.status_code, content=err.to_dict())


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

