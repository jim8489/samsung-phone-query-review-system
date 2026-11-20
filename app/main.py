from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, phones, reviews, scraper, system
from app.config import settings
from app.database import SessionLocal, init_database
from app.data.seed import seed_demo_data

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    if settings.seed_demo_data:
        with SessionLocal() as db:
            seed_demo_data(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "A Samsung smartphone research system with catalogue-driven Requests and "
        "BeautifulSoup GSMArena collection, SQL database, BM25 RAG chatbot, "
        "LangChain specialist agents and an optional local Ollama LLM."
    ),
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(system.router, prefix=settings.api_prefix)
app.include_router(phones.router, prefix=settings.api_prefix)
app.include_router(chat.router, prefix=settings.api_prefix)
app.include_router(reviews.router, prefix=settings.api_prefix)
app.include_router(scraper.router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")
