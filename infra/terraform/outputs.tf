output "supabase_project_id" {
  description = "Supabase project reference. Connection strings are built from it in the dashboard."
  value       = supabase_project.main.id
}

output "r2_bucket_name" {
  description = "Bucket name for the S3_BUCKET variable."
  value       = cloudflare_r2_bucket.raw_archive.name
}

output "vps_public_ips" {
  description = "Public IPs of the ingestion VPS. Verify the country with infra/smoke/check_israeli_ip.sh."
  value       = kamatera_server.ingest.public_ips
}
