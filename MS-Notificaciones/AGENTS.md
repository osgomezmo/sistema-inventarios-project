# Directrices de Desarrollo y Arquitectura — MS-Notificaciones

Este documento contiene las reglas estrictas de arquitectura, diseño y desarrollo que cualquier agente de inteligencia artificial o desarrollador DEBE obedecer siempre que trabaje dentro de la carpeta `MS-Notificaciones/`.

---

## 1. Contexto General del Sistema

- **Sistema:** Gestión de Inventarios basado en arquitectura de microservicios (Entrega 3).
- **Rol del Microservicio:** Recepción asíncrona de alertas del sistema (especialmente `StockBajoUmbral`), registro histórico de alertas y envío de notificaciones push móviles/web mediante Firebase Cloud Messaging (FCM) a los roles correspondientes (`Compras`, `Jefe de bodega`). Persistencia documental en Google Cloud Firestore.
- **Topología de Red y Enrutamiento:**
  - Todo el tráfico externo proveniente de usuarios o clientes frontend ingresa a través del **API Gateway** desarrollado en Laravel.
  - El Gateway valida el token de autenticación de usuario (Laravel Sanctum), verifica roles y permisos, y reenvía las peticiones hacia los microservicios internos **eliminando el prefijo `/api`** (por ejemplo: la petición externa `GET /api/notificaciones` llega a este microservicio como `GET /notificaciones`).
  - **Acceso Directo Prohibido:** Ningún cliente externo tiene acceso directo a este servicio. El servicio solo responde peticiones originadas por el Gateway o eventos de RabbitMQ.

---

## 2. Stack Tecnológico Obligatorio

| Componente | Tecnología / Librería | Propósito |
|---|---|---|
| **Plataforma de Ejecución** | Node.js (v20+ LTS) | Entorno de ejecución JavaScript del lado del servidor. |
| **Framework Web** | Express.js | Servidor HTTP y enrutamiento de peticiones internas. |
| **Persistencia y Push** | `firebase-admin` | Conexión con Google Cloud Firestore y Firebase Cloud Messaging (FCM). |
| **Broker de Mensajería** | `amqplib` | Conexión y consumo de eventos en RabbitMQ vía AMQP 0-9-1. |
| **Variables de Entorno** | `dotenv` | Carga segura de variables de configuración local. |

### Soporte Obligatorio de Modo Local y Abstracción de Notificador

El microservicio debe funcionar tanto en entornos de producción en la nube como en entornos locales de desarrollo y pruebas automatizadas donde no se disponga de credenciales reales de Google/Firebase:

1. **Variable `FIREBASE_MODE`:**
   - `FIREBASE_MODE=production`: Inicializa el SDK de `firebase-admin` usando las credenciales oficiales de la cuenta de servicio (`GOOGLE_APPLICATION_CREDENTIALS` o clave JSON).
   - `FIREBASE_MODE=local`: Conecta con los emuladores de Firebase (ej. `FIRESTORE_EMULATOR_HOST`) o utiliza una implementación simulada en memoria para no bloquear la ejecución cuando no existan credenciales en la máquina del desarrollador.
2. **Interfaz / Patrón Estrategia `Notificador`:**
   - Se debe definir una abstracción desacoplada para el despacho de notificaciones:
     - `NotificadorFCM`: Implementación real que invoca `admin.messaging().send(...)` o envía a tópicos de FCM (ej. `/topics/rol_compras`, `/topics/rol_jefe_de_bodega`).
     - `NotificadorConsola`: Implementación para pruebas y desarrollo local que formatea y muestra en los logs/consola el contenido del mensaje sin arrojar excepciones de red ni depender de credenciales de Google.
   - La selección del notificador activo se resuelve dinámicamente mediante una factoría basada en `FIREBASE_MODE`.

---

## 3. Estructura de Carpetas Obligatoria

Toda la base de código dentro de `MS-Notificaciones/` debe organizarse bajo la siguiente estructura modular:

