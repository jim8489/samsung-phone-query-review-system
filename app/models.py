from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Phone(Base):
    __tablename__ = "phones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    brand: Mapped[str] = mapped_column(String(60), default="Samsung", index=True)
    display_size: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_resolution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    camera_rear: Mapped[str | None] = mapped_column(Text, nullable=True)
    camera_front: Mapped[str | None] = mapped_column(String(180), nullable=True)
    battery_capacity_mah: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_use_score_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    endurance_rating_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery_details: Mapped[str | None] = mapped_column(String(240), nullable=True)
    chipset: Mapped[str | None] = mapped_column(String(300), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(180), nullable=True)
    ram: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage: Mapped[str | None] = mapped_column(String(180), nullable=True)
    refresh_rate: Mapped[str | None] = mapped_column(String(80), nullable=True)
    water_resistance: Mapped[str | None] = mapped_column(String(120), nullable=True)
    charging: Mapped[str | None] = mapped_column(String(180), nullable=True)
    price_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(12), nullable=True)
    source_name: Mapped[str] = mapped_column(String(80), default="demo_seed")
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_quality: Mapped[str] = mapped_column(String(24), default="demo_seed")
    raw_specs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    specifications: Mapped[list[PhoneSpecification]] = relationship(
        back_populates="phone", cascade="all, delete-orphan", order_by="PhoneSpecification.id"
    )
    prices: Mapped[list[PriceObservation]] = relationship(
        back_populates="phone", cascade="all, delete-orphan", order_by="PriceObservation.observed_at.desc()"
    )


class PhoneSpecification(Base):
    __tablename__ = "phone_specifications"
    __table_args__ = (
        UniqueConstraint("phone_id", "section", "spec_name", name="uq_phone_specification"),
        Index("ix_phone_specs_phone_section", "phone_id", "section"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_id: Mapped[int] = mapped_column(ForeignKey("phones.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(100))
    spec_name: Mapped[str] = mapped_column(String(140))
    spec_value: Mapped[str] = mapped_column(Text)

    phone: Mapped[Phone] = relationship(back_populates="specifications")


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (Index("ix_price_phone_date", "phone_id", "observed_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_id: Mapped[int] = mapped_column(ForeignKey("phones.id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(12), default="USD")
    source: Mapped[str] = mapped_column(String(180))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    phone: Mapped[Phone] = relationship(back_populates="prices")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
