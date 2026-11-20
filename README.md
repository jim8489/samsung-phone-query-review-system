# Samsung Phone Query & Review System

A FastAPI web application for collecting, exploring, comparing, and reviewing Samsung smartphones. The project combines a catalogue-driven GSMArena crawler, BeautifulSoup extraction, SQLAlchemy persistence, BM25 retrieval-augmented generation (RAG), a local Ollama model, a LangChain two-agent review workflow, and a browser-based interface.

> **Current implementation note:** The verified command-line crawler uses **Requests + BeautifulSoup** to discover Samsung models from GSMArena's manufacturer catalogue and fetch their direct specification pages. Selenium is not used by the default, verified scraping command. The project may contain optional browser automation code, but the successful 12-model collection described below was performed by the HTTP/BeautifulSoup crawler.

## Features

- **Catalogue-driven GSMArena scraping:** Starts from the Samsung manufacturer catalogue, follows catalogue pagination, selects exact model links, fetches each phone's specification page, detects human-verification pages, and stops rather than treating a challenge page as phone data.
- **Structured specifications:** Preserves specification sections and rows, while normalizing important fields such as display size/resolution, rear and front cameras, chipset, memory, battery capacity, charging, measured active-use score, and endurance rating.
- **Price observations:** Stores dated price observations with currency and source/merchant metadata when that information is available on the source page. Affiliate prices are reference observations, not guaranteed local retail prices.
- **SQLAlchemy database:** Supports SQLite for simple local setup and PostgreSQL for the assessment deployment. A non-destructive migration script copies the existing SQLite data into an empty PostgreSQL database.
- **RAG chatbot:** Uses BM25 lexical retrieval across normalized phone fields and stored specification rows, then uses Ollama to generate a response grounded in the retrieved records. The API identifies whether an answer used Ollama or the deterministic fallback.
- **Open-source local LLM:** Tested with Ollama and `qwen2.5:3b`; no hosted model API key is required.
- **LangChain multi-agent reviews:** A Specification Retrieval Agent queries the database and passes evidence to a Product Review Agent, which retrieves the phone's evidence and generates a balanced, source-grounded review.
- **FastAPI and web interface:** Provides a responsive browser UI, REST endpoints, and interactive Swagger documentation.
- **Automated tests and CI:** Includes an isolated test database, scraper/parser tests, API tests, agent workflow tests, and a GitHub Actions workflow.

## Technology stack

| Area | Technology |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI, Uvicorn, Pydantic |
| Scraping | Requests, BeautifulSoup 4 |
| Database / ORM | SQLAlchemy 2.x, SQLite, PostgreSQL 16 |
| Retrieval | BM25 lexical retrieval over database records |
| LLM | Ollama (`qwen2.5:3b`) |
| Agent orchestration | LangChain `create_agent` and `langchain-ollama` |
| Frontend | HTML, CSS, JavaScript |
| Tests / CI | pytest, GitHub Actions, Node syntax check |
| Containers | Docker Compose for PostgreSQL |

## Architecture

```text
GSMArena Samsung catalogue
          |
          v
Requests crawler ---- catalogue pagination / exact model links
          |
          v
BeautifulSoup parser ---- raw sections + normalized fields + price/test evidence
          |
          v
SQLAlchemy upsert ---- SQLite or PostgreSQL
          |
          +-------------------------------+
          |                               |
          v                               v
BM25 retrieval                    Phone / price / compare APIs
          |
          v
Ollama Qwen2.5 3B
          |
          +---- RAG chatbot response with source records
          |
          +---- LangChain Specification Agent
                         |
                         v
                LangChain Product Review Agent
                         |
                         v
                 Source-grounded review

FastAPI serves the API, Swagger docs, and browser UI.
```

## Verified project status

The maintainer's local run (20 November 2026) completed the following checks:

- **12/12 Samsung models scraped successfully** from GSMArena, with zero failed models.
- **12 live records** passed `scripts/verify_scraped_catalog.py` with source URLs and collection timestamps.
- The PostgreSQL 16 database check reported **12 phones, 593 specification rows, and 58 price observations**.
- The local test suite reported **48 passing tests**.
- `scripts/verify_ollama_rag.py` returned `Generation mode: ollama_rag` using Qwen2.5 3B and retrieved Galaxy S23 evidence.
- The review endpoint returned `generation_mode: langchain_multi_agent` for the Galaxy S23.

These are the results from the maintainer's tested environment. The live database, local Ollama model, and scraped records are not committed to this repository; a fresh clone must run the setup and data-collection steps below.

## Requirements

