# Despliegue en Render — Dark Mystery's

Guía paso a paso para publicar la plataforma **completa** (backend FastAPI + frontend SPA + base de datos PostgreSQL) en [Render](https://render.com).

> **Idea clave:** el backend sirve también el frontend (SPA) desde la misma URL. Por eso **un solo Web Service** alcanza para tener todo online, con una base PostgreSQL administrada.

---

## 0. Resumen de la arquitectura

```
                 ┌──────────────────────────────┐
   Usuarios ───▶ │  Render Web Service          │
                 │  uvicorn app.main:app        │
                 │  ├── /api/...   (REST)       │
                 │  └── /          (SPA)        │
                 └──────────────┬───────────────┘
                                │
                 ┌──────────────▼───────────────┐
                 │  PostgreSQL (Render o Neon)  │
                 └──────────────────────────────┘
```

Un único servicio, una única URL, sin CORS ni builds de frontend.

---

## 1. Requisitos previos

- Cuenta de **GitHub** (gratis).
- Cuenta de **Render** (gratis): https://render.com
- El código del proyecto (esta carpeta `dark-mysterys/`).

---

## 2. Subir el código a GitHub

Desde la carpeta `dark-mysterys/`:

```bash
git init
git add .
git commit -m "Dark Mystery's — plataforma completa (backend + frontend)"
git branch -M main
# Creá un repositorio vacío en GitHub llamado "dark-mysterys" y copiá su URL:
git remote add origin https://github.com/TU_USUARIO/dark-mysterys.git
git push -u origin main
```

> El archivo `.gitignore` ya excluye `.env`, la base SQLite local (`data/`), `__pycache__`, etc. **Nunca subas tu `.env`.**

---

## 3. Opción A — Blueprint (recomendada, 1 clic)

El repositorio ya incluye **`render.yaml`**, que describe toda la infraestructura.

1. En Render: **New +** → **Blueprint**.
2. Elegí el repositorio `dark-mysterys` y la rama `main`.
3. Render detecta `render.yaml` y muestra el plan:
   - **Web Service** `dark-mysterys` (Python, plan free).
   - **PostgreSQL** `dark-mysterys-db` (plan free).
4. Hacé clic en **Apply / Create**. Render:
   - Instala dependencias (`pip install -r backend/requirements.txt`).
   - Genera una `SECRET_KEY` segura automáticamente.
   - Inyecta `DATABASE_URL` desde la base creada.
   - Arranca con `uvicorn` y crea el esquema + seed inicial.
5. Esperá a que el estado sea **Live** y abrí la URL (`https://dark-mysterys.onrender.com`).

> ⚠️ **Importante sobre la base free de Render:** las bases PostgreSQL del plan gratuito de Render **se eliminan a los 90 días**. Para una base **permanente y gratuita**, usá la **Opción B** con Neon o Supabase.

---

## 4. Opción B — Web Service manual + Neon (base permanente)

Ideal si querés que los datos **no se borren nunca** y no pagar.

### 4.1 Crear la base en Neon (gratis, permanente)

1. Entrá a https://neon.tech y creá un proyecto.
2. Copiá la **connection string** (formato `postgresql://usuario:clave@host/db?sslmode=require`).
3. (Alternativa: https://supabase.com → Project Settings → Database → Connection string.)

> No hace falta cambiar nada del código: la app normaliza automáticamente `postgres://` y `postgresql://` al driver `psycopg`.

### 4.2 Crear el Web Service en Render

1. **New +** → **Web Service** → conectá el repositorio.
2. Configurá:
   - **Name:** `dark-mysterys`
   - **Region:** `Oregon` (o la más cercana a tu comunidad)
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install --upgrade pip && pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/api/health`
   - **Instance Type:** `Free`
3. En **Environment → Add Environment Variable**, cargá:

| Variable | Valor | Obligatoria |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | Sí |
| `ENVIRONMENT` | `production` | Sí |
| `SECRET_KEY` | *(generá una: ver abajo)* | Sí |
| `DATABASE_URL` | *(connection string de Neon)* | Sí |
| `DEFAULT_TIMEZONE` | `America/Argentina/Buenos_Aires` | No |
| `SHOP_ENFORCE_HOURS` | `true` | No |
| `EMAIL_BACKEND` | `console` (o `smtp` en producción real) | No |
| `CORS_ORIGINS` | `*` (o tu dominio) | No |

**Generar una `SECRET_KEY` segura:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

4. **Create Web Service** y esperá a que quede **Live**.

---

## 5. Verificación post-despliegue

1. **Health check:** abrí `https://TU-APP.onrender.com/api/health` → debe responder
   ```json
   {"status":"ok","app":"Dark Mystery's","environment":"production"}
   ```
2. **Docs de la API:** `https://TU-APP.onrender.com/docs`
3. **App (SPA):** `https://TU-APP.onrender.com/` → debería verse la pantalla de ingreso.
4. **Login de prueba:** usuario `DN01`, contraseña `DarkMystery2024!`.
5. Recorré el panel: marcador de la Copa, banco, tienda, usuarios, configuración.

---

## 6. Notas importantes

- **Plan free de Render:** el servicio **se duerme tras ~15 min de inactividad** y tarda ~30–60 s en despertar con la primera visita. Para uso real conviene el plan pago más chico (o un *uptime pinger*).
- **Base de datos:** con la Opción A se borra a los 90 días. Con la Opción B (Neon) es permanente.
- **Correo:** con `EMAIL_BACKEND=console`, las invitaciones y recuperaciones **se imprimen en los logs** de Render (no se envían). Para envío real, configurá `EMAIL_BACKEND=smtp` + `SMTP_*`.
- **Seguridad:** cambiá las contraseñas de las cuentas demo y, en producción, **no** dejes el seed demo. Podés desactivarlo editando `app/seed.py` o vaciando `DEMO_ACCOUNTS`.
- **Migraciones:** hoy el esquema se crea con `create_all` al arrancar. Para cambios de esquema en producción, se recomienda incorporar **Alembic**.
- **HTTPS:** Render lo provee automáticamente (certificado gestionado).

---

## 7. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres` | URL sin driver | Ya se normaliza sola; verificá que `psycopg[binary]` esté instalado (está en `requirements.txt`). |
| `connection refused` a la base | `DATABASE_URL` mal o base dormida | Revisá la connection string y que la base esté activa. |
| El servicio no levanta | Falta `SECRET_KEY` o `DATABASE_URL` | Cargá ambas variables de entorno. |
| `502` al abrir la app | El servicio está despertando (plan free) | Esperá 30–60 s y recargá. |
| No llegan correos | `EMAIL_BACKEND=console` | Configurá SMTP real. |
| La SPA carga pero la API falla | Se desplegó solo el frontend | Este proyecto sirve la API desde el mismo servicio; usá el start command indicado. |

---

## 8. Alternativas de hosting

- **Railway / Fly.io:** mismo `startCommand`; definí `DATABASE_URL` y `SECRET_KEY`.
- **VPS propio (Docker):** correr `uvicorn` detrás de Nginx + Certbot.
- **Base de datos:** Neon, Supabase, Railway Postgres, Aiven (todas ofrecen plan gratuito).

---

<div align="center">

**POWERED BY: ZETA LESTRANGE**

</div>
