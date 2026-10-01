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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"
)
logger = logging.getLogger("PharmaGuard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables & seed initial CSV datasets
    logger.info("Initializing PharmaGuard AI Database and Seeding initial catalogs...")
    init_db()
    
    # Start the Autonomous Background Scheduler (Morning Intelligence Agent @ 07:30 AM)
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
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for future frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers with v1 prefix
api_prefix = "/api/v1"
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
app.include_router(simulation_router, prefix=api_prefix)
app.include_router(demo_router, prefix=api_prefix)


@app.get("/", tags=["System"])
def root():
    return {
        "service": "PharmaGuard AI Platform",
        "status": "OPERATIONAL",
        "mode": "AUTONOMOUS_PHARMACY_INTELLIGENCE_AGENT",
        "version": "1.0.0",
        "documentation": "/docs"
    }


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "HEALTHY",
        "agent_status": "ACTIVE",
        "scheduler_status": "RUNNING"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
