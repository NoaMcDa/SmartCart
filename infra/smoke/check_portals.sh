#!/usr/bin/env bash
# Reachability check for the chain transparency portals, plus one real download from laibcatalog,
# the portal the research says blocks cloud IP ranges (verified, research section 2.3).
#
# Run it on the ingestion VPS. Run it once from a non-Israeli machine too if you want proof that
# the block is real: the laibcatalog line should then differ.
#
# Exit codes: 0 everything reachable, every Cerberus login worked and the download probe passed;
#             1 a portal is unreachable, blocked or erroring, a Cerberus login failed, or the
#               download probe failed;
#             2 reachability is fine but the download probe was inconclusive (the laibcatalog
#               listing is empty between midnight and about 08:00 Israel time; re-run later).
# Needs curl and python3 (standard library only). Optional: CURL_MAX_TIME (default 20),
# SKIP_DOWNLOAD_PROBE=1, PROBE_EDI (laibcatalog chain id, default Victory 7290696200003).
#
# Also checks the Cerberus FTP login (FTP over TLS, the user name of each Cerberus chain and an
# empty password) for the four D13 Cerberus chains, in the upstream scraper's own mode:
# ftplib.FTP_TLS(host, user, "") without a context, which does not verify the certificate. The
# portal's certificate does not match url.retail.publishedprices.co.il (seen 2026-10-08), so a
# verifying login fails while the scraper works; the result line says so. A failed login counts
# as a failure. SKIP_FTP_LOGIN_PROBE=1 skips it.
# MARKDOWN_OUT=<file> also appends the results as a Markdown table to that file (the
# portal-probe workflow points it at $GITHUB_STEP_SUMMARY).
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

MARKDOWN_OUT="${MARKDOWN_OUT:-}"
md() {
  # Append one line to the Markdown output when MARKDOWN_OUT is set.
  if [[ -n "$MARKDOWN_OUT" ]]; then printf '%s\n' "$*" >>"$MARKDOWN_OUT"; fi
}
md "### Portal reachability (infra/smoke/check_portals.sh)"
md ""
md "| portal | HTTP | result |"
md "|---|---|---|"

failures=0
printf '%-44s %-6s %s\n' "PORTAL" "HTTP" "RESULT"
for entry in "${PORTALS[@]}"; do
  label="${entry%%|*}"
  url="${entry#*|}"
  code="$(probe "$url")"
  result="$(classify "$code")"
  printf '%-44s %-6s %s\n' "$label" "$code" "$result"
  md "| ${label} | ${code} | ${result} |"
  case "$result" in
    OK | REACHABLE) ;;
    *) failures=$((failures + 1)) ;;
  esac
done

# Cerberus chains log in over FTP with TLS: host|user. The host is the upstream Cerberus engine's
# default ftp_host and the users are from its scrapers (il_supermarket_scarper 1.0.15).
# CERBERUS_FTP_HOST and CERBERUS_FTP_PORT override the host and port (for testing).
CERBERUS_FTP_HOST="${CERBERUS_FTP_HOST:-url.retail.publishedprices.co.il}"
CERBERUS_FTP_PORT="${CERBERUS_FTP_PORT:-21}"
CERBERUS_LOGINS=(
  "${CERBERUS_FTP_HOST}|RamiLevi"
  "${CERBERUS_FTP_HOST}|TivTaam"
  "${CERBERUS_FTP_HOST}|osherad"
  "${CERBERUS_FTP_HOST}|yohananof"
)
if [[ "${SKIP_FTP_LOGIN_PROBE:-0}" != "1" ]]; then
  echo
  md ""
  md "| Cerberus FTP login | result |"
  md "|---|---|"
  for entry in "${CERBERUS_LOGINS[@]}"; do
    host="${entry%%|*}"
    user="${entry#*|}"
    login="$(python3 - "$host" "$user" "$CURL_MAX_TIME" "$CERBERUS_FTP_PORT" <<'PY'
import ftplib
import ssl
import sys

host, user, timeout = sys.argv[1], sys.argv[2], float(sys.argv[3])
ftplib.FTP.port = int(sys.argv[4])


def attempt(context):
    # Exactly how the upstream scraper connects (connection._open_ftp_tls): FTP_TLS(host, user,
    # password) logs in after AUTH TLS. With context=None ftplib uses an unverified context.
    try:
        ftp = ftplib.FTP_TLS(host, user, "", timeout=timeout, context=context)
        try:
            ftp.voidcmd("NOOP")
        finally:
            try:
                ftp.quit()
            except (ftplib.Error, OSError):
                ftp.close()
    except (ftplib.Error, OSError, EOFError) as exc:
        return type(exc).__name__
    return None


err = attempt(None)
if err:
    print(f"FAIL ({err})")
elif attempt(ssl.create_default_context()):
    print("OK (certificate fails verification; upstream does not verify it)")
else:
    print("OK")
PY
)"
    printf 'ftp login %-34s %s\n' "${user}@${host}" "$login"
    md "| ${user}@${host} | ${login} |"
    [[ "$login" == OK* ]] || failures=$((failures + 1))
  done
fi

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
md ""
md "Reachability and login failures: ${failures}; laibcatalog download probe: ${probe_status}."

if [[ "$failures" -gt 0 || "$probe_status" == "FAIL" ]]; then
  exit 1
fi
if [[ "$probe_status" == "INCONCLUSIVE" ]]; then
  exit 2
fi
exit 0
