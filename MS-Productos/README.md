# ms-productos

Microservicio del catálogo de categorías y productos (Flask). Por ahora solo incluye el esqueleto: autenticación por token de servicio, errores en JSON y `GET /health`.

## Preparar el entorno

```bash
cd MS-Productos
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env    # cambia SERVICE_TOKEN y DB_PASSWORD
```

## Correr el servicio

```bash
.venv/bin/python run.py    # http://127.0.0.1:5001
```

El servicio no arranca si `SERVICE_TOKEN` no está definido o conserva el valor de ejemplo. Todas las rutas exigen `Authorization: Bearer <SERVICE_TOKEN>`, salvo `GET /health`.

## Probar

```bash
.venv/bin/pytest
```

## Base de datos de desarrollo

MySQL 8.4 en Docker, en el puerto 33061 del host, con las credenciales del `.env`:

```bash
docker compose up -d
```
