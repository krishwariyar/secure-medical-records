# System Architecture

## Components

### Frontend
React + Vite provides the login screen, medical records table, patient directory, doctor management interface, and security audit trail. It sends JSON requests with a signed JWT in the `Authorization: Bearer <token>` header.

### Backend
FastAPI manages authentication, role-based access control (RBAC), symmetric AES encryption, SHA-256 integrity verification, and database interactions. All authorization decisions are strictly enforced server-side; the client cannot bypass security controls by manipulating the browser.

### Database
SQLite is used for local zero-configuration persistence. Schema:
- `users`: User accounts with bcrypt password hashes and roles (`admin`, `doctor`, `patient`).
- `patients`: Demographic identity records (separated from sensitive clinical records).
- `doctor_patient_assignments`: Explicit doctor-patient relationships authorizing doctor access.
- `medical_records`: Clinical records containing AES-encrypted ciphertext (`encrypted_data`), SHA-256 digest (`integrity_hash`), patient/doctor foreign keys, and timestamp audit fields (`created_at`, `updated_at`, `last_updated_by_id`).
- `audit_logs`: Immutable security event logs capturing actor, role, action, target, result status, and detailed context.

---

## Complete Request & Security Flow

```text
CLIENT (React Dashboard)
   │
   │ HTTP JSON Request + Authorization: Bearer <JWT>
   ▼
FASTAPI SERVER
   │
   ├─► 1. AUTHENTICATION: Validate JWT signature & expiration (current_user)
   │
   ├─► 2. AUTHORIZATION (RBAC):
   │       - Admin: Manage users, doctors, patient assignments, audit logs.
   │       - Doctor: Access only assigned patients and their medical records.
   │       - Patient: Access only their own confidential medical records.
   │       * Rejects unauthorized requests with 403 Forbidden & logs event.
   │
   ├─► 3. CLINICAL RECORD PROCESSING:
   │       [Write / Update]:
   │          Plaintext JSON -> Calculate SHA-256 -> Encrypt with AES-256-GCM -> Save DB
   │       [Read]:
   │          Fetch ciphertext -> Decrypt with AES -> Compute SHA-256 -> Compare with stored hash
   │          - If MATCH -> integrity_status = VALID (Display record)
   │          - If MISMATCH / Corrupted -> integrity_status = TAMPERED (Block/redact clinical fields)
   │
   ├─► 4. AUDIT LOGGING: Record user, action, target ID, status, and details in audit_logs table
   │
   ▼
SQLITE DATABASE (Confidentiality & Integrity Guaranteed)
```

---

## Record Lifecycle

```text
[CREATE / UPDATE RECORD]
   ↓
Validate Doctor is assigned to Patient (403 if unauthorized)
   ↓
Build clinical JSON (diagnosis, prescription, notes, visit_date)
   ↓
SHA-256 digest calculated on plaintext JSON (sort_keys=True)
   ↓
Plaintext encrypted using AES-256-GCM
   ↓
Encrypted ciphertext + SHA-256 digest + Doctor ID stored in database
   ↓
Audit log created (CREATE_RECORD / UPDATE_RECORD)

[READ RECORD]
   ↓
Verify Requesting User Authorization (Doctor assigned / Patient self / Admin)
   ↓
Decrypt ciphertext using AES-256-GCM AES key
   ↓
Recalculate SHA-256 digest on decrypted plaintext
   ↓
Compare recalculated digest with stored digest
   ↓
If EQUAL:
   Status = "VALID"
   Audit log VIEW_RECORD (Status: VALID)
   Return decrypted clinical details to frontend (Verified badge)
If NOT EQUAL or DECRYPTION FAILS:
   Status = "TAMPERED"
   Audit log VIEW_RECORD (Status: TAMPERED)
   Suppress clinical fields (return "[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]")
   Return Tampered badge to frontend
```
