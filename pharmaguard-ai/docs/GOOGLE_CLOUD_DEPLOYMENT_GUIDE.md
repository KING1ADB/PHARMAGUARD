# PharmaGuard AI — Google Cloud Production Deployment Guide

## 1. Executive Summary & Target Architecture

PharmaGuard AI is deployed as a resilient, enterprise-grade cloud-native service on **Google Cloud Platform (GCP)**. The architecture adheres to high availability (HA), zero-trust security, strict data isolation, and automated multi-agent scheduling.

```
                  +---------------------------------------------------+
                  |            Google Cloud Load Balancer             |
                  |                (SSL Termination)                  |
                  +-------------------------+-------------------------+
                                            |
                                            v
+-----------------------+        +--------------------------+        +------------------------+
| Google Cloud Scheduler|------->|     Google Cloud Run     |<-------|  WhatsApp Business API |
| (Daily 07:00 AM Cron) | (OIDC) |   (PharmaGuard Backend)  | (WebH) |  & Pharmacist Clients  |
+-----------------------+        +-------------+------------+        +------------------------+
                                               |
                  +----------------------------+----------------------------+
                  | (Serverless VPC Access Connector: 10.8.0.0/28)          |
                  v                                                         v
+-----------------------------------+                     +-----------------------------------+
|     Cloud SQL PostgreSQL 16       |                     |     Memorystore Redis 7 (HA)      |
|  (Regional HA, SSD, Encrypted)    |                     | (Distributed Lock & Cache Store)  |
+-----------------------------------+                     +-----------------------------------+
                  |                                                         |
                  +----------------------------+----------------------------+
                                               |
                                               v
                          +------------------------------------------+
                          |        Google Cloud Storage (GCS)        |
                          |  - pharmaguard-prod-storage (Docs/PDFs)  |
                          |  - pharmaguard-prod-backups (Gzip Dumps) |
                          +------------------------------------------+
```

---

## 2. Infrastructure Components

| GCP Component | Configuration & Tier | Purpose |
| :--- | :--- | :--- |
| **Cloud Run** | 2 vCPU, 4GB RAM, Min 1, Max 20 instances, Concurrency 80 | Serverless backend executing FastAPI, Multi-Agent Orchestrator, and APIs |
| **Cloud SQL** | PostgreSQL 16, Regional HA, `db-custom-2-7680`, SSD | Multi-tenant transactional database storing inventories, audit logs, and memories |
| **Memorystore** | Redis 7.0, Standard Tier (HA), 2GB RAM | Distributed locking for agent cron runs and rapid sub-millisecond caching |
| **Cloud Storage** | Dual-region, Object Versioning, Nearline lifecycle | Purchase order documents, CSV/Excel ingestion blobs, and `.gz` database snapshots |
| **Secret Manager** | Encrypted secrets (`DATABASE_URL`, `JWT_SECRET`, `WHATSAPP_TOKEN`) | Externalized production credential injection without hardcoding |
| **Cloud Scheduler** | `0 7 * * *` (07:00 AM Africa/Douala) HTTP Target with Secret Header | Autonomous trigger for the Morning Intelligence Agent cycle |
| **Cloud Monitoring** | Custom Metrics, Prometheus Scraping, Uptime Probes | Real-time agent latency, SLI/SLO tracking, error alerting |

---

## 3. Step-by-Step Deployment Procedure

### Step 3.1: GCP Project Initialization & Service APIs
```bash
# Set default project
gcloud config set project pharmaguard-ai-prod
export REGION="europe-west1"

# Enable essential GCP APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  redis.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  vpcaccess.googleapis.com \
  artifactregistry.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com
```

### Step 3.2: Create Artifact Registry Docker Repository
```bash
gcloud artifacts repositories create pharmaguard-repo \
  --repository-format=docker \
  --location=$REGION \
  --description="PharmaGuard AI Production Container Registry"
```

