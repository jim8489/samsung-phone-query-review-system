from sqlalchemy import select

from app.models import Phone, PhoneSpecification
from app.scraper.gsmarena import ScrapedPhone
from app.services.catalog import upsert_scraped_phone


def test_import_replaces_existing_demo_specs_and_is_idempotent(db_session):
    """A live scrape must safely replace a same-name demo phone's specs."""
    existing_demo = db_session.scalar(
        select(Phone).where(Phone.slug == "samsung-galaxy-s23")
    )
    assert existing_demo is not None
    assert existing_demo.data_quality == "demo_seed"
    old_count = len(existing_demo.specifications)
    assert old_count > 0

    raw_specs = {
        "Display": {
            "Type": "Dynamic AMOLED 2X, 120Hz, HDR10+",
            "Size": "6.1 inches",
            "Resolution": "1080 x 2340 pixels",
        },
        "Platform": {"Chipset": "Qualcomm Snapdragon 8 Gen 2"},
        "Main Camera": {"Triple": "50 MP + 10 MP + 12 MP"},
        "Battery": {"Type": "Li-Ion 3900 mAh"},
        "Our Tests": {
            "Battery": "Active use score 11:27h; Endurance rating 101h"
        },
    }
    item = ScrapedPhone(
        name="Samsung Galaxy S23",
        source_url="https://www.gsmarena.com/samsung_galaxy_s23-12082.php",
        test_source_url="https://www.gsmarena.com/samsung_galaxy_s23-12082.php",
        raw_specs=raw_specs,
        normalized={
            "display_size": "6.1 inches",
            "display_resolution": "1080 x 2340 pixels",
            "camera_rear": "50 MP + 10 MP + 12 MP",
            "battery_capacity_mah": 3900,
            "active_use_score_minutes": 687,
            "endurance_rating_hours": 101,
            "chipset": "Qualcomm Snapdragon 8 Gen 2",
        },
    )

    phone = upsert_scraped_phone(db_session, item)
    db_session.commit()

    assert phone.id == existing_demo.id
    assert phone.data_quality == "scraped"
    assert phone.source_url == item.source_url
    first_rows = db_session.scalars(
        select(PhoneSpecification).where(PhoneSpecification.phone_id == phone.id)
    ).all()
    assert len(first_rows) == 7
    first_ids = {row.id for row in first_rows}
    assert any(row.spec_name == "Type" and row.spec_value.startswith("Dynamic AMOLED") for row in first_rows)

    # Re-import the same page: no duplicate rows and values remain current.
    phone = upsert_scraped_phone(db_session, item)
    db_session.commit()
    second_rows = db_session.scalars(
        select(PhoneSpecification).where(PhoneSpecification.phone_id == phone.id)
    ).all()
    assert len(second_rows) == 7
    assert {row.id for row in second_rows} == first_ids
    assert phone.active_use_score_minutes == 687
    assert phone.endurance_rating_hours == 101


def test_scraped_price_observations_are_saved_and_reimported_idempotently(db_session):
    from app.models import PriceObservation

    raw_specs = {
        "Display": {"Size": "6.1 inches"},
        "Platform": {"Chipset": "Snapdragon 8 Gen 2"},
        "Main Camera": {"Triple": "50 MP + 10 MP + 12 MP"},
        "Battery": {"Type": "Li-Ion 3900 mAh"},
    }
    item = ScrapedPhone(
        name="Samsung Galaxy S23",
        source_url="https://www.gsmarena.com/samsung_galaxy_s23-12082.php",
        raw_specs=raw_specs,
        normalized={"display_size": "6.1 inches", "battery_capacity_mah": 3900},
        price_observations=[
            {"amount": 230.61, "currency": "USD", "source": "GSMArena affiliate offer | 128GB | amazon.com"},
            {"amount": 292.32, "currency": "EUR", "source": "GSMArena affiliate offer | 128GB | amazon.de"},
        ],
    )

    phone = upsert_scraped_phone(db_session, item)
    db_session.commit()
    first = db_session.scalars(
        select(PriceObservation).where(PriceObservation.phone_id == phone.id)
    ).all()
    assert len(first) == 2

    item.price_observations[0]["amount"] = 225.00
    phone = upsert_scraped_phone(db_session, item)
    db_session.commit()
    second = db_session.scalars(
        select(PriceObservation).where(PriceObservation.phone_id == phone.id)
    ).all()
    assert len(second) == 2
    usd = next(row for row in second if row.currency == "USD")
    assert usd.amount == 225.00
    assert "Current recorded price" in __import__("app.services.catalog", fromlist=["phone_to_document"]).phone_to_document(phone)
