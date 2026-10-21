# Dark Mystery's — Arquitectura del sistema

> Documento técnico de referencia. Describe la arquitectura, los límites entre
> sistemas, las decisiones de diseño y el enfoque de atomicidad/auditoría.

---

## 1. Visión general

Dark Mystery's es una plataforma privada de comunidad con tres sistemas que
**nunca deben mezclarse**:

| Sistema | Qué mide | Naturaleza | Dónde vive |
|---|---|---|---|
| **Puntos** | Competencia entre Casas (la Copa) | Entero, sin dueño individual | `point_ledger` + `house_scores` |
| **Lunarias** | Moneda virtual (banco/tienda) | Dinero con dueño (wallet) | `wallets` + `wallet_transactions` + `wallet_entries` |
| **Partis** | Registro de participación | Contador histórico por persona | `participation_records` |

**Regla de oro:** una operación pertenece a *un solo* sistema. Un reto puede
generar Puntos **y** Partis (dos asientos separados, en dos libros separados),
pero jamás se convierte un punto en lunaria ni viceversa.

```
                         ┌──────────────────────────────┐
                         │        Frontend (SPA)         │
                         │  HTML + CSS + JS (vanilla)    │
                         └───────────────┬──────────────┘
                                         │  fetch JSON (Bearer JWT)
                                         ▼
                         ┌──────────────────────────────┐
                         │        FastAPI (backend)      │
                         │  routers → services → models  │
                         │  RBAC en cada endpoint        │
                         └───────────────┬──────────────┘
                                         │  SQLAlchemy 2.0 (ORM)
                                         ▼
                         ┌──────────────────────────────┐
                         │   SQLite (dev) / PostgreSQL   │
                         │   (producción)                │
                         └──────────────────────────────┘
```

---

## 2. Stack y justificación

- **Backend:** FastAPI (Python 3.11). Asíncrono, tipado, genera OpenAPI y valida
  con Pydantic v2. Ideal para exponer una API REST clara y auditable.
- **ORM:** SQLAlchemy 2.0 con `DeclarativeBase` y columnas tipadas
  (`Mapped[...]`). Permite transacciones explícitas y `SELECT ... FOR UPDATE`.
- **Base de datos:** SQLite en desarrollo (modo WAL + `PRAGMA foreign_keys=ON`),
  **PostgreSQL recomendado en producción** por el locking a nivel de fila real y
  las restricciones de integridad concurrentes.
- **Auth:** JWT (PyJWT) con `token_version` para invalidar sesiones al instante.
  Contraseñas con **bcrypt** y pre-hash SHA-256 (soporta claves largas).
- **Exportes:** `openpyxl` (XLSX) y módulo `csv` (CSV), generados en backend.
- **Hosting:** Render (contenedor) o cualquier PaaS con PostgreSQL gestionado.
  Supabase es válido como Postgres gestionado. **Nunca** se exponen claves de
  administración en el frontend.

---

## 3. Estructura de carpetas

```
dark-mysterys/
├── backend/
│   ├── app/
│   │   ├── config.py          # settings (pydantic-settings)
│   │   ├── database.py        # engine, SessionLocal, Base
│   │   ├── enums.py           # enums + constantes de puntuación
│   │   ├── models.py          # modelo de datos completo
│   │   ├── security.py        # hash, JWT, tokens opacos
│   │   ├── permissions.py     # matriz RBAC
│   │   ├── deps.py            # dependencias (auth, permisos, auditoría)
│   │   ├── schemas.py         # entrada/salida Pydantic + serializadores
│   │   ├── seed.py            # datos iniciales (casas, roles, demo)
│   │   ├── main.py            # app FastAPI + static SPA
│   │   ├── routers/           # 14 routers (auth, users, wallet, shop, ...)
│   │   └── services/          # lógica de negocio (scoring, wallet, shop, ...)
│   ├── tests/                 # pytest (ver TEST_PLAN.md)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  # SPA estática (CSS, HTML, JS)
├── docs/                      # esta documentación
└── data/                      # SQLite de desarrollo (no versionar)
```

