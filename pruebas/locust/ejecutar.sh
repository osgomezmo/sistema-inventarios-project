#!/usr/bin/env bash
# Corre una prueba del bloque B o C: ./ejecutar.sh B3-N o ./ejecutar.sh C1-N
# Resultados en pruebas/resultados/<ID>/ (CSV y HTML).
# Variables opcionales: LT_HOST (gateway), LT_SALIDA (carpeta base de resultados),
# LT_USUARIOS y LT_DURACION (sobrescriben N y P, por ejemplo para una corrida de humo).
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
ID="${1:-}"
if [[ ! "$ID" =~ ^([BC])([1-7])-([NPE])$ ]]; then
  echo "Uso: $0 <ID>   ID = B1..B5 o C1..C7 seguido de -N, -P o -E (por ejemplo B3-N o C1-N)" >&2
  exit 2
fi
BLOQUE="${BASH_REMATCH[1]}"
NUMERO="${BASH_REMATCH[2]}"
PRUEBA="$(echo "${BLOQUE}${NUMERO}" | tr '[:upper:]' '[:lower:]')"
ESCENARIO="${BASH_REMATCH[3]}"
HOST="${LT_HOST:-http://127.0.0.1:8000}"
SALIDA="${LT_SALIDA:-$AQUI/../resultados}/$ID"
mkdir -p "$SALIDA"

if [ "$BLOQUE" = "B" ]; then
  ARCHIVO_LOCUST="$AQUI/bloque_b.py"
else
  ARCHIVO_LOCUST="$AQUI/bloque_c.py"
fi

ARGS=(--headless --host "$HOST" --tags "$PRUEBA" --csv "$SALIDA/$ID" --html "$SALIDA/$ID.html" --loglevel WARNING)
case "$ESCENARIO" in
  N) export LT_PAUSA_MIN=1 LT_PAUSA_MAX=3
     ARGS+=(-f "$ARCHIVO_LOCUST" -u "${LT_USUARIOS:-20}" -r 5 -t "${LT_DURACION:-5m}") ;;
  P) export LT_PAUSA_MIN=1 LT_PAUSA_MAX=3
     ARGS+=(-f "$ARCHIVO_LOCUST" -u "${LT_USUARIOS:-50}" -r 10 -t "${LT_DURACION:-5m}") ;;
  E) export LT_PAUSA_MIN=0.5 LT_PAUSA_MAX=1.5
     ARGS+=(-f "$ARCHIVO_LOCUST,$AQUI/forma_estres.py") ;;
esac

echo "$ID: prueba $PRUEBA, escenario $ESCENARIO, resultados en $SALIDA"
"$AQUI/.venv/bin/locust" "${ARGS[@]}" || echo "$ID: terminó con errores (ver $SALIDA)"
