# PharmaGuard AI — Disaster Recovery & Business Continuity Procedure

## 1. Objectives & Recovery Targets

| Metric | Target SLA | Strategy |
| :--- | :--- | :--- |
| **Recovery Point Objective (RPO)** | **< 15 Minutes** | Automated Cloud SQL Continuous WAL Archiving + Point-in-Time Recovery (PITR) + Hourly Database GCS Snapshots |
| **Recovery Time Objective (RTO)** | **< 30 Minutes** | Serverless Multi-Zone Cloud Run Auto-Healing + Regional Failover with Terraform Infrastructure as Code |

---

## 2. Disaster Scenarios & Recovery Workflows

### Scenario 2.1: Database Corruption or Accidental Data Deletion
**Objective:** Restore PostgreSQL to a specific timestamp prior to corruption.

#### Procedure:
1. Identify the exact corruption timestamp (e.g., `2026-10-01T14:30:00Z`).
2. Restore Cloud SQL to Point-in-Time (PITR):
   ```bash
   gcloud sql instances clone pharmaguard-pg16-prod pharmaguard-pg16-restored \
     --point-in-time="2026-10-01T14:28:00Z" \
     --region=europe-west1
   ```
3. Update Secret Manager `PHARMAGUARD_DATABASE_URL` with the restored instance connection:
   ```bash
   NEW_URL="postgresql+psycopg2://pharmaguard_app:SECURE_PASS@/pharmaguard_prod?host=/cloudsql/pharmaguard-ai-prod:europe-west1:pharmaguard-pg16-restored"
   echo -n "$NEW_URL" | gcloud secrets versions add PHARMAGUARD_DATABASE_URL --data-file=-
   ```
4. Restart Cloud Run to establish connections with the restored database:
   ```bash
   gcloud run services update pharmaguard-backend --region=europe-west1
   ```
5. Run deployment verification:
   ```bash
   python scripts/verify_gcp_deployment.py --url https://api.pharmaguard.ai
   ```

---

### Scenario 2.2: Total Regional GCP Outage (Failover to Secondary Region)
**Primary Region:** `europe-west1` (Belgium)  
**Secondary DR Region:** `europe-west4` (Netherlands) or `africa-south1` (Johannesburg)

#### Procedure:
1. Trigger Terraform DR deployment in secondary region:
   ```bash
   cd deploy/terraform
   terraform apply \
     -var="region=europe-west4" \
     -var="project_id=pharmaguard-ai-prod" \
     -var="db_password=$PROD_DB_PASS" \
     -var="jwt_secret=$PROD_JWT_SECRET" \
     -var="scheduler_secret=$PROD_SCHEDULER_SECRET"
   ```
2. Restore latest automated `.gz` database snapshot from GCS bucket:
   ```bash
   # Download latest backup
   gsutil cp gs://pharmaguard-ai-prod-backups/latest_backup.sql.gz .
   gunzip latest_backup.sql.gz
   
   # Import into secondary Cloud SQL instance
   gcloud sql import sql pharmaguard-pg16-prod gs://pharmaguard-ai-prod-backups/latest_backup.sql.gz \
     --database=pharmaguard_prod
   ```
3. Switch Global Load Balancer backend service traffic to secondary Cloud Run endpoint:
   ```bash
   gcloud compute backend-services update pharmaguard-lb-backend \
     --global \
     --custom-request-header="X-DR-Region: europe-west4"
   ```
4. Verify all endpoints at `https://api.pharmaguard.ai/api/v1/monitoring/readiness`.

---

## 3. Automated Database Backup & Retention Policy

### Backup Schedule:
1. **Automated GCP Native Daily Backups:** Retained for 30 days with PITR transaction logs enabled.
2. **Scheduled Export to GCS:** Daily compressed SQL export executed at 03:00 AM UTC stored in `gs://pharmaguard-ai-prod-backups/`.
3. **Backup Script ([`scripts/backup_db.py`](file:///c:/Users/adbki/Documents/PharmGuard/PHARMAGUARD/pharmaguard-ai/scripts/backup_db.py)):** Supports encrypted upload directly to GCS bucket with 90-day lifecycle auto-pruning.

### Testing Disaster Recovery:
DR restoration tests are conducted **quarterly** in an isolated staging project to validate RTO and RPO metrics.
