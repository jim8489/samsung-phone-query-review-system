from bs4 import BeautifulSoup

from app.scraper.gsmarena import GSMArenaScraper, ScrapedPhone
from app.services.catalog import upsert_scraped_phone


HTML = """
<html><head><link rel="canonical" href="https://www.gsmarena.com/samsung_galaxy_s23-12345.php"></head><body>
  <h1 class="specs-phone-name-title">Samsung Galaxy S23</h1>
  <div id="specs-list">
    <table><tbody>
      <tr class="ttl"><th colspan="2">Display</th></tr>
      <tr><td class="ttl">Type</td><td class="nfo">Dynamic AMOLED 2X, 120Hz</td></tr>
      <tr><td class="ttl">Size</td><td class="nfo">6.1 inches</td></tr>
      <tr><td class="ttl">Resolution</td><td class="nfo">1080 x 2340 pixels</td></tr>
    </tbody></table>
    <table><tbody>
      <tr class="ttl"><th colspan="2">Platform</th></tr>
      <tr><td class="ttl">Chipset</td><td class="nfo">Snapdragon 8 Gen 2</td></tr>
      <tr><td class="ttl">OS</td><td class="nfo">Android 13</td></tr>
    </tbody></table>
    <table><tbody>
      <tr class="ttl"><th colspan="2">Memory</th></tr>
      <tr><td class="ttl">Internal</td><td class="nfo">128GB 8GB RAM</td></tr>
      <tr><td class="ttl">Card slot</td><td class="nfo">No</td></tr>
    </tbody></table>
    <table><tbody>
      <tr class="ttl"><th colspan="2">Main Camera</th></tr>
      <tr><td class="ttl">Triple</td><td class="nfo">50 MP wide, 10 MP telephoto, 12 MP ultrawide</td></tr>
    </tbody></table>
    <table><tbody>
      <tr class="ttl"><th colspan="2">Battery</th></tr>
      <tr><td class="ttl">Type</td><td class="nfo">Li-Ion 3900 mAh</td></tr>
      <tr><td class="ttl">Charging</td><td class="nfo">25W wired</td></tr>
    </tbody></table>
  </div>
</body></html>
"""


def test_scraper_parses_specification_sections(monkeypatch):
    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(scraper, "find_phone_url", lambda model: ("Samsung Galaxy S23", "https://www.gsmarena.com/samsung_galaxy_s23-12345.php"))
    monkeypatch.setattr(scraper, "_get_soup", lambda url: BeautifulSoup(HTML, "html.parser"))
    comparison_html = """<div id="specs-list"><table><tbody>
      <tr class="ttl"><th colspan="2">Our Tests</th></tr>
      <tr><td class="ttl">Battery</td><td class="nfo">Active use score 11:27h</td></tr>
      <tr><td class="ttl">Battery (old)</td><td class="nfo">Endurance rating 101h</td></tr>
    </tbody></table></div>"""

    def fake_get_soup(url):
        html = comparison_html if "compare.php3" in url else HTML
        return BeautifulSoup(html, "html.parser")

    monkeypatch.setattr(scraper, "_get_soup", fake_get_soup)
    try:
        result = scraper.scrape_detail("Galaxy S23")
    finally:
        scraper.close()

    assert result.name == "Samsung Galaxy S23"
    assert result.raw_specs["Display"]["Size"] == "6.1 inches"
    assert result.normalized["battery_capacity_mah"] == 3900
    assert result.normalized["chipset"] == "Snapdragon 8 Gen 2"
    assert result.normalized["active_use_score_minutes"] == 687
    assert result.normalized["endurance_rating_hours"] == 101
    assert result.test_source_url == "https://www.gsmarena.com/compare.php3?idPhone1=12345"


