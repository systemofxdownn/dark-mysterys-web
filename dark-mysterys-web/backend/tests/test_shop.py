"""Pruebas de la tienda: compras, límites, reembolsos y activaciones."""
from __future__ import annotations

import uuid

import pytest

from app.models import User
from tests.conftest import DEMO_PASSWORD, make_active_user


def _uid(db, identifier: str) -> int:
    return db.query(User).filter(User.identifier == identifier).first().id


def _fund(client, banker_token, auth, user_id, amount=200000):
    client.post("/api/wallet/deposit", headers=auth(banker_token),
                json={"user_id": user_id, "amount": amount, "reason": "fondeo tienda",
                      "idempotency_key": f"dep-{uuid.uuid4()}"})


def _login(client, identifier):
    return client.post("/api/auth/login",
                       json={"identifier": identifier, "password": DEMO_PASSWORD}).json()["access_token"]


def test_purchase_debits_and_creates_activation(client, banker_token, auth, db):
    uid = _uid(db, "MC03")
    _fund(client, banker_token, auth, uid)
    tok = _login(client, "MC03")
    before = client.get("/api/wallet/me", headers=auth(tok)).json()["balance"]
    r = client.post("/api/shop/purchase", headers=auth(tok),
                    json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"})
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDIENTE_ACTIVACION"
    after = client.get("/api/wallet/me", headers=auth(tok)).json()["balance"]
    assert after == before - body["price_paid"]


def test_purchase_without_balance(client, auth, db):
    user = make_active_user(db, name="Pobre", house_id=2, role="ESTUDIANTE")
    tok = _login(client, user.identifier)
    r = client.post("/api/shop/purchase", headers=auth(tok),
                    json={"product_id": 1, "idempotency_key": f"buy-{uuid.uuid4()}"})
    assert r.status_code == 409


def test_frozen_account_cannot_purchase(client, admin_token, auth, db):
    user = make_active_user(db, name="Helado", house_id=2, role="ESTUDIANTE")
    client.post(f"/api/users/{user.id}/freeze", headers=auth(admin_token), json={"reason": "x"})
    tok = client.post("/api/auth/login", json={"identifier": user.identifier, "password": DEMO_PASSWORD})
    # No puede ni loguearse
    assert tok.status_code == 403


def test_daily_purchase_limit_per_house(client, banker_token, auth, db):
    user = make_active_user(db, name="Limite", house_id=3, role="ESTUDIANTE")
    _fund(client, banker_token, auth, user.id)
    tok = _login(client, user.identifier)
    ok = 0
    for _ in range(8):
        r = client.post("/api/shop/purchase", headers=auth(tok),
                        json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"})
        if r.status_code == 201:
            ok += 1
    assert ok == 8
    r9 = client.post("/api/shop/purchase", headers=auth(tok),
                     json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"})
    assert r9.status_code == 409


def test_daily_activation_limit_per_house(client, banker_token, admin_token, auth, db):
    user = make_active_user(db, name="Activa", house_id=2, role="ESTUDIANTE")
    _fund(client, banker_token, auth, user.id)
    tok = _login(client, user.identifier)
    purchase_ids = []
    for _ in range(5):
        r = client.post("/api/shop/purchase", headers=auth(tok),
                        json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"})
        assert r.status_code == 201
        purchase_ids.append(r.json()["id"])
    # Obtener activaciones del usuario
    acts = client.get("/api/shop/activations", headers=auth(admin_token)).json()
    mine = [a for a in acts if a["user_id"] == user.id]
    activated = 0
    for a in mine[:5]:
        r = client.post(f"/api/shop/activations/{a['id']}", headers=auth(admin_token),
                        json={"status": "ACTIVADO", "reason": "prueba"})
        if r.status_code == 200:
            activated += 1
    assert activated == 4  # límite diario por Casa
    # La 5ª activación debe fallar
    r5 = client.post(f"/api/shop/activations/{mine[4]['id']}", headers=auth(admin_token),
                     json={"status": "ACTIVADO", "reason": "quinta"})
    assert r5.status_code == 409


def test_refund_request_and_approval(client, banker_token, admin_token, auth, db):
    uid = _uid(db, "MC04")
    _fund(client, banker_token, auth, uid)
    tok = _login(client, "MC04")
    pur = client.post("/api/shop/purchase", headers=auth(tok),
                      json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"}).json()
    # Solicitar reembolso (producto no usado)
    r = client.post("/api/shop/refunds", headers=auth(tok),
                    json={"purchase_id": pur["id"], "reason": "no lo usé"})
    assert r.status_code == 201
    refund_id = r.json()["id"]
    bal_before = client.get("/api/wallet/me", headers=auth(tok)).json()["balance"]
    # Aprobar
    r2 = client.post(f"/api/shop/refunds/{refund_id}/resolve", headers=auth(admin_token),
                     json={"approve": True, "reason": "ok"})
    assert r2.status_code == 200
    bal_after = client.get("/api/wallet/me", headers=auth(tok)).json()["balance"]
    assert bal_after == bal_before + pur["price_paid"]


def test_refund_rejected_if_used(client, banker_token, admin_token, auth, db):
    uid = _uid(db, "MC04")
    _fund(client, banker_token, auth, uid)
    tok = _login(client, "MC04")
    pur = client.post("/api/shop/purchase", headers=auth(tok),
                      json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"}).json()
    # Activar (usar) el producto
    acts = client.get("/api/shop/activations", headers=auth(admin_token)).json()
    act = next(a for a in acts if a["purchase_id"] == pur["id"])
    client.post(f"/api/shop/activations/{act['id']}", headers=auth(admin_token),
                json={"status": "ACTIVADO", "reason": "usado"})
    # Intentar reembolsar un producto usado -> rechazado
    r = client.post("/api/shop/refunds", headers=auth(tok),
                    json={"purchase_id": pur["id"], "reason": "ya usado"})
    assert r.status_code == 409


def test_catalog_configurable(client, admin_token, auth):
    r = client.post("/api/shop/products", headers=auth(admin_token),
                    json={"name": "Reliquia Nueva", "price": 1234, "published": True})
    assert r.status_code == 201
    pid = r.json()["id"]
    # Editar
    r2 = client.patch(f"/api/shop/products/{pid}", headers=auth(admin_token),
                      json={"name": "Reliquia Nueva", "price": 1500, "published": True})
    assert r2.status_code == 200
    assert r2.json()["price"] == 1500
    # Aparece en el catálogo público
    prods = client.get("/api/shop/products", headers=auth(admin_token)).json()
    assert any(p["id"] == pid for p in prods)


def test_shop_closed_rejects_purchase(client, banker_token, auth, db, monkeypatch):
    from app.services import shop_service
    from app.config import settings
    uid = _uid(db, "MC03")
    _fund(client, banker_token, auth, uid)
    tok = _login(client, "MC03")
    monkeypatch.setattr(settings, "shop_enforce_hours", True)
    monkeypatch.setattr(shop_service, "shop_hours",
                        lambda db_, tz: {"is_open": False, "opens_at": None, "closes_at": None})
    r = client.post("/api/shop/purchase", headers=auth(tok),
                    json={"product_id": 5, "idempotency_key": f"buy-{uuid.uuid4()}"})
    assert r.status_code == 409
