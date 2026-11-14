# Directrices de Desarrollo y Arquitectura — MS-Reportes

Este documento contiene las reglas estrictas de arquitectura, convenciones de código y estándares de ingeniería que cualquier agente de inteligencia artificial o desarrollador DEBE obedecer siempre que trabaje dentro de la carpeta `MS-Reportes/`.

Estas reglas replican exactamente la arquitectura, estructura de archivos y convenciones de base de datos observadas en el microservicio de referencia (`.referencia/ms-productos`).

---

## 1. Contexto General del Sistema

- **Sistema:** Gestión de Inventarios basado en microservicios (Entrega 3).
- **Rol del Microservicio:** Generación de reportes analíticos de inventario (valorización por costo promedio ponderado, análisis de rotación de productos, alertas de stock bajo) y agregación de indicadores clave de rendimiento (KPIs) para el dashboard central.
- **Modelo de Lectura Asíncrono (CQRS Parcial):**
  - Mantiene un modelo relacional de solo lectura en MySQL optimizado para consultas agregadas.
  - Se alimenta de forma asíncrona consumiendo eventos de RabbitMQ: `MovimientoRegistrado`, `OrdenCompraActualizada` y `StockBajoUmbral`.
- **Topología de Red y Enrutamiento:**
  - Todo el tráfico externo proveniente de clientes o frontend entra por el **API Gateway** en Laravel.
  - El Gateway valida el token de autenticación (Laravel Sanctum), verifica permisos de usuario y reenvía las peticiones **eliminando el prefijo `/api`** (por ejemplo: la petición externa `GET /api/reportes/valorizacion` se reenvía a este microservicio como `GET /reportes/valorizacion`).
  - **Acceso Directo Prohibido:** Ningún cliente externo se comunica directamente con este microservicio; solo el Gateway tiene acceso HTTP.
- **Comunicación Interna entre Microservicios:**
  - Para enriquecer los reportes con nombres de productos y categorías, este microservicio consulta síncronamente vía REST a `ms-productos` utilizando la librería `requests`.

---

## 2. Stack Tecnológico Obligatorio

| Componente | Tecnología / Librería | Propósito |
|---|---|---|
| **Lenguaje** | Python 3 (3.11+ / 3.12+) | Lenguaje principal de desarrollo. |
| **Framework Web** | Flask (>= 3.1) | Servidor API REST y enrutamiento con Blueprints. |
| **Servidor WSGI** | Gunicorn | Servidor de aplicaciones HTTP para producción/contenedores. |
| **Acceso a Base de Datos** | `mysql-connector-python` | **SQL puro parametrizado, estrictamente sin ORM** (estilo `.referencia/ms-productos`). |
| **Broker de Mensajería** | `pika` | Cliente AMQP 0-9-1 para el consumo de eventos desde RabbitMQ. |
| **Cliente HTTP Saliente** | `requests` | Consultas síncronas hacia el microservicio `ms-productos`. |
| **Variables de Entorno** | `python-dotenv` | Carga de variables locales de configuración. |

---

## 3. Estructura Canónica de Archivos y Carpetas

La estructura de `MS-Reportes/` debe ser **idéntica** a la de `.referencia/ms-productos`, incorporando el consumidor de RabbitMQ y el cliente HTTP para `ms-productos`:

