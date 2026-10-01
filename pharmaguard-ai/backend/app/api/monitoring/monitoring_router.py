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