- Python 3.11 or newer
- Internet access to retrieve public GSMArena catalogue and phone pages
- Ollama for local LLM generation and LangChain reviews
- Docker Desktop + Docker Compose if you want to run PostgreSQL
- Node.js only for the frontend JavaScript syntax check during development

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/jim8489/samsung-phone-query-review-system.git
cd samsung-phone-query-review-system

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-addons.txt
```

On Windows, activate the virtual environment with `.venv\\Scripts\\activate`.

### 2. Configure the environment

```bash
cp .env.example .env
```

Update the relevant settings in `.env` (do not commit this file):

```dotenv
DATABASE_URL=sqlite:///./data/samsung_phones.db
SEED_DEMO_DATA=true
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
AGENT_FRAMEWORK=langchain
SCRAPER_DELAY_SECONDS=3
```

`SEED_DEMO_DATA=true` inserts a small starter catalogue into a new/empty database. Successfully scraped records are labelled `scraped`; starter records are labelled `demo_seed`. After migrating a populated SQLite database to PostgreSQL, set `SEED_DEMO_DATA=false` to avoid inserting starter data during startup.

### 3. Start Ollama

Install Ollama from <https://ollama.com/download>, launch it, and download the model:

```bash
ollama pull qwen2.5:3b
ollama list
```

Check that the local model is available:

```bash
curl http://localhost:11434/api/tags
```

### 4. Start the API and web application

```bash
uvicorn app.main:app --reload
```

Open:

- Web application: <http://127.0.0.1:8000>
- Swagger API documentation: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/api/health>
- LLM status: <http://127.0.0.1:8000/api/llm>
- Agent status: <http://127.0.0.1:8000/api/agents>

## Collect 10–15 Samsung phones from GSMArena

The default command uses the **Requests + BeautifulSoup catalogue crawler**. It does not use the GSMArena quick-search endpoint and does not require Selenium to run the verified path.

```bash
python scripts/scrape_phones.py --delay 3
```

The default target list contains 12 models:

1. Galaxy S21
2. Galaxy S21+
3. Galaxy S21 Ultra
4. Galaxy S22
5. Galaxy S22 Ultra
6. Galaxy S23
7. Galaxy S23+
8. Galaxy S23 Ultra
9. Galaxy S24
10. Galaxy S24+
11. Galaxy S24 Ultra
12. Galaxy S24 FE

The crawler starts at `https://www.gsmarena.com/samsung-phones-9.php`, follows the catalogue's next-page links as needed, matches the requested handset, and fetches the direct specification URL. It parses the page with BeautifulSoup and saves each successful phone immediately through the SQLAlchemy upsert service. A minimum delay of two seconds is enforced; three seconds is the recommended setting.

To scrape selected models:

```bash
python scripts/scrape_phones.py --models "Galaxy S23" "Galaxy S24 Ultra" --delay 3
```

Verify the assessment target (10–15 live records):

```bash
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
```

A record counts only when it is marked `data_quality='scraped'` and has a GSMArena source URL, a collection timestamp, at least four specification sections, and at least 15 specification rows. Demo seed records do not count. The crawler detects Turnstile/human-verification HTML and stops with an explicit error; it does not attempt to bypass website access controls. Availability can vary by network, request rate, or the source website's access policy.

## Use the RAG chatbot

The chatbot retrieves phone evidence from the configured database before asking Ollama to generate an answer. Confirm the LLM mode:

```bash
python scripts/verify_ollama_rag.py \
  --query "What are the rear camera specifications of the Samsung Galaxy S23?"
```

A successful model-backed result reports `Generation mode: ollama_rag`. If it reports a fallback mode, the answer was not generated by Ollama.

Example API request (the `session_id` can be reused across turns):

```bash
curl -sS -X POST http://127.0.0.1:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"What are the rear camera specifications of the Samsung Galaxy S23?","session_id":"demo-session-001"}'
```

The three assessment-style questions to demonstrate are:

- What are the camera specifications of the Samsung Galaxy S23?
- Which Samsung phone has the best battery life?
- How does the Galaxy S23 compare to the Galaxy S22 in terms of performance?

Battery capacity (mAh), GSMArena active-use score, and GSMArena endurance rating are distinct measurements. The application ranks by measured data when available and identifies capacity as a proxy if measured tests are missing.

## Generate a LangChain multi-agent review

The review workflow uses two LangChain `create_agent` agents:

1. **Specification Retrieval Agent** — calls a database-backed BM25/SQL tool and returns phone facts with source evidence.
2. **Product Review Agent** — receives the first agent's evidence, calls a second database evidence tool, and generates a balanced review.

Check agent configuration:

```bash
curl http://127.0.0.1:8000/api/agents
```

Generate a Galaxy S23 review:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/reviews/samsung-galaxy-s23 \
  -H 'Content-Type: application/json' \
  -d '{"include_limitations":true}'
