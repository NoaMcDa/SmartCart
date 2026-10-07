#!/usr/bin/env bash
# Reachability check for the chain transparency portals, plus one real download from laibcatalog,
# the portal the research says blocks cloud IP ranges (verified, research section 2.3).
#
# Run it on the ingestion VPS. Run it once from a non-Israeli machine too if you want proof that
# the block is real: the laibcatalog line should then differ.
#
# Exit codes: 0 everything reachable and the download probe passed;
#             1 a portal is unreachable, blocked or erroring, or the download probe failed;
#             2 reachability is fine but the download probe was inconclusive (the laibcatalog
#               listing is empty between midnight and about 08:00 Israel time; re-run later).
# Needs curl and python3 (standard library only). Optional: CURL_MAX_TIME (default 20),
# SKIP_DOWNLOAD_PROBE=1, PROBE_EDI (laibcatalog chain id, default Victory 7290696200003).
set -euo pipefail

CURL_MAX_TIME="${CURL_MAX_TIME:-20}"
PROBE_EDI="${PROBE_EDI:-7290696200003}"
# A normal browser User-Agent: some portals sit behind a WAF that rejects empty agents.
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# label|url  (the first five are the portals named in issue #22; the rest are the other
# portals used by the D13 chains, from the upstream scraper source)
PORTALS=(
  "publishedprices (Cerberus, task host)|https://url.publishedprices.co.il/"
  "publishedprices (Cerberus, upstream host)|https://url.retail.publishedprices.co.il/"
  "Shufersal|https://prices.shufersal.co.il/"
  "laibcatalog (Victory, Machsanei Hashuk)|https://laibcatalog.co.il/"
  "matrixcatalog|https://matrixcatalog.co.il/"
  "Carrefour / Yeinot Bitan|https://prices.carrefour.co.il/"
  "Hazi Hinam|https://shop.hazi-hinam.co.il/Prices"
  "King Store (Bina)|http://kingstore.binaprojects.com/"
)

probe() {
  # Echo the HTTP status code (000 when the connection fails). HEAD first, then a one-byte GET
  # because some portals answer HEAD with 403, 405 or 501.
  local url="$1" code
  code="$(curl -sS -o /dev/null -L -I --max-time "$CURL_MAX_TIME" -A "$UA" \
    -w '%{http_code}' "$url" 2>/dev/null || true)"
  code="${code:-000}"
  case "$code" in
    000 | 403 | 405 | 501)
      code="$(curl -sS -o /dev/null -L -r 0-0 --max-time "$CURL_MAX_TIME" -A "$UA" \
        -w '%{http_code}' "$url" 2>/dev/null || true)"
      code="${code:-000}"
      ;;
  esac
  echo "$code"
}

classify() {
  case "$1" in
    000) echo "UNREACHABLE" ;;
    403 | 429) echo "BLOCKED?" ;;
    401 | 404 | 405 | 206) echo "REACHABLE" ;;
    2?? | 3??) echo "OK" ;;
    5??) echo "ERROR" ;;
    *) echo "REACHABLE" ;;
  esac
}

failures=0
printf '%-44s %-6s %s\n' "PORTAL" "HTTP" "RESULT"
for entry in "${PORTALS[@]}"; do
  label="${entry%%|*}"
  url="${entry#*|}"
  code="$(probe "$url")"
  result="$(classify "$code")"
  printf '%-44s %-6s %s\n' "$label" "$code" "$result"
  case "$result" in
    OK | REACHABLE) ;;
    *) failures=$((failures + 1)) ;;
  esac
done

probe_status="SKIPPED"
if [[ "${SKIP_DOWNLOAD_PROBE:-0}" != "1" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  base="https://laibcatalog.co.il"
  listing="$tmp/listing.json"
  echo
  echo "download probe: laibcatalog chain ${PROBE_EDI}"
  if ! curl -fsS --max-time "$CURL_MAX_TIME" -A "$UA" -o "$listing" \
    "${base}/webapi/api/getfiles?edi=${PROBE_EDI}"; then
    echo "  listing request failed"
    probe_status="FAIL"
  else
    # Prefer a small Stores file; fall back to the first listed file.
    fname="$(python3 - "$listing" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        entries = json.load(fh)
except (OSError, ValueError):
    entries = []
names = [e.get("fileName", "") for e in entries if isinstance(e, dict) and e.get("fileName")]
stores = [n for n in names if n.lower().startswith("stores")]
print((stores or names or [""])[0])
PY
)"
    if [[ -z "$fname" ]]; then
      echo "  listing is empty (normal between midnight and about 08:00 Israel time)"
      probe_status="INCONCLUSIVE"
    else
      echo "  downloading ${fname}"
      out="$tmp/download.bin"
      if curl -fsS --max-time 120 --max-filesize 52428800 -A "$UA" -o "$out" \
        "${base}/webapi/${PROBE_EDI}/${fname}"; then
        size="$(wc -c <"$out" | tr -d ' ')"
        magic="$(head -c 2 "$out" | od -An -tx1 | tr -d ' \n')"
        # 1f8b is gzip, 504b is zip; the transparency files are one of the two.
        if [[ "$size" -gt 0 && ( "$magic" == "1f8b" || "$magic" == "504b" ) ]]; then
          echo "  ok: ${size} bytes, archive magic ${magic}"
          probe_status="PASS"
        else
          echo "  unexpected content (${size} bytes, magic ${magic:-none}); a block page, not a data file?"
          probe_status="FAIL"
        fi
      else
        echo "  download failed"
        probe_status="FAIL"
      fi
    fi
  fi
fi

echo
echo "reachability failures: ${failures}"
echo "download probe:        ${probe_status}"

if [[ "$failures" -gt 0 || "$probe_status" == "FAIL" ]]; then
  exit 1
fi
if [[ "$probe_status" == "INCONCLUSIVE" ]]; then
  exit 2
fi
exit 0
