"""
Datos semilla (idempotente).

Crea: Casas, Roles, Configuración y un conjunto de cuentas DEMO para poder
probar la plataforma de inmediato. En producción, Dirección debe crear las
cuentas reales por invitación y cambiar/eliminar las cuentas demo.

Contraseña demo de todas las cuentas sembradas: DarkMystery2024!
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .enums import AccountStatus, Role
from .models import House, Product, RoleDef, Setting, User
from .security import hash_password
from .services import wallet_service
from .services.timez import now_utc

logger = logging.getLogger("darkmysterys.seed")

DEMO_PASSWORD = "DarkMystery2024!"

HOUSES = [
    dict(code="CORVUS", name="Corvus", virtues="Ambición, Inteligencia e Independencia",
         founder="Aurelian Corvus", founded_year=1706, symbols="Cuervo y serpiente",
         colors="Azul profundo y negro", heart_color="azul", heart_hex="#3B82F6",
         identity="Estrategia, autonomía, conocimiento y anticipación.", is_competing=True),
    dict(code="AEGIS", name="Aegis", virtues="Disciplina, Protección y Compromiso",
         founder="Helios Aegis", founded_year=1698, symbols="Dragón",
         colors="Verde y plata", heart_color="verde", heart_hex="#22C55E",
         identity="Deber, defensa, constancia y estabilidad.", is_competing=True),
    dict(code="UMBRA", name="Umbra", virtues="Astucia, Sigilo y Oscuridad",
         founder="Nyxus Umbrae", founded_year=1712, symbols="Calavera y murciélago",
         colors="Negro y blanco", heart_color="morado", heart_hex="#A855F7",
         identity="Observación, discreción, adaptación y estrategia.", is_competing=True),
    dict(code="NOCTURNA", name="Casa Nocturna", virtues="Autoridad, Responsabilidad y Visión",
         founder="Consejo Original", founded_year=None, symbols="Serpiente",
         colors="Gris lunar", heart_color="gris lunar", heart_hex="#9CA3AF",
         identity="Órgano de gobierno: supervisión, administración, auditoría y resolución de conflictos.",
         is_competing=False),
]

ROLES = [
    (Role.ADMINISTRADOR.value, "Administrador", "Dirección (Casa Nocturna). Acceso global."),
    (Role.JEFE_DE_CASA.value, "Jefe de Casa", "Responsable de su Casa."),
    (Role.SUBJEFE_DE_CASA.value, "Subjefe de Casa", "Co-responsable de su Casa."),
    (Role.BANQUERO.value, "Banquero", "Operaciones ordinarias del banco."),
    (Role.ESTUDIANTE.value, "Estudiante", "Integrante de la comunidad."),
]

DEFAULT_SETTINGS = {
    "large_adjustment_threshold": {"value": settings.large_adjustment_threshold,
                                   "description": "Umbral de Lunarias que exige aprobación de Dirección."},
    "refund_window_days": {"value": settings.refund_window_days,
                           "description": "Plazo de reembolso (días)."},
    "shop_daily_purchase_limit": {"value": settings.shop_daily_purchase_limit,
                                  "description": "Compras diarias máximas por Casa."},
    "shop_daily_activation_limit": {"value": settings.shop_daily_activation_limit,
                                    "description": "Activaciones diarias máximas por Casa."},
    "default_timezone": {"value": settings.default_timezone,
                         "description": "Zona horaria por defecto (Argentina)."},
}

DEMO_PRODUCTS = [
    dict(name="Poción de Doble Filo", description="Duplica los puntos de una dinámica (una vez por día).",
         price=4500, published=True, affects_points=True, requires_approval=True,
         conditions="Válido solo si se anuncia la dinámica doble con antelación.",
         activation_requirements="Activación manual por Dirección hasta 15 min antes.",
         special_rules="Máximo una dinámica doble por día."),
    dict(name="Escudo de Aegis", description="Protege de una penalización de puntos en una dinámica.",
         price=3000, published=True, affects_points=True, requires_approval=True,
         conditions="Uso único.", activation_requirements="Activación manual.",
         special_rules="No aplica a penalizaciones administrativas."),
    dict(name="Velo de Umbra", description="Permite observar sin ser contado en una ronda.",
         price=2500, published=True, affects_points=False, requires_approval=True,
         conditions="No otorga puntos ni partis.", activation_requirements="Activación manual.",
         special_rules="Solo una vez por actividad."),
    dict(name="Gema de Corvus", description="Anticipa el tema de la siguiente dinámica.",
         price=3500, published=True, affects_points=False, requires_approval=True,
         conditions="Información sujeta a disponibilidad.", activation_requirements="Activación manual.",
         special_rules="Sujeto a autorización de Dirección."),
    dict(name="Amuleto de Partis", description="Otorga una parti adicional en una dinámica válida.",
         price=2000, published=True, affects_points=False, requires_approval=True,
         conditions="Requiere haber completado al menos 4 rondas.",
         activation_requirements="Activación manual.", special_rules="Máximo 2 por semana."),
]

DEMO_ACCOUNTS = [
    # (nombre, casa, rol, es_director)
    ("Daniela", "NOCTURNA", Role.ADMINISTRADOR.value, True),
    ("Selene", "NOCTURNA", Role.ADMINISTRADOR.value, True),
    ("Aurelian", "CORVUS", Role.JEFE_DE_CASA.value, False),
    ("Cassia", "CORVUS", Role.SUBJEFE_DE_CASA.value, False),
    ("Helios", "AEGIS", Role.JEFE_DE_CASA.value, False),
    ("Iris", "AEGIS", Role.SUBJEFE_DE_CASA.value, False),
    ("Nyxus", "UMBRA", Role.JEFE_DE_CASA.value, False),
    ("Mora", "UMBRA", Role.SUBJEFE_DE_CASA.value, False),
    ("Bancor", "NOCTURNA", Role.BANQUERO.value, False),
    ("María", "CORVUS", Role.ESTUDIANTE.value, False),
    ("Juan", "AEGIS", Role.ESTUDIANTE.value, False),
    ("Marta", "CORVUS", Role.ESTUDIANTE.value, False),
    ("Pepe", "UMBRA", Role.ESTUDIANTE.value, False),
    ("Lucía", "UMBRA", Role.ESTUDIANTE.value, False),
    ("Tomás", "AEGIS", Role.ESTUDIANTE.value, False),
]


def seed(db: Session) -> dict:
    created = {"houses": 0, "roles": 0, "users": 0, "products": 0, "settings": 0}

    # Casas
    house_by_code: dict[str, House] = {}
    for data in HOUSES:
        h = db.scalar(select(House).where(House.code == data["code"]))
        if not h:
            h = House(**data)
            db.add(h)
            db.flush()
            created["houses"] += 1
        house_by_code[data["code"]] = h

    # Roles
    for code, name, desc in ROLES:
        if not db.scalar(select(RoleDef).where(RoleDef.code == code)):
            db.add(RoleDef(code=code, name=name, description=desc))
            created["roles"] += 1

    # Configuración
    for key, val in DEFAULT_SETTINGS.items():
        if not db.get(Setting, key):
            db.add(Setting(key=key, value=val, description=val.get("description")))
            created["settings"] += 1

    # Productos
    if not db.scalar(select(Product.id)):
        for pdata in DEMO_PRODUCTS:
            db.add(Product(**pdata))
            created["products"] += 1

    # Cuentas demo
    if not db.scalar(select(User.id)):
        pw = hash_password(DEMO_PASSWORD)
        counters: dict[int, int] = {}
        for name, code, role, is_director in DEMO_ACCOUNTS:
            house = house_by_code[code]
            counters[house.id] = counters.get(house.id, 0) + 1
            seq = counters[house.id]
            house.counter = max(house.counter or 0, seq)
            ident = f"{name[0].upper()}{code[0].upper()}{seq:02d}"
            u = User(
                identifier=ident, seq_number=seq, display_name=name,
                email=f"{ident.lower()}@darkmysterys.demo", email_verified=True,
                password_hash=pw, role=role, status=AccountStatus.ACTIVA.value,
                house_id=house.id, timezone=settings.default_timezone,
                is_director=is_director,
            )
            db.add(u)
            db.flush()
            wallet_service.get_or_create_wallet(db, u)
            created["users"] += 1

    db.commit()
    logger.info("Seed completado: %s", created)
    return created


def ensure_seed(db: Session) -> dict:
    return seed(db)
