"""Reclamaciones y su resolución por Dirección."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_current_user, require_permission
from ..enums import ComplaintStatus, Role
from ..models import Complaint, User
from ..permissions import Perm
from ..schemas import ComplaintIn, ComplaintResolveIn, serialize_complaint
from ..services.notifications import notify
from ..services.timez import now_utc

router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.get("")
def list_complaints(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role == Role.ADMINISTRADOR.value:
        rows = db.scalars(select(Complaint).order_by(Complaint.created_at.desc()).limit(300)).all()
    else:
        rows = db.scalars(select(Complaint).where(Complaint.requester_id == actor.id)
                          .order_by(Complaint.created_at.desc())).all()
    return [serialize_complaint(c) for c in rows]


@router.post("", status_code=201)
def create_complaint(data: ComplaintIn, actor: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    c = Complaint(requester_id=actor.id, event_id=data.event_id, subject=data.subject,
                  reason=data.reason, status=ComplaintStatus.ABIERTA.value)
    db.add(c)
    audit(db, actor, "RECLAMACION_CREADA", "complaint", None, after={"subject": data.subject})
    db.commit()
    db.refresh(c)
    return serialize_complaint(c)


@router.post("/{complaint_id}/resolve")
def resolve_complaint(complaint_id: int, data: ComplaintResolveIn,
                      admin: User = Depends(require_permission(Perm.COMPLAINTS_RESOLVE)),
                      db: Session = Depends(get_db)):
    c = db.get(Complaint, complaint_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reclamación inexistente.")
    if data.status not in {s.value for s in ComplaintStatus}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Estado inválido.")
    c.status = data.status
    c.resolution = data.resolution
    c.resolved_by = admin.id
    c.resolved_at = now_utc()
    notify(db, c.requester_id, "RECLAMACION", "Tu reclamación fue resuelta",
           f"Estado: {data.status}. {data.resolution}", link="/complaints")
    audit(db, admin, "RECLAMACION_RESUELTA", "complaint", c.id,
          after={"status": data.status, "resolution": data.resolution})
    db.commit()
    db.refresh(c)
    return serialize_complaint(c)