def test_find_phone_url_prefers_exact_model_match(monkeypatch):
    html = """
    <div class="makers"><ul>
      <li><a href="samsung_galaxy_s23_ultra-12024.php">Samsung Galaxy S23 Ultra</a></li>
      <li><a href="samsung_galaxy_s23-12082.php">Samsung Galaxy S23</a></li>
    </ul></div>
    """
    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(scraper, "_get_soup", lambda url: BeautifulSoup(html, "html.parser"))
    try:
        label, url = scraper.find_phone_url("Galaxy S23")
    finally:
        scraper.close()
    assert label == "Samsung Galaxy S23"
    assert url.endswith("samsung_galaxy_s23-12082.php")


def test_find_phone_url_rejects_ambiguous_partial_matches(monkeypatch):
    html = """
    <div class="makers"><ul>
      <li><a href="samsung_galaxy_s23_fe-1.php">Samsung Galaxy S23 FE</a></li>
      <li><a href="samsung_galaxy_s23_ultra-2.php">Samsung Galaxy S23 Ultra</a></li>
    </ul></div>
    """
    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(scraper, "_get_soup", lambda url: BeautifulSoup(html, "html.parser"))
    try:
        try:
            scraper.find_phone_url("Galaxy S23")
        except LookupError as exc:
            assert "Ambiguous" in str(exc)
        else:
            raise AssertionError("Ambiguous search results should not be silently selected.")
    finally:
        scraper.close()


def test_scraper_enforces_respectful_minimum_delay():
    try:
        GSMArenaScraper(delay_seconds=0.5)
    except ValueError as exc:
        assert "at least 2 seconds" in str(exc)
    else:
        raise AssertionError("The scraper should reject an aggressive request interval.")


def test_scraped_phone_upsert_persists_specs_and_source_provenance(db_session):
    raw_specs = {
        "Display": {"Type": "Dynamic AMOLED 2X", "Size": "6.1 inches", "Resolution": "1080 x 2340"},
        "Platform": {"Chipset": "Snapdragon 8 Gen 2"},
        "Battery": {"Type": "Li-Ion 3900 mAh"},
        "Our Tests": {"Battery": "Active use score 11:27h"},
    }
    item = ScrapedPhone(
        name="Samsung Galaxy S23 Live Test",
        source_url="https://www.gsmarena.com/samsung_galaxy_s23_live-12345.php",
        test_source_url="https://www.gsmarena.com/compare.php3?idPhone1=12345",
        raw_specs=raw_specs,
        normalized={
            "display_size": "6.1 inches",
            "battery_capacity_mah": 3900,
            "active_use_score_minutes": 687,
            "endurance_rating_hours": None,
        },
    )

    phone = upsert_scraped_phone(db_session, item)
    db_session.commit()

    assert phone.data_quality == "scraped"
    assert phone.source_url == item.source_url
    assert phone.test_source_url == item.test_source_url
    assert phone.active_use_score_minutes == 687
    assert len(phone.specifications) == 6


def test_scraper_keeps_primary_specs_when_test_enrichment_fails(monkeypatch):
    import requests

    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(
        scraper,
        "find_phone_url",
        lambda model: ("Samsung Galaxy S23", "https://www.gsmarena.com/samsung_galaxy_s23-12345.php"),
    )

    def fake_get_soup(url):
        if "compare.php3" in url:
            raise requests.ConnectionError("comparison page unavailable")
        return BeautifulSoup(HTML, "html.parser")

    monkeypatch.setattr(scraper, "_get_soup", fake_get_soup)
    try:
        result = scraper.scrape_detail("Galaxy S23")
    finally:
        scraper.close()

    assert result.name == "Samsung Galaxy S23"
    assert result.normalized["battery_capacity_mah"] == 3900
    assert result.test_source_url is None


