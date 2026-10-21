"""
Seguridad: hash de contraseñas (bcrypt + pre-hash SHA-256), JWT y tokens opacos.

Notas:
- Se aplica un pre-hash SHA-256 (base64) antes de bcrypt para admitir
  contraseñas de longitud arbitraria sin truncarlas silenciosamente.
- Los tokens de invitación/recuperación se guardan hasheados (SHA-256),
  nunca en claro.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


# ---------------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------------
def _prehash(password: str) -> bytes:
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def password_is_strong(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "La contraseña debe tener al menos 8 caracteres."
    if not any(c.isalpha() for c in password):
        return False, "La contraseña debe incluir al menos una letra."
    if not any(c.isdigit() for c in password):
        return False, "La contraseña debe incluir al menos un número."
    return True, ""


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def create_access_token(user_id: int, token_version: int, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# Tokens opacos (un solo uso)
# ---------------------------------------------------------------------------
def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# ---------------------------------------------------------------------------
# Identificadores de cuenta
# ---------------------------------------------------------------------------
def build_identifier(display_name: str, house_code: str, seq_number: int) -> str:
    """Inicial del nombre + inicial de la Casa + número de cuenta (por Casa)."""
    initial = (display_name.strip()[:1] or "X").upper()
    house_initial = (house_code.strip()[:1] or "X").upper()
    return f"{initial}{house_initial}{seq_number:02d}"
