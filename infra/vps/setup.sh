#!/usr/bin/env bash
# Provision the SmartCart ingestion VPS (Ubuntu 22.04 or 24.04, or Debian 12). Run as root:
#
#     sudo bash infra/vps/setup.sh
#
# Idempotent: safe to run again after a repo update, it converges to the same state. It
#   1. installs system packages (curl, git, logrotate, ufw, unattended-upgrades, psql client);
#   2. installs uv and Python 3.12 (system-wide, under /opt);
#   3. creates the unprivileged `smartcart` service user and the directories it needs;
#   4. clones or updates the repo in /opt/smartcart and syncs the ingest workspace member;
#   5. installs the systemd units (daily full sync, hourly delta) and log rotation;
#   5b. installs the API: smartcart-api.service (127.0.0.1:8000), the nightly precompute and hourly
#      alerts timers, and with SMARTCART_API_DOMAIN a Caddy reverse proxy with TLS (docs/deploy.md);
#   6. applies baseline hardening: firewall, key-only SSH (only when keys exist), auto updates.
#
# Secrets are never written by this script. It creates /etc/smartcart/ingest.env empty (mode 0640,
# root:smartcart) if absent; you fill it from .env.example, see docs/infra-provisioning.md.
#
# Optional environment variables:
#   SMARTCART_REPO_URL   git URL (default https://github.com/NoaMcDa/SmartCart.git). For a private
#                        repo use an ssh URL with a read-only deploy key, or set SMARTCART_SKIP_CLONE=1
#                        and put the code in /opt/smartcart yourself.
#   SMARTCART_REPO_REF   branch or tag to deploy (default main)
#   SMARTCART_SKIP_CLONE 1 to leave /opt/smartcart as it is
#   SMARTCART_SSH_PORT   SSH port to keep open in the firewall (default 22)
#   SMARTCART_SKIP_HARDENING 1 to skip the firewall and sshd changes
#   SMARTCART_SKIP_API   1 to install only the ingestion units (no API service, no API timers)
#   SMARTCART_API_DOMAIN public host name of the API (e.g. api.example.org). When set, Caddy is
#                        installed as a TLS reverse proxy to 127.0.0.1:8000 and ports 80 and 443 are
#                        opened. The DNS A record must already point at this server.
#   SMARTCART_API_PORT   loopback port of the API (default 8000; also set it in api.env)
set -euo pipefail

REPO_URL="${SMARTCART_REPO_URL:-https://github.com/NoaMcDa/SmartCart.git}"
REPO_REF="${SMARTCART_REPO_REF:-main}"
SSH_PORT="${SMARTCART_SSH_PORT:-22}"
APP_USER="smartcart"
APP_DIR="/opt/smartcart"
ENV_DIR="/etc/smartcart"
ENV_FILE="${ENV_DIR}/ingest.env"
API_ENV_FILE="${ENV_DIR}/api.env"
JOBS_ENV_FILE="${ENV_DIR}/jobs.env"
SKIP_API="${SMARTCART_SKIP_API:-0}"
API_DOMAIN="${SMARTCART_API_DOMAIN:-}"
API_PORT="${SMARTCART_API_PORT:-8000}"
LOG_DIR="/var/log/smartcart"
STATE_DIR="/var/lib/smartcart"
UV_PYTHON_DIR="/opt/uv-python"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "run as root (sudo bash infra/vps/setup.sh)" >&2
  exit 1
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "this script supports Debian and Ubuntu (apt) only" >&2
  exit 1
fi

# 1. System packages -----------------------------------------------------------------------------
log "installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates curl git logrotate openssh-server postgresql-client python3 \
  ufw unattended-upgrades util-linux

# 2. uv and Python 3.12 -------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  log "installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi
log "installing Python 3.12 with uv ($(uv --version))"
mkdir -p "${UV_PYTHON_DIR}"
chmod 755 "${UV_PYTHON_DIR}"
UV_PYTHON_INSTALL_DIR="${UV_PYTHON_DIR}" uv python install 3.12

