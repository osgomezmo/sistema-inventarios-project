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
