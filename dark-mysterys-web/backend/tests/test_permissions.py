"""Pruebas de la matriz de permisos (RBAC) aplicada en el backend."""
from __future__ import annotations


def test_student_cannot_view_scoreboard(client, student_token, auth):
    r = client.get("/api/points/scoreboard", headers=auth(student_token))
    assert r.status_code == 403


def test_student_cannot_create_users(client, student_token, auth):
    r = client.post("/api/users", headers=auth(student_token),
                    json={"display_name": "Hacker", "house_id": 1, "role": "ESTUDIANTE"})
    assert r.status_code == 403


def test_banker_cannot_access_points(client, banker_token, auth):
    assert client.get("/api/points/scoreboard", headers=auth(banker_token)).status_code == 403
    assert client.get("/api/points/ledger", headers=auth(banker_token)).status_code == 403


def test_leader_cannot_manage_points(client, corvus_leader_token, auth):
    # Cargar/confirmar puntos es potestad de Dirección
    r = client.post("/api/points/compensation", headers=auth(corvus_leader_token),
                    json={"house_id": 1, "reason": "no permitido"})
    assert r.status_code == 403


def test_leader_can_view_scoreboard(client, corvus_leader_token, auth):
    # Los jefes ven las 3 Casas
    r = client.get("/api/points/scoreboard", headers=auth(corvus_leader_token))
    assert r.status_code == 200
    assert len(r.json()["houses"]) == 3


def test_only_admin_views_audit(client, student_token, banker_token, corvus_leader_token, admin_token, auth):
    assert client.get("/api/audit", headers=auth(student_token)).status_code == 403
    assert client.get("/api/audit", headers=auth(banker_token)).status_code == 403
    assert client.get("/api/audit", headers=auth(corvus_leader_token)).status_code == 403
    assert client.get("/api/audit", headers=auth(admin_token)).status_code == 200


def test_only_admin_manages_config(client, student_token, banker_token, admin_token, auth):
    assert client.get("/api/config", headers=auth(student_token)).status_code == 403
    assert client.get("/api/config", headers=auth(banker_token)).status_code == 403
    assert client.get("/api/config", headers=auth(admin_token)).status_code == 200


def test_banker_cannot_manage_shop_catalog(client, banker_token, auth):
    r = client.post("/api/shop/products", headers=auth(banker_token),
                    json={"name": "X", "price": 1, "published": True})
    assert r.status_code == 403


def test_banker_cannot_approve_large_adjustment(client, banker_token, auth):
    # Solo Dirección aprueba ajustes grandes
    assert client.get("/api/wallet/approvals", headers=auth(banker_token)).status_code == 403


def test_student_cannot_deposit(client, student_token, auth):
    r = client.post("/api/wallet/deposit", headers=auth(student_token),
                    json={"user_id": 1, "amount": 100, "reason": "no"})
    assert r.status_code == 403


def test_private_endpoints_require_token(client):
    for path in ["/api/auth/me", "/api/wallet/me", "/api/shop/products",
                 "/api/events", "/api/notifications", "/api/users"]:
        assert client.get(path).status_code == 401, path


def test_leader_sees_only_own_house_users(client, corvus_leader_token, auth):
    r = client.get("/api/users", headers=auth(corvus_leader_token))
    assert r.status_code == 200
    houses = {u["house_id"] for u in r.json()}
    assert houses == {1}  # solo Corvus
