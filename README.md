# Secure Medical Record Management System (SMRMS)

A college cybersecurity project demonstrating secure storage, transmission, and role-based access control of patient medical records.

## Features & Security Controls
- **Bcrypt Password Hashing**: Passwords are never stored in plaintext. They are one-way hashed with bcrypt.
- **JWT Session Authentication**: Stateless HS256 JWT tokens containing cryptographically verifiable identity claims.
- **Multi-Doctor RBAC**: Full support for multiple doctors with distinct identities, logins, and permissions.
- **Doctor-Patient Assignment**: Strict backend-enforced doctor-patient relationships. Doctors can only view, create, or edit records for their assigned patients.
- **AES-256-GCM (AES) Encryption**: Sensitive clinical data (diagnosis, prescription, doctor notes, visit date) are encrypted using AES-256-GCM authenticated encryption. The database never stores plaintext clinical information.
- **SHA-256 Cryptographic Integrity Verification**: A SHA-256 digest is generated from the clinical payload before encryption and stored in the database. Upon retrieval, records are decrypted, their digests are recomputed, and verified before displaying. Tampered records are automatically blocked.
- **Comprehensive Audit Trail**: Security-sensitive actions (login, failed login, doctor creation, patient assignment, record creation, record edit, record access, and unauthorized attempts) are recorded in an immutable audit log.
- **Separate Identity and Medical Records**: Patient demographic identity is decoupled from sensitive clinical records.

---

## Architecture
```text
React + Vite Frontend (localhost:5173)
        │
        │ HTTP JSON + Authorization: Bearer <JWT>
        ▼
FastAPI Backend (127.0.0.1:8000)
  ├── Authentication (bcrypt + JWT)
  ├── RBAC & Doctor-Patient Assignments
  ├── Encryption Engine (AES-256-GCM)
  ├── Integrity Engine (SHA-256 Digest)
  └── Audit Logging
        │
        ▼
SQLite Database (medical_records.db)
  ├── users
  ├── patients
  ├── doctor_patient_assignments
  ├── medical_records
  └── audit_logs
```

---

## Demo Accounts
| Role | Username | Password | Notes |
|---|---|---|---|
| Admin | `admin` | `Admin@123` | Can create doctors, assign patients, inspect audit trail |
| Doctor 1 | `doctor` | `Doctor@123` | Dr. Aisha Mehta (assigned to Rahul Sharma / PAT-1001) |
| Doctor 2 | `doctor2` | `Doctor2@123` | Can be registered by Admin in demo / Test 2 |
| Doctor 3 | `doctor3` | `Doctor3@123` | Dr. Priya Nair (pre-seeded licensed doctor) |
| Patient | `patient` | `Patient@123` | Rahul Sharma (PAT-1001) |

---

## Running the Application

### 1. Backend
```bash
cd backend
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn main:app --reload --port 8000
```
Backend API will be live at: `http://127.0.0.1:8000`  
Swagger API Documentation: `http://127.0.0.1:8000/docs`

### 2. Frontend
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### 3. Run Automated Security Test Suite
To automatically execute the complete 17-test security and RBAC verification:
```bash
cd backend
.venv/bin/python3 test_system.py
```

---

## API Endpoints
| Method | Endpoint | Access Role | Description |
|---|---|---|---|
| `POST` | `/api/login` | Public | Authenticates credentials with bcrypt and returns signed JWT |
| `POST` | `/api/logout` | Authenticated | Logs logout event |
| `GET` | `/api/users/doctors` | Admin, Doctor | Retrieves list of licensed doctors |
| `POST` | `/api/users/doctors` | Admin only | Registers new doctor account with bcrypt hash |
| `GET` | `/api/patients` | All roles (filtered) | Admin sees all; Doctor sees assigned only; Patient sees self |
| `POST` | `/api/patients` | Admin, Doctor | Registers new patient demographics |
| `POST` | `/api/patients/{id}/assign` | Admin only | Assigns patient to an attending doctor |
| `GET` | `/api/records` | All roles (filtered) | Returns accessible decrypted records with integrity verification |
| `GET` | `/api/records/{id}` | Authorized roles | Returns single decrypted record if authorized |
| `POST` | `/api/records` | Doctor only | Creates AES-encrypted record with SHA-256 digest |
| `PUT` | `/api/records/{id}` | Doctor only | Updates AES-encrypted record and recalculates SHA-256 digest |
| `GET` | `/api/audit` | Admin only | Retrieves security event audit trail |
| `POST` | `/api/admin/crypto/encrypt` | Admin only | Demonstrates backend AES-256-GCM (AES) encryption |
| `POST` | `/api/admin/crypto/decrypt` | Admin only | Demonstrates backend AES-256-GCM (AES) decryption |
