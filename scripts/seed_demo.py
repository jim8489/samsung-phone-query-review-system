import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.seed import seed_demo_data  # noqa: E402
from app.database import SessionLocal, init_database  # noqa: E402


def main() -> None:
    init_database()
    with SessionLocal() as db:
        inserted = seed_demo_data(db)
        print(f"Demo catalogue ready. Inserted {inserted} new phone records.")


if __name__ == "__main__":
    main()
