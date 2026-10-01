import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database.database import init_db, get_db
from .services.scheduler import start_scheduler, shutdown_scheduler
from .api.authentication.auth_router import router as auth_router
from .api.pharmacy.pharmacy_router import router as pharmacy_router
from .api.inventory.inventory_router import router as inventory_router
from .api.agent.agent_router import router as agent_router
from .api.integrations.whatsapp_router import router as whatsapp_router
from .api.action_center.action_center_router import router as action_center_router
from .api.evaluation.evaluation_router import router as evaluation_router
from .api.intelligence.intelligence_router import router as intelligence_router
from .api.system.system_router import router as system_router
from .api.onboarding.onboarding_router import router as onboarding_router
from .api.pilot.pilot_router import router as pilot_router
from .api.dashboard.pilot_dashboard_router import router as pilot_dashboard_router
from .api.command_center.command_center_router import router as command_center_router
from .api.interaction.interaction_router import router as interaction_router
from .api.simulation.simulation_router import router as simulation_router
from .api.demo.demo_router import router as demo_router
from .api.pilot_metrics.pilot_measurement_router import router as pilot_measurement_router
from .api.reports.pilot_reporting_router import router as pilot_reporting_router
from .api.evidence.evidence_router import router as evidence_router
from .api.monitoring.monitoring_router import router as monitoring_router
from .core.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("PharmaGuard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables (clean in production; seeded in dev)
    logger.info(f"Initializing PharmaGuard AI Database [Environment: {settings.APP_ENV}]...")
    init_db()
    
    # Start the Autonomous Background Scheduler (Morning Intelligence Agent)
    logger.info("Starting Autonomous Workflow Scheduler (Morning Intelligence Agent)...")
    start_scheduler()
    
    yield
    
    # Shutdown: Stop Scheduler
    logger.info("Shutting down PharmaGuard AI Scheduler...")
    shutdown_scheduler()


app = FastAPI(
    title="PharmaGuard AI — Autonomous Pharmacy Operations Agent",
    description=(
        "Production AI agent platform operating as an autonomous pharmacy intelligence employee. "
        "Continuously observes stock levels, reasons on stock coverage and expiry risks, stages procurement, "
        "and learns from pharmacist decisions."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Enable CORS using production settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Core Production API routers with v1 prefix
api_prefix = settings.API_V1_PREFIX
app.include_router(auth_router, prefix=api_prefix)
app.include_router(pharmacy_router, prefix=api_prefix)
app.include_router(inventory_router, prefix=api_prefix)
app.include_router(agent_router, prefix=api_prefix)
app.include_router(whatsapp_router, prefix=api_prefix)
app.include_router(action_center_router, prefix=api_prefix)
app.include_router(evaluation_router, prefix=api_prefix)
app.include_router(intelligence_router, prefix=api_prefix)
app.include_router(system_router, prefix=api_prefix)
app.include_router(onboarding_router, prefix=api_prefix)
app.include_router(pilot_router, prefix=api_prefix)
app.include_router(pilot_dashboard_router, prefix=api_prefix)
app.include_router(command_center_router, prefix=api_prefix)
app.include_router(interaction_router, prefix=api_prefix)
app.include_router(pilot_measurement_router, prefix=api_prefix)
app.include_router(pilot_reporting_router, prefix=api_prefix)
app.include_router(evidence_router, prefix=api_prefix)
app.include_router(monitoring_router, prefix=api_prefix)

# Conditionally load simulation & demo sandboxes only when enabled (dev/staging/test)
if settings.ENABLE_SIMULATION_FEATURES:
    logger.info("Simulation and Demonstration feature routers enabled for test/sandbox mode.")
    app.include_router(simulation_router, prefix=api_prefix)
    app.include_router(demo_router, prefix=api_prefix)


@app.get("/", tags=["System"])
def root():
    return {
        "service": "PharmaGuard AI Platform",
        "environment": settings.APP_ENV,
        "status": "OPERATIONAL",
        "mode": "AUTONOMOUS_PHARMACY_INTELLIGENCE_AGENT",
        "version": settings.APP_VERSION,
        "documentation": "/docs"
    }


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "environment": settings.APP_ENV,
        "agent_status": "ACTIVE",
        "scheduler_status": "RUNNING"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
