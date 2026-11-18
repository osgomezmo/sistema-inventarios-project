# Bitácora de uso de IA — Oscar David Gomez Mosquera

**Proyecto:** Sistema de Gestión de Inventarios – Supermercado mediano (caso de estudio)
**Integrante:** Oscar David Gomez Mosquera

> **Cómo llenar esta bitácora** (secciones 6 y 7 del enunciado del proyecto)
>
> - Agregue una fila por cada interacción relevante con una herramienta de IA (Claude, ChatGPT, GitHub Copilot, etc.) en la tabla de la entrega correspondiente.
> - **Prompt utilizado (resumen):** resumen del prompt o enlace a la conversación.
> - **Nivel de intervención humana:** Alto / Medio / Bajo.
> - **Resultado / aprendizaje:** qué se usó tal cual, qué se modificó y qué se aprendió.
> - Al cierre de cada entrega, escriba la **reflexión final de la fase** (5 a 10 líneas): qué tareas delegó a la IA y por qué, qué aprendió, qué errores o limitaciones detectó en las respuestas de la IA y cómo verificó o corrigió lo generado.
> - La bitácora es obligatoria en las cuatro entregas y se sustenta: el docente puede preguntar por cualquier decisión tomada con apoyo de IA.

---

## Entrega 1 — Investigación y fundamentación (28/09/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Oscar David Gomez Mosquera |
| Entrega N.° | 1 |
| Periodo cubierto | 21/09/2026 – 28/09/2026 |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 21/09/2026 | Oscar David Gomez | Claude | Identificación preliminar de microservicios (bounded contexts). | Se solicitó proponer y justificar la partición en microservicios a partir de los RF/RNF del enunciado, aplicando DDD. | Medio | Se validó la propuesta de 7 microservicios contra la técnica estándar de bounded contexts (investigada aparte); se ajustó el manejo de RF13 (devoluciones), que se repartió entre compras e inventario tras la discusión del equipo. |

### Reflexión final de la fase

En esta primera fase se utilizó la IA principalmente para explorar y contrastar la descomposición del sistema en contextos delimitados (Bounded Contexts) bajo principios de Domain-Driven Design (DDD). La IA propuso una partición preliminar de 7 microservicios que sirvió como base para la discusión con el equipo. Como ajuste crítico, se detectó que la IA intentaba centralizar las devoluciones en un servicio único aislado, por lo que se intervino manualmente para distribuir el flujo entre compras e inventario según los requerimientos del supermercado.

---

## Entrega 2 — Diseño y arquitectura (26/10/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Oscar David Gomez Mosquera |
| Entrega N.° | 2 |
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa] |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Oscar David Gomez | | | | | |

### Reflexión final de la fase

En el arranque del repositorio configuré el proyecto base del API Gateway en Laravel con Sanctum (commit inicial de main y develop), estableciendo la base de autenticación perimetral y el enrutamiento hacia los microservicios. Para la Entrega 3 asumo la implementación completa de los dos servicios reactivos (MS-Notificaciones y MS-Reportes), por lo cual el trabajo profundo de implementación e integración de eventos se concentra en dicha fase.

---

