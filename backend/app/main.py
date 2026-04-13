import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import db
from app.services import calendar_service
from app.errors import SP_6009, SP_6010, SP_6011, SP_6012, SP_9999
from app.exceptions import ApiAppException
from app.routers import (
    account,
    archive,
    briefing,
    calendar,
    compare,
    country,
    export,
    portfolio,
    research,
    screener,
    sector,
    stock,
    system,
    watchlist,
)
from app.runtime import get_runtime_state, reset_runtime_state, upsert_startup_task
from app.utils.lazy_module import LazyModuleProxy
from app.utils.memory_hygiene import maybe_trim_process_memory
from app.version import APP_VERSION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

startup_log = logging.getLogger("stock_predict.startup")
memory_log = logging.getLogger("stock_predict.memory")
archive_service = LazyModuleProxy("app.services.archive_service")
learned_fusion_profile_service = LazyModuleProxy("app.services.learned_fusion_profile_service")
market_service = LazyModuleProxy("app.services.market_service")
research_archive_service = LazyModuleProxy("app.services.research_archive_service")
PUBLIC_API_PRE_REQUEST_TRIM_TIMEOUT_SECONDS = 0.15
_public_api_pre_request_trim_task: asyncio.Task | None = None


@dataclass(frozen=True)
class StartupTaskDefinition:
    name: str
    running_detail: str
    success_detail: str
    failure_prefix: str
    timeout_seconds: int
    job: Callable[[], Awaitable[object]]


def _startup_skip_detail(*, name: str, configured_detail: str) -> str:
    if settings.startup_memory_safe_mode and name in {
        "prediction_accuracy_refresh",
        "learned_fusion_profile_refresh",
        "research_archive_sync",
        "market_opportunity_prewarm",
    }:
        return (
            "Render 메모리 세이프 startup 프로필에서 건너뜁니다. "
            "이 보강 작업은 다음 워밍업 또는 수동 재시도에서 다시 실행할 수 있습니다."
        )
    return configured_detail


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


async def _run_startup_tasks(
    task_definitions: list[StartupTaskDefinition],
    *,
    concurrency: int,
) -> None:
    pending = list(task_definitions)
    active: set[asyncio.Task] = set()
    max_concurrency = max(1, int(concurrency))

    try:
        while pending or active:
            while pending and len(active) < max_concurrency:
                task_definition = pending.pop(0)
                active.add(
                    asyncio.create_task(
                        _run_startup_task(
                            name=task_definition.name,
                            running_detail=task_definition.running_detail,
                            success_detail=task_definition.success_detail,
                            failure_prefix=task_definition.failure_prefix,
                            timeout_seconds=task_definition.timeout_seconds,
                            job=task_definition.job,
                        )
                    )
                )
            if not active:
                break
            done, active = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                try:
                    await completed
                except asyncio.CancelledError:
                    raise
                except Exception:
                    startup_log.warning("Unexpected startup coordinator error.", exc_info=True)
    except asyncio.CancelledError:
        for task in active:
            if not task.done():
                task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)
        raise


