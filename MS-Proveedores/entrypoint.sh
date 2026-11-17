#!/bin/sh
# Arranque del contenedor: espera a MySQL, aplica las migraciones, siembra los
# datos iniciales si la base está vacía y ejecuta el comando recibido.
set -e

INTENTOS="${ESPERA_BASE_INTENTOS:-30}"
i=1
while [ "$i" -le "$INTENTOS" ]; do
  if node -e "const mysql=require('mysql2/promise');const {config}=require('./src/config/env');mysql.createConnection({host:config.db.host,port:config.db.port,user:config.db.user,password:config.db.password,database:config.db.database,connectTimeout:3000}).then(c=>c.end()).then(()=>process.exit(0)).catch(()=>process.exit(1));" 2>/dev/null; then
    break
  fi
  if [ "$i" = "$INTENTOS" ]; then
    echo "La base de datos no respondió tras $INTENTOS intentos." >&2
    exit 1
  fi
  echo "Esperando la base de datos ($i/$INTENTOS)..."
  sleep 2
  i=$((i + 1))
done

node db/aplicar_migraciones.js

if [ "${SEMBRAR_DATOS:-1}" != "0" ]; then
  node db/datos_iniciales.js
else
  echo "SEMBRAR_DATOS=0: no se siembran datos iniciales."
fi

exec "$@"
