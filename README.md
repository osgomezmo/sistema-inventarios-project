# Sistema de Gestión de Inventarios

**Integrantes**

- Andrés Hernández - 1054479268
- Daniel Stiven Bahamon Quintero - 1083866695
- Oscar David Gomez Mosquera - 1054862558

Proyecto de Ingeniería de Software II: un sistema de gestión de inventarios para un supermercado mediano, construido con microservicios.

Esta guía está escrita para Ubuntu 24.04 o 22.04. Si sigues los pasos en orden, al final tendrás todo el sistema funcionando en tu computador con un solo comando.

---

## 1. Qué es el sistema

El sistema lleva el inventario de un supermercado con varias bodegas. Permite:

- Manejar el **catálogo**: categorías y productos con su SKU, precio y stock mínimo.
- Llevar el **inventario por bodega**: saldos, salidas, ajustes, traslados entre bodegas, devoluciones de clientes y el **kardex** (la historia de cada producto con su costo promedio).
- Registrar **proveedores** y **órdenes de compra**, con su aprobación, la recepción de la mercancía y las devoluciones al proveedor.
- Avisar cuando un producto queda **bajo su stock mínimo**.
- Consultar **reportes**: valor del inventario, rotación de productos y un tablero con indicadores.

### Componentes

| Componente | Tecnología | Para qué sirve |
|---|---|---|
| Interfaz web (`front-end`) | React + Nginx | Las pantallas que usa el personal del supermercado. |
| API Gateway (`api-gateway`) | Laravel 13 + Sanctum | Puerta única de entrada: inicio de sesión, usuarios, roles y permisos; reenvía cada petición al microservicio que corresponde. |
| `ms-productos` | Python (Flask) | Catálogo: categorías y productos. |
| `ms-inventario` | Python (Flask) | Bodegas, saldos, movimientos, kardex, traslados y devoluciones de clientes. |
| `ms-compras` | Python (Flask) | Órdenes de compra, recepciones y devoluciones a proveedor. |
| `ms-proveedores` | Node.js (Express) | Proveedores y los productos que suministran. |
| `ms-reportes` | Python (Flask) | Reportes y tablero (dashboard). |
| `ms-notificaciones` | Node.js (Express) | Alertas de stock bajo. |
| RabbitMQ | RabbitMQ 4 | Mensajería entre servicios (eventos como "se registró un movimiento" o "un producto quedó bajo el mínimo"). |
| Bases de datos | MySQL 8.4 | Una base de datos propia para cada microservicio y otra para el gateway. |

### Cómo se conectan

```text
                  Navegador (http://127.0.0.1)
                              │
                     front-end (Nginx)
                              │  /api/...
                     api-gateway (Laravel)   ← usuarios, roles y permisos
        ┌──────────┬──────────┼───────────┬────────────┬──────────────────┐
  ms-productos ms-inventario ms-compras ms-proveedores ms-reportes ms-notificaciones
        │          │          │           │            │              │
      MySQL      MySQL      MySQL       MySQL        MySQL      (archivos locales)

        ms-inventario, ms-compras ──► RabbitMQ ──► ms-inventario, ms-reportes, ms-notificaciones
```

Todo lo que viene de afuera entra por el gateway. Los microservicios no se pueden llamar directamente desde el navegador: el gateway les pasa un token interno.

---

## 2. Requisitos

- Ubuntu 24.04 o 22.04 (de escritorio o servidor).
- 8 GB de RAM recomendados (el sistema completo usa cerca de 2 GB; con 4 GB funciona, pero más lento).
- 15 GB libres en disco (las imágenes de Docker ocupan unos 5 GB).
- Conexión a internet: la primera vez se descargan las imágenes y las dependencias.
- Un usuario con permiso para usar `sudo`.

---

## 3. Instalación paso a paso

Abre una terminal (Ctrl + Alt + T) y ejecuta los comandos en el orden en que aparecen. Copia cada bloque completo.

### 3.1. Instalar git

```bash
sudo apt-get update
sudo apt-get install -y git
git --version
```

Si salió bien, verás algo como `git version 2.43.0`.

### 3.2. Instalar Docker y Docker Compose

Se instala Docker Engine desde el repositorio oficial de Docker.

Primero, agrega el repositorio:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

Después, instala Docker y el plugin de Compose:

```bash
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Para usar Docker sin escribir `sudo` cada vez, agrega tu usuario al grupo `docker`:

```bash
sudo usermod -aG docker $USER
```

**Ahora cierra la sesión de Ubuntu y vuelve a entrar** (o reinicia el equipo). Sin este paso, Docker responderá "permission denied".

Al volver, abre otra terminal y comprueba:

```bash
docker run hello-world
```

Si salió bien, verás el mensaje `Hello from Docker!`.

```bash
docker compose version
```

Si salió bien, verás algo como `Docker Compose version v2.x.x`.

### 3.3. Descargar el proyecto

```bash
cd ~
git clone https://github.com/osgomezmo/sistema-inventarios-project.git
cd sistema-inventarios-project
git checkout develop
```

Si salió bien, el último comando dice `Already on 'develop'` o `Switched to branch 'develop'`. La rama `develop` es la que tiene todo el sistema integrado.

Todos los comandos que siguen se ejecutan **dentro de la carpeta `sistema-inventarios-project`**.

### 3.4. Crear el archivo de configuración

El sistema lee su configuración de un archivo `.env`. Créalo a partir de la plantilla:

```bash
cp .env.example .env
```

Ábrelo con un editor de texto:

```bash
nano .env
```

Cambia estos valores (los demás puedes dejarlos como están):

| Variable | Qué es | Qué poner |
|---|---|---|
| `ADMIN_EMAIL` | Correo del administrador | Puedes dejar `admin@inventario.local`. |
| `ADMIN_PASSWORD` | Contraseña del administrador | Una contraseña tuya, de al menos 8 caracteres. |
| `USUARIOS_INICIALES_PASSWORD` | Contraseña de los usuarios de ejemplo de cada rol | Otra contraseña tuya, de al menos 8 caracteres. |
| `FRONTEND_PORT` | Puerto de la página web | Deja `80`. Si ese puerto ya está ocupado en tu equipo, pon `8080` (ver sección 9). |

**No cambies `RABBITMQ_USER` ni `RABBITMQ_PASSWORD`.** El usuario de RabbitMQ viene definido en `infra/rabbitmq/definitions.json` con esa contraseña, y los servicios no podrían conectarse si la cambias.

En `nano`, guarda con Ctrl + O y Enter, y sal con Ctrl + X.

Las contraseñas del `.env` se usan solo la primera vez que arranca el sistema, para crear los usuarios. Si las cambias después, no se aplican (ver "Olvidé la contraseña" en la sección 9).

### 3.5. Levantar el sistema

```bash
docker compose up -d --build
```

La primera vez tarda entre 5 y 15 minutos, según la velocidad de internet: Docker descarga las imágenes, construye los ocho programas (la interfaz, el gateway y los seis microservicios) y cada servicio crea sus tablas y carga sus datos iniciales. Las siguientes veces arranca en menos de un minuto.

Si salió bien, la última parte muestra una lista de contenedores con `Started` o `Healthy`.

Comprueba el estado:

```bash
docker compose ps
```

Si salió bien, todos los contenedores dicen `Up`, y las bases de datos, RabbitMQ, `ms-reportes`, `ms-notificaciones` y `front-end` dicen además `(healthy)`. Si alguno dice `(health: starting)`, espera un minuto y repite el comando.

Comprueba que el gateway responde:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/up
```

Si salió bien, verás `200`. Si ves `000`, el gateway todavía está arrancando: espera 30 segundos y repite.

---

## 4. Cómo usar el sistema

Abre el navegador en **http://127.0.0.1** (si cambiaste `FRONTEND_PORT` a 8080, en **http://127.0.0.1:8080**). Verás la página de ingreso.

### Usuarios disponibles

| Correo | Contraseña | Rol |
|---|---|---|
| El de `ADMIN_EMAIL` (por defecto `admin@inventario.local`) | La de `ADMIN_PASSWORD` | Administrador |
| `jefe.bodega@inventario.local` | La de `USUARIOS_INICIALES_PASSWORD` | Jefe de bodega |
| `compras@inventario.local` | La de `USUARIOS_INICIALES_PASSWORD` | Compras |
| `gerente@inventario.local` | La de `USUARIOS_INICIALES_PASSWORD` | Gerente |

### Qué puede hacer cada rol

| Acción | Administrador | Jefe de bodega | Compras | Gerente |
|---|---|---|---|---|
| Ver productos, categorías, bodegas, stock, proveedores, órdenes y reportes | Sí | Sí | Sí | Sí |
| Crear y editar productos y categorías | Sí | | | |
| Crear y editar bodegas | Sí | Sí | | |
| Ver movimientos, kardex y traslados | Sí | Sí | | Sí |
| Registrar salidas, ajustes, traslados y devoluciones de clientes | Sí | Sí | | |
| Recibir mercancía de una orden de compra | Sí | Sí | | |
| Crear y editar proveedores y órdenes de compra | Sí | | Sí | |
| Aprobar y anular órdenes de compra | Sí | | | Sí |
| Registrar devoluciones a proveedor | Sí | Sí | Sí | |
| Administrar usuarios | Sí | | | |

### Qué probar

