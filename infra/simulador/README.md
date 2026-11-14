# Simulador de Eventos de Inventario — RabbitMQ CLI

Herramienta de línea de comandos (CLI) en Python para publicar eventos de prueba en el exchange topic `inventario.eventos` de RabbitMQ, permitiendo verificar de extremo a extremo:
1. El enrutamiento hacia las colas de los microservicios (`q.notificaciones`, `q.reportes`, `q.inventario`).
2. El consumo y procesamiento idempotente en cada microservicio mediante `id_evento`.
3. El rechazo y transferencia a Dead Letter Queue (`q.<servicio>.errores`) usando la bandera `--corrupto`.

---

## 1. Instalación y Configuración

### 1.1 Requisitos Previos
- Python 3.10 o superior.
- RabbitMQ en ejecución (por ejemplo, con `docker compose up -d` en `infra/rabbitmq/`).

### 1.2 Entorno Virtual e Instalación de Dependencias
Desde la carpeta `infra/simulador/`:

```bash
# Crear entorno virtual
python3 -m venv .venv

# Activar entorno virtual
source .venv/bin/activate

# Instalar dependencias requeridas (pika y python-dotenv)
pip install -r requirements.txt
```

> **Propósito de los paquetes:**
> - `pika`: Cliente AMQP 0-9-1 oficial de Python para conectar, publicar y gestionar propiedades en RabbitMQ.
> - `python-dotenv`: Permite leer automáticamente las credenciales desde `infra/rabbitmq/.env` si está presente.

---

## 2. Variables de Entorno

El script detecta automáticamente el archivo `infra/rabbitmq/.env`. Si no existe o no se especifican variables, utiliza los siguientes valores por defecto:

| Variable | Valor por Defecto | Descripción |
|---|---|---|
| `RABBITMQ_HOST` | `127.0.0.1` | Dirección IP o host del broker. |
| `RABBITMQ_PORT` | `5672` | Puerto estándar del protocolo AMQP. |
| `RABBITMQ_DEFAULT_USER` / `RABBITMQ_USER` | `inventario` | Usuario con permisos en el vhost. |
| `RABBITMQ_DEFAULT_PASS` / `RABBITMQ_PASS` | `inventario_secret` | Contraseña de autenticación. |
| `RABBITMQ_VHOST` | `/` | Virtual host destino. |
| `RABBITMQ_EXCHANGE` | `inventario.eventos` | Exchange de tipo topic. |

---

## 3. Estructura del Sobre de Evento (JSON Envelope)

Todo evento emitido por este publicador cumple estrictamente con el estándar definido para la arquitectura de microservicios:

```json
{
  "id_evento": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "tipo": "StockBajoUmbral",
  "fecha": "2026-11-13T22:54:52Z",
  "productor": "ms-inventario",
  "id_correlacion": "c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90",
  "datos": { ... }
}
```

- `id_evento`: Identificador único (UUID v4) del evento para control de **idempotencia**.
- `tipo`: Nombre canónico del evento que actúa también como **routing key** de RabbitMQ.
- `fecha`: Marca de tiempo en UTC con formato **ISO 8601** terminada en `Z`.
- `productor`: Identificador del microservicio emisor (`ms-inventario`, `ms-compras`, etc.).
- `id_correlacion`: Identificador de trazabilidad distribuida (`X-Correlation-Id`).
- `datos`: Objeto con la carga útil específica del evento.

---

## 4. Comandos Rápidos por Plantilla

### 4.1 Evento `StockBajoUmbral`
Consumido por: `q.notificaciones` y `q.reportes`.

```bash
python3 publicar_evento.py StockBajoUmbral --sku LAC-0001 --bodega 1 --saldo 4.000 --minimo 10.000
```

### 4.2 Evento `MovimientoRegistrado`
Consumido por: `q.reportes`.

```bash
python3 publicar_evento.py MovimientoRegistrado --id-movimiento 101 --sku LAC-0001 --bodega 1 --tipo SALIDA --cantidad 2.000 --costo-unitario 3150.0000 --saldo-resultante 4.000 --costo-promedio 3150.0000 --valor-resultante 12600.00
```

### 4.3 Evento `OrdenCompraActualizada`
Consumido por: `q.reportes`.

```bash
python3 publicar_evento.py OrdenCompraActualizada --id-orden 15 --numero OC-0015 --proveedor 3 --estado APROBADA --total 450000.00
```

---

## 5. Pruebas Especiales de Arquitectura

### 5.1 Prueba de Idempotencia (`--id-evento`)
Para validar que el consumidor ignora un evento repetido y no vuelve a procesar ni generar notificaciones duplicadas:

```bash
# Publicar por primera vez con un ID fijo
python3 publicar_evento.py StockBajoUmbral --id-evento 11111111-2222-3333-4444-555555555555 --sku LAC-0001 --saldo 3.0

# Publicar por segunda vez con el MISMO ID
python3 publicar_evento.py StockBajoUmbral --id-evento 11111111-2222-3333-4444-555555555555 --sku LAC-0001 --saldo 3.0
```
*Resultado esperado:* El consumidor detecta en su tabla o colección `eventos_procesados` que el `id_evento` ya fue registrado, descarta la operación y emite el `ack` inmediatamente.

### 5.2 Prueba de Rechazo y Dead Lettering (`--corrupto`)
Para verificar que un mensaje con carga incompleta o no procesable es rechazado por el consumidor (`nack` con `requeue=true`) y, tras 3 intentos, RabbitMQ lo desvía automáticamente a la cola de errores (`q.<servicio>.errores`):

```bash
python3 publicar_evento.py StockBajoUmbral --corrupto
```

*Resultado esperado:*
1. El publicador emite un payload que deliberadamente omite campos esenciales (`sku`, `saldo`, `stock_minimo`).
2. El consumidor falla en validar los datos requeridos y envía `nack(requeue=true)`.
3. RabbitMQ registra `x-delivery-count = 1, 2, 3`.
4. Al superar el límite `x-delivery-limit: 3`, RabbitMQ traslada el mensaje mediante el dead-letter-exchange `inventario.errores` hacia `q.notificaciones.errores` y `q.reportes.errores`.
5. El mensaje queda almacenado en la Dead Letter Queue con el encabezado de auditoría `x-death`.

---

## 6. Opciones Generales

| Opción | Descripción |
|---|---|
| `--id-evento <UUID>` | Fija un ID de evento en lugar de generar un UUID aleatorio. |
| `--id-correlacion <UUID>` | Fija un ID de correlación específico. |
| `--productor <NOMBRE>` | Sobrescribe el microservicio productor. |
| `--corrupto` | Genera intencionalmente un payload incompleto. |
| `--host <HOST>` | Sobrescribe el host de RabbitMQ. |
| `--port <PUERTO>` | Sobrescribe el puerto de RabbitMQ. |
| `--user <USUARIO>` | Sobrescribe el usuario de conexión. |
| `--password <PASS>` | Sobrescribe la contraseña de conexión. |
