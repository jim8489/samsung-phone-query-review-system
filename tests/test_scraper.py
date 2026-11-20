from bs4 import BeautifulSoup

from app.scraper.gsmarena import GSMArenaScraper, ScrapedPhone
from app.services.catalog import upsert_scraped_phone


HTML = """
<html><body>
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
    </tbody></table>
    <table><tbody>
      <tr class="ttl"><th colspan="2">Battery</th></tr>
      <tr><td class="ttl">Type</td><td class="nfo">Li-Ion 3900 mAh</td></tr>
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



def test_project_research_user_agent_is_replaced_with_the_proven_working_ua():
    from app.scraper.gsmarena import TESTED_CHROME_USER_AGENT, resolve_scraper_user_agent

    configured = "SamsungPhoneResearchBot/1.0 (+mailto:research@example.com)"
    assert resolve_scraper_user_agent(configured) == TESTED_CHROME_USER_AGENT


def test_explicit_meaningful_scraper_user_agent_is_preserved():
    from app.scraper.gsmarena import resolve_scraper_user_agent

    configured = "ExampleResearchCrawler/2.0 (+mailto:research@example.com)"
    assert resolve_scraper_user_agent(configured) == configured


def test_default_scraper_user_agent_matches_the_successful_cli_transport():
    from app.scraper.gsmarena import GSMArenaScraper, TESTED_CHROME_USER_AGENT

    scraper = GSMArenaScraper(delay_seconds=2)
    try:
        assert scraper.session.headers["User-Agent"] == TESTED_CHROME_USER_AGENT
    finally:
        scraper.close()
