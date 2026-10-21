"""Dependencias de FastAPI: autenticación, autorización y utilidades."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .enums import AccountStatus, Role
from .models import AuditLog, User
from .permissions import has_permission
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No autenticado.")

    payload = decode_access_token(creds.credentials)
    if not payload or payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.")

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario inexistente.")

    # Invalida sesiones previas si el token_version cambió (freeze, cambio de clave, etc.)
    if int(payload.get("tv", -1)) != user.token_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión invalidada. Vuelva a iniciar sesión.")

    # Cuenta congelada / dada de baja: no puede operar (bloquea sesiones anteriores)
    if user.status in (AccountStatus.CONGELADA.value, AccountStatus.DADA_DE_BAJA.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta no está habilitada para operar.")

    if user.status == AccountStatus.PENDIENTE_DE_ACTIVACION.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta debe activarse primero.")

    return user


def require_permission(permission: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Permiso denegado: {permission}")
        return user
    return _dep


def require_roles(*roles: str):
    allowed = set(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol no autorizado para esta operación.")
        return user
    return _dep


require_admin = require_roles(Role.ADMINISTRADOR.value)


def audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip: str | None = None,
    meta: dict | None = None,
) -> AuditLog:
    """Registra una acción sensible. Append-only."""
    log = AuditLog(
        actor_id=actor.id if actor else None,
        actor_identifier=actor.identifier if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=before,
        after=after,
        ip=ip,
        meta=meta or {},
    )
    db.add(log)
    return log
