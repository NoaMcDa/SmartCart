#!/usr/bin/env bash
# Verify that this machine's public IP geolocates to Israel, using two independent services.
#
# Exit codes: 0 both services say IL; 1 at least one service says another country;
#             2 inconclusive (a service did not answer, no country mismatch seen).
# Needs only curl. Optional overrides: GEO_URL_1, GEO_URL_2 (each must return a bare
# two-letter country code as plain text), CURL_MAX_TIME (seconds, default 15).
set -euo pipefail

GEO_URL_1="${GEO_URL_1:-https://ipinfo.io/country}"
GEO_URL_2="${GEO_URL_2:-https://ifconfig.co/country-iso}"
IP_URL="${IP_URL:-https://ifconfig.me/ip}"
CURL_MAX_TIME="${CURL_MAX_TIME:-15}"

fetch() {
  # Prints the trimmed body, or nothing when the request fails.
  curl -fsS --max-time "$CURL_MAX_TIME" -A "smartcart-infra-smoke/1.0" "$1" 2>/dev/null \
    | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]' || true
}

public_ip="$(fetch "$IP_URL")"
echo "public ip:        ${public_ip:-unknown}"

c1="$(fetch "$GEO_URL_1")"
c2="$(fetch "$GEO_URL_2")"
echo "service 1 (${GEO_URL_1}): ${c1:-no answer}"
echo "service 2 (${GEO_URL_2}): ${c2:-no answer}"

mismatch=0
missing=0
for c in "$c1" "$c2"; do
  if [[ -z "$c" ]]; then
    missing=1
  elif [[ ! "$c" =~ ^[A-Z]{2}$ ]]; then
    # Anything that is not a two-letter code (an HTML error page, a rate-limit message).
    missing=1
  elif [[ "$c" != "IL" ]]; then
    mismatch=1
  fi
done

if [[ "$mismatch" -eq 1 ]]; then
  echo "FAIL: at least one service places this IP outside Israel (expected IL)."
  exit 1
fi
if [[ "$missing" -eq 1 ]]; then
  echo "INCONCLUSIVE: a geolocation service did not return a country code. Re-run later."
  exit 2
fi
echo "PASS: both services report IL."
