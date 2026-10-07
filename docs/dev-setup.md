# Developer setup

How to install, lint and test the SmartCart monorepo locally, and what CI runs.

## Tooling

| Tool | Version | Notes |
|---|---|---|
| Python | 3.12 or newer | CI tests 3.12 and 3.13. |
| [uv](https://docs.astral.sh/uv/) | any recent | The package manager. The repo root is a uv workspace; each Python service under `services/` is a member. |
| ruff | from the dev group | Lint and format. |
| pytest | from the dev group | Tests. Markers: `db`, `postgis`, `pgvector`. |
| Postgres | 16 (local) / 17 (CI image) | Optional locally; see below. |

`uv.lock` is not committed yet, so `uv sync` resolves the newest versions allowed by the
`pyproject.toml` files.

## Everyday commands

From the repository root:

```bash
uv sync                      # create .venv with every workspace member and the dev tools
uv run ruff check .          # lint
uv run ruff format .         # format (not enforced in CI yet)
uv run pytest                # all tests
uv run pytest -m "not db"    # only tests that need no database
```

## Repository layout

```
apps/web            Next.js PWA (phase 1; empty for now)
services/api        FastAPI (phase 1; empty for now)
services/catalog    normalization, embeddings, matching (phase 1; empty for now)
services/ingest     Python: transparency files -> Postgres, quality gates
supabase            SQL migrations (see supabase/README.md)
infra               docker compose for a local database, provisioning notes
docs                product, decisions, architecture, roadmap, this file
```

## The test database

Tests that touch Postgres use the fixtures in `services/ingest/tests/conftest.py`. The database
comes from one of three places, in this order:

1. **`DATABASE_URL` is set.** That database is migrated (`smartcart_ingest.db.migrate`) and used.
   Each test runs in a transaction that is rolled back, so the only lasting change is the
   migrations themselves. CI works this way.
2. **Postgres server binaries are installed.** The fixture creates a throwaway cluster with
   `initdb` and `pg_ctl` in a temp directory on a free port, migrates it, and deletes it at the
   end of the session. Binaries are looked up in `$PG_BIN`, then `/usr/lib/postgresql/<newest>/bin`,
   then `$PATH`. As root, the server runs as the `postgres` OS user through `runuser`, because
   `initdb` refuses to run as root.
3. **Neither.** Database tests are skipped with a message; the rest still run.

### What is skipped without PostGIS or pgvector

A plain Postgres install usually has `pg_trgm` but not PostGIS or pgvector. Then:

- Migrations that declare `-- requires: postgis` or `-- requires: vector` are skipped and not
  recorded. Today that is `..._extensions.sql` and `..._stores_geog.sql`, so `stores` has no
  `geog` column locally. Everything else (prices, partitions, promos, file tracking) is identical.
- Tests marked `postgis` or `pgvector` are skipped (6 at the time of writing): the geography
  column and GiST index, the radius-query EXPLAIN, `stores_within`, and the #14 smoke tests.
- All other database tests run.

CI sets `SMARTCART_REQUIRE_EXTENSIONS=1`, which turns a missing extension into a failure, so the
skipped tests always run there.

To run everything locally, use one of:

- **Docker:** `docker compose -f infra/docker-compose.yml up -d`, then
  `export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres` (the same URL CI
  uses). The image is the one CI uses.
- **Debian or Ubuntu packages:** `sudo apt install postgresql-16-postgis-3 postgresql-16-pgvector`;
  the throwaway cluster then has both extensions.

## Environment variables

| Variable | Used by | Meaning |
|---|---|---|
| `DATABASE_URL` | `smartcart_ingest.db.connect`, tests | Postgres connection string. Never commit a real one. |
| `PG_BIN` | tests | Directory with `initdb` and `pg_ctl` for the throwaway cluster. |
| `SMARTCART_REQUIRE_EXTENSIONS` | tests | `1` fails the run if PostGIS or pgvector is missing. |
| `SMARTCART_MIGRATIONS_DIR` | `smartcart_ingest.db` | Override the migrations directory (default `supabase/migrations`). |

## Continuous integration

`.github/workflows/ci.yml` runs on every pull request and push, on Python 3.12 and 3.13:
`uv sync`, `ruff check .`, then `pytest` against a
`supabase/postgres:17.11.0.004` service container (PostGIS, pgvector and pg_trgm available). That
tag was verified to exist on Docker Hub on 2026-10-06. Supabase publishes Postgres 15 and 17
images, not 16; the schema uses nothing that differs between 16 and 17.
