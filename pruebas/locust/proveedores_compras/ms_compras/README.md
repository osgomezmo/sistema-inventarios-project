# Pruebas de rendimiento Locust - MS-Compras (P08 a P15)

Suite modular de 8 pruebas de rendimiento con **Locust** para el microservicio `MS-Compras` (Python 3.12 + Flask + Gunicorn `2 workers x 4 threads` + MySQL 8.4 + RabbitMQ), disenada segun la taxonomia y metodologia del taller `locust_test.pdf` (Docente Albeiro Montes, Ingenieria de Software II): **Carga**, **Estres** y **Capacidad (soak)**.

## 1. Arquitectura de dependencias (Modo Solo vs Modo Integrado)

Al inspeccionar el codigo fuente real de `MS-Compras` (`app/routes/`, `app/repositorios/`, `app/clientes/proveedores.py` y `app/messaging/publicador.py`), se distinguen dos niveles exactos de dependencias:

### Operaciones 100% SOLO (`MS-Compras` + su MySQL)
No requieren RabbitMQ ni `MS-Proveedores` encendidos:
- `GET /health` (liveness sin dependencias externas).
- `GET /ordenes-compra` (listado paginado `?page=&per_page=` y filtros `estado`, `id_proveedor`, `desde`, `hasta`).
- `GET /ordenes-compra/{id}` (detalle completo con `items`, `recepciones` y `devoluciones`).
- `GET /ordenes-compra/{id}/recepciones`.
- `GET /devoluciones-proveedor` (paginado + filtros `id_proveedor`, `desde`, `hasta`; roles `admin`, `jefe_bodega`, `compras`).
- Rutas negativas de seguridad, validacion y conflictos de maquina de estados (`401`, `403`, `404`, `422`, `409`) que fallan de forma controlada antes de invocar a `MS-Proveedores` o `RabbitMQ`.

### Operaciones INTEGRADAS (`MS-Compras` + `MS-Proveedores` + `RabbitMQ` en red `redapi`)
- `GET /health/ready` (valida conectividad real a MySQL y RabbitMQ; retorna `503` si RabbitMQ esta caido).
- `POST /ordenes-compra` y `PUT /ordenes-compra/{id}` (consultan sincronicamente `GET /proveedores/{id}` en `MS-Proveedores` y publican `OrdenCompraActualizada` con `confirm_delivery` en RabbitMQ dentro de la transaccion SQL).
- `POST /ordenes-compra/{id}/aprobar` y `POST /ordenes-compra/{id}/anular` (publican `OrdenCompraActualizada` en RabbitMQ; notese que son rutas `POST`, no `PATCH`).
- `POST /ordenes-compra/{id}/recepciones` (publica `MercanciaRecibida` y `OrdenCompraActualizada` en RabbitMQ).
- `POST /ordenes-compra/{id}/devoluciones` (publica `DevolucionProveedorRegistrada` en RabbitMQ).

## 2. Autenticacion y encabezados

`MS-Compras/app/auth.py` exige en todas las rutas protegidas:
- `Authorization: Bearer <SERVICE_TOKEN>` (por defecto en `MS-Compras/docker-compose.yml`: `token-servicio-inventarios-2026-vm`).
- `X-User-Id`: entero positivo (por defecto `1`).
- `X-User-Role`: `admin`, `compras`, `jefe_bodega` o `gerente` (cada tarea envia el rol exacto autorizado por ruta).
- `X-Correlation-Id`: UUID unico por peticion.
- Adicionalmente, `common.py` adjunta `X-Service-Token` para mantener simetria de cabeceras internas.

## 3. Catalogo de pruebas (P08 a P15)

| ID | Archivo | Tipo (`locust_test.pdf`) | Modo | Perfil por defecto | SLO / Criterio de evaluacion |
|---|---|---|---|---|---|
| P08 | `p08_carga_ordenes.py` | Carga | Solo | 20u, spawn 5/s, 10m, pausa 1-3s | `p95 < 500 ms`, errores `< 1%` |
| P09 | `p09_carga_devoluciones.py` | Carga | Solo | 25u, spawn 5/s, 10m, pausa 1-2.5s | `p95 < 600 ms`, errores `< 1%`, comparacion `per_page=10` vs `100` |
| P10 | `p10_carga_validacion.py` | Carga | Solo | 30u, spawn 6/s, 5m, pausa 0.5-1.5s | `p95 < 300 ms`, `0%` desviaciones en codigos `401/403/404/422/409` |
| P11 | `p11_carga_mixta.py` | Carga | Integrado | 20u, spawn 4/s, 10m, pausa 1-3s | `p95 < 1200 ms`, errores `< 1%` (mezcla 75% GET / 25% escrituras) |
| P12 | `p12_carga_ciclo_completo.py` | Carga | Integrado | 15u, spawn 3/s, 10m, pausa 1-2.5s | `p95 < 1500 ms`, errores `< 1%`, consistencia completa de estados y 3 eventos |
| P13 | `p13_estres_lecturas.py` | Estres | Solo | `LoadTestShape`: 20->200u (+20/30s, corte >5% error), pausa 0.3-1s | Registrar concurrencia y RPS de degradacion/quiebre de Gunicorn (`2x4`) y `DB_POOL_SIZE=5` |
| P14 | `p14_estres_escrituras.py` | Estres | Integrado | `LoadTestShape`: 15->120u (+15/30s, corte >5% error), pausa 0.4-1.2s | Registrar concurrencia/RPS de quiebre y clasificar `503` (MySQL vs `MS-Proveedores` vs RabbitMQ) |
| P15 | `p15_capacidad_soak.py` | Capacidad (soak) | Solo (opcional mixto) | 40u, spawn 5/s, 60m, pausa 1-2s | `p95 < 1000 ms`, errores `< 0.5%`, deriva temporal de p95 `< 20%` sin fuga de RAM/pool |

