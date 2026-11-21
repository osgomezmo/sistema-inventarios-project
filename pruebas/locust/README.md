# Pruebas de rendimiento con Locust (bloques B y C)

Todas las pruebas pasan por el gateway (`http://127.0.0.1:8000`). Bloque B (seis pruebas):

| ID | Petición | Componentes |
|---|---|---|
| B1 | `GET /api/auth/me` | Gateway |
| B2 | `GET /api/productos?q=<término>` (términos variados: leche, arroz, jabon, LT-01...) | Gateway, ms-productos |
| B3 | `GET /api/stock/{sku}` | Gateway, ms-inventario |
| B4 | `POST /api/movimientos` (SALIDA de 1 unidad) | Gateway, ms-inventario, ms-productos, RabbitMQ |
| B5 | `POST /api/traslados` (1 unidad, alternando entre LT-B1 y LT-B2) | Gateway, ms-inventario, ms-productos, RabbitMQ |
| B6 | `GET /api/kardex` (LT-0001 en LT-B1, rango del día) | Gateway, ms-inventario |

El login no se somete a carga: tiene un límite de 5 intentos por minuto a propósito.

Bloque C:

| ID | Petición |
|---|---|
| C1 | `GET /api/dashboard` (Consulta de dashboard analítico) |
| C2 | `GET /api/reportes/valorizacion` (Reporte de valorización JSON) |
| C3 | `GET /api/reportes/valorizacion?formato=csv` (Reporte de valorización CSV) |
| C4 | `GET /api/reportes/rotacion` (Reporte de rotación de productos) |
| C5 | `GET /api/reportes/stock-bajo` (Reporte de alertas de stock bajo) |
| C6 | `POST /api/dispositivos` (Registro de dispositivo y token FCM) |
| C7 | `GET /api/notificaciones` (Listado paginado de notificaciones) |

Escenarios: **N** (20 usuarios, 5 por s, 5 min, pausa 1 a 3 s), **P** (50 usuarios,
10 por s, 5 min, pausa 1 a 3 s) y **E** (de 20 a 200 usuarios sumando 20 cada 30 s,
pausa 0,5 a 1,5 s; se detiene al llegar a 200 o con más de 5 % de errores).
Criterio en N y P: p95 menor a 2 s y menos de 1 % de errores. Un 409 cuenta como error.

## Para el docente: correr las pruebas desde cero

Las seis pruebas del bloque B se pueden correr desde la interfaz web de Locust, eligiéndolas de una lista:

| Clase en la interfaz | ID | Qué mide | Componentes |
|---|---|---|---|
| `B1AuthMe` | B1 | `GET /api/auth/me` | Gateway |
| `B2Productos` | B2 | `GET /api/productos?q=` (búsqueda) | Gateway, ms-productos |
| `B3Stock` | B3 | `GET /api/stock/{sku}` | Gateway, ms-inventario |
| `B4Movimientos` | B4 | `POST /api/movimientos` (salida de 1 unidad) | Gateway, ms-inventario, ms-productos, RabbitMQ |
| `B5Traslados` | B5 | `POST /api/traslados` (1 unidad) | Gateway, ms-inventario, ms-productos, RabbitMQ |
| `B6Kardex` | B6 | `GET /api/kardex` (un SKU, una bodega, el día) | Gateway, ms-inventario |

Se necesitan Docker (con Docker Compose) y Python 3.12. Todos los comandos se escriben desde la raíz del repositorio, salvo donde se indica otra carpeta.

1. **Clonar el repositorio** y entrar en la rama del proyecto:

   ```bash
   git clone <url-del-repositorio>
   cd <carpeta-del-repositorio>
   git checkout daniel
   ```

2. **Crear la red compartida** (una sola vez):

   ```bash
   docker network create redapi
   ```

