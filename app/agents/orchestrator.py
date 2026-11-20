from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.agents.specification_agent import SpecificationAgent, SpecificationResult
from app.agents.review_agent import ReviewAgent
from app.models import Phone
from app.services.llm import OllamaClient


class AgentOrchestrator:
    """Coordinates the spec-retrieval agent and grounded answer generation."""

    def __init__(self, db: Session):
        self.db = db
        self.spec_agent = SpecificationAgent(db)
        self.llm = OllamaClient()

    @staticmethod
    def _phone_summary(phone: Phone) -> str:
        return (
            f"**{phone.name}**\n"
            f"- Display: {phone.display_size or 'Not listed'} ({phone.display_resolution or 'resolution not listed'}); {phone.refresh_rate or 'refresh rate not listed'}\n"
            f"- Rear camera: {phone.camera_rear or 'Not listed'}; front camera: {phone.camera_front or 'Not listed'}\n"
            f"- Battery: {f'{phone.battery_capacity_mah:,} mAh' if phone.battery_capacity_mah else 'Not listed'}\n"
            f"- Chipset: {phone.chipset or 'Not listed'}\n"
            f"- RAM / storage: {phone.ram or 'Not listed'} / {phone.storage or 'Not listed'}\n"
            f"- OS: {phone.operating_system or 'Not listed'}"
        )

    @staticmethod
    def _comparison(result: SpecificationResult) -> str:
        if len(result.phones) < 2:
            return "I could not identify two specific catalogue models to compare. Please include both model names, for example: Galaxy S23 vs Galaxy S22."
        sections = [f"## Specification comparison\n\n{AgentOrchestrator._phone_summary(phone)}" for phone in result.phones]
        sections.append(
            "\n**How to interpret this comparison:** these are stored specification records, not independent benchmark or camera-test results. "
            "For regional variants, confirm the exact model number before purchase."
        )
        return "\n\n---\n\n".join(sections)

    @staticmethod
    def _best_battery(result: SpecificationResult) -> str:
        if not result.phones:
            return "The catalogue does not contain battery records yet. Run the GSMArena scraper or add phone data first."

        active_scores = [p for p in result.phones if p.active_use_score_minutes is not None]
        if active_scores:
            ranking = sorted(active_scores, key=lambda p: p.active_use_score_minutes or 0, reverse=True)
            lines = ["## GSMArena measured active-use results\n"]
            lines.extend(
                f"- **{p.name}** — {p.active_use_score_minutes // 60}:{p.active_use_score_minutes % 60:02d}h"
                for p in ranking
            )
            if len(active_scores) < len(result.phones):
                lines.append("\nOnly models with a recorded active-use score are ranked.")
            lines.append("\nThese are published test results, not a guarantee of identical real-world endurance.")
            return "\n".join(lines)

        endurance = [p for p in result.phones if p.endurance_rating_hours is not None]
        if endurance:
            ranking = sorted(endurance, key=lambda p: p.endurance_rating_hours or 0, reverse=True)
            lines = ["## GSMArena endurance ratings\n"]
            lines.extend(f"- **{p.name}** — {p.endurance_rating_hours}h" for p in ranking)
            if len(endurance) < len(result.phones):
                lines.append("\nOnly models with a recorded endurance rating are ranked.")
            lines.append("\nEndurance ratings are published test metrics; usage conditions still affect actual battery life.")
            return "\n".join(lines)

        capacity = [p for p in result.phones if p.battery_capacity_mah is not None]
        if not capacity:
            return "The catalogue has no measured battery tests or battery-capacity records yet."
        ranking = sorted(capacity, key=lambda p: p.battery_capacity_mah or 0, reverse=True)
        lines = [
            "## Battery-life comparison is not available\n",
            "The current catalogue has no GSMArena active-use scores or endurance ratings, so it cannot establish which phone lasts longest.",
            "\nFor reference, the largest listed battery capacities are:",
        ]
        lines.extend(f"- **{p.name}** — {p.battery_capacity_mah:,} mAh" for p in ranking[:5])
        lines.append("\nBattery capacity (mAh) is not the same as measured battery life.")
        return "\n".join(lines)

    @staticmethod
    def _fallback_answer(query: str, result: SpecificationResult) -> str:
        if result.intent in {"best_battery_life", "best_battery_capacity"}:
            if result.intent == "best_battery_capacity":
                phones = sorted(
                    (p for p in result.phones if p.battery_capacity_mah is not None),
                    key=lambda p: p.battery_capacity_mah or 0,
                    reverse=True,
                )
                if not phones:
                    return "The catalogue has no battery-capacity records yet."
                return "## Largest listed battery capacities\n\n" + "\n".join(
                    f"- **{p.name}** — {p.battery_capacity_mah:,} mAh" for p in phones[:5]
                ) + "\n\nCapacity is not a measurement of battery life."
            return AgentOrchestrator._best_battery(result)
        if result.intent == "comparison":
            return AgentOrchestrator._comparison(result)
        if result.intent == "review":
            if not result.phones:
                return "Please include a Samsung model name so the review agent can retrieve its specifications."
            generated_review = ReviewAgent().generate(result.phones[0], include_limitations=True)
            strengths = "\n".join(f"- {item}" for item in generated_review["strengths"]) or "- No verified strengths recorded."
            considerations = "\n".join(f"- {item}" for item in generated_review["considerations"]) or "- No additional limitations recorded."
            review_text = generated_review["review"]
            return f"## {result.phones[0].name} — specification-based review\n\n{review_text}\n\n**Strengths**\n{strengths}\n\n**Considerations**\n{considerations}"
        if not result.phones:
            return (
                "I could not find a sufficiently relevant Samsung phone record in the local catalogue. "
                "Try a specific model name such as Galaxy S23, or run the GSMArena scraper to populate the catalogue."
            )

        phone = result.phones[0]
        q = query.casefold()
        if result.intent == "price":
            current_prices = [price for price in phone.prices if price.is_current]
            if current_prices:
                lines = [f"Current recorded price observations for {phone.name}:"]
                for price in current_prices:
                    lines.append(f"- {price.currency} {price.amount:,.2f} — {price.source} (observed {price.observed_at})")
                lines.append("\nThese are source-attributed observations, not guaranteed live offers. Confirm availability and the exact storage variant with the seller.")
                return "\n".join(lines)
            listed_price = None
            for section_name, entries in (phone.raw_specs or {}).items():
                if section_name.casefold() in {"misc", "launch"}:
                    listed_price = next(
                        (value for key, value in entries.items() if "price" in key.casefold()),
                        listed_price,
                    )
            if listed_price:
                return (
                    f"GSMArena's stored specification page lists this price information for {phone.name}: **{listed_price}**. "
                    "Treat it as a source-page estimate, not a verified current local offer; price, currency, region and stock can change. "
                    "No dated retailer price observation is currently stored."
                )
            return (
                f"I do not have a verified current price for the {phone.name} in the database. "
                "Prices vary by country, storage configuration, retailer and date. Add a dated price observation or check a local retailer for a current quote."
            )
        if result.intent == "camera":
            return (
                f"## {phone.name} camera\n\n"
                f"- Rear: {phone.camera_rear or 'Not present in the stored record'}\n"
                f"- Front: {phone.camera_front or 'Not present in the stored record'}\n"
                f"- Video: {phone.raw_specs.get('Main Camera', {}).get('Video', 'Not present in the stored record')}\n\n"
                "Megapixel counts describe sensor resolution, not overall image quality. Lens quality, processing and testing also matter."
            )
        if result.intent == "display":
            return (
                f"The {phone.name} has a **{phone.display_size or 'display size not listed'}** display with "
                f"{phone.display_resolution or 'resolution not listed'} resolution and {phone.refresh_rate or 'refresh rate not listed'}. "
                f"Panel: {phone.raw_specs.get('Display', {}).get('Type', 'not listed')}."
            )
        if result.intent == "battery":
            return (
                f"The {phone.name} is listed with a **{f'{phone.battery_capacity_mah:,} mAh' if phone.battery_capacity_mah else 'battery capacity not recorded'}** battery. "
                f"Charging information: {phone.charging or 'not recorded'}. Capacity alone does not establish real-world battery life."
            )
        if result.intent == "performance":
            return (
                f"The {phone.name} is listed with **{phone.chipset or 'chipset not recorded'}**. "
                f"Memory configuration: {phone.ram or 'RAM not recorded'} RAM and {phone.storage or 'storage not recorded'} storage. "
                "The catalogue does not contain standardized benchmark results, so I cannot claim a measured performance lead."
            )
        if result.intent == "feature":
            stop_words = {"does", "do", "the", "a", "an", "it", "its", "is", "are", "have", "has", "this", "that", "phone", "galaxy", "samsung", "support", "supports", "with", "for", "of", "and", "or", "what", "which", "tell", "me"}
            query_terms = {token for token in re.findall(r"[a-z0-9]+", q) if token not in stop_words and len(token) > 1}
            matches = []
            for section, entries in (phone.raw_specs or {}).items():
                for label, value in entries.items():
                    searchable = f"{section} {label} {value}".casefold()
                    hits = sum(1 for token in query_terms if token in searchable)
                    if hits:
                        matches.append((hits, section, label, value))
            matches.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
            if matches:
                lines = [f"## Relevant stored specifications for {phone.name}"]
                seen = set()
                for _, section, label, value in matches[:8]:
                    key = (section, label, value)
                    if key in seen:
                        continue
                    seen.add(key)
                    lines.append(f"- **{section} — {label}:** {value}")
                lines.append("\nThese details come from the stored specification record. If a feature is not listed, that does not prove the phone lacks it.")
                return "\n".join(lines)
            return (
                f"I could not find a matching feature field in the stored record for {phone.name}. "
                "That means the feature is not recorded here; it does not prove the phone does not support it."
            )
        return "Here are the matching specifications from the catalogue:\n\n" + AgentOrchestrator._phone_summary(phone)

    @staticmethod
    def _battery_evidence(result: SpecificationResult) -> str:
        """Keep comparison context compact so every candidate reaches the LLM."""
        parts = []
        for phone in result.phones:
            source_index = next(
                (index for index, source in enumerate(result.sources, start=1) if source.get("title") == phone.name),
                None,
            )
            if source_index is None:
                continue
            active_use = (
                f"{phone.active_use_score_minutes // 60}:{phone.active_use_score_minutes % 60:02d}h"
                if phone.active_use_score_minutes is not None else "not recorded"
            )
            endurance = f"{phone.endurance_rating_hours}h" if phone.endurance_rating_hours is not None else "not recorded"
            parts.append(
                f"[S{source_index}] {phone.name}\n"
                f"Battery capacity: {phone.battery_capacity_mah or 'not recorded'} mAh\n"
                f"GSMArena active-use score: {active_use}\n"
                f"GSMArena endurance rating: {endurance}\n"
                f"Source: {phone.source_name}; URL: {phone.source_url or 'not recorded'}; "
                f"data quality: {phone.data_quality}"
            )
            if phone.test_source_url:
                test_source_index = source_index + 1
                test_rows = {
                    section: values
                    for section, values in (phone.raw_specs or {}).items()
                    if "test" in section.casefold()
                }
                if test_rows:
                    parts.append(
                        f"[S{test_source_index}] GSMArena test-result rows for {phone.name}: {test_rows}\n"
                        f"Test source URL: {phone.test_source_url}"
                    )
        return "\n\n".join(parts)

    async def answer(self, query: str, history: list[dict[str, str]] | None = None) -> tuple[str, str, SpecificationResult]:
        result = self.spec_agent.run(query)
        if result.intent in {"best_battery_life", "best_battery_capacity"}:
            result.evidence = self._battery_evidence(result)
        if result.intent == "review" and result.phones:
            review = ReviewAgent().generate(result.phones[0], include_limitations=True)
            result.evidence += "\n\nReview agent assessment:\n" + review["review"] + "\nStrengths: " + "; ".join(review["strengths"]) + "\nConsiderations: " + "; ".join(review["considerations"])
        generated = await self.llm.answer(query=query, evidence=result.evidence, history=history)
        if generated:
            answer = generated
            mode = "ollama_rag"
        else:
            answer = self._fallback_answer(query, result)
            mode = "rag_fallback"
        return answer, mode, result
