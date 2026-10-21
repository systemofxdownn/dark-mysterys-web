"""Registros de auditoría (solo Dirección). Append-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_permission
from ..models import AuditLog
from ..permissions import Perm

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(action: str | None = None, entity_type: str | None = None,
               limit: int = 200, offset: int = 0,
               _: object = Depends(require_permission(Perm.AUDIT_VIEW)),
               db: Session = Depends(get_db)):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    rows = db.scalars(stmt.limit(min(limit, 500)).offset(offset)).all()
    return [{
        "id": r.id, "actor_id": r.actor_id, "actor_identifier": r.actor_identifier,
        "action": r.action, "entity_type": r.entity_type, "entity_id": r.entity_id,
        "before": r.before, "after": r.after, "ip": r.ip, "meta": r.meta,
        "created_at": r.created_at.isoformat(),
    } for r in rows]
