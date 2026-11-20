# Pruebas de Rendimiento con Locust - MS-Proveedores (P01 a P07)

Suite de 7 pruebas de rendimiento independientes para el microservicio `MS-Proveedores` (Node.js 24 + Express 4 + MySQL 8.4), diseñada siguiendo exactamente la metodologia, taxonomia y criterios del taller *Pruebas de rendimiento con Locust* (`locust_test.pdf`, Docente Albeiro Montes).

Esta carpeta compone las pruebas **P01 a P07** de la suite consolidada de 15 pruebas de `proveedores_compras` (complementada por **P08 a P15** en `../ms_compras/`).

---

## 1. Taxonomia de pruebas aplicada (segun `locust_test.pdf`)

El material del curso define tres tipologias oficiales de pruebas de rendimiento (diapositivas 3, 5-7, 16 y 20):

| Tipologia oficial | Definicion y proposito | Pruebas en MS-Proveedores |
|---|---|---|
| **Carga** | Trafico esperado (o ligeramente superior) de forma sostenida en meseta. Mezcla de GET predominante y escrituras minoritarias o flujos nominales. Verifica cumplimiento de SLAs (latencia p95 y tasa de error). | **P01, P02, P03, P04** |
| **Estres** | Incremento progresivo de carga mas alla del diseno nominal mediante rampa agresiva (`LoadTestShape`). Identifica el punto de degradacion y quiebre (timeouts, 5xx), registrando concurrencia y RPS en el quiebre. | **P05, P06** |
| **Capacidad (soak)** | Carga alta sostenida cercana al maximo estable (no al quiebre) durante un periodo prolongado (orientativo 60 min o mas). Detecta degradacion gradual (memoria Node.js, pool `mysql2`, I/O) y deriva temporal. | **P07** |

---

## 2. Arquitectura evaluada y contrato real de `MS-Proveedores`

- **URL standalone por defecto**: `http://127.0.0.1:5003` (puerto contenedor `3001` mapeado a `5003` en `MS-Proveedores/docker-compose.yml`).
- **Base de datos dedicada**: MySQL 8.4 con `--innodb-buffer-pool-size=32M --performance-schema=OFF --max-connections=50`.
- **Pool de conexiones**: `mysql2/promise` con `connectionLimit: 10`, `waitForConnections: true`, `connectTimeout: 5000`.
- **Autenticacion real (`src/middlewares/auth.js`)**:
  - Rutas publicas: `GET /health` y `GET /health/ready`.
  - Rutas de negocio (`/proveedores/**`): exigen `Authorization: Bearer <SERVICE_TOKEN>` (valor por defecto en `docker-compose.yml`: `token-servicio-inventarios-2026-vm`).
  - Cabeceras de contexto y trazabilidad enviadas en cada peticion: `Authorization`, `X-Service-Token`, `X-User-Id`, `X-User-Role` (`admin`, `compras`, `jefe_bodega`, `gerente`) y `X-Correlation-Id` (`lt-pXX-<uuid4>`).
- **Rutas reales cubiertas**:
  - `GET /health`, `GET /health/ready`
  - `GET /proveedores` (`?page=`, `?per_page=`, `?estado=`, `?q=`, `?sku=`)
  - `GET /proveedores/{id}`
  - `POST /proveedores` (simple y transaccional con `contactos` y `productos`)
  - `PUT /proveedores/{id}`
  - `POST /proveedores/{id}/inactivar` y `POST /proveedores/{id}/activar`
  - `POST /proveedores/{id}/contactos`, `PUT /proveedores/{id}/contactos/{id_contacto}`, `DELETE /proveedores/{id}/contactos/{id_contacto}`
  - `GET /proveedores/{id}/productos`, `PUT /proveedores/{id}/productos/{sku}`, `DELETE /proveedores/{id}/productos/{sku}`
- **Generacion de NIT colombiano (DIAN) sin colisiones**:
  - `comun.py` implementa el calculo oficial DIAN modulo 11 (`calcular_dv_dian`) con pesos `[3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71]` y formato `X.XXX.XXX.XXX.XXX-DV`.
  - Combina semilla temporal de corrida + PID + contador protegido por `threading.Lock`, evitando falsos `409 NIT_DUPLICADO` bajo alta concurrencia o ejecuciones consecutivas. Cualquier `409` o `422` inesperado se marca explicitamente como fallo (`response.failure`), cumpliendo la advertencia de la diapositiva 19 de `locust_test.pdf`.

