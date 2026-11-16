#!/usr/bin/env bash
# Corre una prueba del bloque B: ./ejecutar.sh B3-N  (B1..B5 y N, P o E)
# Resultados en pruebas/resultados/<ID>/ (CSV y HTML).
# Variables opcionales: LT_HOST (gateway), LT_SALIDA (carpeta base de resultados),
# LT_USUARIOS y LT_DURACION (sobrescriben N y P, por ejemplo para una corrida de humo).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
ID="${1:-}"
if [[ ! "$ID" =~ ^B([1-5])-([NPE])$ ]]; then
  echo "Uso: $0 <ID>   ID = B1..B5 seguido de -N, -P o -E (por ejemplo B3-N)" >&2
  exit 2
fi
PRUEBA="b${BASH_REMATCH[1]}"
ESCENARIO="${BASH_REMATCH[2]}"
HOST="${LT_HOST:-http://127.0.0.1:8000}"
SALIDA="${LT_SALIDA:-$AQUI/../resultados}/$ID"
mkdir -p "$SALIDA"

ARGS=(--headless --host "$HOST" --tags "$PRUEBA" --csv "$SALIDA/$ID" --html "$SALIDA/$ID.html" --loglevel WARNING)
case "$ESCENARIO" in
  N) export LT_PAUSA_MIN=1 LT_PAUSA_MAX=3
     ARGS+=(-f "$AQUI/bloque_b.py" -u "${LT_USUARIOS:-20}" -r 5 -t "${LT_DURACION:-5m}") ;;
  P) export LT_PAUSA_MIN=1 LT_PAUSA_MAX=3
     ARGS+=(-f "$AQUI/bloque_b.py" -u "${LT_USUARIOS:-50}" -r 10 -t "${LT_DURACION:-5m}") ;;
  E) export LT_PAUSA_MIN=0.5 LT_PAUSA_MAX=1.5
     ARGS+=(-f "$AQUI/bloque_b.py,$AQUI/forma_estres.py") ;;
esac

echo "$ID: prueba $PRUEBA, escenario $ESCENARIO, resultados en $SALIDA"
# Locust sale con código 1 si hubo errores; eso no detiene la serie de pruebas
"$AQUI/.venv/bin/locust" "${ARGS[@]}" || echo "$ID: terminó con errores (ver $SALIDA)"