```text
MS-Reportes/
├── AGENTS.md                   # Este archivo de reglas
├── Dockerfile                  # Empaquetado Docker
├── .dockerignore
├── .env.example                # Plantilla de variables de entorno (sin valores reales)
├── .gitignore
├── requirements.txt            # Dependencias de producción
├── requirements-dev.txt        # Dependencias de pruebas (pytest, etc.)
├── pytest.ini
├── README.md                   # Documentación técnica del microservicio
├── run.py                      # Entrada para servidor web Flask
├── consumidor.py               # Entrada independiente para el worker de RabbitMQ (pika)
├── app/
│   ├── __init__.py             # create_app(): configuración, json_provider, auth, errors, blueprints
│   ├── config.py               # cargar_configuracion(): lectura desde .env y entorno
│   ├── auth.py                 # registrar_autenticacion(): validación de SERVICE_TOKEN
│   ├── db.py                   # abrir_conexion() y contextmanager transaccion() (sin ORM)
│   ├── errors.py               # ApiError, ERRORES_HTTP y registro centralizado de errores
│   ├── json_provider.py        # Serialización JSON (fechas ISO UTC, Decimal, ensure_ascii=False)
│   ├── paginacion.py           # leer_paginacion() y respuesta_paginada() (?page=1&per_page=20)
│   ├── validacion.py           # Clase Errores y validadores (entero, texto, fechas, decimal)
│   ├── clientes/
│   │   ├── __init__.py
│   │   └── productos.py        # Cliente HTTP con requests para consultar ms-productos
│   ├── repositorios/
│   │   ├── __init__.py
│   │   ├── reportes.py         # Consultas SQL para valorización, rotación y stock bajo
│   │   ├── dashboard.py        # Consultas SQL agregadas para métricas del dashboard
│   │   └── eventos.py          # Actualización SQL de saldos/movimientos y eventos_procesados
│   └── routes/
│       ├── __init__.py
│       ├── health.py           # Blueprint GET /health (pública)
│       ├── reportes.py         # Blueprint GET /reportes/valorizacion, /rotacion, /stock-bajo
│       └── dashboard.py        # Blueprint GET /dashboard
├── db/
│   ├── __init__.py
│   ├── aplicar_migraciones.py  # Gestor de migraciones SQL (idéntico a referencia)
│   └── 001_tablas_reportes.sql # Definición DDL de tablas en MySQL
└── tests/                      # Pruebas con pytest
```

---

## 4. Convenciones de Base de Datos (MySQL) y Acceso a Datos

Siguiendo estrictamente las convenciones de `.referencia/ms-productos`:

### 4.1 Sin ORM — Solo Consultas SQL Parametrizadas
- **Prohibido el uso de ORMs** (nada de SQLAlchemy, Peewee, etc.).
- Todas las consultas deben ejecutarse a través de un cursor de diccionarios (`dictionary=True`) obtenido del gestor de contexto `transaccion()` definido en `app/db.py`.
- **Parametrización Obligatoria:** Todas las variables externas deben pasarse con `%s` en una tupla/lista de parámetros. **Queda terminantemente prohibido concatenar o interpolar (`f"..."`) valores dentro de sentencias SQL.**
- Las constantes de columnas (`COLUMNAS = "..."`), órdenes (`ORDER BY ...`) y fragmentos estructurados de consulta deben definirse como constantes inmutables en los módulos de `app/repositorios/`.

### 4.2 Manejo de Conexiones y Transacciones (`app/db.py`)
- Abrir una conexión por petición con:
  - `time_zone="+00:00"` (todas las marcas de tiempo se almacenan y operan en UTC).
  - `autocommit=False`.
  - `charset="utf8mb4"` y `collation="utf8mb4_0900_ai_ci"`.
  - `connection_timeout=5`.
- Las excepciones `mysql.connector.Error` deben capturarse y traducirse a:
  ```python
  raise ApiError("SERVICIO_NO_DISPONIBLE", "La base de datos no está disponible.", 503) from None
  ```
  (sin filtrar credenciales ni detalles internos en los mensajes al cliente).
- El contextmanager `transaccion()` debe iniciar transacción, entregar el cursor, hacer `commit()` al completar con éxito, `rollback()` ante excepciones y **cerrar siempre el cursor y la conexión en el bloque `finally`**.

### 4.3 Sistema de Migraciones SQL (`db/aplicar_migraciones.py`)
- Se ejecutan con el comando: `python -m db.aplicar_migraciones`.
- Se registra cada script ejecutado en la tabla `migraciones_aplicadas`.
- Los scripts en `db/*.sql` deben usar:
  - Nombres ordenados: `001_xxx.sql`, `002_xxx.sql`.
  - Sintaxis compatible: `CREATE TABLE IF NOT EXISTS ...`.
  - Configuración de tabla: `ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;`.
  - Fechas: `DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP())`.

