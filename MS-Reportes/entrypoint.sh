#!/usr/bin/env bash
# Arranque del contenedor: espera a MySQL, aplica las migraciones y ejecuta el comando.
set -e

INTENTOS="${ESPERA_BASE_INTENTOS:-30}"
for i in $(seq 1 "$INTENTOS"); do
  if python -c "from app.config import cargar_configuracion; from app.db import abrir_conexion; abrir_conexion(cargar_configuracion()).close()" 2>/dev/null; then
    break
  fi
  if [ "$i" = "$INTENTOS" ]; then
    echo "La base de datos no respondió tras $INTENTOS intentos." >&2
    exit 1
  fi
  echo "Esperando la base de datos ($i/$INTENTOS)..."
  sleep 2
done

python -m db.aplicar_migraciones

exec "$@"
