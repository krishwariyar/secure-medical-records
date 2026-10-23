# Security Design

## 1. Confidentiality
Clinical record contents (diagnosis, prescription, notes, visit date) are encrypted before storage. The application uses AES-256-GCM from Python's standard `cryptography` library. Internally, AES-256-GCM implements AES-128 in CBC mode with PKCS7 padding and HMAC-SHA256 for ciphertext authentication.

Passwords are NEVER stored in plaintext. They are salted and one-way hashed using `bcrypt` and verified during login.

## 2. Integrity
Integrity is verified using SHA-256 digests.
- Before encryption, a deterministic SHA-256 hash is computed over the serialized plaintext clinical JSON.
- The resulting 64-character hexadecimal digest is stored in `medical_records.integrity_hash`.
- When an authorized user retrieves a record, the backend decrypts the ciphertext, recalculates the SHA-256 digest of the plaintext, and compares it to the stored digest.
- If the digests match, the record is marked `VALID` and returned.
- If tampering or database corruption is detected (hash mismatch or decryption failure), the status is marked `TAMPERED`, clinical fields are redacted/blocked (`[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]`), and an audit log entry is immediately recorded.

## 3. Authentication
The `/api/login` endpoint validates credentials against the bcrypt password hash. Upon success, a JSON Web Token (JWT) signed with HS256 is returned containing the user ID (`sub`), role, and user name with a 60-minute expiration.

## 4. Role-Based Access Control (RBAC) & Doctor-Patient Assignments
Access controls are enforced on every protected backend route:
- **Admin**:
  - Full system administration.
  - Can register new doctors (`POST /api/users/doctors`).
  - Can view all doctors and all patients.
  - Can assign or reassign patients to doctors (`POST /api/patients/{id}/assign`).
  - Can view the complete security audit trail (`GET /api/audit`).
- **Doctor**:
  - Can view only their assigned patients (`GET /api/patients`).
  - Can view, create, and edit medical records ONLY for patients assigned to them (`doctor_patient_assignments`).
  - Attempting to access or modify records of unassigned patients is blocked by the backend with HTTP 403 Forbidden and logged as `UNAUTHORIZED_ACCESS_ATTEMPT`.
- **Patient**:
  - Can view only their own patient demographic info and their own confidential medical records.
  - Blocked from accessing other patients' records or system endpoints.

## 5. Auditability
All security-relevant actions are stored in `audit_logs`:
- `LOGIN` (SUCCESS / FAILED)
- `LOGOUT`
- `CREATE_DOCTOR`
- `CREATE_PATIENT`
- `ASSIGN_PATIENT`
- `CREATE_RECORD`
- `UPDATE_RECORD`
- `VIEW_RECORD` (VALID / TAMPERED)
- `UNAUTHORIZED_ACCESS_ATTEMPT` (status: BLOCKED)

## 6. Threat Model & Mitigations
| Threat | Mitigation |
|---|---|
| Database compromise / password theft | bcrypt salted hashes (computationally hard to brute-force) |
| Database exposure of clinical records | AES-256-GCM authenticated encryption |
| Direct database tampering of records | SHA-256 digest verification + AES-256-GCM HMAC |
| Unauthorized cross-doctor record snooping | Backend RBAC via `doctor_patient_assignments` table |
| Client-side permission manipulation | All permissions enforced on the FastAPI server; token verified per request |
| Untracked actions / repudiation | Centralized audit logging capturing actor, action, timestamp, and status |