### 4.4 Esquema de Tablas de MS-Reportes

1. **`saldo_reporte`** (Alimentada por `MovimientoRegistrado`):
   ```sql
   CREATE TABLE IF NOT EXISTS saldo_reporte (
       sku VARCHAR(50) NOT NULL,
       id_bodega INT NOT NULL,
       cantidad DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
       costo_promedio DECIMAL(14, 4) NOT NULL DEFAULT 0.0000,
       valor_total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
       actualizado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
       PRIMARY KEY (sku, id_bodega),
       KEY idx_saldo_reporte_bodega (id_bodega),
       KEY idx_saldo_reporte_sku (sku)
   ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
   ```

2. **`movimiento_diario`** (Rotación y estadísticas diarias por producto):
   ```sql
   CREATE TABLE IF NOT EXISTS movimiento_diario (
       sku VARCHAR(50) NOT NULL,
       id_bodega INT NOT NULL,
       fecha DATE NOT NULL,
       entradas DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
       salidas DECIMAL(14, 3) NOT NULL DEFAULT 0.000,
       PRIMARY KEY (sku, id_bodega, fecha),
       KEY idx_movimiento_diario_fecha (fecha),
       KEY idx_movimiento_diario_sku (sku)
   ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
   ```

3. **`orden_pendiente`** (Alimentada por `OrdenCompraActualizada`):
   ```sql
   CREATE TABLE IF NOT EXISTS orden_pendiente (
       id_orden INT NOT NULL,
       id_proveedor INT NOT NULL,
       estado VARCHAR(30) NOT NULL,
       total DECIMAL(14, 2) NOT NULL DEFAULT 0.00,
       actualizada_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
       PRIMARY KEY (id_orden),
       KEY idx_orden_pendiente_estado (estado)
   ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
   ```

4. **`alerta_stock`** (Alimentada por `StockBajoUmbral`):
   ```sql
   CREATE TABLE IF NOT EXISTS alerta_stock (
       sku VARCHAR(50) NOT NULL,
       id_bodega INT NOT NULL,
       saldo DECIMAL(14, 3) NOT NULL,
       stock_minimo DECIMAL(14, 3) NOT NULL,
       fecha DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
       activa BOOLEAN NOT NULL DEFAULT TRUE,
       PRIMARY KEY (sku, id_bodega),
       KEY idx_alerta_stock_activa (activa)
   ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
   ```

5. **`evento_procesado`** (Idempotencia en RabbitMQ):
   ```sql
   CREATE TABLE IF NOT EXISTS evento_procesado (
       id_evento VARCHAR(36) NOT NULL,
       tipo VARCHAR(60) NOT NULL,
       procesado_en DATETIME NOT NULL DEFAULT (UTC_TIMESTAMP()),
       PRIMARY KEY (id_evento)
   ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
   ```

---

## 5. Contratos HTTP Transversales

### 5.1 Autenticación de Servicios (`SERVICE_TOKEN`)
- Validar `Authorization: Bearer <SERVICE_TOKEN>` en **todas las rutas** mediante `app/auth.py`.
- Única ruta excluida: `GET /health` (pública, retorna `{"status": "ok"}`).
- La comparación del token debe usar `hmac.compare_digest(recibido.encode(), esperado)`.
- Si el token falta o es incorrecto, responder inmediatamente HTTP **401**:
  ```json
  {
    "error": {
      "codigo": "NO_AUTENTICADO",
      "mensaje": "Token de servicio ausente o inválido.",
      "detalles": null
    }
  }
  ```

### 5.2 Encabezados de Contexto y Correlación
- `X-User-Id`: ID del usuario que solicita la operación.
- `X-User-Role`: Rol del usuario autenticado.
- `X-Correlation-Id`: Identificador único de correlación.
  - Se debe capturar en `before_request`.
  - **Debe propagarse** en la respuesta HTTP (`response.headers["X-Correlation-Id"]`).
  - **Debe propagarse** en llamadas síncronas salientes hacia `ms-productos`.
  - **Debe incluirse** en los registros de logging.

