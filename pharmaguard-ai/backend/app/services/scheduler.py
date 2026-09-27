import os
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ..database.database import SessionLocal
from ..agents.inventory_agent.morning_intelligence_agent import morning_agent

logger = logging.getLogger("pharmaguard.scheduler")
scheduler = BackgroundScheduler()


def run_scheduled_morning_intelligence():
    """
    Background job triggered daily at pharmacy opening time (default: 07:30 AM).
    """
    pharmacy_id = os.getenv("DEFAULT_PHARMACY_ID", "PHARM-DLA-001")
    logger.info(f"🌅 [SCHEDULER] Triggering Morning Intelligence Cycle for {pharmacy_id}...")
    db = SessionLocal()
    try:
        result = morning_agent.execute_morning_cycle(pharmacy_id, db)
        logger.info(f"✅ [SCHEDULER] Morning Cycle completed: {result['cycle_id']} - {result['high_shortage_risks']} shortage alerts.")
    except Exception as e:
        logger.error(f"❌ [SCHEDULER] Morning Intelligence error: {str(e)}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    """Starts the background scheduler for automated opening time workflows."""
    if not scheduler.running:
        # Schedule daily at 07:30 AM
        trigger = CronTrigger(hour=7, minute=30)
        scheduler.add_job(
            run_scheduled_morning_intelligence,
            trigger=trigger,
            id="daily_morning_intelligence",
            replace_existing=True
        )
        scheduler.start()
        logger.info("⏰ [SCHEDULER] PharmaGuard Daily Scheduler active (07:30 AM daily).")


def shutdown_scheduler():
    """Shuts down background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
