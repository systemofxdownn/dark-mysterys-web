"""
Servicio de Lunarias (banco).

Garantías:
- Atomicidad: cada operación se ejecuta dentro de la transacción de la sesión
  y se confirma (commit) de forma atómica. Los movimientos multi-asiento se
  crean juntos o no se crean.
- Concurrencia: se bloquea la fila de la cartera con SELECT ... FOR UPDATE
  (no-op en SQLite, que serializa escrituras). En PostgreSQL evita carreras.
- Idempotencia: `idempotency_key` único por transacción; reintentos devuelven
  la operación original sin duplicar.
- Doble asiento: cada movimiento genera `wallet_entries` (+ crédito / - débito)
  con `balance_after` para reconstruir el saldo.
- Los movimientos contabilizados NO se borran: las correcciones se hacen con
  operaciones compensatorias (reversión).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import (
    AccountStatus,
    TxStatus,
    WalletTxType,
)
from ..models import Approval, User, Wallet, WalletEntry, WalletTransaction
from ..security import hash_password  # noqa: F401 (re-export util)
from .notifications import notify


def generate_reference(prefix: str = "TX") -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}"


def get_or_create_wallet(db: Session, user: User) -> Wallet:
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user.id))
    if wallet is None:
        wallet = Wallet(user_id=user.id, balance=0)
        db.add(wallet)
        db.flush()
    return wallet


def _lock_wallet(db: Session, wallet_id: int) -> Wallet:
    stmt = select(Wallet).where(Wallet.id == wallet_id)
    try:
        stmt = stmt.with_for_update()
    except Exception:  # pragma: no cover
        pass
    return db.scalar(stmt)


def _apply_entry(db: Session, wallet: Wallet, amount: int) -> WalletEntry:
    """Aplica un cambio al saldo y registra el asiento. No hace commit."""
    wallet.balance = wallet.balance + amount
    entry = WalletEntry(
        transaction_id=None,  # se asigna al vincular
        wallet_id=wallet.id,
        user_id=wallet.user_id,
        amount=amount,
        balance_after=wallet.balance,
    )
    return entry


def _existing_by_idempotency(db: Session, key: str | None) -> WalletTransaction | None:
    if not key:
        return None
    return db.scalar(select(WalletTransaction).where(WalletTransaction.idempotency_key == key))


def _assert_operable(user: User):
    if user.status != AccountStatus.ACTIVA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La cuenta destino no está activa.")


# ---------------------------------------------------------------------------
# Depósito (emisión)
# ---------------------------------------------------------------------------
def deposit(db: Session, actor: User, target: User, amount: int, reason: str,
            idempotency_key: str | None = None, ip: str | None = None) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El importe debe ser mayor que cero.")
    existing = _existing_by_idempotency(db, idempotency_key)
    if existing:
        return existing
    _assert_operable(target)

    wallet = get_or_create_wallet(db, target)
    wallet = _lock_wallet(db, wallet.id)

    tx = WalletTransaction(
        reference=generate_reference("DEP"),
        type=WalletTxType.DEPOSITO.value,
        amount=amount,
        status=TxStatus.COMPLETADA.value,
        reason=reason,
        author_id=actor.id,
        counterparty_id=target.id,
        idempotency_key=idempotency_key,
    )
    db.add(tx)
    db.flush()

    entry = _apply_entry(db, wallet, amount)
    entry.transaction_id = tx.id
    db.add(entry)

    notify(db, target.id, "BANCO", "Depósito recibido",
           f"Se acreditaron {amount} Lunarias. Motivo: {reason}", link="/bank")
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Transferencia (atómica, doble asiento)
# ---------------------------------------------------------------------------
def transfer(db: Session, actor: User, sender: User, recipient: User, amount: int,
             reason: str | None = None, idempotency_key: str | None = None,
             ip: str | None = None) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No se admiten importes nulos o negativos.")
    if sender.id == recipient.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No puede transferirse a sí mismo.")
    existing = _existing_by_idempotency(db, idempotency_key)
    if existing:
        return existing
    _assert_operable(sender)
    _assert_operable(recipient)  # no se transfiere a cuentas congeladas

    # Bloqueo en orden de id para evitar deadlocks
    wallets = {}
    for u in sorted([sender, recipient], key=lambda x: x.id):
        w = get_or_create_wallet(db, u)
        wallets[u.id] = _lock_wallet(db, w.id)

    sender_wallet = wallets[sender.id]
    recipient_wallet = wallets[recipient.id]

    if sender_wallet.balance < amount:
        raise HTTPException(status.HTTP_409_CONFLICT, "Saldo insuficiente para la transferencia.")

    tx = WalletTransaction(
        reference=generate_reference("TRF"),
        type=WalletTxType.TRANSFERENCIA.value,
        amount=amount,
        status=TxStatus.COMPLETADA.value,
        reason=reason or f"Transferencia a {recipient.identifier}",
        author_id=actor.id,
        counterparty_id=recipient.id,
        idempotency_key=idempotency_key,
        meta={"from": sender.id, "to": recipient.id},
    )
    db.add(tx)
    db.flush()

    e_out = _apply_entry(db, sender_wallet, -amount)
    e_in = _apply_entry(db, recipient_wallet, amount)
    e_out.transaction_id = tx.id
    e_in.transaction_id = tx.id
    db.add_all([e_out, e_in])

    notify(db, sender.id, "BANCO", "Transferencia enviada",
           f"Enviaste {amount} Lunarias a {recipient.display_name} ({recipient.identifier}).", link="/bank")
    notify(db, recipient.id, "BANCO", "Transferencia recibida",
           f"Recibiste {amount} Lunarias de {sender.display_name} ({sender.identifier}).", link="/bank")
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Ajuste (puede requerir aprobación de Dirección)
# ---------------------------------------------------------------------------
def adjust(db: Session, actor: User, target: User, amount: int, reason: str,
           idempotency_key: str | None = None, ip: str | None = None) -> tuple[WalletTransaction, bool]:
    """
    Ajuste positivo o negativo. Devuelve (transacción, pendiente_de_aprobacion).
    Si |amount| >= umbral y el actor NO es administrador, queda PENDIENTE_APROBACION.
    """
    if amount == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El ajuste no puede ser cero.")
    existing = _existing_by_idempotency(db, idempotency_key)
    if existing:
        return existing, existing.status == TxStatus.PENDIENTE_APROBACION.value

    needs_approval = abs(amount) >= settings.large_adjustment_threshold and actor.role != "ADMINISTRADOR"
    tx_type = WalletTxType.AJUSTE_POSITIVO.value if amount > 0 else WalletTxType.AJUSTE_NEGATIVO.value

    wallet = get_or_create_wallet(db, target)
    wallet = _lock_wallet(db, wallet.id)

    tx = WalletTransaction(
        reference=generate_reference("ADJ"),
        type=tx_type,
        amount=amount,
        status=TxStatus.PENDIENTE_APROBACION.value if needs_approval else TxStatus.COMPLETADA.value,
        reason=reason,
        author_id=actor.id,
        counterparty_id=target.id,
        idempotency_key=idempotency_key,
        meta={"requested_amount": amount},
    )
    db.add(tx)
    db.flush()

    if needs_approval:
        db.add(Approval(
            transaction_id=tx.id, requested_by=actor.id, amount=amount, reason=reason,
            status="PENDIENTE_APROBACION",
        ))
        notify(db, target.id, "BANCO", "Ajuste en revisión",
               f"Se solicitó un ajuste de {amount} Lunarias pendiente de aprobación.", link="/bank")
    else:
        entry = _apply_entry(db, wallet, amount)
        entry.transaction_id = tx.id
        db.add(entry)
        notify(db, target.id, "BANCO", "Ajuste de saldo",
               f"Se aplicó un ajuste de {amount:+d} Lunarias. Motivo: {reason}", link="/bank")

    db.commit()
    db.refresh(tx)
    return tx, needs_approval


def approve_adjustment(db: Session, admin: User, approval_id: int, approve: bool,
                       reason: str | None = None) -> WalletTransaction:
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aprobación inexistente.")
    if approval.status != "PENDIENTE_APROBACION":
        raise HTTPException(status.HTTP_409_CONFLICT, "La aprobación ya fue resuelta.")

    tx = db.get(WalletTransaction, approval.transaction_id)
    approval.resolved_by = admin.id
    approval.resolved_at = datetime.now(timezone.utc)

    if approve:
        approval.status = "APROBADO"
        tx.status = TxStatus.COMPLETADA.value
        wallet = get_or_create_wallet(db, db.get(User, tx.counterparty_id))
        wallet = _lock_wallet(db, wallet.id)
        entry = _apply_entry(db, wallet, tx.amount)
        entry.transaction_id = tx.id
        db.add(entry)
        notify(db, tx.counterparty_id, "BANCO", "Ajuste aprobado",
               f"Se acreditó un ajuste de {tx.amount:+d} Lunarias.", link="/bank")
    else:
        approval.status = "RECHAZADO"
        tx.status = TxStatus.RECHAZADA.value
        notify(db, tx.counterparty_id, "BANCO", "Ajuste rechazado",
               f"El ajuste de {tx.amount:+d} Lunarias fue rechazado.", link="/bank")

    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Penalización de Lunarias (puede dejar deuda)
# ---------------------------------------------------------------------------
def penalize_lunarias(db: Session, actor: User, target: User, amount: int, reason: str,
                      rule_ref: str | None = None, ip: str | None = None) -> WalletTransaction:
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El importe debe ser mayor que cero.")
    wallet = get_or_create_wallet(db, target)
    wallet = _lock_wallet(db, wallet.id)

    tx = WalletTransaction(
        reference=generate_reference("PEN"),
        type=WalletTxType.PENALIZACION.value,
        amount=amount,
        status=TxStatus.COMPLETADA.value,
        reason=reason,
        author_id=actor.id,
        counterparty_id=target.id,
        meta={"rule_ref": rule_ref, "allows_negative": True},
    )
    db.add(tx)
    db.flush()

    # Puede dejar el saldo negativo (deuda). El ingreso futuro la salda.
    entry = _apply_entry(db, wallet, -amount)
    entry.transaction_id = tx.id
    db.add(entry)

    notify(db, target.id, "BANCO", "Penalización de Lunarias",
           f"Se aplicó una penalización de {amount} Lunarias. Motivo: {reason}", link="/bank")
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Reembolso
# ---------------------------------------------------------------------------
def credit_refund(db: Session, actor: User, target: User, amount: int, reason: str,
                  purchase_id: int | None = None, refund_id: int | None = None) -> WalletTransaction:
    wallet = get_or_create_wallet(db, target)
    wallet = _lock_wallet(db, wallet.id)
    tx = WalletTransaction(
        reference=generate_reference("REF"),
        type=WalletTxType.REEMBOLSO.value,
        amount=amount,
        status=TxStatus.COMPLETADA.value,
        reason=reason,
        author_id=actor.id,
        counterparty_id=target.id,
        purchase_id=purchase_id,
        refund_id=refund_id,
    )
    db.add(tx)
    db.flush()
    entry = _apply_entry(db, wallet, amount)
    entry.transaction_id = tx.id
    db.add(entry)
    notify(db, target.id, "TIENDA", "Reembolso acreditado",
           f"Se te reembolsaron {amount} Lunarias. Motivo: {reason}", link="/shop")
    db.commit()
    db.refresh(tx)
    return tx


# ---------------------------------------------------------------------------
# Reversión (operación compensatoria; nunca borra)
# ---------------------------------------------------------------------------
def reverse_transaction(db: Session, actor: User, original: WalletTransaction, reason: str) -> WalletTransaction:
    if original.status == TxStatus.REVERTIDA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La operación ya fue revertida.")
    if original.status != TxStatus.COMPLETADA.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo pueden revertirse operaciones completadas.")

    reversal = WalletTransaction(
        reference=generate_reference("REV"),
        type=WalletTxType.REVERSION.value,
        amount=original.amount,
        status=TxStatus.COMPLETADA.value,
        reason=reason,
        author_id=actor.id,
        reverses_transaction_id=original.id,
        meta={"reversed_reference": original.reference},
    )
    db.add(reversal)
    db.flush()

    # Invierte cada asiento original
    for entry in original.entries:
        wallet = _lock_wallet(db, entry.wallet_id)
        rev = _apply_entry(db, wallet, -entry.amount)
        rev.transaction_id = reversal.id
        db.add(rev)

    original.status = TxStatus.REVERTIDA.value
    db.commit()
    db.refresh(reversal)
    return reversal


# ---------------------------------------------------------------------------
# Reconciliación
# ---------------------------------------------------------------------------
def reconcile_wallet(db: Session, wallet: Wallet) -> dict:
    """Verifica que balance == suma de asientos. Devuelve el resultado."""
    total = db.scalar(
        select(func.coalesce(func.sum(WalletEntry.amount), 0)).where(WalletEntry.wallet_id == wallet.id)
    )
    return {
        "wallet_id": wallet.id,
        "user_id": wallet.user_id,
        "balance": wallet.balance,
        "ledger_sum": int(total or 0),
        "consistent": int(total or 0) == wallet.balance,
    }
