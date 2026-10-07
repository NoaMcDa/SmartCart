#!/usr/bin/env bash
# Regenerate the web app's API types from the FastAPI schema (issue #67).
#
#   services/api/scripts/gen_ts_client.sh
#
# 1. apps/web/src/api/openapi.json  <- the FastAPI app (uv run python -m smartcart_api.export_openapi)
# 2. apps/web/src/api/types.ts      <- openapi-typescript (pinned below), types only, no runtime
#
# Both files are generated: never edit them by hand. CI runs this script and fails when either
# file differs from what is committed. The web app types its calls with `paths` from types.ts
# (for example with openapi-fetch, or plain fetch).
set -euo pipefail

OPENAPI_TYPESCRIPT_VERSION="7.13.0"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

uv run python -m smartcart_api.export_openapi apps/web/src/api/openapi.json >/dev/null
npx --yes "openapi-typescript@${OPENAPI_TYPESCRIPT_VERSION}" apps/web/src/api/openapi.json \
  -o apps/web/src/api/types.ts
echo "regenerated apps/web/src/api/openapi.json and apps/web/src/api/types.ts"
