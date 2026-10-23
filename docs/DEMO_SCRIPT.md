# Demonstration Script (Step-by-Step for Evaluation)

This script follows the exact 17-test evaluation flow:

### 1. Admin Login & Multi-Doctor Management
- Open the application at `http://localhost:5173`.
- Click the **Admin** button (or sign in with `admin` / `Admin@123`).
- Navigate to **Doctors**: Note the existing doctors (`doctor` / Dr. Aisha Mehta, `doctor3` / Dr. Priya Nair).
- Click **+ Add Doctor**:
  - Username: `doctor2`
  - Full Name: `Dr. Rajesh Kumar`
  - Password: `Doctor2@123`
  - Click **Create Doctor**.
- Point out: The doctor account is registered in SQLite with a salted `bcrypt` password hash, never plaintext.

### 2. Patient Assignment Workflow
- Navigate to **Patients & Assignments**:
  - Notice `PAT-1001` (Rahul Sharma) is assigned to `doctor` (Dr. Aisha Mehta).
  - Notice `PAT-1002` (Krish) is currently **Unassigned**.
- On the row for `PAT-1002` (Krish), click **Assign Doctor**:
  - Select `Dr. Rajesh Kumar (@doctor2)`.
  - Click **Assign Patient**.
- Point out: The assignment is recorded in the `doctor_patient_assignments` table and audited.
- Click **Sign out**.

### 3. Doctor 2 Login & Patient Isolation
- Click the **Doctor 2** chip (or sign in with `doctor2` / `Doctor2@123`).
- Go to **My Patients**:
  - Notice Doctor 2 sees **only** `PAT-1002` (Krish).
  - `PAT-1001` (Rahul Sharma) is strictly invisible because it is assigned to Doctor 1.
- Go to **Medical Records**:
  - Currently empty for Doctor 2.

### 4. Create Medical Record Workflow
- Go back to **My Patients**, on `PAT-1002` (Krish), click **+ Add Record**:
  - Visit Date: `2026-10-05`
  - Diagnosis: `Seasonal bronchitis`
  - Prescription: `Azithromycin 500mg once daily for 5 days`
  - Clinical Notes: `Patient presents with mild cough and low-grade fever.`
  - Click **Save Medical Record**.
- Point out:
  1. The diagnosis and prescription are bundled into JSON.
  2. SHA-256 digest is generated from the plaintext JSON.
  3. Plaintext is encrypted with AES-256-GCM.
  4. Only ciphertext is stored in the database.

### 5. View & Edit Medical Record Workflow
- The app automatically navigates to **Medical Records**:
  - The record is displayed with the green **Verified** integrity badge.
  - Attending Doctor is listed as `Dr. Rajesh Kumar`.
- Click **Edit**:
  - Change Prescription to: `Azithromycin 500mg once daily + Cough lozenges prn`
  - Change Notes to: `Patient reports symptom improvement. Advised rest.`
  - Click **Save Changes**.
- Point out:
  - The record updates immediately in the UI.
  - The SHA-256 integrity digest is recalculated for the updated clinical text.
  - The integrity badge remains green **Verified**.
- Click **Sign out**.

### 6. Doctor 1 Cross-Access Prevention (RBAC Enforcement)
- Sign in as **Doctor 1** (`doctor` / `Doctor@123`).
- In **My Patients**, Doctor 1 only sees `PAT-1001` (Rahul Sharma).
- In **Medical Records**, Doctor 1 only sees `PAT-1001`'s record.
- Explain: If Doctor 1 attempts to call the API directly (`GET /api/records/2` or `POST /api/records` for `PAT-1002`), the backend checks `doctor_patient_assignments` and rejects the request with **HTTP 403 Forbidden**.
- Click **Sign out**.

### 7. Patient Confidentiality & Isolation
- Sign in as **Patient** (`patient` / `Patient@123`).
- In **My Records**, Rahul Sharma sees only their own record (`PAT-1001`).
- `PAT-1002` (Krish's record) is completely inaccessible.
- Explain: The patient role cannot access patient directories, audit logs, or other patient records.
- Click **Sign out**.

### 8. Audit Trail Verification
- Sign in as **Admin** (`admin` / `Admin@123`).
- Navigate to **Audit Log**:
  - Show the logged events: `LOGIN`, `CREATE_DOCTOR`, `ASSIGN_PATIENT`, `CREATE_RECORD`, `UPDATE_RECORD`, `VIEW_RECORD`.
  - Highlight that each entry captures the user, role, action, record ID, status, and timestamp.

### 9. Cryptographic Tampering Demonstration (Bonus)
- Explain: If an unauthorized actor with direct SQLite access alters the ciphertext column `encrypted_data` in the database, the backend's SHA-256 verification or decryption fails.
- The record is marked `TAMPERED`, clinical fields are suppressed (`[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]`), and the frontend displays a red `Tampered` warning badge.

### 10. Admin Cryptography Test Demonstration
- Sign in as **Admin** (`admin` / `Admin@123`).
- In the navigation, click **Cryptography Test**.
- Point out the interactive cryptographic pipeline:
  `Plaintext → AES-256-GCM Encryption → Ciphertext (AES-256-GCM Token) → AES-256-GCM Decryption → Original Plaintext`
- Click a sample button (e.g. `Sample: Allergy` or `Sample: Bronchitis`) or type any plaintext.
- Click **Encrypt (Backend AES-256-GCM)**:
  - Demonstrates that the plaintext is sent to the backend endpoint `POST /api/admin/crypto/encrypt`.
  - Backend encrypts it with the **exact same AES-256-GCM key and implementation** used for medical records.
  - The AES-256-GCM ciphertext and authentication tag are displayed.
- Click **Decrypt (Backend AES-256-GCM)**:
  - Demonstrates that the ciphertext is sent to `POST /api/admin/crypto/decrypt`.
  - Backend decrypts it with the same AES-256-GCM key and returns the original plaintext.
  - A green badge verifies: `✓ Decryption succeeded: Plaintext matches original input byte-for-byte!`.
- Click **Simulate Tamper**:
  - Mutates a single character in the ciphertext token to simulate tampering.
  - Click **Decrypt (Backend AES-256-GCM)**:
  - Backend rejects the tampered ciphertext with HTTP 400 Bad Request, demonstrating AES-256-GCM's built-in HMAC authentication.
