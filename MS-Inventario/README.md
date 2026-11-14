# ms-inventario

Microservicio de bodegas, saldos, movimientos, kardex, traslados y devoluciones de cliente (Flask + MySQL). Por ahora incluye la autenticación por token de servicio, los errores en JSON, `GET /health` y la capa de datos (tablas de bodegas, saldos, traslados, movimientos y eventos procesados). Los endpoints de negocio vienen después.

## Preparar el entorno

```bash
cd MS-Inventario
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env    # cambia SERVICE_TOKEN y DB_PASSWORD
```

`requirements.txt` tiene solo las dependencias de ejecución, que son las que instala la imagen Docker. `requirements-dev.txt` las incluye y agrega las de pruebas.

## Red compartida entre servicios

Cada servicio tiene su propio `docker-compose.yml`. Para que los contenedores se hablen entre sí, el servicio `app` se une también a la red externa `redapi`, donde se le encuentra por su alias (`ms-productos` o `ms-inventario`, puerto 5000). Las bases de datos no se unen a esa red.

La red se crea una sola vez, antes del primer `docker compose up`:

```bash
docker network inspect redapi >/dev/null 2>&1 || docker network create redapi
```

ms-inventario consulta a ms-productos en `http://ms-productos:5000` (variable `PRODUCTOS_URL`, que el compose fija para el contenedor). Fuera de Docker se usa la del `.env`, por defecto `http://127.0.0.1:5001`. Los puertos publicados en `127.0.0.1` del host no son alcanzables desde otro contenedor.

## Levantar todo con Docker Compose

```bash
docker compose up -d --build
```

Levanta dos servicios:

- `app`: el microservicio, construido con el `Dockerfile`, en `http://127.0.0.1:5002`. Toma la configuración del `.env`, salvo `DB_HOST` y `DB_PORT`, que dentro de Compose apuntan al servicio `mysql` y a su puerto interno 3306.
- `mysql`: MySQL 8.4, publicado en `127.0.0.1:33062`, con los datos en el volumen `ms_inventario_mysql`. La app espera a que esté sano antes de arrancar.

El servicio no arranca si `SERVICE_TOKEN` no está definido o conserva el valor de ejemplo. Todas las rutas exigen `Authorization: Bearer <SERVICE_TOKEN>`, salvo `GET /health`.

También se puede correr la app fuera de Docker, con solo MySQL en Compose (usa `DB_HOST=127.0.0.1` y `DB_PORT=33062` del `.env`):

```bash
docker compose up -d mysql
.venv/bin/python run.py    # http://127.0.0.1:5002
```

## Crear las tablas

Las tablas se crean con los scripts SQL numerados de `db/` (`001_...`, `002_...`). El aplicador ejecuta en orden los que falten y los registra en la tabla `migraciones_aplicadas`; correrlo otra vez no repite nada.

```bash
docker compose exec app python -m db.aplicar_migraciones   # dentro del contenedor
.venv/bin/python -m db.aplicar_migraciones                 # o desde el venv
```

## Probar

```bash
.venv/bin/pytest
```

Las pruebas de `tests/test_db.py` usan el MySQL de desarrollo (`127.0.0.1:33062`, credenciales del `.env`). Cada una corre en una transacción que se revierte, así que no deja datos. Si MySQL no está arriba, esas pruebas se saltan y el resto corre igual.

## Reiniciar la base de datos

Borra el volumen con todos los datos y vuelve a crear las tablas:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec app python -m db.aplicar_migraciones
```

Para solo apagar los servicios y conservar los datos: `docker compose down`.

## Endpoints

Base local: `http://127.0.0.1:5002`. Dentro de la red `redapi`: `http://ms-inventario:5000`. Desde fuera, el gateway publica cada ruta como `/api/<ruta>`. Los roles los aplica el gateway; el servicio solo exige el token de servicio.

| Método | Ruta | Descripción | Roles |
|---|---|---|---|
| GET | `/health` | Estado del servicio (sin token) | Sondas |
| GET | `/bodegas` | Listado; `?estado` | Todos |
| GET | `/bodegas/{id}` | Una bodega | Todos |
| POST | `/bodegas` | Crea `{codigo, nombre, direccion}` | Admin, Jefe |
| PUT | `/bodegas/{id}` | Cambia `{nombre, direccion}` | Admin, Jefe |
| POST | `/bodegas/{id}/inactivar` y `/activar` | Cambia el estado | Admin, Jefe |
| GET | `/stock` | Saldos; `?sku&id_bodega&bajo_minimo` | Todos |
| GET | `/stock/{sku}` | Saldo por bodega y total | Todos |
| POST | `/movimientos` | Salida o ajuste `{sku, id_bodega, tipo, cantidad, costo_unitario?, motivo?, documento_referencia?}` | Admin, Jefe |
| GET | `/movimientos` | Listado; `?sku&id_bodega&tipo&desde&hasta` | Admin, Jefe, Gerente |
| GET | `/movimientos/{id}` | Un movimiento | Admin, Jefe, Gerente |
| GET | `/kardex` | `?sku&id_bodega&desde&hasta` (obligatorios) | Admin, Jefe, Gerente |
| POST | `/traslados` | `{sku, id_bodega_origen, id_bodega_destino, cantidad, motivo?}` | Admin, Jefe |
| GET | `/traslados` y `/traslados/{id}` | Listado (`?sku&desde&hasta`) y detalle | Admin, Jefe, Gerente |
| POST | `/devoluciones-cliente` | `{sku, id_bodega, cantidad, factura_pos, motivo}` | Admin, Jefe |
| GET | `/devoluciones-cliente` | Listado; `?sku&desde&hasta` | Admin, Jefe, Gerente |

Cabeceras:

- `Authorization: Bearer <SERVICE_TOKEN>` en todas las rutas salvo `/health`; sin él, 401.
- `X-User-Id` (entero positivo): obligatoria en `POST /movimientos`, `/traslados` y `/devoluciones-cliente`; sin ella, 400.
- `X-Correlation-Id`: opcional; se reenvía a ms-productos.

Listados: `?page=1&per_page=20` (máximo 100) y respuesta `{"data": [...], "meta": {"page", "per_page", "total"}}`. Fechas `desde` y `hasta`: `AAAA-MM-DD` (día completo en Bogotá) o ISO 8601 con hora; las respuestas usan UTC con `Z`. Cantidades y valores salen como números JSON.

Errores: `{"error": {"codigo", "mensaje", "detalles"}}`, donde `detalles` es `{campo: [mensajes]}`. Códigos: 400 petición mal formada, 401 sin token, 404 no existe (`NO_EXISTE`, `PRODUCTO_INEXISTENTE`), 409 conflicto (`STOCK_INSUFICIENTE`, `CODIGO_DUPLICADO`, `CONFLICTO`), 422 validación (`VALIDACION`), 503 ms-productos o la base no responden.

Ejemplo:

```bash
TOKEN=...   # el valor de SERVICE_TOKEN del .env; nunca se escribe en el código
curl -H "Authorization: Bearer $TOKEN" -H "X-User-Id: 7" -H "Content-Type: application/json" \
     -d '{"sku":"LAC-0001","id_bodega":1,"tipo":"SALIDA","cantidad":3}' \
     http://127.0.0.1:5002/movimientos
```
