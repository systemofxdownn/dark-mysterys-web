"""Eventos: dinámicas, retos, carga de participantes, confirmación y rectificación."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import EventStatus, EventType, Role
from ..models import Event, EventParticipant, House, User
from ..permissions import HOUSE_LEADER_ROLES, Perm, has_permission
from ..schemas import (
    EventIn,
    GroupChallengeIn,
    IndividualChallengeIn,
    serialize_event,
    serialize_participant,
)
from ..services import points_service

router = APIRouter(prefix="/api/events", tags=["events"])


def _can_manage_event(user: User, event: Event) -> bool:
    if user.role == Role.ADMINISTRADOR.value:
        return True
    if user.role in HOUSE_LEADER_ROLES:
        return event.house_responsible_id == user.house_id and event.status == EventStatus.BORRADOR.value
    return False


@router.get("")
def list_events(type: str | None = None, status_: str | None = None,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Event).order_by(Event.scheduled_at.desc().nullslast(), Event.id.desc())
    if type:
        stmt = stmt.where(Event.type == type)
    if status_:
        stmt = stmt.where(Event.status == status_)
    # Estudiantes solo ven eventos confirmados/cancelados (información pública de actividades)
    if user.role == Role.ESTUDIANTE.value:
        stmt = stmt.where(Event.status.in_([EventStatus.CONFIRMADA.value, EventStatus.CANCELADA.value]))
    events = db.scalars(stmt.limit(300)).all()
    return [serialize_event(e) for e in events]


@router.get("/{event_id}")
def get_event(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    data = serialize_event(event)
    data["participants"] = [serialize_participant(p) for p in event.participants]
    return data


@router.post("", status_code=201)
def create_event(data: EventIn, request: Request,
                 actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role not in (Role.ADMINISTRADOR.value, *HOUSE_LEADER_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
    if actor.role in HOUSE_LEADER_ROLES:
        if not has_permission(actor.role, Perm.EVENTS_LOAD_OWN_DAY):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
        if data.house_responsible_id not in (None, actor.house_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés cargar eventos de tu Casa/día.")

    event = Event(
        name=data.name, type=data.type, status=EventStatus.BORRADOR.value,
        house_responsible_id=data.house_responsible_id or actor.house_id,
        responsible_user_id=data.responsible_user_id or actor.id,
        scheduled_at=data.scheduled_at, double_points=data.double_points,
        rounds_played=data.rounds_played, created_by=actor.id, meta=data.meta,
    )
    db.add(event)
    db.flush()
    for p in data.participants:
        db.add(EventParticipant(
            event_id=event.id, user_id=p.user_id, display_name=p.display_name or "",
            house_id=p.house_id, arrival_order=p.arrival_order,
            is_collaborator=p.is_collaborator, answer_text=p.answer_text,
        ))
    audit(db, actor, "EVENTO_CREADO", "event", event.id,
          after={"name": event.name, "type": event.type}, ip=get_client_ip(request))
    db.commit()
    db.refresh(event)
    return serialize_event(event)


@router.put("/{event_id}/participants")
def set_participants(event_id: int, participants: list[dict],
                     actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    if not _can_manage_event(actor, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No podés editar este evento.")

    for old in list(event.participants):
        db.delete(old)
    db.flush()
    for p in participants:
        db.add(EventParticipant(
            event_id=event.id, user_id=p.get("user_id"),
            display_name=p.get("display_name") or "",
            house_id=p.get("house_id"), arrival_order=p.get("arrival_order", 0),
            is_collaborator=p.get("is_collaborator", False),
            answer_text=p.get("answer_text"),
        ))
    if event.rounds_played is None:
        pass
    audit(db, actor, "PARTICIPANTES_CARGADOS", "event", event.id, after={"count": len(participants)})
    db.commit()
    db.refresh(event)
    return {"participants": [serialize_participant(p) for p in event.participants]}


@router.patch("/{event_id}")
def update_event(event_id: int, data: EventIn,
                 actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    if not _can_manage_event(actor, event):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No podés editar este evento.")
    event.name = data.name
    event.type = data.type
    event.scheduled_at = data.scheduled_at
    event.double_points = data.double_points
    event.rounds_played = data.rounds_played
    audit(db, actor, "EVENTO_ACTUALIZADO", "event", event.id, after={"name": event.name})
    db.commit()
    db.refresh(event)
    return serialize_event(event)


@router.post("/{event_id}/confirm")
def confirm_event(event_id: int, request: Request,
                  admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                  db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    if event.type != EventType.DINAMICA.value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Usá los endpoints de retos para este tipo.")
    result = points_service.confirm_dinamica(db, admin, event)
    audit(db, admin, "DINAMICA_CONFIRMADA", "event", event.id, after=result, ip=get_client_ip(request))
    db.commit()
    return result


@router.post("/{event_id}/rectify")
def rectify_event(event_id: int, reason: str,
                  admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                  db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    result = points_service.rectify_event(db, admin, event, reason)
    audit(db, admin, "EVENTO_RECTIFICADO", "event", event.id, after={"reason": reason})
    db.commit()
    return result


@router.post("/{event_id}/cancel")
def cancel_event(event_id: int, reason: str, compensate: bool = False,
                 admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                 db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento inexistente.")
    event.status = EventStatus.CANCELADA.value
    result = {"event_id": event.id, "status": event.status}
    if compensate and event.house_responsible_id:
        entry = points_service.apply_compensation(db, admin, event.house_responsible_id, None, reason, event.id)
        result["compensation_points"] = entry.points
    audit(db, admin, "EVENTO_CANCELADO", "event", event.id,
          after={"reason": reason, "compensated": compensate})
    db.commit()
    return result


@router.post("/group-challenge", status_code=201)
def group_challenge(data: GroupChallengeIn, request: Request,
                    admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                    db: Session = Depends(get_db)):
    event = Event(name=data.name, type=EventType.RETO_GRUPAL.value, status=EventStatus.BORRADOR.value,
                  scheduled_at=data.scheduled_at, created_by=admin.id, meta=data.meta)
    db.add(event)
    db.flush()
    result = points_service.confirm_group_challenge(db, admin, event, data.ranking)
    audit(db, admin, "RETO_GRUPAL", "event", event.id, after=result, ip=get_client_ip(request))
    db.commit()
    return result


@router.post("/individual-challenge", status_code=201)
def individual_challenge(data: IndividualChallengeIn, request: Request,
                         admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                         db: Session = Depends(get_db)):
    event = Event(name=data.name, type=EventType.RETO_INDIVIDUAL.value, status=EventStatus.BORRADOR.value,
                  house_responsible_id=data.house_id, scheduled_at=data.scheduled_at,
                  created_by=admin.id, meta=data.meta)
    db.add(event)
    db.flush()
    valid = 0
    for p in data.participants:
        db.add(EventParticipant(event_id=event.id, user_id=p.user_id, display_name=p.display_name or "",
                                house_id=p.house_id or data.house_id, arrival_order=p.arrival_order,
                                answer_text=p.answer_text))
        if p.answer_text:
            valid += 1
    db.flush()
    result = points_service.confirm_individual_challenge(db, admin, event, data.house_id, valid)
    audit(db, admin, "RETO_INDIVIDUAL", "event", event.id, after=result, ip=get_client_ip(request))
    db.commit()
    return result
