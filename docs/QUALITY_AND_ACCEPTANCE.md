# Quality and acceptance handoff

This file distinguishes automated tests from live external-service demonstrations. A passing unit-test suite does not prove that the current network can scrape GSMArena or that the user's local Ollama/PostgreSQL services are running.

## Delivered implementation

- GSMArena collection: visible Selenium/Chrome navigation + BeautifulSoup detail-page parsing, human-in-the-loop Turnstile pause, polite delay, page provenance, raw specification rows, GSMArena measured tests and source-attributed price observations.
- Catalogue persistence: SQLAlchemy phone, specification, price and chat tables; safe idempotent upsert for repeat scrapes; SQLite by default; PostgreSQL driver/Compose support and non-destructive migration CLI.
- Chatbot: BM25 retrieval over normalized phone fields and detailed specification rows, followed by optional local Ollama generation using retrieved evidence. The deterministic response remains available when Ollama is off.
- Multi-agent: LangChain `create_agent` specification-retrieval tool agent -> review-generation tool agent, backed by local Ollama. The API reports `langchain_multi_agent` only when that path succeeds.
- FastAPI: phone list/detail, comparisons, measured battery ranking, price observations, RAG chat, product reviews, scraper endpoint, system health, Ollama status and agent status; Swagger at `/docs`.

## Automated checks

Run from the project root with the existing venv:

```bash
pytest -q
python -m compileall -q app scripts tests
node --check app/static/app.js
```

The test suite covers HTML section parsing and normalization, search-result matching, browser navigation via a fake Selenium driver, human-verification pause/resume, price extraction, idempotent specification/price upserts, BM25 retrieval, RAG fallback and mocked Ollama calls, two-agent handoff, safe database migration and API behavior.

## External acceptance gates (must be run on the Mac)

### A. Live GSMArena catalogue

```bash
python scripts/scrape_phones.py --delay 3
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
```

The build environment cannot operate your Mac's visible Chrome session. The browser scraper unit tests are mocked; they do not claim that a live crawl happened. Complete any human verification directly in the Chrome window and press Enter in the scraper Terminal. The verifier requires 10–15 records marked as scraped, source URL + timestamp, at least four sections and at least 15 rows per record.

### B. Actual Ollama-backed RAG

Install Ollama, pull the configured model, set `LLM_PROVIDER=ollama`, and restart the API. Run:

```bash
python scripts/verify_ollama_rag.py
```

The acceptance condition is `Generation mode: ollama_rag` and `[PASS]`. A `rag_fallback` response is not an LLM demonstration.

### C. Actual LangChain multi-agent review

With the LangChain dependencies installed and Ollama/model available, call:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/reviews/samsung-galaxy-s23 \
  -H 'Content-Type: application/json' -d '{"include_limitations": true}'
```

The response must contain `generation_mode: langchain_multi_agent`. `/api/agents` reports the configured framework and roles. If the route falls back to another generation mode, do not describe that run as LangChain multi-agent generation.

### D. PostgreSQL migration

Docker/PostgreSQL is not available in the build container. The included migration has SQLite-to-SQLite automated tests, including a non-empty-target safety test, but a live PostgreSQL deployment must be checked locally:

```bash
docker compose up -d db
python scripts/migrate_database.py --source sqlite:///./data/samsung_phones.db \
  --target 'postgresql+psycopg://samsung_app:YOUR_PASSWORD@localhost:5432/samsung_phones'
```

Change `.env` `DATABASE_URL` to the PostgreSQL URL only after the migration succeeds, restart Uvicorn, and run `python scripts/check_database.py`. It must report PostgreSQL and the expected row counts. Keep the original SQLite DB as rollback backup.

## Data correctness notes

- Demo seed rows remain marked `demo_seed`; they do not count toward the 10–15 scraped phone target.
- The S23 HTML supplied during development parsed as 14 sections and 50 rows, including 6.1-inch display, Snapdragon 8 Gen 2, 3900 mAh, active-use score 11h 27m and endurance rating 101h. This is an HTML fixture parse, not a live browser scrape performed by the build environment.
- Battery capacity is not measured battery life. Best-battery ranking prefers active-use score/endurance test values and explicitly warns when only mAh is available.
- Scraped affiliate offers are currency/variant/merchant attributed and timestamped. They are not assumed to be current Bangladesh retailer prices.
- The live browser scraper does not solve or bypass Cloudflare Turnstile. It pauses for the user to complete a human check in the visible browser.