- **Administrador:** entra en *Usuarios* para ver los cuatro usuarios; en *Productos* y *Categorías* revisa el catálogo (33 productos en 7 categorías) y crea uno nuevo.
- **Jefe de bodega:** en *Stock* busca `LAC-0001` y mira su saldo en cada bodega; en *Movimientos* registra una salida; en *Kardex* consulta la historia de ese producto en la Sala de ventas; en *Traslados* mueve unidades entre bodegas.
- **Compras:** en *Proveedores* revisa los 5 proveedores; en *Órdenes de compra* crea una orden nueva.
- **Gerente:** en *Órdenes de compra* aprueba la orden en estado `BORRADOR`; en *Reportes* y en el tablero revisa el valor del inventario y los productos bajo el mínimo.

Los datos iniciales traen dos productos bajo el mínimo en la Sala de ventas (`BEB-0001` y `PAN-0001`) y órdenes de compra en varios estados (borrador, aprobada, recibida parcialmente, recibida y anulada).

---

## 5. Consultar la API con curl

Todas las peticiones pasan por el gateway en `http://127.0.0.1:8000/api`. Primero inicia sesión y guarda el token en una variable (cambia `TU_CONTRASEÑA` por la de `ADMIN_PASSWORD`):

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@inventario.local", "password": "TU_CONTRASEÑA"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")
echo $TOKEN
```

Si salió bien, verás un token como `1|aBcD...`. Si ves un error de Python, la contraseña o el correo no coinciden con los del `.env`.

Para no repetir la cabecera, guárdala en otra variable:

```bash
AUTH="Authorization: Bearer $TOKEN"
```

### Quién soy

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/auth/me
```

Responde tu usuario, su rol y sus permisos: `{"id":1,"nombre":"Administrador","email":"admin@inventario.local","estado":"ACTIVO","rol":{"codigo":"admin",...},"permisos":[...]}`.

### Catálogo (ms-productos)

```bash
curl -s -H "$AUTH" "http://127.0.0.1:8000/api/categorias?per_page=3"
curl -s -H "$AUTH" "http://127.0.0.1:8000/api/productos?q=leche"
```

La primera responde las categorías raíz con sus subcategorías, en el formato `{"data":[...],"meta":{"page":1,"per_page":3,"total":7}}`. La segunda responde los productos cuyo nombre o SKU contiene "leche", entre ellos `LAC-0001` (Leche entera bolsa 1100 ml).

### Bodegas y stock (ms-inventario)

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/bodegas
curl -s -H "$AUTH" http://127.0.0.1:8000/api/stock/LAC-0001
```

La primera responde las tres bodegas: `BOD-PRINCIPAL` (id 1), `BOD-SALA` (id 2, la sala de ventas) y `BOD-NORTE` (id 3). La segunda responde el saldo de `LAC-0001` en cada bodega y el total, por ejemplo `{"sku":"LAC-0001","por_bodega":[{"id_bodega":1,"cantidad":120.0,...},{"id_bodega":2,"cantidad":67.0,...}],"total":{...}}`.

### Registrar una salida

Vende 2 unidades de `LAC-0001` en la sala de ventas:

```bash
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/movimientos \
  -d '{"sku": "LAC-0001", "id_bodega": 2, "tipo": "SALIDA", "cantidad": 2, "documento_referencia": "POS-000500"}'
```

Responde el movimiento creado, con el saldo que quedó: `{"id_movimiento":98,"sku":"LAC-0001","id_bodega":2,"tipo":"SALIDA","cantidad":2.0,...,"saldo_resultante":65.0,...}`.

### Kardex

Consulta la historia de `LAC-0001` en la sala de ventas durante el día de hoy:

```bash
HOY=$(TZ=America/Bogota date +%F)
curl -s -H "$AUTH" "http://127.0.0.1:8000/api/kardex?sku=LAC-0001&id_bodega=2&desde=$HOY&hasta=$HOY"
```

Responde el saldo inicial, los movimientos en orden (el inventario inicial, una venta, un traslado de reposición y la salida que acabas de registrar) y el saldo final.

### Traslados

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/traslados
```

Responde los dos traslados de reposición de los datos iniciales, cada uno con su movimiento de salida y de entrada.

### Proveedores y órdenes de compra (ms-proveedores y ms-compras)

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/proveedores
curl -s -H "$AUTH" http://127.0.0.1:8000/api/ordenes-compra
```

La primera responde los 5 proveedores (por ejemplo, "Cooperativa de Lácteos y Cárnicos S.A."). La segunda responde las 5 órdenes de compra, de `OC-2026-000001` a `OC-2026-000005`, cada una con su estado.

### Reportes (ms-reportes)

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/dashboard
curl -s -H "$AUTH" http://127.0.0.1:8000/api/reportes/stock-bajo
```

La primera responde los indicadores del tablero: `valor_total_inventario`, `productos_stock_bajo`, `ordenes_pendientes` y los productos de mayor rotación. La segunda responde los productos bajo el mínimo (`BEB-0001` y `PAN-0001` en la bodega 2).

