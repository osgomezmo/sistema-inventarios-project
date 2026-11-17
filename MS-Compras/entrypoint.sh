#!/usr/bin/env bash
# Arranque del contenedor: espera a MySQL, aplica las migraciones, siembra los
# datos iniciales si la base está vacía y ejecuta el comando recibido.
set -e

INTENTOS="${ESPERA_BASE_INTENTOS:-30}"
for i in $(seq 1 "$INTENTOS"); do
  if python -c "import os, mysql.connector; mysql.connector.connect(host=os.getenv('DB_HOST','127.0.0.1'), port=int(os.getenv('DB_PORT','3306')), user=os.getenv('DB_USER','compras_user'), password=os.getenv('DB_PASSWORD','changeme')).close()" 2>/dev/null; then
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

if [ "${SEMBRAR_DATOS:-1}" != "0" ]; then
  python -m db.datos_iniciales
else
  echo "SEMBRAR_DATOS=0: no se siembran datos iniciales."
fi

exec "$@"