**Separación de responsabilidades:**

- `routers/` = capa HTTP: valida permisos, parsea entrada, devuelve salida.
- `services/` = lógica de negocio pura y transaccional (no conoce HTTP).
- `models.py` = persistencia. `schemas.py` = contrato con el cliente.

---

## 4. Los tres sistemas en detalle

### 4.1 Puntos (la Copa)

- Libro **append-only** `point_ledger`: cada movimiento es una fila inmutable con
  `house_id`, `delta`, `type`, `event_id`, `reason`, `created_by`.
- `house_scores` es una **caché** del total por Casa. Se actualiza dentro de la
  misma transacción que inserta el asiento, con `SELECT ... FOR UPDATE`.
- **Reconciliación:** `sum(point_ledger.delta por casa) == house_scores.points`.
  Endpoint `GET /api/points/reconcile` lo verifica.
- **Puntajes:** podio 6000/5000/4000, resto 1500; reto grupal 40000/30000/20000
  a la Casa; reto individual 16000 a la Casa; compensación 7500.
- **Regla del podio:** máximo **una persona por Casa** en el podio; si se
  incumple, las posiciones se corren a la siguiente Casa elegible.
  **Excepción:** si participan **dos Casas o menos**, una Casa puede ocupar dos
  lugares (6000/5000/4000 por orden de llegada).
- **Estados de evento:** `BORRADOR → CONFIRMADA → RECTIFICADA`. Solo al
  confirmar se escriben puntos. Rectificar **revierte** los asientos previos
  (asientos compensatorios) y vuelve a `BORRADOR`.

### 4.2 Lunarias (banco)

- **Doble asiento:** cada operación crea un `wallet_transaction` (cabecera) y uno
  o dos `wallet_entries` (asientos). Cada asiento guarda `balance_after`.
- **Atomicidad:** todo dentro de una transacción de base de datos. Las
  transferencias bloquean las dos wallets en orden de `id` para evitar deadlocks.
- **Idempotencia:** `idempotency_key` única por operación. Reintentar con la
  misma clave devuelve el resultado original sin duplicar.
- **Deuda:** las penalizaciones pueden dejar saldo negativo (deuda). Las
  ganancias futuras la amortizan automáticamente.
- **Sin borrado silencioso:** los errores se corrigen con **asientos
  compensatorios** (`reverse_transaction`), nunca borrando filas.
- **Ajustes grandes:** por encima del umbral (`LARGE_ADJUSTMENT_THRESHOLD`,
  50 000) quedan `PENDIENTE_APROBACION` y requieren aprobación de un segundo
  administrador.

### 4.3 Partis

- Registro **manual en v1** (`participation_records`, append-only).
- Reglas: 4 rondas = 1 parti; >4 o completado = 2 partis; <4 = 0.
- Reto grupal = 1 parti extra **solo para colaboradores**.
- Reto individual = 1 parti por entrega válida.
- Flash sticker = 1 parti al primero en responder.
- Respuestas fuera de tiempo = 0 partis.

---

## 5. Autenticación y sesiones

1. Solo **Dirección** (ADMINISTRADOR) crea usuarios. Se emite una **invitación
   temporal de un solo uso** (token opaco, guardado como hash SHA-256).
2. El primer ingreso exige: definir contraseña + **verificar email**.
3. Contraseñas siempre hasheadas (bcrypt + pre-hash). Nunca en texto plano.
4. Recuperación mediante email verificado (token de un solo uso).
5. **Estados de cuenta:** `PENDIENTE_DE_ACTIVACION`, `ACTIVA`, `CONGELADA`,
   `DADA_DE_BAJA`.
   - Congelar **incrementa `token_version`** → invalida sesiones activas al
     instante y bloquea cualquier operación (no recibe puntos, recompensas,
     transferencias ni reembolsos).

---

## 6. Autorización (RBAC)

- Matriz declarativa en `permissions.py`; se aplica con la dependencia
  `require_permission(...)` en cada endpoint.
