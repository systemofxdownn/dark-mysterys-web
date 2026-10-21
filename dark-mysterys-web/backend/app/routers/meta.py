"""Metadatos públicos: Casas, reglas y zonas horarias (adaptación por país)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import House, RoleDef
from ..schemas import serialize_house

router = APIRouter(prefix="/api/meta", tags=["meta"])

# Zonas horarias por país (adaptación por país de origen del usuario).
TIMEZONES = [
    {"group": "Argentina", "options": [
        {"value": "America/Argentina/Buenos_Aires", "label": "Buenos Aires (UTC-3)"},
        {"value": "America/Argentina/Cordoba", "label": "Córdoba (UTC-3)"},
        {"value": "America/Argentina/Mendoza", "label": "Mendoza (UTC-3)"},
        {"value": "America/Argentina/Salta", "label": "Salta (UTC-3)"},
        {"value": "America/Argentina/Ushuaia", "label": "Ushuaia (UTC-3)"},
    ]},
    {"group": "América", "options": [
        {"value": "America/Santiago", "label": "Chile"},
        {"value": "America/Montevideo", "label": "Uruguay"},
        {"value": "America/Asuncion", "label": "Paraguay"},
        {"value": "America/Sao_Paulo", "label": "Brasil (São Paulo)"},
        {"value": "America/Bogota", "label": "Colombia"},
        {"value": "America/Lima", "label": "Perú"},
        {"value": "America/Caracas", "label": "Venezuela"},
        {"value": "America/Mexico_City", "label": "México"},
        {"value": "America/New_York", "label": "EE.UU. Este"},
        {"value": "America/Chicago", "label": "EE.UU. Centro"},
        {"value": "America/Denver", "label": "EE.UU. Montaña"},
        {"value": "America/Los_Angeles", "label": "EE.UU. Pacífico"},
    ]},
    {"group": "Europa", "options": [
        {"value": "Europe/Madrid", "label": "España"},
        {"value": "Europe/Lisbon", "label": "Portugal"},
        {"value": "Europe/Paris", "label": "Francia"},
        {"value": "Europe/Berlin", "label": "Alemania"},
        {"value": "Europe/Rome", "label": "Italia"},
        {"value": "Europe/London", "label": "Reino Unido"},
    ]},
    {"group": "Otros", "options": [
        {"value": "UTC", "label": "UTC"},
    ]},
]


@router.get("/houses")
def houses(db: Session = Depends(get_db)):
    rows = db.scalars(select(House).order_by(House.id)).all()
    return [serialize_house(h) for h in rows]


@router.get("/roles")
def roles(db: Session = Depends(get_db)):
    rows = db.scalars(select(RoleDef).order_by(RoleDef.id)).all()
    return [{"code": r.code, "name": r.name, "description": r.description} for r in rows]


@router.get("/timezones")
def timezones():
    return {"default": settings.default_timezone, "groups": TIMEZONES}


@router.get("/rules")
def rules():
    """Reglas visibles para el usuario (transparencia)."""
    return {
        "default_timezone": settings.default_timezone,
        "podium_points": {"1": 6000, "2": 5000, "3": 4000, "participacion": 1500},
        "group_challenge_points": {"1": 40000, "2": 30000, "3": 20000},
        "individual_challenge_points": 16000,
        "cancellation_compensation": 7500,
        "shop": {
            "days": "lunes a viernes",
            "opens": f"{settings.shop_open_offset_minutes} min después de la primera dinámica",
            "closes": f"{settings.shop_close_offset_minutes} min después de la última dinámica",
            "daily_purchase_limit": settings.shop_daily_purchase_limit,
            "daily_activation_limit": settings.shop_daily_activation_limit,
            "activation_before_event_minutes": settings.activation_before_event_minutes,
            "refund_window_days": settings.refund_window_days,
        },
        "partis": {
            "dinamica": "4 rondas = 1 parti; más de 4 o completar = 2 partis; menos de 4 = 0",
            "reto_grupal": "1 parti adicional por colaborador",
            "reto_individual": "1 parti por entrega válida",
            "flash_sticker": "1 parti para el primero en responder",
        },
    }
