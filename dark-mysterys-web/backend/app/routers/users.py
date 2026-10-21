"""Gestión de usuarios (Dirección) y consultas acotadas por Casa."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import AccountStatus, Role
from ..models import House, User
from ..permissions import HOUSE_LEADER_ROLES, Perm
from ..schemas import (
    FreezeIn,
    HouseAssignIn,
    RoleAssignIn,
    StatusIn,
    UserCreateIn,
    UserUpdateIn,
    serialize_user,
)
from ..services import accounts, email as email_service
from ..services.timez import now_utc

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
def list_users(house_id: int | None = None, role: str | None = None, q: str | None = None,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(User)
    if user.role in HOUSE_LEADER_ROLES:
        # Jefes/subjefes: solo su Casa
        stmt = stmt.where(User.house_id == user.house_id)
    elif not (user.role == Role.ADMINISTRADOR.value or user.role == Role.BANQUERO.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
    else:
        if house_id:
            stmt = stmt.where(User.house_id == house_id)

    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.display_name.ilike(like)) | (User.identifier.ilike(like)))
    users = db.scalars(stmt.order_by(User.id)).all()
    return [serialize_user(u, include_private=user.role == Role.ADMINISTRADOR.value) for u in users]


@router.get("/lookup")
def lookup(q: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Búsqueda de destinatarios para transferencias (identidad mínima)."""
    like = f"%{q.strip()}%"
    users = db.scalars(
        select(User).where(
            User.status == AccountStatus.ACTIVA.value,
            (User.display_name.ilike(like)) | (User.identifier.ilike(like)),
        ).limit(10)
    ).all()
    return [{"id": u.id, "identifier": u.identifier, "display_name": u.display_name,
             "house": u.house.name if u.house else None, "photo_url": u.photo_url} for u in users]


@router.post("", status_code=201)
def create_user(data: UserCreateIn, request: Request,
                admin: User = Depends(require_permission(Perm.USERS_CREATE)),
                db: Session = Depends(get_db)):
    u, token = accounts.create_user(
        db, display_name=data.display_name, house_id=data.house_id, role=data.role,
        email=data.email, timezone=data.timezone,
    )
    email_service.invitation_email(u.identifier, token)
    audit(db, admin, "USUARIO_CREADO", "user", u.id, after={"identifier": u.identifier, "role": u.role},
          ip=get_client_ip(request))
    db.commit()
    db.refresh(u)
    return {"user": serialize_user(u, include_private=True), "invitation_token": token,
            "note": "En producción el token se envía por correo; aquí se devuelve para pruebas."}


@router.get("/{user_id}")
def get_user(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    if user.role in HOUSE_LEADER_ROLES and target.house_id != user.house_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés ver integrantes de tu Casa.")
    if user.id != target.id and user.role not in (
        Role.ADMINISTRADOR.value, Role.BANQUERO.value, *HOUSE_LEADER_ROLES
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
    return serialize_user(target, include_private=user.role == Role.ADMINISTRADOR.value or user.id == target.id)


@router.patch("/{user_id}")
def update_user(user_id: int, data: UserUpdateIn,
                admin: User = Depends(require_permission(Perm.USERS_MANAGE)),
                db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    before = {"display_name": target.display_name, "email": target.email, "timezone": target.timezone}
    if data.display_name is not None:
        target.display_name = data.display_name.strip()
    if data.photo_url is not None:
        target.photo_url = data.photo_url
    if data.timezone is not None:
        target.timezone = data.timezone
    if data.email is not None:
        target.email = data.email.lower()
        target.email_verified = False
    audit(db, admin, "USUARIO_ACTUALIZADO", "user", target.id, before=before,
          after={"display_name": target.display_name, "email": target.email})
    db.commit()
    db.refresh(target)
    return serialize_user(target, include_private=True)


@router.post("/{user_id}/role")
def assign_role(user_id: int, data: RoleAssignIn,
                admin: User = Depends(require_permission(Perm.ROLES_ASSIGN)),
                db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    if data.role not in {r.value for r in Role}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Rol inválido.")
    before = target.role
    target.role = data.role
    target.token_version += 1  # fuerza re-login con nuevos permisos
    audit(db, admin, "ROL_ASIGNADO", "user", target.id, before={"role": before}, after={"role": data.role})
    db.commit()
    return {"message": "Rol actualizado.", "user": serialize_user(target, include_private=True)}


@router.post("/{user_id}/house")
def assign_house(user_id: int, data: HouseAssignIn,
                 admin: User = Depends(require_permission(Perm.HOUSES_ASSIGN)),
                 db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    house = db.get(House, data.house_id)
    if house is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Casa inexistente.")
    before = target.house_id
    # Los cambios de Casa solo al cierre de la Copa (regla del proyecto)
    if data.effective == "now":
        target.house_id = house.id
        target.token_version += 1
    else:
        target.meta = {**(target.meta or {}), "pending_house_change": house.id}
    audit(db, admin, "CASA_ASIGNADA", "user", target.id, before={"house_id": before},
          after={"house_id": house.id, "effective": data.effective})
    db.commit()
    return {"message": "Casa actualizada.", "user": serialize_user(target, include_private=True)}


@router.post("/{user_id}/freeze")
def freeze(user_id: int, data: FreezeIn,
           admin: User = Depends(require_permission(Perm.ACCOUNTS_FREEZE)),
           db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    target.status = AccountStatus.CONGELADA.value
    target.token_version += 1  # invalida sesiones previas
    audit(db, admin, "CUENTA_CONGELADA", "user", target.id, after={"reason": data.reason})
    db.commit()
    return {"message": "Cuenta congelada.", "user": serialize_user(target, include_private=True)}


@router.post("/{user_id}/unfreeze")
def unfreeze(user_id: int, admin: User = Depends(require_permission(Perm.ACCOUNTS_FREEZE)),
             db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    target.status = AccountStatus.ACTIVA.value
    audit(db, admin, "CUENTA_DESCONGELADA", "user", target.id)
    db.commit()
    return {"message": "Cuenta reactivada.", "user": serialize_user(target, include_private=True)}


@router.post("/{user_id}/status")
def set_status(user_id: int, data: StatusIn,
               admin: User = Depends(require_permission(Perm.USERS_MANAGE)),
               db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    if data.status not in {s.value for s in AccountStatus}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Estado inválido.")
    before = target.status
    target.status = data.status
    target.token_version += 1
    audit(db, admin, "ESTADO_CAMBIADO", "user", target.id, before={"status": before},
          after={"status": data.status, "reason": data.reason})
    db.commit()
    return {"message": "Estado actualizado.", "user": serialize_user(target, include_private=True)}


@router.post("/{user_id}/resend-invitation")
def resend_invitation(user_id: int, admin: User = Depends(require_permission(Perm.USERS_CREATE)),
                      db: Session = Depends(get_db)):
    from datetime import timedelta
    from ..config import settings
    from ..enums import TokenPurpose
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    token = accounts.issue_token(db, target, TokenPurpose.INVITACION,
                                 timedelta(hours=settings.invitation_token_expire_hours))
    email_service.invitation_email(target.identifier, token)
    audit(db, admin, "INVITACION_REENVIADA", "user", target.id)
    db.commit()
    return {"invitation_token": token, "note": "Token de invitación regenerado."}