### Un permiso negado (403)

El usuario de Compras no puede registrar movimientos de inventario. Inicia sesión con él (cambia `TU_CONTRASEÑA` por la de `USUARIOS_INICIALES_PASSWORD`) e intenta una salida:

```bash
TOKEN_COMPRAS=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "compras@inventario.local", "password": "TU_CONTRASEÑA"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")

curl -s -w "\nCódigo HTTP: %{http_code}\n" -X POST \
  -H "Authorization: Bearer $TOKEN_COMPRAS" -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/movimientos \
  -d '{"sku": "LAC-0001", "id_bodega": 2, "tipo": "SALIDA", "cantidad": 1}'
```

Responde `{"error":{"codigo":"SIN_PERMISO",...}}` y `Código HTTP: 403`. El gateway rechaza la petición antes de que llegue a ms-inventario.

---

## 6. RabbitMQ: ver los mensajes entre servicios

Abre el panel en **http://127.0.0.1:15672**. Entra con el usuario `inventario` y la contraseña de `RABBITMQ_PASSWORD` del `.env`. Para verla, ejecuta:

```bash
grep RABBITMQ_PASSWORD .env
```

En la pestaña **Queues and Streams** verás seis colas:

- `q.inventario`: eventos de compras que consume ms-inventario.
- `q.reportes`: eventos que consume ms-reportes.
- `q.notificaciones`: eventos que consume ms-notificaciones.
- `q.inventario.errores`, `q.reportes.errores` y `q.notificaciones.errores`: los mensajes que fallaron tres veces.

Cada cola de trabajo tiene un consumidor conectado (columna *Consumers*). Por eso los mensajes se procesan al instante y el contador de mensajes en espera suele estar en 0. Para ver la actividad, mira las gráficas de *Message rates* en la pestaña **Overview**.

**Comprobar que un movimiento genera mensajes.** Una salida que deja un producto bajo su mínimo genera dos eventos: `MovimientoRegistrado` (para reportes) y `StockBajoUmbral` (para notificaciones). `BEB-0002` tiene 60 unidades en la sala de ventas y un mínimo de 30; vende 31 (usa el `AUTH` del administrador de la sección 5):

```bash
curl -s -X POST -H "$AUTH" -H "Content-Type: application/json" \
  http://127.0.0.1:8000/api/movimientos \
  -d '{"sku": "BEB-0002", "id_bodega": 2, "tipo": "SALIDA", "cantidad": 31}'
```

En el panel, la gráfica *Message rates* de **Overview** muestra el paso de los mensajes. Además, la alerta llega a ms-notificaciones:

```bash
curl -s -H "$AUTH" http://127.0.0.1:8000/api/notificaciones
```

Si salió bien, aparece una notificación de tipo `STOCK_BAJO` para `BEB-0002` ("El producto BEB-0002 en bodega 2 tiene un saldo de 29, inferior al mínimo requerido de 30."). Va dirigida al rol de Compras: en el sistema web la verás en la campana de notificaciones al entrar con `compras@inventario.local`.

---

## 7. Pruebas de rendimiento con Locust

Locust corre en su propio contenedor, dentro de la misma red que el resto, y solo se levanta si lo pides con el perfil `pruebas`.

```bash
docker compose --profile pruebas up -d --build
```

La primera vez, el contenedor crea sus datos de prueba (2000 productos `LT-0001` a `LT-2000`, tres bodegas `LT-B1` a `LT-B3` y un usuario de prueba); tarda unos 3 minutos. Para seguir el avance, ejecuta:

```bash
docker compose logs -f locust
```

Cuando veas `Starting web interface at http://0.0.0.0:8089`, sal con Ctrl + C.

Luego:

1. Abre **http://127.0.0.1:8089**.
2. En la lista de clases, marca **una** prueba:

   | Clase | Qué mide |
   |---|---|
   | `B1AuthMe` | `GET /api/auth/me`: solo el gateway. |
   | `B2Productos` | `GET /api/productos?q=`: búsqueda en el catálogo (gateway y ms-productos). |
   | `B3Stock` | `GET /api/stock/{sku}`: saldo de un producto (gateway y ms-inventario). |
   | `B4Movimientos` | `POST /api/movimientos`: una salida de 1 unidad (gateway, ms-inventario, ms-productos y RabbitMQ). |
   | `B5Traslados` | `POST /api/traslados`: un traslado de 1 unidad entre dos bodegas. |
   | `B6Kardex` | `GET /api/kardex`: la historia de un producto en el día. |
   | `C1Dashboard` | `GET /api/dashboard`: tablero analítico consolidado (gateway y ms-reportes). |
   | `C2ValorizacionJson` | `GET /api/reportes/valorizacion`: valorización del inventario en JSON (gateway y ms-reportes). |
   | `C3ValorizacionCsv` | `GET /api/reportes/valorizacion?formato=csv`: exportación de valorización en CSV (gateway y ms-reportes). |
   | `C4Rotacion` | `GET /api/reportes/rotacion`: reporte de rotación de inventario (gateway y ms-reportes). |
   | `C5StockBajo` | `GET /api/reportes/stock-bajo`: alertas de stock bajo umbral (gateway y ms-reportes). |
   | `C6Dispositivos` | `POST /api/dispositivos`: registro de tokens FCM (gateway y ms-notificaciones). |
   | `C7Notificaciones` | `GET /api/notificaciones`: consulta paginada de notificaciones (gateway y ms-notificaciones). |

