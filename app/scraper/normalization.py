from __future__ import annotations

import re
from typing import Any


def _section(raw: dict[str, dict[str, str]], *names: str) -> dict[str, str]:
    for name in names:
        for section_name, fields in raw.items():
            if section_name.casefold() == name.casefold():
                return fields
    return {}


def _find_value(raw: dict[str, dict[str, str]], section_names: tuple[str, ...], field_names: tuple[str, ...]) -> str | None:
    section = _section(raw, *section_names)
    for expected in field_names:
        for actual, value in section.items():
            if actual.casefold().strip() == expected.casefold():
                return value.strip() or None
    return None


def _first_camera_value(raw: dict[str, dict[str, str]], section_name: str = "Main Camera") -> str | None:
    section = _section(raw, section_name)
    preferred = ("Quad", "Penta", "Triple", "Dual", "Single", "Camera")
    pieces: list[str] = []
    for key in preferred:
        value = next((v for k, v in section.items() if k.casefold() == key.casefold()), None)
        if value and value not in pieces:
            pieces.append(value)
    if not pieces:
        pieces = [v for k, v in section.items() if k.casefold() not in {"features", "video"}]
    return " | ".join(pieces) if pieces else None


def _extract_capacity(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\b(\d{3,5})\s*mAh\b", value, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_ram_storage(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    ram_values = re.findall(r"\b(\d{1,2})\s*GB\s*RAM\b", value, flags=re.IGNORECASE)
    storage_values = re.findall(r"\b(\d{2,4})\s*GB\b", value, flags=re.IGNORECASE)
    ram = " / ".join(dict.fromkeys(f"{v} GB" for v in ram_values)) or None
    storage = " / ".join(dict.fromkeys(f"{v} GB" for v in storage_values if v not in ram_values)) or None
    return ram, storage



def _extract_battery_test_metrics(raw: dict[str, dict[str, str]]) -> tuple[int | None, int | None]:
    """Extract measured GSMArena battery results without confusing them with mAh capacity.

    GSMArena has used labels such as ``Active use score 11:27h`` and
    ``Endurance rating 101h`` in its test-result section. The parser accepts
    the value whether it appears in the row label or row value.
    """
    active_use_minutes: int | None = None
    endurance_hours: int | None = None
    for section_name, entries in raw.items():
        if "test" not in section_name.casefold():
            continue
        for label, value in entries.items():
            combined = f"{label} {value}"
            active_match = re.search(
                r"active\s+use\s+score\s*[:：]?\s*(\d{1,2}):(\d{2})\s*h?",
                combined,
                flags=re.IGNORECASE,
            )
            if active_match:
                hours, minutes = (int(active_match.group(1)), int(active_match.group(2)))
                if minutes < 60:
                    active_use_minutes = hours * 60 + minutes
            endurance_match = re.search(
                r"endurance\s+rating\s*[:：]?\s*(\d{2,3})\s*h",
                combined,
                flags=re.IGNORECASE,
            )
            if endurance_match:
                endurance_hours = int(endurance_match.group(1))
    return active_use_minutes, endurance_hours


def normalize_specs(raw: dict[str, dict[str, str]]) -> dict[str, Any]:
    display_size = _find_value(raw, ("Display",), ("Size",))
    display_resolution = _find_value(raw, ("Display",), ("Resolution",))
    chipset = _find_value(raw, ("Platform",), ("Chipset",))
    operating_system = _find_value(raw, ("Platform",), ("OS",))
    memory_internal = _find_value(raw, ("Memory",), ("Internal",))
    ram_explicit = _find_value(raw, ("Memory",), ("RAM",))
    ram_from_internal, storage_from_internal = _extract_ram_storage(memory_internal)
    battery_details = _find_value(raw, ("Battery",), ("Type",))
    battery_capacity = _extract_capacity(battery_details)
    active_use_score_minutes, endurance_rating_hours = _extract_battery_test_metrics(raw)
    charging = _find_value(raw, ("Battery",), ("Charging",))
    if not charging:
        charging = _find_value(raw, ("Battery",), ("Charging 2.0", "Charging 3.0"))
    camera_front = _first_camera_value(raw, "Selfie camera") or _first_camera_value(raw, "Selfie Camera")
    display_type = _find_value(raw, ("Display",), ("Type",))
    refresh_rate = None
    if display_type:
        match = re.search(r"\b(\d{2,3})\s*Hz\b", display_type, flags=re.IGNORECASE)
        if match:
            refresh_rate = f"{match.group(1)} Hz"
    if not refresh_rate:
        for key, value in _section(raw, "Display").items():
            if "refresh" in key.casefold() or re.search(r"\b\d{2,3}\s*Hz\b", value, re.IGNORECASE):
                match = re.search(r"\b\d{2,3}\s*Hz\b", value, re.IGNORECASE)
                if match:
                    refresh_rate = match.group(0)
                    break
    water_resistance = None
    for section_fields in raw.values():
        for value in section_fields.values():
            match = re.search(r"\bIP\s*\d{2}\b[^,;]*", value, re.IGNORECASE)
            if match:
                water_resistance = match.group(0).strip()
                break
        if water_resistance:
            break
    return {
        "display_size": display_size,
        "display_resolution": display_resolution,
        "camera_rear": _first_camera_value(raw),
        "camera_front": camera_front,
        "battery_capacity_mah": battery_capacity,
        "active_use_score_minutes": active_use_score_minutes,
        "endurance_rating_hours": endurance_rating_hours,
        "battery_details": battery_details,
        "chipset": chipset,
        "operating_system": operating_system,
        "ram": ram_explicit or ram_from_internal,
        "storage": storage_from_internal,
        "refresh_rate": refresh_rate,
        "water_resistance": water_resistance,
        "charging": charging,
    }
