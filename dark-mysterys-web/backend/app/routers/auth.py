"""Autenticación: login, primer acceso, cambio/recuperación de contraseña y verificación de correo."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user
from ..enums import AccountStatus, TokenPurpose
from ..models import User
from ..permissions import permissions_for
from ..schemas import (
    ChangePasswordIn,
    FirstAccessIn,
    ForgotPasswordIn,
    LoginIn,
    ProfileUpdateIn,
    ResetPasswordIn,
    VerifyEmailIn,
    serialize_user,
)
from ..security import (
    create_access_token,
    hash_password,
    password_is_strong,
    verify_password,
)
from ..services import accounts, email as email_service
from ..services.timez import ensure_utc, now_utc

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id, user.token_version),
        "token_type": "bearer",
        "user": serialize_user(user, include_private=True),
        "permissions": permissions_for(user.role),
    }


@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = accounts.find_user_by_login(db, data.identifier)
    ip = get_client_ip(request)

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")

    if user.locked_until and ensure_utc(user.locked_until) > now_utc():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Demasiados intentos fallidos. Intente más tarde.")

    if not verify_password(data.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_login_attempts:
            user.locked_until = now_utc() + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
        audit(db, user, "LOGIN_FALLIDO", "user", user.id, ip=ip)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")

    if user.status == AccountStatus.PENDIENTE_DE_ACTIVACION.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta debe activarse primero (revisá tu invitación).")
    if user.status == AccountStatus.CONGELADA.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta está congelada.")
    if user.status == AccountStatus.DADA_DE_BAJA.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta fue dada de baja.")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now_utc()
    audit(db, user, "LOGIN", "user", user.id, ip=ip)
    db.commit()
    db.refresh(user)
    return _auth_payload(user)


@router.post("/first-access")
def first_access(data: FirstAccessIn, request: Request, db: Session = Depends(get_db)):
    user = accounts.consume_token(db, data.token, TokenPurpose.INVITACION)
    ok, msg = password_is_strong(data.password)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)

    user.password_hash = hash_password(data.password)
    user.email = data.email.lower()
    user.email_verified = False
    if data.display_name:
        user.display_name = data.display_name.strip()
    if data.timezone:
        user.timezone = data.timezone
    user.status = AccountStatus.ACTIVA.value
    user.token_version += 1

    verify_token = accounts.issue_token(db, user, TokenPurpose.VERIFICAR_EMAIL,
                                        timedelta(hours=settings.email_verify_token_expire_hours))
    email_service.verify_email(user.email, verify_token)
    audit(db, user, "PRIMER_ACCESO", "user", user.id, ip=get_client_ip(request))
    db.commit()
    db.refresh(user)
    return {"message": "Cuenta activada. Verificá tu correo electrónico.",
            "user": serialize_user(user, include_private=True)}


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db: Session = Depends(get_db)):
    user = accounts.consume_token(db, data.token, TokenPurpose.VERIFICAR_EMAIL)
    user.email_verified = True
    audit(db, user, "EMAIL_VERIFICADO", "user", user.id)
    db.commit()
    return {"message": "Correo verificado correctamente."}


@router.post("/resend-verification")
def resend_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No hay correo registrado.")
    token = accounts.issue_token(db, user, TokenPurpose.VERIFICAR_EMAIL,
                                 timedelta(hours=settings.email_verify_token_expire_hours))
    email_service.verify_email(user.email, token)
    db.commit()
    return {"message": "Correo de verificación reenviado."}


@router.post("/change-password")
def change_password(data: ChangePasswordIn, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual es incorrecta.")
    ok, msg = password_is_strong(data.new_password)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1  # invalida sesiones previas
    audit(db, user, "CAMBIO_PASSWORD", "user", user.id)
    db.commit()
    return {"message": "Contraseña actualizada. Volvé a iniciar sesión."}


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    # Respuesta uniforme (no revela si el correo existe)
    if user:
        token = accounts.issue_token(db, user, TokenPurpose.RESET_PASSWORD,
                                     timedelta(minutes=settings.reset_token_expire_minutes))
        email_service.reset_email(user.identifier, token)
        db.commit()
    return {"message": "Si el correo está registrado, recibirás un enlace de recuperación."}


@router.post("/reset-password")
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    user = accounts.consume_token(db, data.token, TokenPurpose.RESET_PASSWORD)
    ok, msg = password_is_strong(data.new_password)
    if not ok:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)
    user.password_hash = hash_password(data.new_password)
    user.token_version += 1
    user.failed_login_count = 0
    user.locked_until = None
    audit(db, user, "RESET_PASSWORD", "user", user.id)
    db.commit()
    return {"message": "Contraseña restablecida. Ya podés iniciar sesión."}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"user": serialize_user(user, include_private=True), "permissions": permissions_for(user.role)}


@router.patch("/me")
def update_me(data: ProfileUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    before = {"display_name": user.display_name, "photo_url": user.photo_url, "timezone": user.timezone}
    if data.display_name is not None:
        user.display_name = data.display_name.strip()
    if data.photo_url is not None:
        user.photo_url = data.photo_url
    if data.timezone is not None:
        user.timezone = data.timezone
    if data.locale is not None:
        user.locale = data.locale
    audit(db, user, "PERFIL_ACTUALIZADO", "user", user.id, before=before,
          after={"display_name": user.display_name, "timezone": user.timezone})
    db.commit()
    db.refresh(user)
    return serialize_user(user, include_private=True)