```text
MS-Notificaciones/
├── AGENTS.md                   # Este archivo de reglas
├── Dockerfile                  # Empaquetado para Docker/Kubernetes
├── .dockerignore
├── .env.example                # Plantilla de variables de entorno (sin secretos)
├── .gitignore
├── package.json                # Definición de proyecto y dependencias
├── README.md                   # Documentación técnica del servicio
├── src/
│   ├── config/
│   │   ├── env.js              # Carga y validación de variables de entorno
│   │   ├── firebase.js         # Inicialización de Firebase Admin (según FIREBASE_MODE)
│   │   └── rabbitmq.js         # Configuración y constantes de AMQP
│   ├── middleware/
│   │   ├── auth.js             # Validación de Authorization: Bearer <SERVICE_TOKEN>
│   │   ├── correlation.js      # Lectura y propagación de X-Correlation-Id
│   │   └── errors.js           # Manejador global de errores (formato estándar)
│   ├── notificador/
│   │   ├── notificador.interface.js  # Definición conceptual de la interfaz
│   │   ├── notificador-consola.js    # Notificador para modo local
│   │   ├── notificador-fcm.js        # Notificador real vía Firebase Cloud Messaging
│   │   └── index.js                  # Factoría que instancia la implementación adecuada
│   ├── messaging/
│   │   ├── consumidor.js       # Conexión AMQP, aserción de exchanges/colas y ciclo de consumo
│   │   └── manejadores/
│   │       └── stock-bajo.js   # Lógica al recibir StockBajoUmbral
│   ├── repositories/
│   │   ├── notificaciones.repository.js  # Operaciones en colección 'notificaciones'
│   │   ├── dispositivos.repository.js    # Operaciones en colección 'dispositivos'
│   │   └── eventos.repository.js         # Idempotencia en colección 'eventos_procesados'
│   ├── routes/
│   │   ├── health.routes.js          # GET /health
│   │   ├── dispositivos.routes.js    # POST, DELETE /dispositivos
│   │   └── notificaciones.routes.js  # GET, POST /notificaciones
│   ├── utils/
│   │   ├── api-error.js        # Clase personalizada de excepción
│   │   └── paginacion.js       # Utilidades para ?page=X&per_page=Y
│   ├── app.js                  # Configuración de Express, middlewares y rutas
│   └── server.js               # Punto de entrada: levanta HTTP y arranca consumidor RabbitMQ
└── tests/                      # Pruebas unitarias y de integración
```

---

## 4. Contratos HTTP Transversales

### 4.1 Autenticación de Servicios (`SERVICE_TOKEN`)
- En **todas las rutas** (con la única excepción de `GET /health`), es obligatorio validar el encabezado:
  ```http
  Authorization: Bearer <SERVICE_TOKEN>
  ```
- Si el encabezado no está presente, no inicia con `Bearer ` o el token no coincide exactamente con el `SERVICE_TOKEN` configurado en el entorno, se debe rechazar inmediatamente la petición con estado HTTP **401**:
  ```json
  {
    "error": {
      "codigo": "NO_AUTENTICADO",
      "mensaje": "Token de servicio ausente o inválido.",
      "detalles": null
    }
  }
  ```
- La ruta `GET /health` es pública y responde `{"status": "ok"}` con código HTTP 200 sin exigir token.

### 4.2 Encabezados de Contexto y Trazabilidad
El Gateway reenvía información contextual del usuario autenticado en encabezados HTTP. El servicio debe leerlos:
- `X-User-Id`: Identificador único del usuario que realiza la operación (entero o UUID). Utilizado para asociar el registro de dispositivos o auditar acciones.
- `X-User-Role`: Rol asignado al usuario (`Administrador`, `Jefe de bodega`, `Compras`, `Gerente`). Utilizado para suscribir dispositivos al tema correspondiente o filtrar notificaciones legibles.
- `X-Correlation-Id`: Identificador único de correlación transversal (UUID).
  - **Obligatorio:** Se debe capturar en un middleware inicial.
  - Si no viene en la petición, generar uno nuevo.
  - **Debe propagarse** en el encabezado de respuesta HTTP (`X-Correlation-Id`).
  - **Debe incluirse** en todos los logs emitidos durante el procesamiento de la petición.

### 4.3 Formato Único de Error
Todas las respuestas de error en la API deben cumplir estrictamente la siguiente estructura JSON uniforme:

```json
{
  "error": {
    "codigo": "CODIGO_MAYUSCULAS",
    "mensaje": "Descripción legible y comprensible del error.",
    "detalles": null
  }
}
```

