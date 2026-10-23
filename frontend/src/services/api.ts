const API = 'http://127.0.0.1:8000/api';

export async function api(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(API + path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

export async function login(username: string, password: string) {
  return api('/login', { method: 'POST', body: JSON.stringify({ username, password }) });
}

export async function logout() {
  return api('/logout', { method: 'POST' }).catch(() => ({}));
}

export async function getPatients() {
  return api('/patients');
}

export async function createPatient(data: { full_name: string; date_of_birth: string; contact: string }) {
  return api('/patients', { method: 'POST', body: JSON.stringify(data) });
}

export async function assignPatient(patientId: number, doctorId: number) {
  return api(`/patients/${patientId}/assign`, {
    method: 'POST',
    body: JSON.stringify({ doctor_id: doctorId })
  });
}

export async function getDoctors() {
  return api('/users/doctors');
}

export async function createDoctor(data: { username: string; full_name: string; password: string }) {
  return api('/users/doctors', { method: 'POST', body: JSON.stringify(data) });
}

export async function getRecords() {
  return api('/records');
}

export async function getRecord(recordId: number) {
  return api(`/records/${recordId}`);
}

export async function createRecord(data: {
  patient_id: number;
  diagnosis: string;
  prescription: string;
  notes: string;
  visit_date?: string;
}) {
  return api('/records', { method: 'POST', body: JSON.stringify(data) });
}

export async function updateRecord(
  recordId: number,
  data: { diagnosis: string; prescription: string; notes: string; visit_date?: string }
) {
  return api(`/records/${recordId}`, { method: 'PUT', body: JSON.stringify(data) });
}

export async function getAudit() {
  return api('/audit');
}

export async function encryptText(plaintext: string) {
  return api('/admin/crypto/encrypt', {
    method: 'POST',
    body: JSON.stringify({ plaintext })
  });
}

export async function decryptText(ciphertext: string) {
  return api('/admin/crypto/decrypt', {
    method: 'POST',
    body: JSON.stringify({ ciphertext })
  });
}
