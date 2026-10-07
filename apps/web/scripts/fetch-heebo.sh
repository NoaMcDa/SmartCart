#!/usr/bin/env bash
# One-time setup: download Heebo 400/500/600/700 as static woff2 from Google Fonts into
# public/fonts so the app never depends on fonts.googleapis.com at runtime (works offline).
# The output is committed; rerun only to update the font. Usage: bash scripts/fetch-heebo.sh
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
out="$here/public/fonts"
mkdir -p "$out"
# An older browser UA makes the CSS API return one full (non-subset) woff2 per weight, so each
# file covers Hebrew and Latin together and next/font/local needs no unicode-range handling.
ua="Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0"
css="$(curl -fsS -A "$ua" "https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&display=swap")"
for w in 400 500 600 700; do
  url="$(printf '%s\n' "$css" | awk -v w="font-weight: $w;" '$0 ~ w {f=1} f && /src:/ {match($0, /https:[^)]+/); print substr($0, RSTART, RLENGTH); exit}')"
  echo "Heebo $w <- $url"
  curl -fsS -o "$out/Heebo-$w.woff2" "$url"
done
curl -fsS -o "$out/OFL.txt" "https://raw.githubusercontent.com/google/fonts/main/ofl/heebo/OFL.txt"
