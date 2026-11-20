from app.scraper.normalization import normalize_specs


def test_normalizes_core_fields_from_gsmarena_rows():
    raw = {
        "Display": {
            "Type": "Dynamic AMOLED 2X, 120Hz, HDR10+",
            "Size": "6.1 inches, 90.1 cm2",
            "Resolution": "1080 x 2340 pixels",
        },
        "Platform": {"OS": "Android 13", "Chipset": "Qualcomm SM8550 Snapdragon 8 Gen 2 (4 nm)"},
        "Memory": {"Internal": "128GB 8GB RAM, 256GB 8GB RAM"},
        "Main Camera": {"Triple": "50 MP, 10 MP telephoto, 12 MP ultrawide"},
        "Selfie camera": {"Single": "12 MP"},
        "Battery": {"Type": "Li-Ion 3900 mAh, non-removable", "Charging": "25W wired"},
        "Our Tests": {"Battery": "Active use score 11:27h", "Battery (old)": "Endurance rating 101h"},
    }

    result = normalize_specs(raw)

    assert result["display_size"].startswith("6.1")
    assert result["display_resolution"] == "1080 x 2340 pixels"
    assert result["battery_capacity_mah"] == 3900
    assert "Snapdragon 8 Gen 2" in result["chipset"]
    assert result["ram"] == "8 GB"
    assert result["storage"] == "128 GB / 256 GB"
    assert "50 MP" in result["camera_rear"]
    assert result["camera_front"] == "12 MP"
    assert result["refresh_rate"] == "120 Hz"
    assert result["active_use_score_minutes"] == 687
    assert result["endurance_rating_hours"] == 101
