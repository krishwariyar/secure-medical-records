import { useEffect, useState } from 'react';
import {
  LockKeyhole, ShieldCheck, FileText, Users, ClipboardList,
  LogOut, Plus, CheckCircle2, AlertTriangle, Edit3, UserCheck, Stethoscope,
  KeyRound, ArrowRight
} from 'lucide-react';
import {
  login, logout, getPatients, createPatient, assignPatient,
  getDoctors, createDoctor, getRecords, createRecord, updateRecord, getAudit,
  encryptText, decryptText
} from './services/api';

type User = { id: number; username: string; name: string; role: 'admin' | 'doctor' | 'patient' };

type Patient = {
  id: number;
  patient_code: string;
  full_name: string;
  date_of_birth: string;
  contact: string;
  assigned_doctors?: Array<{ id: number; username: string; full_name: string }>;
};

type Doctor = { id: number; username: string; full_name: string; role: string };

type MedicalRecord = {
  id: number;
  patient_id: number;
  patient_name: string;
  patient_code: string;
  doctor_id: number;
  doctor_name: string;
  last_updated_by?: string;
  diagnosis: string;
  prescription: string;
  notes: string;
  visit_date: string;
  integrity_status: string;
  created_at: string;
  updated_at?: string;
};

type AuditRow = {
  id: number;
  user_id: number;
  username: string;
  user_name: string;
  user_role: string;
  action: string;
  record_id?: number;
  status: string;
  details: string;
  created_at: string;
};

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [username, setUsername] = useState('doctor');
  const [password, setPassword] = useState('Doctor@123');
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const r = await login(username, password);
      localStorage.setItem('token', r.token);
      onLogin(r.user);
    } catch (err: any) {
      setError(err.message || 'Login failed');
    }
  }

  function fillCreds(u: string, p: string) {
    setUsername(u);
    setPassword(p);
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="brand">
          <div className="brand-icon"><LockKeyhole /></div>
          <div>
            <b>Secure Medical</b>
            <span>Record Management System</span>
          </div>
        </div>
        <h1>Secure access</h1>
        <p className="muted">Sign in with role-based credentials to access clinical data.</p>
        <form onSubmit={submit}>
          <label>
            Username
            <input value={username} onChange={e => setUsername(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
          </label>
          {error && <div className="error">{error}</div>}
          <button type="submit">Sign in</button>
        </form>

        <div className="demo">Quick Demo Credentials:</div>
        <div className="demo-chips">
          <button type="button" className="chip" onClick={() => fillCreds('admin', 'Admin@123')}>Admin</button>
          <button type="button" className="chip" onClick={() => fillCreds('doctor', 'Doctor@123')}>Doctor 1</button>
          <button type="button" className="chip" onClick={() => fillCreds('doctor2', 'Doctor2@123')}>Doctor 2</button>
          <button type="button" className="chip" onClick={() => fillCreds('doctor3', 'Doctor3@123')}>Doctor 3</button>
          <button type="button" className="chip" onClick={() => fillCreds('patient', 'Patient@123')}>Patient</button>
        </div>
      </div>
    </main>
  );
}

function App() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    localStorage.removeItem('token');
  }, []);

  if (!user) return <Login onLogin={setUser} />;

  return (
    <Dashboard
      user={user}
      onLogout={async () => {
        await logout();
        localStorage.removeItem('token');
        setUser(null);
      }}
    />
  );
}

