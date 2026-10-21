"""
Modelo de datos de Dark Mystery's.

Diseño (ver docs/DATA_MODEL.md):
- Separación estricta entre Puntos, Lunarias y Partis.
- El saldo y los puntos SIEMPRE tienen historial verificable (ledger).
- Operaciones financieras con doble asiento (wallet_entries).
- Todo lo sensible es auditable (audit_logs) y nunca se borra.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Casas y roles
# ---------------------------------------------------------------------------
class House(Base, TimestampMixin):
    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    virtues: Mapped[str | None] = mapped_column(String(255))
    founder: Mapped[str | None] = mapped_column(String(120))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    symbols: Mapped[str | None] = mapped_column(String(160))
    colors: Mapped[str | None] = mapped_column(String(120))
    heart_color: Mapped[str | None] = mapped_column(String(40))       # color del corazón para puntuación
    heart_hex: Mapped[str | None] = mapped_column(String(9))
    identity: Mapped[str | None] = mapped_column(Text)
    emblem: Mapped[str | None] = mapped_column(String(255))
    is_competing: Mapped[bool] = mapped_column(Boolean, default=True)  # False para Casa Nocturna
    counter: Mapped[int] = mapped_column(Integer, default=0)           # último número de cuenta emitido (por Casa)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    users: Mapped[list["User"]] = relationship(back_populates="house")


class RoleDef(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Usuarios y autenticación
# ---------------------------------------------------------------------------
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    seq_number: Mapped[int] = mapped_column(Integer, nullable=False)  # número dentro de la Casa
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDIENTE_DE_ACTIVACION", index=True)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Argentina/Buenos_Aires")
    locale: Mapped[str] = mapped_column(String(10), default="es")
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # invalida sesiones previas
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_director: Mapped[bool] = mapped_column(Boolean, default=False)  # las dos directoras
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    house: Mapped["House"] = relationship(back_populates="users")
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False)

    __table_args__ = (
        UniqueConstraint("house_id", "seq_number", name="uq_user_house_seq"),
        Index("ix_user_house_status", "house_id", "status"),
    )

    @property
    def is_active_account(self) -> bool:
        return self.status == "ACTIVA"


class AuthToken(Base, TimestampMixin):
    """Tokens de un solo uso: invitación, recuperación, verificación de correo."""
    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


# ---------------------------------------------------------------------------
# Banco de Lunarias
# ---------------------------------------------------------------------------
class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    # balance firmado: negativo = deuda (solo por penalizaciones/pérdidas autorizadas)
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(12), default="LUNARIAS")

    user: Mapped["User"] = relationship(back_populates="wallet")

    @property
    def debt(self) -> int:
        return max(0, -self.balance)


class WalletTransaction(Base, TimestampMixin):
    """Cabecera de una operación financiera."""
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # importe total (positivo)
    status: Mapped[str] = mapped_column(String(40), default="COMPLETADA", index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    purchase_id: Mapped[int | None] = mapped_column(ForeignKey("purchases.id"))
    refund_id: Mapped[int | None] = mapped_column(ForeignKey("refunds.id"))
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    reverses_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_transactions.id"))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    entries: Mapped[list["WalletEntry"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class WalletEntry(Base, TimestampMixin):
    """Asiento contable: cambio aplicado al saldo de una cuenta."""
    __tablename__ = "wallet_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("wallet_transactions.id"), index=True, nullable=False)
    wallet_id: Mapped[int] = mapped_column(ForeignKey("wallets.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # + crédito / - débito
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)

    transaction: Mapped["WalletTransaction"] = relationship(back_populates="entries")


class Approval(Base, TimestampMixin):
    """Aprobación de operaciones de gran importe."""
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("wallet_transactions.id"), nullable=False)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="PENDIENTE_APROBACION", index=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Tienda
# ---------------------------------------------------------------------------
class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    purchase_limit_per_day: Mapped[int | None] = mapped_column(Integer)     # límite propio del producto
    activation_limit_per_day: Mapped[int | None] = mapped_column(Integer)
    conditions: Mapped[str | None] = mapped_column(Text)
    activation_requirements: Mapped[str | None] = mapped_column(Text)
    special_rules: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str | None] = mapped_column(String(160))
    affects_points: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    stock: Mapped[int | None] = mapped_column(Integer)  # None = ilimitado
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Purchase(Base, TimestampMixin):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)  # snapshot histórico
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)         # snapshot histórico
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)  # Casa al momento
    status: Mapped[str] = mapped_column(String(40), default="PENDIENTE_ACTIVACION", index=True)
    conditions_snapshot: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class ProductActivation(Base, TimestampMixin):
    __tablename__ = "product_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    status: Mapped[str] = mapped_column(String(40), default="PENDIENTE", index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    handled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivationHistory(Base, TimestampMixin):
    __tablename__ = "activation_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    activation_id: Mapped[int] = mapped_column(ForeignKey("product_activations.id"), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True, nullable=False)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="SOLICITADO", index=True)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_transactions.id"))


# ---------------------------------------------------------------------------
# Copa / Puntos / Eventos
# ---------------------------------------------------------------------------
class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="BORRADOR", index=True)
    house_responsible_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    double_points: Mapped[bool] = mapped_column(Boolean, default=False)
    rounds_played: Mapped[int | None] = mapped_column(Integer)  # para cálculo de partis
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    compensation_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    participants: Mapped[list["EventParticipant"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventParticipant(Base, TimestampMixin):
    __tablename__ = "event_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))  # permite registrar sin cuenta
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    arrival_order: Mapped[int] = mapped_column(Integer, default=0)
    effective_podium: Mapped[int | None] = mapped_column(Integer)  # 1,2,3 o None
    points_awarded: Mapped[int] = mapped_column(Integer, default=0)
    is_collaborator: Mapped[bool] = mapped_column(Boolean, default=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    partis_awarded: Mapped[int] = mapped_column(Integer, default=0)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    event: Mapped["Event"] = relationship(back_populates="participants")


class PointLedger(Base, TimestampMixin):
    """Libro oficial de puntos. Append-only. Fuente de verdad del marcador."""
    __tablename__ = "point_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # firmado
    reason: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reverses_id: Mapped[int | None] = mapped_column(ForeignKey("point_ledger.id"))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class HouseScore(Base, TimestampMixin):
    """Acumulado por Casa. Reconciliable con point_ledger."""
    __tablename__ = "house_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), unique=True, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ParticipationRecord(Base, TimestampMixin):
    """Libro de partis (append-only). Cada otorgamiento es una fila."""
    __tablename__ = "participation_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), index=True)
    partis: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reverses_id: Mapped[int | None] = mapped_column(ForeignKey("participation_records.id"))


class Sanction(Base, TimestampMixin):
    __tablename__ = "sanctions"

    id: Mapped[int] = mapped_column(primary_key=True)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    target_house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    resource: Mapped[str] = mapped_column(String(20), nullable=False)  # PUNTOS | LUNARIAS
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    rule_ref: Mapped[str | None] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("wallet_transactions.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("point_ledger.id"))


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------
class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[str | None] = mapped_column(String(10))  # ISO date del lunes
    day_of_week: Mapped[int] = mapped_column(Integer)           # 0=lunes .. 6=domingo
    date: Mapped[str | None] = mapped_column(String(10))        # YYYY-MM-DD (zona AR)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(40), default="DINAMICA")
    activity_name: Mapped[str | None] = mapped_column(String(200))
    start_time: Mapped[str | None] = mapped_column(String(5))   # HH:MM
    end_time: Mapped[str | None] = mapped_column(String(5))
    responsible_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(40), default="PROGRAMADA", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class ScheduleChange(Base, TimestampMixin):
    __tablename__ = "schedule_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"), index=True, nullable=False)
    change_type: Mapped[str] = mapped_column(String(40))  # HORARIO | CANCELACION | INTERCAMBIO | COMPENSACION
    detail: Mapped[str | None] = mapped_column(Text)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


# ---------------------------------------------------------------------------
# Reclamaciones y auditoría
# ---------------------------------------------------------------------------
class Complaint(Base, TimestampMixin):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="ABIERTA", index=True)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_identifier: Mapped[str | None] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="SISTEMA")
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Setting(Base, TimestampMixin):
    """Configuración general editable por Dirección (clave/valor JSON)."""
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
