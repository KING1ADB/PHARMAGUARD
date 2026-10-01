output "cloud_run_service_url" {
  description = "The live public HTTPS URL of the PharmaGuard AI Cloud Run service"
  value       = google_cloud_run_v2_service.backend_service.uri
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL PostgreSQL instance connection string"
  value       = google_sql_database_instance.postgres_instance.connection_name
}

output "memorystore_redis_host" {
  description = "Memorystore Redis primary host IP"
  value       = google_redis_instance.redis_cache.host
}

output "storage_bucket_name" {
  description = "Cloud Storage documents and assets bucket"
  value       = google_storage_bucket.documents_bucket.name
}

output "backup_bucket_name" {
  description = "Cloud Storage database backups bucket"
  value       = google_storage_bucket.backups_bucket.name
}

output "scheduler_job_name" {
  description = "Google Cloud Scheduler morning intelligence cron job"
  value       = google_cloud_scheduler_job.morning_intelligence_cron.name
}
