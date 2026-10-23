"""
Automated Comprehensive Test Suite for SMRMS
Executes and validates TEST 1 through TEST 17 plus Tampering Detection.
"""
import json
from fastapi.testclient import TestClient
from database import SessionLocal, engine, Base
from models import User, Patient, DoctorPatientAssignment, MedicalRecord, AuditLog
from security import verify_password, integrity_hash, decrypt_record, encrypt_record
from main import app, seed

client = TestClient(app)

def test_full_security_workflow():
    print("\n================ STARTING FULL SECURITY WORKFLOW ================")
    db = SessionLocal()

    # ---------------- TEST 1: Login as admin ----------------
    print("\n--- TEST 1: Login as admin ---")
    res1 = client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert res1.status_code == 200, f"Admin login failed: {res1.text}"
    admin_data = res1.json()
    admin_token = admin_data["token"]
    assert admin_data["user"]["role"] == "admin"
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✓ TEST 1 PASSED: Admin authenticated successfully with role 'admin'")

    # ---------------- TEST 2: Create Doctor 2 ----------------
    print("\n--- TEST 2: Create Doctor 2 ---")
    doc2_username = "doctor2"
    doc2_password = "Doctor2@123"
    doc2_fullname = "Dr. Rajesh Kumar"

    # If doctor2 already existed from prior run, clean it up for pristine test
    existing_doc2 = db.query(User).filter_by(username=doc2_username).first()
    if existing_doc2:
        db.query(DoctorPatientAssignment).filter_by(doctor_id=existing_doc2.id).delete()
        db.query(MedicalRecord).filter_by(doctor_id=existing_doc2.id).delete()
        db.delete(existing_doc2)
        db.commit()

    res2 = client.post("/api/users/doctors", headers=admin_headers, json={
        "username": doc2_username,
        "password": doc2_password,
        "full_name": doc2_fullname
    })
    assert res2.status_code == 200, f"Doctor 2 creation failed: {res2.text}"
    doc2_created = res2.json()
    doc2_id = doc2_created["id"]
    assert doc2_created["username"] == doc2_username
    assert doc2_created["role"] == "doctor"

    # Verify password is not plaintext in DB
    db_doc2 = db.get(User, doc2_id)
    assert db_doc2.password_hash != doc2_password
    assert verify_password(doc2_password, db_doc2.password_hash)
    print(f"✓ TEST 2 PASSED: Doctor 2 created (ID #{doc2_id}). Password hashed with bcrypt.")

    # ---------------- TEST 3: Logout ----------------
    print("\n--- TEST 3: Logout ---")
    res3 = client.post("/api/logout", headers=admin_headers)
    assert res3.status_code == 200
    print("✓ TEST 3 PASSED: Admin logged out.")

    # ---------------- TEST 4: Login as Doctor 2 ----------------
    print("\n--- TEST 4: Login as Doctor 2 ---")
    res4 = client.post("/api/login", json={"username": doc2_username, "password": doc2_password})
    assert res4.status_code == 200, f"Doctor 2 login failed: {res4.text}"
    doc2_auth = res4.json()
    doc2_token = doc2_auth["token"]
    doc2_headers = {"Authorization": f"Bearer {doc2_token}"}
    print(f"✓ TEST 4 PASSED: Doctor 2 successfully logged in with token.")

    # ---------------- TEST 5: Verify Doctor 2 separate identity & permissions ----------------
    print("\n--- TEST 5: Verify Doctor 2 identity & RBAC permissions ---")
    assert doc2_auth["user"]["id"] == doc2_id
    assert doc2_auth["user"]["role"] == "doctor"
    assert doc2_auth["user"]["name"] == doc2_fullname

    # Doctor 2 must NOT be allowed to access admin audit logs
    res_audit_doc = client.get("/api/audit", headers=doc2_headers)
    assert res_audit_doc.status_code == 403, f"Doctor should not access audit logs: {res_audit_doc.text}"

    # Doctor 2 must NOT be allowed to create another doctor
    res_doc_create = client.post("/api/users/doctors", headers=doc2_headers, json={
        "username": "rogue_doc", "password": "Doc@123", "full_name": "Rogue Doctor"
    })
    assert res_doc_create.status_code == 403
    print("✓ TEST 5 PASSED: Doctor 2 has distinct identity and RBAC denies admin privileges.")

    # ---------------- TEST 6: Assign a patient to Doctor 2 ----------------
    print("\n--- TEST 6: Assign patient PAT-1002 (Krish) to Doctor 2 ---")
    patient_krish = db.query(Patient).filter_by(patient_code="PAT-1002").first()
    assert patient_krish is not None, "Patient PAT-1002 should exist in database"

    res6 = client.post(f"/api/patients/{patient_krish.id}/assign", headers=admin_headers, json={
        "doctor_id": doc2_id
    })
    assert res6.status_code == 200, f"Patient assignment failed: {res6.text}"
    print(f"✓ TEST 6 PASSED: Patient {patient_krish.full_name} assigned to Doctor 2 by Admin.")

    # ---------------- TEST 7: Login as Doctor 2 and check assigned patients ----------------
    print("\n--- TEST 7: Login as Doctor 2 and check assigned patients ---")
    res7 = client.get("/api/patients", headers=doc2_headers)
    assert res7.status_code == 200
    doc2_patients = res7.json()
    doc2_patient_ids = [p["id"] for p in doc2_patients]
    assert patient_krish.id in doc2_patient_ids, "PAT-1002 must be visible to Doctor 2"

    # Patient PAT-1001 (assigned to Doctor 1) MUST NOT be in Doctor 2's list
    p1 = db.query(Patient).filter_by(patient_code="PAT-1001").first()
    assert p1.id not in doc2_patient_ids, "PAT-1001 must NOT be visible to Doctor 2"
    print(f"✓ TEST 7 PASSED: Doctor 2 sees only assigned patient ({patient_krish.full_name}) and NOT Doctor 1's patient.")

    # ---------------- TEST 8: Create a medical record for assigned patient ----------------
    print("\n--- TEST 8: Create medical record for assigned patient ---")
    clinical_input = {
        "patient_id": patient_krish.id,
        "diagnosis": "Seasonal bronchitis",
        "prescription": "Azithromycin 500mg daily",
        "notes": "Mild cough and low grade fever. Review in 5 days.",
        "visit_date": "2026-10-05"
    }
    res8 = client.post("/api/records", headers=doc2_headers, json=clinical_input)
    assert res8.status_code == 200, f"Record creation failed: {res8.text}"
    rec8_data = res8.json()
    new_record_id = rec8_data["record_id"]

    # Verify backend storage: ciphertext is encrypted, not plaintext
    db_rec = db.get(MedicalRecord, new_record_id)
    assert db_rec is not None
    assert "Seasonal bronchitis" not in db_rec.encrypted_data, "Clinical text must NOT be stored in plaintext"
    assert "Azithromycin" not in db_rec.encrypted_data, "Prescription must NOT be stored in plaintext"
    # Verify SHA-256 hash matches plaintext
    expected_plain = json.dumps({
        "diagnosis": clinical_input["diagnosis"],
        "notes": clinical_input["notes"],
        "prescription": clinical_input["prescription"],
        "visit_date": clinical_input["visit_date"]
    }, sort_keys=True)
    assert db_rec.integrity_hash == integrity_hash(expected_plain)
    print(f"✓ TEST 8 PASSED: Medical record #{new_record_id} created. Stored ciphertext is AES encrypted and SHA-256 digest is recorded.")

    # ---------------- TEST 9: Verify diagnosis, prescription and notes appear in Records ----------------
    print("\n--- TEST 9: Verify diagnosis, prescription and notes appear in Records ---")
    res9 = client.get("/api/records", headers=doc2_headers)
    assert res9.status_code == 200
    doc2_records = res9.json()
    my_record = next((r for r in doc2_records if r["id"] == new_record_id), None)
    assert my_record is not None
    assert my_record["diagnosis"] == "Seasonal bronchitis"
    assert my_record["prescription"] == "Azithromycin 500mg daily"
    assert my_record["notes"] == "Mild cough and low grade fever. Review in 5 days."
    assert my_record["integrity_status"] == "VALID"
    assert my_record["doctor_name"] == doc2_fullname
    print("✓ TEST 9 PASSED: Record retrieved, decrypted, and verified successfully.")

    # ---------------- TEST 10: Edit the diagnosis/prescription ----------------
    print("\n--- TEST 10: Edit diagnosis and prescription ---")
    updated_input = {
        "diagnosis": "Bronchitis - resolving",
        "prescription": "Azithromycin 500mg daily + Cough lozenges prn",
        "notes": "Patient condition improving. Advised rest.",
        "visit_date": "2026-10-06"
    }
    res10 = client.put(f"/api/records/{new_record_id}", headers=doc2_headers, json=updated_input)
    assert res10.status_code == 200, f"Record update failed: {res10.text}"
    print("✓ TEST 10 PASSED: Record updated via PUT /api/records/{id}.")

    # ---------------- TEST 11: Verify updated record is displayed ----------------
    print("\n--- TEST 11: Verify updated record is displayed ---")
    res11 = client.get(f"/api/records/{new_record_id}", headers=doc2_headers)
    assert res11.status_code == 200
    updated_rec_view = res11.json()
    assert updated_rec_view["diagnosis"] == "Bronchitis - resolving"
    assert updated_rec_view["prescription"] == "Azithromycin 500mg daily + Cough lozenges prn"
    assert updated_rec_view["notes"] == "Patient condition improving. Advised rest."
    print("✓ TEST 11 PASSED: Updated clinical data correctly displayed.")

    # ---------------- TEST 12: Verify SHA-256 integrity status is still 'Verified' ----------------
    print("\n--- TEST 12: Verify SHA-256 integrity status is still 'Verified' ---")
    assert updated_rec_view["integrity_status"] == "VALID"
    # Inspect DB record directly
    db.expire_all()
    db_rec_updated = db.get(MedicalRecord, new_record_id)
    updated_plain = decrypt_record(db_rec_updated.encrypted_data)
    assert integrity_hash(updated_plain) == db_rec_updated.integrity_hash
    print("✓ TEST 12 PASSED: SHA-256 digest recalculated on update and integrity status is Verified (VALID).")

    # ---------------- TEST 13: Verify audit log contains creation and update ----------------
    print("\n--- TEST 13: Verify audit log contains creation and update ---")
    res13 = client.get("/api/audit", headers=admin_headers)
    assert res13.status_code == 200
    audit_events = res13.json()
    actions = [e["action"] for e in audit_events]
    assert "CREATE_DOCTOR" in actions
    assert "ASSIGN_PATIENT" in actions
    assert "CREATE_RECORD" in actions
    assert "UPDATE_RECORD" in actions
    print("✓ TEST 13 PASSED: Audit log contains CREATE_DOCTOR, ASSIGN_PATIENT, CREATE_RECORD, and UPDATE_RECORD.")

    # ---------------- TEST 14: Login as another doctor ----------------
    print("\n--- TEST 14: Login as another doctor (Dr. Aisha Mehta / 'doctor') ---")
    res14 = client.post("/api/login", json={"username": "doctor", "password": "Doctor@123"})
    assert res14.status_code == 200
    doc1_token = res14.json()["token"]
    doc1_headers = {"Authorization": f"Bearer {doc1_token}"}
    print("✓ TEST 14 PASSED: Doctor 1 logged in.")

    # ---------------- TEST 15: Attempt to access Doctor 2's patient -> Backend rejects ----------------
    print("\n--- TEST 15: Doctor 1 attempts unauthorized access to Doctor 2's patient & record ---")
    # Doctor 1 attempting to view Doctor 2's record
    res15_view = client.get(f"/api/records/{new_record_id}", headers=doc1_headers)
    assert res15_view.status_code == 403, f"Expected 403 for unauthorized record access, got {res15_view.status_code}"
    assert "Access denied" in res15_view.text

    # Doctor 1 attempting to edit Doctor 2's record
    res15_edit = client.put(f"/api/records/{new_record_id}", headers=doc1_headers, json=updated_input)
    assert res15_edit.status_code == 403

    # Doctor 1 attempting to create a record for Doctor 2's patient
    res15_create = client.post("/api/records", headers=doc1_headers, json={
        "patient_id": patient_krish.id,
        "diagnosis": "Malicious diagnosis",
        "prescription": "None",
        "notes": "Unauthorized"
    })
    assert res15_create.status_code == 403
    print("✓ TEST 15 PASSED: Backend strictly rejects unauthorized doctor access with 403 Forbidden.")

    # ---------------- TEST 16: Login as patient -> view own records only ----------------
    print("\n--- TEST 16: Login as patient (Rahul Sharma / 'patient') ---")
    res16_login = client.post("/api/login", json={"username": "patient", "password": "Patient@123"})
    assert res16_login.status_code == 200
    patient_token = res16_login.json()["token"]
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    res16_recs = client.get("/api/records", headers=patient_headers)
    assert res16_recs.status_code == 200
    pat_records = res16_recs.json()
    # Patient Rahul Sharma should only see their own records (PAT-1001)
    for r in pat_records:
        assert r["patient_name"] == "Rahul Sharma"
        assert r["patient_code"] == "PAT-1001"
    # Ensure Doctor 2's record for Krish is NOT returned
    assert all(r["id"] != new_record_id for r in pat_records)
    print("✓ TEST 16 PASSED: Patient can only view their own medical records.")

    # ---------------- TEST 17: Patient unauthorized access to another patient's record ----------------
    print("\n--- TEST 17: Patient attempts unauthorized access to another patient's record ---")
    res17 = client.get(f"/api/records/{new_record_id}", headers=patient_headers)
    assert res17.status_code == 403, f"Expected 403 for cross-patient access, got {res17.status_code}"

    # Patient attempting to create a record
    res17_create = client.post("/api/records", headers=patient_headers, json={
        "patient_id": patient_krish.id, "diagnosis": "X", "prescription": "Y", "notes": "Z"
    })
    assert res17_create.status_code == 403
    print("✓ TEST 17 PASSED: Backend rejects cross-patient and unauthorized patient operations with 403 Forbidden.")

    # ---------------- BONUS TEST: Cryptographic Tampering Detection ----------------
    print("\n--- BONUS: Cryptographic Tampering Verification ---")
    # Directly tamper with ciphertext in database for record #1
    rec1 = db.get(MedicalRecord, 1)
    original_cipher = rec1.encrypted_data
    # Corrupt ciphertext bytes
    tampered_cipher = original_cipher[:-4] + "AAAA"
    rec1.encrypted_data = tampered_cipher
    db.commit()

    # Now attempt to read the record via API
    res_tamper = client.get("/api/records/1", headers=admin_headers)
    assert res_tamper.status_code == 200
    tampered_view = res_tamper.json()
    assert tampered_view["integrity_status"] == "TAMPERED"
    assert "[DATA BLOCKED: INTEGRITY VIOLATION DETECTED]" in tampered_view["diagnosis"]
    assert "[REDACTED]" in tampered_view["prescription"]
    print("✓ BONUS TEST PASSED: Tampering detected! Decryption/digest mismatch triggers TAMPERED status and blocks clinical data.")

    # Restore record #1 so DB remains healthy
    rec1.encrypted_data = original_cipher
    db.commit()
    db.close()

    print("\n================ ALL 17 SPECIFICATION TESTS + TAMPERING PASSED! ================\n")

if __name__ == "__main__":
    test_full_security_workflow()
