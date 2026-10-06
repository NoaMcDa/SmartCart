terraform {
  required_version = ">= 1.6"

  required_providers {
    # Managed Postgres (project only; extensions and roles are SQL, see docs/infra-provisioning.md).
    supabase = {
      source  = "supabase/supabase"
      version = "~> 1.0"
    }
    # Object storage for the raw archive (R2). For AWS S3 swap in the hashicorp/aws provider.
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
    # VPS. Chosen because it operates an Israeli datacenter; see the provider comparison in
    # docs/infra-provisioning.md section 5. Swap this block if you pick another provider.
    kamatera = {
      source  = "Kamatera/kamatera"
      version = "~> 0.8"
    }
  }
}