function Dashboard({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [records, setRecords] = useState<MedicalRecord[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [tab, setTab] = useState<'records' | 'patients' | 'doctors' | 'audit' | 'crypto'>(
    user.role === 'patient' ? 'records' : user.role === 'doctor' ? 'patients' : 'records'
  );
  const [message, setMessage] = useState('');
  const [selectedPatientForRecord, setSelectedPatientForRecord] = useState<Patient | null>(null);

  async function loadData() {
    try {
      setMessage('');
      const recs = await getRecords();
      setRecords(recs);

      if (user.role !== 'patient') {
        const pts = await getPatients();
        setPatients(pts);
      }
      if (user.role === 'admin' || user.role === 'doctor') {
        const docs = await getDoctors().catch(() => []);
        setDoctors(docs);
      }
      if (user.role === 'admin') {
        const logs = await getAudit();
        setAudit(logs);
      }
    } catch (e: any) {
      setMessage(e.message || 'Error loading dashboard data');
    }
  }

  useEffect(() => {
    loadData();
  }, [user]);

  return (
    <div className="app">
      <aside>
        <div className="side-brand">
          <ShieldCheck /> <span>Secure Medical</span>
        </div>
        <nav>
          {user.role === 'patient' && (
            <button className={tab === 'records' ? 'active' : ''} onClick={() => setTab('records')}>
              <FileText /> My Records
            </button>
          )}

          {user.role === 'doctor' && (
            <>
              <button className={tab === 'patients' ? 'active' : ''} onClick={() => setTab('patients')}>
                <Users /> My Patients
              </button>
              <button className={tab === 'records' ? 'active' : ''} onClick={() => setTab('records')}>
                <FileText /> Medical Records
              </button>
            </>
          )}

          {user.role === 'admin' && (
            <>
              <button className={tab === 'records' ? 'active' : ''} onClick={() => setTab('records')}>
                <FileText /> All Records
              </button>
              <button className={tab === 'patients' ? 'active' : ''} onClick={() => setTab('patients')}>
                <Users /> Patients & Assignments
              </button>
              <button className={tab === 'doctors' ? 'active' : ''} onClick={() => setTab('doctors')}>
                <Stethoscope /> Doctors
              </button>
              <button className={tab === 'audit' ? 'active' : ''} onClick={() => setTab('audit')}>
                <ClipboardList /> Audit Log
              </button>
              <button className={tab === 'crypto' ? 'active' : ''} onClick={() => setTab('crypto')}>
                <KeyRound /> Cryptography Test
              </button>
            </>
          )}
        </nav>

        <div className="side-bottom">
          <div className="user-mini">
            <strong>{user.name}</strong>
            <span>{user.role} (ID #{user.id})</span>
          </div>
          <button onClick={onLogout}><LogOut /> Sign out</button>
        </div>
      </aside>

      <main className="content">
        <header>
          <div>
            <div className="eyebrow">SECURITY CONSOLE</div>
            <h1>
              {tab === 'records'
                ? user.role === 'patient' ? 'My Medical Records' : 'Medical Records'
                : tab === 'patients'
                ? user.role === 'doctor' ? 'My Assigned Patients' : 'Patient Management & Assignment'
                : tab === 'doctors'
                ? 'Doctor Management'
                : tab === 'crypto'
                ? 'Cryptographic Engine Verification'
                : 'Security Audit Log'}
            </h1>
          </div>
          <div className="status">
            <span></span>
            Protected session ({user.role})
          </div>
        </header>

        {message && <div className="notice">{message}</div>}

        {tab === 'records' && (
          <RecordsSection
            user={user}
            records={records}
            onRecordUpdated={loadData}
          />
        )}

        {tab === 'patients' && (
          <PatientsSection
            user={user}
            patients={patients}
            doctors={doctors}
            onChanged={loadData}
            onAddRecordForPatient={(patient) => setSelectedPatientForRecord(patient)}
            onViewPatientRecords={() => setTab('records')}
          />
        )}

        {tab === 'doctors' && user.role === 'admin' && (
          <DoctorsSection
            doctors={doctors}
            onDoctorCreated={loadData}
          />
        )}

        {tab === 'audit' && user.role === 'admin' && (
          <AuditSection rows={audit} />
        )}

        {tab === 'crypto' && user.role === 'admin' && (
          <CryptoTestSection />
        )}

        {/* Global modal for doctor adding a medical record from patients list */}
        {selectedPatientForRecord && (
          <AddRecordModal
            patient={selectedPatientForRecord}
            onClose={() => setSelectedPatientForRecord(null)}
            onSaved={() => {
              setSelectedPatientForRecord(null);
              loadData();
              setTab('records');
            }}
          />
        )}
      </main>
    </div>
  );
}

// ----------------- RECORDS SECTION -----------------

function RecordsSection({
  user,
  records,
  onRecordUpdated
}: {
  user: User;
  records: MedicalRecord[];
  onRecordUpdated: () => void;
}) {
  const [editingRecord, setEditingRecord] = useState<MedicalRecord | null>(null);

  return (
    <section>
      <div className="security-strip">
        <ShieldCheck />
        <div>
          <strong>Integrity verification enabled</strong>
          <span>
            Records are decrypted with AES-256-GCM only after server-side authentication and verified against their stored SHA-256 digest.
          </span>
        </div>
      </div>

      <div className="table-card">
        <div className="table-head">
          <div>
            <h2>{user.role === 'patient' ? 'My Verified Records' : 'Accessible Clinical Records'}</h2>
            <p>
              {user.role === 'doctor'
                ? 'Only records of patients assigned to you are accessible.'
                : user.role === 'patient'
                ? 'Only your confidential medical records are returned.'
                : 'All medical records across the healthcare facility with cryptographic verification status.'}
            </p>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Patient</th>
              <th>Diagnosis</th>
              <th>Prescription</th>
              <th>Notes</th>
              <th>Attending Doctor</th>
              <th>Visit Date</th>
              <th>Integrity</th>
              {user.role === 'doctor' && <th>Action</th>}
            </tr>
          </thead>
          <tbody>
            {records.map(r => (
              <tr key={r.id}>
                <td>
                  <strong>{r.patient_name}</strong>
                  <small>{r.patient_code} • Record #{r.id}</small>
                </td>
                <td>
                  <strong>{r.diagnosis || '—'}</strong>
                </td>
                <td>{r.prescription || '—'}</td>
                <td style={{ maxWidth: 220 }}>{r.notes || '—'}</td>
                <td>
                  <div>{r.doctor_name}</div>
                  {r.last_updated_by && r.last_updated_by !== r.doctor_name && (
                    <small>Updated by: {r.last_updated_by}</small>
                  )}
                </td>
                <td>{r.visit_date || '—'}</td>
                <td>
                  {r.integrity_status === 'VALID' ? (
                    <span className="badge valid"><CheckCircle2 /> Verified</span>
                  ) : (
                    <span className="badge bad"><AlertTriangle /> Tampered</span>
                  )}
                </td>
                {user.role === 'doctor' && (
                  <td>
                    <button
                      className="action-btn secondary"
                      onClick={() => setEditingRecord(r)}
                      title="Edit diagnosis & prescription"
                    >
                      <Edit3 size={13} /> Edit
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>

        {records.length === 0 && (
          <div className="empty">No medical records available for this account.</div>
        )}
      </div>

      {editingRecord && (
        <EditRecordModal
          record={editingRecord}
          onClose={() => setEditingRecord(null)}
          onSaved={() => {
            setEditingRecord(null);
            onRecordUpdated();
          }}
        />
      )}
    </section>
  );
}

// ----------------- PATIENTS SECTION -----------------

function PatientsSection({
  user,
  patients,
  doctors,
  onChanged,
  onAddRecordForPatient,
  onViewPatientRecords
}: {
  user: User;
  patients: Patient[];
  doctors: Doctor[];
  onChanged: () => void;
  onAddRecordForPatient: (p: Patient) => void;
  onViewPatientRecords: () => void;
}) {
  const [openRegister, setOpenRegister] = useState(false);
  const [assigningPatient, setAssigningPatient] = useState<Patient | null>(null);
  const [form, setForm] = useState({ full_name: '', date_of_birth: '', contact: '' });
  const [error, setError] = useState('');

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await createPatient(form);
      setForm({ full_name: '', date_of_birth: '', contact: '' });
      setOpenRegister(false);
      onChanged();
    } catch (err: any) {
      setError(err.message || 'Failed to register patient');
    }
  }

  return (
    <section>
      <div className="table-card">
        <div className="table-head">
          <div>
            <h2>
              {user.role === 'doctor' ? 'Assigned Patients' : 'Registered Patients Directory'}
            </h2>
            <p>
              {user.role === 'doctor'
                ? 'You are authorized to create and edit clinical records for these patients.'
                : 'Manage patient identities and assign authorized attending doctors.'}
            </p>
          </div>
          {user.role !== 'patient' && (
            <button className="small-btn" onClick={() => setOpenRegister(true)}>
              <Plus size={14} /> New patient
            </button>
          )}
        </div>

        <table>
          <thead>
            <tr>
              <th>Patient ID</th>
              <th>Name</th>
              <th>Date of Birth</th>
              <th>Contact</th>
              {user.role === 'admin' && <th>Assigned Doctor(s)</th>}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {patients.map(p => (
              <tr key={p.id}>
                <td><strong>{p.patient_code}</strong></td>
                <td>{p.full_name}</td>
                <td>{p.date_of_birth}</td>
                <td>{p.contact}</td>
                {user.role === 'admin' && (
                  <td>
                    {p.assigned_doctors && p.assigned_doctors.length > 0 ? (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {p.assigned_doctors.map(d => (
                          <span key={d.id} className="badge info">
                            {d.full_name} ({d.username})
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="badge bad" style={{ background: '#fff4e5', color: '#9c5400' }}>
                        Unassigned
                      </span>
                    )}
                  </td>
                )}
                <td>
                  <div className="action-group">
                    {user.role === 'doctor' && (
                      <button
                        className="action-btn"
                        onClick={() => onAddRecordForPatient(p)}
                        title="Add diagnosis, prescription and notes"
                      >
                        <Plus size={13} /> Add Record
                      </button>
                    )}
                    {user.role === 'doctor' && (
                      <button
                        className="action-btn secondary"
                        onClick={onViewPatientRecords}
                      >
                        View Records
                      </button>
                    )}
                    {user.role === 'admin' && (
                      <button
                        className="action-btn secondary"
                        onClick={() => setAssigningPatient(p)}
                      >
                        <UserCheck size={13} /> Assign Doctor
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {patients.length === 0 && (
          <div className="empty">
            {user.role === 'doctor'
              ? 'No patients are currently assigned to you. An administrator can assign patients.'
              : 'No patients found in directory.'}
          </div>
        )}
      </div>

      {/* Modal to Register Patient */}
      {openRegister && (
        <div className="modal">
          <div className="modal-card">
            <h2>Register New Patient</h2>
            <p className="muted" style={{ margin: '0 0 16px' }}>
              Basic demographic data is kept separate from encrypted medical records.
            </p>
            <form onSubmit={handleRegister}>
              <label>
                Full Name
                <input
                  required
                  placeholder="e.g. Rahul Sharma"
                  value={form.full_name}
                  onChange={e => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label>
                Date of Birth
                <input
                  type="date"
                  required
                  value={form.date_of_birth}
                  onChange={e => setForm({ ...form, date_of_birth: e.target.value })}
                />
              </label>
              <label>
                Contact Number
                <input
                  required
                  placeholder="e.g. 9876543210"
                  value={form.contact}
                  onChange={e => setForm({ ...form, contact: e.target.value })}
                />
              </label>
              {error && <div className="error">{error}</div>}
              <div className="modal-actions">
                <button type="button" className="secondary" onClick={() => setOpenRegister(false)}>
                  Cancel
                </button>
                <button type="submit">Save Patient</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal to Assign Patient to Doctor (Admin only) */}
      {assigningPatient && (
        <AssignDoctorModal
          patient={assigningPatient}
          doctors={doctors}
          onClose={() => setAssigningPatient(null)}
          onAssigned={() => {
            setAssigningPatient(null);
            onChanged();
          }}
        />
      )}
    </section>
  );
}

// ----------------- DOCTORS SECTION (ADMIN ONLY) -----------------

function DoctorsSection({
  doctors,
  onDoctorCreated
}: {
  doctors: Doctor[];
  onDoctorCreated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ username: '', full_name: '', password: '' });
  const [error, setError] = useState('');

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await createDoctor(form);
      setForm({ username: '', full_name: '', password: '' });
      setOpen(false);
      onDoctorCreated();
    } catch (err: any) {
      setError(err.message || 'Failed to create doctor');
    }
  }

  return (
    <section>
      <div className="table-card">
        <div className="table-head">
          <div>
            <h2>Doctor Management</h2>
            <p>Manage licensed medical practitioners authorized to access and create records.</p>
          </div>
          <button className="small-btn" onClick={() => setOpen(true)}>
            <Plus size={14} /> Add Doctor
          </button>
        </div>

        <table>
          <thead>
            <tr>
              <th>Doctor ID</th>
              <th>Username</th>
              <th>Full Name</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody>
            {doctors.map(d => (
              <tr key={d.id}>
                <td><strong>#{d.id}</strong></td>
                <td>{d.username}</td>
                <td><strong>{d.full_name}</strong></td>
                <td><span className="badge info">{d.role}</span></td>
              </tr>
            ))}
          </tbody>
        </table>

        {doctors.length === 0 && <div className="empty">No doctors registered yet.</div>}
      </div>

      {open && (
        <div className="modal">
          <div className="modal-card">
            <h2>Add New Doctor</h2>
            <p className="muted" style={{ margin: '0 0 16px' }}>
              Create credentials for an authorized doctor. Password will be hashed with bcrypt.
            </p>
            <form onSubmit={handleCreate}>
              <label>
                Username
                <input
                  required
                  placeholder="e.g. doctor2"
                  value={form.username}
                  onChange={e => setForm({ ...form, username: e.target.value })}
                />
              </label>
              <label>
                Full Name
                <input
                  required
                  placeholder="e.g. Dr. Rajesh Kumar"
                  value={form.full_name}
                  onChange={e => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  required
                  placeholder="e.g. Doctor2@123"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                />
              </label>
              {error && <div className="error">{error}</div>}
              <div className="modal-actions">
                <button type="button" className="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </button>
                <button type="submit">Create Doctor</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}

// ----------------- AUDIT SECTION -----------------

function AuditSection({ rows }: { rows: AuditRow[] }) {
  return (
    <section>
      <div className="table-card">
        <div className="table-head">
          <div>
            <h2>Security Audit Trail</h2>
            <p>Every security-sensitive event is immutably logged with actor, role, status, and target.</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Action</th>
              <th>Record / Target</th>
              <th>Status</th>
              <th>Details</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td>
                  <strong>{r.user_name}</strong>
                  <small>@{r.username}</small>
                </td>
                <td>
                  <span className="badge info">{r.user_role}</span>
                </td>
                <td><code>{r.action}</code></td>
                <td>{r.record_id ? `Record #${r.record_id}` : '—'}</td>
                <td>
                  {r.status === 'SUCCESS' || r.status === 'VALID' ? (
                    <span className="badge valid"><CheckCircle2 size={12} /> {r.status}</span>
                  ) : (
                    <span className="badge bad"><AlertTriangle size={12} /> {r.status}</span>
                  )}
                </td>
                <td className="details-cell">{r.details}</td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <div className="empty">No audit events recorded yet.</div>}
      </div>
    </section>
  );
}

// ----------------- CRYPTOGRAPHY TEST SECTION (ADMIN ONLY) -----------------

function CryptoTestSection() {
  const [plaintext, setPlaintext] = useState('Patient #1002 - Diagnosis: Acute Bronchitis, Prescription: Amoxicillin 500mg tid');
  const [ciphertext, setCiphertext] = useState('');
  const [decryptedText, setDecryptedText] = useState('');
  const [encryptStatus, setEncryptStatus] = useState<{ success: boolean; message: string; algorithm?: string } | null>(null);
  const [decryptStatus, setDecryptStatus] = useState<{ success: boolean; message: string; matches?: boolean } | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleEncrypt() {
    if (!plaintext.trim()) return;
    setLoading(true);
    setEncryptStatus(null);
    setDecryptStatus(null);
    setDecryptedText('');
    try {
      const res = await encryptText(plaintext);
      setCiphertext(res.ciphertext);
      setEncryptStatus({
        success: true,
        message: 'Encrypted via backend AES-256-GCM',
        algorithm: res.algorithm
      });
    } catch (err: any) {
      setEncryptStatus({
        success: false,
        message: err.message || 'Encryption failed'
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleDecrypt() {
    if (!ciphertext.trim()) return;
    setLoading(true);
    setDecryptStatus(null);
    try {
      const res = await decryptText(ciphertext);
      setDecryptedText(res.plaintext);
      const isMatch = res.plaintext === plaintext;
      setDecryptStatus({
        success: true,
        message: isMatch
          ? 'Decryption succeeded: Plaintext matches original input byte-for-byte!'
          : 'Decryption succeeded, but output differs from current input box',
        matches: isMatch
      });
    } catch (err: any) {
      setDecryptedText('');
      setDecryptStatus({
        success: false,
        message: err.message || 'Decryption failed: Token is invalid or corrupted'
      });
    } finally {
      setLoading(false);
    }
  }

  async function runFullPipeline() {
    if (!plaintext.trim()) return;
    setLoading(true);
    setEncryptStatus(null);
    setDecryptStatus(null);
    setDecryptedText('');
    try {
      const enc = await encryptText(plaintext);
      setCiphertext(enc.ciphertext);
      setEncryptStatus({
        success: true,
        message: 'Encrypted via backend AES-256-GCM',
        algorithm: enc.algorithm
      });

      const dec = await decryptText(enc.ciphertext);
      setDecryptedText(dec.plaintext);
      const isMatch = dec.plaintext === plaintext;
      setDecryptStatus({
        success: true,
        message: isMatch
          ? 'Full Pipeline Verified: Plaintext → AES-256-GCM Encrypt → Ciphertext → AES-256-GCM Decrypt → Original Plaintext (Exact match)'
          : 'Decrypted, but did not match',
        matches: isMatch
      });
    } catch (err: any) {
      setDecryptStatus({
        success: false,
        message: err.message || 'Pipeline test failed'
      });
    } finally {
      setLoading(false);
    }
  }

  function simulateTampering() {
    if (!ciphertext) return;
    const chars = ciphertext.split('');
    const idx = Math.floor(chars.length / 2);
    chars[idx] = chars[idx] === 'A' ? 'B' : 'A';
    setCiphertext(chars.join(''));
    setDecryptStatus({
      success: false,
      message: 'Ciphertext altered! Click "Decrypt (Backend AES-GCM)" to test authentication failure.'
    });
  }

  return (
    <section>
      <div className="security-strip">
        <ShieldCheck />
        <div>
          <strong>Backend Cryptographic Engine Verification</strong>
          <span>
            Directly tests the same AES-256-GCM implementation and key used to secure patient medical records.
          </span>
        </div>
      </div>

      {/* Visual Pipeline Banner */}
      <div className="crypto-flow-card">
        <div className="flow-step">
          <div className="step-num">1</div>
          <div className="step-label">Plaintext Input</div>
        </div>
        <div className="flow-arrow"><ArrowRight size={18} /></div>
        <div className="flow-step active">
          <div className="step-num">2</div>
          <div className="step-label">AES-256-GCM Encryption</div>
        </div>
        <div className="flow-arrow"><ArrowRight size={18} /></div>
        <div className="flow-step">
          <div className="step-num">3</div>
          <div className="step-label">Ciphertext + Authentication Tag</div>
        </div>
        <div className="flow-arrow"><ArrowRight size={18} /></div>
        <div className="flow-step active">
          <div className="step-num">4</div>
          <div className="step-label">AES-256-GCM Decryption</div>
        </div>
        <div className="flow-arrow"><ArrowRight size={18} /></div>
        <div className="flow-step">
          <div className="step-num">5</div>
          <div className="step-label">Original Plaintext</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px', marginTop: '20px' }}>
        {/* Box 1: Plaintext */}
        <div className="table-card" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '15px' }}>1. Plaintext Input</h3>
            <span className="badge info">Input String</span>
          </div>
          <p className="muted" style={{ margin: '0 0 12px', fontSize: '12px' }}>
            Enter any sensitive clinical or administrative data to encrypt.
          </p>
          <textarea
            style={{ width: '100%', minHeight: '110px', padding: '10px', borderRadius: '7px', border: '1px solid #d6dce4', fontFamily: 'inherit', resize: 'vertical' }}
            value={plaintext}
            onChange={e => setPlaintext(e.target.value)}
            placeholder="Type plaintext here..."
          />
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="chip"
              onClick={() => setPlaintext('Patient #1001 - Diagnosis: Seasonal allergy, Prescription: Cetirizine 10mg once daily')}
            >
              Sample: Allergy
            </button>
            <button
              type="button"
              className="chip"
              onClick={() => setPlaintext('Patient #1002 - Diagnosis: Acute Bronchitis, Prescription: Azithromycin 500mg daily')}
            >
              Sample: Bronchitis
            </button>
            <button
              type="button"
              className="chip"
              onClick={() => setPlaintext('Lab Report: Fasting Blood Sugar 92 mg/dL, HbA1c 5.4% (Normal)')}
            >
              Sample: Lab Report
            </button>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button onClick={handleEncrypt} disabled={loading} style={{ flex: 1 }}>
              {loading ? 'Encrypting...' : 'Encrypt (Backend AES-256-GCM)'}
            </button>
            <button onClick={runFullPipeline} disabled={loading} className="secondary" style={{ flex: 1 }}>
              Run Full Pipeline
            </button>
          </div>
        </div>

        {/* Box 2: Ciphertext */}
        <div className="table-card" style={{ padding: '22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '15px' }}>2. AES-256-GCM Ciphertext</h3>
            {encryptStatus?.success ? (
              <span className="badge valid"><CheckCircle2 size={12} /> Encrypted</span>
            ) : (
              <span className="badge" style={{ background: '#f0f3f6', color: '#5a6675' }}>Waiting</span>
            )}
          </div>
          <p className="muted" style={{ margin: '0 0 12px', fontSize: '12px' }}>
            Base64-encoded AES-256-GCM ciphertext and authentication tag.
          </p>
          <textarea
            style={{ width: '100%', minHeight: '110px', padding: '10px', borderRadius: '7px', border: '1px solid #d6dce4', fontFamily: 'monospace', fontSize: '12px', background: '#f8fafc', resize: 'vertical' }}
            value={ciphertext}
            onChange={e => setCiphertext(e.target.value)}
            placeholder="Ciphertext token will appear here after encryption..."
          />
          {encryptStatus && (
            <div style={{ marginTop: '10px', fontSize: '12px' }}>
              {encryptStatus.success ? (
                <div style={{ color: '#23764f', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <CheckCircle2 size={14} /> {encryptStatus.message}
                </div>
              ) : (
                <div className="error" style={{ padding: '6px 10px', marginTop: '6px' }}>
                  {encryptStatus.message}
                </div>
              )}
            </div>
          )}

          <div style={{ marginTop: '16px', display: 'flex', gap: '10px' }}>
            <button onClick={handleDecrypt} disabled={loading || !ciphertext} style={{ flex: 1 }}>
              {loading ? 'Decrypting...' : 'Decrypt (Backend AES-GCM)'}
            </button>
            <button
              onClick={simulateTampering}
              disabled={!ciphertext}
              className="action-btn secondary"
              title="Flip a character in ciphertext to test tampering detection"
              style={{ padding: '0 12px' }}
            >
              Simulate Tamper
            </button>
          </div>
        </div>
      </div>

      {/* Box 3: Decrypted Plaintext Result Card */}
      <div className="table-card" style={{ padding: '22px', marginTop: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
          <h3 style={{ margin: 0, fontSize: '15px' }}>3. Decrypted Plaintext Output</h3>
          {decryptStatus ? (
            decryptStatus.success ? (
              <span className="badge valid"><CheckCircle2 size={12} /> Decrypted</span>
            ) : (
              <span className="badge bad"><AlertTriangle size={12} /> Decryption Error</span>
            )
          ) : (
            <span className="badge" style={{ background: '#f0f3f6', color: '#5a6675' }}>Not Decrypted Yet</span>
          )}
        </div>
        <p className="muted" style={{ margin: '0 0 12px', fontSize: '12px' }}>
          Resulting plaintext after passing ciphertext back to the backend AES-256-GCM decryption function.
        </p>
        <div
          style={{
            minHeight: '70px',
            padding: '12px 14px',
            borderRadius: '7px',
            border: '1px solid #d6dce4',
            background: decryptedText ? '#f4fbf7' : '#fafbfc',
            fontSize: '13px',
            fontFamily: 'inherit',
            whiteSpace: 'pre-wrap',
            color: decryptedText ? '#1d2734' : '#8894a0'
          }}
        >
          {decryptedText || 'Click "Decrypt (Backend AES-GCM)" or "Run Full Pipeline" to decrypt the ciphertext.'}
        </div>

        {decryptStatus && (
          <div style={{ marginTop: '14px' }}>
            {decryptStatus.success ? (
              <div
                style={{
                  background: '#eaf7f0',
                  border: '1px solid #b7e4ce',
                  color: '#1e6843',
                  padding: '11px 14px',
                  borderRadius: '7px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                <CheckCircle2 size={16} />
                <span>{decryptStatus.message}</span>
              </div>
            ) : (
              <div
                style={{
                  background: '#fff0ed',
                  border: '1px solid #f9cac2',
                  color: '#9e3725',
                  padding: '11px 14px',
                  borderRadius: '7px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13px',
                  fontWeight: 600
                }}
              >
                <AlertTriangle size={16} />
                <span>{decryptStatus.message}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ----------------- MODALS -----------------

function AddRecordModal({
  patient,
  onClose,
  onSaved
}: {
  patient: Patient;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    diagnosis: '',
    prescription: '',
    notes: '',
    visit_date: new Date().toISOString().split('T')[0]
  });
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await createRecord({
        patient_id: patient.id,
        diagnosis: form.diagnosis,
        prescription: form.prescription,
        notes: form.notes,
        visit_date: form.visit_date
      });
      onSaved();
    } catch (err: any) {
      setError(err.message || 'Failed to save medical record');
    }
  }

  return (
    <div className="modal">
      <div className="modal-card wide">
        <h2>Add Medical Record</h2>
        <p className="muted" style={{ margin: '0 0 16px' }}>
          Recording clinical encounter for <strong>{patient.full_name}</strong> ({patient.patient_code}).
          Content will be encrypted with AES and hashed with SHA-256 before storage.
        </p>
        <form onSubmit={submit}>
          <label>
            Visit Date
            <input
              type="date"
              required
              value={form.visit_date}
              onChange={e => setForm({ ...form, visit_date: e.target.value })}
            />
          </label>
          <label>
            Diagnosis
            <input
              required
              placeholder="e.g. Seasonal allergy, Acute bronchitis"
              value={form.diagnosis}
              onChange={e => setForm({ ...form, diagnosis: e.target.value })}
            />
          </label>
          <label>
            Prescription
            <textarea
              required
              placeholder="e.g. Cetirizine 10mg once daily for 7 days"
              value={form.prescription}
              onChange={e => setForm({ ...form, prescription: e.target.value })}
            />
          </label>
          <label>
            Doctor Clinical Notes
            <textarea
              placeholder="e.g. Patient reports mild allergy symptoms. Advised follow-up in one week."
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
            />
          </label>
          {error && <div className="error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit">Save Medical Record</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function EditRecordModal({
  record,
  onClose,
  onSaved
}: {
  record: MedicalRecord;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState({
    diagnosis: record.diagnosis || '',
    prescription: record.prescription || '',
    notes: record.notes || '',
    visit_date: record.visit_date || new Date().toISOString().split('T')[0]
  });
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await updateRecord(record.id, {
        diagnosis: form.diagnosis,
        prescription: form.prescription,
        notes: form.notes,
        visit_date: form.visit_date
      });
      onSaved();
    } catch (err: any) {
      setError(err.message || 'Failed to update record');
    }
  }

  return (
    <div className="modal">
      <div className="modal-card wide">
        <h2>Edit Medical Record #{record.id}</h2>
        <p className="muted" style={{ margin: '0 0 16px' }}>
          Patient: <strong>{record.patient_name}</strong> ({record.patient_code}).
          Updating will re-encrypt data with AES and recalculate the SHA-256 integrity digest.
        </p>
        <form onSubmit={submit}>
          <label>
            Visit Date
            <input
              type="date"
              required
              value={form.visit_date}
              onChange={e => setForm({ ...form, visit_date: e.target.value })}
            />
          </label>
          <label>
            Diagnosis
            <input
              required
              value={form.diagnosis}
              onChange={e => setForm({ ...form, diagnosis: e.target.value })}
            />
          </label>
          <label>
            Prescription
            <textarea
              required
              value={form.prescription}
              onChange={e => setForm({ ...form, prescription: e.target.value })}
            />
          </label>
          <label>
            Doctor Clinical Notes
            <textarea
              value={form.notes}
              onChange={e => setForm({ ...form, notes: e.target.value })}
            />
          </label>
          {error && <div className="error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit">Save Changes</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AssignDoctorModal({
  patient,
  doctors,
  onClose,
  onAssigned
}: {
  patient: Patient;
  doctors: Doctor[];
  onClose: () => void;
  onAssigned: () => void;
}) {
  const [selectedDoctorId, setSelectedDoctorId] = useState<number>(
    doctors.length > 0 ? doctors[0].id : 0
  );
  const [error, setError] = useState('');

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedDoctorId) {
      setError('Please select a doctor');
      return;
    }
    setError('');
    try {
      await assignPatient(patient.id, selectedDoctorId);
      onAssigned();
    } catch (err: any) {
      setError(err.message || 'Failed to assign patient');
    }
  }

  return (
    <div className="modal">
      <div className="modal-card">
        <h2>Assign Patient to Doctor</h2>
        <p className="muted" style={{ margin: '0 0 16px' }}>
          Assign <strong>{patient.full_name}</strong> ({patient.patient_code}) to an attending physician.
          Only assigned physicians will be authorized to access this patient's records.
        </p>
        <form onSubmit={submit}>
          <label>
            Select Doctor
            <select
              value={selectedDoctorId}
              onChange={e => setSelectedDoctorId(Number(e.target.value))}
            >
              {doctors.map(d => (
                <option key={d.id} value={d.id}>
                  {d.full_name} (@{d.username})
                </option>
              ))}
            </select>
          </label>
          {error && <div className="error">{error}</div>}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit">Assign Patient</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default App;
