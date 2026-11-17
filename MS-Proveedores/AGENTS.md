# Guía de Operación y Arquitectura — MS-Proveedores

Este documento describe la arquitectura, contratos de API, esquema de base de datos, comunicación y convenciones de desarrollo de `MS-Proveedores/`.

---

## 1. Resumen del Microservicio

- **Rol:** Maestro de proveedores, sus contactos y la relación con los productos que suministran (`ProductoSuministrado`: SKU, precio de compra, días de entrega y estado) (RF03, RF12).
- **Topología de red y enrutamiento:**
  - El tráfico externo ingresa exclusivamente por el **API Gateway** (Laravel), que autentica al usuario (Sanctum), valida permisos y reenvía las peticiones eliminando el prefijo `/api` (ej. `GET /api/proveedores` llega como `GET /proveedores`).
  - No existe acceso directo desde clientes externos; toda ruta protegida requiere el token de servicio interno.
- **Comunicación con otros servicios:**
  - **Entrante síncrona (REST):**
    - `ms-compras` consulta `GET /proveedores/{id}` para validar que un proveedor existe y está `ACTIVO` antes de crear una orden de compra.
    - El `API Gateway` consulta `GET /proveedores/{id}/productos` para componer el filtro de productos por proveedor (`GET /api/productos?id_proveedor={id}`, RF12).
  - **Saliente síncrona / asíncrona:** Ninguna. Este microservicio no consume otros servicios REST ni publica/consume eventos en RabbitMQ.

---

## 2. Stack Tecnológico

| Componente | Tecnología / Librería | Propósito |
|---|---|---|
| **Plataforma** | Node.js 24 (`node:24-alpine`) | Entorno de ejecución JavaScript |
| **Framework Web** | Express 4 (`express`) | Servidor HTTP REST y enrutamiento |
| **Base de Datos** | MySQL 8.4 (`mysql2/promise`) | Persistencia relacional propia con SQL parametrizado (sin ORM) |
| **Configuración** | `dotenv` | Variables de entorno en desarrollo local |
| **Trazabilidad** | `uuid` | Generación de `X-Correlation-Id` de respaldo |
| **Pruebas** | `jest` + `supertest` | Pruebas unitarias y HTTP aisladas en `tests/` |

---

## 3. Estructura de Carpetas

```text
MS-Proveedores/
├── AGENTS.md
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── package.json
├── README.md
├── tests/
│   ├── repository.db.test.js
│   ├── rutas.proveedores.test.js
│   └── validadores.test.js
├── db/
│   ├── aplicar_migraciones.js
│   └── 001_tablas_proveedores.sql
└── src/
    ├── app.js
    ├── server.js
    ├── config/
    │   ├── env.js
    │   └── db.js
    ├── middlewares/
    │   ├── auth.js
    │   ├── correlation.js
    │   └── errorHandler.js
    ├── controllers/
    │   └── proveedores.controller.js
    ├── repositories/
    │   └── proveedores.repository.js
    ├── routes/
    │   ├── health.routes.js
    │   └── proveedores.routes.js
    └── utils/
        ├── errors.js
        ├── paginacion.js
        ├── roles.js
        └── validadores.js
```

---

## 4. Modelo de Datos y Migraciones (MySQL)

Todas las tablas usan `InnoDB`, `utf8mb4` con collation `utf8mb4_0900_ai_ci` y fechas en UTC (`UTC_TIMESTAMP()`). No hay llaves foráneas hacia otros microservicios: `sku` en `productos_suministrados` es una referencia lógica hacia `ms-productos`.

1. **`proveedores`**:
   - `id_proveedor` (`INT` PK AI), `nit` (`VARCHAR(30)` UNIQUE), `razon_social`, `telefono`, `email`, `direccion`, `estado` (`ENUM('ACTIVO', 'INACTIVO')`), `creado_en`, `actualizado_en`.
2. **`contactos`**:
   - `id_contacto` (`INT` PK AI), `id_proveedor` (`INT` FK -> `proveedores` `ON DELETE CASCADE`), `nombre`, `cargo`, `telefono`, `email`, `creado_en`.
   - Los contactos se pueden eliminar físicamente (`DELETE`) porque no tienen historia transaccional.
3. **`productos_suministrados`** (entidad débil):
   - `id_proveedor` (`INT` FK -> `proveedores` `ON DELETE CASCADE`), `sku` (`VARCHAR(50)`), `precio_compra` (`DECIMAL(14, 2)`), `dias_entrega` (`INT`), `estado` (`ENUM('ACTIVO', 'INACTIVO')`), `actualizado_en`.
   - Clave primaria compuesta `(id_proveedor, sku)` e índice sobre `sku` para responder el filtro `?sku=`.

**Aplicar migraciones:**
```bash
node db/aplicar_migraciones.js
```

