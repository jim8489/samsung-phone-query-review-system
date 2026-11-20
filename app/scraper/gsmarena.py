from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings
from app.data.seed import DEMO_PHONES
from app.scraper.normalization import normalize_specs

BASE_URL = "https://www.gsmarena.com"
SAMSUNG_CATALOGUE_URL = f"{BASE_URL}/samsung-phones-9.php"
DEFAULT_MAX_CATALOGUE_PAGES = 30
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScrapedPhone:
    name: str
    source_url: str
    raw_specs: dict[str, dict[str, str]]
    normalized: dict[str, Any]
    test_source_url: str | None = None
    price_observations: list[dict[str, Any]] = field(default_factory=list)


def _clean_name(value: str) -> str:
    """Normalize catalogue labels and requested Samsung model names.

    Marketing suffixes such as ``5G`` are ignored, while meaningful variants
    (Plus, Ultra, FE, Fold, Flip) remain part of the identity. This prevents a
    request for Galaxy S21 from accidentally selecting S21 Ultra or S21 FE.
    """
    value = (value or "").casefold().replace("+", " plus ")
    tokens = re.findall(r"[a-z0-9]+", value)
    tokens = [token for token in tokens if token not in {"samsung", "galaxy", "5g"}]
    return "".join(tokens)


class GSMArenaChallengeError(RuntimeError):
    """Raised when GSMArena returns a human-verification page instead of data."""


def _cell_text(node: Tag) -> str:
    """Extract cell text while preserving <br> boundaries and inline markup."""
    pieces: list[str] = []

    def visit(element: object) -> None:
        if isinstance(element, NavigableString):
            pieces.append(str(element))
        elif isinstance(element, Tag):
            if element.name == "br":
                pieces.append(" | ")
            # Python's built-in html.parser can attach the text following a
            # self-closing <br /> beneath the br node. Traversing its children
            # also handles that malformed-but-recoverable tree shape.
            for child in element.children:
                visit(child)

    for child in node.children:
        visit(child)
    value = "".join(pieces)
    value = re.sub(r"\s*\|\s*", " | ", value)
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"(?:\s*\|\s*)+$", "", value).strip()
    return re.sub(r"\bcm2\b", "cm²", value)