## Entrega 3 — Implementación e integración (23/11/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Oscar David Gomez Mosquera |
| Entrega N.° | 3 |
| Periodo cubierto | 13/11/2026 – 23/11/2026 |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 13/11/2026 | Óscar David Gómez Mosquera | Claude / Gemini | Auditoría del documento de arquitectura (Entrega 2) y diseño del plan de implementación de MS-Notificaciones y MS-Reportes. | Analizar el documento de la Entrega 2 y las ramas del repositorio para estructurar una guía paso a paso de implementación, identificar vacíos en los contratos de eventos y definir la estrategia de desarrollo local sin cuenta de Firebase. | Alto | Se detectó que el evento MovimientoRegistrado no incluye el campo stock_minimo, por lo que MS-Reportes debe cerrar las alertas activas en AlertaStock comparando saldo_resultante contra el stock_minimo almacenado previamente en la propia alerta. Además, se diseñó un patrón adaptador para probar Firestore y FCM en local y se definió x-dead-letter-routing-key por cola en RabbitMQ. |
| 13/11/2026 | Óscar David Gómez Mosquera | Antigravity | Configuración de reglas AGENTS.md, infraestructura local de RabbitMQ 4 en Docker y simulador CLI de eventos (publicar_evento.py). | Crear los archivos AGENTS.md tomando ms-productos como referencia, levantar RabbitMQ con definitions.json (exchange inventario.eventos, colas quorum con x-delivery-limit: 3 y DLQ) y construir un simulador CLI en Python con pika para inyectar eventos de prueba. | Medio | Se configuró rabbitmq.conf para cargar automáticamente la topología sin sobrescribir el usuario del .env. Se verificó en el panel web (:15672) el enrutamiento hacia q.notificaciones y q.reportes, el uso de --id-evento para probar idempotencia y --corrupto para forzar el envío a las colas .errores. |
| 13/11/2026 | Óscar David Gómez Mosquera | Antigravity | Implementación completa y pruebas de MS-Notificaciones (Express, Firestore/FCM adaptador y consumidor RabbitMQ) | Implementar los pasos 1.1 a 1.3 de MS-Notificaciones: estructura base con Express y variables de entorno, middlewares de correlación (X-Correlation-Id) y autenticación por SERVICE_TOKEN con inyección de usuario/rol, adaptadores desacoplados de persistencia (local en .data/db.json / Firestore) y mensajería push (consola / FCM), controladores y rutas para registro/baja de dispositivos y consulta/marcado de notificaciones con paginación, y consumidor AMQP para StockBajoUmbral con acuse manual (ack/nack) y batería de 36 pruebas automatizadas en Jest. | Medio | Se estructuró la normalización de nombres de roles para temas de FCM (ej. 'Jefe de bodega' a 'rol_jefe_de_bodega' y 'Compras' a 'rol_compras'). Se implementó la autorización estricta 'Dueño o Admin' en DELETE /dispositivos/{id} validando id_usuario y rol admin. Se garantizó la idempotencia mediante la colección eventos_procesados y la deduplicación de alertas no leídas por (rol, sku, bodega) para evitar saturación. Se verificó que ante eventos corruptos el consumidor invoca channel.nack(msg, false, true), provocando que la cola quorum q.notificaciones reintente exactamente 3 veces (x-delivery-limit: 3) antes de derivar el mensaje a q.notificaciones.errores mediante el Dead Letter Exchange. |
| 17/11/2026 | Óscar David Gómez Mosquera | Antigravity | Implementación de MS-Reportes (Flask, MySQL CQRS, RabbitMQ, exportación CSV/PDF) e integración con API Gateway | Implementar los pasos 2.1 a 2.3 de MS-Reportes y su integración: estructura base en Flask con contenedor MySQL 8.4 independiente (puerto 33065) y migraciones SQL sin ORM; proyecciones atómicas de eventos (MovimientoRegistrado, OrdenCompraActualizada, StockBajoUmbral) en consumidor RabbitMQ (pika) con cola quorum q.reportes y DLQ; cliente HTTP tolerante a fallos para ms-productos, endpoints analíticos (valorización, rotación, stock bajo, dashboard) con exportación a CSV y PDF (ReportLab); empaquetado Docker (Dockerfile, entrypoint.sh) e integración completa con API Gateway en Laravel, asegurando el passthrough de cabeceras y binarios. | Medio | Se consolidó el modelo de lectura (CQRS) usando claves compuestas con INSERT ... ON DUPLICATE KEY UPDATE para actualizar eficientemente saldos agregados y métricas diarias por (sku, id_bodega, fecha). Se implementó el cierre automático de alertas activas en alerta_stock cuando un MovimientoRegistrado eleva el saldo resultante por encima del stock mínimo previamente registrado. Se programó la exportación dinámica a CSV y a PDF vectorial manteniendo estilos corporativos y metadatos de filtrado. Se comprobó que el API Gateway en Laravel reenvía los archivos binarios y cabeceras Content-Type y Content-Disposition sin corromper el contenido, validándolo tanto con una nueva prueba en PHPUnit como en una prueba E2E en vivo con el simulador de eventos. |
| 18/11/2026 | Óscar David Gómez Mosquera | Antigravity | Contenerización con Docker, manifiestos de Kubernetes (liveness/readiness probes) y scripts de pruebas de carga con Locust para MS-Notificaciones y MS-Reportes | Completar Fases 3 y 4 de la Entrega 3: Dockerfile multi-etapa/optimizados con HEALTHCHECK para MS-Notificaciones (node:24-alpine) y MS-Reportes (python:3.12-slim con gunicorn y consumidor AMQP integrado); manifiestos de Kubernetes en infra/k8s/ (Deployment, Service ClusterIP, ConfigMap, Secret, PVC y probes HTTP/exec con límites de recursos para rabbitmq, db-reportes, ms-notificaciones y ms-reportes); integración en docker-compose.yml general; y suite de pruebas de carga con Locust para los endpoints de dashboard, valorización (JSON/CSV), rotación, stock bajo, dispositivos y notificaciones a través del API Gateway. | Medio | Se optimizó la construcción de las imágenes Docker (en Node.js mediante COPY --chown para evitar la sobrecarga de un chown recursivo en overlayfs y en Python mediante entrypoint.sh con gestión de procesos en segundo plano y trampas de señales para el consumidor pika). En Kubernetes se implementaron las sondas livenessProbe y readinessProbe mapeadas a los endpoints /health de cada servicio y a diagnósticos internos en RabbitMQ y MySQL, previniendo tráfico prematuro durante el arranque y reinicios en falso. En las pruebas de rendimiento con Locust (bloque C en pruebas/locust y locustfile.py central en infra/locust) se modelaron escenarios concurrentes (N, P, E) validando la estabilidad del API Gateway, el despojo del prefijo /api, la reutilización de tokens Sanctum y la latencia en la generación de streams binarios de reportes. |

