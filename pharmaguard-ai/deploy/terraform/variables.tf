variable "project_id" {
  description = "The Google Cloud Platform Project ID"
  type        = string
  default     = "pharmaguard-ai-prod"
}

variable "region" {
  description = "The primary GCP region for all infrastructure resources"
  type        = string
  default     = "europe-west1"
}

variable "db_password" {
  description = "PostgreSQL production database user password"
  type        = string
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT encryption secret key for production authentication"
  type        = string
  sensitive   = true
}

variable "scheduler_secret" {
  description = "Secret token for authenticating Google Cloud Scheduler HTTP triggers"
  type        = string
  sensitive   = true
}
