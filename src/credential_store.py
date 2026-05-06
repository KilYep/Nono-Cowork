"""
Encrypted credential store — user-provided API keys for third-party services.

Keys are encrypted with Fernet (AES-128-CBC + HMAC) and stored in .env.credentials.
The encryption secret is auto-generated in .env on first use.
"""

import os
import base64
import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CREDENTIALS_FILE = _PROJECT_ROOT / ".env.credentials"
_ENV_FILE = _PROJECT_ROOT / ".env"
_SECRET_KEY = "CREDENTIAL_SECRET"


def _ensure_secret() -> str:
    """Return the encryption secret, generating one if missing."""
    from dotenv import dotenv_values
    vals = dotenv_values(_ENV_FILE)
    secret = vals.get(_SECRET_KEY, "").strip()
    if secret:
        return secret

    secret = Fernet.generate_key().decode()
    with open(_ENV_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n# Auto-generated encryption key for credential store\n")
        f.write(f"{_SECRET_KEY}={secret}\n")
    return secret


def _get_fernet() -> Fernet:
    secret = _ensure_secret()
    # Fernet requires a url-safe base64 key; if the stored secret is already
    # a valid Fernet key, use it directly. Otherwise derive one via SHA-256.
    try:
        return Fernet(secret.encode())
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(derived)


def _load_store() -> dict[str, str]:
    """Load the encrypted credential file. Returns {name: encrypted_value}."""
    if not _CREDENTIALS_FILE.exists():
        return {}
    data = {}
    for line in _CREDENTIALS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        name, value = line.split("=", 1)
        data[name.strip()] = value.strip()
    return data


def _save_store(data: dict[str, str]):
    """Write the credential store back to disk."""
    lines = ["# Encrypted credential store — do not edit manually"]
    for name, enc_value in sorted(data.items()):
        lines.append(f"{name}={enc_value}")
    _CREDENTIALS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_credential(name: str, plaintext: str):
    """Encrypt and store a credential."""
    f = _get_fernet()
    encrypted = f.encrypt(plaintext.encode()).decode()
    store = _load_store()
    store[name] = encrypted
    _save_store(store)


def get_credential(name: str) -> str | None:
    """Retrieve and decrypt a credential. Returns None if not found."""
    store = _load_store()
    encrypted = store.get(name)
    if not encrypted:
        return None
    f = _get_fernet()
    return f.decrypt(encrypted.encode()).decode()


def has_credential(name: str) -> bool:
    """Check if a credential exists (without decrypting)."""
    return name in _load_store()


def list_credentials() -> list[dict]:
    """List stored credential names with masked previews."""
    store = _load_store()
    result = []
    f = _get_fernet()
    for name in sorted(store):
        try:
            plain = f.decrypt(store[name].encode()).decode()
            masked = plain[:2] + "***" + plain[-4:] if len(plain) > 6 else "***"
        except Exception:
            masked = "(decrypt error)"
        result.append({"name": name, "preview": masked})
    return result


def delete_credential(name: str) -> bool:
    """Delete a credential. Returns True if it existed."""
    store = _load_store()
    if name not in store:
        return False
    del store[name]
    _save_store(store)
    return True
