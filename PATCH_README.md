# v2 Incremental Fix: Catalogue Turnstile Regression

This is a one-file overlay fix for the existing Samsung Phone Assistant v2 project.

## What failed

The old `test_search_reports_turnstile_instead_of_misleading_no_result` test replaces
`GSMArenaScraper._get_soup()` with a test double that returns parsed HTML directly.
The HTTP method normally detects Cloudflare Turnstile pages, but the catalogue
crawler boundary did not repeat that validation. As a result, the mocked challenge
HTML was interpreted as a catalogue page with no `.makers` links and raised a
misleading `ValueError`.

## What this patch changes

- Adds a defensive challenge-page check at the catalogue-page parsing boundary.
- Raises the existing `GSMArenaChallengeError` (a `RuntimeError` subclass) with a
  clear message identifying Turnstile human verification.
- Keeps the message compatible with the existing regression test and points to
  the saved-HTML importer as an authorized fallback.
- Does not change scraping strategy, database models, configuration, dependencies,
  or catalogue parsing behavior for normal pages.

## Apply to the existing v2 project

From the project root, extract this ZIP and allow `app/scraper/gsmarena.py` to be
replaced. No reinstall, dependency installation, environment change, or database
migration is required.

Then run:

```bash
pytest -q tests/test_scraper.py::test_search_reports_turnstile_instead_of_misleading_no_result
pytest -q
```

The full assembled v2 regression suite passed 48 tests after this change.