### 5.3 Formato Único de Errores
Toda respuesta de error debe devolver la estructura uniforme:

```json
{
  "error": {
    "codigo": "CODIGO_MAYUSCULAS",
    "mensaje": "Explicación clara del error.",
    "detalles": null
  }
}
```

Códigos HTTP mapeados:
- **400** (`PETICION_INVALIDA`): Petición con sintaxis o parámetros inválidos.
- **401** (`NO_AUTENTICADO`): Token de servicio ausente o inválido.
- **403** (`SIN_PERMISO`): Sin autorización para el recurso.
- **404** (`NO_EXISTE`): Recurso solicitado no encontrado.
- **409** (`CONFLICTO`): Conflicto con el estado actual.
- **422** (`VALIDACION`): Error de validación en parámetros o filtros (ej. `precio_min > precio_max`, fechas incongruentes).
- **503** (`SERVICIO_NO_DISPONIBLE`): Base de datos no disponible o fallo al contactar `ms-productos`.

### 5.4 Paginación Estándar
- Parámetros por query string: `?page=1&per_page=20` (máximo `100`).
- Implementado mediante `leer_paginacion()` y `respuesta_paginada()` en `app/paginacion.py`.
- Formato de respuesta:
  ```json
  {
    "data": [ ... ],
    "meta": {
      "page": 1,
      "per_page": 20,
      "total": 100
    }
  }
  ```

---

## 6. Endpoints del Microservicio y Consultas Síncronas

### 6.1 Catálogo de Rutas HTTP

| Método | Ruta | Roles | Parámetros Query | Respuesta / Propósito |
|---|---|---|---|---|
| `GET` | `/health` | Público | Ninguno | Estado del servicio (`200 OK`). |
| `GET` | `/reportes/valorizacion` | Todos | `agrupar` (`producto`, `categoria`, `bodega`), `id_bodega`, `formato` (`json`, `csv`, `pdf`), `page`, `per_page` | Reporte de valorización de inventario por costo promedio (RF11). |
| `GET` | `/reportes/rotacion` | Todos | `desde`, `hasta`, `id_bodega`, `top` (def. 10), `formato` (`json`, `csv`, `pdf`), `page`, `per_page` | Productos de mayor y menor rotación calculados con base en entradas y salidas (RF11). |
| `GET` | `/reportes/stock-bajo` | Todos | `id_bodega`, `page`, `per_page` | Lista de productos con stock actual inferior o igual al mínimo fijado. |
| `GET` | `/dashboard` | Todos | Ninguno | Resumen consolidado: `{valor_total_inventario, productos_stock_bajo, ordenes_pendientes, mayor_rotacion, menor_rotacion}` (RF14). |

### 6.2 Integración Síncrona con `ms-productos` (`app/clientes/productos.py`)
- Para presentar el nombre del producto, categoría y marca en los reportes:
  - Realizar peticiones HTTP usando la librería `requests`.
  - Configurar timeout estricto (por ejemplo, `timeout=5.0`).
  - Propagar los encabezados `Authorization: Bearer <SERVICE_TOKEN>` y `X-Correlation-Id`.
  - Si `ms-productos` no responde o arroja un error 5xx, lanzar:
    ```python
    raise ApiError("SERVICIO_NO_DISPONIBLE", "El microservicio de productos no está disponible.", 503)
    ```

---

## 7. Mensajería Asíncrona con RabbitMQ (`consumidor.py`)

### 7.1 Configuración de Infraestructura AMQP

- **Exchange Principal:**
  - Nombre: `inventario.eventos`
  - Tipo: `topic`
  - Opciones: `durable=True`
- **Exchange de Errores (Dead Letter):**
  - Nombre: `inventario.errores`
  - Tipo: `topic` (o `direct`)
  - Opciones: `durable=True`
