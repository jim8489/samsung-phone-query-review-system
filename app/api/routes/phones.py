from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Phone, PriceObservation
from app.schemas import PhoneDetail, PhoneListItem, PriceCreate, PriceObservationOut

router = APIRouter(prefix="/phones", tags=["Phones"])


@router.get("", response_model=list[PhoneListItem], summary="List Samsung phones")
def get_phones(
    search: str | None = Query(default=None, description="Filter by model name"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    statement = select(Phone).order_by(Phone.name.asc()).limit(limit).offset(offset)
    if search:
        statement = statement.where(Phone.name.ilike(f"%{search.strip()}%"))
    return list(db.scalars(statement).all())


@router.get("/compare", summary="Compare two or more Samsung models")
def compare_phones(
    slugs: str = Query(..., description="Comma-separated phone slugs, e.g. samsung-galaxy-s23,samsung-galaxy-s22"),
    db: Session = Depends(get_db),
):
    requested = [slug.strip() for slug in slugs.split(",") if slug.strip()]
    if len(requested) < 2 or len(requested) > 4:
        raise HTTPException(status_code=422, detail="Provide between 2 and 4 phone slugs.")
    phones = list(
        db.scalars(
            select(Phone).options(selectinload(Phone.specifications)).where(Phone.slug.in_(requested))
        ).all()
    )
    by_slug = {phone.slug: phone for phone in phones}
    missing = [slug for slug in requested if slug not in by_slug]
    if missing:
        raise HTTPException(status_code=404, detail={"message": "Phone model not found", "slugs": missing})
    ordered = [by_slug[slug] for slug in requested]
    fields = (
        "display_size", "display_resolution", "camera_rear", "camera_front", "battery_capacity_mah",
        "active_use_score_minutes", "endurance_rating_hours", "chipset", "ram", "storage",
        "refresh_rate", "water_resistance", "charging", "operating_system", "price_amount", "price_currency",
    )
    return {
        "models": [phone.name for phone in ordered],
        "comparison": {field: {phone.name: getattr(phone, field) for phone in ordered} for field in fields},
        "data_quality": {phone.name: phone.data_quality for phone in ordered},
    }


@router.get("/best-battery", summary="Rank models by measured endurance when available")
def best_battery(db: Session = Depends(get_db)):
    phones = list(db.scalars(select(Phone)).all())
    active = [phone for phone in phones if phone.active_use_score_minutes is not None]
    if active:
        ranked = sorted(active, key=lambda phone: phone.active_use_score_minutes or 0, reverse=True)
        return {
            "metric": "GSMArena active use score",
            "warning": "Published test results are useful comparisons, not a guarantee of identical real-world endurance.",
            "results": [{"name": p.name, "slug": p.slug, "active_use_score_minutes": p.active_use_score_minutes} for p in ranked],
        }
    endurance = [phone for phone in phones if phone.endurance_rating_hours is not None]
    if endurance:
        ranked = sorted(endurance, key=lambda phone: phone.endurance_rating_hours or 0, reverse=True)
        return {
            "metric": "GSMArena endurance rating (hours)",
            "warning": "Only models with a recorded GSMArena endurance rating are included.",
            "results": [{"name": p.name, "slug": p.slug, "endurance_rating_hours": p.endurance_rating_hours} for p in ranked],
        }
    capacity = sorted(
        (phone for phone in phones if phone.battery_capacity_mah is not None),
        key=lambda phone: phone.battery_capacity_mah or 0,
        reverse=True,
    )
    return {
        "metric": "battery capacity (mAh) — proxy only",
        "warning": "No measured battery test values are stored. Capacity cannot establish which phone has the longest battery life.",
        "results": [{"name": p.name, "slug": p.slug, "battery_capacity_mah": p.battery_capacity_mah} for p in capacity],
    }


@router.get("/{slug}", response_model=PhoneDetail, summary="Get a phone and its specifications")
def get_phone(slug: str, db: Session = Depends(get_db)):
    phone = db.scalar(
        select(Phone).options(selectinload(Phone.specifications), selectinload(Phone.prices)).where(Phone.slug == slug)
    )
    if phone is None:
        raise HTTPException(status_code=404, detail=f"Phone '{slug}' was not found.")
    return phone


@router.get("/{slug}/prices", response_model=list[PriceObservationOut], summary="Get dated price observations")
def get_phone_prices(slug: str, db: Session = Depends(get_db)):
    phone = db.scalar(select(Phone).where(Phone.slug == slug))
    if phone is None:
        raise HTTPException(status_code=404, detail=f"Phone '{slug}' was not found.")
    statement = select(PriceObservation).where(PriceObservation.phone_id == phone.id).order_by(PriceObservation.observed_at.desc())
    return list(db.scalars(statement).all())


@router.post("/{slug}/prices", response_model=PriceObservationOut, status_code=201, summary="Add a dated price observation")
def add_phone_price(slug: str, payload: PriceCreate, db: Session = Depends(get_db)):
    phone = db.scalar(select(Phone).where(Phone.slug == slug))
    if phone is None:
        raise HTTPException(status_code=404, detail=f"Phone '{slug}' was not found.")
    currency = payload.currency.strip().upper()
    if not currency.isalpha():
        raise HTTPException(status_code=422, detail="Currency must be a code containing letters only, such as BDT or USD.")
    observed_at = payload.observed_at or datetime.now(timezone.utc)
    db.query(PriceObservation).filter(
        PriceObservation.phone_id == phone.id,
        PriceObservation.currency == currency,
        PriceObservation.is_current.is_(True),
    ).update({"is_current": False}, synchronize_session=False)
    observation = PriceObservation(
        phone_id=phone.id,
        amount=payload.amount,
        currency=currency,
        source=payload.source.strip(),
        observed_at=observed_at,
        is_current=True,
    )
    db.add(observation)
    phone.price_amount = payload.amount
    phone.price_currency = currency
    db.commit()
    db.refresh(observation)
    return observation
