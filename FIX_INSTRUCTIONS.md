# Fix: safe, repeatable GSMArena imports

## What caused the error

The old importer replaced `phone.specifications` by calling `clear()` and then appending new rows. Since `(phone_id, section, spec_name)` is unique, SQLAlchemy could issue INSERTs before orphan DELETEs and hit a SQLite unique-constraint error when converting an existing demo record into a live scraped record.

## What this patch changes

`app/services/catalog.py` now synchronizes specification records by their unique key:

- updates matching rows in place;
- inserts only rows that do not exist yet;
- deletes rows no longer present in the source page;
- safely supports re-importing the same HTML page multiple times.

## Apply on macOS

From the root of your existing `samsung_phone_assistant` project, extract this ZIP and allow it to overwrite files, or run:

```bash
unzip -o ~/Downloads/samsung_phone_assistant_catalog_upsert_fix.zip -d .
```

This replaces `app/services/catalog.py` and adds one regression test at `tests/test_catalog_upsert.py`. It does not replace your database or HTML files.

Then run:

```bash
source .venv/bin/activate
pytest -q
python scripts/import_saved_html.py
python scripts/verify_scraped_catalog.py --minimum 1 --maximum 1
```

After more real phone pages have been imported, use the default acceptance range:

```bash
python scripts/verify_scraped_catalog.py
```

The default acceptance target is 10–15 live-source records.
