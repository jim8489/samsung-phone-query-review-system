# Samsung Phone Query & Review System

A FastAPI web application for Samsung smartphone research. It combines browser-based GSMArena collection, BeautifulSoup specification parsing, SQLAlchemy storage, BM25 retrieval-augmented generation (RAG), a local Ollama model, LangChain specialist agents and a browser UI.

## Features

- **Automated GSMArena scraper:** Selenium navigates GSMArena in a visible Chrome session; BeautifulSoup parses the search/detail HTML. If Cloudflare Turnstile appears, the scraper pauses for a person to complete verification in Chrome. It does not bypass human verification. Successful phone records are written straight to the configured database.
- **Structured data:** SQLAlchemy tables for phones, individual specification rows, dated price observations and chat history. SQLite is the default; PostgreSQL is supported, with a non-destructive migration script.
- **RAG chatbot:** BM25 retrieves relevant phone records and complete stored specification rows before the answer is generated. It covers camera, display, chipset/performance, features, price, comparisons and battery questions.
- **Open-source local LLM:** Ollama with a model such as `qwen2.5:3b`. The application retains a grounded fallback if Ollama is unavailable and reports which mode was used.
- **LangChain multi-agent review:** A Specification Retrieval Agent uses a database-backed BM25/SQL tool and passes its evidence to a Product Review Agent, which retrieves full evidence and generates a balanced, source-grounded review.
- **FastAPI + web UI:** Catalogue, compare, battery, price, chat, review, system-status and scraper endpoints, with Swagger documentation.

## Requirements

- Python 3.11 or newer
- Google Chrome for live browser scraping
- Internet access to access public GSMArena pages
- Ollama for an actual local-LLM demonstration
- Docker Desktop + Docker Compose for PostgreSQL (optional, but the assessment execution plan explicitly asks for PostgreSQL)

## Run the existing local project

For a fresh install, create a virtual environment, install core requirements, copy `.env.example` to `.env`, and start FastAPI:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

For the existing v2 installation, **do not recreate `.venv` or `.env`**. Apply the incremental upgrade ZIP to the existing project root, then install only the add-on requirements:

```bash
source .venv/bin/activate
python -m pip install -r requirements-addons.txt
```

Application URLs:

- Web application: <http://127.0.0.1:8000>
- Swagger: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>
- Ollama status: <http://127.0.0.1:8000/api/llm>
- Agent status: <http://127.0.0.1:8000/api/agents>

## Scrape 10–15 Samsung phones from GSMArena

Install the add-on requirements once:

```bash
python -m pip install -r requirements-addons.txt
```

Run the default 12-model catalogue from an interactive Terminal:

```bash
python scripts/scrape_phones.py --delay 3
```

Selenium opens a visible Chrome window and automatically searches for each model, opens its specification page, and sends the loaded page HTML to the existing BeautifulSoup parser. Successful records are upserted into the configured database immediately; no individual HTML files need to be saved. If Turnstile appears, complete the check yourself in Chrome and press Enter in the same Terminal. The browser session uses a dedicated profile under `data/chrome_profile_gsmarena`.

The default targets are Galaxy S21, S21+, S21 Ultra, S22, S22 Ultra, S23, S23+, S23 Ultra, S24, S24+, S24 Ultra and S24 FE. The existing S23 record is refreshed in place. The scraper continues after an individual model fails unless `--stop-on-error` is supplied.

Verify the PDF target:

```bash
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
```

A record counts only when it has `data_quality='scraped'`, a GSMArena source URL, a collection timestamp, at least four spec sections and at least 15 spec rows. Demo seed records do not count. The scraper enforces a minimum two-second delay (default three seconds) and never attempts to defeat Cloudflare or another access control. If GSMArena still restricts automated access after normal human verification, stop and follow the site's terms.

For selected models:

```bash
python scripts/scrape_phones.py --models "Galaxy S23 Ultra" "Galaxy S24 Ultra" --delay 3
```

## Enable the Ollama RAG chatbot

Install the Ollama macOS app from <https://ollama.com/download/mac>, open it, then run:

```bash
ollama pull qwen2.5:3b
ollama list
```

Add/update the following in your existing `.env` (do not overwrite unrelated settings):

```dotenv
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
AGENT_FRAMEWORK=langchain
```

Restart Uvicorn after changing `.env`, then check `http://127.0.0.1:8000/api/llm`. It should show the model as reachable and installed. Run a real RAG acceptance query:

```bash
python scripts/verify_ollama_rag.py --query "What are the rear camera specifications of the Samsung Galaxy S23?"
```

