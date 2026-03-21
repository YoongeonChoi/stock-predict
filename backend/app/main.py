from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import db
from app.routers import country, sector, stock, watchlist, compare, archive, calendar, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.initialize()
    yield


app = FastAPI(
    title="Stock Predict API",
    description="AI-powered stock market analysis for US, KR, JP markets",
    version="1.0.0",
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

app.include_router(country.router)
app.include_router(sector.router)
app.include_router(stock.router)
app.include_router(watchlist.router)
app.include_router(compare.router)
app.include_router(archive.router)
app.include_router(calendar.router)
app.include_router(export.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
