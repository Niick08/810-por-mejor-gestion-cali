#!/bin/bash
# Crea el esquema, las reglas y los datos de demostración la primera vez que arranca la base.
set -euo pipefail
for f in 01_esquema.sql 02_funciones_triggers.sql 04_funciones_api.sql 03_datos_demo.sql; do
  echo "[rcd] cargando $f"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/sql/$f"
done
