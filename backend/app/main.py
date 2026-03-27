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
from app.exceptions import ApiAppException
from app.routers import account, country, sector, stock, watchlist, compare, archive, calendar, export, screener, portfolio, system, research, briefing
from app.runtime import get_runtime_state, reset_runtime_state, upsert_startup_task
from app.services import archive_service, market_service, research_archive_service
from app.version import APP_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

startup_log = logging.getLogger("stock_predict.startup")


async def _run_startup_task(
    *,
    name: str,
    running_detail: str,
    success_detail: str,
    failure_prefix: str,
    timeout_seconds: int,
    job,
) -> None:
    upsert_startup_task(name, "running", running_detail)
    try:
        await asyncio.wait_for(job(), timeout=timeout_seconds)
    except asyncio.CancelledError:
        startup_log.info("Startup task '%s' cancelled during shutdown.", name)
        raise
    except asyncio.TimeoutError:
        startup_log.warning(
            "%s: startup time budget (%ss) was reached; service will continue without waiting for completion.",
            failure_prefix,
            timeout_seconds,
        )
        readable_name = name.replace("_", " ")
        upsert_startup_task(
            name,
            "ok",
            (
                f"Startup window ended before {readable_name} finished. "
                "서비스는 계속 시작되며, 해당 보강 작업은 다음 워밍업이나 수동 재시도에서 다시 반영됩니다."
            ),
        )
    except Exception as exc:
        startup_log.warning("%s: %s", failure_prefix, exc, exc_info=True)
        upsert_startup_task(
            name,
            "warning",
            f"Startup continued without {name.replace('_', ' ')}: {exc}",
        )
    else:
        upsert_startup_task(name, "ok", success_detail)


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks: list[asyncio.Task] = []
    reset_runtime_state()
    upsert_startup_task("database_initialize", "running", "Initializing SQLite database.")
    await db.initialize()
    upsert_startup_task("database_initialize", "ok", "Database initialization complete.")

    if settings.startup_prediction_accuracy_refresh:
        upsert_startup_task(
            "prediction_accuracy_refresh",
            "running",
            "Refreshing stored next-day prediction accuracy in background.",
        )
        background_tasks.append(
            asyncio.create_task(
                _run_startup_task(
                    name="prediction_accuracy_refresh",
                    running_detail="Refreshing stored next-day prediction accuracy in background.",
                    success_detail="Prediction accuracy refresh completed.",
                    failure_prefix="Prediction accuracy refresh failed during startup",
                    timeout_seconds=settings.startup_prediction_accuracy_refresh_timeout,
                    job=lambda: archive_service.refresh_prediction_accuracy(limit=100),
                )
            )
        )
    else:
        upsert_startup_task(
            "prediction_accuracy_refresh",
            "ok",
            "Prediction accuracy refresh skipped by configuration.",
        )

    if settings.startup_research_archive_sync:
        upsert_startup_task(
            "research_archive_sync",
            "running",
            "Syncing curated public research archive in background.",
        )
        background_tasks.append(
            asyncio.create_task(
                _run_startup_task(
                    name="research_archive_sync",
                    running_detail="Syncing curated public research archive in background.",
                    success_detail="Curated research archive refresh completed.",
                    failure_prefix="Research archive sync failed during startup",
                    timeout_seconds=settings.startup_research_archive_sync_timeout,
                    job=lambda: research_archive_service.sync_public_research_reports(force=False),
                )
            )
        )
    else:
        upsert_startup_task(
            "research_archive_sync",
            "ok",
            "Curated research archive sync skipped by configuration.",
        )

    if settings.startup_market_opportunity_prewarm:
        upsert_startup_task(
            "market_opportunity_prewarm",
            "running",
            "Prewarming KR opportunity radar cache in background.",
        )
        background_tasks.append(
            asyncio.create_task(
                _run_startup_task(
                    name="market_opportunity_prewarm",
                    running_detail="Prewarming KR opportunity radar cache in background.",
                    success_detail="KR opportunity radar prewarm completed.",
                    failure_prefix="Market opportunity prewarm failed during startup",
                    timeout_seconds=settings.startup_market_opportunity_prewarm_timeout,
                    job=lambda: market_service.get_market_opportunities_quick("KR", limit=12),
                )
            )
        )
    else:
        upsert_startup_task(
            "market_opportunity_prewarm",
            "ok",
            "KR opportunity radar prewarm skipped by configuration.",
        )
    try:
        yield
    finally:
        for task in background_tasks:
            if not task.done():
                task.cancel()
        if background_tasks:
            await asyncio.gather(*background_tasks, return_exceptions=True)


app = FastAPI(
    title="Stock Predict API",
    description="AI-powered stock market analysis for the Korean market",
    version=APP_VERSION,
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
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


@app.exception_handler(ApiAppException)
async def api_app_exception_handler(request: Request, exc: ApiAppException):
    return JSONResponse(status_code=exc.status_code, content=exc.error.to_dict(), headers=exc.headers)


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
app.include_router(account.router)
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
app.include_router(briefing.router)


@app.get("/api/health")
async def health():
    runtime_state = get_runtime_state()
    return {
        "status": runtime_state["status"],
        "version": APP_VERSION,
        "startup_tasks": runtime_state["startup_tasks"],
    }

