# Cybersecurity Viva Voce Questions & Answers

### 1. How does a doctor log in?
1. The doctor submits their username and password via the login form to `POST /api/login`.
2. The FastAPI backend queries the `users` table for that username.
3. The password provided is verified against the stored hash using `bcrypt.checkpw()`. Plaintext passwords are never stored.
4. If valid, the backend creates a signed JSON Web Token (JWT) with the doctor's user ID, role (`doctor`), and full name, and returns it to the client.
5. A `LOGIN` event with status `SUCCESS` is written to the audit log.

---

### 2. How does the system know which doctor is logged in?
1. The frontend stores the JWT in `localStorage` and includes it in every subsequent HTTP request in the header:
   `Authorization: Bearer <token>`
2. On every protected backend route, the `current_user` dependency decodes and verifies the cryptographic signature of the token using `SECRET_KEY` and algorithm `HS256`.
3. The subject claim (`sub`) in the token contains the doctor's unique database user ID. The backend fetches this user from the database.
4. The backend never relies on the frontend telling it who the user is; the identity is cryptographically proven by the signed token.

---

### 3. How does RBAC work?
- **Role-Based Access Control (RBAC)** means access permissions are determined by the user's role (`admin`, `doctor`, `patient`).
- The backend checks `user.role` on every endpoint:
  - If a patient calls `POST /api/records`, the backend returns `403 Forbidden`.
  - If a doctor tries to read the audit logs at `GET /api/audit`, the backend returns `403 Forbidden`.
  - If an admin calls `POST /api/users/doctors`, it is permitted.
- Security decisions are made strictly on the server, not in React.

---

### 4. How can multiple doctors exist?
- Doctors are stored as distinct records in the `users` table with unique auto-incrementing integer IDs (`id`), unique usernames (`username`), independent bcrypt password hashes, and `role = "doctor"`.
- The system comes with demo doctors (e.g. `doctor`, `doctor3`) and the Admin can create additional doctors at any time via `POST /api/users/doctors`.
- Each doctor logs in independently with their own credentials and receives a JWT identifying their unique ID.

---

### 5. How is a patient assigned to a doctor?
- Through the `doctor_patient_assignments` table, which maps a `patient_id` to an authorized `doctor_id` along with an assignment timestamp (`assigned_at`).
- An administrator assigns a patient to a doctor using `POST /api/patients/{patient_id}/assign`.
- Additionally, when a doctor registers a new patient, the system automatically creates an assignment between that doctor and the new patient.

---

### 6. How does a doctor create a medical record?
1. The doctor submits patient ID, diagnosis, prescription, clinical notes, and visit date to `POST /api/records`.
2. The backend identifies the doctor from the JWT and checks `doctor_patient_assignments`. If the patient is not assigned to this doctor, access is denied with `403 Forbidden`.
3. If authorized, the clinical information is packaged into a JSON string with deterministic key sorting (`sort_keys=True`).
4. The backend calculates a SHA-256 integrity hash of this plaintext string.
5. The backend encrypts the plaintext string using AES-256-GCM (AES).
6. The ciphertext, the SHA-256 digest, the patient ID, the doctor ID, and timestamps are saved in the `medical_records` table.
7. A `CREATE_RECORD` event is recorded in the audit log.

---

### 7. How is the diagnosis encrypted? Where is AES used?
- Sensitive clinical data (diagnosis, prescription, doctor notes, and visit date) are bundled into a JSON object:
  `{"diagnosis": "...", "prescription": "...", "notes": "...", "visit_date": "..."}`
- This string is encrypted using **AES-256-GCM symmetric encryption** from Python's standard `cryptography` library.
- AES-256-GCM internally implements **AES (Advanced Encryption Standard) with a 128-bit key in CBC mode** with PKCS7 padding, combined with HMAC-SHA256 for authenticated encryption.
- In the database table `medical_records`, only the ciphertext (`encrypted_data`) is stored. The database never contains plaintext diagnosis or prescription text.

---

### 8. How is the encryption key handled?
- The symmetric encryption key is managed by the server in `backend/security.py`.
- The AES-256-GCM key can optionally be supplied via the `AES_GCM_KEY` environment variable.
- If not provided, the application generates a secure key on first boot and persists it to `backend/aes_gcm.key` (with restricted filesystem permissions).
- The key is never sent to the frontend or exposed to users.

---

### 9. How does SHA-256 verify integrity?
- When a medical record is created or updated, the SHA-256 cryptographic hash function computes a 256-bit (64 hex characters) digest of the plaintext clinical JSON:
  `integrity_hash = sha256(plaintext_data).hexdigest()`
- This digest is stored in the `medical_records.integrity_hash` column.
- When an authorized user requests the record:
  1. The backend decrypts the ciphertext into plaintext.
  2. The backend recalculates the SHA-256 digest of the decrypted plaintext.
  3. It compares `recalculated_digest == stored_digest`.
  4. If equal, integrity is verified (`VALID`).
  5. If not equal, the record is flagged as `TAMPERED`.

---

### 10. What happens if someone modifies the encrypted record directly in the database?
1. If an attacker or unauthorized database administrator changes the ciphertext or stored hash:
2. When the record is accessed, AES-256-GCM decryption will fail (HMAC mismatch) OR the recalculated SHA-256 digest will not match the stored digest.
3. The backend catches this, flags the record status as `TAMPERED`, and logs a `VIEW_RECORD` audit event with status `TAMPERED`.
4. Most importantly: the backend **blocks the clinical data**—returning placeholder text `[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]` and redacting prescriptions/notes.
5. The frontend displays the red `Tampered` warning badge instead of `Verified`.

---

### 11. How does the system prevent Doctor A from accessing Doctor B's patients?
- This is enforced server-side via SQL queries and explicit permission checks:
  1. When a doctor requests `/api/patients`, the query joins `doctor_patient_assignments` on `doctor_id == current_user.id`. The doctor never even receives unassigned patients.
  2. When a doctor calls `/api/records`, the query filters records where `patient_id` is in the doctor's assigned patient IDs.
  3. If Doctor A guesses a record ID or manually calls `/api/records/{id}` for a patient assigned to Doctor B, the backend queries `doctor_patient_assignments`. If Doctor A is not assigned, the request is immediately aborted with `HTTP 403 Forbidden` and an `UNAUTHORIZED_RECORD_ACCESS_ATTEMPT` is recorded in the audit log.

---

### 12. How does the patient role differ from the doctor role?
- **Patient**:
  - Can only view their own identity profile.
  - Can only view medical records associated with their own patient ID.
  - Cannot access the patient directory, cannot view any other patient's records, cannot create or edit records, and cannot view audit logs.
- **Doctor**:
  - Can view their assigned patients.
  - Can create new patients.
  - Can create and edit medical records for assigned patients.
  - Cannot manage system users or view system audit logs.

---

### 13. How are actions recorded in the audit log?
- The backend contains a centralized `log(db, user_id, action, record_id, status_val, user_role, details)` function.
- Whenever an important event occurs (login, failed login, doctor creation, patient assignment, record creation, record edit, record view, or unauthorized attempt):
- A row is written to `audit_logs` with:
  - `user_id` & `user_role`
  - `action` (e.g., `CREATE_RECORD`, `ASSIGN_PATIENT`, `UNAUTHORIZED_ACCESS_ATTEMPT`)
  - `record_id` (affected medical record ID if applicable)
  - `status` (`SUCCESS`, `FAILED`, `BLOCKED`, `VALID`, `TAMPERED`)
  - `details` (human-readable description)
  - `created_at` (UTC timestamp)
- The audit log is accessible only by administrators at `GET /api/audit`.