- `detalles`: puede ser `null` o un objeto con detalles de validación campo por campo (por ejemplo: `{"token_fcm": ["El campo es requerido"]}`).
- Los códigos de estado HTTP permitidos y sus códigos de negocio estándar son:

| Código HTTP | Código en JSON | Escenario de uso |
|---|---|---|
| **400** | `PETICION_INVALIDA` | Petición mal formada, JSON inválido o parámetros de ruta erróneos. |
| **401** | `NO_AUTENTICADO` | `SERVICE_TOKEN` ausente, inválido o expirado. |
| **403** | `SIN_PERMISO` | El usuario carece de permisos para acceder o modificar el recurso. |
| **404** | `NO_EXISTE` | Notificación o dispositivo solicitado no encontrado en Firestore. |
| **409** | `CONFLICTO` | Conflicto con el estado actual del recurso (ej. duplicidad irreconciliable). |
| **422** | `VALIDACION` | Parámetros del cuerpo o query string que no superan las reglas de validación. |
| **503** | `SERVICIO_NO_DISPONIBLE` | Fallo de conexión o indisponibilidad temporal de Firestore, FCM o RabbitMQ. |

### 4.4 Paginación Estándar
Todos los listados paginados reciben por query string:
- `page`: Número de página (entero $\ge 1$, por defecto `1`).
- `per_page`: Cantidad de elementos por página (entero entre `1` y `100`, por defecto `20`).

La respuesta debe estructurarse obligatoriamente de la siguiente manera:
```json
{
  "data": [
    { ... }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 45
  }
}
```

---

## 5. Endpoints del Microservicio

| Método | Ruta | Roles autorizados | Descripción | Códigos HTTP |
|---|---|---|---|---|
| `GET` | `/health` | Público | Comprobación de salud del servicio. | `200` |
| `POST` | `/dispositivos` | Todos | Registra el token FCM de un dispositivo móvil/web y lo suscribe al tema de Firebase correspondiente a su rol. | `201`, `422`, `503` |
| `DELETE` | `/dispositivos/:id` | Dueño o Admin | Elimina el registro del dispositivo y cancela su suscripción al tema. | `204`, `404`, `503` |
| `GET` | `/notificaciones` | Todos | Consulta el historial de notificaciones. Soporta `?page=1&per_page=20` y filtro `?leida=true\|false`. Filtra por el rol o destinatario del usuario solicitante. | `200`, `422`, `503` |
| `POST` | `/notificaciones/:id/leida` | Todos | Marca una notificación específica como leída (`leida: true`). | `200`, `404`, `503` |

> **Nota Crítica de Negocio:** Las notificaciones **no se crean a través de endpoints HTTP**. Nacen exclusivamente del consumo asíncrono del evento `StockBajoUmbral` proveniente de RabbitMQ.

---

## 6. Persistencia en Google Cloud Firestore

Las colecciones y campos estándar son:

1. **Colección `notificaciones`:**
   - `id_notificacion` (String / UUID autogenerado)
   - `tipo` (String, ej. `'STOCK_BAJO'`)
   - `titulo` (String, ej. `'Alerta de Stock Bajo'`)
   - `mensaje` (String descriptivo)
   - `rol_destino` (String, ej. `'Compras'`, `'Jefe de bodega'`)
   - `datos` (Objeto con atributos: `sku`, `id_bodega`, `saldo`, `stock_minimo`)
   - `leida` (Boolean, por defecto `false`)
   - `creada_en` (Timestamp UTC en formato ISO 8601 o Firestore Timestamp)

2. **Colección `dispositivos`:**
   - `id_dispositivo` (String / UUID)
   - `id_usuario` (Entero o String obtenido de `X-User-Id`)
   - `rol` (String obtenido de `X-User-Role`)
   - `token_fcm` (String, token de registro emitido por Firebase en el cliente)
   - `plataforma` (String, ej. `'android'`, `'ios'`, `'web'`)
   - `registrado_en` (Timestamp UTC)

3. **Colección `eventos_procesados` (Idempotencia):**
   - `id_evento` (String / UUID del evento — usado preferentemente como ID del documento)
   - `tipo` (String, ej. `'StockBajoUmbral'`)
   - `procesado_en` (Timestamp UTC)