---

## 3. Levantamiento aislado de `MS-Proveedores` y verificacion previa

Antes de ejecutar Locust, levanta `MS-Proveedores` en solitario con su propio MySQL 8.4 (Paso 3 de `locust_test.pdf`):

```bash
cd MS-Proveedores
docker compose up -d
```

Verifica que el servicio y la base de datos semilla (5 proveedores y 33 productos suministrados) respondan correctamente antes de iniciar carga:

```bash
# 1. Salud del servicio y conexion a MySQL
curl -s http://127.0.0.1:5003/health
curl -s http://127.0.0.1:5003/health/ready

# 2. Listado paginado con token de servicio por defecto
curl -s "http://127.0.0.1:5003/proveedores?page=1&per_page=10" \
  -H "Authorization: Bearer token-servicio-inventarios-2026-vm" \
  -H "X-User-Id: 1" \
  -H "X-User-Role: admin" \
  -H "X-Correlation-Id: check-manual-01"
```

Para instalar Locust en un entorno virtual aislado (desde `pruebas/locust/proveedores_compras/`):

```bash
python -m venv .venv
# Linux / macOS:
.venv/bin/pip install -r requirements.txt
# Windows PowerShell:
.\.venv\Scripts\pip.exe install -r requirements.txt
```

---

## 4. Resumen de las 7 pruebas (P01 a P07)

| ID | Archivo | Tipo PDF | Endpoints principales | Usuarios (`-u`) | Spawn (`-r`) | Duracion (`-t`) | `wait_time` | Criterio SLO / Objetivo |
|---|---|---|---|---|---|---|---|---|
| **P01** | `p01_carga_lectura.py` | Carga | `GET /proveedores` (`estado`, `q`, `sku`), `GET /proveedores/{id}`, `GET /proveedores/{id}/productos`, `GET /health/ready` | 25 | 5 u/s | 5m (10-30m formal) | 1.0 - 3.0 s | `p95 < 300 ms`, errores `< 1%` |
| **P02** | `p02_carga_mixta.py` | Carga | Mezcla ~82% GET (`proveedores`, `/{id}`, `/{id}/productos`) + ~18% `POST /proveedores`, `PUT /proveedores/{id}` | 30 | 5 u/s | 5m (10-30m formal) | 1.0 - 3.0 s | `p95 < 500 ms`, errores `< 1%` |
| **P03** | `p03_carga_ciclo_vida.py` | Carga | Flujo secuencial: `POST /proveedores` -> `GET` -> `PUT` -> `POST/PUT/DELETE /contactos` -> `inactivar` -> `activar` | 20 | 4 u/s | 5m | 1.0 - 2.5 s | `p95 < 600 ms`, errores `< 1%` |
| **P04** | `p04_carga_productos.py` | Carga | `GET /{id}/productos`, `GET /proveedores?sku=`, `PUT /{id}/productos/{sku}` (upsert), `DELETE /{id}/productos/{sku}` | 25 | 5 u/s | 5m | 0.8 - 2.0 s | `p95 < 500 ms`, errores `< 1%` |
| **P05** | `p05_estres_lectura.py` | Estres | `GET /proveedores?q=` (LIKE), `GET /proveedores?sku=` (EXISTS), `GET /{id}`, `GET /{id}/productos` | Rampa 20 -> 200 | +20 / 30 s | Max 5m (corte >5% err) | 0.3 - 1.0 s | Registrar concurrencia y RPS de degradacion/quiebre |
| **P06** | `p06_estres_escritura.py` | Estres | `POST /proveedores` (transaccional), `PUT /{id}/productos/{sku}`, `POST /{id}/contactos`, `PUT /{id}`, `GET /{id}` | Rampa 15 -> 150 | +15 / 30 s | Max 5m (corte >5% err) | 0.2 - 0.8 s | Registrar quiebre del pool MySQL (10 conns) / InnoDB |
| **P07** | `p07_capacidad_soak.py` | Capacidad (soak) | Mezcla completa con reciclaje de SKUs y limpieza de contactos + `/health` y `/health/ready` | 40 | 5 u/s | 15m local / `60m` formal | 1.0 - 2.5 s | `p95 < 700 ms`, deriva p95 `< 20%`, errores `< 1%` |

