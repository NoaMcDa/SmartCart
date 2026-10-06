# No real values live in this repository. Supply secrets as TF_VAR_<name> environment variables
# (the names are listed in .env.example) and non-secret choices in a terraform.tfvars that you keep
# out of git (see terraform.tfvars.example).

# --- Supabase ----------------------------------------------------------------------------------
variable "supabase_access_token" {
  description = "Supabase personal access token (account settings, access tokens)."
  type        = string
  sensitive   = true
}

variable "supabase_organization_id" {
  description = "Supabase organization slug that will own the project."
  type        = string
}

variable "supabase_database_password" {
  description = "Password of the postgres superuser. Generate a long random value; never reuse it."
  type        = string
  sensitive   = true
}

variable "supabase_project_name" {
  description = "Project name."
  type        = string
  default     = "smartcart"
}

variable "supabase_region" {
  description = "Supabase region code. There is no Israeli region; pick the nearest and measure latency from the VPS (estimate: eu-central-1)."
  type        = string
  default     = "eu-central-1"
}

# --- Object storage (Cloudflare R2) -----------------------------------------------------------
variable "cloudflare_api_token" {
  description = "Cloudflare API token allowed to edit R2 buckets in the account."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account id that owns the bucket."
  type        = string
}

variable "r2_bucket_name" {
  description = "Name of the raw-archive bucket."
  type        = string
  default     = "smartcart-raw-archive"
}

variable "r2_location" {
  description = "R2 location hint (for example eeur for Eastern Europe, weur for Western Europe)."
  type        = string
  default     = "eeur"
}

# --- VPS (Kamatera) ---------------------------------------------------------------------------
variable "kamatera_api_client_id" {
  description = "Kamatera API client id."
  type        = string
  sensitive   = true
}

variable "kamatera_api_secret" {
  description = "Kamatera API secret."
  type        = string
  sensitive   = true
}

variable "vps_name" {
  description = "Server name."
  type        = string
  default     = "smartcart-ingest"
}

variable "vps_datacenter_country" {
  description = "Country of the datacenter. Must be one where the public IP geolocates to Israel."
  type        = string
  default     = "Israel"
}

variable "vps_cpu_cores" {
  description = "vCPU count. Ingestion is I/O bound; two cores is the planned size (estimate)."
  type        = number
  default     = 2
}

variable "vps_ram_mb" {
  description = "RAM in MB. 2048 to 4096 is the planned size (estimate)."
  type        = number
  default     = 4096
}

variable "vps_disk_gb" {
  description = "System disk in GB. Raw files go to the bucket, so this stays small."
  type        = number
  default     = 40
}

variable "ssh_public_key" {
  description = "Public key (one line) for the admin account. Password login is disabled by infra/vps/setup.sh."
  type        = string
}