```

A successful framework-backed response reports `generation_mode: langchain_multi_agent`. Other modes indicate that the endpoint used a single-model or deterministic fallback; report the mode accurately in a demonstration.

## PostgreSQL setup and SQLite migration

SQLite is the default for a quick local run. To use PostgreSQL, the project includes a PostgreSQL 16 Docker Compose service and a non-destructive migration script.

1. Start Docker Desktop.
2. Set a private URL-safe password and host port in `.env`. Use `5433` if port `5432` is already occupied on your machine:

   ```dotenv
   POSTGRES_PASSWORD=YOUR_PRIVATE_LOCAL_PASSWORD
   POSTGRES_PORT=5433
   ```

3. Back up the SQLite source and start PostgreSQL:

   ```bash
   cp data/samsung_phones.db data/samsung_phones_backup.db
   docker compose up -d db
   docker compose ps
   ```

   Wait until the database reports `healthy`.

4. Migrate the existing records into the empty PostgreSQL database. Replace the password and host port with the values you configured:

   ```bash
   python scripts/migrate_database.py \
     --source "sqlite:///./data/samsung_phones.db" \
     --target "postgresql+psycopg://samsung_app:YOUR_PRIVATE_LOCAL_PASSWORD@127.0.0.1:5433/samsung_phones"
   ```

5. After migration succeeds, change `DATABASE_URL` in `.env` to the same PostgreSQL URL and set `SEED_DEMO_DATA=false`. Restart Uvicorn and verify:

   ```bash
   python scripts/check_database.py
   curl http://127.0.0.1:8000/api/health
   ```

The migration refuses to copy into a target that already contains project data and does not modify the SQLite source. Keep the SQLite backup as a rollback copy. See `docs/POSTGRESQL_UPGRADE.md` for additional details.

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Service and database health |
| `GET` | `/api/llm` | Ollama reachability and model availability |
| `GET` | `/api/agents` | Agent framework and roles |
| `GET` | `/api/phones` | List/search phone records |
| `GET` | `/api/phones/{slug}` | Phone detail and specifications |
| `GET` | `/api/phones/compare?slugs={slug1},{slug2}` | Compare 2–4 phones |
| `GET` | `/api/phones/best-battery` | Rank measured battery results when available |
| `GET` | `/api/phones/{slug}/prices` | Dated price observations |
| `POST` | `/api/phones/{slug}/prices` | Add a price observation |
| `POST` | `/api/chat` | Ask the RAG chatbot (`query`, optional `session_id`) |
| `POST` | `/api/reviews/{slug}` | Generate a product review |
| `POST` | `/api/scraper/run` | Run the server-side Requests/BeautifulSoup scraper |

The interactive API schema is available at `/docs` while the server is running.

## Tests and quality checks

```bash
pip install -r requirements-dev.txt
pytest -q
python -m compileall -q app scripts tests
node --check app/static/app.js
python scripts/check_database.py
python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15
python scripts/verify_ollama_rag.py
```

The test suite isolates itself from a developer's `.env` database and uses an in-memory SQLite database. Tests for LangChain/browser boundaries use test doubles; they do not replace the live acceptance checks for GSMArena, Ollama, or PostgreSQL.

## Project structure

```text
app/
  agents/          # Specification, review, and LangChain workflow
  api/routes/      # FastAPI routers
  data/            # Demo seed catalogue
  scraper/         # Requests/BeautifulSoup scraper and normalization
  services/        # Catalog persistence, BM25 retrieval, Ollama, chat
  static/          # Browser UI assets
  database.py      # SQLAlchemy engine, sessions, metadata
  models.py        # Phone, specification, price, and chat models
  schemas.py       # Pydantic request/response schemas
scripts/           # Scrape, migrate, verify, and database utilities
docs/              # Architecture, acceptance, migration, and demo guides
tests/             # Unit, API, parser, and integration-boundary tests
```

## Repository hygiene

- Never commit `.env`, database files, Chrome profiles, Ollama model files, or personal credentials.
- `.env.example` contains placeholders only; create a private `.env` locally.
- The live catalogue is generated locally and is intentionally excluded from Git.
- GSMArena data and affiliate prices should be attributed to their source and treated as observations at the time of collection.

## Assessment submission

The assessment asks for a GitHub repository, a **5–10 minute** demonstration video uploaded to Google Drive, and an email containing both links to **sd14@gtrbd.com**. The demonstration should show the verified scraper run, the database, an actual `ollama_rag` chatbot answer, a `langchain_multi_agent` review, and the FastAPI endpoints. Do not claim an external integration succeeded unless its corresponding acceptance command has passed.

## License

This project is distributed under the MIT License. See [LICENSE](LICENSE).