class GSMArenaScraper:
    """Polite catalogue-driven GSMArena crawler using Requests and BeautifulSoup."""

    def __init__(
        self,
        delay_seconds: float | None = None,
        timeout_seconds: float | None = None,
        *,
        user_agent: str | None = None,
        catalogue_url: str = SAMSUNG_CATALOGUE_URL,
        max_catalogue_pages: int = DEFAULT_MAX_CATALOGUE_PAGES,
    ):
        self.delay_seconds = settings.scraper_delay_seconds if delay_seconds is None else delay_seconds
        if self.delay_seconds < 2.0:
            raise ValueError("Use a request delay of at least 2 seconds for respectful scraping.")
        if max_catalogue_pages < 1:
            raise ValueError("max_catalogue_pages must be at least 1")
        self.timeout_seconds = timeout_seconds or settings.scraper_timeout_seconds
        self.catalogue_url = catalogue_url
        self.max_catalogue_pages = max_catalogue_pages
        self._catalogue_next_url: str | None = catalogue_url
        self._catalogue_page_count = 0
        self._catalogue_candidates: list[tuple[str, str]] = []
        self._catalogue_visited_urls: set[str] = set()
        self._catalogue_exhausted = False
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": BASE_URL + "/",
            }
        )
        retry = Retry(total=3, connect=3, read=3, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._last_request_at = 0.0

    @staticmethod
    def _is_challenge_page(soup: BeautifulSoup) -> bool:
        title = soup.title.get_text(" ", strip=True).casefold() if soup.title else ""
        visible_text = soup.get_text(" ", strip=True).casefold()
        return (
            "turnstile" in title
            or "one quick check before you continue" in visible_text
            or "verify you are human" in visible_text
            or bool(soup.select_one(
                '.cf-turnstile, input[name="cf-turnstile-response"], '
                'iframe[src*="challenges.cloudflare.com"], #challenge-form'
            ))
        )

    def _get_soup(self, url: str) -> BeautifulSoup:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        response = self.session.get(url, timeout=self.timeout_seconds)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        content_type = response.headers.get("content-type", "text/html").lower()
        if "text/html" not in content_type:
            raise ValueError(f"Unexpected content type from {url}: {content_type}")
        soup = BeautifulSoup(response.text, "html.parser")
        if self._is_challenge_page(soup):
            raise GSMArenaChallengeError(
                "GSMArena returned a Turnstile human-verification page instead of "
                f"data for {response.url}. No data was scraped. If you have an "
                "authorized browser-assisted capture, import it with "
                "scripts/import_saved_html.py."
            )
        return soup

    @staticmethod
    def _extract_catalogue_candidates(soup: BeautifulSoup) -> list[tuple[str, str]]:
        """Extract Samsung handset links from the manufacturer listing page."""
        candidates: list[tuple[str, str]] = []
        seen: set[str] = set()
        for anchor in soup.select(".makers a[href], .maker-list a[href]"):
            label = " ".join(anchor.stripped_strings)
            if not label:
                image = anchor.select_one("img[alt], img[title]")
                if image:
                    label = (image.get("alt") or image.get("title") or "").strip()
            href = anchor.get("href", "").strip()
            if not label or not href:
                continue
            full_url = urljoin(BASE_URL + "/", href)
            parsed = urlparse(full_url)
            if parsed.scheme != "https" or parsed.hostname not in {
                "gsmarena.com", "www.gsmarena.com", "m.gsmarena.com"
            }:
                continue
            if not re.search(r"-[0-9]+\.php$", parsed.path):
                continue
            if "samsung" not in label.casefold() and "galaxy" not in label.casefold():
                continue
            if full_url not in seen:
                candidates.append((label, full_url))
                seen.add(full_url)
        return candidates

    @staticmethod
    def _next_catalogue_page(soup: BeautifulSoup, current_url: str) -> str | None:
        """Return GSMArena's explicit Next-page URL, if one is present."""
        anchor = soup.select_one(
            "a.pages-next[href], .nav-pages a.pages-next[href], a[rel~='next'][href]"
        )
        if anchor is None:
            for candidate in soup.select(".nav-pages a[href], .pages a[href]"):
                label = " ".join(candidate.stripped_strings).casefold()
                title = (candidate.get("title") or "").casefold()
                aria = (candidate.get("aria-label") or "").casefold()
                if "next" in label or "next" in title or "next" in aria:
                    anchor = candidate
                    break
        if anchor is None:
            return None
        href = (anchor.get("href") or "").strip()
        if not href or href == "#" or href.casefold().startswith("javascript:"):
            return None
        next_url = urljoin(current_url, href)
        parsed = urlparse(next_url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "gsmarena.com", "www.gsmarena.com", "m.gsmarena.com"
        }:
            return None
        return next_url

    @staticmethod
    def _raise_if_challenge_page(soup: BeautifulSoup, url: str) -> None:
        """Fail explicitly if a transport or test double returns a challenge page.

        `_get_soup` normally performs this check, but keeping the guard at the
        catalogue boundary makes the crawler safe when an alternate transport
        or a test override supplies the parsed HTML directly.
        """
        if GSMArenaScraper._is_challenge_page(soup):
            raise GSMArenaChallengeError(
                "GSMArena returned a Turnstile human-verification page instead of "
                f"catalogue data for {url}. No data was scraped. If you have an "
                "authorized browser-assisted capture, import it with "
                "scripts/import_saved_html.py."
            )

    def _load_next_catalogue_page(self) -> bool:
        if self._catalogue_exhausted or not self._catalogue_next_url:
            self._catalogue_exhausted = True
            return False
        if self._catalogue_page_count >= self.max_catalogue_pages:
            self._catalogue_exhausted = True
            logger.warning(
                "Reached the Samsung catalogue page limit (%s)", self.max_catalogue_pages
            )
            return False

        page_url = self._catalogue_next_url
        if page_url in self._catalogue_visited_urls:
            self._catalogue_exhausted = True
            return False
        soup = self._get_soup(page_url)
        # Defense in depth: `_get_soup` checks HTTP responses, but test doubles
        # and alternate transports may return parsed challenge HTML directly.
        self._raise_if_challenge_page(soup, page_url)
        candidates = self._extract_catalogue_candidates(soup)
        if not candidates:
            raise ValueError(
                f"Samsung catalogue page contained no .makers phone links: {page_url}"
            )
        self._catalogue_candidates.extend(candidates)
        self._catalogue_visited_urls.add(page_url)
        self._catalogue_page_count += 1
        next_url = self._next_catalogue_page(soup, page_url)
        self._catalogue_next_url = next_url if next_url not in self._catalogue_visited_urls else None
        if self._catalogue_next_url is None:
            self._catalogue_exhausted = True
        logger.info(
            "Loaded Samsung catalogue page %s (%s handset links)",
            self._catalogue_page_count,
            len(candidates),
        )
        return True

    def _match_catalogue_model(self, model_name: str) -> tuple[str, str] | None:
        target = _clean_name(model_name)
        if not target:
            raise ValueError("Model name cannot be empty")
        exact = [
            candidate for candidate in self._catalogue_candidates
            if _clean_name(candidate[0]) == target
        ]
        unique = {url: label for label, url in exact}
        if len(unique) == 1:
            url, label = next(iter(unique.items()))
            return label, url
        if len(unique) > 1:
            raise LookupError(
                f"Multiple exact GSMArena catalogue entries matched {model_name!r}: "
                + ", ".join(unique.values())
            )
        return None

    @staticmethod
    def find_phone_url_in_html(html: str, model_name: str) -> tuple[str, str]:
        """Find the best exact Samsung model match in a GSMArena search page.

        This method is shared by the Requests and Selenium transports so the
        result-selection rules are identical regardless of how the HTML was
        obtained. It also supports the mobile subdomain returned by GSMArena.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if "turnstile" in page_title.casefold() or soup.select_one(
            'input[name="cf-turnstile-response"], .cf-turnstile, iframe[src*="challenges.cloudflare.com"]'
        ):
            raise RuntimeError(
                "GSMArena returned a Cloudflare Turnstile human-verification page instead of search results. "
                "Use the visible Selenium browser workflow and complete the check yourself; "
                "the browser-assisted saved-page importer (scripts/import_saved_html.py) remains available as a last-resort fallback."
            )

        candidates: list[tuple[int, str, str]] = []
        # Desktop and mobile result pages both expose model links, but wrappers
        # can differ. The URL and Samsung-name checks below keep this broad scan safe.
        anchors = soup.select(".makers a[href], .maker-list a[href], a[href]")
        normalized_query = _clean_name(model_name)
        for anchor in anchors:
            label = " ".join(anchor.stripped_strings)
            if not label:
                image = anchor.select_one("img[alt]")
                label = image.get("alt", "").strip() if image else ""
            href = anchor.get("href")
            if not href or not label:
                continue
            full_url = urljoin(BASE_URL + "/", href)
            parsed_url = urlparse(full_url)
            if parsed_url.scheme != "https" or parsed_url.hostname not in {
                "gsmarena.com", "www.gsmarena.com", "m.gsmarena.com"
            }:
                continue
            if not re.search(r"-\d+\.php$", parsed_url.path):
                continue
            if "samsung" not in label.casefold() and "galaxy" not in label.casefold():
                continue

            normalized_label = _clean_name(label)
            score = 100 if normalized_label == normalized_query else 0
            if normalized_query and normalized_query in normalized_label:
                score += 30
            candidates.append((score, label, full_url))

        if not candidates:
            raise LookupError(f"No Samsung phone result found on GSMArena for '{model_name}'.")
        candidates.sort(key=lambda item: (item[0], -len(_clean_name(item[1]))), reverse=True)
        best_score = candidates[0][0]
        best = [candidate for candidate in candidates if candidate[0] == best_score]
        if best_score < 30:
            raise LookupError(f"No sufficiently close GSMArena result found for '{model_name}'.")
        unique_urls = {candidate[2] for candidate in best}
        if len(unique_urls) > 1:
            names = ", ".join(candidate[1] for candidate in best[:4])
            raise LookupError(
                f"Ambiguous GSMArena results for '{model_name}': {names}. Specify the exact model name."
            )
        _, label, url = best[0]
        return label, url

    def find_phone_url(self, model_name: str) -> tuple[str, str]:
        """Find a Samsung model by crawling the public Samsung manufacturer index.

        The quick-search endpoint is deliberately not used: the user's live
        diagnostics showed it returns Turnstile while both the manufacturer
        catalogue and direct specification URLs are accessible. This crawler
        follows the catalogue's Next link and matches exact model variants.
        """
        match = self._match_catalogue_model(model_name)
        while match is None and not self._catalogue_exhausted:
            if not self._load_next_catalogue_page():
                break
            match = self._match_catalogue_model(model_name)
        if match is not None:
            return match

        target = _clean_name(model_name)
        partials = [
            label for label, _url in self._catalogue_candidates
            if target in _clean_name(label) or _clean_name(label) in target
        ]
        if len(partials) > 1:
            raise LookupError(
                f"Ambiguous partial GSMArena catalogue matches for {model_name!r}; nearby entries: "
                + ", ".join(partials[:6])
            )
        pages = self._catalogue_page_count
        raise LookupError(
            f"Samsung model {model_name!r} was not found after scanning {pages} "
            f"GSMArena catalogue page(s). Check the model name or increase --max-catalogue-pages."
        )

    @staticmethod
    def _extract_price_observations(soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract source-attributed GSMArena affiliate price offers when present.

        Prices are not treated as local Bangladesh retail quotes. Each offer
        retains its currency, storage variant and merchant host in the source.
        """
        symbols = {"$": "USD", "€": "EUR", "£": "GBP", "৳": "BDT", "₹": "INR", "¥": "JPY"}
        observations: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in soup.select("table.pricing.inline.widget tbody tr"):
            cells = row.find_all("td", recursive=False)
            variant = cells[0].get_text(" ", strip=True) if cells else "storage variant not specified"
            for anchor in row.select("a[href]"):
                text = anchor.get_text(" ", strip=True).replace("\u2009", " ").replace("\u00a0", " ")
                match = re.search(r"([$€£৳₹¥])\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", text)
                if not match:
                    continue
                currency = symbols[match.group(1)]
                amount = float(match.group(2).replace(",", ""))
                merchant_host = urlparse(anchor.get("href", "")).hostname or "merchant not identified"
                source = f"GSMArena affiliate offer | {variant} | {merchant_host}"[:180]
                key = (currency, source)
                if key in seen:
                    continue
                seen.add(key)
                observations.append({"amount": amount, "currency": currency, "source": source})
        return observations

    @staticmethod
    def _parse_spec_sections(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
        """Parse GSMArena specification tables, including row-spanned headings.

        Current GSMArena detail pages identify a section with a ``th`` carrying
        ``scope="row"`` and ``rowspan`` (for example ``Display`` or ``Battery``).
        Older/alternate markup uses a ``tr.ttl th[colspan]`` heading. Both forms
        are supported so a whole phone's specifications are not collapsed into
        a single ``General`` section.
        """
        specs_container = soup.select_one("#specs-list")
        if specs_container is None:
            return {}

        raw: dict[str, dict[str, str]] = {}
        for table in specs_container.find_all("table"):
            heading = table.select_one('th[scope="row"]')
            if heading is None:
                heading = table.select_one("tr.ttl th[colspan], tr.ttl th")
            if heading is None:
                heading = table.select_one("th[colspan]")

            section = heading.get_text(" ", strip=True) if heading else "General"
            if not section:
                section = "General"

            last_label: str | None = None
            for row in table.find_all("tr"):
                label_node = row.select_one("td.ttl")
                value_node = row.select_one("td.nfo")
                if value_node is None:
                    continue

                # Preserve <br>-separated modules/modes while keeping inline
                # markup (superscripts, links, symbols) as normal text.
                value = _cell_text(value_node)
                if not value:
                    continue

                label = label_node.get_text(" ", strip=True) if label_node else ""
                if label and label.replace(" ", "").strip():
                    label = re.sub(r"\s+", " ", label).strip()
                    raw.setdefault(section, {})[label] = value
                    last_label = label
                elif last_label:
                    # GSMArena sometimes puts continuation text on a row whose
                    # label cell is intentionally blank (e.g. regional bands).
                    current = raw.setdefault(section, {}).get(last_label, "")
                    if value not in current:
                        raw[section][last_label] = f"{current} | {value}" if current else value
        return raw

    @classmethod
    def parse_detail_html(
        cls,
        html: str,
        *,
        source_url: str | None = None,
        expected_model: str | None = None,
    ) -> ScrapedPhone:
        """Parse a saved GSMArena detail page without making network requests.

        This supports a browser-assisted workflow when GSMArena presents a
        human-verification page to automated HTTP clients. The supplied HTML
        must be the actual public phone specification page; the parser validates
        its title, canonical URL and specification-table structure.
        """
        soup = BeautifulSoup(html, "html.parser")
        title = soup.select_one("h1.specs-phone-name-title")
        if title is None:
            page_title = soup.title.get_text(" ", strip=True) if soup.title else "unknown page"
            if "turnstile" in page_title.casefold() or "check" in page_title.casefold():
                raise ValueError("The saved file is a human-verification page, not a phone specification page.")
            raise ValueError("The saved HTML does not contain a GSMArena phone title.")

        name = title.get_text(" ", strip=True)
        if "samsung" not in name.casefold():
            raise ValueError(f"Expected a Samsung phone specification page, received: {name!r}.")
        if expected_model and _clean_name(expected_model) not in _clean_name(name):
            raise ValueError(f"Saved page is for {name!r}, not the requested model {expected_model!r}.")

        canonical = soup.select_one('link[rel="canonical"]')
        canonical_url = canonical.get("href", "").strip() if canonical else ""
        resolved_source_url = canonical_url or source_url
        if not resolved_source_url:
            raise ValueError("No source URL supplied and no canonical GSMArena URL found in the page.")
        parsed_url = urlparse(resolved_source_url)
        if parsed_url.scheme != "https" or parsed_url.hostname not in {"gsmarena.com", "www.gsmarena.com", "m.gsmarena.com"}:
            raise ValueError("Source URL must be an HTTPS GSMArena phone page.")
        if not re.search(r"-\d+\.php$", parsed_url.path):
            raise ValueError("Source URL does not look like a GSMArena phone specification page.")
        if canonical_url and source_url:
            canonical_parsed = urlparse(canonical_url)
            if canonical_parsed.hostname not in {"gsmarena.com", "www.gsmarena.com", "m.gsmarena.com"}:
                raise ValueError("The page's canonical URL does not belong to GSMArena.")
            if canonical_parsed.path != parsed_url.path:
                raise ValueError("The supplied source URL does not match the page's canonical phone URL.")

        raw = cls._parse_spec_sections(soup)
        row_count = sum(len(fields) for fields in raw.values())
        if len(raw) < 3 or row_count < 5:
            raise ValueError(
                f"The phone page did not contain enough specification data ({len(raw)} sections, {row_count} rows; minimum is 3 sections and 5 rows)."
            )

        # Current detail pages already contain GSMArena's measured 'Our Tests'
        # section, including active-use score and endurance rating.
        has_test_rows = any("test" in section.casefold() for section in raw)
        return ScrapedPhone(
            name=name,
            source_url=resolved_source_url,
            raw_specs=raw,
            normalized=normalize_specs(raw),
            test_source_url=resolved_source_url if has_test_rows else None,
            price_observations=cls._extract_price_observations(soup),
        )

    def scrape_detail(self, model_name: str) -> ScrapedPhone:
        result_name, url = self.find_phone_url(model_name)
        soup = self._get_soup(url)
        result = self.parse_detail_html(str(soup), source_url=url, expected_model=model_name)

        # Older GSMArena pages may omit the test rows from the detail page.
        # Fetch the comparison view only in that case, keeping request volume
        # and the chance of hitting verification pages as low as possible.
        if result.test_source_url is None:
            phone_id_match = re.search(r"-(\d+)\.php$", urlparse(url).path)
            if phone_id_match:
                comparison_url = f"{BASE_URL}/compare.php3?idPhone1={phone_id_match.group(1)}"
                try:
                    comparison_soup = self._get_soup(comparison_url)
                    comparison_sections = self._parse_spec_sections(comparison_soup)
                    test_sections = {
                        section: values
                        for section, values in comparison_sections.items()
                        if "test" in section.casefold()
                    }
                    if test_sections:
                        result.raw_specs.update(test_sections)
                        result.normalized = normalize_specs(result.raw_specs)
                        result.test_source_url = comparison_url
                except (requests.RequestException, ValueError) as exc:
                    logger.warning("Could not fetch GSMArena test data for %s: %s", result.name, exc)

        return result

    def close(self) -> None:
        self.session.close()


def default_models() -> list[str]:
    return [item["name"].replace("Samsung ", "") for item in DEMO_PHONES]


def scrape_default_catalog() -> list[ScrapedPhone]:
    scraper = GSMArenaScraper()
    results: list[ScrapedPhone] = []
    try:
        for model in default_models()[: settings.scraper_max_models_per_run]:
            results.append(scraper.scrape_detail(model))
    finally:
        scraper.close()
    return results