---

## 7. Mensajería Asíncrona con RabbitMQ

### 7.1 Configuración de Infraestructura AMQP

- **Exchange Principal de Eventos:**
  - Nombre: `inventario.eventos`
  - Tipo: `topic`
  - Opciones: `durable: true`
- **Exchange de Errores (Dead Letter Exchange):**
  - Nombre: `inventario.errores`
  - Tipo: `topic` (o `direct`)
  - Opciones: `durable: true`
- **Cola del Microservicio:**
  - Nombre: `q.notificaciones`
  - Tipo: Quorum queue (`x-queue-type: quorum`)
  - Límite de entregas: `x-delivery-limit: 3`
  - Dead Letter Exchange: `x-dead-letter-exchange: inventario.errores`
  - Dead Letter Routing Key: `q.notificaciones.errores`
  - Cola receptora de errores manuales: `q.notificaciones.errores` (enlazada a `inventario.errores`)
- **Binding / Enlace:**
  - Routing key de escucha: `StockBajoUmbral`

### 7.2 Formato Uniforme del Mensaje (Sobre JSON)

```json
{
  "id_evento": "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10",
  "tipo": "StockBajoUmbral",
  "fecha": "2026-11-13T18:00:00Z",
  "productor": "ms-inventario",
  "id_correlacion": "c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90",
  "datos": {
    "sku": "PRD-001",
    "id_bodega": 1,
    "saldo": 5.0,
    "stock_minimo": 10.0
  }
}
```

### 7.3 Protocolo Estricto de Consumo e Idempotencia

1. **Lectura y Validación:** Al recibir el mensaje de la cola, deserializar el JSON y extraer `id_evento`.
2. **Chequeo de Idempotencia:** Consultar la colección `eventos_procesados` en Firestore buscando el `id_evento`.
   - Si el `id_evento` **ya existe**, el mensaje es un duplicado: registrar advertencia en logs y confirmar inmediatamente con `channel.ack(msg)` sin volver a disparar notificaciones.
3. **Persistencia y Despacho:**
   - Crear el registro en la colección `notificaciones`.
   - Despachar el mensaje push a través de la interfaz `Notificador` (hacia los tópicos de los roles `Compras` y `Jefe de bodega`, o a la consola en modo local).
   - Registrar el `id_evento` en `eventos_procesados`.
4. **Confirmación Manual (`ack`):**
   - Emitir `channel.ack(msg)` **ÚNICAMENTE DESPUÉS** de que la persistencia en Firestore y el registro de idempotencia hayan finalizado con éxito.
5. **Manejo de Errores y Reintentos (`nack`):**
   - Si ocurre un fallo inesperado (ej. corte de conexión con Firestore o error de red), llamar a:
     ```javascript
     channel.nack(msg, false, true); // requeue = true
     ```
   - Al marcar `requeue=true`, RabbitMQ reintentará la entrega. Dado que la cola es de tipo *quorum* con `x-delivery-limit: 3`, al fallar en el 3er intento, RabbitMQ transferirá automáticamente el mensaje al exchange `inventario.errores` y de allí a `q.notificaciones.errores` para auditoría y rescate manual.

---

## 8. Reglas de Trabajo del Agente

Siempre que un agente trabaje dentro de `MS-Notificaciones/`, debe seguir de manera innegociable las siguientes directrices:

1. **No instalar paquetes sin explicación previa:** Antes de ejecutar cualquier `npm install`, el agente debe explicar explícitamente al usuario qué paquete necesita, por qué es imprescindible y cuál es su impacto.
2. **Confidencialidad absoluta de `.env`:** NUNCA leer, imprimir, volcar ni revelar en el chat el contenido de archivos `.env`. Toda configuración debe documentarse en `.env.example` con valores de muestra ficticios.
3. **Aislamiento de carpeta:** No modificar ni crear archivos fuera del directorio `MS-Notificaciones/` a menos que el usuario lo solicite expresamente.
4. **Prohibición de comandos Git:** No ejecutar `git commit`, `git push`, `git checkout` ni alterar el historial de control de versiones.
5. **Explicación didáctica:** Cada archivo nuevo o refactorizado debe explicarse de forma clara, detallando su responsabilidad, diseño y cómo interactúa con el resto del sistema.
