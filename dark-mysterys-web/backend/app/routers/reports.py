"""
Informes y exportación (CSV / XLSX).

Todas las exportaciones se generan en el BACKEND con consultas autorizadas.
Los permisos se verifican por informe; nunca se confía en filtros del navegador.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_permission
from ..enums import Role
from ..models import (
    Event,
    House,
    ParticipationRecord,
    PointLedger,
    Product,
    ProductActivation,
    Purchase,
    Refund,
    Sanction,
    User,
    Wallet,
    WalletTransaction,
)
from ..permissions import HOUSE_LEADER_ROLES, Perm, has_permission
from ..services import points_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _rows_wallet_global(db, user, params):
    stmt = select(WalletTransaction).order_by(WalletTransaction.created_at.desc()).limit(5000)
    rows = db.scalars(stmt).all()
    return [{"referencia": t.reference, "tipo": t.type, "importe": t.amount, "estado": t.status,
             "autor_id": t.author_id, "contraparte_id": t.counterparty_id, "motivo": t.reason,
             "fecha": t.created_at.isoformat()} for t in rows]


def _rows_wallet_account(db, user, params):
    target_id = int(params.get("user_id", user.id))
    if target_id != user.id and not has_permission(user.role, Perm.WALLET_VIEW_ALL):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés exportar tus movimientos.")
    from ..models import WalletEntry
    rows = db.execute(
        select(WalletTransaction, WalletEntry).join(WalletEntry, WalletEntry.transaction_id == WalletTransaction.id)
        .where(WalletEntry.user_id == target_id).order_by(WalletTransaction.created_at.desc()).limit(5000)
    ).all()
    return [{"referencia": t.reference, "tipo": t.type, "importe_asiento": e.amount,
             "saldo_resultante": e.balance_after, "motivo": t.reason,
             "fecha": t.created_at.isoformat()} for t, e in rows]


def _rows_purchases(db, user, params):
    stmt = select(Purchase).order_by(Purchase.purchased_at.desc()).limit(5000)
    if user.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(Purchase.house_id == user.house_id)
    rows = db.scalars(stmt).all()
    return [{"id": p.id, "usuario_id": p.user_id, "producto": p.product_name, "precio": p.price_paid,
             "casa_id": p.house_id, "estado": p.status, "fecha": p.purchased_at.isoformat()} for p in rows]


def _rows_refunds(db, user, params):
    rows = db.scalars(select(Refund).order_by(Refund.created_at.desc()).limit(5000)).all()
    return [{"id": r.id, "compra_id": r.purchase_id, "solicitante": r.requested_by, "importe": r.amount,
             "estado": r.status, "procesado_por": r.processed_by, "motivo": r.reason,
             "fecha": r.created_at.isoformat()} for r in rows]


def _rows_activations(db, user, params):
    rows = db.execute(select(ProductActivation, Purchase).join(Purchase, Purchase.id == ProductActivation.purchase_id)
                      .order_by(ProductActivation.created_at.desc()).limit(5000)).all()
    return [{"activacion_id": a.id, "producto": p.product_name, "usuario_id": a.user_id,
             "casa_id": p.house_id, "estado": a.status, "evento_id": a.event_id,
             "motivo": a.reason, "fecha": a.created_at.isoformat()} for a, p in rows]


def _rows_products(db, user, params):
    rows = db.scalars(select(Product).order_by(Product.id)).all()
    return [{"id": p.id, "nombre": p.name, "precio": p.price, "publicado": p.published,
             "afecta_puntos": p.affects_points, "stock": p.stock} for p in rows]


def _rows_house_points(db, user, params):
    return points_service.get_all_scores(db)


def _rows_events(db, user, params):
    rows = db.scalars(select(Event).order_by(Event.created_at.desc()).limit(5000)).all()
    return [{"id": e.id, "nombre": e.name, "tipo": e.type, "estado": e.status,
             "casa_responsable": e.house_responsible_id, "puntos_dobles": e.double_points,
             "fecha": e.scheduled_at.isoformat() if e.scheduled_at else None} for e in rows]


def _rows_rewards(db, user, params):
    rows = db.scalars(select(PointLedger).where(PointLedger.type.in_(
        ["RETO_GRUPAL", "RETO_INDIVIDUAL", "COMPENSACION", "RECOMPENSA_ORGANIZACION", "CASA_NOCTURNA"]
    )).order_by(PointLedger.created_at.desc()).limit(5000)).all()
    return [{"id": l.id, "casa_id": l.house_id, "tipo": l.type, "puntos": l.points,
             "motivo": l.reason, "evento_id": l.event_id, "fecha": l.created_at.isoformat()} for l in rows]


def _rows_partis(db, user, params):
    stmt = select(ParticipationRecord).order_by(ParticipationRecord.created_at.desc()).limit(5000)
    if user.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(ParticipationRecord.house_id == user.house_id)
    rows = db.scalars(stmt).all()
    return [{"id": r.id, "usuario_id": r.user_id, "casa_id": r.house_id, "evento_id": r.event_id,
             "partis": r.partis, "motivo": r.reason, "fecha": r.created_at.isoformat()} for r in rows]


def _rows_members(db, user, params):
    stmt = select(User).order_by(User.id)
    if user.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(User.house_id == user.house_id)
    rows = db.scalars(stmt).all()
    return [{"id": u.id, "identificador": u.identifier, "nombre": u.display_name, "rol": u.role,
             "estado": u.status, "casa_id": u.house_id} for u in rows]


def _rows_sanctions(db, user, params):
    stmt = select(Sanction).order_by(Sanction.created_at.desc()).limit(5000)
    if user.role in HOUSE_LEADER_ROLES:
        stmt = stmt.where(Sanction.target_house_id == user.house_id)
    rows = db.scalars(stmt).all()
    return [{"id": s.id, "usuario_id": s.target_user_id, "casa_id": s.target_house_id,
             "recurso": s.resource, "importe": s.amount, "motivo": s.reason,
             "autor_id": s.author_id, "fecha": s.created_at.isoformat()} for s in rows]


def _rows_admin_activity(db, user, params):
    from ..models import AuditLog
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(5000)).all()
    return [{"id": r.id, "actor": r.actor_identifier, "accion": r.action, "entidad": r.entity_type,
             "entidad_id": r.entity_id, "fecha": r.created_at.isoformat()} for r in rows]


# nombre -> (función, permiso requerido)
REPORTS = {
    "wallet_global": (_rows_wallet_global, Perm.REPORTS_EXPORT_FINANCIAL),
    "wallet_account": (_rows_wallet_account, None),
    "purchases": (_rows_purchases, Perm.REPORTS_EXPORT_OWN_HOUSE),
    "refunds": (_rows_refunds, Perm.REPORTS_EXPORT_ALL),
    "activations": (_rows_activations, Perm.SHOP_ACTIVATIONS_MANAGE),
    "products": (_rows_products, Perm.SHOP_MANAGE),
    "house_points": (_rows_house_points, Perm.POINTS_VIEW_ALL),
    "events": (_rows_events, Perm.POINTS_MANAGE),
    "rewards": (_rows_rewards, Perm.REPORTS_EXPORT_ALL),
    "partis": (_rows_partis, Perm.REPORTS_EXPORT_OWN_HOUSE),
    "members": (_rows_members, Perm.USERS_VIEW_OWN_HOUSE),
    "sanctions": (_rows_sanctions, Perm.REPORTS_EXPORT_OWN_HOUSE),
    "admin_activity": (_rows_admin_activity, Perm.AUDIT_VIEW),
}


@router.get("")
def available_reports(user: User = Depends(get_current_user)):
    allowed = []
    for name, (_, perm) in REPORTS.items():
        if perm is None or has_permission(user.role, perm) or user.role == Role.ADMINISTRADOR.value:
            allowed.append(name)
    return {"reports": allowed}


@router.get("/{report_name}")
def export_report(report_name: str, format: str = "csv", user_id: int | None = None,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if report_name not in REPORTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Informe inexistente.")
    fn, perm = REPORTS[report_name]
    if perm is not None and not has_permission(user.role, perm):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No tenés permiso para exportar este informe.")

    params = {"user_id": user_id} if user_id else {}
    rows = fn(db, user, params)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"darkmysterys_{report_name}_{stamp}"

    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = report_name[:30]
        if rows:
            headers = list(rows[0].keys())
            ws.append(headers)
            for r in rows:
                ws.append([r.get(h) for h in headers])
        else:
            ws.append(["sin datos"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    # CSV
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    else:
        buf.write("sin datos\n")
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
