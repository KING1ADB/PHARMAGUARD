# PharmaGuard AI — Production Deployment Guide

**Target Environment:** Bare-Metal Linux, AWS EC2 / ECS, Google Cloud Run, DigitalOcean  
**Version:** 1.0.0 (Production Live)

---

## 1. Prerequisites

- Linux host (Ubuntu 22.04 LTS recommended)
- Docker 24.0+ & Docker Compose v2+
- Domain name with DNS pointed to host (e.g., `api.pharmaguard.ai`, `app.pharmaguard.ai`)
- SSL certificates (Let's Encrypt / Certbot)

---

## 2. Quick Deployment (Docker Compose)

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/KING1ADB/PHARMAGUARD.git
cd PHARMAGUARD/pharmaguard-ai

# Copy production environment template
cp .env.production.example .env.production

# Edit production credentials
nano .env.production
```

### Step 2: Generate SSL Certificates
```bash
mkdir -p nginx/ssl
# Copy fullchain.pem and privkey.pem to nginx/ssl/
```

### Step 3: Launch Production Stack
```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

### Step 4: Verify Deployment Health
```bash
curl -f http://localhost:8000/health
# Response: {"status": "HEALTHY", "environment": "production", "agent_status": "ACTIVE", "scheduler_status": "RUNNING"}
```

---

## 3. Production Verification Checklist

- [x] Application health check returns `HTTP 200 HEALTHY`.
- [x] Nginx reverse proxy enforces HTTPS and security headers.
- [x] Multi-worker Uvicorn processes handle concurrent requests.
- [x] PostgreSQL connection pool actively manages database connections.
- [x] Background morning intelligence scheduler runs at opening time.
- [x] Simulation and demo sandboxes are disabled in production mode.
