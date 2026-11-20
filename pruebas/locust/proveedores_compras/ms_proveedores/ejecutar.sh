#!/usr/bin/env bash
# Ejecutor de pruebas de rendimiento Locust para MS-Proveedores (P01..P07).
#
# Uso:
#   ./ejecutar.sh P01              # Ejecuta P01 en modo headless con CSV y HTML
#   ./ejecutar.sh P05              # Ejecuta P05 (estres con LoadTestShape)
#   ./ejecutar.sh P01 --ui         # Abre la interfaz web de Locust para P01
#   ./ejecutar.sh P01 --humo       # Corrida corta de verificacion (5u, 20s)
#   ./ejecutar.sh TODAS            # Ejecuta P01..P07 secuencialmente
#
# Variables de entorno opcionales:
#   HOST / LT_HOST                 URL base de MS-Proveedores (defecto: http://127.0.0.1:5003)
#   SERVICE_TOKEN / LT_SERVICE_TOKEN  Token de servicio (defecto: token-servicio-inventarios-2026-vm)
#   LT_USER_ID                     X-User-Id (defecto: 1)
#   LT_USER_ROLE                   X-User-Role (defecto: admin)
#   LT_USUARIOS                    Sobrescribe -u en pruebas de Carga y Capacidad
#   LT_SPAWN_RATE                  Sobrescribe -r en pruebas de Carga y Capacidad
#   LT_DURACION                    Sobrescribe -t en pruebas de Carga y Capacidad (ej. 30m, 60m)
#   LT_SALIDA                      Carpeta base de reportes CSV/HTML
#   LOCUST_BIN                     Ruta explicita al binario locust

set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ_LOCUST="$(cd "$AQUI/.." && pwd)"
RAIZ_PRUEBAS="$(cd "$AQUI/../../.." && pwd)"

ID_RAW="${1:-}"
MODO="${2:-}"

if [[ -z "$ID_RAW" ]]; then
  echo "Uso: $0 <P01..P07|TODAS> [--ui|--humo]" >&2
  exit 2
fi

ID="$(echo "$ID_RAW" | tr '[:lower:]' '[:upper:]')"

if [[ "$ID" == "TODAS" ]]; then
  for p in P01 P02 P03 P04 P05 P06 P07; do
    "$0" "$p" "$MODO"
  done
  exit 0
fi

resolver_locust() {
  if [[ -n "${LOCUST_BIN:-}" ]]; then
    echo "$LOCUST_BIN"
    return 0
  fi
  for candidato in \
    "$RAIZ_LOCUST/.venv/bin/locust" \
    "$RAIZ_LOCUST/.venv/Scripts/locust.exe" \
    "$AQUI/../../.venv/bin/locust" \
    "$AQUI/../../.venv/Scripts/locust.exe"; do
    if [[ -x "$candidato" ]]; then
      echo "$candidato"
      return 0
    fi
  done
  if command -v locust >/dev/null 2>&1; then
    command -v locust
    return 0
  fi
  echo "No se encontro el ejecutable 'locust'. Instala requirements.txt en un entorno virtual." >&2
  exit 1
}

ARCHIVO=""
TIPO=""
USUARIOS_DEF=""
SPAWN_DEF=""
DURACION_DEF=""

case "$ID" in
  P01)
    ARCHIVO="$AQUI/p01_carga_lectura.py"
    TIPO="carga"
    USUARIOS_DEF=25; SPAWN_DEF=5; DURACION_DEF="5m"
    ;;
  P02)
    ARCHIVO="$AQUI/p02_carga_mixta.py"
    TIPO="carga"
    USUARIOS_DEF=30; SPAWN_DEF=5; DURACION_DEF="5m"
    ;;
  P03)
    ARCHIVO="$AQUI/p03_carga_ciclo_vida.py"
    TIPO="carga"
    USUARIOS_DEF=20; SPAWN_DEF=4; DURACION_DEF="5m"
    ;;
  P04)
    ARCHIVO="$AQUI/p04_carga_productos.py"
    TIPO="carga"
    USUARIOS_DEF=25; SPAWN_DEF=5; DURACION_DEF="5m"
    ;;
  P05)
    ARCHIVO="$AQUI/p05_estres_lectura.py"
    TIPO="estres"
    ;;
  P06)
    ARCHIVO="$AQUI/p06_estres_escritura.py"
    TIPO="estres"
    ;;
  P07)
    ARCHIVO="$AQUI/p07_capacidad_soak.py"
    TIPO="capacidad"
    USUARIOS_DEF=40; SPAWN_DEF=5; DURACION_DEF="15m"
    ;;
  *)
    echo "Identificador invalido: $ID_RAW. Valores validos: P01..P07 o TODAS." >&2
    exit 2
    ;;
esac

HOST_EFECTIVO="${LT_HOST:-${HOST:-http://127.0.0.1:5003}}"
export LT_HOST="$HOST_EFECTIVO"
export HOST="$HOST_EFECTIVO"
export LT_SERVICE_TOKEN="${LT_SERVICE_TOKEN:-${SERVICE_TOKEN:-token-servicio-inventarios-2026-vm}}"
export SERVICE_TOKEN="$LT_SERVICE_TOKEN"

LOCUST_CMD="$(resolver_locust)"

if [[ "$MODO" == "--ui" ]]; then
  echo "[$ID] Iniciando interfaz web Locust contra $HOST_EFECTIVO ($ARCHIVO)"
  exec "$LOCUST_CMD" -f "$ARCHIVO" --host "$HOST_EFECTIVO"
fi

SALIDA_BASE="${LT_SALIDA:-$RAIZ_PRUEBAS/resultados/proveedores_compras}"
DIR_SALIDA="$SALIDA_BASE/$ID"
mkdir -p "$DIR_SALIDA"

ARGS=(-f "$ARCHIVO" --headless --host "$HOST_EFECTIVO" --csv "$DIR_SALIDA/$ID" --html "$DIR_SALIDA/$ID.html" --loglevel INFO)

if [[ "$TIPO" == "estres" ]]; then
  if [[ "$MODO" == "--humo" ]]; then
    export LT_PASO_USUARIOS="${LT_PASO_USUARIOS:-5}"
    export LT_PASO_SEGUNDOS="${LT_PASO_SEGUNDOS:-10}"
    export LT_MAX_USUARIOS="${LT_MAX_USUARIOS:-15}"
  fi
else
  if [[ "$MODO" == "--humo" ]]; then
    USUARIOS="${LT_USUARIOS:-5}"
    SPAWN="${LT_SPAWN_RATE:-5}"
    DURACION="${LT_DURACION:-20s}"
  else
    USUARIOS="${LT_USUARIOS:-$USUARIOS_DEF}"
    SPAWN="${LT_SPAWN_RATE:-$SPAWN_DEF}"
    DURACION="${LT_DURACION:-$DURACION_DEF}"
  fi
  ARGS+=(-u "$USUARIOS" -r "$SPAWN" -t "$DURACION")
fi

echo "[$ID] Ejecutando ($TIPO) contra $HOST_EFECTIVO | Reportes en: $DIR_SALIDA"
"$LOCUST_CMD" "${ARGS[@]}"