**Reglas de acceso a datos:**
- Todas las consultas usan SQL puro parametrizado (`?` en `mysql2/promise`). Nunca interpolar valores externos en cadenas SQL.
- Fallos de conexión/disponibilidad de MySQL se traducen a HTTP `503` con código `SERVICIO_NO_DISPONIBLE`.

---

## 5. Contratos HTTP Transversales

### 5.1 Autenticación y Encabezados
- **Excepciones públicas:** `GET /health` y `GET /health/ready` no requieren token de servicio.
- **Rutas de negocio:** Exigen `Authorization: Bearer <SERVICE_TOKEN>` validado con comparación en tiempo constante (`crypto.timingSafeEqual`). Si falta o es inválido, responde `401 NO_AUTENTICADO`.
- **Contexto del Gateway:**
  - `X-User-Id`: identificador del usuario autenticado.
  - `X-User-Role`: rol del usuario (`Administrador`, `Jefe de bodega`, `Compras`, `Gerente` o sus variantes normalizadas).
  - `X-Correlation-Id`: UUID de trazabilidad propagado en la respuesta HTTP y registrado en los logs JSON.

### 5.2 Formato Único de Error y Paginación
- **Error estándar:**
  ```json
  {
    "error": {
      "codigo": "NIT_DUPLICADO",
      "mensaje": "Ya existe un proveedor con ese NIT.",
      "detalles": { "nit": ["El NIT ya está registrado."] }
    }
  }
  ```
- **Códigos HTTP:** `400` (`PETICION_INVALIDA`), `401` (`NO_AUTENTICADO`), `403` (`SIN_PERMISO`), `404` (`NO_EXISTE`), `409` (`NIT_DUPLICADO`), `422` (`VALIDACION`), `503` (`SERVICIO_NO_DISPONIBLE`).
- **Paginación:** `?page=1&per_page=20` (máximo `100`) -> `{"data": [...], "meta": {"page": 1, "per_page": 20, "total": N}}`.

---

## 6. Catálogo de Endpoints

| Método | Ruta interna | Roles | Entrada | Respuesta | Errores |
|---|---|---|---|---|---|
| `GET` | `/health` | Público | — | `200 {"status":"ok","service":"ms-proveedores"}` | — |
| `GET` | `/health/ready` | Público | — | `200 {"status":"ok","service":"ms-proveedores","db":"connected"}` | `503` |
| `GET` | `/proveedores` | Todos e interno | `?q&estado&sku&page&per_page` | `200` listado paginado de proveedores con `contactos` | `422` |
| `GET` | `/proveedores/{id}` | Todos e interno | — | `200` proveedor con `contactos` | `400`, `404` |
| `POST` | `/proveedores` | Admin, Compras | `{nit, razon_social, telefono, email, direccion}` | `201` proveedor creado (`estado: ACTIVO`) | `400`, `403`, `409 NIT_DUPLICADO`, `422` |
| `PUT` | `/proveedores/{id}` | Admin, Compras | `{razon_social, telefono, email, direccion}` (sin `nit`) | `200` proveedor actualizado | `400`, `403`, `404`, `422` |
| `POST` | `/proveedores/{id}/inactivar` | Admin, Compras | — | `200` proveedor `INACTIVO` | `400`, `403`, `404` |
| `POST` | `/proveedores/{id}/activar` | Admin, Compras | — | `200` proveedor `ACTIVO` | `400`, `403`, `404` |
| `POST` | `/proveedores/{id}/contactos` | Admin, Compras | `{nombre, cargo, telefono, email}` | `201` contacto | `400`, `403`, `404`, `422` |
| `PUT` | `/proveedores/{id}/contactos/{id_contacto}` | Admin, Compras | `{nombre, cargo, telefono, email}` | `200` contacto | `400`, `403`, `404`, `422` |
| `DELETE` | `/proveedores/{id}/contactos/{id_contacto}` | Admin, Compras | — | `204` | `400`, `403`, `404` |
| `GET` | `/proveedores/{id}/productos` | Todos e interno | — | `200 [{sku, precio_compra, dias_entrega, estado}]` | `400`, `404` |
| `PUT` | `/proveedores/{id}/productos/{sku}` | Admin, Compras | `{precio_compra, dias_entrega, estado?}` | `200` crea o actualiza `ProductoSuministrado` | `400`, `403`, `404`, `422` |
| `DELETE` | `/proveedores/{id}/productos/{sku}` | Admin, Compras | — | `204` | `400`, `403`, `404` |

---

## 7. Variables de Entorno y Ejecución

Documentadas en `.env.example` (nunca leer ni exponer archivos `.env` reales):
- `PORT` (`3001` local, `3000` en contenedor Docker)
- `SERVICE_TOKEN`
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `LOG_LEVEL`

**Ejecución local:**
```bash
npm install
node db/aplicar_migraciones.js
npm start
```

**Pruebas unitarias (`tests/`):**
```bash
npm test
```

**Contenedor Docker:**
```bash
docker build -t ms-proveedores:1.0.0 .
```
