from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Phone
from app.services.retriever import BM25Retriever
from app.services.catalog import phone_to_document


@dataclass(slots=True)
class SpecificationResult:
    intent: str
    phones: list[Phone]
    evidence: str
    sources: list[dict]


class SpecificationAgent:
    """Retrieves the relevant phone records and builds a source-grounded context."""

    def __init__(self, db: Session):
        self.db = db
        self.retriever = BM25Retriever()

    @staticmethod
    def _phone_aliases(phone: Phone) -> list[str]:
        name = phone.name.casefold()
        aliases = [name, name.replace("samsung ", ""), name.replace("samsung galaxy ", "galaxy ")]
        short = name.replace("samsung galaxy ", "").replace("samsung ", "")
        aliases.append(short)
        if "+" in short:
            aliases.extend([short.replace("+", " plus"), short.replace("+", "plus")])
        return sorted(set(alias.strip() for alias in aliases if alias.strip()), key=len, reverse=True)

    def _mentions(self, query: str, phones: list[Phone]) -> list[Phone]:
        lowered = query.casefold()
        found: list[tuple[int, int, Phone]] = []
        for phone in phones:
            for alias in self._phone_aliases(phone):
                pattern = r"(?<![a-z0-9])" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
                match = re.search(pattern, lowered)
                if match:
                    found.append((match.start(), match.end(), phone))
                    break
        found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        selected: list[Phone] = []
        occupied: list[tuple[int, int]] = []
        for start, end, phone in found:
            if any(start < existing_end and end > existing_start for existing_start, existing_end in occupied):
                continue
            if phone not in selected:
                selected.append(phone)
                occupied.append((start, end))
        return selected

    @staticmethod
    def _intent(query: str, mentions: list[Phone]) -> str:
        q = query.casefold()
        if any(term in q for term in ("best battery life", "longest battery life", "longest battery", "battery endurance", "longest endurance", "battery backup")) and not mentions:
            return "best_battery_life"
        if any(term in q for term in ("best battery capacity", "largest battery", "biggest battery", "largest capacity", "battery capacity", "most mah")) and not mentions:
            return "best_battery_capacity"
        if len(mentions) >= 2 or any(term in q for term in ("compare", "comparison", "versus", " vs ", "difference between")):
            return "comparison"
        if any(term in q for term in ("review", "pros and cons", "should i buy", "recommend")):
            return "review"
        if any(term in q for term in ("price", "cost", "how much", "retail", "market price")):
            return "price"
        if any(term in q for term in ("camera", "photo", "video", "selfie")):
            return "camera"
        if any(term in q for term in ("display", "screen", "resolution", "refresh rate")):
            return "display"
        if any(term in q for term in ("battery", "charging", "mAh")):
            return "battery"
        if any(term in q for term in ("processor", "chipset", "performance", "gaming", "cpu")):
            return "performance"
        if any(
            term in q
            for term in (
                "does it have", "does the", "support", "supports", "nfc", "bluetooth",
                "wi-fi", "wifi", "5g", "esim", "headphone jack", "3.5mm", "usb",
                "sd card", "water resistant", "water resistance", "wireless charging",
                "gorilla glass", "dex", "fingerprint", "gps",
            )
        ):
            return "feature"
        return "general"

    def run(self, query: str) -> SpecificationResult:
        phones = list(
            self.db.scalars(select(Phone).options(selectinload(Phone.specifications), selectinload(Phone.prices)).order_by(Phone.name.asc())).all()
        )
        mentions = self._mentions(query, phones)
        intent = self._intent(query, mentions)

        if intent in {"best_battery_life", "best_battery_capacity"}:
            # Keep the full candidate set so the answer can distinguish missing
            # measured test data from a genuine endurance ranking.
            selected = phones
        elif mentions:
            selected = mentions[:4]
        else:
            selected = [doc.phone for doc in self.retriever.retrieve(query, phones, top_k=3) if doc.score > 0]

        # Keep relevant phone order deterministic and prevent duplicate context.
        selected = list(dict.fromkeys(selected))
        evidence_parts: list[str] = []
        sources: list[dict] = []
        for phone in selected:
            phone_source_id = len(sources) + 1
            evidence_parts.append(f"[S{phone_source_id}]\n{phone_to_document(phone)}")
            sources.append(
                {
                    "title": phone.name,
                    "source": phone.source_name,
                    "url": phone.source_url,
                    "data_quality": phone.data_quality,
                }
            )
            if phone.test_source_url:
                test_source_id = len(sources) + 1
                test_section = {
                    section: values
                    for section, values in (phone.raw_specs or {}).items()
                    if "test" in section.casefold()
                }
                if test_section:
                    evidence_parts.append(f"[S{test_source_id}] GSMArena measured test results for {phone.name}: {test_section}")
                    sources.append(
                        {
                            "title": f"{phone.name} measured test results",
                            "source": "GSMArena measured test data",
                            "url": phone.test_source_url,
                            "data_quality": phone.data_quality,
                        }
                    )
            for price in phone.prices:
                if intent != "price" or not price.is_current:
                    continue
                source_url = price.source if price.source.startswith(("https://", "http://")) else None
                source_id = len(sources) + 1
                evidence_parts.append(
                    f"[S{source_id}] Current dated price observation for {phone.name}\n"
                    f"Amount: {price.amount} {price.currency}\n"
                    f"Provider/source: {price.source}\n"
                    f"Observed at: {price.observed_at}"
                )
                sources.append(
                    {
                        "title": f"{phone.name} price observation",
                        "source": price.source,
                        "url": source_url,
                        "data_quality": "price_observation",
                    }
                )
        return SpecificationResult(intent=intent, phones=selected, evidence="\n\n".join(evidence_parts), sources=sources)
