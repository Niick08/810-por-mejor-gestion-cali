#!/bin/sh
# Preparación antes de arrancar la API (todo es repetible: se puede reiniciar sin riesgo).
set -e
if [ "${MODO_DEMO:-0}" = "1" ]; then
  flask --app api claves-demo                       # clave demo1234 para los usuarios de demostración
fi
if [ "${CARGAR_DATOS_REALES:-1}" = "1" ]; then
  # Solo la primera vez: si la base todavía tiene las 3 comunas de prueba, carga las de la IDESC
  if python -c "import os,psycopg,sys; c=psycopg.connect(os.environ['DATABASE_URL']); sys.exit(0 if c.execute('select count(*) from rcd.comuna').fetchone()[0] <= 3 else 1)"; then
    python scripts/cargar_datos_reales.py || echo "[rcd] No se pudieron cargar los datos de la IDESC; la app sigue con los de prueba"
  fi
fi
exec "$@"
