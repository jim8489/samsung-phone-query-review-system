# Suggested 5–10 minute project demonstration

## 0:00–0:40 — Introduce the project

Explain that the system combines Selenium browser automation, BeautifulSoup specification parsing, SQLAlchemy storage, BM25 retrieval, an Ollama open-source LLM, LangChain specialist agents and FastAPI.

## 0:40–2:00 — Demonstrate automated GSMArena collection

Show the live Chrome window and run `python scripts/scrape_phones.py --delay 3`. Explain that Selenium navigates search/specification pages and BeautifulSoup extracts the rows. If a human verification challenge appears, complete it normally. Show the scraper's success summary and run `python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15`. Point out source URLs, scrape timestamps, and the distinction between demo seed and scraped records.

## 2:00–3:00 — Show structured database and API

If PostgreSQL is configured, run `python scripts/check_database.py` and show the PostgreSQL connection and row counts. Otherwise be honest that SQLite is being used locally. Open `/docs`; show phone listing/detail, comparison, prices, chat and review endpoints.

## 3:00–4:30 — Demonstrate RAG with Ollama

Show `ollama list` and `/api/llm`, then run `python scripts/verify_ollama_rag.py`. Ask: “What are the camera specifications of the Samsung Galaxy S23?” Explain that BM25 retrieves the DB evidence before Ollama produces the answer. Show `mode=ollama_rag` and source URLs. Follow with S23 vs S22 performance and a battery-life question.

## 4:30–6:15 — Demonstrate LangChain agents

Call `POST /api/reviews/samsung-galaxy-s23`. Explain the flow: Specification Retrieval Agent invokes a SQL/BM25 tool and hands the evidence to Product Review Agent; Product Review Agent retrieves the full record and writes a detailed review with strengths, limitations and source grounding. Show `generation_mode=langchain_multi_agent` and `/api/agents`.

## 6:15–7:15 — Show quality and price evidence

Point out source-attributed price observations with currency, merchant, storage variant and observation timestamp. Explain that GSMArena affiliate offer prices are not Bangladesh retailer price guarantees. Show that battery capacity (mAh) and measured active-use/endurance tests are separate fields.

## 7:15–8:00 — Close

Show `pytest -q`, explain SQLite/PostgreSQL support, and summarize the four assessment workstreams. Do not claim live scraping, real Ollama generation, LangChain review or PostgreSQL deployment unless the corresponding local checks were actually run successfully.