# 3. Service user and directories ---------------------------------------------------------------
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  log "creating user ${APP_USER}"
  useradd --system --create-home --home-dir "${STATE_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi
install -d -m 0755 -o "${APP_USER}" -g "${APP_USER}" "${LOG_DIR}" "${STATE_DIR}"
install -d -m 0750 -o root -g "${APP_USER}" "${ENV_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  log "creating empty ${ENV_FILE} (fill it from .env.example)"
  install -m 0640 -o root -g "${APP_USER}" /dev/null "${ENV_FILE}"
  cat >"${ENV_FILE}" <<'EOF'
# SmartCart ingestion environment. Variable names are catalogued in .env.example in the repo.
# Never commit this file. Mode 0640, owner root, group smartcart.
# DATABASE_URL=
# S3_ENDPOINT_URL=
# S3_BUCKET=
# S3_REGION=
# S3_ACCESS_KEY_ID=
# S3_SECRET_ACCESS_KEY=
EOF
  chown root:"${APP_USER}" "${ENV_FILE}"
  chmod 0640 "${ENV_FILE}"
fi

# 4. Code and virtualenv ------------------------------------------------------------------------
install -d -m 0755 -o "${APP_USER}" -g "${APP_USER}" "${APP_DIR}"
as_app() { runuser -u "${APP_USER}" -- env HOME="${STATE_DIR}" "$@"; }
if [[ "${SMARTCART_SKIP_CLONE:-0}" != "1" ]]; then
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "updating ${APP_DIR} to ${REPO_REF}"
    as_app git -C "${APP_DIR}" fetch --tags origin
    as_app git -C "${APP_DIR}" checkout -f "${REPO_REF}"
    # Fast-forward only when on a branch; a tag leaves a detached HEAD, which is fine.
    as_app git -C "${APP_DIR}" pull --ff-only origin "${REPO_REF}" 2>/dev/null || true
  else
    log "cloning ${REPO_URL} into ${APP_DIR}"
    as_app git clone "${REPO_URL}" "${APP_DIR}"
    as_app git -C "${APP_DIR}" checkout "${REPO_REF}"
  fi
fi
if [[ ! -f "${APP_DIR}/pyproject.toml" ]]; then
  echo "no repo found in ${APP_DIR}; set SMARTCART_REPO_URL or place the code there" >&2
  exit 1
fi
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"

# One environment for both: the API package depends on the ingest package, and syncing them
# together keeps a later sync of one from removing the other's dependencies.
SYNC_PACKAGES="--package smartcart-ingest"
if [[ "${SKIP_API}" != "1" ]]; then
  SYNC_PACKAGES="${SYNC_PACKAGES} --package smartcart-api"
fi
log "syncing the environment (${SYNC_PACKAGES})"
runuser -u "${APP_USER}" -- env \
  HOME="${STATE_DIR}" \
  UV_PYTHON_INSTALL_DIR="${UV_PYTHON_DIR}" \
  UV_CACHE_DIR="${STATE_DIR}/.cache/uv" \
  bash -c "cd '${APP_DIR}' && uv sync ${SYNC_PACKAGES} --python 3.12 --no-dev"

if [[ ! -x "${APP_DIR}/.venv/bin/smartcart-ingest" ]]; then
  warn "smartcart-ingest entry point not found in ${APP_DIR}/.venv/bin; the units will fail until the ingest package defines it"
fi

# 5. systemd units, log rotation ----------------------------------------------------------------
log "installing systemd units"
for unit in \
  smartcart-ingest-full.service smartcart-ingest-full.timer \
  smartcart-ingest-delta.service smartcart-ingest-delta.timer; do
  install -m 0644 -o root -g root "${SCRIPT_DIR}/${unit}" "/etc/systemd/system/${unit}"
done

