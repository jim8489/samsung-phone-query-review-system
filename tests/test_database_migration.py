from __future__ import annotations

from sqlalchemy import create_engine, func, select

from app.database import Base
from app.models import ChatMessage, ChatSession, Phone, PhoneSpecification, PriceObservation
from scripts.migrate_database import migrate_database


def test_migrate_database_copies_rows_without_modifying_source(tmp_path):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    source_url = f"sqlite:///{source}"
    target_url = f"sqlite:///{target}"

    source_engine = create_engine(source_url)
    Base.metadata.create_all(source_engine)
    with source_engine.begin() as connection:
        connection.execute(
            Phone.__table__.insert().values(
                id=1,
                slug="samsung-galaxy-migration-test",
                name="Samsung Galaxy Migration Test",
                brand="Samsung",
                source_name="GSMArena",
                source_url="https://www.gsmarena.com/samsung_galaxy_migration_test-99999.php",
                data_quality="scraped",
                raw_specs={"Display": {"Size": "6.1 inches"}},
            )
        )
        connection.execute(
            PhoneSpecification.__table__.insert().values(
                id=1, phone_id=1, section="Display", spec_name="Size", spec_value="6.1 inches"
            )
        )
        connection.execute(
            PriceObservation.__table__.insert().values(
                id=1, phone_id=1, amount=299.99, currency="USD", source="Test merchant", is_current=True
            )
        )
        connection.execute(ChatSession.__table__.insert().values(id="session-migration-test"))
        connection.execute(
            ChatMessage.__table__.insert().values(
                id=1, session_id="session-migration-test", role="user", content="Compare S23 and S22", sources=[]
            )
        )
    source_engine.dispose()

    copied = migrate_database(source_url, target_url)
    assert copied["phones"] == 1
    assert copied["phone_specifications"] == 1
    assert copied["price_observations"] == 1
    assert copied["chat_sessions"] == 1
    assert copied["chat_messages"] == 1

    with create_engine(source_url).connect() as connection:
        assert connection.execute(select(func.count()).select_from(Phone.__table__)).scalar_one() == 1
    target_engine = create_engine(target_url)
    with target_engine.connect() as connection:
        assert connection.execute(select(func.count()).select_from(Phone.__table__)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(PhoneSpecification.__table__)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(PriceObservation.__table__)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(ChatSession.__table__)).scalar_one() == 1
        assert connection.execute(select(func.count()).select_from(ChatMessage.__table__)).scalar_one() == 1
    target_engine.dispose()


def test_migration_refuses_to_merge_into_nonempty_target(tmp_path):
    source_url = f"sqlite:///{tmp_path / 'source_empty.db'}"
    target_url = f"sqlite:///{tmp_path / 'target_nonempty.db'}"
    target_engine = create_engine(target_url)
    Base.metadata.create_all(target_engine)
    with target_engine.begin() as connection:
        connection.execute(
            Phone.__table__.insert().values(slug="existing", name="Existing", brand="Samsung")
        )
    target_engine.dispose()

    try:
        migrate_database(source_url, target_url)
    except RuntimeError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("Migration must not merge into a non-empty target silently.")
