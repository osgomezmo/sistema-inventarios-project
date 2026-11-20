# Suite de Pruebas de Rendimiento con Locust - MS-Proveedores y MS-Compras (P01 a P15)

Conjunto consolidado de **15 pruebas de rendimiento** implementadas con **Locust** para los microservicios `MS-Proveedores` (7 pruebas: `P01` a `P07`) y `MS-Compras` (8 pruebas: `P08` a `P15`), siguiendo la taxonomia, parametros y metodologia del taller `locust_test.pdf` (Docente Albeiro Montes, Ingenieria de Software II).

## 1. Taxonomia de pruebas segun `locust_test.pdf`

El taller define exactamente tres tipologias de pruebas de rendimiento sobre servicios REST (diapositivas 3, 5, 6, 7, 16 y 20), todas cubiertas en ambos microservicios:

1. **Carga (`Carga`)**: Comportamiento nominal. Trafico esperado (o ligeramente superior) de forma sostenida en meseta, con mezcla de operaciones GET predominantes y escrituras minoritarias, validando SLAs de latencia (`p95`) y tasa de error. Duracion orientativa: 10-30 min en regimen estable (configurable por variables de entorno).
2. **Estres (`Estres`)**: Limite del sistema. Incremento progresivo de carga mas alla del diseno nominal mediante rampa escalonada (`LoadTestShape`), con corte automatico cuando la tasa de fallos supera el 5%, para identificar el punto de degradacion/quiebre y registrar concurrencia, RPS y tipo de fallo (timeouts, `5xx`, saturacion de pool MySQL/hilos).
3. **Capacidad / Soak (`Capacidad (soak)`)**: Resistencia en el tiempo. Carga alta sostenida cercana al maximo estable (sin alcanzar el punto de quiebre) durante un periodo prolongado (orientativamente 60 min o mas) para detectar degradacion gradual de memoria, pool de conexiones, I/O y deriva temporal de latencia.

Distribucion equilibrada de la suite:
- **Carga**: 9 pruebas (`P01`-`P04` en `MS-Proveedores`; `P08`-`P12` en `MS-Compras`).
- **Estres**: 4 pruebas (`P05`-`P06` en `MS-Proveedores`; `P13`-`P14` en `MS-Compras`).
- **Capacidad (soak)**: 2 pruebas (`P07` en `MS-Proveedores`; `P15` en `MS-Compras`).
- **Total**: **15 pruebas** (7 en `MS-Proveedores` + 8 en `MS-Compras`).

## 2. Estructura de carpetas

```text
pruebas/locust/proveedores_compras/
├── README.md                              # Esta guia consolidada (P01..P15)
├── requirements.txt                       # Dependencias Python (locust==2.47.0, requests)
├── ms_proveedores/                        # 7 pruebas para MS-Proveedores (puerto 5003)
│   ├── README.md
│   ├── comun.py
│   ├── locustfile.py
│   ├── ejecutar.sh                        # Runner Bash (LF)
│   ├── ejecutar.py                        # Runner multiplataforma
│   ├── p01_carga_lectura.py
│   ├── p02_carga_mixta.py
│   ├── p03_carga_ciclo_vida.py
│   ├── p04_carga_productos.py
│   ├── p05_estres_lectura.py
│   ├── p06_estres_escritura.py
│   └── p07_capacidad_soak.py
└── ms_compras/                            # 8 pruebas para MS-Compras (puerto 5004)
    ├── README.md
    ├── common.py
    ├── mock_proveedores.py                # Stub HTTP opcional para aislar MS-Proveedores
    ├── ejecutar.sh                        # Runner Bash (LF)
    ├── ejecutar.py                        # Runner multiplataforma
    ├── p08_carga_ordenes.py
    ├── p09_carga_devoluciones.py
    ├── p10_carga_validacion.py
    ├── p11_carga_mixta.py
    ├── p12_carga_ciclo_completo.py
    ├── p13_estres_lecturas.py
    ├── p14_estres_escrituras.py
    └── p15_capacidad_soak.py
```