log "installing log rotation"
cat >/etc/logrotate.d/smartcart <<EOF
${LOG_DIR}/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    # The units append to these files through systemd, so truncate in place instead of renaming.
    copytruncate
    su ${APP_USER} ${APP_USER}
}
EOF
install -d -m 0755 /etc/systemd/journald.conf.d
cat >/etc/systemd/journald.conf.d/smartcart.conf <<'EOF'
[Journal]
SystemMaxUse=500M
MaxRetentionSec=1month
EOF
systemctl restart systemd-journald || warn "could not restart journald"

systemctl daemon-reload
systemctl enable smartcart-ingest-full.timer smartcart-ingest-delta.timer
if grep -Eq '^DATABASE_URL=.+' "${ENV_FILE}"; then
  systemctl restart smartcart-ingest-full.timer smartcart-ingest-delta.timer
  log "timers started"
else
  warn "${ENV_FILE} has no DATABASE_URL yet: timers are enabled but not started."
  warn "fill the file, then: systemctl start smartcart-ingest-full.timer smartcart-ingest-delta.timer"
fi

# 5b. API service, precompute and alerts timers, reverse proxy -----------------------------------
if [[ "${SKIP_API}" != "1" ]]; then
  log "installing the API units"
  for unit in \
    smartcart-api.service \
    smartcart-precompute.service smartcart-precompute.timer \
    smartcart-alerts.service smartcart-alerts.timer; do
    install -m 0644 -o root -g root "${SCRIPT_DIR}/${unit}" "/etc/systemd/system/${unit}"
  done
  for f in "${API_ENV_FILE}" "${JOBS_ENV_FILE}"; do
    if [[ ! -f "${f}" ]]; then
      log "creating empty ${f} (fill it from .env.example, see docs/deploy.md)"
      install -m 0640 -o root -g "${APP_USER}" /dev/null "${f}"
    fi
  done
  if [[ ! -s "${API_ENV_FILE}" ]]; then
    cat >"${API_ENV_FILE}" <<'EOF'
# SmartCart API environment (smartcart-api.service). Loaded after ingest.env; values here win.
# Names are catalogued in .env.example; see docs/deploy.md. Never commit this file.
# DATABASE_URL=            # the API's service connection (transaction pooler), not the ingest role
# SUPABASE_JWT_SECRET=
# SUPABASE_URL=
# SUPABASE_SERVICE_ROLE_KEY=
# API_CORS_ORIGINS=https://<your domain>
# API_PUBLIC_WEB_URL=https://<your domain>
# VAPID_PRIVATE_KEY=
# VAPID_PUBLIC_KEY=
# VAPID_SUBJECT=mailto:
# API_QUERY_EMBEDDER=hash
# WEB_CONCURRENCY=2
EOF
  fi
  if [[ ! -s "${JOBS_ENV_FILE}" ]]; then
    cat >"${JOBS_ENV_FILE}" <<'EOF'
# SmartCart batch jobs (smartcart-precompute, smartcart-alerts). Loaded last; values here win.
# The precompute deletes stale effective_prices rows and the alerts job reads every user's alerts,
# so DATABASE_URL here must be a connection that may do both (docs/deploy.md). Never commit it.
# DATABASE_URL=
EOF
  fi
  chown root:"${APP_USER}" "${API_ENV_FILE}" "${JOBS_ENV_FILE}"
  chmod 0640 "${API_ENV_FILE}" "${JOBS_ENV_FILE}"

  systemctl daemon-reload
  systemctl enable smartcart-api.service smartcart-precompute.timer smartcart-alerts.timer
  if grep -Eq '^DATABASE_URL=.+' "${ENV_FILE}" "${API_ENV_FILE}"; then
    # A restart picks up the new code and environment after every deploy.
    systemctl restart smartcart-api.service
    systemctl restart smartcart-precompute.timer smartcart-alerts.timer
    log "waiting for the API health check on 127.0.0.1:${API_PORT}"
    healthy=0
    for _ in $(seq 1 30); do
      if curl -fsS --max-time 2 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
        healthy=1
        break
      fi
      sleep 1
    done
    if [[ "${healthy}" -ne 1 ]]; then
      echo "the API did not answer /health within 30 s; last lines of ${LOG_DIR}/api.log:" >&2
      tail -n 40 "${LOG_DIR}/api.log" >&2 || true
      exit 1
    fi
    log "API healthy: $(curl -fsS "http://127.0.0.1:${API_PORT}/health")"
  else
    warn "no DATABASE_URL in ${ENV_FILE} or ${API_ENV_FILE}: the API and its timers are enabled, not started."
    warn "fill ${API_ENV_FILE}, then run this script again (or: systemctl restart smartcart-api)"
  fi

  if [[ -n "${API_DOMAIN}" ]]; then
    log "installing Caddy as the TLS reverse proxy for ${API_DOMAIN}"
    apt-get install -y --no-install-recommends caddy
    cat >/etc/caddy/Caddyfile <<EOF
