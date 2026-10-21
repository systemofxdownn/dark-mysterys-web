"""Configuración general (Dirección) y utilidades de desarrollo."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import audit, require_permission
from ..models import Setting, User
from ..permissions import Perm
from ..schemas import SettingIn
from ..services import email as email_service

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
def list_settings(_: object = Depends(require_permission(Perm.CONFIG_MANAGE)),
                  db: Session = Depends(get_db)):
    rows = db.scalars(select(Setting).order_by(Setting.key)).all()
    return [{"key": s.key, "value": s.value, "description": s.description} for s in rows]


@router.put("")
def upsert_setting(data: SettingIn, admin: User = Depends(require_permission(Perm.CONFIG_MANAGE)),
                   db: Session = Depends(get_db)):
    s = db.get(Setting, data.key)
    if s is None:
        s = Setting(key=data.key, value=data.value, description=data.description)
        db.add(s)
    else:
        s.value = data.value
        if data.description:
            s.description = data.description
    audit(db, admin, "CONFIG_ACTUALIZADA", "setting", data.key, after=data.value)
    db.commit()
    return {"key": s.key, "value": s.value}


@router.get("/public")
def public_config():
    """Configuración no sensible para el frontend."""
    return {
        "app_name": settings.app_name,
        "default_timezone": settings.default_timezone,
        "environment": settings.environment,
    }


@router.get("/email-outbox")
def email_outbox(_: object = Depends(require_permission(Perm.CONFIG_MANAGE))):
    """Solo desarrollo: permite ver los correos generados (invitaciones, recuperación)."""
    if settings.is_production:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No disponible.")
    return email_service.OUTBOX[-50:]
