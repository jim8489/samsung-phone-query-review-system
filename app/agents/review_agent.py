from __future__ import annotations

from app.models import Phone


class ReviewAgent:
    """Builds an evidence-based product review from one persisted phone record.

    The deterministic review is the safe fallback. When Ollama is configured,
    the API can ask the local model to turn the same evidence into richer prose.
    """

    def generate(self, phone: Phone, include_limitations: bool = True) -> dict:
        strengths: list[str] = []
        considerations: list[str] = []

        if phone.display_size or phone.refresh_rate:
            display = phone.display_size or "Display size not recorded"
            refresh = f", {phone.refresh_rate}" if phone.refresh_rate else ""
            panel = phone.raw_specs.get("Display", {}).get("Type") if phone.raw_specs else None
            panel_detail = f"; {panel}" if panel else ""
            strengths.append(f"Display specification: {display}{refresh}{panel_detail}.")
        if phone.chipset:
            strengths.append(f"Recorded platform: {phone.chipset}.")
        if phone.camera_rear:
            strengths.append(f"Rear-camera configuration: {phone.camera_rear}.")
        if phone.camera_front:
            strengths.append(f"Front-camera specification: {phone.camera_front}.")
        if phone.water_resistance:
            strengths.append(f"Listed ingress-protection rating: {phone.water_resistance}.")
        if phone.battery_capacity_mah:
            strengths.append(f"Battery capacity: {phone.battery_capacity_mah:,} mAh.")

        if not phone.price_amount and not any(price.is_current for price in phone.prices):
            considerations.append("No dated, verified retailer price is stored, so value-for-money cannot be assessed.")
        if phone.chipset and ("region-dependent" in phone.chipset.casefold() or "/" in phone.chipset):
            considerations.append("The chipset may vary by market; confirm the exact regional model/SKU before comparing performance.")
        if phone.battery_capacity_mah and phone.active_use_score_minutes is None and phone.endurance_rating_hours is None:
            considerations.append("Battery capacity is recorded, but no measured endurance test is stored. Capacity alone does not establish battery life.")
        if not phone.camera_rear:
            considerations.append("Rear-camera details are incomplete in the current record.")
        if phone.data_quality == "demo_seed":
            considerations.append("This is abbreviated starter/demo data. A live GSMArena scrape is required for a complete source-backed assessment.")
        if phone.data_quality == "scraped" and not phone.source_url:
            considerations.append("The record is marked as scraped but has no stored source URL; verify provenance before publication.")

        review_lines = [
            f"## {phone.name}: specification-based review",
            "",
            "### Hardware overview",
            f"- **Display:** {phone.display_size or 'Not recorded'}; {phone.display_resolution or 'resolution not recorded'}; {phone.refresh_rate or 'refresh rate not recorded'}. ",
            f"- **Platform:** {phone.chipset or 'Not recorded'}.",
            f"- **Memory:** {phone.ram or 'RAM not recorded'} RAM; {phone.storage or 'storage not recorded'} storage.",
            f"- **Rear camera:** {phone.camera_rear or 'Not recorded'}.",
            f"- **Front camera:** {phone.camera_front or 'Not recorded'}.",
            f"- **Battery:** {f'{phone.battery_capacity_mah:,} mAh' if phone.battery_capacity_mah else 'Capacity not recorded'}.",
        ]
        if phone.active_use_score_minutes is not None:
            review_lines.append(f"- **Measured active-use score:** {phone.active_use_score_minutes // 60}:{phone.active_use_score_minutes % 60:02d}h.")
        elif phone.endurance_rating_hours is not None:
            review_lines.append(f"- **Measured endurance rating:** {phone.endurance_rating_hours}h.")
        review_lines.extend([
            f"- **Charging:** {phone.charging or 'Not recorded'}.",
            f"- **Water resistance:** {phone.water_resistance or 'Not recorded'}.",
            "",
            "### Assessment",
            "The stored hardware record describes the device's components, but it does not by itself establish camera quality, sustained performance, software reliability or day-to-day battery endurance. Those require independent tests. The review therefore distinguishes listed specifications from real-world outcomes and does not assign an unsupported overall score.",
        ])
        if phone.data_quality == "demo_seed":
            review_lines.append("\n**Data-quality note:** this assessment is based on the project's starter record, not a fresh GSMArena scrape.")
        if phone.source_url:
            review_lines.append(f"\n**Specification source:** [{phone.source_name}]({phone.source_url}).")
        if phone.test_source_url:
            review_lines.append(f"**Measured test results:** [GSMArena measured test data]({phone.test_source_url}).")

        return {
            "review": "\n".join(review_lines),
            "strengths": strengths,
            "considerations": considerations if include_limitations else [],
        }
