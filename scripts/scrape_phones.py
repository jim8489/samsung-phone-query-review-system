from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.data.seed import DEMO_PHONES  # noqa: E402
from app.database import SessionLocal, init_database  # noqa: E402
from app.models import Phone  # noqa: E402
from app.scraper.gsmarena import GSMArenaScraper  # noqa: E402
from app.services.catalog import upsert_scraped_phone  # noqa: E402


TESTED_CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/157.0.0.0 Safari/537.36"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Automatically crawl Samsung's public GSMArena manufacturer catalogue, "
            "follow exact handset specification links, parse each page with BeautifulSoup, "
            "and upsert the results into the configured SQLAlchemy database. "
            "This avoids the quick-search endpoint, which may return Turnstile."
        )
    )
    parser.add_argument(
        "--models",
        nargs="+",
        help="Model names, e.g. 'Galaxy S21' 'Galaxy S23 Ultra'. Defaults to the 12 configured Samsung models.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=max(settings.scraper_delay_seconds, 3.0),
        help="Minimum delay between HTTP requests; the scraper enforces at least 2 seconds.",
    )
    parser.add_argument(
        "--user-agent",
        default=TESTED_CHROME_USER_AGENT,
        help=(
            "User-Agent used for requests. Defaults to the Chrome 157 User-Agent that "
            "successfully accessed the Samsung catalogue and direct S23 page in the user's diagnostic."
        ),
    )
    parser.add_argument(
        "--max-catalogue-pages",
        type=int,
        default=30,
        help="Maximum Samsung catalogue pages to follow when older models are not on the first page.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop after the first failed phone. By default, later models are still attempted.",
    )
    args = parser.parse_args()

    models = args.models or [item["name"].replace("Samsung ", "") for item in DEMO_PHONES]
    models = list(dict.fromkeys(model.strip() for model in models if model.strip()))
    if not models:
        parser.error("At least one Samsung model must be supplied.")
    if len(models) > settings.scraper_max_models_per_run:
        parser.error(f"At most {settings.scraper_max_models_per_run} models are allowed per run.")
    if args.delay < 2.0:
        parser.error("Use a request delay of at least 2 seconds for respectful scraping.")
    if args.max_catalogue_pages < 1:
        parser.error("--max-catalogue-pages must be at least 1.")

    init_database()
    scraper = GSMArenaScraper(
        delay_seconds=args.delay,
        user_agent=args.user_agent,
        max_catalogue_pages=args.max_catalogue_pages,
    )
    print("[INFO] Automated HTTP + BeautifulSoup crawler started.")
    print("[INFO] Discovery source: https://www.gsmarena.com/samsung-phones-9.php")
    print("[INFO] The GSMArena quick-search endpoint is not used.")
    print(f"[INFO] Target models: {len(models)}; request delay: {args.delay:.1f}s")

    scraped = 0
    failed = 0
    failure_details: list[str] = []
    try:
        with SessionLocal() as db:
            for index, model in enumerate(models, start=1):
                try:
                    print(f"\n[{index}/{len(models)}] Collecting {model} ...", flush=True)
                    item = scraper.scrape_detail(model)
                    phone = upsert_scraped_phone(db, item)
                    db.commit()
                    scraped += 1
                    normalized = item.normalized
                    active = normalized.get("active_use_score_minutes")
                    active_text = f"{active // 60}:{active % 60:02d}h" if active is not None else "not recorded"
                    endurance = normalized.get("endurance_rating_hours")
                    rows = sum(len(section_rows) for section_rows in item.raw_specs.values())
                    print(
                        f"[OK] {phone.name}: {rows} specification rows; "
                        f"{len(item.price_observations)} price observations"
                    )
                    print(f"     Display: {normalized.get('display_size') or 'not listed'}")
                    print(f"     Chipset: {normalized.get('chipset') or 'not listed'}")
                    print(f"     Rear camera: {normalized.get('camera_rear') or 'not listed'}")
                    print(f"     Battery: {normalized.get('battery_capacity_mah') or 'not listed'} mAh")
                    print(
                        f"     GSMArena measured battery: active use {active_text}; "
                        f"endurance {f'{endurance}h' if endurance is not None else 'not recorded'}"
                    )
                    print(f"     Source: {item.source_url}")
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    message = f"{model}: {type(exc).__name__}: {exc}"
                    failure_details.append(message)
                    print(f"[FAILED] {message}")
                    if args.stop_on_error:
                        break
    finally:
        scraper.close()

    with SessionLocal() as db:
        live_count = db.scalar(
            select(func.count()).select_from(Phone).where(Phone.data_quality == "scraped")
        ) or 0

    print("\n========== SCRAPE SUMMARY ==========")
    print(f"Models attempted: {min(len(models), scraped + failed)} / {len(models)}")
    print(f"Successfully scraped this run: {scraped}")
    print(f"Failed this run: {failed}")
    print(f"Samsung catalogue pages visited: {scraper._catalogue_page_count}")
    print(f"Live GSMArena records currently in database: {live_count}")
    print("Only successfully parsed GSMArena phone-detail pages are marked data_quality='scraped'.")
    if failure_details:
        print("\nFailures:")
        for detail in failure_details:
            print(f"- {detail}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
