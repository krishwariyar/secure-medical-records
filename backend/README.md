# Backend - Secure Medical Record Management System

## Run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API runs at http://127.0.0.1:8000 and Swagger docs at /docs.

## Security implementation
- bcrypt password hashing
- JWT authentication
- role-based authorization
- AES-256-GCM authenticated encryption for medical record contents
- SHA-256 integrity digest stored separately from encrypted data
- audit logging for login and record access

Demo passwords are intentionally included for a classroom demonstration only. Change them before real deployment.
