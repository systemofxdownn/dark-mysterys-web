"""Tienda: catálogo, compras, límites, reembolsos y activaciones manuales."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import audit, get_client_ip, get_current_user, require_permission
from ..enums import Role
from ..models import Product, ProductActivation, Purchase, Refund, User
from ..permissions import Perm
from ..schemas import (
    ActivationUpdateIn,
    ProductIn,
    PurchaseIn,
    RefundRequestIn,
    RefundResolveIn,
    serialize_activation,
    serialize_product,
    serialize_purchase,
)
from ..services import shop_service

router = APIRouter(prefix="/api/shop", tags=["shop"])


# ------------------------------ Catálogo ------------------------------
@router.get("/products")
def list_products(all: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Product)
    if not (all and user.role == Role.ADMINISTRADOR.value):
        stmt = stmt.where(Product.published.is_(True))
    return [serialize_product(p) for p in db.scalars(stmt.order_by(Product.id)).all()]


@router.post("/products", status_code=201)
def create_product(data: ProductIn, admin: User = Depends(require_permission(Perm.SHOP_MANAGE)),
                   db: Session = Depends(get_db)):
    p = Product(**data.model_dump())
    db.add(p)
    audit(db, admin, "PRODUCTO_CREADO", "product", None, after=data.model_dump())
    db.commit()
    db.refresh(p)
    return serialize_product(p)


@router.patch("/products/{product_id}")
def update_product(product_id: int, data: ProductIn,
                   admin: User = Depends(require_permission(Perm.SHOP_MANAGE)),
                   db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto inexistente.")
    before = serialize_product(p)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    audit(db, admin, "PRODUCTO_ACTUALIZADO", "product", p.id, before=before, after=data.model_dump())
    db.commit()
    db.refresh(p)
    return serialize_product(p)


@router.post("/products/{product_id}/toggle")
def toggle_product(product_id: int, admin: User = Depends(require_permission(Perm.SHOP_MANAGE)),
                   db: Session = Depends(get_db)):
    p = db.get(Product, product_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Producto inexistente.")
    p.published = not p.published
    audit(db, admin, "PRODUCTO_PUBLICACION", "product", p.id, after={"published": p.published})
    db.commit()
    return serialize_product(p)


# ------------------------------ Horario y límites ------------------------------
@router.get("/hours")
def hours(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return shop_service.shop_hours(db, user.timezone)


@router.get("/limits")
def limits(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {
        "purchases_today": shop_service.house_daily_purchase_count(db, user.house_id, user.timezone),
        "purchase_limit": shop_service.settings.shop_daily_purchase_limit,
        "activations_today": shop_service.house_daily_activation_count(db, user.house_id, user.timezone),
        "activation_limit": shop_service.settings.shop_daily_activation_limit,
    }


# ------------------------------ Compras ------------------------------
@router.post("/purchase", status_code=201)
def purchase(data: PurchaseIn, request: Request, user: User = Depends(require_permission(Perm.SHOP_BUY)),
             db: Session = Depends(get_db)):
    pur = shop_service.purchase(db, user, data.product_id, data.idempotency_key)
    audit(db, user, "COMPRA", "purchase", pur.id,
          after={"product": pur.product_name, "price": pur.price_paid}, ip=get_client_ip(request))
    db.commit()
    return serialize_purchase(pur)


@router.get("/purchases")
def list_purchases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.ADMINISTRADOR.value:
        purs = db.scalars(select(Purchase).order_by(Purchase.purchased_at.desc()).limit(300)).all()
    else:
        purs = db.scalars(select(Purchase).where(Purchase.user_id == user.id)
                          .order_by(Purchase.purchased_at.desc())).all()
    return [serialize_purchase(p) for p in purs]


# ------------------------------ Reembolsos ------------------------------
@router.post("/refunds", status_code=201)
def request_refund(data: RefundRequestIn, user: User = Depends(require_permission(Perm.SHOP_REFUND_REQUEST)),
                   db: Session = Depends(get_db)):
    refund = shop_service.request_refund(db, user, data.purchase_id, data.reason)
    audit(db, user, "REEMBOLSO_SOLICITADO", "refund", refund.id, after={"purchase_id": data.purchase_id})
    db.commit()
    return {"id": refund.id, "status": refund.status, "amount": refund.amount,
            "purchase_id": refund.purchase_id}


@router.get("/refunds")
def list_refunds(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role == Role.ADMINISTRADOR.value:
        rows = db.scalars(select(Refund).order_by(Refund.created_at.desc()).limit(300)).all()
    else:
        rows = db.scalars(select(Refund).where(Refund.requested_by == user.id)
                          .order_by(Refund.created_at.desc())).all()
    return [{"id": r.id, "purchase_id": r.purchase_id, "requested_by": r.requested_by,
             "amount": r.amount, "reason": r.reason, "status": r.status,
             "processed_by": r.processed_by, "transaction_id": r.transaction_id} for r in rows]


@router.post("/refunds/{refund_id}/resolve")
def resolve_refund(refund_id: int, data: RefundResolveIn,
                   admin: User = Depends(require_permission(Perm.SHOP_REFUND_APPROVE)),
                   db: Session = Depends(get_db)):
    refund = shop_service.resolve_refund(db, admin, refund_id, data.approve, data.reason)
    audit(db, admin, "REEMBOLSO_RESUELTO", "refund", refund.id, after={"approved": data.approve})
    db.commit()
    return {"id": refund.id, "status": refund.status, "transaction_id": refund.transaction_id}


# ------------------------------ Activaciones ------------------------------
@router.get("/activations")
def list_activations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(ProductActivation, Purchase)
    if user.role != Role.ADMINISTRADOR.value:
        stmt = stmt.where(ProductActivation.user_id == user.id)
    stmt = stmt.join(Purchase, Purchase.id == ProductActivation.purchase_id)
    rows = db.execute(stmt.order_by(ProductActivation.created_at.desc()).limit(300)).all()
    out = []
    for a, p in rows:
        data = serialize_activation(a)
        data["product_name"] = p.product_name
        data["house_id"] = p.house_id
        out.append(data)
    return out


@router.post("/activations/{activation_id}")
def update_activation(activation_id: int, data: ActivationUpdateIn,
                      admin: User = Depends(require_permission(Perm.SHOP_ACTIVATIONS_MANAGE)),
                      db: Session = Depends(get_db)):
    act = shop_service.update_activation(db, admin, activation_id, data.status, data.reason, data.event_id)
    audit(db, admin, "ACTIVACION_ACTUALIZADA", "activation", act.id,
          after={"status": data.status, "reason": data.reason})
    db.commit()
    return serialize_activation(act)
