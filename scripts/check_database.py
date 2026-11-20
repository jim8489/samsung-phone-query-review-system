from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select, text  # noqa: E402

from app.database import SessionLocal, engine, init_database  # noqa: E402
from app.models import Phone, PhoneSpecification, PriceObservation  # noqa: E402


def main() -> None:
    init_database()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        if engine.dialect.name == "postgresql":
            version = connection.execute(text("SELECT version()")).scalar_one()
            print(f"Database: PostgreSQL ({version.split(',')[0]})")
        else:
            print(f"Database: {engine.dialect.name}")

    with SessionLocal() as db:
        phones = db.scalar(select(func.count()).select_from(Phone)) or 0
        live = db.scalar(
            select(func.count()).select_from(Phone).where(Phone.data_quality == "scraped")
        ) or 0
        specs = db.scalar(select(func.count()).select_from(PhoneSpecification)) or 0
        prices = db.scalar(select(func.count()).select_from(PriceObservation)) or 0

    print(f"Phones: {phones}")
    print(f"Live GSMArena phones: {live}")
    print(f"Specification rows: {specs}")
    print(f"Price observations: {prices}")
    if engine.dialect.name == "postgresql":
        print("[PASS] PostgreSQL connection and schema are available.")
    else:
        print("[INFO] The application is currently using SQLite. PostgreSQL is supported but not active.")


if __name__ == "__main__":
    main()
