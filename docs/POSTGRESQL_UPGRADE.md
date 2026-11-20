# PostgreSQL setup and safe migration from the existing SQLite database

The project already supports SQLite and PostgreSQL through SQLAlchemy. SQLite is the database currently used by the installed v2 project; this procedure migrates its existing rows to PostgreSQL without deleting or modifying the SQLite source.

## 1. Prepare a local PostgreSQL service

Docker Desktop must be installed and running. In the existing project `.env`, change the placeholder to a private local password made only of URL-safe letters and numbers, for example a random 20+ character value:

```env
POSTGRES_PASSWORD=REPLACE_WITH_YOUR_PRIVATE_LOCAL_PASSWORD
POSTGRES_PORT=5432
```

Do not use the literal placeholder in a real submission. For ease of composing the connection URL, avoid characters such as `@`, `:`, `/`, `?`, `#` unless URL-encoded.

Start only the database service first:

```bash
docker compose up -d db
docker compose ps
```

Wait until the database health status is `healthy`.

## 2. Migrate the current SQLite data

Keep `DATABASE_URL=sqlite:///./data/samsung_phones.db` in `.env` while running the one-time migration. Use the same password set above in the target URL:

```bash
python scripts/migrate_database.py \
  --source sqlite:///./data/samsung_phones.db \
  --target 'postgresql+psycopg://samsung_app:REPLACE_WITH_YOUR_PRIVATE_LOCAL_PASSWORD@localhost:5432/samsung_phones'
```

The migration creates the SQLAlchemy schema in PostgreSQL, refuses to copy into a target that already contains project data, copies phone/specification/price/chat tables and preserves primary keys. It advances PostgreSQL integer sequences for subsequent inserts. The source SQLite database is not modified. Keep a backup of `data/samsung_phones.db` anyway.

If the target database already has rows, stop and inspect it; the script intentionally refuses to merge or overwrite silently.

## 3. Switch the existing local API to PostgreSQL

After migration succeeds, update only `DATABASE_URL` in `.env`:

```env
DATABASE_URL=postgresql+psycopg://samsung_app:YOUR_PASSWORD@localhost:5432/samsung_phones
SEED_DEMO_DATA=false
```

Keep `POSTGRES_PASSWORD` set too. Restart Uvicorn, then run:

```bash
python scripts/check_database.py
```

It should report `Database: PostgreSQL`, phone count, live GSMArena count, specification row count and price observation count. Compare these counts with the migration output. Also check `http://127.0.0.1:8000/api/health` and `/api/phones`.

The original SQLite file remains in `data/` as a rollback copy. To return to it, stop the API, restore the SQLite `DATABASE_URL` value, and restart.

## 4. Docker Compose API option

After the migration, `docker compose up -d --build` starts the containerized API against the Postgres service. The compose file uses `db` as its internal hostname and maps the Ollama endpoint to `host.docker.internal:11434`. Browser scraping should still be run on the Mac host (not inside the API container), because the Selenium workflow needs a visible Chrome window for a human verification prompt.

If Docker is not available before the deadline, continue using the existing SQLite database. PostgreSQL is supported and the migration is scripted, but do not claim it was deployed or tested unless `scripts/check_database.py` confirms a PostgreSQL connection.
