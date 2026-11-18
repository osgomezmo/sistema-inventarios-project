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

# Si el comando es gunicorn y se solicita iniciar el consumidor en el mismo contenedor
if [ "${INICIAR_CONSUMIDOR:-1}" = "1" ] && [[ "$*" =~ gunicorn ]]; then
  echo "Iniciando consumidor de RabbitMQ en segundo plano..."
  python consumidor.py &
  CONSUMIDOR_PID=$!
  trap 'kill -TERM $CONSUMIDOR_PID 2>/dev/null || true' SIGTERM SIGINT
fi

exec "$@"
