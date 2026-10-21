"""
Servicio de la Tienda.

Reglas:
- Abre lunes a viernes, 30 min después de la primera dinámica y cierra 30 min
  después de la última. Las activaciones están disponibles hasta las 00:00 (AR).
- Límite general: 8 compras/día por Casa; 4 activaciones/día por Casa.
- Los límites son de la Casa y no cambian si la persona cambia de Casa.
- Compra atómica: valida saldo, estado de cuenta, límites y disponibilidad, y
  descuenta en una única transacción. Si algo falla, NO hay débito.
- Reembolso: requiere solicitud + aprobación de Dirección, dentro de 15 días,
  y solo si el producto no fue utilizado.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import (
    AccountStatus,
    ActivationStatus,
    PurchaseStatus,
    RefundStatus,
    WalletTxType,
)
from ..models import (
    ActivationHistory,
    Event,
    Product,
    ProductActivation,
    Purchase,
    Refund,
    Schedule,
    User,
    Wallet,
    WalletTransaction,
)
from ..schemas import iso
from . import wallet_service
from .notifications import notify
from .timez import combine_local, day_bounds_utc, ensure_utc, now_utc, parse_hhmm, today_local, tz


# ---------------------------------------------------------------------------
# Horario de la tienda
# ---------------------------------------------------------------------------
def shop_hours(db: Session, tzname: str | None = None) -> dict:
    """Calcula el horario de la tienda para hoy (zona del usuario)."""
    d = today_local(tzname)
    weekday = d.weekday()  # 0=lunes
    schedules = db.scalars(
        select(Schedule).where(Schedule.date == d.isoformat(), Schedule.status != "CANCELADA")
    ).all()
    starts = [parse_hhmm(s.start_time) for s in schedules if s.start_time]
    ends = [parse_hhmm(s.end_time) for s in schedules if s.end_time]
    starts = [s for s in starts if s]
    ends = [e for e in ends if e]

    open_t = None
    close_t = None
    if starts:
        first = min(starts)
        open_dt = combine_local(d, first, tzname) + timedelta(minutes=settings.shop_open_offset_minutes)
        open_t = open_dt
    if ends:
        last = max(ends)
        close_dt = combine_local(d, last, tzname) + timedelta(minutes=settings.shop_close_offset_minutes)
        close_t = close_dt

    now = now_utc()
    is_weekday = weekday <= 4
    is_open = False
    if is_weekday:
        if open_t and close_t:
            # Ventana relativa a las dinámicas del día (30 min antes/después)
            is_open = open_t <= now <= close_t
        else:
            # Día hábil sin dinámicas cargadas: la tienda permanece abierta.
            # (Al cargar horarios, la ventana se ajusta automáticamente.)
            is_open = True

    return {
        "date": d.isoformat(),
        "weekday": weekday,
        "is_weekday": is_weekday,
        "opens_at": iso(open_t),
        "closes_at": iso(close_t),
        "activations_until": iso(combine_local(d + timedelta(days=1), parse_hhmm("00:00"), tzname)),
        "is_open": is_open,
        "daily_purchase_limit": settings.shop_daily_purchase_limit,
        "daily_activation_limit": settings.shop_daily_activation_limit,
    }


def assert_shop_open(db: Session, user: User):
    if not settings.shop_enforce_hours:
        return
    hours = shop_hours(db, user.timezone)
    if not hours["is_open"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "La tienda está cerrada. Abre de lunes a viernes, 30 min después de la primera dinámica.",
        )


# ---------------------------------------------------------------------------
# Límites diarios por Casa
# ---------------------------------------------------------------------------
def house_daily_purchase_count(db: Session, house_id: int | None, tzname: str | None) -> int:
    if house_id is None:
        return 0
    d = today_local(tzname)
    start, end = day_bounds_utc(d, tzname)
    return int(db.scalar(
        select(func.count(Purchase.id)).where(
            Purchase.house_id == house_id,
            Purchase.purchased_at >= start,
            Purchase.purchased_at < end,
            Purchase.status != PurchaseStatus.CANCELADO.value,
        )
    ) or 0)


def house_daily_activation_count(db: Session, house_id: int | None, tzname: str | None) -> int:
    if house_id is None:
        return 0
    d = today_local(tzname)
    start, end = day_bounds_utc(d, tzname)
    # "Compra ≠ activación": el límite cuenta ACTIVACIONES efectivas (ACTIVADO),
    # no las compras pendientes de activar.
    return int(db.scalar(
        select(func.count(ProductActivation.id))
        .join(Purchase, Purchase.id == ProductActivation.purchase_id)
        .where(
            Purchase.house_id == house_id,
            ProductActivation.created_at >= start,
            ProductActivation.created_at < end,
            ProductActivation.status == ActivationStatus.ACTIVADO.value,
        )
    ) or 0)


# ---------------------------------------------------------------------------
# Compra
# ---------------------------------------------------------------------------
def purchase(db: Session, user: User, product_id: int, idempotency_key: str | None = None) -> Purchase:
    if idempotency_key:
        existing = db.scalar(select(Purchase).where(Purchase.idempotency_key == idempotency_key))
        if existing:
            return existing

    if user.status != AccountStatus.ACTIVA.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "La cuenta no está habilitada para comprar.")

    # Horario de la tienda (lun-vie, ventana relativa a las dinámicas del día)
    assert_shop_open(db, user)

    product = db.get(Product, product_id)
    if product is None or not product.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto no disponible.")

    if product.stock is not None and product.stock <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Producto sin stock.")

    # Límite diario por Casa
    used = house_daily_purchase_count(db, user.house_id, user.timezone)
    if used >= settings.shop_daily_purchase_limit:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La Casa alcanzó el límite de {settings.shop_daily_purchase_limit} compras diarias.",
        )

    # Límite propio del producto
    if product.purchase_limit_per_day:
        d = today_local(user.timezone)
        start, end = day_bounds_utc(d, user.timezone)
        prod_count = int(db.scalar(
            select(func.count(Purchase.id)).where(
                Purchase.product_id == product.id,
                Purchase.house_id == user.house_id,
                Purchase.purchased_at >= start,
                Purchase.purchased_at < end,
                Purchase.status != PurchaseStatus.CANCELADO.value,
            )
        ) or 0)
        if prod_count >= product.purchase_limit_per_day:
            raise HTTPException(status.HTTP_409_CONFLICT, "Se alcanzó el límite diario de este producto.")

    wallet = wallet_service.get_or_create_wallet(db, user)
    wallet = db.scalar(select(Wallet).where(Wallet.id == wallet.id).with_for_update()) if False else wallet
    if wallet.balance < product.price:
        raise HTTPException(status.HTTP_409_CONFLICT, "Saldo insuficiente para completar la compra.")

    # Débito atómico + registro de compra
    tx = WalletTransaction(
        reference=wallet_service.generate_reference("CMP"),
        type=WalletTxType.COMPRA.value,
        amount=product.price,
        status="COMPLETADA",
        reason=f"Compra: {product.name}",
        author_id=user.id,
        counterparty_id=user.id,
    )
    db.add(tx)
    db.flush()

    entry = wallet_service._apply_entry(db, wallet, -product.price)
    entry.transaction_id = tx.id
    db.add(entry)

    pur = Purchase(
        user_id=user.id,
        product_id=product.id,
        product_name=product.name,
        price_paid=product.price,
        house_id=user.house_id,
        status=PurchaseStatus.PENDIENTE_ACTIVACION.value,
        conditions_snapshot=product.conditions,
        idempotency_key=idempotency_key,
        purchased_at=now_utc(),
    )
    db.add(pur)
    db.flush()

    tx.purchase_id = pur.id
    if product.stock is not None:
        product.stock -= 1

    act = ProductActivation(
        purchase_id=pur.id, user_id=user.id, status=ActivationStatus.PENDIENTE.value,
    )
    db.add(act)
    db.flush()
    db.add(ActivationHistory(activation_id=act.id, from_status=None,
                             to_status=ActivationStatus.PENDIENTE.value,
                             reason="Compra registrada", author_id=user.id))

    notify(db, user.id, "TIENDA", "Compra registrada",
           f"Compraste «{product.name}» por {product.price} Lunarias. Queda pendiente de activación.", link="/shop")
    db.commit()
    db.refresh(pur)
    return pur


# ---------------------------------------------------------------------------
# Reembolsos
# ---------------------------------------------------------------------------
def request_refund(db: Session, user: User, purchase_id: int, reason: str) -> Refund:
    pur = db.get(Purchase, purchase_id)
    if pur is None or pur.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compra inexistente.")
    if pur.status in (PurchaseStatus.REEMBOLSADO.value, PurchaseStatus.CANCELADO.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "La compra ya fue reembolsada o cancelada.")
    # No se puede reembolsar un producto utilizado (activado)
    if pur.status == PurchaseStatus.ACTIVADO.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede reembolsar un producto ya utilizado/activado.")

    deadline = ensure_utc(pur.purchased_at) + timedelta(days=settings.refund_window_days)
    if now_utc() > deadline:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"El plazo de {settings.refund_window_days} días para reembolso venció.")

    existing = db.scalar(select(Refund).where(
        Refund.purchase_id == pur.id, Refund.status.in_([RefundStatus.SOLICITADO.value, RefundStatus.APROBADO.value])
    ))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una solicitud de reembolso en curso.")

    refund = Refund(purchase_id=pur.id, requested_by=user.id, amount=pur.price_paid,
                    reason=reason, status=RefundStatus.SOLICITADO.value)
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


def resolve_refund(db: Session, admin: User, refund_id: int, approve: bool, reason: str | None = None) -> Refund:
    refund = db.get(Refund, refund_id)
    if refund is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reembolso inexistente.")
    if refund.status != RefundStatus.SOLICITADO.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "La solicitud ya fue resuelta.")

    pur = db.get(Purchase, refund.purchase_id)
    if approve:
        buyer = db.get(User, refund.requested_by)
        tx = wallet_service.credit_refund(db, admin, buyer, refund.amount,
                                          reason or "Reembolso aprobado",
                                          purchase_id=pur.id, refund_id=refund.id)
        refund.status = RefundStatus.PROCESADO.value
        refund.transaction_id = tx.id
        pur.status = PurchaseStatus.REEMBOLSADO.value
        act = db.scalar(select(ProductActivation).where(ProductActivation.purchase_id == pur.id))
        if act:
            db.add(ActivationHistory(activation_id=act.id, from_status=act.status,
                                     to_status=ActivationStatus.REEMBOLSADO.value,
                                     reason=reason or "Reembolso aprobado", author_id=admin.id))
            act.status = ActivationStatus.REEMBOLSADO.value
        notify(db, refund.requested_by, "TIENDA", "Reembolso aprobado",
               f"Se acreditó el reembolso de {refund.amount} Lunarias por «{pur.product_name}».", link="/shop")
    else:
        refund.status = RefundStatus.RECHAZADO.value
        notify(db, refund.requested_by, "TIENDA", "Reembolso rechazado",
               f"Tu solicitud de reembolso por «{pur.product_name}» fue rechazada.", link="/shop")

    refund.processed_by = admin.id
    refund.processed_at = now_utc()
    db.commit()
    db.refresh(refund)
    return refund


# ---------------------------------------------------------------------------
# Activaciones
# ---------------------------------------------------------------------------
def update_activation(db: Session, actor: User, activation_id: int, new_status: str,
                      reason: str | None = None, event_id: int | None = None) -> ProductActivation:
    act = db.get(ProductActivation, activation_id)
    if act is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activación inexistente.")
    valid = {s.value for s in ActivationStatus}
    if new_status not in valid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Estado de activación inválido.")

    # Validación de ventana previa al evento (máx 15 min antes)
    if new_status == ActivationStatus.ACTIVADO.value and event_id:
        ev = db.get(Event, event_id)
        if ev and ev.scheduled_at:
            limit = ensure_utc(ev.scheduled_at) - timedelta(minutes=settings.activation_before_event_minutes)
            if now_utc() > limit:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    "No se puede activar retroactivamente: debe hacerse hasta 15 min antes del inicio.",
                )

    # Límite diario de activaciones por Casa
    if new_status == ActivationStatus.ACTIVADO.value and act.status != ActivationStatus.ACTIVADO.value:
        pur = db.get(Purchase, act.purchase_id)
        used = house_daily_activation_count(db, pur.house_id, actor.timezone)
        if used >= settings.shop_daily_activation_limit:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"La Casa alcanzó el límite de {settings.shop_daily_activation_limit} activaciones diarias.",
            )

    prev = act.status
    act.status = new_status
    act.reason = reason
    if event_id:
        act.event_id = event_id
    act.handled_by = actor.id
    act.handled_at = now_utc()
    db.add(ActivationHistory(activation_id=act.id, from_status=prev, to_status=new_status,
                             reason=reason, author_id=actor.id))

    pur = db.get(Purchase, act.purchase_id)
    if new_status == ActivationStatus.ACTIVADO.value:
        pur.status = PurchaseStatus.ACTIVADO.value
        notify(db, pur.user_id, "TIENDA", "Producto activado",
               f"«{pur.product_name}» fue activado.", link="/shop")
    elif new_status == ActivationStatus.RECHAZADO.value:
        pur.status = PurchaseStatus.RECHAZADO.value
        notify(db, pur.user_id, "TIENDA", "Activación rechazada",
               f"La activación de «{pur.product_name}» fue rechazada.", link="/shop")
    elif new_status == ActivationStatus.CANCELADO.value:
        pur.status = PurchaseStatus.CANCELADO.value
    db.commit()
    db.refresh(act)
    return act
