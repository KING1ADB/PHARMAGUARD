from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.database import init_db
from .api import pharmacy, inventory, agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database and Seed Default Data from CSV
    print("🚀 [PharmaGuard AI] Initializing Database and Autonomous Agents...")
    init_db()
    print("✅ [PharmaGuard AI] System ready. Agent Decision Loop active.")
    yield
    # Shutdown
    print("🛑 [PharmaGuard AI] System shut down.")


app = FastAPI(
    title="PharmaGuard AI — Pharmacy Intelligence Agent",
    description=(
        "Autonomous AI Pharmacy Operations Agent & Healthcare Network Engine. "
        "Provides stockout prediction, expiry mitigation, automated procurement, "
        "and connected medicine access for Cameroon & African community pharmacies."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard and WhatsApp webhook clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(pharmacy.router)
app.include_router(inventory.router)
app.include_router(agent.router)


@app.get("/")
def root():
    return {
        "system": "PharmaGuard AI Agent Engine",
        "status": "ONLINE",
        "version": "1.0.0",
        "city": "Douala",
        "country": "Cameroon",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }


@app.get("/health")
def health_check():
    return {
        "status": "HEALTHY",
        "database": "CONNECTED",
        "agent_engine": "READY"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
