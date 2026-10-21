"""
Configuración central de Dark Mystery's.

Todos los valores sensibles se leen de variables de entorno (nunca hardcodeados
en producción). Se proveen valores por defecto seguros para desarrollo.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # .../backend
PROJECT_DIR = BASE_DIR.parent                       # .../dark-mysterys


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identidad del proyecto ---
    app_name: str = "Dark Mystery's"
    environment: str = Field(default="development")  # development | production

    # --- Base de datos ---
    # En producción se recomienda PostgreSQL:
    #   DATABASE_URL=postgresql+psycopg://user:pass@host:5432/darkmysterys
    database_url: str = Field(default=f"sqlite:///{PROJECT_DIR / 'data' / 'darkmysterys.db'}")

    # --- Seguridad / JWT ---
    secret_key: str = Field(default="dev-insecure-change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8          # 8 horas
    invitation_token_expire_hours: int = 72            # 3 días
    reset_token_expire_minutes: int = 60               # 1 hora
    email_verify_token_expire_hours: int = 48

    # --- Reglas de negocio (configurables) ---
    default_timezone: str = "America/Argentina/Buenos_Aires"
    large_adjustment_threshold: int = 50_000           # Lunarias: requiere aprobación de Dirección
    refund_window_days: int = 15                        # plazo de reembolso
    shop_daily_purchase_limit: int = 8                  # por Casa / día
    shop_daily_activation_limit: int = 4                # por Casa / día
    shop_open_offset_minutes: int = 30                  # abre 30 min tras 1ª dinámica
    shop_close_offset_minutes: int = 30                 # cierra 30 min tras última dinámica
    shop_enforce_hours: bool = True                     # exigir horario en compras (lun-vie)
    activation_before_event_minutes: int = 15           # activar hasta 15 min antes
    max_login_attempts: int = 8
    login_lockout_minutes: int = 15

    # --- Puntuación (Copa) ---
    podium_points: tuple[int, int, int] = (6000, 5000, 4000)
    participation_points: int = 1500
    group_challenge_points: tuple[int, int, int] = (40000, 30000, 20000)
    individual_challenge_points: int = 16000
    cancellation_compensation: int = 7500
    late_answer_reference: int = 900  # solo referencia, no se automatiza

    # --- Correo (desarrollo: consola) ---
    email_backend: str = "console"  # console | smtp
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "no-reply@darkmysterys.local"

    # --- CORS ---
    cors_origins: str = "*"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Normaliza la URL de Postgres entregada por el proveedor de hosting.

        Render (y Heroku) entregan 'postgres://' o 'postgresql://' sin driver.
        SQLAlchemy 2.0 exige el driver explícito (psycopg3), por lo que la URL
        se reescribe automáticamente a 'postgresql+psycopg://'.
        """
        if not v:
            return v
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def secret_key_is_default(self) -> bool:
        return self.secret_key == "dev-insecure-change-me-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
