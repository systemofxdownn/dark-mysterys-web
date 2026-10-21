"""Esquemas Pydantic (validación de entrada) y serializadores de salida."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


def _normalize_utc(v: datetime | None) -> datetime | None:
    """Convierte un datetime *aware* a UTC naive para almacenamiento uniforme.

    El sistema almacena SIEMPRE en UTC. SQLite descarta el tzinfo al guardar, por
    lo que normalizamos explícitamente para evitar desfases al comparar o mostrar.
    """
    if v is None:
        return None
    if v.tzinfo is not None:
        return v.astimezone(timezone.utc).replace(tzinfo=None)
    return v


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
class LoginIn(BaseModel):
    identifier: str
    password: str


class FirstAccessIn(BaseModel):
    token: str
    password: str
    email: EmailStr
    display_name: Optional[str] = None
    timezone: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


class VerifyEmailIn(BaseModel):
    token: str


class ProfileUpdateIn(BaseModel):
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None


# ---------------------------------------------------------------------------
# Usuarios (admin)
# ---------------------------------------------------------------------------
class UserCreateIn(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    house_id: int
    role: str
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None


class UserUpdateIn(BaseModel):
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    timezone: Optional[str] = None
    email: Optional[EmailStr] = None


class RoleAssignIn(BaseModel):
    role: str


class HouseAssignIn(BaseModel):
    house_id: int
    effective: str = "now"  # now | end_of_cup


class FreezeIn(BaseModel):
    reason: Optional[str] = None


class StatusIn(BaseModel):
    status: str
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------
class DepositIn(BaseModel):
    user_id: int
    amount: int = Field(gt=0)
    reason: str = Field(min_length=2)
    idempotency_key: Optional[str] = None


class AdjustIn(BaseModel):
    user_id: int
    amount: int  # puede ser negativo
    reason: str = Field(min_length=2)
    idempotency_key: Optional[str] = None


class TransferIn(BaseModel):
    to_user_id: Optional[int] = None
    to_identifier: Optional[str] = None
    amount: int = Field(gt=0)
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    @field_validator("to_identifier")
    @classmethod
    def _strip(cls, v):
        return v.strip().upper() if v else v


class ReversalIn(BaseModel):
    reason: str = Field(min_length=2)


# ---------------------------------------------------------------------------
# Tienda
# ---------------------------------------------------------------------------
class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: Optional[str] = None
    image_url: Optional[str] = None
    price: int = Field(ge=0)
    published: bool = True
    purchase_limit_per_day: Optional[int] = None
    activation_limit_per_day: Optional[int] = None
    conditions: Optional[str] = None
    activation_requirements: Optional[str] = None
    special_rules: Optional[str] = None
    availability: Optional[str] = None
    affects_points: bool = False
    requires_approval: bool = True
    stock: Optional[int] = None


class PurchaseIn(BaseModel):
    product_id: int
    idempotency_key: Optional[str] = None


class RefundRequestIn(BaseModel):
    purchase_id: int
    reason: str = Field(min_length=2)


class RefundResolveIn(BaseModel):
    approve: bool
    reason: Optional[str] = None


class ActivationUpdateIn(BaseModel):
    status: str
    reason: Optional[str] = None
    event_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Copa / Puntos
# ---------------------------------------------------------------------------
class ParticipantIn(BaseModel):
    user_id: Optional[int] = None
    display_name: Optional[str] = None
    house_id: Optional[int] = None
    arrival_order: int = 0
    is_collaborator: bool = False
    answer_text: Optional[str] = None


class EventIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    type: str
    house_responsible_id: Optional[int] = None
    responsible_user_id: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    double_points: bool = False
    rounds_played: Optional[int] = None
    participants: list[ParticipantIn] = []
    meta: dict[str, Any] = {}

    _norm_sched = field_validator("scheduled_at")(classmethod(lambda cls, v: _normalize_utc(v)))


class GroupChallengeIn(BaseModel):
    name: str
    scheduled_at: Optional[datetime] = None
    # lista de house_id en orden de llegada (1º, 2º, 3º)
    ranking: list[int]
    meta: dict[str, Any] = {}

    _norm_sched = field_validator("scheduled_at")(classmethod(lambda cls, v: _normalize_utc(v)))


class IndividualChallengeIn(BaseModel):
    name: str
    house_id: int
    participants: list[ParticipantIn] = []
    scheduled_at: Optional[datetime] = None
    meta: dict[str, Any] = {}

    _norm_sched = field_validator("scheduled_at")(classmethod(lambda cls, v: _normalize_utc(v)))


class CompensationIn(BaseModel):
    house_id: int
    event_id: Optional[int] = None
    amount: Optional[int] = None  # por defecto 7500
    reason: str = Field(min_length=2)


class SanctionIn(BaseModel):
    target_user_id: Optional[int] = None
    target_house_id: Optional[int] = None
    resource: str  # PUNTOS | LUNARIAS
    amount: int = Field(gt=0)
    reason: str = Field(min_length=2)
    rule_ref: Optional[str] = None


class ParticipationIn(BaseModel):
    user_id: int
    partis: int
    event_id: Optional[int] = None
    reason: Optional[str] = None


class CasaNocturnaIn(BaseModel):
    allocations: list[dict]  # [{house_id, points}]
    reason: str = Field(min_length=2)


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------
class ScheduleIn(BaseModel):
    date: Optional[str] = None
    day_of_week: int
    house_id: Optional[int] = None
    activity_type: str = "DINAMICA"
    activity_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    responsible_user_id: Optional[int] = None
    notes: Optional[str] = None


class ScheduleUpdateIn(BaseModel):
    activity_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    change_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Reclamaciones
# ---------------------------------------------------------------------------
class ComplaintIn(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    reason: str = Field(min_length=3)
    event_id: Optional[int] = None


class ComplaintResolveIn(BaseModel):
    status: str
    resolution: str = Field(min_length=2)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
class SettingIn(BaseModel):
    key: str
    value: dict[str, Any]
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Serializadores
# ---------------------------------------------------------------------------
def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_house(h) -> dict:
    return {
        "id": h.id, "code": h.code, "name": h.name, "virtues": h.virtues,
        "founder": h.founder, "founded_year": h.founded_year, "symbols": h.symbols,
        "colors": h.colors, "heart_color": h.heart_color, "heart_hex": h.heart_hex,
        "identity": h.identity, "emblem": h.emblem, "is_competing": h.is_competing,
    }


def serialize_user(u, include_private: bool = False) -> dict:
    data = {
        "id": u.id,
        "identifier": u.identifier,
        "display_name": u.display_name,
        "photo_url": u.photo_url,
        "role": u.role,
        "status": u.status,
        "house_id": u.house_id,
        "house": serialize_house(u.house) if u.house else None,
        "timezone": u.timezone,
        "locale": u.locale,
        "is_director": u.is_director,
        "created_at": iso(u.created_at),
    }
    if include_private:
        data.update({
            "email": u.email,
            "email_verified": u.email_verified,
            "last_login_at": iso(u.last_login_at),
            "seq_number": u.seq_number,
        })
    return data


def serialize_wallet(w) -> dict:
    return {
        "id": w.id,
        "user_id": w.user_id,
        "balance": w.balance,
        "debt": w.debt,
        "currency": w.currency,
    }


def serialize_transaction(t) -> dict:
    return {
        "id": t.id,
        "reference": t.reference,
        "type": t.type,
        "amount": t.amount,
        "status": t.status,
        "reason": t.reason,
        "author_id": t.author_id,
        "counterparty_id": t.counterparty_id,
        "purchase_id": t.purchase_id,
        "refund_id": t.refund_id,
        "event_id": t.event_id,
        "reverses_transaction_id": t.reverses_transaction_id,
        "created_at": iso(t.created_at),
        "meta": t.meta,
    }


def serialize_entry(e) -> dict:
    return {
        "id": e.id,
        "transaction_id": e.transaction_id,
        "user_id": e.user_id,
        "amount": e.amount,
        "balance_after": e.balance_after,
        "created_at": iso(e.created_at),
    }


def serialize_product(p) -> dict:
    return {
        "id": p.id, "name": p.name, "description": p.description, "image_url": p.image_url,
        "price": p.price, "published": p.published,
        "purchase_limit_per_day": p.purchase_limit_per_day,
        "activation_limit_per_day": p.activation_limit_per_day,
        "conditions": p.conditions, "activation_requirements": p.activation_requirements,
        "special_rules": p.special_rules, "availability": p.availability,
        "affects_points": p.affects_points, "requires_approval": p.requires_approval,
        "stock": p.stock,
    }


def serialize_purchase(p) -> dict:
    return {
        "id": p.id, "user_id": p.user_id, "product_id": p.product_id,
        "product_name": p.product_name, "price_paid": p.price_paid,
        "house_id": p.house_id, "status": p.status,
        "conditions_snapshot": p.conditions_snapshot,
        "purchased_at": iso(p.purchased_at), "meta": p.meta,
    }


def serialize_activation(a) -> dict:
    return {
        "id": a.id, "purchase_id": a.purchase_id, "user_id": a.user_id,
        "event_id": a.event_id, "status": a.status, "reason": a.reason,
        "handled_by": a.handled_by, "handled_at": iso(a.handled_at),
    }


def serialize_event(e) -> dict:
    return {
        "id": e.id, "name": e.name, "type": e.type, "status": e.status,
        "house_responsible_id": e.house_responsible_id,
        "responsible_user_id": e.responsible_user_id,
        "scheduled_at": iso(e.scheduled_at),
        "double_points": e.double_points, "rounds_played": e.rounds_played,
        "confirmed_at": iso(e.confirmed_at), "compensation_applied": e.compensation_applied,
        "meta": e.meta, "created_at": iso(e.created_at),
    }


def serialize_participant(p) -> dict:
    return {
        "id": p.id, "event_id": p.event_id, "user_id": p.user_id,
        "display_name": p.display_name, "house_id": p.house_id,
        "arrival_order": p.arrival_order, "effective_podium": p.effective_podium,
        "points_awarded": p.points_awarded, "is_collaborator": p.is_collaborator,
        "answer_text": p.answer_text, "partis_awarded": p.partis_awarded,
    }


def serialize_ledger(l) -> dict:
    return {
        "id": l.id, "house_id": l.house_id, "user_id": l.user_id, "event_id": l.event_id,
        "type": l.type, "points": l.points, "reason": l.reason,
        "author_id": l.author_id, "reverses_id": l.reverses_id,
        "created_at": iso(l.created_at), "meta": l.meta,
    }


def serialize_sanction(s) -> dict:
    return {
        "id": s.id, "target_user_id": s.target_user_id, "target_house_id": s.target_house_id,
        "resource": s.resource, "amount": s.amount, "reason": s.reason,
        "rule_ref": s.rule_ref, "author_id": s.author_id,
        "transaction_id": s.transaction_id, "ledger_id": s.ledger_id,
        "created_at": iso(s.created_at),
    }


def serialize_schedule(s) -> dict:
    return {
        "id": s.id, "week_start": s.week_start, "day_of_week": s.day_of_week, "date": s.date,
        "house_id": s.house_id, "activity_type": s.activity_type, "activity_name": s.activity_name,
        "start_time": s.start_time, "end_time": s.end_time,
        "responsible_user_id": s.responsible_user_id, "status": s.status,
        "notes": s.notes, "meta": s.meta,
    }


def serialize_complaint(c) -> dict:
    return {
        "id": c.id, "requester_id": c.requester_id, "event_id": c.event_id,
        "subject": c.subject, "reason": c.reason, "status": c.status,
        "resolution": c.resolution, "resolved_by": c.resolved_by,
        "resolved_at": iso(c.resolved_at), "created_at": iso(c.created_at),
    }


def serialize_notification(n) -> dict:
    return {
        "id": n.id, "kind": n.kind, "title": n.title, "body": n.body,
        "link": n.link, "read": n.read, "created_at": iso(n.created_at),
    }
