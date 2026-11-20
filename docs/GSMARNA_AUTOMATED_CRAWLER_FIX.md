# Automated GSMArena crawler fix (incremental v2 patch)

## What the diagnostics established

The machine running the application successfully fetched all three URLs using Requests and a Chrome 157 User-Agent:

- `https://www.gsmarena.com/` — HTTP 200
- `https://www.gsmarena.com/samsung-phones-9.php` — HTTP 200, title `All Samsung phones`, 50 `.makers a` phone links
- `https://www.gsmarena.com/samsung_galaxy_s23-12082.php` — HTTP 200, actual phone specifications page

The quick-search endpoint `results.php3?sQuickSearch=yes...` returned the Turnstile page in earlier diagnostics. The scraper no longer uses that endpoint.

## New automated flow

1. Requests fetches the public Samsung manufacturer catalogue at `samsung-phones-9.php`.
2. BeautifulSoup extracts handset names and detail URLs from `.makers a`.
3. If a target model is not on the current page, the crawler follows GSMArena's explicit `a.pages-next` link, up to 30 pages by default.
4. Model matching is exact after normalization: the optional `5G` suffix is ignored, while `Plus`, `Ultra`, `FE`, `Fold`, and `Flip` remain meaningful. This prevents a base model query from selecting an Ultra/FE variant.
5. Requests fetches the direct detail URL. BeautifulSoup uses the existing section-aware parser to extract the entire `#specs-list`, battery test rows, and price offers.
6. SQLAlchemy upserts each successful phone immediately. Re-running the command refreshes the existing record rather than creating duplicate spec rows.

This is automated collection; it does not require opening Chrome or saving individual HTML files. It uses Requests + BeautifulSoup, both already part of the existing v2 stack. The PDF lists BeautifulSoup, Scrapy and Selenium as scraping technology options; it does not require all three.

## Run it

From the existing project root, with its existing `.venv` activated:

```bash
python scripts/scrape_phones.py --delay 3
```

The CLI defaults to the Chrome 157 User-Agent from the successful connectivity test. To supply a different User-Agent explicitly:

```bash
python scripts/scrape_phones.py --delay 3 --user-agent 'YOUR_USER_AGENT'
```

To collect a single test model:

```bash
python scripts/scrape_phones.py --models 'Galaxy S21' --delay 3
```

To increase the catalogue pagination limit if an older model is not found within the default 30 pages:

```bash
python scripts/scrape_phones.py --delay 3 --max-catalogue-pages 45
```

Verify the assessment's 10–15 record target:

```bash
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
```

## Important behavior

- Minimum request delay is 2 seconds; use 3 seconds as shown.
- The script uses the manufacturer index and direct detail URLs. It does not call the Turnstile-triggering quick-search endpoint.
- If the manufacturer catalogue or a detail page starts returning a Turnstile challenge, the scraper raises `GSMArenaChallengeError` with the affected URL. It does not misreport the challenge as an empty result or try to bypass it.
- Every successful phone is committed independently. One failed model does not discard earlier imports.
- The pre-existing S23 entry is safe to scrape again because the upsert is idempotent.
- No `.env`, `.venv`, database, user HTML file, Chrome profile, or other project data is included in this patch.

## Scope of verification

The added regression tests verify catalogue-link extraction, pagination, exact variant matching, no use of the quick-search endpoint, challenge-page detection, and host restrictions. The parser was also run against the actual S23 HTML supplied in this conversation and extracted 14 sections, 50 specification rows, the Snapdragon 8 Gen 2 chipset, 3900 mAh battery, 11:27h active-use score, 101h endurance rating, and five price offers.

The live network request was verified by the user's Mac diagnostics. This patch's automated 12-model run still must be executed on that Mac to establish the final 10–15-record count; this build environment cannot resolve GSMArena.
