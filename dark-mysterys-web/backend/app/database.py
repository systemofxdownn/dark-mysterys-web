"""
Capa de base de datos.

- SQLite para desarrollo (por defecto) y PostgreSQL para producción.
- Se habilitan claves foráneas en SQLite.
- `Base` es la clase declarativa común.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    url = settings.database_url
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        # Asegura que exista el directorio del archivo SQLite
        if ":///" in url:
            db_path = url.split(":///", 1)[1]
            if db_path and db_path != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL (producción): pool acotado y reciclado para no agotar las
        # conexiones del plan gratuito y sobrevivir a reinicios del servicio.
        kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)
    engine = create_engine(url, **kwargs)

    if url.startswith("sqlite"):
        # Activar integridad referencial (FK) y modo WAL para concurrencia
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover
            cur = dbapi_connection.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """Dependencia FastAPI: entrega una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