### Reflexión final de la fase

Durante la Entrega 3 se implementaron de forma integral los dos servicios reactivos del sistema: MS-Notificaciones y MS-Reportes. El éxito de esta fase radicó en una estrategia técnica basada en cuatro pilares fundamentales:

1. **Gobernanza mediante reglas de contexto (`AGENTS.md`)**: Establecer directrices estrictas en cada microservicio garantizó que el código respetara la arquitectura de referencia (`.referencia/ms-productos`), evitando el uso de ORMs innecesarios en Python, estandarizando la gestión atómica de transacciones en MySQL, unificando la propagación de encabezados (`X-Correlation-Id`, `X-User-Id`, `X-User-Role`) y protegiendo las credenciales mediante el uso exclusivo de archivos `.env.example`.
2. **Simulador de eventos e infraestructura local**: El desarrollo de `publicar_evento.py` y la configuración automatizada de RabbitMQ 4 con colas quorum (`x-delivery-limit: 3`) permitieron simular el comportamiento real de `ms-inventario` y `ms-compras`. Esto facilitó verificar empíricamente la idempotencia transaccional con `evento_procesado`, el enrutamiento a Dead Letter Queues (`q.*.errores`) ante mensajes corruptos y la reactividad de las proyecciones analíticas.
3. **Diseño de adaptadores locales**: La implementación de adaptadores desacoplados de persistencia (JSON local/Firestore) y mensajería push (consola/FCM) en MS-Notificaciones permitió desarrollar y ejecutar suites completas de pruebas unitarias e integración en Jest sin dependencias externas bloqueantes de nube.
4. **Verificación E2E y despliegue**: La integración con el API Gateway en Laravel comprobó que los contratos de enrutamiento, la seguridad perimetral con Sanctum y el passthrough de respuestas binarias complejas (como la exportación a PDF y CSV) operan de manera robusta, culminando con la contenerización en Docker, manifiestos de Kubernetes con sondas de salud y pruebas de carga con Locust.

---

## Entrega 4 — Cierre y sustentación final (12/12/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Oscar David Gomez Mosquera |
| Entrega N.° | 4 |
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa] |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Oscar David Gomez | | | | | |

### Reflexión final de la fase

_Pendiente. En esta entrega la bitácora se consolida y se agrega una reflexión final sobre el uso de IA en todo el proyecto._
