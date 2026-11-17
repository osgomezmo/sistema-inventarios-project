#!/usr/bin/env bash
# Arranque del contenedor: espera a MySQL, migra, siembra los datos iniciales si
# no hay roles (D51) y arranca Apache. Artisan corre como www-data para que los
# archivos de storage sigan siendo de Apache.
set -e

artisan() {
  runuser -u www-data -- php artisan "$@"
}

INTENTOS="${ESPERA_BASE_INTENTOS:-30}"
for i in $(seq 1 "$INTENTOS"); do
  if php -r 'new PDO("mysql:host=".getenv("DB_HOST").";port=".getenv("DB_PORT").";dbname=".getenv("DB_DATABASE"), getenv("DB_USERNAME"), getenv("DB_PASSWORD"));' 2>/dev/null; then
    break
  fi
  if [ "$i" = "$INTENTOS" ]; then
    echo "La base de datos no respondió tras $INTENTOS intentos." >&2
    exit 1
  fi
  echo "Esperando la base de datos ($i/$INTENTOS)..."
  sleep 2
done

artisan migrate --force

if [ "${SEMBRAR_DATOS:-1}" != "0" ]; then
  artisan gateway:datos-iniciales
else
  echo "SEMBRAR_DATOS=0: no se siembran datos iniciales."
fi

exec apache2-foreground
