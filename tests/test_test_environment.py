from app.database import engine


def test_pytest_application_database_is_in_memory_and_isolated():
    assert engine.dialect.name == "sqlite"
    assert engine.url.database in {None, ""}
