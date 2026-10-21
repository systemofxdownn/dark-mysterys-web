"""Banco de Lunarias: saldo, movimientos, transferencias, depósitos, ajustes y penalizaciones."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import AccountStatus, Role, SanctionResource
from ..models import Approval, Sanction, User, Wallet, WalletEntry, WalletTransaction
from ..permissions import HOUSE_LEADER_ROLES, Perm, has_permission
from ..schemas import (
    AdjustIn,
    DepositIn,
    ReversalIn,
    SanctionIn,
    TransferIn,
    serialize_entry,
    serialize_sanction,
    serialize_transaction,
    serialize_wallet,
)
from ..services import accounts, wallet_service

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("/me")
def my_wallet(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = wallet_service.get_or_create_wallet(db, user)
    db.commit()
    return serialize_wallet(wallet)


@router.get("/transactions")
def my_transactions(limit: int = 50, offset: int = 0,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Historial personal: asientos donde participa el usuario."""
    stmt = (
        select(WalletTransaction, WalletEntry)
        .join(WalletEntry, WalletEntry.transaction_id == WalletTransaction.id)
        .where(WalletEntry.user_id == user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(min(limit, 200)).offset(offset)
    )
    rows = db.execute(stmt).all()
    return [{"transaction": serialize_transaction(t), "entry": serialize_entry(e)} for t, e in rows]


@router.get("/transactions/all")
def all_transactions(limit: int = 100, offset: int = 0, user_id: int | None = None,
                     tx_type: str | None = None,
                     user: User = Depends(require_permission(Perm.WALLET_VIEW_ALL)),
                     db: Session = Depends(get_db)):
    stmt = select(WalletTransaction).order_by(WalletTransaction.created_at.desc())
    if tx_type:
        stmt = stmt.where(WalletTransaction.type == tx_type)
    if user_id:
        stmt = stmt.where((WalletTransaction.counterparty_id == user_id) | (WalletTransaction.author_id == user_id))
    txs = db.scalars(stmt.limit(min(limit, 500)).offset(offset)).all()
    return [serialize_transaction(t) for t in txs]


@router.get("/accounts")
def accounts_overview(q: str | None = None,
                      user: User = Depends(require_permission(Perm.WALLET_VIEW_ALL)),
                      db: Session = Depends(get_db)):
    stmt = select(User, Wallet).outerjoin(Wallet, Wallet.user_id == User.id).order_by(User.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((User.display_name.ilike(like)) | (User.identifier.ilike(like)))
    rows = db.execute(stmt).all()
    out = []
    for u, w in rows:
        out.append({
            "user": {"id": u.id, "identifier": u.identifier, "display_name": u.display_name,
                     "role": u.role, "status": u.status,
                     "house": u.house.name if u.house else None},
            "balance": w.balance if w else 0,
            "debt": max(0, -(w.balance if w else 0)),
        })
    return out


@router.post("/transfer")
def transfer(data: TransferIn, request: Request, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    if not has_permission(user.role, Perm.WALLET_TRANSFER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Permiso denegado.")
    recipient = None
    if data.to_user_id:
        recipient = db.get(User, data.to_user_id)
    elif data.to_identifier:
        recipient = accounts.find_user_by_login(db, data.to_identifier)
    if recipient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Destinatario inexistente.")
    if recipient.status != AccountStatus.ACTIVA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede transferir a una cuenta no activa/congelada.")

    tx = wallet_service.transfer(db, user, user, recipient, data.amount, data.reason,
                                 data.idempotency_key, get_client_ip(request))
    audit(db, user, "TRANSFERENCIA", "wallet_transaction", tx.id,
          after={"to": recipient.identifier, "amount": data.amount}, ip=get_client_ip(request))
    db.commit()
    return serialize_transaction(tx)


@router.post("/deposit")
def deposit(data: DepositIn, request: Request,
            actor: User = Depends(require_permission(Perm.WALLET_DEPOSIT)),
            db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    tx = wallet_service.deposit(db, actor, target, data.amount, data.reason,
                                data.idempotency_key, get_client_ip(request))
    audit(db, actor, "DEPOSITO", "wallet_transaction", tx.id,
          after={"to": target.identifier, "amount": data.amount, "reason": data.reason},
          ip=get_client_ip(request))
    db.commit()
    return serialize_transaction(tx)


@router.post("/adjust")
def adjust(data: AdjustIn, request: Request,
           actor: User = Depends(require_permission(Perm.WALLET_ADJUST)),
           db: Session = Depends(get_db)):
    target = db.get(User, data.user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario inexistente.")
    tx, pending = wallet_service.adjust(db, actor, target, data.amount, data.reason,
                                        data.idempotency_key, get_client_ip(request))
    audit(db, actor, "AJUSTE_SALDO", "wallet_transaction", tx.id,
          after={"to": target.identifier, "amount": data.amount, "pending_approval": pending},
          ip=get_client_ip(request))
    db.commit()
    return {"transaction": serialize_transaction(tx), "pending_approval": pending}


@router.post("/sanction")
def sanction_lunarias(data: SanctionIn, request: Request,
                      actor: User = Depends(require_permission(Perm.SANCTIONS_LUNARIAS)),
                      db: Session = Depends(get_db)):
    if data.resource != SanctionResource.LUNARIAS.value:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Este endpoint es para penalizaciones de Lunarias.")
    target = db.get(User, data.target_user_id) if data.target_user_id else None
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario objetivo inexistente.")

    # Jefes/subjefes: solo integrantes de su propia Casa
    if has_permission(actor.role, Perm.SANCTIONS_OWN_HOUSE_ONLY) and target.house_id != actor.house_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo podés penalizar a integrantes de tu Casa.")

    tx = wallet_service.penalize_lunarias(db, actor, target, data.amount, data.reason, data.rule_ref,
                                          get_client_ip(request))
    db.add(Sanction(target_user_id=target.id, resource=SanctionResource.LUNARIAS.value,
                    amount=data.amount, reason=data.reason, rule_ref=data.rule_ref,
                    author_id=actor.id, transaction_id=tx.id))
    audit(db, actor, "PENALIZACION_LUNARIAS", "user", target.id,
          after={"amount": data.amount, "reason": data.reason}, ip=get_client_ip(request))
    db.commit()
    return serialize_transaction(tx)


@router.get("/approvals")
def list_approvals(actor: User = Depends(require_permission(Perm.WALLET_APPROVE_LARGE)),
                   db: Session = Depends(get_db)):
    rows = db.scalars(select(Approval).order_by(Approval.created_at.desc()).limit(200)).all()
    return [{"id": a.id, "transaction_id": a.transaction_id, "requested_by": a.requested_by,
             "amount": a.amount, "reason": a.reason, "status": a.status,
             "resolved_by": a.resolved_by} for a in rows]


@router.post("/approvals/{approval_id}")
def resolve_approval(approval_id: int, approve: bool, reason: str | None = None,
                     actor: User = Depends(require_permission(Perm.WALLET_APPROVE_LARGE)),
                     db: Session = Depends(get_db)):
    tx = wallet_service.approve_adjustment(db, actor, approval_id, approve, reason)
    audit(db, actor, "APROBACION_AJUSTE", "approval", approval_id,
          after={"approved": approve})
    db.commit()
    return serialize_transaction(tx)


@router.post("/transactions/{tx_id}/reverse")
def reverse_tx(tx_id: int, data: ReversalIn, actor: User = Depends(require_permission(Perm.WALLET_ADJUST)),
               db: Session = Depends(get_db)):
    original = db.get(WalletTransaction, tx_id)
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transacción inexistente.")
    reversal = wallet_service.reverse_transaction(db, actor, original, data.reason)
    audit(db, actor, "REVERSION", "wallet_transaction", reversal.id,
          after={"reversed": original.reference, "reason": data.reason})
    db.commit()
    return serialize_transaction(reversal)


@router.get("/reconcile")
def reconcile(actor: User = Depends(require_permission(Perm.WALLET_ADJUST)),
              db: Session = Depends(get_db)):
    wallets = db.scalars(select(Wallet)).all()
    results = [wallet_service.reconcile_wallet(db, w) for w in wallets]
    return {"consistent": all(r["consistent"] for r in results), "wallets": results}