## 4. Despliegue del entorno

### 4.1 Ejecutar MS-Compras completamente SOLO (para P08, P09, P10, P13 y P15)

```bash
cd MS-Compras
docker compose up -d
```

Verificar que el contenedor y los datos sembrados (`OC-2026-000001` a `OC-2026-000005`, `SEMBRAR_DATOS=1`) esten activos en `http://127.0.0.1:5004`:

```bash
curl -s http://127.0.0.1:5004/health
```

### 4.2 Ejecutar MS-Compras en modo INTEGRADO (para P11, P12, P14 y P15 con escrituras)

Levantar RabbitMQ, `MS-Proveedores` y `MS-Compras` en la red Docker `redapi`:

```bash
cd infra/rabbitmq && docker compose up -d
cd ../../MS-Proveedores && docker compose up -d
cd ../MS-Compras && docker compose up -d
```

Verificar `readiness` (MySQL + RabbitMQ):

```bash
curl -s http://127.0.0.1:5004/health/ready
```

### 4.3 Alternativa aislada con `mock_proveedores.py` (opcional)

Si se desea medir escrituras de `MS-Compras` + `RabbitMQ` sin levantar `MS-Proveedores`:

```bash
python mock_proveedores.py --host 0.0.0.0 --port 3001
```

Y arrancar `MS-Compras` apuntando `PROVEEDORES_URL=http://host.docker.internal:3001` (con `extra_hosts` en Linux o nativo en Docker Desktop Windows/macOS).

## 5. Ejecucion de las pruebas

### Instalacion del entorno virtual (desde `pruebas/locust/proveedores_compras/`)

```bash
python -m venv .venv
# Linux / macOS:
.venv/bin/pip install -r requirements.txt
# Windows PowerShell:
.\.venv\Scripts\pip install -r requirements.txt
```

### Usando el script Bash (`ejecutar.sh`, Linux/macOS/Git Bash)

```bash
cd pruebas/locust/proveedores_compras/ms_compras
./ejecutar.sh P08
./ejecutar.sh solo
./ejecutar.sh integrado

# Corrida rapida de humo (30 segundos, 5 usuarios):
LT_USUARIOS=5 LT_SPAWN_RATE=2 LT_DURACION=30s ./ejecutar.sh P08

# P15 en modo integrado (incluye /health/ready y creacion/anulacion):
LT_INCLUIR_ESCRITURAS=1 LT_DURACION=15m ./ejecutar.sh P15
```

### Usando el ejecutor Python multiplataforma (`ejecutar.py`, Windows/Linux/macOS)

```powershell
cd pruebas\locust\proveedores_compras\ms_compras
python ejecutar.py --listar
python ejecutar.py P08
python ejecutar.py P08 -u 10 -r 2 -t 30s
python ejecutar.py solo -t 2m
python ejecutar.py P13 --web
```

### Ejecucion directa con `locust` (Headless o Web UI)

```bash
# Modo Web UI (http://localhost:8089):
locust -f p08_carga_ordenes.py --host http://127.0.0.1:5004

# Modo Headless con exportacion CSV y HTML:
locust -f p08_carga_ordenes.py --headless --host http://127.0.0.1:5004 \
  -u 20 -r 5 -t 10m \
  --csv ../../../resultados/proveedores_compras/P08/P08 \
  --html ../../../resultados/proveedores_compras/P08/P08.html
```

## 6. Variables de entorno soportadas

| Variable | Valor por defecto | Descripcion |
|---|---|---|
| `HOST` / `LT_HOST` | `http://127.0.0.1:5004` | URL base de `MS-Compras` |
| `SERVICE_TOKEN` / `LT_SERVICE_TOKEN` | `token-servicio-inventarios-2026-vm` | Token interno para `Authorization: Bearer` y `X-Service-Token` |
| `LT_USER_ID` | `1` | Valor de `X-User-Id` |
| `LT_USER_ROLE` | `admin` | Rol por defecto cuando una tarea no fuerza un rol especifico |
| `LT_PROVEEDOR_IDS` | `1,2,3,4` | IDs de proveedores activos usados en filtros y creacion de ordenes |
| `LT_BODEGA_IDS` | `1,2,3` | IDs de bodegas destino usadas al crear ordenes |
| `LT_USUARIOS`, `LT_SPAWN_RATE`, `LT_DURACION` | Segun prueba | Sobrescriben `-u`, `-r`, `-t` en pruebas de carga y capacidad |
| `LT_PAUSA_MIN`, `LT_PAUSA_MAX` | Segun prueba | Sobrescriben `wait_time` (`between(min, max)`) |
| `LT_PASO_USUARIOS`, `LT_PASO_SEGUNDOS`, `LT_MAX_USUARIOS`, `LT_LIMITE_ERRORES` | P13: 20/30s/200/0.05; P14: 15/30s/120/0.05 | Parametros del `LoadTestShape` en pruebas de estres |
| `LT_INCLUIR_ESCRITURAS` | `0` | En P15, `1` habilita `/health/ready` y ciclo ligero de escritura/anulacion |
| `LT_SALIDA` | `pruebas/resultados/proveedores_compras` | Directorio base donde se guardan CSV y HTML por prueba |
