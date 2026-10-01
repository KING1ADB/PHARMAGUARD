import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ...core.config import settings
from ...database.database import get_db
from ...database.models.entities import Pharmacy
from ...agents.inventory_agent.morning_intelligence_agent import morning_agent
from ...services.gcp.redis_cache_service import redis_service
from ...monitoring.agent_reliability_monitor import agent_reliability_monitor

logger = logging.getLogger("pharmaguard.gcp.scheduler")

scheduler_router = APIRouter(prefix="/scheduler", tags=["Google Cloud Scheduler"])


def verify_cloud_scheduler_auth(
    x_cloudscheduler: Optional[str] = Header(None, alias="X-CloudScheduler"),
    authorization: Optional[str] = Header(None),
    x_scheduler_secret: Optional[str] = Header(None, alias="X-Scheduler-Secret")
):
    """
    Validates that incoming requests originate from Google Cloud Scheduler.
    Checks either standard Cloud Scheduler HTTP header with secret or Bearer token matching CLOUD_SCHEDULER_SECRET.
    """
    expected_secret = settings.CLOUD_SCHEDULER_SECRET

    # Direct secret header check
    if x_scheduler_secret and x_scheduler_secret == expected_secret:
        return True

    # Authorization Bearer check
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1] == expected_secret:
            return True

    # In development/test environments, allow header if secret not strictly enforced
    if settings.APP_ENV in ["development", "test"] and (x_cloudscheduler or x_scheduler_secret):
        return True

    logger.warning("Unauthorized attempt to trigger Cloud Scheduler endpoint.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized Cloud Scheduler trigger. Invalid credentials."
    )


@scheduler_router.get("/health")
def cloud_scheduler_health():
    """Healthcheck endpoint specifically for Cloud Scheduler probe."""
    return {
        "status": "HEALTHY",
        "service": "Google Cloud Scheduler Target",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cron_schedule": "0 7 * * * (07:00 AM Daily)",
        "timezone": "Africa/Douala"
    }


@scheduler_router.post("/trigger-morning-intelligence")
def trigger_scheduled_morning_intelligence(
    pharmacy_id: Optional[str] = None,
    auth_verified: bool = Depends(verify_cloud_scheduler_auth),
    db: Session = Depends(get_db)
):
    """
    Autonomous Morning Intelligence Agent endpoint triggered daily by Google Cloud Scheduler.
    Executes multi-agent risk detection, stockout prediction, and procurement draft generation.
    Uses Redis distributed locks to ensure idempotency across multiple Cloud Run replicas.
    """
    lock_key = f"morning_cycle_{pharmacy_id or 'all_active'}_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    
    # Acquire distributed lock for 10 minutes to prevent duplicate executions
    lock_acquired = redis_service.acquire_distributed_lock(lock_key, lock_timeout_seconds=600)
    if not lock_acquired and settings.APP_ENV == "production":
        logger.warning(f"Morning intelligence cycle already executing or executed today for {lock_key}.")
        return {
            "status": "SKIPPED_IDEMPOTENT",
            "message": "Morning intelligence cycle is already executing or completed today.",
            "lock_key": lock_key
        }

    start_time = datetime.now(timezone.utc)
    results = []

    try:
        # Determine target pharmacies
        if pharmacy_id:
            pharmacies = db.query(Pharmacy).filter(Pharmacy.id == pharmacy_id).all()
        else:
            pharmacies = db.query(Pharmacy).all()

        if not pharmacies:
            # Fallback to default
            pharmacies = [Pharmacy(id="PHARM-DLA-001", organization_name="Pharmacie du Centre")]

        for pharm in pharmacies:
            try:
                cycle_result = morning_agent.execute_morning_cycle(
                    pharmacy_id=pharm.id,
                    db=db
                )
                results.append({
                    "pharmacy_id": pharm.id,
                    "organization_name": pharm.organization_name,
                    "status": "COMPLETED",
                    "alerts_count": cycle_result.get("alerts_count", len(cycle_result.get("alerts", []))),
                    "recommendations_count": cycle_result.get("recommendations_count", len(cycle_result.get("recommendations", []))),
                    "report_id": cycle_result.get("report_id")
                })
            except Exception as pharm_err:
                logger.error(f"Error executing morning cycle for pharmacy {pharm.id}: {pharm_err}")
                results.append({
                    "pharmacy_id": pharm.id,
                    "status": "FAILED",
                    "error": str(pharm_err)
                })

        return {
            "status": "SUCCESS",
            "trigger_source": "GOOGLE_CLOUD_SCHEDULER",
            "executed_at": start_time.isoformat(),
            "pharmacies_processed": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Scheduled morning intelligence execution failed: {e}")
        agent_reliability_monitor.record_agent_execution(
            agent_name="MorningSchedulerTrigger",
            duration_ms=0,
            success=False,
            error_message=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scheduled morning agent failure: {str(e)}"
        )
