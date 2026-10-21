"""
Matriz de permisos por rol.

La autorización se aplica SIEMPRE en el backend (dependencias FastAPI).
Ocultar un botón en el frontend no es seguridad.

Ver docs/PERMISSIONS.md para la matriz completa.
"""
from __future__ import annotations

from .enums import Role


class Perm:
    # Usuarios / cuentas
    USERS_CREATE = "users:create"
    USERS_MANAGE = "users:manage"            # editar, desactivar, reactivar, baja
    USERS_VIEW_ALL = "users:view_all"
    USERS_VIEW_OWN_HOUSE = "users:view_own_house"
    ROLES_ASSIGN = "roles:assign"
    HOUSES_ASSIGN = "houses:assign"
    ACCOUNTS_FREEZE = "accounts:freeze"

    # Banco
    WALLET_VIEW_OWN = "wallet:view_own"
    WALLET_TRANSFER = "wallet:transfer"
    WALLET_VIEW_ALL = "wallet:view_all"
    WALLET_DEPOSIT = "wallet:deposit"
    WALLET_ADJUST = "wallet:adjust"
    WALLET_APPROVE_LARGE = "wallet:approve_large"

    # Tienda
    SHOP_MANAGE = "shop:manage"              # catálogo
    SHOP_BUY = "shop:buy"
    SHOP_VIEW_OWN = "shop:view_own"
    SHOP_ACTIVATIONS_MANAGE = "shop:activations_manage"
    SHOP_REFUND_REQUEST = "shop:refund_request"
    SHOP_REFUND_APPROVE = "shop:refund_approve"

    # Puntos / Copa
    POINTS_VIEW_ALL = "points:view_all"      # las 3 Casas
    POINTS_MANAGE = "points:manage"          # cargar/confirmar/rectificar
    SANCTIONS_POINTS = "sanctions:points"
    SANCTIONS_LUNARIAS = "sanctions:lunarias"
    SANCTIONS_OWN_HOUSE_ONLY = "sanctions:own_house_only"

    # Eventos / calendario
    EVENTS_MANAGE = "events:manage"
    EVENTS_LOAD_OWN_DAY = "events:load_own_day"
    SCHEDULE_MANAGE = "schedule:manage"
    SCHEDULE_MANAGE_OWN_DAY = "schedule:manage_own_day"

    # Participaciones
    PARTICIPATIONS_VIEW_ALL = "partis:view_all"
    PARTICIPATIONS_VIEW_OWN_HOUSE = "partis:view_own_house"
    PARTICIPATIONS_MANAGE = "partis:manage"

    # Estadísticas / informes
    STATS_VIEW = "stats:view"
    STATS_VIEW_OWN_HOUSE = "stats:view_own_house"
    REPORTS_EXPORT_ALL = "reports:export_all"
    REPORTS_EXPORT_OWN_HOUSE = "reports:export_own_house"
    REPORTS_EXPORT_FINANCIAL = "reports:export_financial"

    # Reclamaciones / auditoría / config
    COMPLAINTS_CREATE = "complaints:create"
    COMPLAINTS_RESOLVE = "complaints:resolve"
    AUDIT_VIEW = "audit:view"
    CONFIG_MANAGE = "config:manage"

    # Perfil
    PROFILE_EDIT = "profile:edit"


_ADMIN = {
    Perm.USERS_CREATE, Perm.USERS_MANAGE, Perm.USERS_VIEW_ALL, Perm.ROLES_ASSIGN,
    Perm.HOUSES_ASSIGN, Perm.ACCOUNTS_FREEZE,
    Perm.WALLET_VIEW_OWN, Perm.WALLET_TRANSFER, Perm.WALLET_VIEW_ALL, Perm.WALLET_DEPOSIT,
    Perm.WALLET_ADJUST, Perm.WALLET_APPROVE_LARGE,
    Perm.SHOP_MANAGE, Perm.SHOP_BUY, Perm.SHOP_VIEW_OWN, Perm.SHOP_ACTIVATIONS_MANAGE,
    Perm.SHOP_REFUND_REQUEST, Perm.SHOP_REFUND_APPROVE,
    Perm.POINTS_VIEW_ALL, Perm.POINTS_MANAGE, Perm.SANCTIONS_POINTS, Perm.SANCTIONS_LUNARIAS,
    Perm.EVENTS_MANAGE, Perm.EVENTS_LOAD_OWN_DAY, Perm.SCHEDULE_MANAGE, Perm.SCHEDULE_MANAGE_OWN_DAY,
    Perm.PARTICIPATIONS_VIEW_ALL, Perm.PARTICIPATIONS_MANAGE,
    Perm.STATS_VIEW, Perm.REPORTS_EXPORT_ALL, Perm.REPORTS_EXPORT_FINANCIAL,
    Perm.COMPLAINTS_CREATE, Perm.COMPLAINTS_RESOLVE, Perm.AUDIT_VIEW, Perm.CONFIG_MANAGE,
    Perm.PROFILE_EDIT,
}

_HOUSE_LEADER = {
    Perm.USERS_VIEW_OWN_HOUSE,
    Perm.WALLET_VIEW_OWN, Perm.WALLET_TRANSFER,
    Perm.SHOP_BUY, Perm.SHOP_VIEW_OWN, Perm.SHOP_REFUND_REQUEST,
    Perm.POINTS_VIEW_ALL,                 # jefes/subjefes ven las 3 Casas
    Perm.SANCTIONS_POINTS, Perm.SANCTIONS_LUNARIAS, Perm.SANCTIONS_OWN_HOUSE_ONLY,
    Perm.EVENTS_LOAD_OWN_DAY, Perm.SCHEDULE_MANAGE_OWN_DAY,
    Perm.PARTICIPATIONS_VIEW_OWN_HOUSE,
    Perm.STATS_VIEW_OWN_HOUSE, Perm.REPORTS_EXPORT_OWN_HOUSE,
    Perm.COMPLAINTS_CREATE, Perm.PROFILE_EDIT,
}

_BANKER = {
    Perm.WALLET_VIEW_OWN, Perm.WALLET_TRANSFER,
    Perm.WALLET_VIEW_ALL, Perm.WALLET_DEPOSIT, Perm.WALLET_ADJUST,
    Perm.SHOP_BUY, Perm.SHOP_VIEW_OWN, Perm.SHOP_REFUND_REQUEST,
    Perm.REPORTS_EXPORT_FINANCIAL,
    Perm.COMPLAINTS_CREATE, Perm.PROFILE_EDIT,
}

_STUDENT = {
    Perm.WALLET_VIEW_OWN, Perm.WALLET_TRANSFER,
    Perm.SHOP_BUY, Perm.SHOP_VIEW_OWN, Perm.SHOP_REFUND_REQUEST,
    Perm.COMPLAINTS_CREATE, Perm.PROFILE_EDIT,
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    Role.ADMINISTRADOR.value: _ADMIN,
    Role.JEFE_DE_CASA.value: _HOUSE_LEADER,
    Role.SUBJEFE_DE_CASA.value: _HOUSE_LEADER,
    Role.BANQUERO.value: _BANKER,
    Role.ESTUDIANTE.value: _STUDENT,
}


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def permissions_for(role: str) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role, set()))


HOUSE_LEADER_ROLES = {Role.JEFE_DE_CASA.value, Role.SUBJEFE_DE_CASA.value}
ADMIN_ROLES = {Role.ADMINISTRADOR.value}
