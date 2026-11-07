# Estiba · interfaz web (plantilla)

Plantilla de la interfaz gráfica del sistema de gestión de inventarios del supermercado (proyecto de Ingeniería de Software II). Todos los datos son **de ejemplo**: todavía no se conecta al API Gateway, pero cada llamada tiene la misma ruta, filtros y forma de respuesta que los contratos de la entrega 2 (capítulo 4).

«Estiba» es un nombre provisional; el equipo lo puede cambiar.

## Ejecutar

```bash
cd front-end
npm install
npm run dev        # http://localhost:5173
npm run build      # compila TypeScript y genera dist/
```

En la pantalla de inicio de sesión hay botones para entrar con un usuario de ejemplo de cada rol (Administrador, Jefe de bodega, Compras y Gerente). Cualquier contraseña sirve; Sergio Valencia está inactivo y muestra el error 403.

## Qué incluye

- Inicio de sesión y recuperación de contraseña.
- Dashboard por bodega con el **rack selectivo en 3D**: un nivel por categoría, una estiba por producto y cajas proporcionales al saldo (5 cajas = stock mínimo). El rótulo de cada posición (B2-N1-P03) se pinta con franja amarilla y negra en stock bajo y en rojo si está agotado.
- Stock por bodega (rack y tabla con la misma selección) y detalle por producto.
- Movimientos, registro de salidas y ajustes, kardex con exportación CSV, traslados y devoluciones.
- Órdenes de compra: listado, detalle con aprobación, recepción, devolución y anulación, y creación.
- Proveedores, productos, categorías, bodegas, notificaciones, reportes (valorización, rotación y stock bajo) y usuarios con la matriz de permisos.
- Cada rol ve solo los módulos y acciones que le permite la tabla 4 de la entrega 2.

## Estructura

```
src/
  api/types.ts          tipos de los contratos de la entrega 2
  api/cliente.ts        una función por endpoint (hoy simulado en memoria)
  api/mock/             datos de ejemplo y simulación de octubre (saldos con costo promedio ponderado)
  auth/                 sesión (token de Sanctum) y matriz de permisos por rol
  componentes/          barra, riel, gráficas y piezas comunes
  paginas/              una pantalla por módulo
  tres/                 rack 3D (React Three Fiber)
  estilos/              tokens de color y tipografía, y estilos
```

## Conectar el gateway real

1. Crear `front-end/.env.local` con `VITE_API_URL=http://localhost:8000/api`.
2. En `src/api/cliente.ts`, reemplazar el cuerpo de cada función por un `fetch` a `VITE_API_URL` + la ruta del comentario, con el encabezado `Authorization: Bearer <token>`. Las firmas y los tipos no cambian.
3. Configurar CORS en el gateway para el origen de la interfaz (punto API-2 de la guía técnica).

Pendiente fuera de los contratos: la serie diaria del valor del inventario (`reportesApi.serieValor`) es una propuesta para ms-reportes.
