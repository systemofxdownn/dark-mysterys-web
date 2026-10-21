"""
Servicio de cuentas: creación de usuarios, identificadores únicos por Casa y
tokens de un solo uso (invitación / recuperación / verificación de correo).

Decisión confirmada: el número de cuenta es INDEPENDIENTE POR CASA.
Cada Casa tiene su propia cuenta nº 1, nº 2, etc. Los números no se reutilizan
(aunque la cuenta se dé de baja) y se admiten más de dos dígitos.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import AccountStatus, Role, TokenPurpose
from ..models import AuthToken, House, User
from ..security import build_identifier, generate_opaque_token, hash_token
from .timez import now_utc


def _next_seq(db: Session, house: House) -> int:
    """Reserva el siguiente número de cuenta de la Casa (bloqueo de fila)."""
    locked = db.scalar(select(House).where(House.id == house.id).with_for_update())
    locked.counter = (locked.counter or 0) + 1
    db.flush()
    return locked.counter


def create_user(db: Session, *, display_name: str, house_id: int, role: str,
                email: str | None = None, timezone: str | None = None,
                is_director: bool = False) -> tuple[User, str]:
    if role not in {r.value for r in Role}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol inválido.")
    house = db.get(House, house_id)
    if house is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Casa inexistente.")

    seq = _next_seq(db, house)
    identifier = build_identifier(display_name, house.code, seq)

    # Garantiza unicidad (colisiones por nombres distintos con misma inicial)
    while db.scalar(select(User).where(User.identifier == identifier)):
        seq = _next_seq(db, house)
        identifier = build_identifier(display_name, house.code, seq)

    user = User(
        identifier=identifier,
        seq_number=seq,
        display_name=display_name.strip(),
        email=email.lower() if email else None,
        role=role,
        status=AccountStatus.PENDIENTE_DE_ACTIVACION.value,
        house_id=house.id,
        timezone=timezone or settings.default_timezone,
        is_director=is_director,
    )
    db.add(user)
    db.flush()

    token = issue_token(db, user, TokenPurpose.INVITACION,
                        timedelta(hours=settings.invitation_token_expire_hours))
    return user, token


def issue_token(db: Session, user: User, purpose: TokenPurpose, ttl: timedelta) -> str:
    raw = generate_opaque_token()
    db.add(AuthToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        purpose=purpose.value,
        expires_at=now_utc() + ttl,
    ))
    db.flush()
    return raw


def consume_token(db: Session, raw_token: str, purpose: TokenPurpose) -> User:
    th = hash_token(raw_token)
    token = db.scalar(select(AuthToken).where(
        AuthToken.token_hash == th, AuthToken.purpose == purpose.value
    ))
    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token inválido.")
    if token.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El token ya fue utilizado.")
    if token.expires_at.replace(tzinfo=token.expires_at.tzinfo or now_utc().tzinfo) < now_utc():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El token expiró.")
    user = db.get(User, token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Usuario inexistente.")
    token.used_at = now_utc()
    return user


def find_user_by_login(db: Session, identifier: str) -> User | None:
    ident = identifier.strip().upper()
    user = db.scalar(select(User).where(User.identifier == ident))
    if user:
        return user
    # permite ingresar por email
    if "@" in identifier:
        return db.scalar(select(User).where(User.email == identifier.lower()))
    return None
