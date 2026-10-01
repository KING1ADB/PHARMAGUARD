# PharmaGuard AI — Google Cloud Operations Runbook

## 1. System Overview & SLOs

| Metric | Target SLO | Warning Threshold | Critical Incident Threshold |
| :--- | :--- | :--- | :--- |
| **API Availability** | 99.9% Uptime | < 99.5% over 1h | < 99.0% over 15m |
| **Morning Cycle Latency** | < 15.0s per pharmacy | > 25.0s | > 45.0s |
| **Cloud SQL Connections** | < 60% pool utilization | > 75% | > 90% |
| **Redis Memory Utilization** | < 50% of 2GB | > 75% | > 85% |
| **Agent Execution Success** | > 99.0% | < 97.0% | < 95.0% |

---

## 2. Daily Operational Runbooks

### Runbook 2.1: Checking System Health & Telemetry
```bash
# Check JSON System Health & Active Metrics
curl -s https://api.pharmaguard.ai/api/v1/monitoring/metrics | jq .

# Check Live Readiness Probe
curl -s https://api.pharmaguard.ai/api/v1/monitoring/readiness | jq .

# Query Prometheus Scraping Output
curl -s https://api.pharmaguard.ai/api/v1/monitoring/prometheus
```

### Runbook 2.2: Viewing Real-Time Logs in Cloud Logging
```bash
# Tail live logs for PharmaGuard Backend
gcloud logging tail 'resource.type="cloud_run_revision" AND resource.labels.service_name="pharmaguard-backend"'

# Filter for Agent Failures or Critical Alerts
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' --limit=50 --format=json
```

### Runbook 2.3: Manual Morning Intelligence Cycle Trigger
If a pharmacy's automated Cloud Scheduler job did not trigger or needs an on-demand re-run:
```bash
# Trigger for all active pharmacies
curl -X POST https://api.pharmaguard.ai/api/v1/scheduler/trigger-morning-intelligence \
  -H "X-Scheduler-Secret: $CLOUD_SCHEDULER_SECRET" \
  -H "Content-Type: application/json"

# Trigger for specific pharmacy
curl -X POST "https://api.pharmaguard.ai/api/v1/scheduler/trigger-morning-intelligence?pharmacy_id=PHARM-DLA-001" \
  -H "X-Scheduler-Secret: $CLOUD_SCHEDULER_SECRET" \
  -H "Content-Type: application/json"
```

---

## 3. Incident Response & Remediation

### Incident 3.1: Cloud Run Service Latency Spike / CrashLoop
**Symptoms:** Latency > 2.0s on general API endpoints or 502 Bad Gateway.
1. Check Cloud Run revisions and container restarts:
   ```bash
   gcloud run services describe pharmaguard-backend --region=europe-west1
   ```
2. Roll back immediately to the previous healthy revision:
   ```bash
   # List revisions
   gcloud run revisions list --service=pharmaguard-backend --region=europe-west1
   # Route 100% traffic to stable revision
   gcloud run services update-traffic pharmaguard-backend \
     --region=europe-west1 \
     --to-revisions=STABLE_REVISION_NAME=100
   ```
3. Check memory & CPU utilization; scale container limits if needed:
   ```bash
   gcloud run services update pharmaguard-backend \
     --region=europe-west1 \
     --cpu=4 --memory=8Gi --max-instances=30
   ```

### Incident 3.2: Database Connection Saturation
**Symptoms:** `TimeoutError: QueuePool limit of size 20 overflow 10 reached`.
1. Inspect active Postgres connections:
   ```bash
   gcloud sql connect pharmaguard-pg16-prod --user=postgres
   # SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
2. Terminate idle connections if locked:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'idle in transaction' AND state_change < current_timestamp - INTERVAL '5 minutes';
   ```
3. Adjust Cloud Run instance concurrency or increase PostgreSQL `max_connections` flag.

---

## 4. Secret & Credential Rotation

When rotating JWT secrets, WhatsApp API tokens, or SMTP keys:
1. Update the secret version in GCP Secret Manager:
   ```bash
   echo -n "NEW_SECRET_VALUE" | gcloud secrets versions add PHARMAGUARD_JWT_SECRET --data-file=-
   ```
2. Cloud Run automatically picks up new secret versions upon revision deployment or automatically if pinned to `:latest`.
3. Force a rolling restart of Cloud Run:
   ```bash
   gcloud run services update pharmaguard-backend --region=europe-west1
   ```
