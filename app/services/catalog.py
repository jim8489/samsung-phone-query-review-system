from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Phone, PhoneSpecification, PriceObservation
from app.scraper.gsmarena import ScrapedPhone
from app.data.seed import slugify


def get_phone(db: Session, slug: str) -> Phone | None:
    return db.scalar(
        select(Phone).options(selectinload(Phone.specifications), selectinload(Phone.prices)).where(Phone.slug == slug)
    )


def list_phones(db: Session, search: str | None = None, limit: int = 50, offset: int = 0) -> list[Phone]:
    statement = select(Phone).order_by(Phone.name.asc()).limit(limit).offset(offset)
    if search:
        needle = f"%{search.strip()}%"
        statement = statement.where(Phone.name.ilike(needle))
    return list(db.scalars(statement).all())


def upsert_scraped_phone(db: Session, item: ScrapedPhone) -> Phone:
    """Insert or refresh a scraped phone and its specification rows.

    Specification rows have a unique constraint on (phone_id, section,
    spec_name). Replacing a relationship collection with ``clear()`` followed
    by appends is not safe on every SQLAlchemy/database combination: INSERTs
    can be emitted before orphan DELETEs, briefly violating that constraint.
    Updating existing rows in place avoids the ordering issue and makes repeat
    imports idempotent.
    """
    slug = slugify(item.name)
    phone = db.scalar(select(Phone).where(Phone.slug == slug))
    if phone is None:
        phone = Phone(slug=slug, name=item.name, brand="Samsung")
        db.add(phone)
        db.flush()

    normalized = dict(item.normalized)
    for field, value in normalized.items():
        setattr(phone, field, value)
    phone.name = item.name
    phone.source_name = "GSMArena"
    phone.source_url = item.source_url
    phone.test_source_url = item.test_source_url
    phone.data_quality = "scraped"
    phone.raw_specs = item.raw_specs
    phone.scraped_at = datetime.now(timezone.utc)

    existing_rows = db.scalars(
        select(PhoneSpecification).where(PhoneSpecification.phone_id == phone.id)
    ).all()
    existing_by_key = {
        (row.section, row.spec_name): row
        for row in existing_rows
    }
    incoming_keys: set[tuple[str, str]] = set()

    for section, entries in item.raw_specs.items():
        for spec_name, spec_value in entries.items():
            key = (section, spec_name)
            incoming_keys.add(key)
            existing = existing_by_key.get(key)
            if existing is not None:
                existing.spec_value = str(spec_value)
            else:
                db.add(
                    PhoneSpecification(
                        phone_id=phone.id,
                        section=section,
                        spec_name=spec_name,
                        spec_value=str(spec_value),
                    )
                )

    # Remove obsolete rows, but leave matching rows in place and update them.
    for key, existing in existing_by_key.items():
        if key not in incoming_keys:
            db.delete(existing)

    # Price offers from the GSMArena page are stored as dated, source-attributed
    # observations. Update an identical variant/currency/merchant source in place
    # so repeated scraping does not create duplicate rows.
    observed_at = datetime.now(timezone.utc)
    incoming_price_keys = {
        (str(quote.get("currency", "")).upper(), str(quote.get("source", "GSMArena listing"))[:180])
        for quote in (getattr(item, "price_observations", []) or [])
        if quote.get("currency") and float(quote.get("amount", 0)) > 0
    }
    previous_gsm_prices = db.scalars(
        select(PriceObservation).where(
            PriceObservation.phone_id == phone.id,
            PriceObservation.source.like("GSMArena affiliate offer%"),
            PriceObservation.is_current.is_(True),
        )
    ).all()
    for previous in previous_gsm_prices:
        if (previous.currency, previous.source) not in incoming_price_keys:
            previous.is_current = False

    for quote in getattr(item, "price_observations", []) or []:
        currency = str(quote.get("currency", "")).upper()
        source = str(quote.get("source", "GSMArena listing"))[:180]
        amount = float(quote.get("amount", 0))
        if not currency or amount <= 0:
            continue
        existing_price = db.scalar(
            select(PriceObservation).where(
                PriceObservation.phone_id == phone.id,
                PriceObservation.currency == currency,
                PriceObservation.source == source,
            )
        )
        if existing_price is not None:
            existing_price.amount = amount
            existing_price.observed_at = observed_at
            existing_price.is_current = True
        else:
            db.add(
                PriceObservation(
                    phone_id=phone.id,
                    amount=amount,
                    currency=currency,
                    source=source,
                    observed_at=observed_at,
                    is_current=True,
                )
            )

    db.flush()
    # The relationship may already have been loaded by a caller (for example,
    # after seeding demo records). Expire it so subsequent access reflects the
    # rows just inserted/updated/deleted above.
    db.expire(phone, ["specifications"])
    return phone


def upsert_many_scraped_phones(db: Session, items: list[ScrapedPhone]) -> list[Phone]:
    phones = [upsert_scraped_phone(db, item) for item in items]
    db.commit()
    return phones


def phone_to_document(phone: Phone) -> str:
    fields = [
        f"Phone: {phone.name}",
        f"Display: {phone.display_size or 'not listed'}; {phone.display_resolution or 'resolution not listed'}; refresh rate {phone.refresh_rate or 'not listed'}",
        f"Rear camera: {phone.camera_rear or 'not listed'}",
        f"Front camera: {phone.camera_front or 'not listed'}",
        f"Battery capacity: {phone.battery_capacity_mah or 'not listed'} mAh; {phone.battery_details or ''}",
        f"GSMArena active use score: {f'{phone.active_use_score_minutes // 60}:{phone.active_use_score_minutes % 60:02d}h' if phone.active_use_score_minutes is not None else 'not recorded'}",
        f"GSMArena endurance rating: {f'{phone.endurance_rating_hours}h' if phone.endurance_rating_hours is not None else 'not recorded'}",
        f"Chipset: {phone.chipset or 'not listed'}",
        f"Operating system: {phone.operating_system or 'not listed'}",
        f"Memory: RAM {phone.ram or 'not listed'}; storage {phone.storage or 'not listed'}",
        f"Charging: {phone.charging or 'not listed'}; water resistance: {phone.water_resistance or 'not listed'}",
        f"Source: {phone.source_name}; URL: {phone.source_url or 'not recorded'}; data quality: {phone.data_quality}",
        f"GSMArena test-results source: {phone.test_source_url or 'not recorded'}",
    ]
    for spec in phone.specifications:
        fields.append(f"{spec.section} — {spec.spec_name}: {spec.spec_value}")
    for price in phone.prices:
        if price.is_current:
            fields.append(
                f"Current recorded price: {price.amount:,.2f} {price.currency}; "
                f"source: {price.source}; observed at: {price.observed_at}"
            )
    return "\n".join(fields)
