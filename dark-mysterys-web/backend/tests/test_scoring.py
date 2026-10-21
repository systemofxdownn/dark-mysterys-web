"""Pruebas unitarias del motor de puntuación (Copa)."""
from __future__ import annotations

from app.services.scoring import (
    compute_dinamica,
    compute_group_challenge,
    compute_individual_challenge,
    compute_partis,
    compensation_amount,
)


def _p(house_id, order, **kw):
    return {"house_id": house_id, "arrival_order": order, **kw}


def test_podium_standard_three_houses():
    participants = [_p(1, 1), _p(2, 2), _p(3, 3), _p(1, 4), _p(2, 5)]
    r = compute_dinamica(participants)
    by_order = {p.arrival_order: p for p in r.participants}
    assert by_order[1].points == 6000
    assert by_order[2].points == 5000
    assert by_order[3].points == 4000
    assert by_order[4].points == 1500
    assert by_order[5].points == 1500
    assert r.used_two_house_exception is False


def test_podium_one_per_house_shifts_positions():
    participants = [_p(1, 1), _p(1, 2), _p(2, 3), _p(3, 4)]
    r = compute_dinamica(participants)
    by_order = {p.arrival_order: p for p in r.participants}
    assert by_order[1].points == 6000      # Casa 1, 1º
    assert by_order[2].points == 1500      # Casa 1 repetida -> no podio
    assert by_order[3].points == 5000      # Casa 2 toma el 2º puesto
    assert by_order[4].points == 4000      # Casa 3 toma el 3º puesto


def test_two_house_exception_allows_repeat():
    participants = [_p(1, 1), _p(1, 2), _p(2, 3)]
    r = compute_dinamica(participants)
    by_order = {p.arrival_order: p for p in r.participants}
    assert r.used_two_house_exception is True
    assert by_order[1].points == 6000
    assert by_order[2].points == 5000
    assert by_order[3].points == 4000


def test_double_points_multiplies():
    participants = [_p(1, 1), _p(2, 2), _p(3, 3)]
    r = compute_dinamica(participants, double_points=True)
    by_order = {p.arrival_order: p for p in r.participants}
    assert by_order[1].points == 12000
    assert by_order[2].points == 10000
    assert by_order[3].points == 8000


def test_group_challenge_points():
    totals = compute_group_challenge([1, 2, 3])
    assert totals[1] == 40000
    assert totals[2] == 30000
    assert totals[3] == 20000


def test_individual_challenge_points():
    assert compute_individual_challenge(3, 1)[1] == 3 * 16000
    assert compute_individual_challenge(0, 1) == {}


def test_compensation_amount():
    assert compensation_amount() == 7500


def test_partis_rules():
    assert compute_partis("DINAMICA", 4)["per_participant"] == 1
    assert compute_partis("DINAMICA", 5)["per_participant"] == 2
    assert compute_partis("DINAMICA", 3)["per_participant"] == 0
    assert compute_partis("RETO_GRUPAL", None)["collaborator_partis"] == 1
    assert compute_partis("RETO_INDIVIDUAL", None)["per_valid_delivery"] == 1
    assert compute_partis("FLASH_STICKER", None)["first_responder"] == 1
