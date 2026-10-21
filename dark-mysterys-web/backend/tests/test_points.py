"""Pruebas de la Copa: podio, retos, rectificación, compensación, sanciones y partis."""
from __future__ import annotations

from app.models import User


def _score(client, token, auth) -> dict:
    data = client.get("/api/points/scoreboard", headers=auth(token)).json()["houses"]
    return {h["house_id"]: h["points"] for h in data}


def _uid(db, identifier: str) -> int:
    return db.query(User).filter(User.identifier == identifier).first().id


def test_dinamica_podium_three_houses(client, admin_token, auth, db):
    before = _score(client, admin_token, auth)
    payload = {
        "name": "Dinámica de prueba 3 casas", "type": "DINAMICA", "rounds_played": 4,
        "participants": [
            {"house_id": 1, "arrival_order": 1, "display_name": "A"},
            {"house_id": 2, "arrival_order": 2, "display_name": "B"},
            {"house_id": 3, "arrival_order": 3, "display_name": "C"},
        ],
    }
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    r = client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    assert r.status_code == 200
    totals = r.json()["house_totals"]
    assert totals["1"] == 6000 and totals["2"] == 5000 and totals["3"] == 4000
    after = _score(client, admin_token, auth)
    assert after[1] - before.get(1, 0) == 6000
    assert after[2] - before.get(2, 0) == 5000
    assert after[3] - before.get(3, 0) == 4000


