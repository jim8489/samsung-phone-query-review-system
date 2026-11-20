# Incremental v2 upgrade instructions

This document applies to the project already running locally, including a SQLite database that contains the imported Samsung Galaxy S23 GSMArena record. The upgrade is an overlay; it is not a fresh install.

## 1. Preserve the existing installation

Keep the existing project folder, `.venv`, `.env`, and `data/samsung_phones.db`. Extract the incremental patch ZIP into the project root. Do not extract it into a new folder and do not replace the entire project with another full-project archive.

Activate the existing venv and install the optional packages:

```bash
source .venv/bin/activate
python -m pip install -r requirements-addons.txt
```

`requirements-addons.txt` installs only the optional PostgreSQL driver, Selenium, LangChain and the Ollama LangChain integration. It does not reinstall the base requirements or require deleting/recreating the environment.

## 2. Automated GSMArena scraping

The scraper's default transport is now visible Chrome controlled by Selenium. The browser uses a dedicated persistent profile at `data/chrome_profile_gsmarena`; this keeps site session state separate from your everyday Chrome profile. Selenium Manager resolves a compatible ChromeDriver when the browser starts.

Run:

```bash
python scripts/scrape_phones.py --delay 3
```

The default catalogue contains 12 targets from `app/data/seed.py`: Galaxy S21, S21+, S21 Ultra, S22, S22 Ultra, S23, S23+, S23 Ultra, S24, S24+, S24 Ultra and S24 FE. The already imported S23 will be refreshed in place. Each successful phone is committed immediately. If a model fails, the scraper continues with the remaining models unless `--stop-on-error` is supplied.

If Turnstile appears, the scraper detects the check and pauses. Complete it manually in the visible Chrome browser and press Enter in the same Terminal. This is a human-in-the-loop step only; the code does not solve, bypass or automate the challenge. Do not run the scraper in a background/non-interactive shell if a human check may appear.

Useful targeted run:

```bash
python scripts/scrape_phones.py --models "Galaxy S23 Ultra" "Galaxy S24 Ultra" --delay 3
```

Use the verifier after the full run:

```bash
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
```

A record counts as live only if it is marked `data_quality='scraped'`, has a canonical GSMArena source URL and scrape timestamp, and contains at least four specification sections and 15 specification rows. Demo seed records do not count.

## 3. Scraper limitations and respectful use

The Requests transport remains available for sites/pages that serve ordinary HTML, but your observed GSMArena search request returned the Cloudflare Turnstile page. Selenium is the default because Chrome works after your own browser verification. The scraper uses a minimum two-second delay and defaults to three seconds. It does not evade access restrictions. If GSMArena continues to deny automated access after normal human verification, stop and follow the site's terms rather than increasing request frequency or trying to defeat the challenge.

The BeautifulSoup parser handles GSMArena's row-spanned section headings and retains every parsed specification row. The current page's `Our Tests` section supplies active-use and endurance metrics; battery mAh is not used as a substitute for measured battery life. GSMArena affiliate price offers are stored as dated, currency-specific, merchant-attributed observations, not as Bangladesh local market prices.


## Swagger scraper and product-review reliability fix

The Swagger scraper route and CLI now share the same tested User-Agent resolver. The earlier mismatch caused the CLI to succeed while `/api/scraper/run` used the project placeholder User-Agent from `.env` and received a catalogue response without phone links. Project-branded placeholder values now resolve to the known-working browser User-Agent; explicit meaningful custom User-Agents remain supported.

LangChain review agents now have bounded graph recursion, bounded Ollama HTTP requests, and a maximum output-token setting. FastAPI uses the asynchronous agent invocation with an overall deadline. If LangChain/Ollama exceeds the deadline or errors, the endpoint returns the deterministic specification-based review instead of launching another unbounded Ollama fallback. The response reports `generation_mode=rule_based` in that case.

Configuration defaults: `AGENT_REQUEST_TIMEOUT_SECONDS=35`, `AGENT_TOTAL_TIMEOUT_SECONDS=90`, `AGENT_RECURSION_LIMIT=5`, and `AGENT_MAX_OUTPUT_TOKENS=384`.