3. **Copiar los archivos de configuración.** En Windows (PowerShell) se usa `Copy-Item` en lugar de `cp`.

   ```bash
   cp MS-Productos/.env.example MS-Productos/.env
   cp MS-Inventario/.env.example MS-Inventario/.env
   cp gateway/.env.example gateway/.env
   cp infra/rabbitmq/.env.example infra/rabbitmq/.env
   ```

   Luego hay que editarlos:

   - `SERVICE_TOKEN`: el **mismo** valor aleatorio en `MS-Productos/.env`, `MS-Inventario/.env` y `gateway/.env`. Los servicios no arrancan con el valor de ejemplo.
   - `DB_PASSWORD`: una contraseña cualquiera en cada servicio.
   - `infra/rabbitmq/.env`: un usuario y una contraseña para RabbitMQ.
   - `MS-Inventario/.env`: en `RABBITMQ_URL` van ese mismo usuario y esa misma contraseña.
   - `gateway/.env`: su propio `ADMIN_EMAIL`, `ADMIN_NOMBRE` y `ADMIN_PASSWORD`. Con ese administrador se crean los datos de prueba.

4. **Levantar los servicios**, en este orden:

   ```bash
   docker compose -f infra/rabbitmq/docker-compose.yml up -d
   docker compose -f MS-Productos/docker-compose.yml up -d --build
   docker compose -f MS-Inventario/docker-compose.yml up -d --build
   docker compose -f gateway/docker-compose.yml up -d --build
   ```

   Al arrancar, cada servicio crea sus tablas y sus datos iniciales. El gateway debe responder en http://127.0.0.1:8000/up.

5. **Preparar Python para las pruebas:**

   ```bash
   cd pruebas/locust
   python -m venv .venv
   ```

   - En Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   - En Linux o Mac: `source .venv/bin/activate`

   Después, en cualquier sistema:

   ```bash
   pip install -r requirements.txt
   ```

6. **Abrir la interfaz** (desde `pruebas/locust`, con el entorno activado):

   ```bash
   python interfaz.py
   ```

   El script comprueba que el gateway responda. Si faltan el usuario de prueba o los datos LT, los crea; eso tarda unos 3 minutos la primera vez. Después deja Locust escuchando. Con `python interfaz.py --estres` se agrega la forma de estrés, de 20 a 200 usuarios.

7. **Correr una prueba:**
   1. Abrir http://127.0.0.1:8089.
   2. En el selector, elegir una clase (por ejemplo `B3Stock`).
   3. Escribir el número de usuarios (por ejemplo 20) y la tasa de arranque (por ejemplo 5 por segundo).
   4. Pulsar **Start**.

   En las pestañas *Statistics* y *Charts* se ven las peticiones por segundo, los tiempos de respuesta (p50 y p95) y los errores. *Stop* detiene la prueba; con Ctrl+C en la terminal se cierra Locust.

8. **Limpiar al terminar:**

   ```bash
   python limpiar_datos.py
   ```

   Borra los datos de prueba (prefijos `LT` y `lt.`) y deja intactos los datos iniciales.

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
que no se sube), 20 categorías, 2000 productos `LT-0001` a `LT-2000` (con nombres
como "Leche LT 0001" o "Arroz LT 0002", para que B2 encuentre coincidencias), las bodegas
`LT-B1`, `LT-B2` y `LT-B3` y los saldos iniciales. Se puede repetir: solo completa lo
que falte (también repone los saldos que hayan bajado).

## Correr una prueba

```bash
./ejecutar.sh B3-N
```

Deja `B3-N_stats.csv`, `B3-N_stats_history.csv`, `B3-N_failures.csv` y `B3-N.html`
en `pruebas/resultados/B3-N/`. Los HTML no se suben al repositorio.
Para una corrida corta de prueba: `LT_USUARIOS=5 LT_DURACION=30s LT_SALIDA=/tmp/humo ./ejecutar.sh B1-N`.

## Correr las 18 del bloque B

```bash
for p in B1 B2 B3 B4 B5 B6; do for e in N P E; do ./ejecutar.sh "$p-$e"; sleep 20; done; done
```

Tardan unos 97 minutos (5 min cada una, más 20 s de pausa entre pruebas). Conviene volver a correr
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
- B4 y B5 publican `MovimientoRegistrado` en RabbitMQ; si nadie consume `q.reportes`,
  esos mensajes se acumulan ahí.
- B6 consulta el kardex del día de LT-0001; B4 y B5 le agregan movimientos, y el
  kardex admite como máximo 5000 movimientos por consulta.