## 3. Indice consolidado de las 15 pruebas (P01 a P15)

### 3.1 Bloque MS-Proveedores (P01 a P07) - `http://127.0.0.1:5003`

Todas las pruebas de `MS-Proveedores` corren **100% SOLO** (unicamente `MS-Proveedores` + su MySQL 8.4), usando `Authorization: Bearer <SERVICE_TOKEN>` (mas `X-Service-Token`, `X-User-Id`, `X-User-Role`, `X-Correlation-Id`), NITs DIAN validos con digito de verificacion modulo 11 y rutas reales (`POST /proveedores/:id/inactivar` y `POST /proveedores/:id/activar`).

| ID | Archivo | Tipo (`locust_test.pdf`) | Modo | Perfil por defecto | Operaciones principales y SLO |
|---|---|---|---|---|---|
| P01 | `ms_proveedores/p01_carga_lectura.py` | Carga | Solo | 25u, 5/s, 5m (pausa 1-3s) | Lectura paginada, filtros `estado`/`q`/`sku`, detalle `/{id}`, `/{id}/productos`, `/health/ready`. SLO: `p95 < 300 ms`, err `< 1%`. |
| P02 | `ms_proveedores/p02_carga_mixta.py` | Carga | Solo | 30u, 5/s, 5m (pausa 1-3s) | Mezcla 82% GET + 18% `POST /proveedores` y `PUT /proveedores/{id}` con NIT DIAN unico. SLO: `p95 < 500 ms`, err `< 1%`. |
| P03 | `ms_proveedores/p03_carga_ciclo_vida.py` | Carga | Solo | 20u, 4/s, 5m (pausa 1-2.5s) | `SequentialTaskSet`: `POST` -> `GET` -> `PUT` -> CRUD `/contactos` -> `POST /inactivar` -> `POST /activar`. SLO: `p95 < 600 ms`, err `< 1%`. |
| P04 | `ms_proveedores/p04_carga_productos.py` | Carga | Solo | 25u, 5/s, 5m (pausa 0.8-2s) | Catalogo `productos_suministrados`: `GET /{id}/productos`, `GET ?sku=`, `PUT /{id}/productos/{sku}` upsert, `DELETE`. SLO: `p95 < 500 ms`, err `< 1%`. |
| P05 | `ms_proveedores/p05_estres_lectura.py` | Estres | Solo | `LoadTestShape`: 20->200u (+20/30s, corte >5% err, pausa 0.3-1s) | Busquedas intensivas `LIKE`/`EXISTS`, detalle y productos hasta punto de degradacion/quiebre. |
| P06 | `ms_proveedores/p06_estres_escritura.py` | Estres | Solo | `LoadTestShape`: 15->150u (+15/30s, corte >5% err, pausa 0.2-0.8s) | Escrituras transaccionales concurrentes presionando pool MySQL (10 conexiones) hasta quiebre. |
| P07 | `ms_proveedores/p07_capacidad_soak.py` | Capacidad (soak) | Solo | 40u, 5/s, 15m local / 60m formal (pausa 1-2.5s) | Carga alta estable sostenida con reciclaje de SKUs y limpieza de contactos. SLO: `p95 < 700 ms`, deriva `< 20%`, err `< 1%`. |

### 3.2 Bloque MS-Compras (P08 a P15) - `http://127.0.0.1:5004`

`MS-Compras` autentica con `Authorization: Bearer <SERVICE_TOKEN>` (mas `X-Service-Token`, `X-User-Id`, `X-User-Role`, `X-Correlation-Id`). Cinco pruebas (`P08`, `P09`, `P10`, `P13`, `P15`) corren **100% SOLO** (solo `MS-Compras` + su MySQL, cubriendo las 3 tipologias del PDF), y tres pruebas (`P11`, `P12`, `P14`) ejercitan escritura transaccional, maquina de estados (`POST /aprobar`, `POST /anular`, `POST /recepciones`, `POST /devoluciones`), validacion HTTP hacia `MS-Proveedores` y publicacion en `RabbitMQ`.

