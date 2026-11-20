from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal, init_database  # noqa: E402
from app.models import Phone  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the live GSMArena records needed for the Samsung phone assessment."
    )
    parser.add_argument("--minimum", type=int, default=10, help="Minimum required successfully scraped phones (default: 10).")
    parser.add_argument("--maximum", type=int, default=15, help="Maximum target phone count (default: 15).")
    args = parser.parse_args()
    if args.minimum < 1 or args.maximum < args.minimum:
        parser.error("Require 1 <= minimum <= maximum.")

    init_database()
    with SessionLocal() as db:
        phones = list(
            db.scalars(
                select(Phone).where(Phone.data_quality == "scraped").order_by(Phone.name.asc())
            ).all()
        )

    print(f"Live GSMArena records: {len(phones)} (required: {args.minimum}–{args.maximum})")
    incomplete = []
    for phone in phones:
        sections = len(phone.raw_specs or {})
        row_count = sum(len(rows) for rows in (phone.raw_specs or {}).values())
        is_complete = bool(phone.source_url and phone.scraped_at and sections >= 4 and row_count >= 15)
        print(
            f"{'[OK]' if is_complete else '[CHECK]'} {phone.name}: "
            f"{sections} sections, {row_count} rows, source={'yes' if phone.source_url else 'no'}, "
            f"timestamp={'yes' if phone.scraped_at else 'no'}"
        )
        if not is_complete:
            incomplete.append(phone.name)

    if not args.minimum <= len(phones) <= args.maximum:
        raise SystemExit("FAIL: live scraped phone count is outside the assessment target range.")
    if incomplete:
        raise SystemExit("FAIL: incomplete live records: " + ", ".join(incomplete))
    print("PASS: the live catalogue meets the count, provenance and specification-row checks.")


if __name__ == "__main__":
    main()