# Managed by infra/vps/setup.sh (SMARTCART_API_DOMAIN). TLS certificates are automatic.
${API_DOMAIN} {
	encode zstd gzip
	reverse_proxy 127.0.0.1:${API_PORT}
}
EOF
    caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
    systemctl enable caddy
    systemctl reload caddy 2>/dev/null || systemctl restart caddy
    if [[ "${SMARTCART_SKIP_HARDENING:-0}" != "1" ]]; then
      ufw allow 80/tcp >/dev/null
      ufw allow 443/tcp >/dev/null
    fi
  else
    log "SMARTCART_API_DOMAIN not set: the API listens on loopback only (no reverse proxy)"
  fi
else
  log "API skipped (SMARTCART_SKIP_API=1)"
fi

# 6. Baseline hardening -------------------------------------------------------------------------
log "enabling automatic security updates"
cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

if [[ "${SMARTCART_SKIP_HARDENING:-0}" != "1" ]]; then
  log "configuring the firewall (inbound: ssh on ${SSH_PORT} only)"
  ufw default deny incoming >/dev/null
  ufw default allow outgoing >/dev/null
  ufw allow "${SSH_PORT}/tcp" >/dev/null
  ufw --force enable >/dev/null

  # Key-only SSH, but only when it cannot lock the owner out: at least one login account must
  # already hold an authorized key.
  admin_keys=0
  root_keys=0
  while IFS=: read -r name _ uid _ _ home _; do
    [[ "${uid}" =~ ^[0-9]+$ ]] || continue
    if [[ "${name}" == "root" && -s "${home}/.ssh/authorized_keys" ]]; then
      root_keys=1
    elif [[ "${uid}" -ge 1000 && "${uid}" -lt 60000 && "${name}" != "${APP_USER}" \
      && -s "${home}/.ssh/authorized_keys" ]]; then
      admin_keys=1
    fi
  done </etc/passwd

  if [[ "${admin_keys}" -eq 1 || "${root_keys}" -eq 1 ]]; then
    install -d -m 0755 /etc/ssh/sshd_config.d
    {
      echo "# Managed by infra/vps/setup.sh"
      echo "PasswordAuthentication no"
      echo "KbdInteractiveAuthentication no"
      if [[ "${admin_keys}" -eq 1 ]]; then
        echo "PermitRootLogin no"
      else
        echo "PermitRootLogin prohibit-password"
      fi
    } >/etc/ssh/sshd_config.d/99-smartcart.conf
    if sshd -t; then
      systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
      log "ssh: key-only login enforced"
    else
      rm -f /etc/ssh/sshd_config.d/99-smartcart.conf
      warn "sshd config test failed; the hardening drop-in was removed"
    fi
  else
    warn "no authorized_keys found for any login user: SSH hardening skipped (it would lock you out)"
    warn "create an admin user with your public key, then run this script again"
  fi
else
  log "hardening skipped (SMARTCART_SKIP_HARDENING=1)"
fi

log "done"
systemctl list-timers 'smartcart-*' --no-pager || true