3. En *Number of users* escribe 20 y en *Ramp up* escribe 5 (usuarios nuevos por segundo).
4. Pulsa **Start**.
5. En la pestaña *Statistics* verás, por petición, el número de peticiones, los errores (*Fails*) y los tiempos de respuesta (mediana, percentil 95 y percentil 99, en milisegundos). En *Charts* verás tres gráficas en el tiempo: peticiones por segundo, tiempos de respuesta y número de usuarios.
6. Pulsa **Stop** para terminar.

El criterio del proyecto es que el 95 % de las peticiones responda en menos de 2 segundos, con menos del 1 % de errores.

**Resultados ya medidos.** Las 18 corridas del bloque B (6 pruebas en los escenarios normal, pico y estrés) están en [pruebas/resultados/resumen.md](pruebas/resultados/resumen.md), con sus archivos CSV en `pruebas/resultados/`. La guía completa de estas pruebas está en [pruebas/locust/README.md](pruebas/locust/README.md).

**Borrar los datos de prueba** al terminar:

```bash
docker compose exec locust python limpiar_datos.py
```

Si salió bien, verás `0 filas de prueba` en las tres bases. Los reportes (ms-reportes) conservan los movimientos de las pruebas; si quieres dejarlos limpios, empieza desde cero (sección 8).

**Otras pruebas del equipo:**

- `pruebas/locust/bloque_c.py`: reportes y notificaciones. Sus clases, de `C1Dashboard` a `C7Notificaciones`, aparecen en la misma interfaz web y se documentan en [pruebas/locust/README.md](pruebas/locust/README.md).
- `pruebas/locust/proveedores_compras/`: ms-proveedores y ms-compras.
- `infra/simulador/`: un simulador de eventos de RabbitMQ.

Las de `proveedores_compras/` y `infra/simulador/` tienen su propio README en su carpeta.

---

## 8. Detener, reiniciar y borrar

| Quiero… | Comando | Qué pasa con los datos |
|---|---|---|
| Detener todo sin borrar nada | `docker compose --profile pruebas stop` | Se conservan. |
| Volver a encender | `docker compose up -d` (o `docker compose --profile pruebas up -d` para incluir Locust) | Siguen ahí. |
| Apagar y quitar los contenedores | `docker compose --profile pruebas down` | Se conservan en los volúmenes de Docker; al volver a levantar, todo sigue igual. |
| Borrar todo y empezar desde cero | `docker compose --profile pruebas down -v` | **Se borran** todas las bases de datos. Al volver a levantar, el sistema se crea de nuevo con los datos iniciales y las contraseñas del `.env`. |

Los contenedores tienen reinicio automático: si apagas el equipo con el sistema encendido, al prenderlo vuelve a arrancar solo. Para que no arranque, usa `docker compose --profile pruebas down` antes de apagar.

---

## 9. Solución de problemas

**"address already in use" o "port is already allocated" al levantar.** Otro programa usa ese puerto. Si es el puerto 80 (la página web), cambia `FRONTEND_PORT=8080` en el `.env`, ejecuta `docker compose up -d` y entra por http://127.0.0.1:8080. Si es otro puerto (8000, 5672, 15672, 8089 o 3306x), mira qué programa lo usa con `sudo ss -ltnp | grep :8000` (cambia el número) y ciérralo.

**"permission denied while trying to connect to the Docker daemon socket".** Tu usuario no está en el grupo `docker`, o no has cerrado la sesión después de agregarlo. Ejecuta `sudo usermod -aG docker $USER`, cierra la sesión de Ubuntu y vuelve a entrar.

**Un contenedor no queda `healthy`, o aparece `Restarting` o `Exited`.** Mira sus mensajes, por ejemplo para el gateway:

```bash
docker compose logs --tail 50 api-gateway
```

Cambia `api-gateway` por el nombre del servicio que falla (la primera columna de `docker compose ps`). Si el error menciona RabbitMQ y `ACCESS_REFUSED`, revisa que no hayas cambiado `RABBITMQ_USER` ni `RABBITMQ_PASSWORD` en el `.env`.