- **Ocultar un botón en el frontend NO es seguridad.** El backend es la fuente
  de verdad: toda operación valida rol + propiedad del recurso (por ejemplo, un
  jefe solo penaliza a su propia Casa).
- Detalle completo en [`PERMISSIONS.md`](./PERMISSIONS.md).

---

## 7. Identificadores de cuenta

- Formato: **inicial del nombre + inicial de la Casa + número** → `DU01`.
- **Numeración independiente por Casa** (cada Casa tiene su cuenta #1, #2, …).
- Único, permanente, nunca reutilizado. Soporta más de 2 dígitos (`DU100`).
- Se genera con un **contador por Casa** (`house.counter`) bloqueado con
  `FOR UPDATE` y un bucle de unicidad por seguridad.

---

## 8. Zona horaria

- Almacenamiento **siempre en UTC**. Presentación en la zona del usuario.
- Por defecto `America/Argentina/Buenos_Aires`, pero **cada usuario puede
  cambiarla a su país** desde su perfil (`PATCH /api/auth/me` → `timezone`).
- Catálogo agrupado por región en `GET /api/meta/timezones`.
- La tienda abre lunes a viernes, 30 min después de la primera dinámica y cierra
  30 min después de la última; las activaciones se permiten hasta las 00:00 de
  Argentina.

---

## 9. Auditoría

- `audit_logs` **append-only**: actor, acción, entidad, antes/después, IP.
- Se registran operaciones sensibles: creación/edición de usuarios, cambios de
  rol/estado, movimientos de dinero, ajustes, aprobaciones, reversiones,
  confirmaciones/rectificaciones de eventos, penalizaciones, cambios de config.
- `GET /api/audit` (solo ADMINISTRADOR) permite consultar el histórico.

---

## 10. Seguridad

- RBAC forzado en backend.
- HTTPS en producción (HSTS activado cuando `ENVIRONMENT=production`).
- Cabeceras de seguridad: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`.
- Rate limiting de login (bloqueo temporal tras varios intentos).
- Prevención de duplicados por `idempotency_key`.
- Transacciones de base de datos en compras y transferencias.
- Sin claves de administración en el frontend.

---

## 11. Flujo de una operación (ejemplo: transferencia)

```
Cliente → POST /api/wallet/transfer (Bearer JWT)
  → deps.get_current_user()        valida JWT + token_version + estado ACTIVA
  → deps.require_permission(...)   valida WALLET_TRANSFER
  → wallet_service.transfer()
       ├─ valida idempotencia (devuelve original si ya existe)
       ├─ _lock_wallet(origen) / _lock_wallet(destino)   (FOR UPDATE, por id)
       ├─ verifica saldo disponible
       ├─ crea WalletTransaction + 2 WalletEntry (con balance_after)
       ├─ audit()
       └─ commit
  ← 200 { tx_id, nuevo_saldo }
```

---

## 12. Decisiones de diseño relevantes

| Decisión | Motivo |
|---|---|
| Libros append-only + caché reconciliable | Trazabilidad total y rendimiento de lectura |
| Doble asiento con `balance_after` | Auditable y reconstruible |
| Idempotencia por clave | Reintentos seguros (redes móviles, doble clic) |
| `token_version` | Invalidar sesiones al congelar/dar de baja |
| Numeración por Casa con contador | Identificadores únicos y estables |
| Timezone por usuario | Requisito explícito (cada quien su país) |
| Casa Nocturna separada (`is_competing=false`) | Gobierno, no compite en la Copa |
| Penalizaciones → deuda | Requisito explícito del cliente |

---

## 13. Puesta en marcha

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # ajustar SECRET_KEY
uvicorn app.main:app --reload # http://localhost:8000
```

- Documentación interactiva: `http://localhost:8000/docs`
- Salud: `http://localhost:8000/api/health`
- La primera ejecución crea el esquema y siembra casas, roles, productos y
  cuentas demo (contraseña demo: `DarkMystery2024!`).

En producción: usar PostgreSQL (`DATABASE_URL=postgresql+psycopg://...`),
`ENVIRONMENT=production`, `SECRET_KEY` única y `EMAIL_BACKEND=smtp`.