The check passes only when the chatbot response uses `mode=ollama_rag`; `rag_fallback` means Ollama was not used. Try the assessment's three questions in the web UI or through `POST /api/chat`: S23 camera specifications, best measured battery life, and S23 vs S22 performance. The assistant distinguishes battery capacity in mAh from GSMArena active-use/endurance tests.

## Demonstrate the LangChain multi-agent review

The patch uses LangChain's `create_agent` API and `ChatOllama`. The agents have different responsibilities:

1. **Specification Retrieval Agent:** calls a BM25/SQL database tool and returns technical facts plus source evidence.
2. **Product Review Agent:** receives the first agent's handoff, calls a second database evidence tool, and generates a balanced detailed review.

With Ollama running and the add-on requirements installed:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/reviews/samsung-galaxy-s23 \
  -H 'Content-Type: application/json' \
  -d '{"include_limitations": true}'
```

A successful framework-backed review reports `generation_mode=langchain_multi_agent`. If the service/model or packages are unavailable, the API remains functional and falls back; the generation mode makes that explicit. Inspect `/api/agents` for the configured framework and agent roles.

## PostgreSQL setup and safe migration

The current local database remains SQLite until you explicitly migrate it. The migration utility will not overwrite an existing target and never modifies the SQLite source.

1. Install/start Docker Desktop.
2. In `.env`, replace the `POSTGRES_PASSWORD` placeholder with a private URL-safe local password (letters/numbers recommended).
3. Start only PostgreSQL:

   ```bash
   docker compose up -d db
   docker compose ps
   ```

4. Migrate the current database into the empty PostgreSQL service:

   ```bash
   python scripts/migrate_database.py \
     --source sqlite:///./data/samsung_phones.db \
     --target 'postgresql+psycopg://samsung_app:YOUR_PASSWORD@localhost:5432/samsung_phones'
   ```

5. Only after migration succeeds, change `DATABASE_URL` in `.env` to the same PostgreSQL URL and set `SEED_DEMO_DATA=false`. Restart Uvicorn and run:

   ```bash
   python scripts/check_database.py
   ```

   It must report PostgreSQL and show the expected phone/specification/price counts. Keep the SQLite database as a rollback backup. Full details are in `docs/POSTGRESQL_UPGRADE.md`.

The Docker Compose API service is also configured for Postgres and points to Ollama on the Mac host via `host.docker.internal`. Run visible Selenium scraping on the Mac host rather than inside a headless API container.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Service/database health |
| GET | `/api/llm` | Ollama and model availability |
| GET | `/api/agents` | Agent framework and role status |
| GET | `/api/phones` | List/filter phone records |
| GET | `/api/phones/{slug}` | Full phone record and specs |
| GET | `/api/phones/compare?slugs={slug1},{slug2}` | Compare 2–4 phones |
| GET | `/api/phones/best-battery` | Rank by measured endurance where available |
| GET/POST | `/api/phones/{slug}/prices` | Read/add dated price observations |
| POST | `/api/chat` | RAG chatbot question |
| POST | `/api/reviews/{slug}` | Multi-agent or fallback product review |
| POST | `/api/scraper/run` | Direct HTTP scraper endpoint (GSMArena may present Turnstile; use the Selenium CLI above for browser-assisted collection) |

## Tests and verification

```bash
pip install -r requirements-dev.txt
pytest -q
python -m compileall -q app scripts tests
node --check app/static/app.js
```

The automated browser tests use a mock WebDriver; they verify navigation, parser integration and the human-verification pause, but they do not claim a live crawl. Live Chrome, Ollama generation and PostgreSQL deployment must be demonstrated on the machine where those services run.

## Project structure

```text
app/
  agents/       # custom agents and LangChain multi-agent workflow
  api/routes/   # FastAPI routers
  data/         # 12-model demo catalogue
  scraper/      # Requests fallback, Selenium browser and BeautifulSoup parser
  services/     # catalogue persistence, BM25 retrieval, Ollama and chat
  static/       # responsive web UI
scripts/        # scrape, verify, migrate, database and Ollama checks
docs/           # architecture, acceptance mapping, setup and demo guide
tests/          # unit, API and integration-boundary tests
```

## Assessment submission

The PDF requires a GitHub repository, a 5–10 minute demonstration video uploaded to Google Drive, and an email with both links to **sd14@gtrbd.com**. The video should demonstrate live scraping, actual Ollama-backed RAG, the LangChain two-agent review, PostgreSQL if deployed, and the API. Do not claim any external-service run as complete until its acceptance command passes. See `docs/V2_REVIEW_AND_FINAL_ACCEPTANCE.md` and `docs/DEMO_SCRIPT.md`.