**Olvidé la contraseña del administrador, o la cambié en el `.env` y no funciona.** Las contraseñas del `.env` solo se usan al crear los usuarios la primera vez. Para poner una nueva (cambia `NuevaClave2026` y el correo si usaste otro):

```bash
docker compose exec -u www-data -e XDG_CONFIG_HOME=/tmp api-gateway php artisan tinker --execute="App\Models\User::where('email', 'admin@inventario.local')->first()->update(['password' => 'NuevaClave2026']);"
```

Si salió bien, el comando termina sin mensajes y ya puedes entrar con la contraseña nueva. Sirve igual para los usuarios de cada rol, cambiando el correo.

Si cambias así la contraseña del administrador, pon la misma en `ADMIN_PASSWORD` del `.env`: Locust la usa para crear sus datos de prueba. Después aplica el cambio con `docker compose --profile pruebas up -d locust`.

**Quiero empezar desde cero.** Borra todo (incluidos los datos) y vuelve a levantar:

```bash
docker compose --profile pruebas down -v
docker compose up -d --build
```

---

## 10. Cómo funciona por dentro

### Una base de datos por microservicio

Cada microservicio guarda sus datos en su propia base, y ningún servicio lee la base de otro. Cuando un servicio necesita algo de otro, se lo pide por HTTP (siempre con el token de servicio) o se entera por un evento de RabbitMQ.

| Servicio | Dónde guarda sus datos | Base (valor por defecto) |
|---|---|---|
| `ms-productos` | MySQL `productos-mysql` | `ms_productos` |
| `ms-inventario` | MySQL `inventario-mysql` | `ms_inventario` |
| `ms-compras` | MySQL `compras-mysql` | `mscompras` |
| `ms-proveedores` | MySQL `proveedores-mysql` | `proveedores` |
| `ms-reportes` | MySQL `reportes-mysql` | `ms_reportes` |
| `ms-notificaciones` | Archivo local en el volumen `ms_notificaciones_data` (o Firebase, si se configura) | — |
| `api-gateway` | MySQL `gateway-mysql` (usuarios, roles y tokens) | `gateway` |

Ejemplos de consultas entre servicios: ms-inventario le pregunta a ms-productos si un SKU existe antes de registrar un movimiento, y ms-compras le pregunta a ms-proveedores por el proveedor de una orden.

### Cómo se llama la API y qué cabeceras viajan

```text
Cliente ──► api-gateway ─────────────────────────────► microservicio
            Authorization: Bearer <token de Sanctum>    Authorization: Bearer <token de servicio>
            1. ¿el token es válido?                     X-User-Id: 7
            2. ¿el usuario está ACTIVO?                 X-User-Role: jefe_bodega
            3. ¿su rol tiene el permiso de esa ruta?    X-Correlation-Id: 6f1c2a9e-...
```

El cliente (la página web o curl) manda una sola cabecera: `Authorization: Bearer <token>`, con el token que recibió al iniciar sesión. El gateway revisa tres cosas: que el token sea válido (Sanctum), que el usuario siga `ACTIVO` y que su rol tenga el permiso que exige la ruta. Si algo falla, responde 401 o 403 y la petición no llega al microservicio.

Si todo está bien, el gateway arma una petición nueva hacia el microservicio con estas cabeceras:

| Cabecera | Para qué sirve |
|---|---|
| `Authorization: Bearer <token de servicio>` | Demuestra que la petición viene del gateway. Es el mismo valor (`SERVICE_TOKEN`) en el gateway y en todos los microservicios. |
| `X-User-Id` | Quién hizo la operación. ms-inventario lo guarda en cada movimiento, para saber quién lo registró. |
| `X-User-Role` | El rol del usuario: `admin`, `jefe_bodega`, `compras` o `gerente`. |
| `X-Correlation-Id` | Un identificador de la petición. Viaja también en los eventos, para seguir una operación en los logs de todos los servicios. |

El gateway no reenvía las cabeceras del cliente: arma las suyas desde cero. Si el cliente manda un `X-User-Id` o un `X-User-Role` inventados, se descartan. La única que conserva es un `X-Correlation-Id` válido (letras, números y guiones, hasta 64 caracteres); si no viene o no es válido, genera uno nuevo.

Los seis microservicios responden 401 a cualquier petición que no traiga el token de servicio. Sus puertos solo se publican en `127.0.0.1` y, sin ese token, no se pueden usar directamente: todo pasa por el gateway.

### Cómo manejamos los eventos

Los servicios se avisan cosas a través de RabbitMQ, en el exchange `inventario.eventos`, de tipo *topic*. La routing key de cada mensaje es el nombre del evento, y cada cola recibe solo los eventos que le interesan.

Todos los mensajes tienen el mismo sobre:

```json
{
  "id_evento": "6f1c2a9e-1b7d-4c55-9a51-3f0e8d2b7c10",
  "tipo": "MovimientoRegistrado",
  "fecha": "2026-11-22T14:32:05Z",
  "productor": "ms-inventario",
  "id_correlacion": "c1f4b8e2-77a0-4d1e-9a3b-0c5d6e7f8a90",
  "datos": { "...": "lo propio de cada evento" }
}
```

| Evento | Lo publica | Lo consume (cola) | Cuándo |
|---|---|---|---|
| `MercanciaRecibida` | ms-compras | ms-inventario (`q.inventario`) | Se recibe mercancía de una orden: ms-inventario la suma al stock. |
| `DevolucionProveedorRegistrada` | ms-compras | ms-inventario (`q.inventario`) | Se devuelve mercancía al proveedor: ms-inventario la descuenta. |
| `MovimientoRegistrado` | ms-inventario | ms-reportes (`q.reportes`) | Cada movimiento de inventario. |
| `OrdenCompraActualizada` | ms-compras | ms-reportes (`q.reportes`) | Una orden se crea, se edita, se aprueba, se anula o se recibe. |
| `StockBajoUmbral` | ms-inventario | ms-reportes y ms-notificaciones (`q.reportes` y `q.notificaciones`) | Un saldo que estaba por encima de su stock mínimo queda en el mínimo o por debajo. |

Cómo se procesa un mensaje:

- **Confirmación manual.** El consumidor confirma el mensaje (*ack*) solo después de guardar su efecto. Si falla, lo rechaza y RabbitMQ lo vuelve a entregar.
- **Tres intentos.** Las colas `q.inventario`, `q.reportes` y `q.notificaciones` tienen un límite de 3 entregas (`x-delivery-limit`). Al superarlo, el mensaje pasa a su cola `.errores` (por ejemplo, `q.inventario.errores`) para revisarlo a mano. ms-inventario además cuenta los intentos él mismo con la cabecera `x-acquired-count` y, desde el tercero, rechaza sin reentrega para que el mensaje llegue a `q.inventario.errores`.
- **Después de guardar.** En ms-inventario, el evento se publica después de confirmar la transacción en la base. Si el movimiento no se guarda, no se avisa nada.

### Idempotencia: no aplicar dos veces el mismo evento

RabbitMQ puede entregar un mismo mensaje más de una vez; por ejemplo, si el consumidor se cae justo después de guardar y antes de confirmar. Si ms-inventario aplicara dos veces una `MercanciaRecibida`, el stock quedaría duplicado.

Para evitarlo, cada consumidor anota el `id_evento` de los mensajes que ya procesó:

| Servicio | Dónde anota los eventos procesados |
|---|---|
| ms-inventario | Tabla `eventos_procesados` |
| ms-reportes | Tabla `evento_procesado` |
| ms-notificaciones | Lista `eventos_procesados` en su archivo de datos (o la colección del mismo nombre en Firebase) |

El `id_evento` se guarda en la misma transacción que el cambio (en ms-notificaciones, en la misma escritura del archivo). Si llega un mensaje con un `id_evento` que ya está anotado, se confirma sin aplicarlo otra vez.

### Healthchecks: cuándo un contenedor está listo de verdad

Un contenedor "encendido" no siempre está listo. MySQL, por ejemplo, tarda varios segundos en aceptar conexiones después de arrancar. Por eso varios contenedores tienen un *healthcheck*: un comando que Docker ejecuta cada cierto tiempo para saber si el servicio responde.

| Contenedores | Comando | interval | timeout | retries | start_period |
|---|---|---|---|---|---|
| Las 6 bases MySQL | `mysqladmin ping` con el usuario de la base | 5 s | 10 s | 30 | 60 s |
| RabbitMQ | `rabbitmq-diagnostics -q ping` | 10 s | 15 s | 20 | 60 s |
| ms-reportes (en su Dockerfile) | Abre `http://127.0.0.1:5000/health` | 10 s | 5 s | 3 | 10 s |
| ms-notificaciones (en su Dockerfile) | Abre `http://127.0.0.1:5006/health` | 10 s | 5 s | 3 | 10 s |
| front-end (en su Dockerfile) | Abre `http://127.0.0.1/salud` | 30 s | 3 s | 3 | 5 s |

Qué significa cada valor:

- **interval:** cada cuánto se ejecuta el comando.
- **timeout:** cuánto se espera la respuesta antes de darlo por fallido.
- **retries:** cuántos fallos seguidos hacen falta para marcar el contenedor como `unhealthy`.
- **start_period:** tiempo de gracia al arrancar; los fallos de ese periodo no cuentan.

