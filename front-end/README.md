# Estiba · interfaz web

Interfaz gráfica del sistema de gestión de inventarios del supermercado (proyecto de Ingeniería de Software II). Trabaja sobre la API pública del **API Gateway** (`/api/...`): inicia sesión con un token personal de **Sanctum** y lo envía en cada petición como `Authorization: Bearer <token>`. El gateway valida el token y el permiso del rol y llama a cada microservicio con su token de servicio.

«Estiba» es un nombre provisional; el equipo lo puede cambiar.

## Cómo habla con el gateway (sin CORS)

El navegador nunca llama al gateway en otro origen: todas las peticiones van a `/api` del mismo servidor que sirve la interfaz, y ese servidor las reenvía al gateway.

- **En el contenedor**, Nginx sirve la aplicación y reenvía `/api/` a `GATEWAY_URL` (por defecto `http://api-gateway`, el alias del gateway en la red `redapi`).
- **En desarrollo**, el proxy de Vite reenvía `/api` a `GATEWAY_URL` (por defecto `http://127.0.0.1:8000`, el puerto que publica `gateway/docker-compose.yml`).

Como el origen es el mismo, no hay que configurar CORS en el gateway.

## Ejecutar en desarrollo

Con el gateway y los microservicios arriba:

```bash
cd front-end
npm install
npm run dev        # http://localhost:5173, /api se reenvía al gateway
npm run build      # compila TypeScript y genera dist/
```

Para apuntar a otro gateway: `GATEWAY_URL=http://otro-host:8000 npm run dev`.

Los usuarios son los del gateway: el administrador inicial (`ADMIN_EMAIL` del `.env` del gateway) y, si se definió `USUARIOS_INICIALES_PASSWORD`, `jefe.bodega@inventario.local`, `compras@inventario.local` y `gerente@inventario.local`.

## Contenedor

```bash
docker build -t estiba-front ./front-end
docker run --rm -p 8080:80 --network redapi estiba-front   # http://localhost:8080
```

- Etapa 1 (`node:24-alpine`): `npm ci` y `npm run build`.
- Etapa 2 (`nginx:1.27-alpine`): sirve `dist/` con respaldo a `index.html` para las rutas de React Router y reenvía `/api/` al gateway (`nginx/default.conf.template`).
- `GATEWAY_URL` (esquema, host y puerto, sin ruta) se cambia con `-e GATEWAY_URL=...`. El contenedor debe estar en la misma red de Docker que el gateway (`redapi`): Nginx resuelve el nombre con el DNS interno de Docker en cada petición, así que arranca aunque el gateway todavía no esté arriba.
- `GET /salud` responde `ok` para el `HEALTHCHECK`.

## Qué incluye

- Inicio de sesión con el token de Sanctum. Si el gateway rechaza el token (vencido, revocado o usuario inactivado), la sesión se cierra y vuelve a la pantalla de ingreso.
- Dashboard por bodega con el **rack selectivo en 3D**: un nivel por categoría, una estiba por producto y cajas proporcionales al saldo (5 cajas = stock mínimo).
- Stock por bodega (rack y tabla con la misma selección) y detalle por producto.
- Movimientos, registro de salidas y ajustes, kardex con exportación CSV, traslados y devoluciones.
- Órdenes de compra: listado, detalle con aprobación, recepción, devolución y anulación, y creación.
- Proveedores, productos, categorías, bodegas, notificaciones, reportes (valorización, rotación y stock bajo) y usuarios con la matriz de permisos.
- Cada rol ve solo los módulos y acciones que le permite la tabla 4 de la entrega 2; el gateway igual responde 403 si se intenta otra cosa.

## Estructura

```
src/
  api/http.ts           fetch a /api con el token, errores en el formato del contrato y cierre de sesión ante un 401
  api/cliente.ts        una función por endpoint; traduce las formas que difieren del contrato
  api/maestros.ts       productos, categorías, bodegas y proveedores en memoria para mostrar nombres
  api/types.ts          tipos de los contratos de la entrega 2
  auth/                 sesión (token de Sanctum) y matriz de permisos por rol
  contexto/             datos maestros, bodega activa y avisos
  componentes/          barra, riel, gráficas y piezas comunes
  paginas/              una pantalla por módulo
  tres/                 rack 3D (React Three Fiber) y el rack decorativo de la portada
  estilos/              tokens de color y tipografía, y estilos
nginx/                  configuración de Nginx del contenedor
```

## Diferencias con los contratos que resuelve el cliente

- **Gateway**: el rol llega como `{codigo, nombre}` con los códigos `admin`, `jefe_bodega`, `compras` y `gerente`; no hay «último acceso» ni recuperación de contraseña por correo.
- **ms-compras**: usa `creada_en`, `actualizada_en`, `aprobada_en`, `id_usuario_creador` y `cantidad_pedida`; el listado agrega `total_pages`. El cliente acepta esos nombres y los del contrato.
- **ms-notificaciones**: usa `id_notificacion`, `rol_destino` en minúsculas y los datos del evento dentro de `datos`.
- **ms-reportes** aún no existe: `/api/dashboard` y `/api/reportes/*` responden 503 y la interfaz muestra «Servicio de reportes no disponible». El rack, el stock y los movimientos siguen funcionando.
- La serie diaria del valor del inventario se quitó del dashboard porque no está en los contratos.
