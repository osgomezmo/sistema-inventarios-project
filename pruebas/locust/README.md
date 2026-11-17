# Pruebas de rendimiento con Locust (bloque B: inventario)

Cinco pruebas, todas a través del gateway (`http://127.0.0.1:8000`):

| ID | Petición |
|---|---|
| B1 | `GET /api/stock/{sku}` |
| B2 | `GET /api/stock?bajo_minimo=true` |
| B3 | `POST /api/movimientos` (SALIDA de 1 unidad) |
| B4 | `POST /api/traslados` (1 unidad, alternando entre LT-B1 y LT-B2) |
| B5 | `GET /api/kardex` (LT-0001 en LT-B1, rango del día) |

Escenarios: **N** (20 usuarios, 5 por s, 5 min, pausa 1 a 3 s), **P** (50 usuarios,
10 por s, 5 min, pausa 1 a 3 s) y **E** (de 20 a 200 usuarios sumando 20 cada 30 s,
pausa 0,5 a 1,5 s; se detiene al llegar a 200 o con más de 5 % de errores).
Criterio en N y P: p95 menor a 2 s y menos de 1 % de errores. Un 409 cuenta como error.

## Requisitos

RabbitMQ, ms-productos, ms-inventario (app y consumidor) y el gateway arriba, en la red `redapi`.

```bash
cd pruebas/locust
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Preparar los datos

```bash
.venv/bin/python preparar_datos.py
```

Usa el administrador de `gateway/.env` y crea, si no existen: el usuario
`lt.jefe@ejemplo.invalid` (rol jefe_bodega, con su contraseña en `pruebas/locust/.env`,
que no se sube), 20 categorías, 2000 productos `LT-0001` a `LT-2000`, las bodegas
`LT-B1`, `LT-B2` y `LT-B3` y los saldos iniciales. Se puede repetir: solo completa lo
que falte (también repone los saldos que hayan bajado).

## Correr una prueba

```bash
./ejecutar.sh B3-N
```

Deja `B3-N_stats.csv`, `B3-N_stats_history.csv`, `B3-N_failures.csv` y `B3-N.html`
en `pruebas/resultados/B3-N/`. Los HTML no se suben al repositorio.
Para una corrida corta de prueba: `LT_USUARIOS=5 LT_DURACION=30s LT_SALIDA=/tmp/humo ./ejecutar.sh B1-N`.

## Correr las 15

```bash
for p in B1 B2 B3 B4 B5; do for e in N P E; do ./ejecutar.sh "$p-$e"; done; done
```

Tardan unos 80 minutos (5 min cada una, más pausas). Conviene volver a correr
`preparar_datos.py` antes de la serie.

## Limpiar

```bash
python3 limpiar_datos.py
```

Borra todo lo que empieza por `LT` o `lt.` en las bases de ms-inventario, ms-productos
y gateway, y muestra los conteos que quedan (deben ser 0).

## Notas

- El token se obtiene una sola vez al empezar y lo comparten todos los usuarios
  virtuales, porque el login permite 5 intentos por minuto.
- B3 y B4 publican `MovimientoRegistrado` en RabbitMQ; mientras ms-reportes no exista,
  esos mensajes se acumulan en `q.reportes`.
- B5 consulta el kardex del día de LT-0001; B3 y B4 le agregan movimientos, y el
  kardex admite como máximo 5000 movimientos por consulta.
