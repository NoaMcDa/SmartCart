#!/usr/bin/env bash
# Copy the portal probe's fixture artifact into services/ingest/tests/fixtures/<chain>/real/.
#
#   scripts/unblock/copy_fixtures.sh <artifact dir> [<fixtures dir>]
#
# The artifact is untrusted data built from portal downloads. Only paths of the exact form
# <chain>/real/<file name> are copied, where <chain> already has a fixture folder with an
# expected.json and the file name is plain ([A-Za-z0-9._-]); anything else is skipped with a
# warning. Nothing in the artifact is executed or parsed here. Prints the number copied; exits 1
# when nothing was copied.
set -euo pipefail

src="${1:?usage: $0 <artifact dir> [<fixtures dir>]}"
dest="${2:-services/ingest/tests/fixtures}"
src="${src%/}"
copied=0
while IFS= read -r -d '' file; do
  rel="${file#"$src"/}"
  slug="${rel%%/*}"
  name="${rel##*/}"
  if [[ ! "$rel" =~ ^[a-z_]+/real/[A-Za-z0-9._-]+$ || ! -f "$dest/$slug/expected.json" ]]; then
    echo "skipping unexpected path in the artifact: $rel" >&2
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then echo "::warning::skipping unexpected path: $rel"; fi
    continue
  fi
  mkdir -p "$dest/$slug/real"
  cp -- "$file" "$dest/$slug/real/$name"
  copied=$((copied + 1))
done < <(find "$src" -type f -print0 | sort -z)
echo "copied $copied file(s) into $dest/<chain>/real/"
[[ "$copied" -gt 0 ]]
