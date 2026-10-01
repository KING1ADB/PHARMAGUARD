# PharmaGuard AI — Administrator Operations Manual

**Target Audience:** DevOps Engineers, Platform Administrators, Site Reliability Engineers  
**System Version:** 1.0.0 (Production Live)

---

## 1. System Architecture & Topology

PharmaGuard AI operates as a containerized, asynchronous AI agent platform:

- **Reverse Proxy:** Nginx with TLSv1.3 SSL termination, rate-limiting (20 req/sec), and HTTP/2.
- **Application Server:** FastAPI running under Uvicorn multi-worker daemon (`gunicorn -w 4 -k uvicorn.workers.UvicornWorker`).
- **Relational Store:** PostgreSQL 16 with connection pooling (`pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`).
- **Asynchronous Task Broker:** Background autonomous APScheduler daemon.
- **Monitoring & Metrics:** Native Prometheus exporter (`/api/v1/monitoring/prometheus`) + JSON telemetry endpoint (`/api/v1/monitoring/metrics`).

---

## 2. Managing Autonomous Scheduler

The morning intelligence scheduler runs inside the application lifespan.

### Verifying Scheduler Status
```bash
curl -s http://localhost:8000/api/v1/monitoring/metrics | jq '.system_health.background_scheduler'
# Expected output: "ACTIVE"
```

### Manual Trigger for Emergency Testing / Calibration
```bash
curl -X POST http://localhost:8000/api/v1/agent/trigger-morning-cycle \
  -H "Authorization: Bearer <ADMIN_OR_OWNER_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"pharmacy_id": "PHARM-DLA-001"}'
```

---

## 3. Database Maintenance & Backups

### Automated Nightly Backups
Backups are triggered via cron or the Python backup utility:
```bash
# Execute backup
python scripts/backup_db.py

# Backups are compressed into gzip and stored in /backups/
ls -lh backups/
```

### Restoring PostgreSQL Database
```bash
gunzip -c backups/pg_backup_20261001_020000.sql.gz | psql -U pharmaguard_user -d pharmaguard_prod
```

---

## 4. Telemetry & Observability

- **Health Check Endpoint:** `GET /health` $\to$ Returns HTTP 200 with service health and environment status.
- **System Telemetry:** `GET /api/v1/monitoring/metrics` $\to$ Returns uptime, execution success rate, and average latency.
- **Prometheus Scraping Target:** `GET /api/v1/monitoring/prometheus` $\to$ Exposes standard metrics (`pharmaguard_uptime_seconds`, `pharmaguard_agent_actions_total`, `pharmaguard_alerts_total`, `pharmaguard_purchase_orders_total`).