- **Cola del Microservicio:**
  - Nombre: `q.reportes`
  - Argumentos de cola Quorum:
    ```python
    argumentos = {
        "x-queue-type": "quorum",
        "x-delivery-limit": 3,
        "x-dead-letter-exchange": "inventario.errores",
        "x-dead-letter-routing-key": "q.reportes.errores",
    }
    ```
  - Cola DLQ: `q.reportes.errores` (enlazada al exchange `inventario.errores`).
- **Bindings (Routing Keys a escuchar en `inventario.eventos`):**
  - `MovimientoRegistrado`
  - `OrdenCompraActualizada`
  - `StockBajoUmbral`

### 7.2 Formato del Evento (Sobre JSON)

```json
{
  "id_evento": "UUID",
  "tipo": "NombreDelEvento",
  "fecha": "2026-11-13T18:00:00Z",
  "productor": "ms-inventario|ms-compras",
  "id_correlacion": "UUID",
  "datos": { ... }
}
```

### 7.3 Protocolo de Consumo e Idempotencia Transaccional

El procesamiento debe ejecutarse en el proceso independiente `consumidor.py` con `pika`:

1. **Recepción del Mensaje:** Deserializar el payload JSON y extraer `id_evento`.
2. **Transacción Atómica en MySQL:**
   ```python
   with transaccion() as cursor:
       # Paso A: Verificar si el evento ya fue procesado
       cursor.execute("SELECT id_evento FROM evento_procesado WHERE id_evento = %s", (id_evento,))
       if cursor.fetchone():
           # Ya procesado: se descarta sin duplicar efectos
           ch.basic_ack(delivery_tag=method.delivery_tag)
           return

       # Paso B: Aplicar actualización según el tipo de evento
       if tipo == "MovimientoRegistrado":
           # Actualizar saldo_reporte y acumular en movimiento_diario
           ...
       elif tipo == "OrdenCompraActualizada":
           # Insertar o actualizar orden_pendiente (o eliminar si pasa a RECIBIDA/ANULADA)
           ...
       elif tipo == "StockBajoUmbral":
           # Registrar o actualizar alerta_stock
           ...

       # Paso C: Registrar idempotencia
       cursor.execute(
           "INSERT INTO evento_procesado (id_evento, tipo) VALUES (%s, %s)",
           (id_evento, tipo),
       )
   ```
3. **Confirmación Manual (`ack`):**
   - Ejecutar `ch.basic_ack(delivery_tag=method.delivery_tag)` **ÚNICAMENTE DESPUÉS** de que la transacción en MySQL haya hecho commit exitoso.
4. **Manejo de Errores y Reintentos (`nack`):**
   - Si ocurre una excepción durante la transacción o fallo de base de datos:
     ```python
     ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
     ```
   - Al marcar `requeue=True`, RabbitMQ reintentará la entrega hasta alcanzar el límite de 3 entregas (`x-delivery-limit: 3`). En el tercer fallo, el broker lo trasladará automáticamente a `inventario.errores` y de ahí a `q.reportes.errores`.

---

## 8. Reglas de Trabajo del Agente

Cualquier agente que opere dentro de `MS-Reportes/` debe cumplir estrictamente las siguientes directrices:

1. **No instalar paquetes sin explicar su propósito:** Antes de sugerir o ejecutar comandos de instalación (ej. `pip install`), se debe documentar en el chat la justificación técnica de cada librería y agregarla a `requirements.txt`.
2. **Confidencialidad absoluta de `.env`:** NUNCA leer, consultar ni imprimir en pantalla el archivo `.env`. Toda variable de entorno debe documentarse exclusivamente en `.env.example` con valores de ejemplo genéricos.
3. **Aislamiento de carpeta:** No modificar ni crear archivos fuera de la carpeta `MS-Reportes/`.
4. **Prohibición de comandos Git:** No ejecutar `git commit`, `git push`, `git checkout` ni comandos que alteren el control de versiones.
5. **Explicación didáctica:** Todo archivo, módulo o función creado debe ser explicado paso a paso, indicando su rol dentro de la arquitectura de microservicios y su congruencia con el microservicio de referencia.
