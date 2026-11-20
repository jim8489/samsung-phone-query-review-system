from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import SessionLocal
from app.data.seed import DEMO_PHONES
from app.schemas import ScrapeItemResult, ScrapeRequest, ScrapeResponse
from app.scraper.gsmarena import GSMArenaScraper
from app.services.catalog import upsert_scraped_phone

router = APIRouter(prefix="/scraper", tags=["GSMArena scraper"])


def _run_scrape(models: list[str], delay: float) -> ScrapeResponse:
    """Run blocking HTTP work with a dedicated database session in the worker thread."""
    scraper = GSMArenaScraper(delay_seconds=delay)
    results: list[ScrapeItemResult] = []
    scraped = 0
    try:
        with SessionLocal() as db:
            for model in models:
                try:
                    item = scraper.scrape_detail(model)
                    upsert_scraped_phone(db, item)
                    db.commit()
                    scraped += 1
                    results.append(ScrapeItemResult(
                        model=model, status="scraped", message="Specifications saved; test rows enriched when available.",
                        source_url=item.source_url, test_source_url=item.test_source_url,
                    ))
                except Exception as exc:  # Keep processing the rest of the requested model list.
                    db.rollback()
                    results.append(ScrapeItemResult(model=model, status="failed", message=f"{type(exc).__name__}: {exc}"))
    finally:
        scraper.close()
    return ScrapeResponse(attempted=len(models), scraped=scraped, failed=len(models) - scraped, results=results)


@router.post("/run", response_model=ScrapeResponse, summary="Scrape Samsung models from GSMArena")
async def run_scraper(
    payload: ScrapeRequest,
    x_scraper_api_key: str | None = Header(default=None),
):
    if settings.scraper_api_key and x_scraper_api_key != settings.scraper_api_key:
        raise HTTPException(status_code=401, detail="A valid X-Scraper-Api-Key header is required.")
    requested_models = payload.models or [item["name"].replace("Samsung ", "") for item in DEMO_PHONES]
    models = list(dict.fromkeys(model.strip() for model in requested_models if model.strip()))
    if len(models) > settings.scraper_max_models_per_run:
        raise HTTPException(status_code=422, detail=f"A maximum of {settings.scraper_max_models_per_run} models can be scraped per run.")
    if not models:
        raise HTTPException(status_code=422, detail="No phone models were supplied.")
    delay = payload.delay_seconds if payload.delay_seconds is not None else settings.scraper_delay_seconds
    return await run_in_threadpool(_run_scrape, models, delay)
