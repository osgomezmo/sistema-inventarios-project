#!/usr/bin/env bash
# Ejecuta las pruebas de rendimiento Locust P08..P15 para MS-Compras.
# Uso:
#   ./ejecutar.sh P08
#   ./ejecutar.sh solo
#   ./ejecutar.sh integrado
#   ./ejecutar.sh todas
# Variables opcionales:
#   HOST / LT_HOST (defecto http://127.0.0.1:5004)
#   SERVICE_TOKEN / LT_SERVICE_TOKEN (defecto token-servicio-inventarios-2026-vm)
#   LT_USUARIOS, LT_SPAWN_RATE, LT_DURACION, LT_SALIDA, LT_INCLUIR_ESCRITURAS
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
OBJETIVO="${1:-}"
HOST_EFECTIVO="${HOST:-${LT_HOST:-http://127.0.0.1:5004}}"
SALIDA_BASE="${LT_SALIDA:-$AQUI/../../../resultados/proveedores_compras}"

localizar_locust() {
  if [ -n "${LOCUST_BIN:-}" ]; then
    echo "$LOCUST_BIN"
  elif [ -x "$AQUI/../.venv/bin/locust" ]; then
    echo "$AQUI/../.venv/bin/locust"
  elif [ -x "$AQUI/../.venv/Scripts/locust.exe" ]; then
    echo "$AQUI/../.venv/Scripts/locust.exe"
  elif [ -x "$AQUI/../../.venv/bin/locust" ]; then
    echo "$AQUI/../../.venv/bin/locust"
  elif [ -x "$AQUI/../../.venv/Scripts/locust.exe" ]; then
    echo "$AQUI/../../.venv/Scripts/locust.exe"
  elif command -v locust >/dev/null 2>&1; then
    command -v locust
  else
    echo "Error: no se encontro 'locust'. Instale con pip install -r $AQUI/../requirements.txt o defina LOCUST_BIN" >&2
    exit 1
  fi
}

correr_una() {
  local ID="$1"
  local ARCHIVO=""
  local USA_SHAPE="0"
  local DEF_U=""
  local DEF_R=""
  local DEF_T=""

  case "$ID" in
    P08) ARCHIVO="p08_carga_ordenes.py"; DEF_U="20"; DEF_R="5"; DEF_T="10m" ;;
    P09) ARCHIVO="p09_carga_devoluciones.py"; DEF_U="25"; DEF_R="5"; DEF_T="10m" ;;
    P10) ARCHIVO="p10_carga_validacion.py"; DEF_U="30"; DEF_R="6"; DEF_T="5m" ;;
    P11) ARCHIVO="p11_carga_mixta.py"; DEF_U="20"; DEF_R="4"; DEF_T="10m" ;;
    P12) ARCHIVO="p12_carga_ciclo_completo.py"; DEF_U="15"; DEF_R="3"; DEF_T="10m" ;;
    P13) ARCHIVO="p13_estres_lecturas.py"; USA_SHAPE="1" ;;
    P14) ARCHIVO="p14_estres_escrituras.py"; USA_SHAPE="1" ;;
    P15) ARCHIVO="p15_capacidad_soak.py"; DEF_U="40"; DEF_R="5"; DEF_T="60m" ;;
    *)
      echo "Uso: $0 <P08..P15|solo|integrado|todas>" >&2
      exit 2
      ;;
  esac

  local LOCUST_BIN
  LOCUST_BIN="$(localizar_locust)"
  local SALIDA="$SALIDA_BASE/$ID"
  mkdir -p "$SALIDA"

  local ARGS=(
    --headless
    -f "$AQUI/$ARCHIVO"
    --host "$HOST_EFECTIVO"
    --csv "$SALIDA/$ID"
    --html "$SALIDA/$ID.html"
    --loglevel "${LT_LOGLEVEL:-WARNING}"
  )

  if [ "$USA_SHAPE" = "0" ]; then
    ARGS+=(
      -u "${LT_USUARIOS:-$DEF_U}"
      -r "${LT_SPAWN_RATE:-$DEF_R}"
      -t "${LT_DURACION:-$DEF_T}"
    )
  fi

  echo "[$ID] Ejecutando $ARCHIVO contra $HOST_EFECTIVO -> $SALIDA"
  (cd "$AQUI" && "$LOCUST_BIN" "${ARGS[@]}") || echo "[$ID] Finalizo con alertas/errores (ver $SALIDA)"
}

case "$(echo "$OBJETIVO" | tr '[:lower:]' '[:upper:]')" in
  P08|P09|P10|P11|P12|P13|P14|P15)
    correr_una "$(echo "$OBJETIVO" | tr '[:lower:]' '[:upper:]')"
    ;;
  SOLO)
    for id in P08 P09 P10 P13 P15; do
      correr_una "$id"
    done
    ;;
  INTEGRADO)
    for id in P11 P12 P14; do
      correr_una "$id"
    done
    ;;
  TODAS)
    for id in P08 P09 P10 P11 P12 P13 P14 P15; do
      correr_una "$id"
    done
    ;;
  *)
    echo "Uso: $0 <P08..P15|solo|integrado|todas>" >&2
    exit 2
    ;;
esac
