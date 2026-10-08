# Sign-off records

Files here record a human decision about seed data. They are evidence, not configuration: nothing
reads them at run time, and they never change `data/canonicals.yaml` by themselves.

Today there is one kind, the canonical sign-off of issue #15 (`docs/catalog.md` section 2, "Open:
domain-aware reviewer sign-off"). How the reviewer produces one: `docs/review-packet.md`.

## `canonicals-<YYYY-MM-DD>.yaml`

Written by `smartcart-catalog review-import FILLED.csv --reviewer "Name"`. The date is the review
date (`--date`, default today). An existing file is not overwritten without `--force`.
`template.yaml` is the empty form.

| Key | Meaning |
|---|---|
| `version` | Format version, `1`. |
| `kind` | `canonical-signoff`. |
| `issue` | `15`. |
| `status` | `complete` when every canonical in `data/canonicals.yaml` has a decision; `partial` when the import was run with `--allow-partial` and some are in `pending`. Issue #15 asks for complete. |
| `reviewer` | The reviewer's name, as given to `--reviewer`. |
| `reviewed_on` | `YYYY-MM-DD`. |
| `note` | Free text (role, scope, caveats). |
| `source.canonicals_file` | Always `data/canonicals.yaml`. |
| `source.canonicals_sha256_12` | First 12 hex digits of the sha256 of that file when the import ran. If the file changed afterwards, this tells you the sign-off is about an older list. |
| `source.canonicals_total` | Number of canonicals in the file at import. |
| `source.review_csv` | File name of the filled CSV. |
| `source.csv_encoding` | `utf-8`, or `windows-1255` when the CSV came from Hebrew Excel's plain "CSV" save. |
| `summary` | Counts: `ok`, `change`, `remove`, `add`, `pending`. |
| `decisions` | One entry per decided canonical, in CSV order (below). |
| `additions` | Products the reviewer says are missing (below). |
| `pending` | Slugs with no decision (empty when `status` is `complete`). |

### A `decisions` entry

| Key | Required | Meaning |
|---|---|---|
| `slug` | yes | The canonical's slug in `data/canonicals.yaml`. |
| `decision` | yes | `ok` (the canonical is right as is), `change` (something is wrong, see `comment` and `proposed`), `remove` (take it off the list). |
| `comment` | for `change` and `remove`, unless `proposed` is given | The reviewer's words. |
| `proposed` | no, `change` only | Machine-readable edits: any of `display_name_he`, `base_unit` (`100g`, `100ml`, `unit` or `kg`), `critical_attrs`, `soft_attrs` (maps of attribute keys to values; a key set must still equal the product type's critical keys, `docs/catalog.md` section 2) and `rank` (the position the canonical should take in the list left after removals). A value that is not given is unchanged. |

### An `additions` entry

`display_name_he` and `comment` (required), and any of `taxonomy_id`, `product_type`,
`base_unit` the reviewer knew. An addition needs a taxonomy node, a product type and critical
attributes before it can be a canonical, so an engineer finishes it; it is never part of the
printed diff.

## How decisions turn into changes

`review-import` prints the diff the decisions imply for `data/canonicals.yaml` and says whether the
result would pass `smartcart-catalog seed --check`. The diff compares a normalized rendering of the
file (flow-style attribute maps, no YAML anchors) with and without the decisions, so it is for
reading; an engineer applies the decisions by hand or from `--patch-out`. Removing a canonical
renumbers every rank after it, because the seed validation requires ranks `1..N` without gaps.
Two things the import cannot do: `change` without a `proposed` block (it lists the comment for a
manual edit) and `add`.

After an engineer applies the decisions and re-seeds, the sign-off file is committed next to the
change, and `docs/catalog.md` section 2 is updated to say the review happened, by whom and when.
