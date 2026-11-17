# AGENTS.md - Guia Operativa de MS-Compras

## 1. Resumen del Microservicio

`MS-Compras` gestiona el ciclo completo de abastecimiento a proveedores en el Sistema de Gestion de Inventarios:

- Creacion y edicion de ordenes de compra en estado `BORRADOR`.
- Flujo de aprobacion (`BORRADOR -> APROBADA`) y anulacion (`BORRADOR | APROBADA` sin recepciones -> `ANULADA`).
- Recepcion parcial o total de mercancia (`APROBADA | RECIBIDA_PARCIAL -> RECIBIDA_PARCIAL | RECIBIDA`).
- Registro y consulta de devoluciones al proveedor sobre cantidades previamente recibidas.
- Publicacion sincrona de eventos de dominio hacia RabbitMQ (`OrdenCompraActualizada`, `MercanciaRecibida`, `DevolucionProveedorRegistrada`) y validacion sincrona de proveedores en `ms-proveedores`.

Decisiones arquitectonicas clave:
- **Base de datos propia:** MySQL exclusiva (`mscompras`), esquema UTF-8 (`utf8mb4_0900_ai_ci`) y marcas de tiempo en UTC (`time_zone="+00:00"`).
- **SQL parametrizado puro:** Sin ORM; acceso mediante `mysql-connector-python` con `MySQLConnectionPool`, bloqueos `FOR UPDATE` en transiciones de estado y `Decimal` para calculos monetarios y de cantidades.
- **Publicacion directa en RabbitMQ (sin tabla `outbox_eventos`):** Cada operacion mutadora publica directamente al broker con `confirm_delivery()` y `delivery_mode=2` dentro de la ventana transaccional antes del `commit`. Si RabbitMQ no esta disponible, la transaccion MySQL ejecuta `rollback` y el endpoint responde `503 SERVICIO_NO_DISPONIBLE`.

## 2. Stack Tecnologico y Estructura

- **Lenguaje y Framework:** Python 3.12+ con Flask (`>=3.1`) y Gunicorn (`>=23.0`).
- **Base de datos:** `mysql-connector-python` (`>=9.1`).
- **Mensajeria y HTTP:** `pika` (`>=1.3`), `requests` (`>=2.32`), `python-dotenv` (`>=1.0`).
- **Puerto por defecto:** `5000` (Gunicorn en contenedor Docker). En ejecucion local simultanea con otros servicios Flask se recomienda asignar `PORT=5003` en `.env`.

Estructura principal:
```text
MS-Compras/
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── run.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_clientes_y_mensajeria.py
│   ├── test_rutas_y_flujo.py
│   └── test_validacion.py
├── db/
│   ├── __init__.py
│   ├── 001_tablas_compras.sql
│   └── aplicar_migraciones.py
└── app/
    ├── __init__.py
    ├── auth.py
    ├── config.py
    ├── db.py
    ├── errors.py
    ├── json_provider.py
    ├── paginacion.py
    ├── validacion.py
    ├── clientes/
    │   ├── __init__.py
    │   └── proveedores.py
    ├── messaging/
    │   ├── __init__.py
    │   └── publicador.py
    ├── repositorios/
    │   ├── __init__.py
    │   ├── devoluciones.py
    │   ├── ordenes.py
    │   └── recepciones.py
    └── routes/
        ├── __init__.py
        ├── devoluciones.py
        ├── health.py
        └── ordenes.py
```

## 3. Esquema de Base de Datos (`mscompras`)

Definido en `db/001_tablas_compras.sql`:

- `ordenes_compra`: `id_orden` (PK), `numero` (UNIQUE, formato `OC-YYYY-000001`), `id_proveedor`, `id_bodega_destino`, `estado` (`BORRADOR`, `APROBADA`, `RECIBIDA_PARCIAL`, `RECIBIDA`, `ANULADA`), `total` (`DECIMAL(14,2)`), `id_usuario_creador`, `id_usuario_aprobador`, `motivo_anulacion`, `creada_en`, `aprobada_en`, `actualizada_en`.
- `detalles_orden`: `id_detalle` (PK), `id_orden` (FK `ON DELETE CASCADE`), `sku`, `cantidad_pedida` (`DECIMAL(14,3)`), `cantidad_recibida` (`DECIMAL(14,3)`), `cantidad_devuelta` (`DECIMAL(14,3)`), `precio_unitario` (`DECIMAL(14,2)`), restriccion unica `(id_orden, sku)`.
- `recepciones`: `id_recepcion` (PK), `id_orden` (FK), `fecha`, `id_usuario`, `observaciones`.
- `recepcion_detalle`: `id_recepcion` (FK), `id_detalle` (FK), `cantidad` (`DECIMAL(14,3)`), PK `(id_recepcion, id_detalle)`.
- `devoluciones_proveedor`: `id_devolucion` (PK), `id_orden` (FK), `fecha`, `motivo`, `id_usuario`.
- `devolucion_detalle`: `id_devolucion` (FK), `id_detalle` (FK), `cantidad` (`DECIMAL(14,3)`), PK `(id_devolucion, id_detalle)`.

