from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus, urlparse

from bs4 import BeautifulSoup

from app.scraper.gsmarena import BASE_URL, GSMArenaScraper, ScrapedPhone
from app.scraper.normalization import normalize_specs


class GSMArenaBrowserScraper:
    """Visible Selenium/Chrome transport with BeautifulSoup extraction.

    Selenium is used only to navigate public pages in a normal visible browser.
    If GSMArena presents a Turnstile challenge, the user completes it manually.
    The project does not solve, evade, or automate the challenge.
    """

    def __init__(
        self,
        delay_seconds: float = 3.0,
        profile_dir: str | Path = "data/chrome_profile_gsmarena",
        *,
        driver=None,
        verification_timeout_seconds: int = 300,
        input_fn: Callable[[str], str] | None = None,
    ) -> None:
        if delay_seconds < 2.0:
            raise ValueError("Use a delay of at least 2 seconds between page navigations.")
        self.delay_seconds = delay_seconds
        self.verification_timeout_seconds = verification_timeout_seconds
        self.input_fn = input_fn or input
        self._last_navigation_at = 0.0
        self.driver = driver if driver is not None else self._create_driver(profile_dir)
        if hasattr(self.driver, "set_page_load_timeout"):
            self.driver.set_page_load_timeout(60)

    @staticmethod
    def _create_driver(profile_dir: str | Path):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError as exc:
            raise RuntimeError(
                "Selenium is not installed. Run: python -m pip install -r requirements-addons.txt"
            ) from exc

        profile_path = Path(profile_dir).expanduser().resolve()
        profile_path.mkdir(parents=True, exist_ok=True)
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--lang=en-US")
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        # Selenium Manager resolves a compatible ChromeDriver automatically.
        # Chrome remains visible so a human can complete a site verification.
        try:
            return webdriver.Chrome(options=options)
        except Exception as exc:
            raise RuntimeError(
                "Could not start Chrome through Selenium. Confirm Google Chrome is installed, "
                "install requirements-addons.txt, close other scraper windows using the same "
                "profile, and allow Selenium Manager to resolve ChromeDriver. "
                f"Original error: {exc}"
            ) from exc

    @staticmethod
    def is_turnstile_page(html: str, title: str = "") -> bool:
        normalized_title = (title or "").casefold()
        if "turnstile" in normalized_title:
            return True
        soup = BeautifulSoup(html or "", "html.parser")
        visible_text = soup.get_text(" ", strip=True).casefold()
        challenge_phrases = (
            "one quick check before you continue",
            "verify you are human",
            "complete the security check",
            "checking your browser",
        )
        if any(phrase in visible_text for phrase in challenge_phrases):
            return True
        return bool(
            soup.select_one(
                'iframe[src*="challenges.cloudflare.com"], '
                '.cf-turnstile, input[name="cf-turnstile-response"], #challenge-form'
            )
        )

    def _wait_for_document_ready(self, timeout_seconds: int = 45) -> None:
        if not hasattr(self.driver, "execute_script"):
            return
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                if self.driver.execute_script("return document.readyState") == "complete":
                    return
            except Exception:
                # Browser may be in the middle of a redirect/navigation.
                pass
            time.sleep(0.25)
        raise TimeoutError("Timed out waiting for the GSMArena page to finish loading.")

    def _pause_for_human_verification(self, html: str) -> str:
        title = getattr(self.driver, "title", "") or ""
        if not self.is_turnstile_page(html, title):
            return html

        if not sys.stdin.isatty() and self.input_fn is input:
            raise RuntimeError(
                "GSMArena requires human verification. Run the scraper from an interactive Terminal "
                "so you can complete the check in the visible Chrome window."
            )

        print("\n[VERIFY] GSMArena is requesting human verification in Chrome.")
        print("         Complete the check yourself in the visible browser. Do not automate or bypass it.")
        self.input_fn("         When the real GSMArena page is visible, press Enter here to continue...")

        deadline = time.monotonic() + self.verification_timeout_seconds
        while time.monotonic() < deadline:
            current_html = self.driver.page_source
            current_title = getattr(self.driver, "title", "") or ""
            if not self.is_turnstile_page(current_html, current_title):
                self._wait_for_document_ready()
                return self.driver.page_source
            time.sleep(1.0)

        raise TimeoutError(
            "The human-verification page is still present. No challenge was bypassed. "
            "Stop and retry later if GSMArena has not accepted the manual check."
        )

    def _navigate(self, url: str) -> str:
        elapsed = time.monotonic() - self._last_navigation_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self.driver.get(url)
        self._last_navigation_at = time.monotonic()
        self._wait_for_document_ready()
        return self._pause_for_human_verification(self.driver.page_source)

    def find_phone_url(self, model_name: str) -> tuple[str, str]:
        search_url = f"{BASE_URL}/results.php3?sQuickSearch=yes&sName={quote_plus(model_name)}"
        html = self._navigate(search_url)
        return GSMArenaScraper.find_phone_url_in_html(html, model_name)

    def scrape_detail(self, model_name: str) -> ScrapedPhone:
        _result_name, detail_url = self.find_phone_url(model_name)
        detail_html = self._navigate(detail_url)
        item = GSMArenaScraper.parse_detail_html(
            detail_html,
            source_url=detail_url,
            expected_model=model_name,
        )

        # Most current GSMArena specification pages include an "Our Tests"
        # section with measured battery metrics. Fetch the comparison page only
        # when those measurements are missing from the detail page.
        if item.test_source_url is None:
            import re

            match = re.search(r"-(\d+)\.php$", urlparse(detail_url).path)
            if match:
                comparison_url = f"{BASE_URL}/compare.php3?idPhone1={match.group(1)}"
                comparison_html = self._navigate(comparison_url)
                comparison_sections = GSMArenaScraper._parse_spec_sections(
                    BeautifulSoup(comparison_html, "html.parser")
                )
                test_sections = {
                    section: values
                    for section, values in comparison_sections.items()
                    if "test" in section.casefold()
                }
                if test_sections:
                    item.raw_specs.update(test_sections)
                    item.normalized = normalize_specs(item.raw_specs)
                    item.test_source_url = comparison_url
        return item

    def close(self) -> None:
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
