"""
Motor de puntuación de la Copa.

Reglas implementadas (ver docs/ARCHITECTURE.md §Puntuación):

DINÁMICA (podio por orden de llegada):
  - 1º efectivo: 6.000 / 2º: 5.000 / 3º: 4.000 / resto: 1.500 c/u.
  - Regla general: máximo UNA persona por Casa en el podio. Si la Casa ya
    tiene representante, el puesto se desplaza a la siguiente Casa elegible.
  - EXCEPCIÓN: si participan SOLO DOS Casas (o una), se permite repetir Casa
    en el podio; se premia el orden de llegada 1,2,3 con 6000/5000/4000.
  - Dinámica de puntos dobles: multiplica por 2.

RETO GRUPAL: puntos a la CASA por orden de llegada (40.000/30.000/20.000).
RETO INDIVIDUAL: 16.000 puntos por entrega válida, sumados al total de la Casa.
COMPENSACIÓN por dinámica no realizada: 7.500 puntos a la Casa afectada.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..enums import (
    CANCELLATION_COMPENSATION,
    GROUP_CHALLENGE_POINTS,
    INDIVIDUAL_CHALLENGE_POINTS,
    PARTICIPATION_POINTS,
    PODIUM_POINTS,
)


@dataclass
class ParticipantScore:
    index: int
    house_id: int | None
    arrival_order: int
    effective_podium: int | None
    points: int


@dataclass
class ScoringResult:
    participants: list[ParticipantScore] = field(default_factory=list)
    house_totals: dict[int, int] = field(default_factory=dict)
    participating_houses: set[int] = field(default_factory=set)
    used_two_house_exception: bool = False


def compute_dinamica(
    participants: list[dict],
    double_points: bool = False,
) -> ScoringResult:
    """
    participants: lista de dicts con al menos {house_id, arrival_order}.
    Devuelve el puntaje por participante y los totales por Casa.
    """
    result = ScoringResult()
    if not participants:
        return result

    # Orden por llegada (estable)
    ordered = sorted(participants, key=lambda p: (p.get("arrival_order") or 0))

    houses = {p.get("house_id") for p in ordered if p.get("house_id") is not None}
    result.participating_houses = set(houses)

    # Excepción: solo dos Casas (o una) participan -> se permite repetir Casa.
    two_house_exception = len(houses) <= 2
    result.used_two_house_exception = two_house_exception

    multiplier = 2 if double_points else 1

    podium_houses: set[int] = set()
    next_slot = 1
    house_totals: dict[int, int] = {}

    for i, p in enumerate(ordered):
        house_id = p.get("house_id")
        podium_slot: int | None = None

        if next_slot <= 3:
            if two_house_exception:
                # Se premia el orden de llegada sin restricción de Casa
                podium_slot = next_slot
            elif house_id is not None and house_id not in podium_houses:
                podium_slot = next_slot
            elif house_id is None:
                # Sin Casa definida no ocupa podio
                podium_slot = None

        if podium_slot is not None:
            points = PODIUM_POINTS[podium_slot] * multiplier
            next_slot += 1
            if house_id is not None:
                podium_houses.add(house_id)
        else:
            points = PARTICIPATION_POINTS * multiplier

        ps = ParticipantScore(
            index=i,
            house_id=house_id,
            arrival_order=p.get("arrival_order") or 0,
            effective_podium=podium_slot,
            points=points,
        )
        result.participants.append(ps)
        if house_id is not None:
            house_totals[house_id] = house_totals.get(house_id, 0) + points

    result.house_totals = house_totals
    return result


def compute_group_challenge(ranking: list[int], double_points: bool = False) -> dict[int, int]:
    """ranking: lista de house_id en orden de llegada (1º, 2º, 3º...)."""
    multiplier = 2 if double_points else 1
    totals: dict[int, int] = {}
    for position, house_id in enumerate(ranking, start=1):
        if position in GROUP_CHALLENGE_POINTS and house_id is not None:
            totals[house_id] = totals.get(house_id, 0) + GROUP_CHALLENGE_POINTS[position] * multiplier
    return totals


def compute_individual_challenge(valid_deliveries: int, house_id: int, double_points: bool = False) -> dict[int, int]:
    """16.000 puntos por entrega válida, sumados al total de la Casa."""
    if house_id is None or valid_deliveries <= 0:
        return {}
    multiplier = 2 if double_points else 1
    return {house_id: INDIVIDUAL_CHALLENGE_POINTS * valid_deliveries * multiplier}


def compute_partis(event_type: str, rounds_played: int | None, *, collaborators: int = 0,
                   valid_deliveries: int = 0, first_responder: bool = False) -> dict:
    """
    Calcula partis según el tipo de evento.

    - DINAMICA: 4 rondas -> 1 parti; >4 o completada -> 2 partis; <4 -> 0.
    - RETO_GRUPAL: 1 parti adicional por colaborador.
    - RETO_INDIVIDUAL: 1 parti por entrega válida.
    - FLASH_STICKER: 1 parti para el primero en responder.
    """
    if event_type == "DINAMICA":
        r = rounds_played or 0
        if r >= 5:
            return {"per_participant": 2}
        if r == 4:
            return {"per_participant": 1}
        return {"per_participant": 0}
    if event_type == "RETO_GRUPAL":
        return {"collaborator_partis": 1}
    if event_type == "RETO_INDIVIDUAL":
        return {"per_valid_delivery": 1}
    if event_type == "FLASH_STICKER":
        return {"first_responder": 1}
    return {"per_participant": 0}


def compensation_amount() -> int:
    return CANCELLATION_COMPENSATION