## 4. Seguridad, Headers y Formato de Error

Todas las rutas de negocio (excepto `/health` y `/health/ready`) exigen:
- `Authorization: Bearer <SERVICE_TOKEN>` (validado con `hmac.compare_digest`).
- `X-User-Id`: entero positivo del usuario autenticado en el gateway.
- `X-User-Role`: `admin`, `jefe_bodega`, `compras` o `gerente` (alias como `jefe` se normalizan a `jefe_bodega`).
- `X-Correlation-Id`: propagado en respuestas HTTP, llamadas sincronas a `ms-proveedores` y en el campo `id_correlacion` de cada evento RabbitMQ (se genera UUID v4 si no llega).

Formato estandar de respuesta ante error:
```json
{
  "error": {
    "codigo": "CODIGO_ERROR",
    "mensaje": "Descripcion legible",
    "detalles": {}
  }
}
```

## 5. Contratos de API REST

### Salud del Servicio (Publicos)
- `GET /health` -> `200 {"status": "ok", "service": "ms-compras"}`
- `GET /health/ready` -> Verifica MySQL (`SELECT 1`) y conexion activa con RabbitMQ; responde `200` o `503 SERVICIO_NO_DISPONIBLE`.

### Ordenes de Compra (`/ordenes-compra`)
- `GET /ordenes-compra`
  - Roles: `admin`, `jefe_bodega`, `compras`, `gerente`.
  - Query: `estado`, `id_proveedor`, `desde`, `hasta`, `page` (defecto `1`), `per_page` (defecto `20`, maximo `100`).
  - Respuesta: `200 {"data": [...], "meta": {"page", "per_page", "total", "total_pages"}}`.
- `GET /ordenes-compra/<id>`
  - Roles: `admin`, `jefe_bodega`, `compras`, `gerente`.
  - Respuesta: `200` objeto de la orden con `items`, `recepciones` y `devoluciones`; `404 NO_EXISTE`.
- `POST /ordenes-compra`
  - Roles: `admin`, `compras`.
  - Body: `{"id_proveedor": int, "id_bodega_destino": int, "items": [{"sku": str, "cantidad": number, "precio_unitario": number}]}`. (Acepta `cantidad_pedida` como alias de `cantidad`).
  - Flujo: valida proveedor activo en `ms-proveedores`, inserta en estado `BORRADOR`, asigna `numero`, publica `OrdenCompraActualizada`.
  - Respuesta: `201` orden creada | `422 VALIDACION` / `PROVEEDOR_NO_EXISTE` / `PROVEEDOR_INACTIVO` | `503 SERVICIO_NO_DISPONIBLE`.
- `PUT /ordenes-compra/<id>`
  - Roles: `admin`, `compras`.
  - Body: igual a `POST /ordenes-compra`.
  - Regla: solo editable si `estado == 'BORRADOR'`; de lo contrario `409 ESTADO_NO_EDITABLE`. Publica `OrdenCompraActualizada`.
- `POST /ordenes-compra/<id>/aprobar`
  - Roles: `admin`, `gerente`.
  - Regla: transicion `BORRADOR -> APROBADA`; publica `OrdenCompraActualizada`. Devuelve `409 TRANSICION_INVALIDA` en otro estado.
- `POST /ordenes-compra/<id>/anular`
  - Roles: `admin`, `gerente`.
  - Body: `{"motivo": str}` (obligatorio -> `422 VALIDACION`).
  - Regla: permitido en `BORRADOR` o `APROBADA` sin recepciones registradas (`409 TRANSICION_INVALIDA` si incumple). Publica `OrdenCompraActualizada`.

