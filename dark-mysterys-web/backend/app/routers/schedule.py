"""Calendario semanal, días asignados, cambios, cancelaciones y compensaciones."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import Role, ScheduleStatus
from ..models import Schedule, ScheduleChange, User
from ..permissions import HOUSE_LEADER_ROLES, Perm, has_permission
from ..schemas import ScheduleIn, ScheduleUpdateIn, serialize_schedule
from ..services import points_service

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("")
def list_schedule(week_start: str | None = None, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    stmt = select(Schedule).order_by(Schedule.date, Schedule.start_time)
    if week_start:
        stmt = stmt.where(Schedule.week_start == week_start)
    return [serialize_schedule(s) for s in db.scalars(stmt.limit(300)).all()]


@router.post("", status_code=201)
def create_schedule(data: ScheduleIn, request: Request,
                    actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role == Role.ADMINISTRADOR.value:
        pass
    elif actor.role in HOUSE_LEADER_ROLES and has_permission(actor.role, Perm.SCHEDULE_MANAGE_OWN_DAY):
        if data.house_id not in (None, actor.house_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés gestionar el día de tu Casa.")
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")

    s = Schedule(**data.model_dump(), created_by=actor.id, status=ScheduleStatus.PROGRAMADA.value)
    db.add(s)
    audit(db, actor, "HORARIO_CREADO", "schedule", None, after=data.model_dump(), ip=get_client_ip(request))
    db.commit()
    db.refresh(s)
    return serialize_schedule(s)


@router.patch("/{schedule_id}")
def update_schedule(schedule_id: int, data: ScheduleUpdateIn,
                    actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Schedule, schedule_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Horario inexistente.")
    if actor.role != Role.ADMINISTRADOR.value:
        if not (actor.role in HOUSE_LEADER_ROLES and s.house_id == actor.house_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No podés editar este horario.")

    before = serialize_schedule(s)
    changes = []
    if data.activity_name is not None:
        s.activity_name = data.activity_name; changes.append("nombre")
    if data.start_time is not None:
        s.start_time = data.start_time; changes.append("inicio")
    if data.end_time is not None:
        s.end_time = data.end_time; changes.append("fin")
    if data.status is not None:
        s.status = data.status; changes.append("estado")
    if data.notes is not None:
        s.notes = data.notes
    if changes:
        db.add(ScheduleChange(schedule_id=s.id, change_type="HORARIO",
                              detail=f"Cambios: {', '.join(changes)}. {data.change_reason or ''}",
                              author_id=actor.id))
    audit(db, actor, "HORARIO_ACTUALIZADO", "schedule", s.id, before=before,
          after=serialize_schedule(s))
    db.commit()
    db.refresh(s)
    return serialize_schedule(s)


@router.post("/{schedule_id}/cancel")
def cancel_schedule(schedule_id: int, reason: str, compensate: bool = False,
                    admin: User = Depends(require_permission(Perm.SCHEDULE_MANAGE)),
                    db: Session = Depends(get_db)):
    s = db.get(Schedule, schedule_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Horario inexistente.")
    s.status = ScheduleStatus.CANCELADA.value
    db.add(ScheduleChange(schedule_id=s.id, change_type="CANCELACION", detail=reason, author_id=admin.id))
    result = {"schedule_id": s.id, "status": s.status}
    if compensate and s.house_id:
        entry = points_service.apply_compensation(db, admin, s.house_id, None, reason, None)
        result["compensation_points"] = entry.points
        s.status = ScheduleStatus.COMPENSADA.value
    audit(db, admin, "HORARIO_CANCELADO", "schedule", s.id, after={"reason": reason})
    db.commit()
    return result


@router.get("/{schedule_id}/history")
def schedule_history(schedule_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    rows = db.scalars(select(ScheduleChange).where(ScheduleChange.schedule_id == schedule_id)
                      .order_by(ScheduleChange.created_at.desc())).all()
    return [{"id": c.id, "change_type": c.change_type, "detail": c.detail,
             "author_id": c.author_id, "created_at": c.created_at.isoformat()} for c in rows]
