# Pruebas de Carga y Rendimiento con Locust — MS-Notificaciones y MS-Reportes

Este directorio contiene las definiciones de pruebas de estrés y rendimiento utilizando [Locust](https://locust.io/) para los endpoints de **MS-Notificaciones** y **MS-Reportes** a través del API Gateway en Laravel.

## Endpoints Sometidos a Carga

1. **`GET /api/dashboard`**: Métricas de inventario, productos bajo umbral y órdenes pendientes.
2. **`GET /api/reportes/valorizacion`**: Valorización de inventario por costo promedio (agrupación dinámica en formato JSON).
3. **`GET /api/reportes/valorizacion?formato=csv`**: Exportación y streaming de archivos tabulares CSV.
4. **`GET /api/reportes/rotacion`**: Productos de mayor y menor rotación según movimientos agregados.
5. **`GET /api/reportes/stock-bajo`**: Detección de productos en nivel crítico de inventario.
6. **`POST /api/dispositivos`**: Registro de tokens FCM para notificaciones push.
7. **`GET /api/notificaciones`**: Consulta paginada del feed de notificaciones.

## Instalación y Ejecución

1. Crear entorno virtual e instalar dependencias:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Ejecutar la interfaz web interactiva de Locust:
   ```bash
   locust -f locustfile.py --host http://127.0.0.1:8000
   ```
   Abrir el navegador en `http://localhost:8089`.

3. O ejecutar en modo headless (por ejemplo, 50 usuarios, tasa de 10 usuarios/segundo durante 1 minuto):
   ```bash
   locust -f locustfile.py --headless -u 50 -r 10 --run-time 1m --host http://127.0.0.1:8000 --html reporte_carga.html
   ```