async def _prewarm_public_dashboard_payloads() -> None:
    await country.prewarm_market_indicators_cache()
    await briefing.prewarm_daily_briefing_cache()
    await country.prewarm_primary_country_report_cache()
    await screener.prewarm_public_screener_cache_seed()
    await calendar_service.prewarm_public_calendar_cache_seed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_tasks: list[asyncio.Task] = []
    reset_runtime_state()
    upsert_startup_task("database_initialize", "running", "Initializing SQLite database.")
    await db.initialize()
    upsert_startup_task("database_initialize", "ok", "Database initialization complete.")

    startup_tasks: list[StartupTaskDefinition] = []

    if settings.effective_startup_learned_fusion_refresh:
        startup_tasks.append(
            StartupTaskDefinition(
                name="learned_fusion_profile_refresh",
                running_detail="Refreshing learned fusion profiles from stored prediction records.",
                success_detail="Learned fusion profile refresh completed.",
                failure_prefix="Learned fusion profile refresh failed during startup",
                timeout_seconds=settings.startup_learned_fusion_refresh_timeout,
                job=lambda: learned_fusion_profile_service.refresh_profiles(),
            )
        )
    else:
        upsert_startup_task(
            "learned_fusion_profile_refresh",
            "ok",
            _startup_skip_detail(
                name="learned_fusion_profile_refresh",
                configured_detail="Learned fusion profile refresh skipped by configuration.",
            ),
        )

    if settings.effective_startup_prediction_accuracy_refresh:
        startup_tasks.append(
            StartupTaskDefinition(
                name="prediction_accuracy_refresh",
                running_detail="Refreshing stored next-day prediction accuracy in background.",
                success_detail="Prediction accuracy refresh completed.",
                failure_prefix="Prediction accuracy refresh failed during startup",
                timeout_seconds=settings.effective_startup_prediction_accuracy_refresh_timeout,
                job=lambda: archive_service.refresh_prediction_accuracy(
                    limit=settings.effective_startup_prediction_accuracy_refresh_limit
                ),
            )
        )
    else:
        upsert_startup_task(
            "prediction_accuracy_refresh",
            "ok",
            _startup_skip_detail(
                name="prediction_accuracy_refresh",
                configured_detail="Prediction accuracy refresh skipped by configuration.",
            ),
        )

    if settings.effective_startup_research_archive_sync:
        startup_tasks.append(
            StartupTaskDefinition(
                name="research_archive_sync",
                running_detail="Syncing curated public research archive in background.",
                success_detail="Curated research archive refresh completed.",
                failure_prefix="Research archive sync failed during startup",
                timeout_seconds=settings.startup_research_archive_sync_timeout,
                job=lambda: research_archive_service.sync_public_research_reports(force=False),
            )
        )
    else:
        upsert_startup_task(
            "research_archive_sync",
            "ok",
            _startup_skip_detail(
                name="research_archive_sync",
                configured_detail="Curated research archive sync skipped by configuration.",
            ),
        )

    if settings.effective_startup_market_opportunity_prewarm:
        startup_tasks.append(
            StartupTaskDefinition(
                name="market_opportunity_prewarm",
                running_detail="Prewarming KR opportunity radar cache in background.",
                success_detail="KR opportunity radar prewarm completed.",
                failure_prefix="Market opportunity prewarm failed during startup",
                timeout_seconds=settings.effective_startup_market_opportunity_prewarm_timeout,
                job=lambda: market_service.get_market_opportunities_quick("KR", limit=12),
            )
        )
    else:
        upsert_startup_task(
            "market_opportunity_prewarm",
            "ok",
            _startup_skip_detail(
                name="market_opportunity_prewarm",
                configured_detail="KR opportunity radar prewarm skipped by configuration.",
            ),
        )

    if settings.effective_startup_public_dashboard_prewarm:
        startup_tasks.append(
            StartupTaskDefinition(
                name="public_dashboard_prewarm",
                running_detail="Prewarming public dashboard caches for first deployed hits.",
                success_detail="Public dashboard prewarm completed.",
                failure_prefix="Public dashboard prewarm failed during startup",
                timeout_seconds=90,
                job=_prewarm_public_dashboard_payloads,
            )
        )
    else:
        upsert_startup_task(
            "public_dashboard_prewarm",
            "ok",
            "Public dashboard prewarm skipped by configuration or because Render memory-safe startup mode is not active.",
        )

    if startup_tasks:
        startup_concurrency = settings.effective_startup_background_task_concurrency
        for index, task_definition in enumerate(startup_tasks):
            if index < startup_concurrency:
                upsert_startup_task(
                    task_definition.name,
                    "running",
                    task_definition.running_detail,
                )
            else:
                upsert_startup_task(
                    task_definition.name,
                    "queued",
                    f"{task_definition.running_detail} 앞선 startup 작업이 끝나면 이어서 시작합니다.",
                )
        background_tasks.append(
            asyncio.create_task(
                _run_startup_tasks(
                    startup_tasks,
                    concurrency=startup_concurrency,
                )
            )
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


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def _memory_hygiene_request_reason(request: Request) -> str:
    normalized = request.url.path.removeprefix("/api/").strip("/") or "health"
    return normalized.replace("/", ":")[:96]


async def _run_public_api_pre_request_trim(reason: str) -> dict[str, object]:
    return await asyncio.to_thread(maybe_trim_process_memory, reason)


def _finalize_public_api_pre_request_trim(task: asyncio.Task) -> None:
    global _public_api_pre_request_trim_task
    if _public_api_pre_request_trim_task is task:
        _public_api_pre_request_trim_task = None
    try:
        task.result()
    except asyncio.CancelledError:
        memory_log.debug("pre-request memory trim task was cancelled")
    except Exception as exc:  # pragma: no cover - best effort guard
        memory_log.debug("pre-request memory trim task failed: %s", exc, exc_info=True)


async def _maybe_schedule_public_api_pre_request_trim(reason: str) -> None:
    global _public_api_pre_request_trim_task

    task = _public_api_pre_request_trim_task
    if task is not None and not task.done():
        return

    task = asyncio.create_task(
        _run_public_api_pre_request_trim(reason),
        name="public-api-pre-request-trim",
    )
    _public_api_pre_request_trim_task = task
    task.add_done_callback(_finalize_public_api_pre_request_trim)
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=PUBLIC_API_PRE_REQUEST_TRIM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        memory_log.debug(
            "pre-request memory trim for %s exceeded %.2fs; continuing while trim finishes in background.",
            reason,
            PUBLIC_API_PRE_REQUEST_TRIM_TIMEOUT_SECONDS,
        )


@app.middleware("http")
async def public_api_memory_hygiene_middleware(request: Request, call_next):
    if (
        settings.startup_memory_safe_mode
        and request.method in {"GET", "HEAD"}
        and request.url.path.startswith("/api/")
        and request.url.path != "/api/health"
    ):
        try:
            await _maybe_schedule_public_api_pre_request_trim(
                f"pre:{_memory_hygiene_request_reason(request)}"
            )
        except Exception as exc:  # pragma: no cover - best effort guard
            memory_log.debug(
                "pre-request memory trim skipped for %s: %s",
                request.url.path,
                exc,
            )
    return await call_next(request)


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
