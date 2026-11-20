from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, func, inspect, select, text  # noqa: E402

from app.database import Base  # noqa: E402
from app import models  # noqa: F401,E402


def _row_count(connection, table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def migrate_database(source_url: str, target_url: str) -> dict[str, int]:
    """Copy all project tables from source to an empty target database.

    The operation is deliberately non-destructive: it refuses to merge into a
    target containing data. The source is read-only and is never modified.
    """
    if source_url == target_url:
        raise ValueError("Source and target DATABASE_URL values must be different.")

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(bind=target_engine)
        tables = list(Base.metadata.sorted_tables)

        with target_engine.connect() as target:
            occupied = {
                table.name: _row_count(target, table)
                for table in tables
                if table.name in inspect(target_engine).get_table_names()
            }
        nonempty = {name: count for name, count in occupied.items() if count}
        if nonempty:
            raise RuntimeError(
                "Target database is not empty; refusing to overwrite or merge data. "
                f"Non-empty tables: {nonempty}. Use a fresh database or back it up and clear it first."
            )

        copied: dict[str, int] = {}
        with source_engine.connect() as source, target_engine.begin() as target:
            source_tables = set(inspect(source_engine).get_table_names())
            for table in tables:
                if table.name not in source_tables:
                    copied[table.name] = 0
                    continue
                rows = source.execute(select(table)).mappings().all()
                if rows:
                    target.execute(table.insert(), [dict(row) for row in rows])
                copied[table.name] = len(rows)

            # Explicit IDs are preserved during migration. Advance PostgreSQL
            # sequences so future inserts cannot collide with migrated IDs.
            if target_engine.dialect.name == "postgresql":
                for table in tables:
                    primary_keys = list(table.primary_key.columns)
                    if len(primary_keys) != 1 or not hasattr(primary_keys[0].type, "python_type"):
                        continue
                    pk = primary_keys[0]
                    try:
                        is_integer_pk = pk.type.python_type is int
                    except (NotImplementedError, AttributeError):
                        is_integer_pk = False
                    if not is_integer_pk:
                        continue
                    max_id = target.execute(select(func.max(pk))).scalar_one()
                    if max_id is not None:
                        target.execute(
                            text(
                                "SELECT setval(pg_get_serial_sequence(:table_name, :column_name), :max_id, true)"
                            ),
                            {"table_name": table.name, "column_name": pk.name, "max_id": int(max_id)},
                        )

        return copied
    finally:
        source_engine.dispose()
        target_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Safely copy the existing SQLite catalogue and chat/price records into an empty PostgreSQL database. "
            "The SQLite source is never changed."
        )
    )
    parser.add_argument(
        "--source",
        default="sqlite:///./data/samsung_phones.db",
        help="Source database URL (default: current v2 SQLite database).",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Target database URL, e.g. postgresql+psycopg://user:password@localhost:5432/samsung_phones.",
    )
    args = parser.parse_args()

    try:
        counts = migrate_database(args.source, args.target)
    except Exception as exc:
        print(f"[FAILED] {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc

    print("Database migration completed. Source database was not modified.")
    total = 0
    for table, count in counts.items():
        print(f"  {table}: {count} rows copied")
        total += count
    print(f"Total rows copied: {total}")


if __name__ == "__main__":
    main()
