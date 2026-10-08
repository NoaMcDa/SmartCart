# Infrastructure

Scripts and a Terraform skeleton for the phase 0 infrastructure: the Supabase database (#14), the
Israeli-IP ingestion VPS and the raw-archive bucket (#22). The procedure, expected outputs and the
policies (roles, connections, backups, secrets) are in `docs/infra-provisioning.md`; start there. Going
live once provisioned is `docs/deploy.md`; the one-secret provisioning path and the manual workflows
are `docs/unblock.md`.

Nothing here contains secrets. Every script reads environment variables; the names are catalogued in
the repo root `.env.example`.

| Path | What it is |
|---|---|
| `vps/setup.sh` | Idempotent VPS setup: Python 3.12, uv, the `smartcart` user, the ingest environment, systemd units, log rotation, baseline hardening. Run as root. |
| `vps/smartcart-ingest-full.{service,timer}` | Daily full sync, 06:00 and 08:30 Israel time, calls `smartcart-ingest`. |
| `vps/smartcart-ingest-delta.{service,timer}` | Hourly delta poll at minute 20, calls `smartcart-ingest`. |
| `vps/smartcart-api.service` | The FastAPI service on 127.0.0.1:8000 (Caddy in front when `SMARTCART_API_DOMAIN` is set). |
| `vps/smartcart-precompute.{service,timer}` | Nightly effective-price precompute at 09:30 Israel time, after the full sync. |
| `vps/smartcart-alerts.{service,timer}` | Hourly price-drop alerts job at minute 45. |
| `docker-compose.yml` | Local database by default; `--profile app` adds migrate, api and web; `--profile jobs` the timers' jobs. |
| `smoke/check_israeli_ip.sh` | Geolocates the public IP with two services; exits non-zero unless both say IL. |
| `smoke/check_portals.sh` | Reachability of the transparency portals plus a real laibcatalog download. |
| `smoke/bucket_roundtrip.py` | Upload, read back and delete one object with the least-privilege token (boto3, R2 or S3). |
| `smoke/db_smoke.sql` | Lists extensions, runs a PostGIS distance and a pgvector cosine distance, asserts the results. |
| `terraform/` | Skeleton for the Supabase project, an R2 bucket and a VPS. Not validated against live providers. |

Quick reference, once the variables exist:

```bash
psql "$DATABASE_URL_DIRECT" -f infra/smoke/db_smoke.sql   # on any machine with psql
bash infra/smoke/check_israeli_ip.sh                      # on the VPS
bash infra/smoke/check_portals.sh                         # on the VPS
uv run infra/smoke/bucket_roundtrip.py                    # on the VPS or anywhere with the S3_* variables
```

The scripts are checked in CI-free ways only: `bash -n` for the shell scripts and `uv run ruff check .`
for the Python one. None of them has been run against live services, because none of the services
exists yet. See section 0 of `docs/infra-provisioning.md` for which acceptance items wait for that.
