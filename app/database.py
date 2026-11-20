from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import ensure_sqlite_directory, settings


class Base(DeclarativeBase):
    pass


ensure_sqlite_directory(settings.database_url)
_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
        _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database() -> None:
    """Create tables and apply small additive migrations for existing local databases.

    The project uses SQLAlchemy metadata for initial setup. These additive column
    migrations keep an existing SQLite/PostgreSQL install compatible when a new
    nullable specification field is introduced between assessment versions.
    """
    # Import models so SQLAlchemy has registered all mapped tables.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "phones" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("phones")}
    additive_columns = {
        "active_use_score_minutes": "INTEGER",
        "endurance_rating_hours": "INTEGER",
        "test_source_url": "TEXT",
    }
    missing = [(name, sql_type) for name, sql_type in additive_columns.items() if name not in existing_columns]
    if missing:
        with engine.begin() as connection:
            for name, sql_type in missing:
                connection.execute(text(f"ALTER TABLE phones ADD COLUMN {name} {sql_type}"))
