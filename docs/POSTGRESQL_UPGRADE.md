# PostgreSQL setup and safe migration from SQLite

The application supports SQLite and PostgreSQL through SQLAlchemy. SQLite is the simplest local default. This guide migrates an existing SQLite catalogue into an empty PostgreSQL database without modifying the SQLite source.

## 1. Prepare PostgreSQL

Install and start Docker Desktop. In the existing `.env`, set a private URL-safe local password. If port 5432 is already occupied on your Mac, select host port 5433:

```dotenv
POSTGRES_PASSWORD=YOUR_PRIVATE_LOCAL_PASSWORD
POSTGRES_PORT=5433
```

Use a password made of URL-safe letters and numbers to avoid URL-encoding issues in the connection string. Do not commit `.env`.

Start PostgreSQL:

```bash
docker compose up -d db
docker compose ps
```

Wait until the service reports `healthy`. Docker maps `${POSTGRES_PORT}` on the host to port `5432` inside the container.

## 2. Back up and migrate the SQLite database

Keep the current SQLite `DATABASE_URL` in `.env` while running the one-time migration. Make a backup first:

```bash
cp data/samsung_phones.db data/samsung_phones_backup.db
```

Then run the migration. Replace the password and host port with the values configured above:

```bash
python scripts/migrate_database.py \
  --source "sqlite:///./data/samsung_phones.db" \
  --target "postgresql+psycopg://samsung_app:YOUR_PRIVATE_LOCAL_PASSWORD@127.0.0.1:5433/samsung_phones"
```

The migration creates the SQLAlchemy schema, refuses to copy into a target that already contains project data, copies the phone/specification/price/chat tables, preserves primary keys, and advances PostgreSQL integer sequences for later inserts. It does not modify the SQLite source. If the target already contains rows, stop and inspect it; the script intentionally refuses to merge or overwrite silently.

## 3. Switch the local application to PostgreSQL

Only after migration succeeds, update `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://samsung_app:YOUR_PRIVATE_LOCAL_PASSWORD@127.0.0.1:5433/samsung_phones
SEED_DEMO_DATA=false
```

Keep `POSTGRES_PASSWORD` and `POSTGRES_PORT` set. Restart Uvicorn and check the connection and record counts:

```bash
python scripts/check_database.py
curl http://127.0.0.1:8000/api/health
```

Compare the counts with the migration output. Keep the SQLite backup as a rollback copy. To return to SQLite, stop the API, restore the SQLite `DATABASE_URL` value, and restart.

## 4. Optional Docker Compose API service

After the migration, `docker compose up -d --build` can start the containerized API using the Compose PostgreSQL service. Inside the Compose network the database hostname is `db` and its port is `5432`; the host port may be `5433` or another value from `POSTGRES_PORT`. The Compose API points at a host Ollama service through `host.docker.internal:11434`.

The verified GSMArena CLI crawler uses Requests + BeautifulSoup and can be run on the Mac host. If GSMArena returns a Turnstile page, the crawler detects it and stops rather than attempting to bypass the site's access control.