def test_dinamica_one_per_house_shift(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    payload = {
        "name": "Dinámica con repetición de Casa", "type": "DINAMICA", "rounds_played": 4,
        "participants": [
            {"house_id": 1, "arrival_order": 1, "display_name": "A1"},
            {"house_id": 1, "arrival_order": 2, "display_name": "A2"},
            {"house_id": 2, "arrival_order": 3, "display_name": "B1"},
            {"house_id": 3, "arrival_order": 4, "display_name": "C1"},
        ],
    }
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    r = client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    totals = r.json()["house_totals"]
    # Casa 1: 6000 (1º) + 1500 (repetida) = 7500; Casa 2: 5000; Casa 3: 4000
    assert totals["1"] == 7500
    assert totals["2"] == 5000
    assert totals["3"] == 4000


def test_dinamica_two_house_exception(client, admin_token, auth):
    payload = {
        "name": "Dinámica solo dos Casas", "type": "DINAMICA", "rounds_played": 4,
        "participants": [
            {"house_id": 1, "arrival_order": 1, "display_name": "A1"},
            {"house_id": 1, "arrival_order": 2, "display_name": "A2"},
            {"house_id": 2, "arrival_order": 3, "display_name": "B1"},
        ],
    }
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    r = client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    assert r.json()["used_two_house_exception"] is True
    totals = r.json()["house_totals"]
    assert totals["1"] == 11000  # 6000 + 5000
    assert totals["2"] == 4000


def test_dinamica_double_points(client, admin_token, auth):
    payload = {
        "name": "Dinámica doble", "type": "DINAMICA", "rounds_played": 4, "double_points": True,
        "participants": [
            {"house_id": 1, "arrival_order": 1, "display_name": "A"},
            {"house_id": 2, "arrival_order": 2, "display_name": "B"},
            {"house_id": 3, "arrival_order": 3, "display_name": "C"},
        ],
    }
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    r = client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    totals = r.json()["house_totals"]
    assert totals["1"] == 12000 and totals["2"] == 10000 and totals["3"] == 8000


def test_confirm_twice_is_rejected(client, admin_token, auth):
    payload = {"name": "Dinámica única", "type": "DINAMICA", "rounds_played": 4,
               "participants": [{"house_id": 1, "arrival_order": 1, "display_name": "A"}]}
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    r2 = client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    assert r2.status_code == 409


def test_rectify_reverses_points(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    payload = {"name": "Dinámica a rectificar", "type": "DINAMICA", "rounds_played": 4,
               "participants": [{"house_id": 1, "arrival_order": 1, "display_name": "A"}]}
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    mid = _score(client, admin_token, auth)
    assert mid[1] - before.get(1, 0) == 6000
    # Rectificar -> revierte
    r = client.post(f"/api/events/{ev['id']}/rectify", headers=auth(admin_token),
                    params={"reason": "error de carga"})
    assert r.status_code == 200
    after = _score(client, admin_token, auth)
    assert after[1] == before.get(1, 0)


def test_group_challenge(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    r = client.post("/api/events/group-challenge", headers=auth(admin_token),
                    json={"name": "Reto grupal", "ranking": [1, 2, 3]})
    assert r.status_code == 201
    totals = r.json()["house_totals"]
    assert totals["1"] == 40000 and totals["2"] == 30000 and totals["3"] == 20000
    after = _score(client, admin_token, auth)
    assert after[1] - before.get(1, 0) == 40000


def test_individual_challenge(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    r = client.post("/api/events/individual-challenge", headers=auth(admin_token),
                    json={"name": "Reto individual", "house_id": 1,
                          "participants": [
                              {"house_id": 1, "arrival_order": 1, "answer_text": "respuesta 1"},
                              {"house_id": 1, "arrival_order": 2, "answer_text": "respuesta 2"},
                          ]})
    assert r.status_code == 201
    assert r.json()["house_totals"]["1"] == 32000
    after = _score(client, admin_token, auth)
    assert after[1] - before.get(1, 0) == 32000


def test_compensation(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    r = client.post("/api/points/compensation", headers=auth(admin_token),
                    json={"house_id": 1, "reason": "dinámica cancelada"})
    assert r.status_code == 200
    after = _score(client, admin_token, auth)
    assert after[1] - before.get(1, 0) == 7500


def test_admin_sanction_points(client, admin_token, auth):
    before = _score(client, admin_token, auth)
    r = client.post("/api/points/sanction", headers=auth(admin_token),
                    json={"target_house_id": 1, "resource": "PUNTOS", "amount": 1000,
                          "reason": "sanción de prueba"})
    assert r.status_code == 200
    after = _score(client, admin_token, auth)
    assert after[1] - before.get(1, 0) == -1000


def test_leader_sanction_own_house_only(client, corvus_leader_token, auth, db):
    corvus_user = _uid(db, "MC03")
    aegis_user = _uid(db, "JA03")
    # Propia Casa: permitido
    r1 = client.post("/api/points/sanction", headers=auth(corvus_leader_token),
                     json={"target_user_id": corvus_user, "resource": "PUNTOS", "amount": 100,
                           "reason": "propia casa"})
    assert r1.status_code == 200
    # Otra Casa: prohibido
    r2 = client.post("/api/points/sanction", headers=auth(corvus_leader_token),
                     json={"target_user_id": aegis_user, "resource": "PUNTOS", "amount": 100,
                           "reason": "otra casa"})
    assert r2.status_code == 403


def test_points_reconcile_consistent(client, admin_token, auth):
    r = client.get("/api/points/reconcile", headers=auth(admin_token))
    assert r.status_code == 200
    assert r.json()["consistent"] is True


def test_partis_awarded_on_dinamica(client, admin_token, auth, db):
    uid = _uid(db, "MC03")
    payload = {"name": "Dinámica con partis", "type": "DINAMICA", "rounds_played": 4,
               "participants": [{"user_id": uid, "house_id": 1, "arrival_order": 1,
                                 "display_name": "María"}]}
    ev = client.post("/api/events", headers=auth(admin_token), json=payload).json()
    client.post(f"/api/events/{ev['id']}/confirm", headers=auth(admin_token))
    summary = client.get("/api/partis/summary", headers=auth(admin_token)).json()
    row = next(x for x in summary if x["user_id"] == uid)
    assert row["partis"] >= 1


def test_manual_partis(client, admin_token, auth, db):
    uid = _uid(db, "MC04")
    r = client.post("/api/partis", headers=auth(admin_token),
                    json={"user_id": uid, "partis": 2, "reason": "carga manual"})
    assert r.status_code == 201
    assert r.json()["partis"] == 2
