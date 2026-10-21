"""
Fixtures de pruebas para Dark Mystery's.

Cada sesión de pytest usa una base SQLite temporal aislada. La app arranca con
sus eventos de startup (crea esquema + seed) y se expone un TestClient.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# --- Aislar la base ANTES de importar la app ---
# Por defecto se usa una base SQLite temporal. Para validar contra PostgreSQL
# real, definí DM_TEST_DATABASE_URL (ver scripts/run_tests_postgres.sh).
_EXTERNAL_DB = os.environ.get("DM_TEST_DATABASE_URL")
if _EXTERNAL_DB:
    os.environ["DATABASE_URL"] = _EXTERNAL_DB
else:
    _TMP_DB = Path(tempfile.gettempdir()) / "darkmysterys_test.db"
    if _TMP_DB.exists():
        _TMP_DB.unlink()
    os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["ENVIRONMENT"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["EMAIL_BACKEND"] = "console"
# La tienda se prueba con el horario desactivado para que los tests sean
# deterministas cualquier día de la semana; la lógica de horario se prueba aparte.
os.environ["SHOP_ENFORCE_HOURS"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services import accounts  # noqa: E402
from app.enums import Role, TokenPurpose  # noqa: E402
from datetime import timedelta  # noqa: E402

DEMO_PASSWORD = "DarkMystery2024!"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, identifier: str, password: str = DEMO_PASSWORD) -> str:
    r = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# Identificadores reales (numeración independiente por Casa):
#   Nocturna: Daniela DN01, Selene SN02, Bancor BN03
#   Corvus:   Aurelian AC01, Cassia CC01, María MC03, Marta MC04
#   Aegis:    Helios HA01, Iris IA01, Juan JA03, Tomás TA04
#   Umbra:    Nyxus NU01, Mora MU01, Pepe PU03, Lucía LU04
@pytest.fixture(scope="session")
def admin_token(client) -> str:
    return _login(client, "DN01")  # Daniela, ADMINISTRADOR, Casa Nocturna


@pytest.fixture(scope="session")
def banker_token(client) -> str:
    return _login(client, "BN03")  # Bancor, BANQUERO, Casa Nocturna


@pytest.fixture(scope="session")
def corvus_leader_token(client) -> str:
    return _login(client, "AC01")  # Aurelian, JEFE_DE_CASA, Corvus


@pytest.fixture(scope="session")
def student_token(client) -> str:
    return _login(client, "MC03")  # María, ESTUDIANTE, Corvus


@pytest.fixture(scope="session")
def auth():
    return _auth


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_active_user(db, *, name: str, house_id: int, role: str, email: str | None = None) -> User:
    """Crea un usuario ACTIVA con contraseña conocida (para pruebas)."""
    from app.security import hash_password
    from app.enums import AccountStatus

    user, _token = accounts.create_user(
        db, display_name=name, house_id=house_id, role=role, email=email,
    )
    user.status = AccountStatus.ACTIVA.value
    user.email_verified = True
    user.password_hash = hash_password(DEMO_PASSWORD)
    db.commit()
    db.refresh(user)
    return user
