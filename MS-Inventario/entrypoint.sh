#!/usr/bin/env bash
# Arranque del contenedor: espera a MySQL, aplica las migraciones, siembra los
# datos iniciales si la base está vacía (D51) y ejecuta el comando recibido.
# El consumidor arranca con MIGRAR_BASE=0 y SEMBRAR_DATOS=0: solo la app lo hace.
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

if [ "${MIGRAR_BASE:-1}" != "0" ]; then
  python -m db.aplicar_migraciones
fi

if [ "${SEMBRAR_DATOS:-1}" != "0" ]; then
  python -m db.datos_iniciales
else
  echo "SEMBRAR_DATOS=0: no se siembran datos iniciales."
fi

exec "$@"
