from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SpecificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    section: str
    spec_name: str
    spec_value: str


class PhoneListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    slug: str
    name: str
    display_size: str | None = None
    camera_rear: str | None = None
    battery_capacity_mah: int | None = None
    active_use_score_minutes: int | None = None
    endurance_rating_hours: int | None = None
    chipset: str | None = None
    ram: str | None = None
    storage: str | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    data_quality: str


class PhoneDetail(PhoneListItem):
    display_resolution: str | None = None
    camera_front: str | None = None
    battery_details: str | None = None
    operating_system: str | None = None
    refresh_rate: str | None = None
    water_resistance: str | None = None
    charging: str | None = None
    source_name: str
    source_url: str | None = None
    test_source_url: str | None = None
    scraped_at: datetime | None = None
    raw_specs: dict[str, Any] = Field(default_factory=dict)
    specifications: list[SpecificationOut] = Field(default_factory=list)
    price_observations: list[PriceObservationOut] = Field(default_factory=list, validation_alias="prices")


class PriceObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    amount: float
    currency: str
    source: str
    observed_at: datetime
    is_current: bool


class PriceCreate(BaseModel):
    amount: float = Field(gt=0, le=100_000_000)
    currency: str = Field(min_length=3, max_length=12, description="Currency code, e.g. BDT or USD")
    source: str = Field(min_length=2, max_length=180)
    observed_at: datetime | None = None


class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    session_id: str | None = None


class SourceOut(BaseModel):
    title: str
    source: str
    url: str | None = None
    data_quality: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    mode: Literal["rag_fallback", "ollama_rag"]
    sources: list[SourceOut] = Field(default_factory=list)
    relevant_phones: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    include_limitations: bool = True


class ReviewResponse(BaseModel):
    phone: str
    review: str
    generation_mode: Literal["rule_based", "ollama_rag", "langchain_multi_agent"] = "rule_based"
    strengths: list[str]
    considerations: list[str]
    source: SourceOut


class ScrapeRequest(BaseModel):
    models: list[str] = Field(default_factory=list, max_length=15)
    delay_seconds: float | None = Field(default=None, ge=2.0, le=30)


class ScrapeItemResult(BaseModel):
    model: str
    status: Literal["scraped", "skipped", "failed"]
    message: str
    source_url: str | None = None
    test_source_url: str | None = None


class ScrapeResponse(BaseModel):
    attempted: int
    scraped: int
    failed: int
    results: list[ScrapeItemResult]


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    llm_provider: str
