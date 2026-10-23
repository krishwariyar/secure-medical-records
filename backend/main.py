import json
import os
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import Base, engine, get_db, SessionLocal
from models import User, Patient, DoctorPatientAssignment, MedicalRecord, AuditLog
from schemas import (
    LoginRequest, DoctorCreate, PatientCreate, PatientAssign,
    RecordCreate, RecordUpdate, CryptoEncryptRequest, CryptoDecryptRequest
)
from security import (
    SECRET_KEY, ALGORITHM, hash_password, verify_password,
    create_token, encrypt_record, decrypt_record, integrity_hash, migrate_legacy_ciphertext
)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ensure migration safety for existing databases
    with engine.connect() as conn:
        for table, col, col_type in [
            ("patients", "user_id", "INTEGER"),
            ("medical_records", "last_updated_by_id", "INTEGER"),
            ("audit_logs", "user_role", "VARCHAR(30)"),
            ("audit_logs", "details", "VARCHAR(255)")
        ]:
            try:
                res = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                col_names = [r[1] for r in res]
                if col not in col_names:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
            except Exception:
                pass

init_db()

# One-time, idempotent migration: existing Fernet ciphertext is re-encrypted with AES-256-GCM.
# The original SHA-256 digests remain valid because the plaintext records are unchanged.
def migrate_existing_records_to_aes_gcm():
    db = SessionLocal()
    try:
        records = db.query(MedicalRecord).all()
        changed = 0
        for record in records:
            if not record.encrypted_data.startswith("AES256GCM:"):
                record.encrypted_data = migrate_legacy_ciphertext(record.encrypted_data)
                changed += 1
        if changed:
            db.commit()
            print(f"Migrated {changed} legacy medical record(s) to AES-256-GCM.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

migrate_existing_records_to_aes_gcm()

app = FastAPI(title="Secure Medical Record Management System", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def current_user(authorization: str | None, db: Session) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    token = authorization[7:]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        user = db.get(User, int(user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def log(db: Session, user_id: int, action: str, record_id: int | None = None,
        status_val: str = "SUCCESS", user_role: str | None = None, details: str | None = None):
    audit_entry = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action=action,
        record_id=record_id,
        status=status_val,
        details=details
    )
    db.add(audit_entry)
    db.commit()


def seed():
    db = next(get_db())
    
    # 1. Seed users if not present
    if db.query(User).filter_by(username="admin").first() is None:
        db.add(User(username="admin", password_hash=hash_password("Admin@123"), role="admin", full_name="System Administrator"))
    if db.query(User).filter_by(username="doctor").first() is None:
        db.add(User(username="doctor", password_hash=hash_password("Doctor@123"), role="doctor", full_name="Dr. Aisha Mehta"))
    if db.query(User).filter_by(username="doctor3").first() is None:
        db.add(User(username="doctor3", password_hash=hash_password("Doctor3@123"), role="doctor", full_name="Dr. Priya Nair"))
    if db.query(User).filter_by(username="patient").first() is None:
        db.add(User(username="patient", password_hash=hash_password("Patient@123"), role="patient", full_name="Rahul Sharma"))
    db.commit()

    admin = db.query(User).filter_by(username="admin").first()
    doc1 = db.query(User).filter_by(username="doctor").first()
    patient_user = db.query(User).filter_by(username="patient").first()

    # 2. Seed patients if not present
    p1 = db.query(Patient).filter_by(patient_code="PAT-1001").first()
    if not p1:
        p1 = Patient(
            patient_code="PAT-1001",
            full_name="Rahul Sharma",
            date_of_birth="2007-01-20",
            contact="9876543210",
            user_id=patient_user.id if patient_user else None
        )
        db.add(p1)
    elif patient_user and not p1.user_id:
        p1.user_id = patient_user.id

    p2 = db.query(Patient).filter_by(patient_code="PAT-1002").first()
    if not p2:
        p2 = Patient(patient_code="PAT-1002", full_name="Krish", date_of_birth="2004-05-15", contact="9876543211")
        db.add(p2)

    p3 = db.query(Patient).filter_by(patient_code="PAT-1003").first()
    if not p3:
        p3 = Patient(patient_code="PAT-1003", full_name="Neil Jacob", date_of_birth="2005-09-10", contact="9876543212")
        db.add(p3)
    db.commit()

    # 3. Seed initial assignment for doc1 -> PAT-1001
    p1 = db.query(Patient).filter_by(patient_code="PAT-1001").first()
    if p1 and doc1:
        if db.query(DoctorPatientAssignment).filter_by(doctor_id=doc1.id, patient_id=p1.id).count() == 0:
            db.add(DoctorPatientAssignment(doctor_id=doc1.id, patient_id=p1.id))
            db.commit()

    # 4. Seed initial medical record for PAT-1001 by doc1
    if db.query(MedicalRecord).count() == 0 and p1 and doc1:
        data = {
            "diagnosis": "Seasonal allergy",
            "prescription": "Cetirizine 10mg once daily",
            "notes": "Patient reports mild allergy symptoms. Review after 7 days.",
            "visit_date": "2026-10-04"
        }
        plain = json.dumps(data, sort_keys=True)
        rec = MedicalRecord(
            patient_id=p1.id,
            doctor_id=doc1.id,
            last_updated_by_id=doc1.id,
            encrypted_data=encrypt_record(plain),
            integrity_hash=integrity_hash(plain),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        log(db, doc1.id, "CREATE_RECORD", rec.id, status_val="SUCCESS", user_role="doctor", details=f"Initial record for patient {p1.patient_code}")

    db.close()

seed()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        if user:
            log(db, user.id, "LOGIN", status_val="FAILED", user_role=user.role, details=f"Failed login attempt for user {body.username}")
        else:
            log(db, 0, "LOGIN", status_val="FAILED", user_role="unknown", details=f"Failed login attempt for non-existent user {body.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    log(db, user.id, "LOGIN", status_val="SUCCESS", user_role=user.role, details=f"User {user.username} logged in successfully")
    return {
        "token": create_token(user.id, user.role, user.full_name),
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.full_name,
            "role": user.role
        }
    }


@app.post("/api/logout")
def logout(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    try:
        user = current_user(authorization, db)
        log(db, user.id, "LOGOUT", status_val="SUCCESS", user_role=user.role, details=f"User {user.username} logged out")
    except Exception:
        pass
    return {"message": "Logged out successfully"}


# ---------------- DOCTORS MANAGEMENT ----------------

@app.get("/api/users/doctors")
def get_doctors(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role not in {"admin", "doctor"}:
        log(db, user.id, "UNAUTHORIZED_DOCTOR_LIST_ACCESS", status_val="BLOCKED", user_role=user.role)
        raise HTTPException(status_code=403, detail="Staff access required")
    doctors = db.query(User).filter_by(role="doctor").order_by(User.id.asc()).all()
    return [{"id": d.id, "username": d.username, "full_name": d.full_name, "role": d.role} for d in doctors]


@app.post("/api/users/doctors")
def create_doctor(body: DoctorCreate, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "admin":
        log(db, user.id, "UNAUTHORIZED_DOCTOR_CREATION_ATTEMPT", status_val="BLOCKED", user_role=user.role, details=f"Unauthorized creation attempt for {body.username}")
        raise HTTPException(status_code=403, detail="Admin access required to create doctors")
    
    if len(body.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(status_code=400, detail="Username already exists")

    new_doctor = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        role="doctor",
        full_name=body.full_name.strip()
    )
    db.add(new_doctor)
    db.commit()
    db.refresh(new_doctor)

    log(db, user.id, "CREATE_DOCTOR", status_val="SUCCESS", user_role=user.role, details=f"Created doctor account {new_doctor.username} ({new_doctor.full_name}) with ID #{new_doctor.id}")
    return {
        "id": new_doctor.id,
        "username": new_doctor.username,
        "full_name": new_doctor.full_name,
        "role": new_doctor.role
    }


# ---------------- PATIENTS & ASSIGNMENTS ----------------

@app.get("/api/patients")
def get_patients(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    
    if user.role == "patient":
        # Patient can only view their own patient profile
        pts = db.query(Patient).filter((Patient.user_id == user.id) | (Patient.full_name == user.full_name)).all()
        return [{
            "id": p.id,
            "patient_code": p.patient_code,
            "full_name": p.full_name,
            "date_of_birth": p.date_of_birth,
            "contact": p.contact
        } for p in pts]
    
    if user.role == "doctor":
        # Doctor only sees assigned patients
        assignments = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id).all()
        assigned_ids = [a.patient_id for a in assignments]
        pts = db.query(Patient).filter(Patient.id.in_(assigned_ids)).order_by(Patient.id.asc()).all()
        return [{
            "id": p.id,
            "patient_code": p.patient_code,
            "full_name": p.full_name,
            "date_of_birth": p.date_of_birth,
            "contact": p.contact
        } for p in pts]

    if user.role == "admin":
        # Admin sees all patients with assigned doctors
        pts = db.query(Patient).order_by(Patient.id.asc()).all()
        assignments = db.query(DoctorPatientAssignment).all()
        doctors_map = {d.id: d for d in db.query(User).filter_by(role="doctor").all()}
        
        patient_assignments = {}
        for a in assignments:
            if a.doctor_id in doctors_map:
                doc = doctors_map[a.doctor_id]
                patient_assignments.setdefault(a.patient_id, []).append({
                    "id": doc.id,
                    "username": doc.username,
                    "full_name": doc.full_name
                })
        
        return [{
            "id": p.id,
            "patient_code": p.patient_code,
            "full_name": p.full_name,
            "date_of_birth": p.date_of_birth,
            "contact": p.contact,
            "assigned_doctors": patient_assignments.get(p.id, [])
        } for p in pts]

    raise HTTPException(status_code=403, detail="Unauthorized access")


@app.post("/api/patients")
def create_patient(body: PatientCreate, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role not in {"admin", "doctor"}:
        log(db, user.id, "UNAUTHORIZED_PATIENT_CREATION_ATTEMPT", status_val="BLOCKED", user_role=user.role)
        raise HTTPException(status_code=403, detail="Permission denied")

    count = db.query(Patient).count() + 1001
    patient_code = f"PAT-{count}"
    patient = Patient(
        patient_code=patient_code,
        full_name=body.full_name.strip(),
        date_of_birth=body.date_of_birth.strip(),
        contact=body.contact.strip()
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # If created by a doctor, automatically assign the patient to this doctor
    if user.role == "doctor":
        db.add(DoctorPatientAssignment(doctor_id=user.id, patient_id=patient.id))
        db.commit()
        log(db, user.id, "CREATE_PATIENT", status_val="SUCCESS", user_role=user.role, details=f"Created patient {patient.patient_code} ({patient.full_name}) and auto-assigned to doctor")
    else:
        log(db, user.id, "CREATE_PATIENT", status_val="SUCCESS", user_role=user.role, details=f"Admin created patient {patient.patient_code} ({patient.full_name})")

    return {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient.full_name,
        "date_of_birth": patient.date_of_birth,
        "contact": patient.contact
    }


@app.post("/api/patients/{patient_id}/assign")
def assign_patient(patient_id: int, body: PatientAssign, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "admin":
        log(db, user.id, "UNAUTHORIZED_ASSIGNMENT_ATTEMPT", status_val="BLOCKED", user_role=user.role, details=f"Attempted to assign patient {patient_id} to doctor {body.doctor_id}")
        raise HTTPException(status_code=403, detail="Admin access required to assign patients")

    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    doctor = db.get(User, body.doctor_id)
    if not doctor or doctor.role != "doctor":
        raise HTTPException(status_code=400, detail="Invalid doctor selected")

    existing = db.query(DoctorPatientAssignment).filter_by(doctor_id=doctor.id, patient_id=patient.id).first()
    if not existing:
        assignment = DoctorPatientAssignment(doctor_id=doctor.id, patient_id=patient.id)
        db.add(assignment)
        db.commit()

    log(db, user.id, "ASSIGN_PATIENT", status_val="SUCCESS", user_role=user.role, details=f"Assigned patient {patient.patient_code} ({patient.full_name}) to doctor {doctor.username} ({doctor.full_name})")
    return {
        "message": f"Patient {patient.full_name} successfully assigned to {doctor.full_name}",
        "patient_id": patient.id,
        "doctor_id": doctor.id
    }


# ---------------- MEDICAL RECORDS ----------------

@app.get("/api/records")
def get_records(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    query = db.query(MedicalRecord)

    if user.role == "doctor":
        # Authorized patients for this doctor
        assignments = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id).all()
        assigned_pids = [a.patient_id for a in assignments]
        query = query.filter(MedicalRecord.patient_id.in_(assigned_pids))

    elif user.role == "patient":
        # Only own records
        patient = db.query(Patient).filter((Patient.user_id == user.id) | (Patient.full_name == user.full_name)).first()
        if not patient:
            return []
        query = query.filter(MedicalRecord.patient_id == patient.id)

    elif user.role == "admin":
        # Admin can view all records for audit/security inspection
        pass
    else:
        raise HTTPException(status_code=403, detail="Unauthorized")

    records = query.order_by(MedicalRecord.created_at.desc()).all()
    users_map = {u.id: u for u in db.query(User).all()}
    patients_map = {p.id: p for p in db.query(Patient).all()}

    results = []
    for record in records:
        patient = patients_map.get(record.patient_id)
        doctor = users_map.get(record.doctor_id)
        updater = users_map.get(record.last_updated_by_id) if record.last_updated_by_id else doctor

        try:
            plain = decrypt_record(record.encrypted_data)
            recalculated = integrity_hash(plain)
            if recalculated == record.integrity_hash:
                status_val = "VALID"
                data = json.loads(plain)
            else:
                status_val = "TAMPERED"
                data = {}
        except Exception:
            status_val = "TAMPERED"
            data = {}

        log(db, user.id, "VIEW_RECORD", record.id, status_val=status_val, user_role=user.role, details=f"Decrypted record #{record.id} with integrity {status_val}")

        results.append({
            "id": record.id,
            "patient_id": patient.id if patient else record.patient_id,
            "patient_name": patient.full_name if patient else "Unknown",
            "patient_code": patient.patient_code if patient else "PAT-???",
            "doctor_id": doctor.id if doctor else record.doctor_id,
            "doctor_name": doctor.full_name if doctor else "Unknown Doctor",
            "last_updated_by": updater.full_name if updater else None,
            "diagnosis": data.get("diagnosis", "[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]" if status_val == "TAMPERED" else ""),
            "prescription": data.get("prescription", "[REDACTED]" if status_val == "TAMPERED" else ""),
            "notes": data.get("notes", "[REDACTED]" if status_val == "TAMPERED" else ""),
            "visit_date": data.get("visit_date", "—"),
            "integrity_status": status_val,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        })

    return results


@app.get("/api/records/{record_id}")
def get_record(record_id: int, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    record = db.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")

    patient = db.get(Patient, record.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # RBAC authorization check
    if user.role == "doctor":
        is_assigned = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id, patient_id=patient.id).first()
        if not is_assigned:
            log(db, user.id, "UNAUTHORIZED_RECORD_ACCESS_ATTEMPT", record_id, status_val="BLOCKED", user_role=user.role, details=f"Doctor {user.username} tried to access record {record_id} of unassigned patient {patient.patient_code}")
            raise HTTPException(status_code=403, detail="Access denied: Patient is not assigned to you")
    elif user.role == "patient":
        if patient.user_id != user.id and patient.full_name != user.full_name:
            log(db, user.id, "UNAUTHORIZED_RECORD_ACCESS_ATTEMPT", record_id, status_val="BLOCKED", user_role=user.role, details=f"Patient {user.username} tried to access another patient's record {record_id}")
            raise HTTPException(status_code=403, detail="Access denied: You can only view your own medical records")

    try:
        plain = decrypt_record(record.encrypted_data)
        recalculated = integrity_hash(plain)
        if recalculated == record.integrity_hash:
            status_val = "VALID"
            data = json.loads(plain)
        else:
            status_val = "TAMPERED"
            data = {}
    except Exception:
        status_val = "TAMPERED"
        data = {}

    log(db, user.id, "VIEW_RECORD", record.id, status_val=status_val, user_role=user.role, details=f"Decrypted record #{record.id} with integrity {status_val}")
    doctor = db.get(User, record.doctor_id)
    updater = db.get(User, record.last_updated_by_id) if record.last_updated_by_id else doctor

    return {
        "id": record.id,
        "patient_id": patient.id,
        "patient_name": patient.full_name,
        "patient_code": patient.patient_code,
        "doctor_id": doctor.id if doctor else record.doctor_id,
        "doctor_name": doctor.full_name if doctor else "Unknown Doctor",
        "last_updated_by": updater.full_name if updater else None,
        "diagnosis": data.get("diagnosis", "[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]" if status_val == "TAMPERED" else ""),
        "prescription": data.get("prescription", "[REDACTED]" if status_val == "TAMPERED" else ""),
        "notes": data.get("notes", "[REDACTED]" if status_val == "TAMPERED" else ""),
        "visit_date": data.get("visit_date", "—"),
        "integrity_status": status_val,
        "created_at": record.created_at.isoformat() if record.created_at else "",
        "updated_at": record.updated_at.isoformat() if record.updated_at else None
    }


@app.get("/api/patients/{patient_id}/records")
def get_patient_records(patient_id: int, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if user.role == "doctor":
        is_assigned = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id, patient_id=patient.id).first()
        if not is_assigned:
            log(db, user.id, "UNAUTHORIZED_PATIENT_RECORDS_ACCESS_ATTEMPT", status_val="BLOCKED", user_role=user.role, details=f"Doctor {user.username} tried to access records of unassigned patient {patient.patient_code}")
            raise HTTPException(status_code=403, detail="Access denied: Patient is not assigned to you")
    elif user.role == "patient":
        if patient.user_id != user.id and patient.full_name != user.full_name:
            log(db, user.id, "UNAUTHORIZED_PATIENT_RECORDS_ACCESS_ATTEMPT", status_val="BLOCKED", user_role=user.role, details=f"Patient {user.username} tried to access records of patient {patient.patient_code}")
            raise HTTPException(status_code=403, detail="Access denied: You can only view your own medical records")

    records = db.query(MedicalRecord).filter_by(patient_id=patient.id).order_by(MedicalRecord.created_at.desc()).all()
    users_map = {u.id: u for u in db.query(User).all()}

    results = []
    for record in records:
        doctor = users_map.get(record.doctor_id)
        updater = users_map.get(record.last_updated_by_id) if record.last_updated_by_id else doctor
        try:
            plain = decrypt_record(record.encrypted_data)
            status_val = "VALID" if integrity_hash(plain) == record.integrity_hash else "TAMPERED"
            data = json.loads(plain) if status_val == "VALID" else {}
        except Exception:
            status_val, data = "TAMPERED", {}

        log(db, user.id, "VIEW_RECORD", record.id, status_val=status_val, user_role=user.role, details=f"Viewed record #{record.id} for patient {patient.patient_code}")
        results.append({
            "id": record.id,
            "patient_id": patient.id,
            "patient_name": patient.full_name,
            "patient_code": patient.patient_code,
            "doctor_id": doctor.id if doctor else record.doctor_id,
            "doctor_name": doctor.full_name if doctor else "Unknown Doctor",
            "last_updated_by": updater.full_name if updater else None,
            "diagnosis": data.get("diagnosis", ""),
            "prescription": data.get("prescription", ""),
            "notes": data.get("notes", ""),
            "visit_date": data.get("visit_date", "—"),
            "integrity_status": status_val,
            "created_at": record.created_at.isoformat() if record.created_at else "",
            "updated_at": record.updated_at.isoformat() if record.updated_at else None
        })
    return results


@app.post("/api/records")
def create_record(body: RecordCreate, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "doctor":
        log(db, user.id, "UNAUTHORIZED_RECORD_CREATION_ATTEMPT", status_val="BLOCKED", user_role=user.role)
        raise HTTPException(status_code=403, detail="Only doctors can create medical records")

    patient = db.get(Patient, body.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Verify doctor is assigned to this patient
    is_assigned = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id, patient_id=patient.id).first()
    if not is_assigned:
        log(db, user.id, "UNAUTHORIZED_RECORD_CREATION_ATTEMPT", status_val="BLOCKED", user_role=user.role, details=f"Doctor {user.username} tried to create record for unassigned patient {patient.patient_code}")
        raise HTTPException(status_code=403, detail="Access denied: Patient is not assigned to you")

    data = {
        "diagnosis": body.diagnosis.strip(),
        "prescription": body.prescription.strip(),
        "notes": body.notes.strip(),
        "visit_date": body.visit_date.strip() if body.visit_date else datetime.utcnow().strftime("%Y-%m-%d")
    }
    plain = json.dumps(data, sort_keys=True)
    digest = integrity_hash(plain)
    encrypted = encrypt_record(plain)

    record = MedicalRecord(
        patient_id=patient.id,
        doctor_id=user.id,
        last_updated_by_id=user.id,
        encrypted_data=encrypted,
        integrity_hash=digest,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    log(db, user.id, "CREATE_RECORD", record.id, status_val="SUCCESS", user_role=user.role, details=f"Created medical record #{record.id} for patient {patient.patient_code} ({patient.full_name})")
    return {"message": "Record stored securely", "record_id": record.id}


@app.put("/api/records/{record_id}")
def update_record(record_id: int, body: RecordUpdate, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "doctor":
        log(db, user.id, "UNAUTHORIZED_RECORD_UPDATE_ATTEMPT", record_id, status_val="BLOCKED", user_role=user.role)
        raise HTTPException(status_code=403, detail="Only doctors can edit medical records")

    record = db.get(MedicalRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")

    patient = db.get(Patient, record.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Verify doctor is assigned to this patient
    is_assigned = db.query(DoctorPatientAssignment).filter_by(doctor_id=user.id, patient_id=patient.id).first()
    if not is_assigned:
        log(db, user.id, "UNAUTHORIZED_RECORD_UPDATE_ATTEMPT", record.id, status_val="BLOCKED", user_role=user.role, details=f"Doctor {user.username} tried to edit record {record_id} of unassigned patient {patient.patient_code}")
        raise HTTPException(status_code=403, detail="Access denied: Patient is not assigned to you")

    data = {
        "diagnosis": body.diagnosis.strip(),
        "prescription": body.prescription.strip(),
        "notes": body.notes.strip(),
        "visit_date": body.visit_date.strip() if body.visit_date else datetime.utcnow().strftime("%Y-%m-%d")
    }
    plain = json.dumps(data, sort_keys=True)
    digest = integrity_hash(plain)
    encrypted = encrypt_record(plain)

    record.encrypted_data = encrypted
    record.integrity_hash = digest
    record.last_updated_by_id = user.id
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)

    log(db, user.id, "UPDATE_RECORD", record.id, status_val="SUCCESS", user_role=user.role, details=f"Updated medical record #{record.id} for patient {patient.patient_code} ({patient.full_name})")
    return {"message": "Record updated securely", "record_id": record.id}


# ---------------- AUDIT LOGS ----------------

@app.get("/api/audit")
def get_audit_logs(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "admin":
        log(db, user.id, "UNAUTHORIZED_AUDIT_ACCESS_ATTEMPT", status_val="BLOCKED", user_role=user.role)
        raise HTTPException(status_code=403, detail="Admin access required to view audit logs")

    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    users_map = {u.id: u for u in db.query(User).all()}

    return [{
        "id": x.id,
        "user_id": x.user_id,
        "username": users_map[x.user_id].username if x.user_id in users_map else ("admin" if x.user_id == 0 else f"User #{x.user_id}"),
        "user_name": users_map[x.user_id].full_name if x.user_id in users_map else "System / Guest",
        "user_role": x.user_role or (users_map[x.user_id].role if x.user_id in users_map else "unknown"),
        "action": x.action,
        "record_id": x.record_id,
        "status": x.status,
        "details": x.details or "—",
        "created_at": x.created_at.isoformat() if x.created_at else ""
    } for x in logs]


# ---------------- ADMIN CRYPTOGRAPHY TEST ----------------

@app.post("/api/admin/crypto/encrypt")
def admin_crypto_encrypt(body: CryptoEncryptRequest, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "admin":
        log(db, user.id, "UNAUTHORIZED_CRYPTO_TEST_ATTEMPT", status_val="BLOCKED", user_role=user.role, details="Non-admin attempted crypto test")
        raise HTTPException(status_code=403, detail="Admin access required for Cryptography Test")

    if not body.plaintext:
        raise HTTPException(status_code=400, detail="Plaintext cannot be empty")

    # Encrypt using the same AES-256-GCM implementation and key used for medical records
    ciphertext = encrypt_record(body.plaintext)
    log(db, user.id, "CRYPTO_ENCRYPT_TEST", status_val="SUCCESS", user_role=user.role, details=f"Admin encrypted {len(body.plaintext)} chars via AES-256-GCM")

    return {
        "success": True,
        "plaintext": body.plaintext,
        "ciphertext": ciphertext,
        "algorithm": "AES-256-GCM",
        "key_source": "backend/aes_gcm.key"
    }


@app.post("/api/admin/crypto/decrypt")
def admin_crypto_decrypt(body: CryptoDecryptRequest, authorization: str | None = Header(None), db: Session = Depends(get_db)):
    user = current_user(authorization, db)
    if user.role != "admin":
        log(db, user.id, "UNAUTHORIZED_CRYPTO_TEST_ATTEMPT", status_val="BLOCKED", user_role=user.role, details="Non-admin attempted crypto test")
        raise HTTPException(status_code=403, detail="Admin access required for Cryptography Test")

    if not body.ciphertext or not body.ciphertext.strip():
        raise HTTPException(status_code=400, detail="Ciphertext cannot be empty")

    try:
        # Decrypt using the same AES-256-GCM implementation and key used for medical records
        plaintext = decrypt_record(body.ciphertext.strip())
        log(db, user.id, "CRYPTO_DECRYPT_TEST", status_val="SUCCESS", user_role=user.role, details=f"Admin decrypted {len(plaintext)} chars via AES-256-GCM")
        return {
            "success": True,
            "ciphertext": body.ciphertext.strip(),
            "plaintext": plaintext,
            "algorithm": "AES-256-GCM",
            "key_source": "backend/aes_gcm.key"
        }
    except Exception as e:
        log(db, user.id, "CRYPTO_DECRYPT_TEST", status_val="FAILED", user_role=user.role, details=f"Decryption failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Decryption failed: Invalid ciphertext or authentication failed ({str(e)})")
