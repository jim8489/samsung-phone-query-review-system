from __future__ import annotations

from bs4 import BeautifulSoup

from app.scraper.gsmarena import (
    GSMArenaChallengeError,
    GSMArenaScraper,
    SAMSUNG_CATALOGUE_URL,
)


PAGE_1 = """
<html><head><title>All Samsung phones</title></head><body>
<div class="makers"><ul>
  <li><a href="samsung_galaxy_s23_ultra-12024.php"><img alt="Samsung Galaxy S23 Ultra"></a></li>
  <li><a href="samsung_galaxy_s23-12082.php"><img alt="Samsung Galaxy S23 5G"></a></li>
</ul></div>
<div class="nav-pages"><a class="pages-next" href="samsung-phones-f-9-0-p2.php">Next</a></div>
</body></html>
"""

PAGE_2 = """
<html><head><title>All Samsung phones</title></head><body>
<div class="makers"><ul>
  <li><a href="samsung_galaxy_s21_ultra-10626.php">Samsung Galaxy S21 Ultra 5G</a></li>
  <li><a href="samsung_galaxy_s21-10627.php">Samsung Galaxy S21 5G</a></li>
</ul></div>
</body></html>
"""


def test_catalogue_crawler_uses_manufacturer_listing_and_not_quick_search(monkeypatch):
    scraper = GSMArenaScraper(delay_seconds=2)
    visited = []

    def fake_get_soup(url):
        visited.append(url)
        return BeautifulSoup(PAGE_1, "html.parser")

    monkeypatch.setattr(scraper, "_get_soup", fake_get_soup)
    try:
        label, url = scraper.find_phone_url("Galaxy S23")
    finally:
        scraper.close()

    assert label == "Samsung Galaxy S23 5G"
    assert url.endswith("samsung_galaxy_s23-12082.php")
    assert visited == [SAMSUNG_CATALOGUE_URL]
    assert all("results.php3" not in requested for requested in visited)


def test_catalogue_crawler_follows_next_page_for_older_models(monkeypatch):
    scraper = GSMArenaScraper(delay_seconds=2)
    visited = []
    pages = {
        SAMSUNG_CATALOGUE_URL: PAGE_1,
        "https://www.gsmarena.com/samsung-phones-f-9-0-p2.php": PAGE_2,
    }

    def fake_get_soup(url):
        visited.append(url)
        return BeautifulSoup(pages[url], "html.parser")

    monkeypatch.setattr(scraper, "_get_soup", fake_get_soup)
    try:
        label, url = scraper.find_phone_url("Galaxy S21")
    finally:
        scraper.close()

    assert label == "Samsung Galaxy S21 5G"
    assert url.endswith("samsung_galaxy_s21-10627.php")
    assert visited == list(pages)
    assert scraper._catalogue_page_count == 2


def test_catalogue_variant_matching_does_not_confuse_base_and_ultra(monkeypatch):
    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(
        scraper,
        "_get_soup",
        lambda _url: BeautifulSoup(PAGE_1, "html.parser"),
    )
    try:
        label, url = scraper.find_phone_url("Galaxy S23 Ultra")
    finally:
        scraper.close()
    assert label == "Samsung Galaxy S23 Ultra"
    assert url.endswith("samsung_galaxy_s23_ultra-12024.php")


def test_catalogue_crawler_reports_challenge_instead_of_empty_results(monkeypatch):
    import requests
    import pytest

    scraper = GSMArenaScraper(delay_seconds=2)
    challenge_html = (
        "<html><head><title>GSMArena Turnstile check</title></head>"
        "<body>One quick check before you continue</body></html>"
    )
    response = requests.Response()
    response.status_code = 200
    response.url = SAMSUNG_CATALOGUE_URL
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._content = challenge_html.encode("utf-8")
    monkeypatch.setattr(scraper.session, "get", lambda *_args, **_kwargs: response)
    try:
        with pytest.raises(GSMArenaChallengeError, match="Turnstile"):
            scraper.find_phone_url("Galaxy S21")
    finally:
        scraper.close()

    assert GSMArenaScraper._is_challenge_page(BeautifulSoup(challenge_html, "html.parser")) is True
    assert GSMArenaScraper._is_challenge_page(BeautifulSoup(PAGE_1, "html.parser")) is False


def test_catalogue_next_page_is_restricted_to_gsmarena_host():
    html = '<div class="nav-pages"><a class="pages-next" href="https://example.com/evil.php">Next</a></div>'
    soup = BeautifulSoup(html, "html.parser")
    assert GSMArenaScraper._next_catalogue_page(soup, SAMSUNG_CATALOGUE_URL) is None


def test_catalogue_matching_rejects_partial_variant_instead_of_guessing(monkeypatch):
    html = """<div class="makers">
    <a href="samsung_galaxy_s21_fe-1.php">Samsung Galaxy S21 FE</a>
    <a href="samsung_galaxy_s21_ultra-2.php">Samsung Galaxy S21 Ultra</a>
    </div>"""
    scraper = GSMArenaScraper(delay_seconds=2)
    monkeypatch.setattr(scraper, "_get_soup", lambda _url: BeautifulSoup(html, "html.parser"))
    try:
        try:
            scraper.find_phone_url("Galaxy S21")
        except LookupError as exc:
            assert "Ambiguous" in str(exc)
        else:
            raise AssertionError("The crawler must not guess between FE and Ultra variants.")
    finally:
        scraper.close()
