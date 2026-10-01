terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Required GCP APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "redis.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "vpcaccess.googleapis.com",
    "artifactregistry.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com"
  ])
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# 2. Artifact Registry Repository
resource "google_artifact_registry_repository" "pharmaguard_repo" {
  location      = var.region
  repository_id = "pharmaguard-repo"
  description   = "Docker repository for PharmaGuard AI production container images"
  format        = "DOCKER"
  depends_on    = [google_project_service.required_apis]
}

# 3. Serverless VPC Access Connector (for Cloud Run to private Cloud SQL & Memorystore)
resource "google_vpc_access_connector" "serverless_connector" {
  name          = "pharmaguard-vpc-conn"
  region        = var.region
  ip_cidr_range = "10.8.0.0/28"
  network       = "default"
  min_instances = 2
  max_instances = 10
  depends_on    = [google_project_service.required_apis]
}

# 4. Cloud SQL PostgreSQL 16 Instance
resource "google_sql_database_instance" "postgres_instance" {
  name             = "pharmaguard-pg16-prod"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier              = "db-custom-2-7680" # 2 vCPU, 7.5GB RAM
    availability_type = "REGIONAL"         # High Availability (Multi-Zone)
    disk_size         = 50
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "02:00"
      transaction_log_retention_days = 7
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
    }

    database_flags {
      name  = "max_connections"
      value = "200"
    }
  }
  deletion_protection = true
  depends_on          = [google_project_service.required_apis]
}

resource "google_sql_database" "database" {
  name     = "pharmaguard_prod"
  instance = google_sql_database_instance.postgres_instance.name
}

resource "google_sql_user" "db_user" {
  name     = "pharmaguard_app"
  instance = google_sql_database_instance.postgres_instance.name
  password = var.db_password
}

# 5. Memorystore Redis 7 Instance
resource "google_redis_instance" "redis_cache" {
  name           = "pharmaguard-redis-prod"
  tier           = "STANDARD_HA" # Highly Available Multi-Zone Redis
  memory_size_gb = 2
  region         = var.region
  redis_version  = "REDIS_7_0"
  depends_on     = [google_project_service.required_apis]
}

# 6. Cloud Storage Buckets (Documents & Backups)
resource "google_storage_bucket" "documents_bucket" {
  name          = "${var.project_id}-storage"
  location      = var.region
  force_destroy = false
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

resource "google_storage_bucket" "backups_bucket" {
  name          = "${var.project_id}-backups"
  location      = var.region
  force_destroy = false
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }
}

# 7. Dedicated Service Account & IAM
resource "google_service_account" "app_sa" {
  account_id   = "pharmaguard-runner"
  display_name = "PharmaGuard AI Cloud Run Execution Service Account"
}

resource "google_project_iam_member" "sa_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "sa_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "sa_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# 8. Secret Manager Secrets
resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "PHARMAGUARD_JWT_SECRET"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "jwt_secret_val" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = var.jwt_secret
}

resource "google_secret_manager_secret" "db_url" {
  secret_id = "PHARMAGUARD_DATABASE_URL"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_url_val" {
  secret      = google_secret_manager_secret.db_url.id
  secret_data = "postgresql+psycopg2://${google_sql_user.db_user.name}:${var.db_password}@/${google_sql_database.database.name}?host=/cloudsql/${google_sql_database_instance.postgres_instance.connection_name}"
}

# 9. Cloud Run Backend Service
resource "google_cloud_run_v2_service" "backend_service" {
  name     = "pharmaguard-backend"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.app_sa.email

    scaling {
      min_instance_count = 1
      max_instance_count = 20
    }

    vpc_access {
      connector = google_vpc_access_connector.serverless_connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres_instance.connection_name]
      }
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/pharmaguard-repo/pharmaguard-backend:latest"

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "REDIS_URL"
        value = "redis://${google_redis_instance.redis_cache.host}:${google_redis_instance.redis_cache.port}/0"
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.documents_bucket.name
      }
      env {
        name  = "USE_LOCAL_STORAGE_FALLBACK"
        value = "false"
      }
      env {
        name  = "ENABLE_SIMULATION_FEATURES"
        value = "false"
      }
      env {
        name  = "CLOUD_SCHEDULER_SECRET"
        value = var.scheduler_secret
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.db_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "JWT_SECRET_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8000
        }
        initial_delay_seconds = 10
        period_seconds        = 15
      }

      startup_probe {
        http_get {
          path = "/api/v1/monitoring/readiness"
          port = 8000
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        failure_threshold     = 10
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_sql_database_instance.postgres_instance,
    google_redis_instance.redis_cache
  ]
}

# 10. Public Access Binding for Cloud Run
resource "google_cloud_run_service_iam_member" "public_access" {
  location = google_cloud_run_v2_service.backend_service.location
  service  = google_cloud_run_v2_service.backend_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# 11. Cloud Scheduler Cron Job (Daily 07:00 AM Douala Time)
resource "google_cloud_scheduler_job" "morning_intelligence_cron" {
  name             = "pharmaguard-morning-intelligence-daily"
  description      = "Daily autonomous morning intelligence agent trigger"
  schedule         = "0 7 * * *" # Every day at 07:00 AM
  time_zone        = "Africa/Douala"
  attempt_deadline = "300s"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.backend_service.uri}/api/v1/scheduler/trigger-morning-intelligence"
    headers = {
      "X-Scheduler-Secret" = var.scheduler_secret
      "Content-Type"       = "application/json"
    }
  }

  depends_on = [google_cloud_run_v2_service.backend_service]
}
