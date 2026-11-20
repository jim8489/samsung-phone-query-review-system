from __future__ import annotations

from app.scraper.browser import GSMArenaBrowserScraper


SEARCH_HTML = """
<html><head><title>GSMArena search results</title></head><body><div class="makers"><ul>
<li><a href="samsung_galaxy_s23_ultra-12024.php">Samsung Galaxy S23 Ultra</a></li>
<li><a href="samsung_galaxy_s23-12082.php">Samsung Galaxy S23</a></li>
</ul></div></body></html>
"""
DETAIL_HTML = """
<!doctype html><html><head><title>Samsung Galaxy S23 - Full phone specifications</title>
<link rel="canonical" href="https://www.gsmarena.com/samsung_galaxy_s23-12082.php"></head><body>
<h1 class="specs-phone-name-title">Samsung Galaxy S23</h1><div id="specs-list">
<table><tr><th rowspan="3" scope="row">Display</th><td class="ttl">Type</td><td class="nfo">AMOLED, 120Hz</td></tr>
<tr><td class="ttl">Size</td><td class="nfo">6.1 inches</td></tr><tr><td class="ttl">Resolution</td><td class="nfo">1080 x 2340 pixels</td></tr></table>
<table><tr><th rowspan="2" scope="row">Platform</th><td class="ttl">Chipset</td><td class="nfo">Snapdragon 8 Gen 2</td></tr>
<tr><td class="ttl">OS</td><td class="nfo">Android 13</td></tr></table>
<table><tr><th rowspan="1" scope="row">Main Camera</th><td class="ttl">Triple</td><td class="nfo">50 MP wide<br>10 MP telephoto<br>12 MP ultrawide</td></tr></table>
<table><tr><th rowspan="2" scope="row">Battery</th><td class="ttl">Type</td><td class="nfo">Li-Ion 3900 mAh</td></tr>
<tr><td class="ttl">Charging</td><td class="nfo">25W wired</td></tr></table>
<table><tr><th rowspan="2" scope="row">Our Tests</th><td class="ttl">Battery</td><td class="nfo">Active use score 11:27h</td></tr>
<tr><td class="ttl">Battery (old)</td><td class="nfo">Endurance rating 101h</td></tr></table></div>
<table class="pricing inline widget"><tbody><tr><td>128GB 8GB RAM</td>
<td><a href="https://www.amazon.com/item">$ 230.61</a></td><td><a href="https://www.amazon.de/item">€ 292.32</a></td></tr></tbody></table>
</body></html>
"""


class FakeDriver:
    def __init__(self, pages):
        self.pages = pages
        self.page_source = ""
        self.current_url = ""
        self.title = ""
        self.visited = []
        self.closed = False

    def set_page_load_timeout(self, _seconds):
        return None

    def get(self, url):
        self.current_url = url
        self.visited.append(url)
        self.page_source, self.title = self.pages[url]

    def execute_script(self, _script):
        return "complete"

    def quit(self):
        self.closed = True


def test_selenium_scraper_navigates_and_parses_with_beautifulsoup(monkeypatch):
    from app.scraper import browser as browser_module

    monkeypatch.setattr(browser_module.time, "sleep", lambda _seconds: None)
    search_url = "https://www.gsmarena.com/results.php3?sQuickSearch=yes&sName=Galaxy+S23"
    detail_url = "https://www.gsmarena.com/samsung_galaxy_s23-12082.php"
    driver = FakeDriver(
        {
            search_url: (SEARCH_HTML, "GSMArena search results"),
            detail_url: (DETAIL_HTML, "Samsung Galaxy S23 - Full phone specifications"),
        }
    )
    scraper = GSMArenaBrowserScraper(delay_seconds=2, driver=driver)
    try:
        item = scraper.scrape_detail("Galaxy S23")
    finally:
        scraper.close()

    assert item.name == "Samsung Galaxy S23"
    assert item.normalized["battery_capacity_mah"] == 3900
    assert item.normalized["active_use_score_minutes"] == 687
    assert item.normalized["endurance_rating_hours"] == 101
    assert len(item.price_observations) == 2
    assert len(driver.visited) == 2
    assert driver.closed is True


def test_selenium_pauses_for_human_turnstile_completion(monkeypatch):
    from app.scraper import browser as browser_module

    monkeypatch.setattr(browser_module.time, "sleep", lambda _seconds: None)
    challenge = (
        '<html><head><title>GSMArena Turnstile check</title></head>'
        '<body>One quick check before you continue</body></html>'
    )
    search_url = "https://www.gsmarena.com/results.php3?sQuickSearch=yes&sName=Galaxy+S23"
    driver = FakeDriver({search_url: (challenge, "GSMArena Turnstile check")})

    def complete_human_check(_prompt):
        driver.page_source = SEARCH_HTML
        driver.title = "GSMArena search results"
        return ""

    scraper = GSMArenaBrowserScraper(delay_seconds=2, driver=driver, input_fn=complete_human_check)
    try:
        label, url = scraper.find_phone_url("Galaxy S23")
    finally:
        scraper.close()
    assert label == "Samsung Galaxy S23"
    assert url.endswith("samsung_galaxy_s23-12082.php")


def test_selenium_turnstile_detector():
    challenge = '<html><head><title>GSMArena Turnstile check</title></head><body>Continue</body></html>'
    assert GSMArenaBrowserScraper.is_turnstile_page(challenge, "GSMArena Turnstile check")
    assert not GSMArenaBrowserScraper.is_turnstile_page(SEARCH_HTML, "GSMArena search results")


def test_gsmarena_price_extractor_keeps_variant_currency_and_merchant():
    from bs4 import BeautifulSoup

    html = """
    <table class="pricing inline widget"><tbody>
      <tr><td>128GB 8GB RAM</td>
      <td><a href="https://www.amazon.com/dp/example">$ 230.61</a></td>
      <td><a href="https://www.amazon.de/dp/example">€ 292.32</a></td></tr>
    </tbody></table>
    """
    quotes = __import__("app.scraper.gsmarena", fromlist=["GSMArenaScraper"]).GSMArenaScraper._extract_price_observations(
        BeautifulSoup(html, "html.parser")
    )
    assert [(item["currency"], item["amount"]) for item in quotes] == [("USD", 230.61), ("EUR", 292.32)]
    assert all("128GB 8GB RAM" in item["source"] for item in quotes)
