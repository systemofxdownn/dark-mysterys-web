"""
Dark Mystery's — Aplicación principal (FastAPI).

- API REST bajo /api
- Sirve el frontend estático (SPA) desde /frontend
- Crea el esquema y siembra datos iniciales al arrancar
- Cabeceras de seguridad y CORS
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_DIR, settings
from .database import Base, SessionLocal, engine
from .routers import (
    audit,
    auth,
    complaints,
    config as config_router,
    events,
    meta,
    notifications,
    partis,
    points,
    reports,
    schedule,
    shop,
    users,
    wallet,
)
from .seed import ensure_seed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("darkmysterys")

app = FastAPI(
    title="Dark Mystery's API",
    description="Plataforma privada de la comunidad Dark Mystery's (Casas, banco, tienda y Copa).",
    version="1.0.0",
)

origins = [o.strip() for o in settings.cors_origins.split(",")] if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# --- Routers ---
for r in (auth, users, wallet, shop, points, events, schedule, partis,
          complaints, audit, reports, notifications, config_router, meta):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.on_event("startup")
def on_startup():
    if settings.is_production and settings.secret_key_is_default:
        logger.critical(
            "SECRET_KEY insegura en producción. Definí la variable de entorno "
            "SECRET_KEY con un valor aleatorio: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = ensure_seed(db)
        logger.info("Base de datos lista. Seed: %s", result)
    finally:
        db.close()


# --- Frontend estático (SPA) ---
FRONTEND_DIR = PROJECT_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:  # pragma: no cover
    @app.get("/")
    def _no_frontend():
        return JSONResponse({"message": "Frontend no encontrado."})