Los servicios usan `depends_on` con `condition: service_healthy` para esperar a su base y, si la usan, a RabbitMQ. Por ejemplo, ms-inventario no arranca hasta que `inventario-mysql` y `rabbitmq` están `healthy`, no solo encendidos. Así, cuando el servicio crea sus tablas y carga sus datos iniciales, la base ya acepta conexiones. Las dependencias entre aplicaciones (por ejemplo, el gateway con los microservicios) solo esperan a que el contenedor haya arrancado (`service_started`).

### Limitaciones conocidas

**Dependencia de RabbitMQ.** Esto es lo que pasa según el código si RabbitMQ se cae:

- **ms-inventario:** los movimientos, traslados y devoluciones de clientes se siguen registrando, porque el evento se publica después de guardar. Si la publicación falla, solo queda un aviso en el log y el evento se pierde: ms-reportes no se entera del movimiento y ms-notificaciones no recibe las alertas de stock bajo de ese momento.
- **ms-compras:** publica sus eventos dentro de la misma transacción en que guarda. Si RabbitMQ no responde, la operación se deshace y responde 503 (`SERVICIO_NO_DISPONIBLE`). Mientras RabbitMQ esté caído no se pueden crear, editar, aprobar, anular ni recibir órdenes, ni registrar devoluciones a proveedor. A cambio, ms-inventario nunca se queda sin enterarse de una recepción guardada.
- **Consumidores** (ms-inventario, ms-reportes y ms-notificaciones): pierden la conexión y reintentan conectarse solos cada pocos segundos (5 s en ms-inventario y ms-notificaciones, 3 s en ms-reportes). Cuando RabbitMQ vuelve, siguen con lo que haya quedado en sus colas.

Cómo se podría mejorar:

- Guardar en ms-inventario los eventos que no se pudieron publicar en una tabla de pendientes y reenviarlos después (el patrón *outbox*: el evento se escribe en la base, en la misma transacción que el cambio, y un proceso aparte lo publica).
- Correr RabbitMQ en clúster de varios nodos, para que la caída de uno no detenga la mensajería.

**Otras limitaciones medidas** (ver [pruebas/resultados/resumen.md](pruebas/resultados/resumen.md)):

- Conexiones de la base del gateway: en las pruebas de estrés, las lecturas empiezan a fallar con errores 500 desde unos 80 usuarios. La base del gateway acepta como máximo 50 conexiones (`--max-connections=50`), mientras que su Apache puede atender hasta 150 peticiones a la vez.
- Un solo worker de Gunicorn: ms-productos y ms-inventario arrancan Gunicorn sin indicar `--workers`, así que atienden con un solo proceso. Las escrituras de inventario (salidas y traslados) son las más lentas y ya fallan con 50 usuarios (errores 503 en B4-P y B5-P).

---

## 11. Documentación del proyecto

**Entregas:**

- [Enunciado del proyecto](docs/Proyecto_ISW2_Sistema_Gestion_Inventarios_Microservicios-2.docx)
- [Entrega 1: investigación y fundamentación](docs/Entrega_1_Proyecto_ISW2_Sistema_Gestion_Inventarios.docx)
- [Entrega 2: diseño y arquitectura](docs/Entrega_2_Proyecto_ISW2_Sistema_Gestion_Inventarios.docx) y su [borrador con los contratos de la API](docs/Entrega_2_borrador.md)
- Bitácoras de uso de IA de cada integrante: [bitacora_ia/](bitacora_ia/)

**README de cada componente:**

- [API Gateway](gateway/README.md)
- [ms-productos](MS-Productos/README.md)
- [ms-inventario](MS-Inventario/README.md)
- [ms-compras](MS-Compras/README.md)
- [ms-proveedores](MS-Proveedores/README.md)
- [Interfaz web](front-end/README.md)
- [Kubernetes](infra/k8s/README.md)
- [Pruebas de rendimiento](pruebas/locust/README.md)

---

## 12. Despliegue en la nube (Google Cloud)

Además de correrlo en local, el equipo desplegó el sistema en una máquina virtual con Debian en Google Cloud. Fue un trabajo adicional, para aprender y ver cómo se comporta en un entorno real.

Entra en **http://35.196.111.68/ingresar** con alguno de estos usuarios:

| Correo | Rol | Contraseña |
|---|---|---|
| `jefe.bodega@inventario.local` | Jefe de bodega | `Inventario2026` |
| `compras@inventario.local` | Compras | `Inventario2026` |
| `gerente@inventario.local` | Gerente | `Inventario2026` |

El despliegue usa el mismo `docker-compose.yml` de la raíz. El flujo de GitHub Actions del repositorio ([.github/workflows/main.yml](.github/workflows/main.yml)) se conecta por SSH a la máquina virtual y vuelve a levantar los contenedores con la rama `develop` cada vez que se fusiona un pull request en `develop` (también se puede lanzar a mano).
