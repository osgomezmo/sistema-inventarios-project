# Resultados preliminares de rendimiento: bloque B

## Datos de la corrida

| Dato | Valor |
|---|---|
| Fecha | 21/11/2026, de 16:40 a 18:02 (hora de Colombia) |
| Entorno | Docker Compose local: gateway, ms-productos, ms-inventario (app y consumidor), RabbitMQ y un MySQL por servicio, en la misma máquina que Locust |
| Equipo | AMD Ryzen 7 5700U (8 núcleos, 16 hilos), 17 GiB de RAM |
| Datos | Datos iniciales de los servicios más los datos de prueba LT: 2000 productos, 3 bodegas y 2050 saldos |
| Herramienta | Locust 2.47.0, sin interfaz (`--headless`) |
| Código probado | commit `3b9f076` de la rama `daniel` |
| Usuario de prueba | `lt.jefe@ejemplo.invalid` (rol jefe_bodega); un solo token compartido por todos los usuarios virtuales |

**Escenarios:** Normal (N): 20 usuarios, 5 por segundo, 5 min, pausa de 1 a 3 s. Pico (P): 50 usuarios, 10 por segundo, 5 min, pausa de 1 a 3 s. Estrés (E): de 20 a 200 usuarios sumando 20 cada 30 s, pausa de 0,5 a 1,5 s; se detiene al llegar a 200 o si los errores superan el 5 %.

**Criterio de aprobación (N y P):** p95 menor a 2 s y menos de 1 % de errores. Un 409 cuenta como error.

## Resultados

Tiempos en milisegundos. En estrés, "usuarios" es el máximo que alcanzó la prueba antes de detenerse.

| ID | Endpoint | Componentes | Escenario | Usuarios | Peticiones | Pet/s | p50 | p95 | p99 | Errores | Cumple |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1-N | `GET /api/auth/me` | Gateway | Normal | 20 | 2.929 | 9,8 | 30 | 41 | 59 | 0,00 % | Sí |
| B1-P | `GET /api/auth/me` | Gateway | Pico | 50 | 7.287 | 24,3 | 31 | 39 | 59 | 0,00 % | Sí |
| B1-E | `GET /api/auth/me` | Gateway | Estrés | hasta 200 | 29.574 | 98,4 | 23 | 38 | 68 | 0,00 % | No aplica |
| B2-N | `GET /api/productos?q=` | Gateway, ms-productos | Normal | 20 | 2.836 | 9,5 | 86 | 150 | 200 | 0,00 % | Sí |
| B2-P | `GET /api/productos?q=` | Gateway, ms-productos | Pico | 50 | 6.678 | 22,3 | 170 | 510 | 770 | 0,00 % | Sí |
| B2-E | `GET /api/productos?q=` | Gateway, ms-productos | Estrés | hasta 120 | 6.165 | 39,7 | 580 | 1.100 | 1.400 | 5,04 % | No aplica |
| B3-N | `GET /api/stock/{sku}` | Gateway, ms-inventario | Normal | 20 | 2.846 | 9,5 | 78 | 130 | 180 | 0,00 % | Sí |
| B3-P | `GET /api/stock/{sku}` | Gateway, ms-inventario | Pico | 50 | 6.869 | 22,9 | 130 | 360 | 570 | 0,00 % | Sí |
| B3-E | `GET /api/stock/{sku}` | Gateway, ms-inventario | Estrés | hasta 100 | 5.104 | 37,1 | 330 | 1.500 | 2.000 | 5,11 % | No aplica |
| B4-N | `POST /api/movimientos` (SALIDA) | Gateway, ms-inventario, ms-productos, RabbitMQ | Normal | 20 | 2.444 | 8,2 | 380 | 770 | 2.800 | 0,00 % | Sí |
| B4-P | `POST /api/movimientos` (SALIDA) | Gateway, ms-inventario, ms-productos, RabbitMQ | Pico | 50 | 2.934 | 9,8 | 3.100 | 5.000 | 5.100 | 8,21 % | **No** |
| B4-E | `POST /api/movimientos` (SALIDA) | Gateway, ms-inventario, ms-productos, RabbitMQ | Estrés | hasta 80 | 1.174 | 12,6 | 2.000 | 4.300 | 4.900 | 6,64 % | No aplica |
| B5-N | `POST /api/traslados` | Gateway, ms-inventario, ms-productos, RabbitMQ | Normal | 20 | 2.284 | 7,6 | 300 | 2.200 | 2.900 | 0,00 % | **No** |
| B5-P | `POST /api/traslados` | Gateway, ms-inventario, ms-productos, RabbitMQ | Pico | 50 | 4.578 | 15,3 | 1.100 | 2.300 | 5.000 | 1,68 % | **No** |
| B5-E | `POST /api/traslados` | Gateway, ms-inventario, ms-productos, RabbitMQ | Estrés | hasta 60 | 1.300 | 15,5 | 1.400 | 4.400 | 5.000 | 5,15 % | No aplica |
| B6-N | `GET /api/kardex` | Gateway, ms-inventario | Normal | 20 | 2.869 | 9,6 | 39 | 69 | 2.200 | 0,00 % | Sí |
| B6-P | `GET /api/kardex` | Gateway, ms-inventario | Pico | 50 | 7.235 | 24,2 | 44 | 100 | 230 | 0,00 % | Sí |
| B6-E | `GET /api/kardex` | Gateway, ms-inventario | Estrés | hasta 120 | 6.417 | 41,1 | 440 | 1.100 | 1.200 | 5,17 % | No aplica |

