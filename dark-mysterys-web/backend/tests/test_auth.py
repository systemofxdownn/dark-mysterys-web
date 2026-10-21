"""Pruebas de autenticación, cuentas e identificadores."""
from __future__ import annotations

from app.enums import Role
from tests.conftest import DEMO_PASSWORD, make_active_user


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_ok(client):
    r = client.post("/api/auth/login", json={"identifier": "DN01", "password": DEMO_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["user"]["identifier"] == "DN01"
    assert "permissions" in body


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"identifier": "DN01", "password": "incorrecta"})
    assert r.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client, admin_token, auth):
    r = client.get("/api/auth/me", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["user"]["role"] == Role.ADMINISTRADOR.value


def test_create_user_independent_numbering_per_house(client, admin_token, auth, db):
    from app.models import House
    corvus = db.query(House).filter(House.code == "CORVUS").first()
    umbra = db.query(House).filter(House.code == "UMBRA").first()
    c_next = corvus.counter + 1
    u_next = umbra.counter + 1
    # Dos en Corvus (misma serie, incrementa) y uno en Umbra (serie independiente)
    r1 = client.post("/api/users", headers=auth(admin_token),
                     json={"display_name": "Zoe", "house_id": 1, "role": "ESTUDIANTE"})
    r2 = client.post("/api/users", headers=auth(admin_token),
                     json={"display_name": "Zara", "house_id": 1, "role": "ESTUDIANTE"})
    r3 = client.post("/api/users", headers=auth(admin_token),
                     json={"display_name": "Uma", "house_id": 3, "role": "ESTUDIANTE"})
    assert r1.status_code == 201 and r2.status_code == 201 and r3.status_code == 201
    id1 = r1.json()["user"]["identifier"]
    id2 = r2.json()["user"]["identifier"]
    id3 = r3.json()["user"]["identifier"]
    assert id1 == f"ZC{c_next:02d}"        # Corvus usa su propio contador
    assert id2 == f"ZC{c_next + 1:02d}"    # Corvus incrementa su serie
    assert id3 == f"UU{u_next:02d}"        # Umbra tiene su serie independiente
    assert len({id1, id2, id3}) == 3


def test_identifier_unique_and_never_reused(client, admin_token, auth, db):
    r = client.post("/api/users", headers=auth(admin_token),
                    json={"display_name": "Zoe", "house_id": 1, "role": "ESTUDIANTE"})
    ident = r.json()["user"]["identifier"]
    r2 = client.post("/api/users", headers=auth(admin_token),
                     json={"display_name": "Zafiro", "house_id": 1, "role": "ESTUDIANTE"})
    ident2 = r2.json()["user"]["identifier"]
    assert ident != ident2


def test_invitation_first_access_single_use(client, admin_token, auth):
    r = client.post("/api/users", headers=auth(admin_token),
                    json={"display_name": "Nova", "house_id": 2, "role": "ESTUDIANTE"})
    token = r.json()["invitation_token"]
    # Primer acceso: define contraseña + email
    r2 = client.post("/api/auth/first-access", json={
        "token": token, "password": "NuevaClave123", "email": "nova@example.com",
    })
    assert r2.status_code == 200
    assert r2.json()["user"]["status"] == "ACTIVA"
    # El token ya no puede reutilizarse
    r3 = client.post("/api/auth/first-access", json={
        "token": token, "password": "OtraClave123", "email": "otra@example.com",
    })
    assert r3.status_code == 400


def test_password_is_hashed(client, db):
    from app.models import User
    u = db.query(User).filter(User.identifier == "DN01").first()
    assert u.password_hash is not None
    assert u.password_hash != DEMO_PASSWORD
    assert u.password_hash.startswith("$2")  # bcrypt


def test_frozen_account_cannot_login(client, admin_token, auth, db):
    user = make_active_user(db, name="Frost", house_id=1, role="ESTUDIANTE")
    # Congelar
    r = client.post(f"/api/users/{user.id}/freeze", headers=auth(admin_token), json={"reason": "prueba"})
    assert r.status_code == 200
    r2 = client.post("/api/auth/login", json={"identifier": user.identifier, "password": DEMO_PASSWORD})
    assert r2.status_code == 403


def test_frozen_account_invalidates_prior_session(client, admin_token, auth, db):
    user = make_active_user(db, name="Glacier", house_id=1, role="ESTUDIANTE")
    # Login previo
    login = client.post("/api/auth/login", json={"identifier": user.identifier, "password": DEMO_PASSWORD})
    old_token = login.json()["access_token"]
    assert client.get("/api/auth/me", headers=auth(old_token)).status_code == 200
    # Congelar -> el token previo debe quedar invalidado
    client.post(f"/api/users/{user.id}/freeze", headers=auth(admin_token), json={"reason": "prueba"})
    assert client.get("/api/auth/me", headers=auth(old_token)).status_code in (401, 403)


def test_timezone_update(client, admin_token, auth):
    r = client.patch("/api/auth/me", headers=auth(admin_token), json={"timezone": "Europe/Madrid"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "Europe/Madrid"
    # restaurar
    client.patch("/api/auth/me", headers=auth(admin_token),
                 json={"timezone": "America/Argentina/Buenos_Aires"})
