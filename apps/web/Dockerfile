# syntax=docker/dockerfile:1.7
#
# SmartCart web image: the Next.js PWA and the static SEO pages as a standalone Node server.
# The zero-ops alternative is Vercel (apps/web/vercel.json); both take the same variables. See
# docs/deploy.md.
#
# Build from apps/web (the context is the web app only):
#
#   docker build -f apps/web/Dockerfile -t smartcart-web \
#     --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.example.org \
#     --build-arg NEXT_PUBLIC_SITE_URL=https://example.org \
#     --build-arg NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co \
#     --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key> \
#     apps/web
#   docker run --rm -p 3000:3000 smartcart-web
#
# NEXT_PUBLIC_* values are inlined into the JavaScript at BUILD time (docs/web.md): an image is
# built for one API origin and one site URL. Changing them means building a new image, not
# restarting the container. They are public by design (they ship to every browser); nothing
# secret belongs here. The build context is filtered by apps/web/Dockerfile.dockerignore.

# Pinned base (Node 22, as CI). An argument so a mirror or a CA-trusting variant of the same image
# can be swapped in at build time (hadolint cannot see through the argument: DL3006 ignored).
ARG NODE_IMAGE=node:22.20.0-bookworm-slim

# --- deps: npm ci from the lockfile ------------------------------------------------------------
# hadolint ignore=DL3006
FROM ${NODE_IMAGE} AS deps
WORKDIR /app
ENV NPM_CONFIG_UPDATE_NOTIFIER=false NPM_CONFIG_FUND=false NPM_CONFIG_AUDIT=false
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci

# --- build: next build with output "standalone" ------------------------------------------------
# hadolint ignore=DL3006
FROM ${NODE_IMAGE} AS build
WORKDIR /app

# The env contract (docs/deploy.md). Defaults build a local image against a local API.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_SITE_URL=
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=
ARG NEXT_PUBLIC_VAPID_PUBLIC_KEY=
ARG NEXT_PUBLIC_BETA_EVENTS=
ARG NEXT_PUBLIC_CONTACT_EMAIL=
# Test-only switches; leave empty in production.
ARG NEXT_PUBLIC_API_MOCK=
ARG NEXT_PUBLIC_DISABLE_SW=

ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_OUTPUT=standalone \
    NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL} \
    NEXT_PUBLIC_SUPABASE_URL=${NEXT_PUBLIC_SUPABASE_URL} \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=${NEXT_PUBLIC_SUPABASE_ANON_KEY} \
    NEXT_PUBLIC_VAPID_PUBLIC_KEY=${NEXT_PUBLIC_VAPID_PUBLIC_KEY} \
    NEXT_PUBLIC_BETA_EVENTS=${NEXT_PUBLIC_BETA_EVENTS} \
    NEXT_PUBLIC_CONTACT_EMAIL=${NEXT_PUBLIC_CONTACT_EMAIL} \
    NEXT_PUBLIC_API_MOCK=${NEXT_PUBLIC_API_MOCK} \
    NEXT_PUBLIC_DISABLE_SW=${NEXT_PUBLIC_DISABLE_SW}

COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build \
 && test -f .next/standalone/server.js

# --- runtime: node server.js, non-root ---------------------------------------------------------
# hadolint ignore=DL3006
FROM ${NODE_IMAGE} AS runtime

LABEL org.opencontainers.image.title="smartcart-web" \
      org.opencontainers.image.description="SmartCart PWA and SEO pages (Next.js standalone)" \
      org.opencontainers.image.source="https://github.com/NoaMcDa/SmartCart"

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# The standalone server does not copy public/ (service worker, manifest icons, fonts, the SEO
# data the product and category pages read at request time) or the hashed static chunks.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
# The ISR / fetch cache directory must be writable by the server user.
RUN mkdir -p .next/cache && chown -R node:node .next/cache

USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:' + (process.env.PORT || 3000) + '/manifest.webmanifest').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "server.js"]