### Step 3.3: Provision Infrastructure with Terraform
```bash
cd deploy/terraform
terraform init
terraform plan -out=tfplan \
  -var="project_id=pharmaguard-ai-prod" \
  -var="region=europe-west1" \
  -var="db_password=REPLACE_WITH_STRONG_DB_PASSWORD" \
  -var="jwt_secret=REPLACE_WITH_256_BIT_JWT_SECRET" \
  -var="scheduler_secret=REPLACE_WITH_SCHEDULER_SECRET"

terraform apply tfplan
```

---

## 4. Secret Manager Configuration

All confidential keys must be populated in Google Cloud Secret Manager:

```bash
# 1. Database Connection String
gcloud secrets create PHARMAGUARD_DATABASE_URL --data-file=- <<EOF
postgresql+psycopg2://pharmaguard_app:DB_PASSWORD@/pharmaguard_prod?host=/cloudsql/pharmaguard-ai-prod:europe-west1:pharmaguard-pg16-prod
EOF

# 2. JWT Production Secret
gcloud secrets create PHARMAGUARD_JWT_SECRET --data-file=- <<EOF
YOUR_CRYPTOGRAPHICALLY_SECURE_JWT_SECRET_2026
EOF

# 3. WhatsApp Business Cloud API Access Token
gcloud secrets create PHARMAGUARD_WHATSAPP_TOKEN --data-file=- <<EOF
EAA...YOUR_META_GRAPH_API_SYSTEM_USER_TOKEN
EOF

# 4. Transactional SMTP Password
gcloud secrets create PHARMAGUARD_SMTP_PASSWORD --data-file=- <<EOF
SG.YOUR_SENDGRID_OR_SMTP_PASSWORD
EOF
```

---

## 5. Automated CI/CD Deployment with GitHub Actions

The repository includes a production workflow [`.github/workflows/deploy_gcp.yml`](file:///c:/Users/adbki/Documents/PharmGuard/PHARMAGUARD/pharmaguard-ai/.github/workflows/deploy_gcp.yml).

### Required GitHub Repository Secrets:
* `GCP_PROJECT_ID`: `pharmaguard-ai-prod`
* `GCP_REGION`: `europe-west1`
* `GCP_SA_KEY`: JSON service account key for `pharmaguard-runner` with Cloud Run, Storage, and Secret Manager permissions.
* `CLOUD_SCHEDULER_SECRET`: Token shared with Cloud Scheduler.

### Pipeline Stages:
1. **Automated Unit & Integration Testing:** Executes all test suites across agents, security, and connectors (100% pass required).
2. **Container Build & Push:** Builds multi-stage non-root container to Google Artifact Registry.
3. **Zero-Downtime Deployment:** Deploys new revision to Google Cloud Run with VPC Connector, Cloud SQL socket mount, and Secret Manager references.
4. **Smoke & Readiness Testing:** Runs [`scripts/verify_gcp_deployment.py`](file:///c:/Users/adbki/Documents/PharmGuard/PHARMAGUARD/pharmaguard-ai/scripts/verify_gcp_deployment.py) against live URLs.
5. **Automated Rollback:** If smoke verification fails, traffic instantly reverts 100% to the previous healthy revision.

---

## 6. Verification and Health Checks

Post-deployment, execute the smoke verification script:
```bash
python scripts/verify_gcp_deployment.py --url https://pharmaguard-backend-xyz.a.run.app --secret "$CLOUD_SCHEDULER_SECRET"
```
Expected output:
```
✅ [PASS] Root Endpoint (200 OK)
✅ [PASS] Health Endpoint (200 OK)
✅ [PASS] Production Readiness Probe (READY)
    - Database Healthy: True
    - Redis Memorystore: True
    - Cloud Storage: True
✅ [PASS] Prometheus Metrics Scraping Endpoint (200 OK)
✅ [PASS] Cloud Scheduler Target Endpoint (200 OK)
✅ [PASS] Production Isolation: Demo/Simulation routes safely protected/isolated
```