---

## 5. Detalle individual y comandos de ejecucion

### Variables de entorno soportadas

| Variable | Alias | Valor por defecto | Descripcion |
|---|---|---|---|
| `LT_HOST` | `HOST` | `http://127.0.0.1:5003` | URL base de `MS-Proveedores` |
| `LT_SERVICE_TOKEN` | `SERVICE_TOKEN` | `token-servicio-inventarios-2026-vm` | Token de servicio para `Authorization: Bearer` |
| `LT_USER_ID` | - | `1` | Cabecera `X-User-Id` |
| `LT_USER_ROLE` | - | `admin` | Cabecera `X-User-Role` por defecto |
| `LT_USUARIOS` | - | Segun perfil | Sobrescribe `-u` en P01..P04 y P07 |
| `LT_SPAWN_RATE` | - | Segun perfil | Sobrescribe `-r` en P01..P04 y P07 |
| `LT_DURACION` | - | Segun perfil | Sobrescribe `-t` (ej. `10m`, `30m`, `60m`) |
| `LT_PAUSA_MIN` / `LT_PAUSA_MAX` | - | Segun perfil | Sobrescribe rango de `wait_time` en segundos |
| `LT_PASO_USUARIOS` / `LT_PASO_SEGUNDOS` / `LT_MAX_USUARIOS` / `LT_LIMITE_ERRORES` | - | P05: 20/30s/200/0.05; P06: 15/30s/150/0.05 | Parametros de `LoadTestShape` en estres |
| `LT_SALIDA` | - | `pruebas/resultados/proveedores_compras` | Carpeta destino de CSV y HTML |

### Ejecucion rapida con los runners incluidos

Desde `pruebas/locust/proveedores_compras/ms_proveedores/`:

```bash
# Bash (Linux / macOS / Git Bash)
./ejecutar.sh P01
./ejecutar.sh P05
LT_DURACION=60m ./ejecutar.sh P07
./ejecutar.sh P02 --ui
./ejecutar.sh TODAS --humo

# Python multiplataforma (Windows PowerShell / Linux / macOS)
python ejecutar.py P01
python ejecutar.py P06 --humo
python ejecutar.py P07 --duracion 60m
python ejecutar.py P03 --ui
python ejecutar.py TODAS --humo
```

### Comandos directos de Locust por prueba (Headless y Web UI)

Todos los comandos headless exportan `*_stats.csv`, `*_stats_history.csv`, `*_failures.csv` y `*.html`.

#### P01 - Carga: Lectura nominal del catalogo
- **Headless**:
  ```bash
  locust -f p01_carga_lectura.py --headless --host http://127.0.0.1:5003 -u 25 -r 5 -t 5m --csv ../../../resultados/proveedores_compras/P01/P01 --html ../../../resultados/proveedores_compras/P01/P01.html
  ```
- **Web UI**:
  ```bash
  locust -f p01_carga_lectura.py --host http://127.0.0.1:5003
  ```

#### P02 - Carga: Operacion diaria mixta (82% GET / 18% POST-PUT)
- **Headless**:
  ```bash
  locust -f p02_carga_mixta.py --headless --host http://127.0.0.1:5003 -u 30 -r 5 -t 5m --csv ../../../resultados/proveedores_compras/P02/P02 --html ../../../resultados/proveedores_compras/P02/P02.html
  ```
- **Web UI**:
  ```bash
  locust -f p02_carga_mixta.py --host http://127.0.0.1:5003
  ```

#### P03 - Carga: Ciclo de vida completo de proveedor y contactos
- **Headless**:
  ```bash
  locust -f p03_carga_ciclo_vida.py --headless --host http://127.0.0.1:5003 -u 20 -r 4 -t 5m --csv ../../../resultados/proveedores_compras/P03/P03 --html ../../../resultados/proveedores_compras/P03/P03.html
  ```
