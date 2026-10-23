from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class DoctorCreate(BaseModel):
    username: str
    password: str
    full_name: str

class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: str
    contact: str

class PatientAssign(BaseModel):
    doctor_id: int

class RecordCreate(BaseModel):
    patient_id: int
    diagnosis: str
    prescription: str
    notes: str
    visit_date: str | None = None

class RecordUpdate(BaseModel):
    diagnosis: str
    prescription: str
    notes: str
    visit_date: str | None = None

class RecordResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_code: str
    doctor_id: int
    doctor_name: str
    last_updated_by: str | None = None
    diagnosis: str
    prescription: str
    notes: str
    visit_date: str
    integrity_status: str
    created_at: str
    updated_at: str | None = None

class CryptoEncryptRequest(BaseModel):
    plaintext: str

class CryptoDecryptRequest(BaseModel):
    ciphertext: str
