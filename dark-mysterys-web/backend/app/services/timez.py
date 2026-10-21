"""
Utilidades de zona horaria.

Regla del proyecto: el sistema ALMACENA en UTC y MUESTRA/CALCULA en la zona
horaria del usuario. Por defecto: America/Argentina/Buenos_Aires. Cada usuario
puede elegir su zona horaria (adaptación por país de origen).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import settings

UTC = timezone.utc


def tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or settings.default_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.default_timezone)


def now_utc() -> datetime:
    return datetime.now(UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normaliza un datetime a UTC-aware.

    SQLite (y algunos drivers) devuelven datetimes *naive* aunque la columna sea
    ``DateTime(timezone=True)``. Comparar un naive con ``now_utc()`` (aware)
    lanzar\u00eda ``TypeError``. Este helper asume UTC cuando falta el tzinfo.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_tz(dt: datetime | None, tzname: str | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz(tzname))


def local_date(dt: datetime | None, tzname: str | None) -> date | None:
    local = to_tz(dt, tzname)
    return local.date() if local else None


def today_local(tzname: str | None) -> date:
    return now_utc().astimezone(tz(tzname)).date()


def parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hh, mm = value.split(":")[:2]
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return None


def combine_local(d: date, t: time, tzname: str | None) -> datetime:
    return datetime.combine(d, t, tzinfo=tz(tzname))


def local_to_utc(dt_local: datetime, tzname: str | None) -> datetime:
    return dt_local.astimezone(UTC)


def day_bounds_utc(d: date, tzname: str | None) -> tuple[datetime, datetime]:
    """Devuelve [inicio, fin) del día local expresado en UTC."""
    start = datetime.combine(d, time.min, tzinfo=tz(tzname)).astimezone(UTC)
    end = start + timedelta(days=1)
    return start, end
