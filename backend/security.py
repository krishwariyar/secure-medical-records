import base64
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import jwt
import bcrypt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
ALGORITHM = "HS256"

# AES-256-GCM key persists between restarts. Do not regenerate it while records exist.
AES_KEY_ENV = os.getenv("AES_GCM_KEY")
AES_KEY_FILE = os.path.join(BASE_DIR, "aes_gcm.key")
if AES_KEY_ENV:
    try:
        AES_KEY = base64.b64decode(AES_KEY_ENV, validate=True)
    except Exception as exc:
        raise RuntimeError("AES_GCM_KEY must be valid base64.") from exc
else:
    if os.path.exists(AES_KEY_FILE):
        with open(AES_KEY_FILE, "rb") as f:
            AES_KEY = base64.b64decode(f.read().strip(), validate=True)
    else:
        AES_KEY = secrets.token_bytes(32)
        # Restrict permissions where supported; key file must be backed up securely.
        fd = os.open(AES_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(base64.b64encode(AES_KEY) + b"\n")
if len(AES_KEY) != 32:
    raise RuntimeError("AES-256-GCM requires a 32-byte key.")
aesgcm = AESGCM(AES_KEY)

# Legacy Fernet key is retained only to read/migrate records created by older versions.
FERNET_KEY = os.getenv("FERNET_KEY")
FERNET_KEY_FILE = os.path.join(BASE_DIR, "fernet.key")
if not FERNET_KEY and os.path.exists(FERNET_KEY_FILE):
    with open(FERNET_KEY_FILE, "r", encoding="utf-8") as f:
        FERNET_KEY = f.read().strip()
legacy_cipher = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None

AES_PREFIX = "AES256GCM:"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def encrypt_record(data: str) -> str:
    nonce = os.urandom(12)  # Fresh 96-bit nonce for every encryption under this key.
    encrypted = aesgcm.encrypt(nonce, data.encode("utf-8"), None)
    payload = {
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(encrypted).decode("ascii"),
    }
    return AES_PREFIX + base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decrypt_record(data: str) -> str:
    if data.startswith(AES_PREFIX):
        payload_b64 = data[len(AES_PREFIX):]
        payload = json.loads(base64.b64decode(payload_b64, validate=True).decode("utf-8"))
        nonce = base64.b64decode(payload["nonce"], validate=True)
        ciphertext = base64.b64decode(payload["ciphertext"], validate=True)
        if len(nonce) != 12:
            raise ValueError("Invalid AES-GCM nonce length.")
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")

    # Backward compatibility: allow old Fernet records to be read until migration completes.
    if legacy_cipher is None:
        raise ValueError("Legacy Fernet key is unavailable for this record.")
    return legacy_cipher.decrypt(data.encode()).decode("utf-8")


def migrate_legacy_ciphertext(data: str) -> str:
    """Convert one legacy Fernet value to AES-256-GCM; leave new values unchanged."""
    if data.startswith(AES_PREFIX):
        return data
    if legacy_cipher is None:
        raise ValueError("Cannot migrate legacy record: Fernet key is unavailable.")
    plaintext = legacy_cipher.decrypt(data.encode()).decode("utf-8")
    return encrypt_record(plaintext)


def integrity_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def create_token(user_id: int, role: str, name: str = "") -> str:
    expires = datetime.utcnow() + timedelta(minutes=60)
    return jwt.encode({"sub": str(user_id), "role": role, "name": name, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)
