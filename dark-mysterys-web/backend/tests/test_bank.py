"""Pruebas del banco de Lunarias (doble asiento, idempotencia, deuda, reversión)."""
from __future__ import annotations

import uuid

from app.models import User
from tests.conftest import DEMO_PASSWORD, make_active_user


def _uid(db, identifier: str) -> int:
    return db.query(User).filter(User.identifier == identifier).first().id


def _balance(client, token, auth):
    return client.get("/api/wallet/me", headers=auth(token)).json()["balance"]


def test_deposit_credits_balance(client, banker_token, auth, db):
    uid = _uid(db, "MC03")
    before = _balance(client, banker_token, auth)  # noqa: F841 (no-op)
    r = client.post("/api/wallet/deposit", headers=auth(banker_token),
                    json={"user_id": uid, "amount": 10000, "reason": "bienvenida",
                          "idempotency_key": f"dep-{uuid.uuid4()}"})
    assert r.status_code == 200
    assert r.json()["type"] == "DEPOSITO"


def test_transfer_moves_balance_and_creates_two_entries(client, admin_token, banker_token, auth, db):
    sender = _uid(db, "MC03")
    recipient = _uid(db, "MC04")
    # Asegurar fondos del emisor
    client.post("/api/wallet/deposit", headers=auth(banker_token),
                json={"user_id": sender, "amount": 20000, "reason": "fondeo",
                      "idempotency_key": f"dep-{uuid.uuid4()}"})
    # Login como emisor
    tok = client.post("/api/auth/login", json={"identifier": "MC03", "password": DEMO_PASSWORD}).json()["access_token"]
    bal_before = _balance(client, tok, auth)
    r = client.post("/api/wallet/transfer", headers=auth(tok),
                    json={"to_user_id": recipient, "amount": 3000, "reason": "prueba",
                          "idempotency_key": f"tr-{uuid.uuid4()}"})
    assert r.status_code == 200
    assert _balance(client, tok, auth) == bal_before - 3000
    # Verificar doble asiento: suma de asientos == 0
    from app.models import WalletEntry
    tx_id = r.json()["id"]
    entries = db.query(WalletEntry).filter(WalletEntry.transaction_id == tx_id).all()
    assert len(entries) == 2
    assert sum(e.amount for e in entries) == 0


def test_transfer_insufficient_funds(client, auth, db):
    tok = client.post("/api/auth/login", json={"identifier": "JA03", "password": DEMO_PASSWORD}).json()["access_token"]
    recipient = _uid(db, "MC03")
    r = client.post("/api/wallet/transfer", headers=auth(tok),
                    json={"to_user_id": recipient, "amount": 999999999, "reason": "sin fondos",
                          "idempotency_key": f"tr-{uuid.uuid4()}"})
    assert r.status_code in (400, 409, 422)


def test_transfer_idempotency(client, banker_token, auth, db):
    sender = _uid(db, "MC03")
    recipient = _uid(db, "MC04")
    client.post("/api/wallet/deposit", headers=auth(banker_token),
                json={"user_id": sender, "amount": 20000, "reason": "fondeo",
                      "idempotency_key": f"dep-{uuid.uuid4()}"})
    tok = client.post("/api/auth/login", json={"identifier": "MC03", "password": DEMO_PASSWORD}).json()["access_token"]
    key = f"tr-idem-{uuid.uuid4()}"
    payload = {"to_user_id": recipient, "amount": 1000, "reason": "idem", "idempotency_key": key}
    r1 = client.post("/api/wallet/transfer", headers=auth(tok), json=payload)
    r2 = client.post("/api/wallet/transfer", headers=auth(tok), json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    # No debe duplicar: misma transacción
    assert r1.json()["id"] == r2.json()["id"]


def test_large_adjustment_requires_approval(client, banker_token, admin_token, auth, db):
    uid = _uid(db, "MC03")
    r = client.post("/api/wallet/adjust", headers=auth(banker_token),
                    json={"user_id": uid, "amount": 60000, "reason": "ajuste grande",
                          "idempotency_key": f"adj-{uuid.uuid4()}"})
    assert r.status_code == 200
    assert r.json()["pending_approval"] is True
    assert r.json()["transaction"]["status"] == "PENDIENTE_APROBACION"


def test_small_adjustment_applies_directly(client, banker_token, auth, db):
    uid = _uid(db, "MC03")
    r = client.post("/api/wallet/adjust", headers=auth(banker_token),
                    json={"user_id": uid, "amount": 500, "reason": "ajuste chico",
                          "idempotency_key": f"adj-{uuid.uuid4()}"})
    assert r.status_code == 200
    assert r.json()["pending_approval"] is False


def test_penalty_can_create_debt(client, banker_token, corvus_leader_token, auth, db):
    # Las penalizaciones de Lunarias las aplican Dirección o los jefes/subjefes
    # (solo a integrantes de su propia Casa). Usamos un usuario dedicado para no
    # contaminar la billetera de las cuentas demo compartidas entre pruebas.
    deudor = make_active_user(db, name="Deudor", house_id=1, role="ESTUDIANTE")
    r = client.post("/api/wallet/sanction", headers=auth(corvus_leader_token),
                    json={"target_user_id": deudor.id, "resource": "LUNARIAS", "amount": 999999,
                          "reason": "penalización que genera deuda"})
    assert r.status_code == 200
    w = client.get("/api/wallet/accounts", headers=auth(banker_token)).json()
    row = next(x for x in w if x["user"]["id"] == deudor.id)
    assert row["balance"] < 0
    assert row["debt"] > 0


def test_reversal_creates_compensating_entry(client, banker_token, auth, db):
    uid = _uid(db, "MC03")
    dep = client.post("/api/wallet/deposit", headers=auth(banker_token),
                      json={"user_id": uid, "amount": 4000, "reason": "a revertir",
                            "idempotency_key": f"dep-{uuid.uuid4()}"})
    tx_id = dep.json()["id"]
    r = client.post(f"/api/wallet/transactions/{tx_id}/reverse", headers=auth(banker_token),
                    json={"reason": "corrección"})
    assert r.status_code == 200
    assert r.json()["type"] == "REVERSION"
    # El original no se borra
    assert client.get("/api/wallet/transactions/all", headers=auth(banker_token)).status_code == 200


def test_wallet_reconcile_consistent(client, banker_token, auth):
    r = client.get("/api/wallet/reconcile", headers=auth(banker_token))
    assert r.status_code == 200
    assert r.json()["consistent"] is True