### Recepciones y Devoluciones
- `POST /ordenes-compra/<id>/recepciones`
  - Roles: `admin`, `jefe_bodega`.
  - Body: `{"observaciones": str (opcional), "items": [{"id_detalle": int, "cantidad": number}]}`.
  - Reglas: orden debe estar en `APROBADA` o `RECIBIDA_PARCIAL` (`409 ORDEN_NO_APROBADA`); `cantidad <= cantidad_pedida - cantidad_recibida` (`409 CANTIDAD_MAYOR_QUE_PENDIENTE`); pasa a `RECIBIDA_PARCIAL` o `RECIBIDA`.
  - Eventos: publica `MercanciaRecibida` y `OrdenCompraActualizada`. Responde `201`.
- `GET /ordenes-compra/<id>/recepciones`
  - Roles: `admin`, `jefe_bodega`, `compras`, `gerente`.
  - Respuesta: `200` lista de recepciones de la orden con detalle de items.
- `POST /ordenes-compra/<id>/devoluciones`
  - Roles: `admin`, `jefe_bodega`, `compras`.
  - Body: `{"motivo": str (obligatorio), "items": [{"id_detalle": int, "cantidad": number}]}`.
  - Reglas: orden debe estar en `RECIBIDA_PARCIAL` o `RECIBIDA` (`409 TRANSICION_INVALIDA`); `cantidad <= cantidad_recibida - cantidad_devuelta` (`409 CANTIDAD_MAYOR_QUE_RECIBIDA`).
  - Evento: publica `DevolucionProveedorRegistrada`. Responde `201`.
- `GET /devoluciones-proveedor`
  - Roles: `admin`, `jefe_bodega`, `compras`.
  - Query: `id_proveedor`, `desde`, `hasta`, `page`, `per_page`.
  - Respuesta: `200 {"data": [...], "meta": {...}}`.

## 6. Comunicacion entre Servicios

### Comunicacion Sincrona (HTTP)
- **`MS-Compras` -> `MS-Proveedores`**:
  - Llamada `GET {PROVEEDORES_URL}/proveedores/{id_proveedor}` con `Authorization`, `X-User-Id`, `X-User-Role`, `X-Correlation-Id` y timeout configurado (`PROVEEDORES_TIMEOUT_SECONDS`).
  - Verifica que el proveedor exista (`404` -> `422 PROVEEDOR_NO_EXISTE`) y tenga `estado == "ACTIVO"` (`422 PROVEEDOR_INACTIVO`). Si `ms-proveedores` falla o no responde -> `503 SERVICIO_NO_DISPONIBLE`.

### Comunicacion Asincrona (RabbitMQ)
- Exchange: `inventario.eventos` (tipo `topic`, `durable=true`).
- Sobre estandar:
  `{"id_evento": uuid, "tipo": "<RoutingKey>", "fecha": "ISO-8601 UTC Z", "productor": "ms-compras", "id_correlacion": "<X-Correlation-Id>", "datos": {...}}`
- Eventos publicados:
  1. `OrdenCompraActualizada`: `datos = {id_orden, numero, id_proveedor, estado, total}` (consumido por `ms-reportes`).
  2. `MercanciaRecibida`: `datos = {id_orden, id_recepcion, id_bodega, id_usuario, items: [{sku, cantidad, costo_unitario}]}` (consumido por `ms-inventario`).
  3. `DevolucionProveedorRegistrada`: `datos = {id_orden, id_devolucion, id_bodega, id_usuario, motivo, items: [{sku, cantidad}]}` (consumido por `ms-inventario`).

## 7. Variables de Entorno

Definidas en `.env.example`:
- `PORT`: puerto HTTP local (por defecto `5000`).
- `FLASK_DEBUG`: `false` en produccion.
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_POOL_SIZE`.
- `RABBITMQ_URL`, `RABBITMQ_EXCHANGE`.
- `PROVEEDORES_URL`, `PROVEEDORES_TIMEOUT_SECONDS`.
- `SERVICE_TOKEN`: token compartido para autenticacion interna.

## 8. Comandos Utiles

### Configuracion y Migraciones Locales
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python db/aplicar_migraciones.py
```

### Ejecucion Local y Gunicorn
```bash
python run.py
# o con Gunicorn (Linux/contenedor):
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 run:app
```

### Construccion y Ejecucion Docker
```bash
docker build -t ms-compras:latest .
docker run --env-file .env -p 5003:5000 ms-compras:latest
```

### Pruebas Unitarias (`tests/`)
```bash
pip install -r requirements-dev.txt
pytest -v
```