def test_parser_handles_current_rowspanned_gsmarena_tables_and_saved_html():
    html = """
    <!doctype html><html><head>
      <title>Samsung Galaxy S23 - Full phone specifications</title>
      <link rel="canonical" href="https://www.gsmarena.com/samsung_galaxy_s23-12082.php">
    </head><body>
      <h1 class="specs-phone-name-title">Samsung Galaxy S23</h1>
      <div id="specs-list">
        <table><tr>
          <th rowspan="4" scope="row">Display</th>
          <td class="ttl">Type</td>
          <td class="nfo" data-spec="displaytype">Dynamic AMOLED 2X, 120Hz</td>
        </tr><tr>
          <td class="ttl">Size</td>
          <td class="nfo" data-spec="displaysize">6.1 inches, 90.1 cm<sup>2</sup></td>
        </tr><tr>
          <td class="ttl">Resolution</td>
          <td class="nfo" data-spec="displayresolution">1080 x 2340 pixels</td>
        </tr></table>
        <table><tr>
          <th rowspan="3" scope="row">Platform</th>
          <td class="ttl">Chipset</td>
          <td class="nfo" data-spec="chipset">Snapdragon 8 Gen 2 (4 nm)</td>
        </tr><tr>
          <td class="ttl">OS</td>
          <td class="nfo" data-spec="os">Android 13</td>
        </tr></table>
        <table><tr>
          <th rowspan="4" scope="row">Main Camera</th>
          <td class="ttl">Triple</td>
          <td class="nfo" data-spec="cam1modules">50 MP wide<br>10 MP telephoto<br>12 MP ultrawide</td>
        </tr></table>
        <table><tr>
          <th rowspan="2" scope="row">Selfie camera</th>
          <td class="ttl">Single</td>
          <td class="nfo" data-spec="cam2modules">12 MP wide</td>
        </tr><tr>
          <td class="ttl">Video</td><td class="nfo">4K@30/60fps</td>
        </tr></table>
        <table><tr>
          <th rowspan="2" scope="row">Battery</th>
          <td class="ttl">Type</td><td class="nfo" data-spec="batdescription1">Li-Ion 3900 mAh</td>
        </tr><tr>
          <td class="ttl">Charging</td><td class="nfo">25W wired<br>15W wireless</td>
        </tr></table>
        <table><tr>
          <th rowspan="2" scope="row">Our Tests</th>
          <td class="ttl">Battery</td><td class="nfo" data-spec="batlife2">Active use score 11:27h</td>
        </tr><tr>
          <td class="ttl">Battery (old)</td><td class="nfo">Endurance rating 101h</td>
        </tr></table>
      </div>
    </body></html>
    """

    item = GSMArenaScraper.parse_detail_html(html)

    assert item.name == "Samsung Galaxy S23"
    assert item.source_url == "https://www.gsmarena.com/samsung_galaxy_s23-12082.php"
    assert item.test_source_url == item.source_url
    assert set(item.raw_specs) == {"Display", "Platform", "Main Camera", "Selfie camera", "Battery", "Our Tests"}
    assert item.normalized["display_size"] == "6.1 inches, 90.1 cm²"
    assert item.normalized["chipset"] == "Snapdragon 8 Gen 2 (4 nm)"
    assert item.normalized["battery_capacity_mah"] == 3900
    assert item.normalized["active_use_score_minutes"] == 687
    assert item.normalized["endurance_rating_hours"] == 101
    assert "10 MP telephoto" in item.normalized["camera_rear"]
    assert item.normalized["camera_front"] == "12 MP wide"


def test_saved_html_parser_rejects_cloudflare_turnstile_page():
    html = "<html><head><title>GSMArena Turnstile check</title></head><body>Continue</body></html>"
    try:
        GSMArenaScraper.parse_detail_html(html)
    except ValueError as exc:
        assert "human-verification" in str(exc)
    else:
        raise AssertionError("Turnstile pages must never be imported as phone data.")


def test_search_reports_turnstile_instead_of_misleading_no_result(monkeypatch):
    scraper = GSMArenaScraper(delay_seconds=2)
    html = "<html><head><title>GSMArena Turnstile check</title></head><body>Continue</body></html>"
    monkeypatch.setattr(scraper, "_get_soup", lambda url: BeautifulSoup(html, "html.parser"))
    try:
        try:
            scraper.find_phone_url("Galaxy S23")
        except RuntimeError as exc:
            assert "Turnstile human-verification" in str(exc)
            assert "import_saved_html.py" in str(exc)
        else:
            raise AssertionError("A Turnstile page must not be reported as an empty search result.")
    finally:
        scraper.close()