| ID | Archivo | Tipo (`locust_test.pdf`) | Modo | Perfil por defecto | Operaciones principales y SLO |
|---|---|---|---|---|---|
| P08 | `ms_compras/p08_carga_ordenes.py` | Carga | Solo | 20u, 5/s, 10m (pausa 1-3s) | `GET /ordenes-compra` paginado y con filtros (`estado`, `id_proveedor`), `GET /{id}`, `GET /{id}/recepciones`, `GET /health`. SLO: `p95 < 500 ms`, err `< 1%`. |
| P09 | `ms_compras/p09_carga_devoluciones.py` | Carga | Solo | 25u, 5/s, 10m (pausa 1-2.5s) | `GET /devoluciones-proveedor` (paginado + `id_proveedor` + `desde`/`hasta`), comparacion `per_page=10` vs `100` en ordenes y `GET /{id}/recepciones`. SLO: `p95 < 600 ms`, err `< 1%`. |
| P10 | `ms_compras/p10_carga_validacion.py` | Carga | Solo | 30u, 6/s, 5m (pausa 0.5-1.5s) | Rutas negativas antes de dependencias externas: `401` auth, `403` RBAC, `404`, `422` validacion y `409` conflictos de estado. SLO: `p95 < 300 ms`, `0%` desviacion. |
| P11 | `ms_compras/p11_carga_mixta.py` | Carga | Integrado | 20u, 4/s, 10m (pausa 1-3s) | Mezcla 75% GET + 25% `POST /ordenes-compra` -> `PUT /{id}` -> `POST /aprobar` o `POST /anular`. SLO: `p95 < 1200 ms`, err `< 1%`. |
| P12 | `ms_compras/p12_carga_ciclo_completo.py` | Carga | Integrado | 15u, 3/s, 10m (pausa 1-2.5s) | `SequentialTaskSet` completo: crear -> aprobar -> recepcion parcial -> recepcion total -> devolucion -> verificar consistencia (publica 3 eventos RabbitMQ). SLO: `p95 < 1500 ms`, err `< 1%`. |
| P13 | `ms_compras/p13_estres_lecturas.py` | Estres | Solo | `LoadTestShape`: 20->200u (+20/30s, corte >5% err, pausa 0.3-1s) | Lecturas con JOINs (`per_page=50`, detalle, recepciones, devoluciones) para localizar limite de Gunicorn (`2x4`) y `DB_POOL_SIZE=5`. |
| P14 | `ms_compras/p14_estres_escrituras.py` | Estres | Integrado | `LoadTestShape`: 15->120u (+15/30s, corte >5% err, pausa 0.4-1.2s) | Mezcla con escrituras concurrentes (`FOR UPDATE`, HTTP a `MS-Proveedores` y `pika` con `confirm_delivery` en RabbitMQ) hasta punto de quiebre. |
| P15 | `ms_compras/p15_capacidad_soak.py` | Capacidad (soak) | Solo (opcional mixto) | 40u, 5/s, 60m (pausa 1-2s) | Carga sostenida prolongada de consultas y `/health` (opcional `LT_INCLUIR_ESCRITURAS=1` para `/health/ready` + escritura). SLO: `p95 < 1000 ms`, deriva `< 20%`, err `< 0.5%`. |

## 4. Instalacion del entorno virtual de Locust

Desde la carpeta `pruebas/locust/proveedores_compras/`:

```bash
# Linux / macOS
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

## 5. Levantar cada microservicio individualmente con su `docker-compose.yml`

Cada microservicio cuenta con su propio `docker-compose.yml` con MySQL 8.4 aislado y `SERVICE_TOKEN` por defecto `token-servicio-inventarios-2026-vm`.

### 5.1 Levantar solo `MS-Proveedores` (para P01 a P07)

```bash
cd MS-Proveedores
docker compose up -d
curl -s http://127.0.0.1:5003/health/ready
```

### 5.2 Levantar solo `MS-Compras` (para P08, P09, P10, P13 y P15 en modo solo)

```bash
cd MS-Compras
docker compose up -d
curl -s http://127.0.0.1:5004/health
```

### 5.3 Levantar `MS-Compras` con sus dependencias en `redapi` (para P11, P12, P14 y P15 integrado)

```bash
cd infra/rabbitmq && docker compose up -d
cd ../../MS-Proveedores && docker compose up -d
cd ../MS-Compras && docker compose up -d
curl -s http://127.0.0.1:5004/health/ready
```

Opcionalmente, si se desea aislar `MS-Compras` de `MS-Proveedores` manteniendo RabbitMQ real, puede ejecutarse `python ms_compras/mock_proveedores.py --host 0.0.0.0 --port 3001` y configurar `PROVEEDORES_URL` hacia el host del stub.

## 6. Ejecucion de pruebas y recoleccion de metricas CSV/HTML

Todos los ejecutores (`ejecutar.sh` y `ejecutar.py`) invocan Locust en modo `--headless` generando automaticamente los 4 artefactos de evidencia por prueba en `pruebas/resultados/proveedores_compras/<ID>/`:
- `<ID>_stats.csv`: resumen por operacion HTTP (total de peticiones, fallos, media, mediana, p50, p95, p99, maximo, RPS).
- `<ID>_stats_history.csv`: serie temporal segundo a segundo (fundamental para graficar rampas en **Estres** y deriva de latencia en **Capacidad/Soak**).
- `<ID>_failures.csv`: detalle agrupado de cada error HTTP o fallo de validacion JSON.
- `<ID>.html`: reporte visual exportable a PDF para el informe tecnico del taller.

### Ejemplos rapidos (`MS-Proveedores`, P01-P07)

```bash
cd pruebas/locust/proveedores_compras/ms_proveedores
./ejecutar.sh P01
./ejecutar.sh P05
# Windows PowerShell o multiplataforma:
python ejecutar.py P01 --humo
python ejecutar.py TODAS
```

### Ejemplos rapidos (`MS-Compras`, P08-P15)

```bash
cd pruebas/locust/proveedores_compras/ms_compras
./ejecutar.sh P08
./ejecutar.sh solo
./ejecutar.sh integrado
# Windows PowerShell o multiplataforma:
python ejecutar.py --listar
python ejecutar.py P08 -u 10 -r 2 -t 30s
python ejecutar.py solo -t 2m
```

### Variables de entorno comunes

| Variable | Uso |
|---|---|
| `HOST` / `LT_HOST` | URL base del microservicio (`http://127.0.0.1:5003` o `http://127.0.0.1:5004`) |
| `SERVICE_TOKEN` / `LT_SERVICE_TOKEN` | Token de servicio (`token-servicio-inventarios-2026-vm` por defecto) |
| `LT_USUARIOS`, `LT_SPAWN_RATE`, `LT_DURACION` | Sobrescriben `-u`, `-r`, `-t` para corridas cortas o extendidas |
| `LT_PAUSA_MIN`, `LT_PAUSA_MAX` | Rango de `wait_time` (`between(min, max)`) |
| `LT_SALIDA` | Carpeta base de salida para reportes CSV y HTML |

### Telemetria de entorno recomendada (diapositiva 18 de `locust_test.pdf`)

Durante cada corrida, registrar en paralelo el consumo de CPU y RAM de los contenedores:

```bash
docker stats --no-stream ms-proveedores-app ms-proveedores-mysql ms-compras-app ms-compras-mysql rabbitmq-inventario
```

Para cada escenario del informe tecnico, documentar: usuarios simulados, spawn rate, duracion, host, version de Locust (`2.47.0`), estado de paginacion/indices, percentiles (`p50`, `p95`, `p99`), RPS, tasa de error y consumo CPU/RAM observado.

Para detalle fino de endpoints, payloads y reglas de negocio de cada servicio, consultar [ms_proveedores/README.md](ms_proveedores/README.md) y [ms_compras/README.md](ms_compras/README.md).
