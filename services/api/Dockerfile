# syntax=docker/dockerfile:1.7
#
# SmartCart API image: FastAPI (`smartcart-api serve`), the nightly precompute and the alerts job,
# plus `smartcart-ingest migrate` for the schema. See docs/deploy.md.
#
# Build from the REPOSITORY ROOT (the API depends on the ingest and catalog workspace members and
# the migrations live in supabase/):
#
#   docker build -f services/api/Dockerfile -t smartcart-api .
#   docker run --rm -p 8000:8000 -e DATABASE_URL=... -e SUPABASE_JWT_SECRET=... smartcart-api
#   docker run --rm -e DATABASE_URL=... smartcart-api smartcart-api precompute
#   docker run --rm -e DATABASE_URL=... smartcart-api smartcart-api alerts-run
#   docker run --rm -e DATABASE_URL=<direct, owner> smartcart-api smartcart-ingest migrate
#
# The build context is filtered by services/api/Dockerfile.dockerignore (BuildKit reads the
# ignore file next to the Dockerfile). Runtime variables are the ones in docs/api.md; nothing
# secret is baked into the image.

# Pinned base. An argument so a mirror or a CA-trusting variant of the same image can be swapped
# in at build time (hadolint cannot see through the argument, hence DL3006 is ignored below).
ARG PYTHON_IMAGE=python:3.12.12-slim-bookworm

# --- build: resolve and install into /app/.venv with uv ------------------------------------------
# hadolint ignore=DL3006
FROM ${PYTHON_IMAGE} AS build

ARG UV_VERSION=0.11.32
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /app

# Dependencies first, from the manifests only, so a code change does not re-resolve them. The
# workspace root lists every member, so each member's manifest must exist (the dashboard's too,
# although it is not installed). uv.lock is not committed (docs/dev-setup.md): uv resolves the
# newest versions the manifests allow, exactly as CI does.
COPY pyproject.toml ./
COPY services/ingest/pyproject.toml services/ingest/pyproject.toml
COPY services/catalog/pyproject.toml services/catalog/pyproject.toml
COPY services/api/pyproject.toml services/api/pyproject.toml
COPY services/dashboard/pyproject.toml services/dashboard/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package smartcart-api --no-dev --no-install-workspace

# The code. The members are installed editable on purpose: the packages find the migrations
# (supabase/migrations) and the catalog data (data/) relative to the repository layout.
COPY services/ingest/smartcart_ingest services/ingest/smartcart_ingest
COPY services/catalog/smartcart_catalog services/catalog/smartcart_catalog
COPY services/api/smartcart_api services/api/smartcart_api
COPY supabase/migrations supabase/migrations
COPY supabase/queries supabase/queries
COPY data/taxonomy.yaml data/canonicals.yaml data/product_type_rules.yaml data/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --package smartcart-api --no-dev \
 && /app/.venv/bin/python -c "import ortools.sat.python.cp_model, smartcart_api.main" \
 && /app/.venv/bin/smartcart-api --help >/dev/null

# --- runtime: the venv and the code, no build tools, non-root ------------------------------------
# hadolint ignore=DL3006
FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="smartcart-api" \
      org.opencontainers.image.description="SmartCart FastAPI service, precompute and alerts jobs" \
      org.opencontainers.image.source="https://github.com/NoaMcDa/SmartCart"

RUN groupadd --system --gid 10001 smartcart \
 && useradd --system --uid 10001 --gid smartcart --home-dir /home/smartcart --create-home \
      --shell /usr/sbin/nologin smartcart

# Code and venv are owned by root and read-only for the service user.
COPY --from=build /app /app

ENV PATH=/app/.venv/bin:${PATH} \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SMARTCART_MIGRATIONS_DIR=/app/supabase/migrations \
    PORT=8000

# A writable working directory: the upstream il_supermarket_* packages write logging.log into the
# current directory when they are imported (only the ingest code paths import them).
WORKDIR /home/smartcart
USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"]

# Shell form through sh -c so $PORT is honoured (Render, Fly and Cloud Run set it).
CMD ["sh", "-c", "exec smartcart-api serve --host 0.0.0.0 --port \"${PORT}\""]
