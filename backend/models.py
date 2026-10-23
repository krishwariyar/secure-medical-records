from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    full_name = Column(String(100), nullable=False)

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    patient_code = Column(String(30), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    date_of_birth = Column(String(20), nullable=False)
    contact = Column(String(30), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class DoctorPatientAssignment(Base):
    __tablename__ = "doctor_patient_assignments"
    __table_args__ = (UniqueConstraint("doctor_id", "patient_id", name="uq_doctor_patient"),)
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)

class MedicalRecord(Base):
    __tablename__ = "medical_records"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    last_updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    encrypted_data = Column(Text, nullable=False)
    integrity_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    user_role = Column(String(30), nullable=True)
    action = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False)
    details = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
