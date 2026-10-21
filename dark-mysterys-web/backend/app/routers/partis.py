"""Participaciones (partis). Contabilización manual por Dirección (v1)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_current_user, require_permission
from ..enums import EventType, Role
from ..models import Event, EventParticipant, ParticipationRecord, User
from ..permissions import HOUSE_LEADER_ROLES, Perm
from ..schemas import ParticipationIn

router = APIRouter(prefix="/api/partis", tags=["partis"])


@router.get("")
def list_partis(house_id: int | None = None, user_id: int | None = None,
                actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(ParticipationRecord).order_by(ParticipationRecord.created_at.desc())
    if actor.role == Role.ADMINISTRADOR.value:
        if house_id:
            stmt = stmt.where(ParticipationRecord.house_id == house_id)
        if user_id:
            stmt = stmt.where(ParticipationRecord.user_id == user_id)
    elif actor.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(ParticipationRecord.house_id == actor.house_id)
    else:
        stmt = stmt.where(ParticipationRecord.user_id == actor.id)
    rows = db.scalars(stmt.limit(500)).all()
    return [{"id": r.id, "user_id": r.user_id, "house_id": r.house_id, "event_id": r.event_id,
             "partis": r.partis, "reason": r.reason, "author_id": r.author_id,
             "created_at": r.created_at.isoformat()} for r in rows]


@router.get("/summary")
def summary(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Totales de partis por usuario (y por Casa)."""
    stmt = (
        select(User.id, User.display_name, User.identifier, User.house_id,
               func.coalesce(func.sum(ParticipationRecord.partis), 0))
        .join(ParticipationRecord, ParticipationRecord.user_id == User.id, isouter=True)
        .group_by(User.id)
        .order_by(func.coalesce(func.sum(ParticipationRecord.partis), 0).desc())
    )
    if actor.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(User.house_id == actor.house_id)
    elif actor.role == Role.ESTUDIANTE.value:
        stmt = stmt.where(User.id == actor.id)
    rows = db.execute(stmt).all()
    return [{"user_id": r[0], "display_name": r[1], "identifier": r[2],
             "house_id": r[3], "partis": int(r[4] or 0)} for r in rows]


@router.post("", status_code=201)
def add_partis(data: ParticipationIn,
               admin: User = Depends(require_permission(Perm.PARTICIPATIONS_MANAGE)),
               db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    rec = ParticipationRecord(user_id=target.id, house_id=target.house_id, event_id=data.event_id,
                              partis=data.partis, reason=data.reason, author_id=admin.id)
    db.add(rec)
    audit(db, admin, "PARTIS_AGREGADOS", "user", target.id,
          after={"partis": data.partis, "reason": data.reason})
    db.commit()
    return {"id": rec.id, "user_id": rec.user_id, "partis": rec.partis}


@router.get("/inactivity")
def inactivity(admin: User = Depends(require_permission(Perm.PARTICIPATIONS_MANAGE)),
               db: Session = Depends(get_db)):
    """
    Referencias de inactividad (NO expulsa automáticamente; solo informa):
    - menos de 4 dinámicas jugadas en toda la Copa
    - menos de 20 partis al cierre
    """
    users = db.scalars(select(User).where(User.role == Role.ESTUDIANTE.value)).all()
    out = []
    for u in users:
        din_count = int(db.scalar(
            select(func.count(func.distinct(EventParticipant.event_id)))
            .join(Event, Event.id == EventParticipant.event_id)
            .where(EventParticipant.user_id == u.id, Event.type == EventType.DINAMICA.value)
        ) or 0)
        partis = int(db.scalar(
            select(func.coalesce(func.sum(ParticipationRecord.partis), 0))
            .where(ParticipationRecord.user_id == u.id)
        ) or 0)
        out.append({
            "user_id": u.id, "identifier": u.identifier, "display_name": u.display_name,
            "house_id": u.house_id, "dinamicas": din_count, "partis": partis,
            "flag_low_dinamicas": din_count < 4, "flag_low_partis": partis < 20,
        })
    return out
