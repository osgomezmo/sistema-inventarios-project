# MS-Proveedores

Microservicio encargado de la gestión del maestro de proveedores, sus contactos y la relación de productos suministrados (RF03, RF12).

## Stack

- Node.js 24 + Express 4
- MySQL 8.4 (`mysql2/promise` con SQL parametrizado y migraciones en `db/`)
- Docker (`node:24-alpine`, puerto interno `3000`)

## Configuración

Copia `.env.example` a `.env` y define las credenciales de MySQL y `SERVICE_TOKEN`.

```bash
npm install
npm run migrate
npm start
```

Consulta [AGENTS.md](./AGENTS.md) para el detalle completo de contratos HTTP, esquema de datos y roles autorizados.
