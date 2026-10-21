"""
Puntos de la Copa.

VISIBILIDAD (aplicada en backend):
- ADMINISTRADOR: todo.
- JEFE/SUBJEFE: marcador de las 3 Casas (no el libro individual completo).
- BANQUERO: sin acceso a puntos.
- ESTUDIANTE: sin acceso a puntos.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import PointLedgerType, Role, SanctionResource
from ..models import PointLedger, Sanction, User
from ..permissions import HOUSE_LEADER_ROLES, Perm, has_permission
from ..schemas import CasaNocturnaIn, CompensationIn, SanctionIn, serialize_ledger
from ..services import points_service

router = APIRouter(prefix="/api/points", tags=["points"])


def _require_points_viewer(user: User) -> None:
    if not (has_permission(user.role, Perm.POINTS_VIEW_ALL) or user.role == Role.ADMINISTRADOR.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tenés acceso al sistema de puntos.")


@router.get("/scoreboard")
def scoreboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_points_viewer(user)
    return {"houses": points_service.get_all_scores(db)}


@router.get("/ledger")
def ledger(house_id: int | None = None, limit: int = 200, offset: int = 0,
           admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
           db: Session = Depends(get_db)):
    stmt = select(PointLedger).order_by(PointLedger.created_at.desc())
    if house_id:
        stmt = stmt.where(PointLedger.house_id == house_id)
    rows = db.scalars(stmt.limit(min(limit, 500)).offset(offset)).all()
    return [serialize_ledger(l) for l in rows]


@router.get("/reconcile")
def reconcile(admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
              db: Session = Depends(get_db)):
    results = points_service.reconcile_scores(db)
    return {"consistent": all(r["consistent"] for r in results), "houses": results}


@router.post("/sanction")
def sanction_points(data: SanctionIn, request: Request,
                    actor: User = Depends(require_permission(Perm.SANCTIONS_POINTS)),
                    db: Session = Depends(get_db)):
    if data.resource != SanctionResource.PUNTOS.value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Este endpoint es para penalizaciones de Puntos.")

    target_user = db.get(User, data.target_user_id) if data.target_user_id else None
    house_id = data.target_house_id or (target_user.house_id if target_user else None)
    if house_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Indicá la Casa o el usuario objetivo.")

    # Jefes/subjefes: solo integrantes de su propia Casa
    if has_permission(actor.role, Perm.SANCTIONS_OWN_HOUSE_ONLY):
        if target_user is None or target_user.house_id != actor.house_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés penalizar puntos de integrantes de tu Casa.")

    entry = points_service.penalize_points(db, actor, house_id, data.amount, data.reason,
                                           user_id=data.target_user_id, rule_ref=data.rule_ref)
    db.add(Sanction(target_user_id=data.target_user_id, target_house_id=house_id,
                    resource=SanctionResource.PUNTOS.value, amount=data.amount,
                    reason=data.reason, rule_ref=data.rule_ref, author_id=actor.id,
                    ledger_id=entry.id))
    audit(db, actor, "PENALIZACION_PUNTOS", "house", house_id,
          after={"amount": data.amount, "reason": data.reason}, ip=get_client_ip(request))
    db.commit()
    return serialize_ledger(entry)


@router.post("/compensation")
def compensation(data: CompensationIn, request: Request,
                 admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                 db: Session = Depends(get_db)):
    entry = points_service.apply_compensation(db, admin, data.house_id, data.amount,
                                              data.reason, data.event_id)
    audit(db, admin, "COMPENSACION", "house", data.house_id,
          after={"amount": entry.points, "reason": data.reason}, ip=get_client_ip(request))
    db.commit()
    return serialize_ledger(entry)


@router.post("/casa-nocturna")
def casa_nocturna(data: CasaNocturnaIn, request: Request,
                  admin: User = Depends(require_permission(Perm.POINTS_MANAGE)),
                  db: Session = Depends(get_db)):
    entries = points_service.casa_nocturna_allocation(db, admin, data.allocations, data.reason)
    audit(db, admin, "CASA_NOCTURNA", "points", None, after={"allocations": data.allocations},
          ip=get_client_ip(request))
    db.commit()
    return [serialize_ledger(e) for e in entries]


@router.get("/sanctions")
def list_sanctions(actor: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if actor.role == Role.ADMINISTRADOR.value:
        rows = db.scalars(select(Sanction).order_by(Sanction.created_at.desc()).limit(300)).all()
    elif actor.role in HOUSE_LEADER_ROLES:
        rows = db.scalars(select(Sanction).where(Sanction.target_house_id == actor.house_id)
                          .order_by(Sanction.created_at.desc()).limit(300)).all()
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
    return [{"id": s.id, "target_user_id": s.target_user_id, "target_house_id": s.target_house_id,
             "resource": s.resource, "amount": s.amount, "reason": s.reason,
             "rule_ref": s.rule_ref, "author_id": s.author_id, "created_at": s.created_at.isoformat()}
            for s in rows]
