from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, init_database  # noqa: E402
from app.scraper.gsmarena import GSMArenaScraper  # noqa: E402
from app.services.catalog import upsert_scraped_phone  # noqa: E402


def _collect_files(paths: list[str], directory: str) -> list[Path]:
    if paths:
        files = [Path(value).expanduser().resolve() for value in paths]
    else:
        root = Path(directory).expanduser()
        if not root.is_absolute():
            root = PROJECT_ROOT / root
        files = sorted(
            path.resolve()
            for pattern in ("*.html", "*.htm", "*.txt")
            for path in root.glob(pattern)
        )
    return [path for path in files if path.is_file()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import browser-saved GSMArena phone specification pages into the project database. "
            "This is useful when the website requires human verification for automated requests."
        )
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Saved HTML file(s). If omitted, imports HTML/HTM/TXT files from data/gsmarena_html.",
    )
    parser.add_argument(
        "--directory",
        default="data/gsmarena_html",
        help="Directory scanned when no file paths are provided (default: data/gsmarena_html).",
    )
    args = parser.parse_args()

    files = _collect_files(args.files, args.directory)
    if not files:
        print("No saved pages found.")
        print("Save GSMArena phone specification pages into data/gsmarena_html and run this command again.")
        raise SystemExit(2)

    init_database()
    imported = 0
    failed = 0
    with SessionLocal() as db:
        for path in files:
            try:
                html = path.read_text(encoding="utf-8-sig", errors="replace")
                item = GSMArenaScraper.parse_detail_html(html)
                phone = upsert_scraped_phone(db, item)
                db.commit()
                imported += 1
                normalized = item.normalized
                print(f"[OK] {phone.name}")
                print(f"     Source: {item.source_url}")
                print(
                    "     Display: {display}; chipset: {chipset}; battery: {battery} mAh; "
                    "active use: {active}; endurance: {endurance}".format(
                        display=normalized.get("display_size") or "not parsed",
                        chipset=normalized.get("chipset") or "not parsed",
                        battery=normalized.get("battery_capacity_mah") or "not parsed",
                        active=(
                            f"{normalized['active_use_score_minutes'] // 60}:"
                            f"{normalized['active_use_score_minutes'] % 60:02d}h"
                            if normalized.get("active_use_score_minutes") is not None
                            else "not listed"
                        ),
                        endurance=(
                            f"{normalized['endurance_rating_hours']}h"
                            if normalized.get("endurance_rating_hours") is not None
                            else "not listed"
                        ),
                    )
                )
                print(f"     Stored {sum(len(values) for values in item.raw_specs.values())} specification rows from {path.name}")
            except Exception as exc:
                db.rollback()
                failed += 1
                print(f"[FAILED] {path.name}: {type(exc).__name__}: {exc}")

    print(f"Finished: {imported}/{len(files)} saved pages imported; {failed} failed.")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
