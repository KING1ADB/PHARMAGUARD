import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...database.database import get_db
from ...monitoring.agent_reliability_monitor import agent_reliability_monitor

logger = logging.getLogger("PharmaGuard.MonitoringRouter")
router = APIRouter(prefix="/monitoring", tags=["AI Reliability & Production Telemetry"])


@router.get("/metrics")
def get_system_telemetry_endpoint(db: Session = Depends(get_db)):
    """Returns JSON system reliability, latency, and uptime telemetry."""
    return agent_reliability_monitor.get_system_reliability_metrics(db)


@router.get("/prometheus")
def get_prometheus_metrics_endpoint(db: Session = Depends(get_db)):
    """Exposes Prometheus scraping endpoint for Grafana/Prometheus collectors."""
    metrics_str = agent_reliability_monitor.generate_prometheus_metrics(db)
    return Response(content=metrics_str, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/readiness")
def get_production_readiness_probe(db: Session = Depends(get_db)):
    """
    Comprehensive Kubernetes/Cloud Run startup and readiness probe.
    Verifies PostgreSQL, Redis Memorystore, Google Cloud Storage,
    Secret Manager, and Notification channel configuration.
    """
    from ...services.gcp.cloud_storage_service import gcs_service
    from ...services.gcp.redis_cache_service import redis_service
    from ...services.gcp.secret_manager_service import secret_manager_service
    from ...core.config import settings

    # Check Database
    db_healthy = False
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_healthy = True
    except Exception as e:
        logger.error(f"Readiness check: DB failed: {e}")

    # Check Redis
    redis_health = redis_service.check_health()

    # Check GCS
    gcs_health = gcs_service.check_health()

    # Check Secret Manager
    secret_health = secret_manager_service.check_health()

    # Overall system readiness
    is_ready = db_healthy and redis_health.get("healthy", False) and gcs_health.get("healthy", False)

    return {
        "status": "READY" if is_ready else "DEGRADED",
        "timestamp": agent_reliability_monitor._get_uptime_seconds(),
        "app_env": settings.APP_ENV,
        "checks": {
            "database": {"healthy": db_healthy, "type": "PostgreSQL" if "postgresql" in settings.DATABASE_URL else "SQLite"},
            "redis_memorystore": redis_health,
            "cloud_storage": gcs_health,
            "secret_manager": secret_health,
            "notifications": {
                "whatsapp_configured": bool(settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN),
                "email_configured": bool(settings.SMTP_HOST and settings.SMTP_USERNAME),
                "sms_configured": bool(settings.SMS_API_KEY)
            }
        }
    }

