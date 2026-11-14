# ms-productos

Microservicio del catálogo de categorías y productos (Flask + MySQL). Por ahora incluye la autenticación por token de servicio, los errores en JSON, `GET /health` y la capa de datos (tablas de categorías y productos). Los endpoints del catálogo vienen después.

## Preparar el entorno

```bash
cd MS-Productos
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

ms-inventario consulta este servicio en `http://ms-productos:5000`. Los puertos publicados en `127.0.0.1` del host no son alcanzables desde otro contenedor.

## Levantar todo con Docker Compose

```bash
docker compose up -d --build
```

Levanta dos servicios:

- `app`: el microservicio, construido con el `Dockerfile`, en `http://127.0.0.1:5001`. Toma la configuración del `.env`, salvo `DB_HOST` y `DB_PORT`, que dentro de Compose apuntan al servicio `mysql` y a su puerto interno 3306.
- `mysql`: MySQL 8.4, publicado en `127.0.0.1:33061`, con los datos en el volumen `ms_productos_mysql`. La app espera a que esté sano antes de arrancar.

El servicio no arranca si `SERVICE_TOKEN` no está definido o conserva el valor de ejemplo. Todas las rutas exigen `Authorization: Bearer <SERVICE_TOKEN>`, salvo `GET /health`.

También se puede correr la app fuera de Docker, con solo MySQL en Compose (usa `DB_HOST=127.0.0.1` y `DB_PORT=33061` del `.env`):

```bash
docker compose up -d mysql
.venv/bin/python run.py    # http://127.0.0.1:5001
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

Las pruebas de `tests/test_db.py` usan el MySQL de desarrollo (`127.0.0.1:33061`, credenciales del `.env`). Cada una corre en una transacción que se revierte, así que no deja datos. Si MySQL no está arriba, esas pruebas se saltan y el resto corre igual.

## Reiniciar la base de datos

Borra el volumen con todos los datos y vuelve a crear las tablas:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec app python -m db.aplicar_migraciones
```

Para solo apagar los servicios y conservar los datos: `docker compose down`.

## Endpoints

Base local: `http://127.0.0.1:5001`. Dentro de la red `redapi`: `http://ms-productos:5000`. Desde fuera, el gateway publica cada ruta como `/api/<ruta>`. Los roles los aplica el gateway; el servicio solo exige el token de servicio.

| Método | Ruta | Descripción | Roles |
|---|---|---|---|
| GET | `/health` | Estado del servicio (sin token) | Sondas |
| GET | `/categorias` | Raíces con subcategorías; `?estado&id_padre` | Todos |
| GET | `/categorias/{id}` | Una categoría | Todos |
| POST | `/categorias` | Crea `{nombre, descripcion?, id_categoria_padre?}` | Admin |
| PUT | `/categorias/{id}` | Reemplaza `{nombre, descripcion?, id_categoria_padre?}` | Admin |
| POST | `/categorias/{id}/inactivar` y `/activar` | Cambia el estado | Admin |
| GET | `/productos` | Listado; `?q&id_categoria&estado&precio_min&precio_max&skus` | Todos |
| GET | `/productos/{id}` | Un producto | Todos |
| GET | `/productos/sku/{sku}` | `{sku, nombre, estado, unidad_medida, stock_minimo, id_categoria}` | Todos e interno (ms-inventario) |
| POST | `/productos` | Crea `{sku, nombre, descripcion?, marca, id_categoria, unidad_medida, precio_venta, stock_minimo}` | Admin |
| PUT | `/productos/{id}` | Reemplaza lo mismo sin `sku` | Admin |
| POST | `/productos/{id}/inactivar` y `/activar` | Cambia el estado | Admin |

Cabeceras:

- `Authorization: Bearer <SERVICE_TOKEN>` en todas las rutas salvo `/health`; sin él, 401.
- `X-Correlation-Id`: opcional, para rastrear la petición en los logs.

Listados: `?page=1&per_page=20` (máximo 100) y respuesta `{"data": [...], "meta": {"page", "per_page", "total"}}`; `?skus` va separado por comas (máximo 100). Precios y stock mínimo salen como números JSON.

Errores: `{"error": {"codigo", "mensaje", "detalles"}}`, donde `detalles` es `{campo: [mensajes]}`. Códigos: 400 cuerpo que no es JSON, 401 sin token, 404 `NO_EXISTE`, 409 `NOMBRE_REPETIDO`, `SKU_DUPLICADO`, `CATEGORIA_CON_PRODUCTOS` o `CONFLICTO`, 422 `VALIDACION`, 503 la base no responde.

Ejemplo:

```bash
TOKEN=...   # el valor de SERVICE_TOKEN del .env; nunca se escribe en el código
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:5001/productos?q=leche&per_page=10"
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5001/productos/sku/LAC-0001
```
