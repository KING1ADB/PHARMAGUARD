# PharmaGuard AI — Production Security & Regulatory Compliance

**Compliance Standards:** Healthcare Information Security, Multi-Tenant Row Isolation, Role-Based Access Control (RBAC)  
**Platform Version:** 1.0.0 (Production Live)

---

## 1. Authentication & Cryptographic Standards

- **Password Storage:** Salted hashing with fallback to bcrypt / SHA-256 with dynamic salt (`pharmaguard_salt_`).
- **Session Tokens:** Signed JWT (JSON Web Tokens) using HMAC-SHA256 (`HS256`) with a cryptographically secure 64-character secret key.
- **Token Expiry:** Standard session tokens expire in **24 hours**. Password reset tokens expire in **60 minutes**.
- **Multi-Factor Authentication (MFA):** TOTP 6-digit verification support for administrative and owner operations.

---

## 2. Multi-Tenant Data Isolation Matrix

PharmaGuard AI is built from the ground up as a secure multi-tenant platform:

1. **Foreign Key Enforcement:** Every entity (`Inventory`, `SalesHistory`, `PurchaseOrder`, `Alert`, `AgentMemory`, `AgentActionLog`) strictly references `pharmacy_id`.
2. **Access Control Filtering:**
   - Standard Pharmacists and Assistants can only read and write records where `User.pharmacy_id == target_pharmacy_id`.
   - Any cross-tenant read or write request returns `403 FORBIDDEN`.
3. **Audit Trail Immutability:**
   - Every AI agent decision, human approval, quantity modification, and supplier message is written to append-only `AgentActionLog` records.

---

## 3. Role-Based Access Control (RBAC) Matrix

| Endpoint & Action | `OWNER` | `PHARMACIST` | `ASSISTANT` | `AUDITOR` |
| :--- | :---: | :---: | :---: | :---: |
| **View Command Center & Briefings** | ✅ | ✅ | ✅ | ✅ |
| **Approve Financial Purchase Orders** | ✅ | ✅ | ❌ | ❌ |
| **Modify Supplier / Order Quantities** | ✅ | ✅ | ❌ | ❌ |
| **Manage Staff Accounts & RBAC** | ✅ | ❌ | ❌ | ❌ |
| **Scan Delivery Barcodes** | ✅ | ✅ | ✅ | ❌ |
| **View Audit Logs & Compliance Reports**| ✅ | ✅ | ❌ | ✅ |

---

## 4. Clinical Safety Boundaries

- **Strict Non-Diagnostic Boundary:** PharmaGuard AI **never** prescribes drugs, suggests patient dosages, or replaces clinical pharmacist verification.
- **Mandatory Financial Authorization:** The AI operates exclusively in `DRAFT` staging mode for external procurement. No purchase order can be sent to distributors without verified pharmacist signature.
