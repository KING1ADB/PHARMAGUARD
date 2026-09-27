from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database.database import init_db
from .api import pharmacy_api, inventory_api, agent_api


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
    title="PharmaGuard AI — Autonomous Pharmacy Intelligence Agent",
    description=(
        "Autonomous AI Pharmacy Operations Agent & Healthcare Network Engine. "
        "Continuously analyzes pharmacy data, detects operational risks, explains reasoning, "
        "generates recommendations, and performs approved actions while keeping pharmacists in control."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard and webhook clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(pharmacy_api.router)
app.include_router(inventory_api.router)
app.include_router(agent_api.router)


@app.get("/")
def root():
    return {
        "system": "PharmaGuard AI Agent Engine",
        "status": "ONLINE",
        "role": "Autonomous Pharmacy Intelligence Employee",
        "decision_loop": "Observe → Analyze → Reason → Recommend → Request Approval → Act → Learn",
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
