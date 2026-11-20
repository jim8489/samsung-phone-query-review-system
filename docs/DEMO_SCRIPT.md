# Suggested 5–10 minute project demonstration

Use the actual modes and results returned by the running project. Do not describe the default crawler as Selenium-based: the verified command-line collection path uses Requests + BeautifulSoup.

## 0:00–0:40 — Introduce the project

Explain that the system combines catalogue-driven GSMArena scraping, BeautifulSoup specification parsing, SQLAlchemy storage, BM25 retrieval, an Ollama open-source LLM, LangChain specialist agents, and FastAPI.

## 0:40–2:00 — Demonstrate automated GSMArena collection

Show the command `python scripts/scrape_phones.py --delay 3`. Explain that the crawler starts from the public Samsung manufacturer catalogue, follows catalogue pagination, discovers direct phone specification URLs, and parses those pages with BeautifulSoup. It commits each successfully parsed phone to the configured database with its source URL and collection timestamp. Show the successful 12-model summary and run `python scripts/verify_scraped_catalog.py --minimum 10 --maximum 15`. Mention that Turnstile pages are detected and not bypassed.

## 2:00–3:00 — Show PostgreSQL and the API

Run `python scripts/check_database.py` and show the PostgreSQL connection and row counts. Open `/docs` and demonstrate phone list/detail, comparison, price, chat, and review endpoints.

## 3:00–4:30 — Demonstrate RAG with Ollama

Show `ollama list` and `/api/llm`, then run `python scripts/verify_ollama_rag.py`. Ask: “What are the camera specifications of the Samsung Galaxy S23?” Explain that BM25 retrieves database evidence before Ollama generates an answer. Show `mode=ollama_rag` and source URLs. Follow with S23 vs S22 performance and a measured battery-life question.

## 4:30–6:15 — Demonstrate LangChain agents

Call `POST /api/reviews/samsung-galaxy-s23`. Explain the sequential workflow: the Specification Retrieval Agent invokes a SQL/BM25 tool and passes evidence to the Product Review Agent; the Product Review Agent retrieves the detailed phone record and produces a balanced review. Show `generation_mode=langchain_multi_agent` and `/api/agents`.

## 6:15–7:15 — Show data quality and price evidence

Point out source-attributed price observations, currency, merchant/variant data where available, and observation timestamps. Explain that GSMArena affiliate offers are not guaranteed Bangladesh retailer prices. Show that battery capacity (mAh), active-use score, and endurance rating are different fields.

## 7:15–8:00 — Close

Show `pytest -q`, explain the SQLite/PostgreSQL support, and summarize the four assessment workstreams. Do not claim a live scrape, Ollama generation, LangChain review, or PostgreSQL connection unless the corresponding local checks passed during the demonstration.
