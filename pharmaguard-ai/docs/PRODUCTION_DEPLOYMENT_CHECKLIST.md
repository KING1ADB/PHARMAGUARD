# PharmaGuard AI — Production Pilot Deployment Checklist

**Product Identity:** Autonomous Pharmacy Operations Agent  
**Environment:** Live Real-World Pilot Pharmacy Deployment  
**Standard:** Enterprise Healthcare AI Operational Grade

---

## 1. Pharmacy Onboarding Readiness Verification

| Check Item | Validation Method | Acceptance Criteria | Status |
| :--- | :--- | :--- | :--- |
| **Pharmacy Registration** | `POST /api/v1/onboarding/register` | Legal trade name, ministry license, and regional zone recorded. | **VERIFIED** |
| **Staff RBAC Setup** | `POST /api/v1/onboarding/staff` | At least 1 verified `PHARMACIST` and 1 `OWNER` account provisioned with bcrypt/salted hash. | **VERIFIED** |
| **Role Permissions** | `require_roles(["PHARMACIST", "OWNER"])` | Strict enforcement: Only licensed pharmacists can approve purchase orders. | **VERIFIED** |
| **Schedule Configuration** | `POST /api/v1/onboarding/activate` | Daily morning execution schedule set (Default: `07:30 AM`). | **VERIFIED** |

---

## 2. Security & Tenant Data Isolation Validation

| Check Item | Validation Method | Acceptance Criteria | Status |
| :--- | :--- | :--- | :--- |
| **JWT Authentication** | `decode_access_token` | Signed HS256 tokens with 24-hour expiry and encrypted payload. | **VERIFIED** |
| **Tenant Isolation** | Multi-tenant Foreign Key Queries | Strict `pharmacy_id` filtering on all database transactions; no cross-tenant leakage. | **VERIFIED** |
| **WhatsApp Webhook Auth** | `X-Hub-Signature-256` HMAC-SHA256 | Only authorized verified phone numbers can trigger approval actions. | **VERIFIED** |
| **Audit Log Immutability** | `AgentActionLog` & `AgentMemory` | Every single autonomous run and user decision is timestamped and recorded. | **VERIFIED** |

---

## 3. Data Quality & Catalog Integrity Validation

| Check Item | Validation Method | Acceptance Criteria | Status |
| :--- | :--- | :--- | :--- |
| **Data Quality Score (DQS)** | `pilot_manager.get_pharmacy_pilot_status` | Overall DQS $\ge 70\%$ across cost, expiry, and batch completeness. | **VERIFIED** |
| **Date Parsing Robustness** | Flexible multi-format parser | Validates `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY` without throwing exceptions. | **VERIFIED** |
| **Header Synonym Mapping** | Automatic synonym resolver | Supports diverse French and English POS column aliases (`quantite`, `prix_achat`, `peremption`). | **VERIFIED** |
| **Cold-Chain Flagging** | Medicine Intelligence Layer | Insulin and vaccines enforce 2°C–8°C storage tags and lead-time safety buffers. | **VERIFIED** |

---

## 4. Agent Reliability & Operational Autonomous Checks

| Check Item | Validation Method | Acceptance Criteria | Status |
| :--- | :--- | :--- | :--- |
| **Autonomous Scheduler** | Background Daemon Process | Scheduler triggers daily morning cycle at opening time without human intervention. | **VERIFIED** |
| **Two-Tier Memory Loop** | Short-term Working + Long-term Episodic | Short-term memory clears per cycle; long-term memory accumulates human preferences. | **VERIFIED** |
| **HITL Safety Constraint** | Procurement Agent Workflow | Staged purchase orders are **strictly `DRAFT`** until explicitly authorized. | **VERIFIED** |
| **Scenario Validation Suite** | `POST /api/v1/pilot/validate-scenarios` | 100% pass on Stock Shortage, Supplier Delays, Seasonal Surge, and Feedback Learning. | **VERIFIED** |
