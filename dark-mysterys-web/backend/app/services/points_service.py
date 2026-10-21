"""
Servicio de Puntos (Copa).

- El marcador oficial es DERIVADO del `point_ledger` (append-only) y se cachea
  en `house_scores` de forma reconciliable.
- Confirmar una dinámica calcula y aplica los puntos; una dinámica no puede
  contabilizarse dos veces (estado + control de ledger).
- Las correcciones se hacen por RECTIFICACIÓN (asiento inverso + nuevo asiento),
  nunca borrando.
- Los puntos de un reto grupal pertenecen a la CASA.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..enums import EventStatus, EventType, PointLedgerType
from ..models import (
    Event,
    EventParticipant,
    House,
    HouseScore,
    ParticipationRecord,
    PointLedger,
    User,
)
from . import scoring
from .notifications import notify


def get_house_score(db: Session, house_id: int) -> int:
    hs = db.scalar(select(HouseScore).where(HouseScore.house_id == house_id))
    if hs is None:
        hs = HouseScore(house_id=house_id, points=0)
        db.add(hs)
        db.flush()
    return hs.points


def get_all_scores(db: Session) -> list[dict]:
    rows = db.execute(
        select(House, HouseScore.points)
        .outerjoin(HouseScore, HouseScore.house_id == House.id)
        .where(House.is_competing.is_(True))
        .order_by(House.id)
    ).all()
    return [{"house_id": h.id, "code": h.code, "name": h.name,
             "heart_color": h.heart_color, "heart_hex": h.heart_hex,
             "points": int(p or 0)} for h, p in rows]


def _apply_ledger(db: Session, *, house_id: int, points: int, type_: str,
                  user_id: int | None = None, event_id: int | None = None,
                  reason: str | None = None, author_id: int | None = None,
                  reverses_id: int | None = None, meta: dict | None = None) -> PointLedger:
    """Crea un asiento en el libro de puntos y actualiza el acumulado de la Casa."""
    entry = PointLedger(
        house_id=house_id, user_id=user_id, event_id=event_id, type=type_,
        points=points, reason=reason, author_id=author_id,
        reverses_id=reverses_id, meta=meta or {},
    )
    db.add(entry)
    db.flush()

    hs = db.scalar(select(HouseScore).where(HouseScore.house_id == house_id).with_for_update())
    if hs is None:
        hs = HouseScore(house_id=house_id, points=0)
        db.add(hs)
        db.flush()
    hs.points = hs.points + points
    return entry


def _award_partis(db: Session, user_id: int, house_id: int | None, partis: int,
                  event_id: int | None, reason: str, author_id: int | None) -> None:
    if partis <= 0 or user_id is None:
        return
    db.add(ParticipationRecord(
        user_id=user_id, house_id=house_id, event_id=event_id,
        partis=partis, reason=reason, author_id=author_id,
    ))


# ---------------------------------------------------------------------------
# Confirmación de dinámica
# ---------------------------------------------------------------------------
def confirm_dinamica(db: Session, actor: User, event: Event) -> dict:
    if event.status == EventStatus.CONFIRMADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La dinámica ya fue confirmada.")
    if event.status == EventStatus.CANCELADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La dinámica está cancelada.")

    participants = event.participants
    if not participants:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No hay participantes cargados.")

    # Evita doble contabilización
    already = db.scalar(select(func.count(PointLedger.id)).where(
        PointLedger.event_id == event.id, PointLedger.type.in_(
            [PointLedgerType.DINAMICA_PODIO.value, PointLedgerType.PARTICIPACION.value])
    ))
    if already:
        raise HTTPException(status.HTTP_409_CONFLICT, "Los puntos de esta dinámica ya fueron contabilizados.")

    data = [{"house_id": p.house_id, "arrival_order": p.arrival_order} for p in participants]
    result = scoring.compute_dinamica(data, double_points=event.double_points)

    # Aplica por participante
    for p, sc in zip(participants, result.participants):
        p.effective_podium = sc.effective_podium
        p.points_awarded = sc.points
        if p.house_id is not None:
            _apply_ledger(
                db, house_id=p.house_id, points=sc.points,
                type_=PointLedgerType.DINAMICA_PODIO.value if sc.effective_podium
                else PointLedgerType.PARTICIPACION.value,
                user_id=p.user_id, event_id=event.id,
                reason=f"Dinámica «{event.name}» — llegada #{p.arrival_order}",
                author_id=actor.id,
                meta={"podium": sc.effective_podium, "arrival_order": p.arrival_order,
                      "two_house_exception": result.used_two_house_exception},
            )

    # Partis
    parti_rule = scoring.compute_partis("DINAMICA", event.rounds_played)
    per = parti_rule.get("per_participant", 0)
    for p in participants:
        if p.user_id and per:
            _award_partis(db, p.user_id, p.house_id, per, event.id,
                          f"Dinámica «{event.name}» ({event.rounds_played} rondas)", actor.id)
            p.partis_awarded = per

    event.status = EventStatus.CONFIRMADA.value
    event.confirmed_at = func.now()
    event.confirmed_by = actor.id
    db.commit()
    return {
        "event_id": event.id,
        "house_totals": result.house_totals,
        "used_two_house_exception": result.used_two_house_exception,
        "participants": [{"user_id": p.user_id, "display_name": p.display_name,
                          "podium": p.effective_podium, "points": p.points_awarded} for p in participants],
    }


# ---------------------------------------------------------------------------
# Retos
# ---------------------------------------------------------------------------
def confirm_group_challenge(db: Session, actor: User, event: Event, ranking: list[int]) -> dict:
    if event.status == EventStatus.CONFIRMADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "El reto ya fue confirmado.")
    totals = scoring.compute_group_challenge(ranking, double_points=event.double_points)
    for house_id, pts in totals.items():
        _apply_ledger(db, house_id=house_id, points=pts, type_=PointLedgerType.RETO_GRUPAL.value,
                      event_id=event.id, reason=f"Reto grupal «{event.name}»", author_id=actor.id,
                      meta={"ranking": ranking})
    # Partis solo para colaboradores
    for p in event.participants:
        if p.is_collaborator and p.user_id:
            _award_partis(db, p.user_id, p.house_id, 1, event.id,
                          f"Colaboración en reto grupal «{event.name}»", actor.id)
            p.partis_awarded = 1
    event.status = EventStatus.CONFIRMADA.value
    event.confirmed_at = func.now()
    event.confirmed_by = actor.id
    event.meta = {**(event.meta or {}), "ranking": ranking}
    db.commit()
    return {"event_id": event.id, "house_totals": totals}


def confirm_individual_challenge(db: Session, actor: User, event: Event, house_id: int,
                                 valid_deliveries: int) -> dict:
    if event.status == EventStatus.CONFIRMADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "El reto ya fue confirmado.")
    totals = scoring.compute_individual_challenge(valid_deliveries, house_id, double_points=event.double_points)
    for hid, pts in totals.items():
        _apply_ledger(db, house_id=hid, points=pts, type_=PointLedgerType.RETO_INDIVIDUAL.value,
                      event_id=event.id, reason=f"Reto individual «{event.name}» ({valid_deliveries} entregas)",
                      author_id=actor.id, meta={"valid_deliveries": valid_deliveries})
    for p in event.participants:
        if p.user_id and p.answer_text:
            _award_partis(db, p.user_id, p.house_id, 1, event.id,
                          f"Reto individual «{event.name}»", actor.id)
            p.partis_awarded = 1
    event.status = EventStatus.CONFIRMADA.value
    event.confirmed_at = func.now()
    event.confirmed_by = actor.id
    db.commit()
    return {"event_id": event.id, "house_totals": totals}


# ---------------------------------------------------------------------------
# Rectificación
# ---------------------------------------------------------------------------
def rectify_event(db: Session, actor: User, event: Event, reason: str) -> dict:
    """Revierte los asientos de un evento confirmado y lo deja en BORRADOR para recargar."""
    if event.status not in (EventStatus.CONFIRMADA.value, EventStatus.RECTIFICADA.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo pueden rectificarse eventos confirmados.")

    entries = db.scalars(select(PointLedger).where(
        PointLedger.event_id == event.id, PointLedger.reverses_id.is_(None)
    )).all()
    reversed_total = 0
    for e in entries:
        _apply_ledger(db, house_id=e.house_id, points=-e.points, type_=PointLedgerType.RECTIFICACION.value,
                      user_id=e.user_id, event_id=event.id,
                      reason=f"Rectificación: {reason}", author_id=actor.id, reverses_id=e.id)
        reversed_total += e.points
    event.status = EventStatus.BORRADOR.value
    event.meta = {**(event.meta or {}), "last_rectification": reason}
    db.commit()
    return {"event_id": event.id, "reversed_points": reversed_total}


# ---------------------------------------------------------------------------
# Compensación por dinámica no realizada
# ---------------------------------------------------------------------------
def apply_compensation(db: Session, actor: User, house_id: int, amount: int | None,
                       reason: str, event_id: int | None = None) -> PointLedger:
    amt = amount if amount is not None else scoring.compensation_amount()
    entry = _apply_ledger(db, house_id=house_id, points=amt, type_=PointLedgerType.COMPENSACION.value,
                          event_id=event_id, reason=reason, author_id=actor.id,
                          meta={"compensation": True})
    if event_id:
        ev = db.get(Event, event_id)
        if ev:
            ev.compensation_applied = True
            ev.status = EventStatus.CANCELADA.value
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# Penalización de puntos
# ---------------------------------------------------------------------------
def penalize_points(db: Session, actor: User, house_id: int, amount: int, reason: str,
                    user_id: int | None = None, rule_ref: str | None = None) -> PointLedger:
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El importe debe ser mayor que cero.")
    entry = _apply_ledger(db, house_id=house_id, points=-amount, type_=PointLedgerType.PENALIZACION.value,
                          user_id=user_id, reason=reason, author_id=actor.id,
                          meta={"rule_ref": rule_ref})
    db.commit()
    return entry


# ---------------------------------------------------------------------------
# Casa Nocturna (asignación manual, sin fórmula automática)
# ---------------------------------------------------------------------------
def casa_nocturna_allocation(db: Session, actor: User, allocations: list[dict], reason: str) -> list[PointLedger]:
    entries = []
    for alloc in allocations:
        hid = int(alloc.get("house_id"))
        pts = int(alloc.get("points", 0))
        if pts == 0:
            continue
        entries.append(_apply_ledger(db, house_id=hid, points=pts,
                                     type_=PointLedgerType.CASA_NOCTURNA.value,
                                     reason=reason, author_id=actor.id,
                                     meta={"casa_nocturna": True}))
    db.commit()
    return entries


# ---------------------------------------------------------------------------
# Reconciliación
# ---------------------------------------------------------------------------
def reconcile_scores(db: Session) -> list[dict]:
    out = []
    houses = db.scalars(select(House).where(House.is_competing.is_(True))).all()
    for h in houses:
        ledger_sum = int(db.scalar(
            select(func.coalesce(func.sum(PointLedger.points), 0)).where(PointLedger.house_id == h.id)
        ) or 0)
        cached = get_house_score(db, h.id)
        out.append({"house_id": h.id, "code": h.code, "cached": cached,
                    "ledger_sum": ledger_sum, "consistent": cached == ledger_sum})
    return out