**Cumplen el criterio 9 de las 12 corridas N y P.** No cumplen B4-P (p95 de 5.000 ms y 8,21 % de errores), B5-N (p95 de 2.200 ms) y B5-P (p95 de 2.300 ms y 1,68 % de errores).

## Punto de quiebre en estrés

Punto de quiebre: primer nivel de usuarios en que el p95 supera 2 s durante 5 muestras seguidas o los errores acumulados superan el 5 %.

| Prueba | Punto de quiebre | Primer error | Detalle |
|---|---|---|---|
| B1-E | No se rompió hasta 200 usuarios | Ninguno | 0 errores; p95 de 38 ms |
| B2-E | 120 usuarios (errores mayores a 5 %) | Con 80 usuarios | Se detuvo con 5,04 % de errores |
| B3-E | 100 usuarios (errores mayores a 5 %) | Con 80 usuarios | Se detuvo con 5,11 % de errores |
| B4-E | 20 usuarios (p95 mayor a 2 s desde el primer escalón) | Con 60 usuarios | Se detuvo con 80 usuarios y 6,64 % de errores |
| B5-E | 60 usuarios (p95 mayor a 2 s sostenido) | Con 60 usuarios | Se detuvo con 60 usuarios y 5,15 % de errores |
| B6-E | 120 usuarios (errores mayores a 5 %) | Con 100 usuarios | Se detuvo con 5,17 % de errores |

## Errores registrados

Según los archivos `*_failures.csv`:

- HTTP 500: B2-E (311), B3-E (261), B4-E (78), B5-E (27) y B6-E (332).
- HTTP 503: B4-P (241), B5-P (77) y B5-E (40).
- Ninguna corrida tuvo errores 409.

## Cuánto tiempo agrega cada capa

Mediana (p50) en el escenario normal:

| Prueba | Recorrido | p50 | Diferencia con B1 |
|---|---|---|---|
| B1 | Solo gateway (token y usuario) | 30 ms | — |
| B2 | Gateway y ms-productos (búsqueda) | 86 ms | +56 ms |
| B3 | Gateway y ms-inventario (saldo por SKU) | 78 ms | +48 ms |
| B4 | Gateway, ms-inventario, ms-productos y RabbitMQ (salida) | 380 ms | +350 ms |

Una lectura que pasa por un microservicio suma unos 50 ms al gateway. La salida suma unos 350 ms: además de la escritura, consulta a ms-productos y publica en RabbitMQ.

## Observaciones

1. Las lecturas cumplen en normal y pico. B1, B2, B3 y B6 tienen 0 errores y p95 de 510 ms o menos con 50 usuarios.
2. El gateway solo (B1) escala sin degradarse: pasa de 9,8 a 98,4 peticiones por segundo entre 20 y 200 usuarios, con p95 de 38 a 41 ms y 0 errores.
3. Las lecturas que pasan por un microservicio (B2, B3 y B6) empiezan a fallar entre 80 y 100 usuarios y se detienen entre 100 y 120 por errores 500.
4. Las escrituras son el cuello de botella. B4 casi no aumenta su rendimiento al pasar de 20 a 50 usuarios (de 8,2 a 9,8 peticiones por segundo), mientras su p95 sube de 770 ms a 5.000 ms. En B4-P aparecen 241 errores 503.
5. El traslado (B5) es la operación más lenta: su p95 ya supera 2 s con 20 usuarios (2.200 ms).
6. El kardex (B6) es la lectura más rápida después de B1: p50 de 39 ms con 20 usuarios y de 44 ms con 50.

## Nota

Son resultados **preliminares** de una sola corrida por prueba. En la Entrega 4 cada prueba se repetirá 3 veces y se reportará la mediana, en el mismo entorno, para comparar antes y después de las optimizaciones.
