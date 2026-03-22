import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import db
from app.errors import AppError
from app.routers import country, sector, stock, watchlist, compare, archive, calendar, export, screener, portfolio

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    await archive_service.refresh_prediction_accuracy(limit=100)
    yield


app = FastAPI(
    title="Stock Predict API",
    description="AI-powered stock market analysis for US, KR, JP markets",
    version="2.0.0",
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
