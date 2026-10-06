# Skeleton, not yet applied and not yet validated against live providers. Before the first apply:
#   terraform init && terraform validate && terraform plan
# Data source and argument names of the Kamatera provider in particular must be confirmed against
# its current documentation (marked TODO below). Nothing here holds a secret.

provider "supabase" {
  access_token = var.supabase_access_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "kamatera" {
  api_client_id = var.kamatera_api_client_id
  api_secret    = var.kamatera_api_secret
}

# --- Supabase project (Postgres 16 is the platform default for new projects: confirm in the dashboard)
resource "supabase_project" "main" {
  organization_id   = var.supabase_organization_id
  name              = var.supabase_project_name
  database_password = var.supabase_database_password
  region            = var.supabase_region

  lifecycle {
    # The password is set once; rotate it in the dashboard, not through Terraform.
    ignore_changes = [database_password]
  }
}

# Enabling postgis and vector, creating roles and the schema are SQL, not Terraform:
# see docs/infra-provisioning.md sections 2 and 3 and infra/smoke/db_smoke.sql.

# --- Raw archive bucket ------------------------------------------------------------------------
resource "cloudflare_r2_bucket" "raw_archive" {
  account_id = var.cloudflare_account_id
  name       = var.r2_bucket_name
  location   = var.r2_location
}

# The least-privilege API tokens (one writer for ingestion, one admin for cleanup) are created in
# the Cloudflare dashboard: docs/infra-provisioning.md section 6. The lifecycle (retention) rule is
# set there too, or with the Cloudflare API, because provider support for R2 lifecycle varies by
# version.

# --- Ingestion VPS -----------------------------------------------------------------------------
# TODO: confirm data source arguments in the Kamatera provider documentation.
data "kamatera_datacenter" "israel" {
  country = var.vps_datacenter_country
}

data "kamatera_image" "ubuntu" {
  datacenter_id = data.kamatera_datacenter.israel.id
  os            = "Ubuntu"
  code          = "24.04 64bit"
}

resource "kamatera_server" "ingest" {
  name          = var.vps_name
  datacenter_id = data.kamatera_datacenter.israel.id
  image_id      = data.kamatera_image.ubuntu.id

  cpu_type      = "B"
  cpu_cores     = var.vps_cpu_cores
  ram_mb        = var.vps_ram_mb
  disk_sizes_gb = [var.vps_disk_gb]
  billing_cycle = "monthly"
  ssh_pubkey    = var.ssh_public_key

  network {
    name = "wan"
  }
}
