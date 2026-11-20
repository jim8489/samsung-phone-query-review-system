from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Tests must never read from or write to a developer's .env-configured catalogue.
# conftest.py is imported before test modules, so these values are in place before
# app.config/app.database construct their module-level Settings and SQLAlchemy engine.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SEED_DEMO_DATA"] = "true"
os.environ["LLM_PROVIDER"] = "none"
os.environ["AGENT_FRAMEWORK"] = "custom"

from app.database import Base, engine as application_test_engine  # noqa: E402
from app import models  # noqa: F401,E402
from app.data.seed import seed_demo_data  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def verify_test_database_is_isolated():
    assert application_test_engine.dialect.name == "sqlite"
    assert application_test_engine.url.database in {None, ""}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSession()
    seed_demo_data(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