- **Web UI**:
  ```bash
  locust -f p03_carga_ciclo_vida.py --host http://127.0.0.1:5003
  ```

#### P04 - Carga: Catalogo transaccional de productos suministrados
- **Headless**:
  ```bash
  locust -f p04_carga_productos.py --headless --host http://127.0.0.1:5003 -u 25 -r 5 -t 5m --csv ../../../resultados/proveedores_compras/P04/P04 --html ../../../resultados/proveedores_compras/P04/P04.html
  ```
- **Web UI**:
  ```bash
  locust -f p04_carga_productos.py --host http://127.0.0.1:5003
  ```

#### P05 - Estres: Busqueda con filtros LIKE/EXISTS (rampa 20 -> 200 usuarios)
- **Headless** (`LoadTestShape` controla usuarios, spawn rate y corte al superar 5% de errores):
  ```bash
  locust -f p05_estres_lectura.py --headless --host http://127.0.0.1:5003 --csv ../../../resultados/proveedores_compras/P05/P05 --html ../../../resultados/proveedores_compras/P05/P05.html
  ```
- **Web UI**:
  ```bash
  locust -f p05_estres_lectura.py --host http://127.0.0.1:5003
  ```

#### P06 - Estres: Escrituras transaccionales concurrentes (rampa 15 -> 150 usuarios)
- **Headless** (`LoadTestShape` controla usuarios, spawn rate y corte al superar 5% de errores):
  ```bash
  locust -f p06_estres_escritura.py --headless --host http://127.0.0.1:5003 --csv ../../../resultados/proveedores_compras/P06/P06 --html ../../../resultados/proveedores_compras/P06/P06.html
  ```
- **Web UI**:
  ```bash
  locust -f p06_estres_escritura.py --host http://127.0.0.1:5003
  ```

#### P07 - Capacidad (soak): Resistencia sostenida en el tiempo
- **Headless (validacion 15m / corrida soak formal 60m)**:
  ```bash
  locust -f p07_capacidad_soak.py --headless --host http://127.0.0.1:5003 -u 40 -r 5 -t 60m --csv ../../../resultados/proveedores_compras/P07/P07 --html ../../../resultados/proveedores_compras/P07/P07.html
  ```
- **Web UI**:
  ```bash
  locust -f p07_capacidad_soak.py --host http://127.0.0.1:5003
  ```

#### Punto de entrada unificado (`locustfile.py`)
Para abrir todas las clases de usuario en la interfaz web con selector de clases o filtrar por etiqueta:

```bash
locust -f locustfile.py --host http://127.0.0.1:5003 --class-picker
locust -f locustfile.py --headless --host http://127.0.0.1:5003 --tags p02 -u 30 -r 5 -t 5m
```

---

## 6. Metricas a registrar en el informe (segun diapositiva 18 de `locust_test.pdf`)

Para cada ejecucion P01..P07 se deben documentar:

1. **Por operacion HTTP** (tomados de `*_stats.csv` y reporte HTML):
   - Percentiles de latencia (`p50`, `p95`, `p99`, promedio y maximo).
   - Peticiones totales y throughput (`RPS`).
   - Porcentaje de fallos y desglose de errores (`*_failures.csv`: 4xx, 5xx, timeouts).
2. **Entorno y contexto**:
   - Uso de CPU y RAM de los contenedores `ms-proveedores-app` y `ms-proveedores-mysql` (`docker stats --no-stream ms-proveedores-app ms-proveedores-mysql`).
   - Motor y tamano del dataset (MySQL 8.4, 5 proveedores semilla + registros acumulados).
   - Version de Locust (`locust --version`), parametros exactos (`-u`, `-r`, `-t`, `--host`) y estado de la paginacion (`per_page` acotado a `1..100` en `src/utils/paginacion.js`).

---

## 7. Limpieza de datos generados por las pruebas

Las pruebas P02, P03, P04, P06 y P07 insertan proveedores sintéticos con prefijo `Proveedor P0X ...` y NITs generados dinamicamente. Para restaurar el estado limpio de la base standalone de `MS-Proveedores`:

```bash
cd MS-Proveedores
docker compose down -v
docker compose up -d
```
