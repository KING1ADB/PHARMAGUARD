# PharmaGuard AI — Autonomous Pharmacy Intelligence Agent

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![Status](https://img.shields.io/badge/Status-Active_Prototype-success.svg)]()

> **"PharmaGuard AI is not an app; it is an Autonomous AI Pharmacy Operations Employee."**

PharmaGuard AI transforms community pharmacies across Cameroon and Africa from reactive record-keeping into proactive, intelligent operations. It actively observes inventory velocities, predicts critical stockouts, prevents batch expiration losses, negotiates replenishment with suppliers, and coordinates medicine availability for patients.

---

## 🏗️ Project Architecture & Directory Structure

```text
pharmaguard-ai/
│
├── app/
│   ├── main.py                        # FastAPI entrypoint, lifespan seeding, middleware
│   │
│   ├── agent/                         # Core Agent Orchestration & State
│   │   ├── orchestrator.py            # Master AI Orchestrator (Observe-Analyze-Plan-Act-Learn)
│   │   ├── prompts.py                 # System prompts, personas, and safety guardrails
│   │   ├── memory.py                  # Short-term and episodic memory buffer
│   │   └── state.py                   # Pydantic agent state & context models
│   │
│   ├── agents/                        # Specialized Sub-Agents
│   │   ├── inventory_agent.py         # Stock health, batch monitoring, FEFO protocol
│   │   ├── forecasting_agent.py       # Demand prediction, seasonal factors, depletion dates
│   │   └── procurement_agent.py       # Supplier optimization & DRAFT Purchase Order generator
│   │
│   ├── tools/                         # Agent Action Tools
│   │   ├── inventory_tools.py         # SKU search, stock adjustment, catalog stats
│   │   ├── risk_tools.py              # Expiry risk assessment, supplier bottleneck checks
│   │   └── report_tools.py            # WhatsApp daily briefings & purchase order formatters
│   │
│   ├── database/                      # Data Persistence Layer
│   │   ├── models.py                  # SQLAlchemy ORM models (Medicines, Suppliers, POs, Alerts, Logs)
│   │   ├── database.py                # Database connection, session maker, CSV auto-seeding
│   │   └── schemas.py                 # Pydantic validation & response serialization schemas
│   │
│   ├── api/                           # REST API Routers
│   │   ├── pharmacy.py                # Pharmacy profile & connected supplier endpoints
│   │   ├── inventory.py               # Inventory CRUD, CSV upload, and risk profiles
│   │   └── agent.py                   # Autonomous cycle trigger, interactive query, PO approvals
│   │
│   └── services/                      # Analytical Engines
│       ├── analysis.py                # Sales velocity & Days of Inventory Remaining (DIR)
│       └── forecasting.py             # Seasonal demand forecasting & reorder calculation
│
├── data/                              # Real-World Seed Data (Douala, Cameroon)
│   ├── inventory.csv                  # Medicines (Antimalarials, Antibiotics, Chronic disease)
│   ├── sales.csv                      # Historical sales transaction records
│   └── suppliers.csv                  # Wholesale distributors (PharmaCam, Laborex, Ubipharm)
│
├── tests/                             # Test Suite
│   ├── test_services.py               # Velocity, health, and forecasting tests
│   ├── test_agent.py                  # Autonomous decision loop and query tests
│   └── test_api.py                    # FastAPI endpoint integration tests
│
├── .env                               # Environment configurations
├── requirements.txt                   # Python dependencies
└── README.md                          # Comprehensive documentation
```

---

## 🔄 The 5-Stage Autonomous Decision Cycle

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        THE AGENT DECISION LOOP                         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
  1. OBSERVE   ───► Scans current inventory, batch expiries, sales velocity
       │
  2. ANALYZE   ───► Computes Days of Inventory Remaining (DIR) & seasonal demand
       │
  3. PLAN      ───► Selects optimal supplier, calculates MOQs, drafts POs
       │
  4. ACT       ───► Sends WhatsApp briefing, registers alerts, awaits approval
       │
  5. LEARN     ───► Records cycle metrics, adapts lead times & user preferences
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
Ensure you have Python 3.10+ installed.

```bash
cd pharmaguard-ai
pip install -r requirements.txt
```

### 2. Start the Backend Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
* Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`
* Alternative Redoc Documentation: `http://localhost:8000/redoc`

### 3. Run Automated Tests
```bash
pytest
```

---

## 📡 Core API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/agent/cycle` | Trigger full autonomous 5-stage intelligence cycle |
| `POST` | `/agent/query` | Interactive natural language query (Pharmacist / Patient) |
| `GET` | `/agent/briefing` | Get WhatsApp-formatted daily executive briefing |
| `GET` | `/agent/alerts` | Get active stockout & expiry alerts |
| `GET` | `/agent/purchase-orders` | List draft and approved supplier purchase orders |
| `POST` | `/agent/purchase-orders/{id}/approve` | **Human-in-the-Loop** approval of draft purchase order |
| `GET` | `/inventory` | List all medicines with real-time risk profile |
| `POST` | `/inventory/upload-csv` | Batch upload/sync inventory from Excel/POS CSV |

---

## 🛡️ Governance & Human-in-the-Loop (HITL)

PharmaGuard AI enforces strict safety boundaries:
1. **Financial Authorization**: The agent **never** dispatches purchase orders or financial commitments autonomously. All orders are staged in `DRAFT` status until the licensed pharmacist reviews and authorizes them.
2. **Clinical Safety**: The agent does not generate diagnostic advice; it coordinates inventory availability and generic-brand substitution mappings.

---

## 🌍 Pilot Deployment Context
* **Initial Market**: Douala, Cameroon (Community Pharmacies)
* **Wholesale Suppliers Configured**: PharmaCam Wholesalers, Laborex Cameroon, Ubipharm Central Africa
* **Currency**: Central African CFA Franc (XAF / FCFA)
