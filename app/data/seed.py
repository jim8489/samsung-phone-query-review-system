"""Small demo catalogue so the application is useful before a live scrape.

Values are intentionally labelled demo_seed. A fresh GSMArena scrape replaces
these abbreviated starter records with the values parsed from the source pages.
"""
from __future__ import annotations

import re
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Phone, PhoneSpecification


DEMO_PHONES: list[dict] = [
    {
        "name": "Samsung Galaxy S21",
        "display_size": "6.2 inches",
        "display_resolution": "1080 x 2400 pixels",
        "camera_rear": "12 MP wide + 64 MP telephoto + 12 MP ultrawide",
        "camera_front": "10 MP",
        "battery_capacity_mah": 4000,
        "chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)",
        "operating_system": "Android 11 (launch version)", "ram": "8 GB",
        "storage": "128 GB / 256 GB", "refresh_rate": "120 Hz",
        "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.2 inches", "Resolution": "1080 x 2400 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "12 MP wide + 64 MP telephoto + 12 MP ultrawide", "Video": "Up to 8K recording"}, "Selfie camera": {"Single": "10 MP"}, "Platform": {"Chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)"}, "Battery": {"Type": "Li-Ion 4000 mAh", "Charging": "25 W wired; 15 W wireless"}},
    },
    {
        "name": "Samsung Galaxy S21+",
        "display_size": "6.7 inches", "display_resolution": "1080 x 2400 pixels",
        "camera_rear": "12 MP wide + 64 MP telephoto + 12 MP ultrawide", "camera_front": "10 MP",
        "battery_capacity_mah": 4800, "chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)",
        "operating_system": "Android 11 (launch version)", "ram": "8 GB", "storage": "128 GB / 256 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.7 inches", "Resolution": "1080 x 2400 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "12 MP wide + 64 MP telephoto + 12 MP ultrawide"}, "Selfie camera": {"Single": "10 MP"}, "Platform": {"Chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)"}, "Battery": {"Type": "Li-Ion 4800 mAh"}},
    },
    {
        "name": "Samsung Galaxy S21 Ultra",
        "display_size": "6.8 inches", "display_resolution": "1440 x 3200 pixels",
        "camera_rear": "108 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide",
        "camera_front": "40 MP", "battery_capacity_mah": 5000,
        "chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)", "operating_system": "Android 11 (launch version)",
        "ram": "12 GB / 16 GB", "storage": "128 GB / 256 GB / 512 GB", "refresh_rate": "120 Hz",
        "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.8 inches", "Resolution": "1440 x 3200 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Quad": "108 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "40 MP"}, "Platform": {"Chipset": "Exynos 2100 / Snapdragon 888 (region-dependent)"}, "Battery": {"Type": "Li-Ion 5000 mAh"}},
    },
    {
        "name": "Samsung Galaxy S22", "display_size": "6.1 inches", "display_resolution": "1080 x 2340 pixels",
        "camera_rear": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "10 MP",
        "battery_capacity_mah": 3700, "chipset": "Exynos 2200 / Snapdragon 8 Gen 1 (region-dependent)",
        "operating_system": "Android 12 (launch version)", "ram": "8 GB", "storage": "128 GB / 256 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.1 inches", "Resolution": "1080 x 2340 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "10 MP"}, "Platform": {"Chipset": "Exynos 2200 / Snapdragon 8 Gen 1 (region-dependent)"}, "Battery": {"Type": "Li-Ion 3700 mAh"}},
    },
    {
        "name": "Samsung Galaxy S22 Ultra", "display_size": "6.8 inches", "display_resolution": "1440 x 3088 pixels",
        "camera_rear": "108 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide",
        "camera_front": "40 MP", "battery_capacity_mah": 5000,
        "chipset": "Exynos 2200 / Snapdragon 8 Gen 1 (region-dependent)", "operating_system": "Android 12 (launch version)",
        "ram": "8 GB / 12 GB", "storage": "128 GB / 256 GB / 512 GB / 1 TB", "refresh_rate": "120 Hz",
        "water_resistance": "IP68", "charging": "45 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.8 inches", "Resolution": "1440 x 3088 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Quad": "108 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "40 MP"}, "Platform": {"Chipset": "Exynos 2200 / Snapdragon 8 Gen 1 (region-dependent)"}, "Battery": {"Type": "Li-Ion 5000 mAh"}},
    },
    {
        "name": "Samsung Galaxy S23", "display_size": "6.1 inches", "display_resolution": "1080 x 2340 pixels",
        "camera_rear": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "12 MP",
        "battery_capacity_mah": 3900, "chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy",
        "operating_system": "Android 13 (launch version)", "ram": "8 GB", "storage": "128 GB / 256 GB / 512 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.1 inches", "Resolution": "1080 x 2340 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "Video": "Up to 8K recording"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy"}, "Battery": {"Type": "Li-Ion 3900 mAh", "Charging": "25 W wired; 15 W wireless"}},
    },
    {
        "name": "Samsung Galaxy S23+", "display_size": "6.6 inches", "display_resolution": "1080 x 2340 pixels",
        "camera_rear": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "12 MP",
        "battery_capacity_mah": 4700, "chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy",
        "operating_system": "Android 13 (launch version)", "ram": "8 GB", "storage": "256 GB / 512 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "45 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.6 inches", "Resolution": "1080 x 2340 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy"}, "Battery": {"Type": "Li-Ion 4700 mAh"}},
    },
    {
        "name": "Samsung Galaxy S23 Ultra", "display_size": "6.8 inches", "display_resolution": "1440 x 3088 pixels",
        "camera_rear": "200 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide",
        "camera_front": "12 MP", "battery_capacity_mah": 5000,
        "chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy", "operating_system": "Android 13 (launch version)",
        "ram": "8 GB / 12 GB", "storage": "256 GB / 512 GB / 1 TB", "refresh_rate": "120 Hz",
        "water_resistance": "IP68", "charging": "45 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.8 inches", "Resolution": "1440 x 3088 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Quad": "200 MP wide + 10 MP telephoto (3x) + 10 MP periscope telephoto (10x) + 12 MP ultrawide", "Video": "Up to 8K recording"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Qualcomm Snapdragon 8 Gen 2 for Galaxy"}, "Battery": {"Type": "Li-Ion 5000 mAh"}},
    },
    {
        "name": "Samsung Galaxy S24", "display_size": "6.2 inches", "display_resolution": "1080 x 2340 pixels",
        "camera_rear": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "12 MP",
        "battery_capacity_mah": 4000, "chipset": "Exynos 2400 / Snapdragon 8 Gen 3 (region-dependent)",
        "operating_system": "Android 14 (launch version)", "ram": "8 GB", "storage": "128 GB / 256 GB / 512 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic LTPO AMOLED 2X", "Size": "6.2 inches", "Resolution": "1080 x 2340 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Exynos 2400 / Snapdragon 8 Gen 3 (region-dependent)"}, "Battery": {"Type": "Li-Ion 4000 mAh"}},
    },
    {
        "name": "Samsung Galaxy S24+", "display_size": "6.7 inches", "display_resolution": "1440 x 3120 pixels",
        "camera_rear": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "12 MP",
        "battery_capacity_mah": 4900, "chipset": "Exynos 2400 / Snapdragon 8 Gen 3 (region-dependent)",
        "operating_system": "Android 14 (launch version)", "ram": "12 GB", "storage": "256 GB / 512 GB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "45 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic LTPO AMOLED 2X", "Size": "6.7 inches", "Resolution": "1440 x 3120 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 10 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Exynos 2400 / Snapdragon 8 Gen 3 (region-dependent)"}, "Battery": {"Type": "Li-Ion 4900 mAh"}},
    },
    {
        "name": "Samsung Galaxy S24 Ultra", "display_size": "6.8 inches", "display_resolution": "1440 x 3120 pixels",
        "camera_rear": "200 MP wide + 50 MP periscope telephoto (5x) + 10 MP telephoto (3x) + 12 MP ultrawide",
        "camera_front": "12 MP", "battery_capacity_mah": 5000, "chipset": "Qualcomm Snapdragon 8 Gen 3 for Galaxy",
        "operating_system": "Android 14 (launch version)", "ram": "12 GB", "storage": "256 GB / 512 GB / 1 TB",
        "refresh_rate": "120 Hz", "water_resistance": "IP68", "charging": "45 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic LTPO AMOLED 2X", "Size": "6.8 inches", "Resolution": "1440 x 3120 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Quad": "200 MP wide + 50 MP periscope telephoto (5x) + 10 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "12 MP"}, "Platform": {"Chipset": "Qualcomm Snapdragon 8 Gen 3 for Galaxy"}, "Battery": {"Type": "Li-Ion 5000 mAh"}},
    },
    {
        "name": "Samsung Galaxy S24 FE", "display_size": "6.7 inches", "display_resolution": "1080 x 2340 pixels",
        "camera_rear": "50 MP wide + 8 MP telephoto (3x) + 12 MP ultrawide", "camera_front": "10 MP",
        "battery_capacity_mah": 4700, "chipset": "Exynos 2400e", "operating_system": "Android 14 (launch version)",
        "ram": "8 GB", "storage": "128 GB / 256 GB / 512 GB", "refresh_rate": "120 Hz",
        "water_resistance": "IP68", "charging": "25 W wired; 15 W wireless",
        "raw_specs": {"Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.7 inches", "Resolution": "1080 x 2340 pixels", "Refresh rate": "120 Hz"}, "Main Camera": {"Triple": "50 MP wide + 8 MP telephoto (3x) + 12 MP ultrawide"}, "Selfie camera": {"Single": "10 MP"}, "Platform": {"Chipset": "Exynos 2400e"}, "Battery": {"Type": "Li-Ion 4700 mAh"}},
    },
]


def slugify(value: str) -> str:
    value = re.sub(r"\s+5g$", "", value.strip(), flags=re.IGNORECASE)
    value = value.lower().replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def seed_demo_data(db: Session) -> int:
    """Insert starter phones only when the catalogue is empty; never overwrite scraped data."""
    inserted = 0
    for item in DEMO_PHONES:
        slug = slugify(item["name"])
        existing = db.scalar(select(Phone).where(Phone.slug == slug))
        if existing:
            continue
        phone = Phone(
            slug=slug,
            brand="Samsung",
            source_name="demo_seed",
            source_url=None,
            data_quality="demo_seed",
            **item,
        )
        db.add(phone)
        inserted += 1
    db.flush()
    # The richer live scraper stores the complete table rows here. Seed rows are
    # also represented in the same table so every agent uses one retrieval path.
    for phone in db.scalars(select(Phone).where(Phone.source_name == "demo_seed")).all():
        if phone.specifications:
            continue
        for section, entries in (phone.raw_specs or {}).items():
            for spec_name, spec_value in entries.items():
                db.add(PhoneSpecification(phone=phone, section=section, spec_name=spec_name, spec_value=str(spec_value)))
    db.commit()
    return inserted
