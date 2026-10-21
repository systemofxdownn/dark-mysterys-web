#!/usr/bin/env bash
# ==========================================================================
# Corre la suite de pruebas contra PostgreSQL REAL (no SQLite).
# Valida la ruta de producción antes de desplegar.
#
# Uso:
#   DM_TEST_DATABASE_URL="postgresql+psycopg://user:pass@host:5432/db" \
#     bash scripts/run_tests_postgres.sh
# ==========================================================================
set -euo pipefail

PG_URL="${DM_TEST_DATABASE_URL:-postgresql+psycopg://dm:dmtest@127.0.0.1:5432/darkmysterys_test}"
export DM_TEST_DATABASE_URL="$PG_URL"

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "→ Base de pruebas: $PG_URL"
python - <<'PY'
import os
from sqlalchemy import create_engine, text

url = os.environ["DM_TEST_DATABASE_URL"]
eng = create_engine(url)
with eng.begin() as conn:
    conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
print("→ Esquema reiniciado")
PY

cd "$HERE/../backend"
python -m pytest -q "$@"
