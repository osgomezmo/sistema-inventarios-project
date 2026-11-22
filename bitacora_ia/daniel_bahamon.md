# Bitácora de uso de IA — Daniel Stiven Bahamon Quintero

**Proyecto:** Sistema de Gestión de Inventarios – Supermercado mediano (caso de estudio)
**Integrante:** Daniel Stiven Bahamon Quintero

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
| Integrante | Daniel Stiven Bahamon Quintero |
| Entrega N.° | 1 |
| Periodo cubierto | 21/09/2026 – 19/10/2026 |

Entrada registrada a posteriori el 07/11/2026, una vez entregada la fase.

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 30/09/2026 | Daniel Stiven Bahamon | Perplexity | Investigación de antecedentes: Odoo Inventory, ERPNext (módulo Stock) y Zoho Inventory. | Qué hace cada sistema y cuáles son sus fortalezas y debilidades. | Medio | Se usó como punto de partida de la sección de antecedentes del documento de la Entrega 1, donde quedó el resultado. Revisé el resultado antes de usarlo. |
| 30/09/2026 | Daniel Stiven Bahamon | Claude | Elaboración de las diapositivas de la sustentación de la Entrega 1. | Armar las diapositivas a partir del documento de la Entrega 1. | Medio | Diapositivas basadas en el documento entregado; las diapositivas lo indican al pie. Revisé las diapositivas antes de presentarlas. |

### Reflexión final de la fase

_Pendiente: escribir de 5 a 10 líneas sobre qué tareas se delegaron a la IA y por qué, qué se aprendió, qué errores o limitaciones se detectaron en sus respuestas y cómo se verificó o corrigió lo generado._

---

## Entrega 2 — Diseño y arquitectura (26/10/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Daniel Stiven Bahamon Quintero |
| Entrega N.° | 2 |
| Periodo cubierto | 19/10/2026 – 26/10/2026 |

Entrada registrada a posteriori el 07/11/2026, una vez entregada la fase.

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 22/10/2026 | Daniel Stiven Bahamon | Claude | Validación de la normalización de la base de datos de ms-productos y ms-inventario. | Se preguntó si el modelo de datos de los dos microservicios asignados estaba bien normalizado. | Medio | Se usó para contrastar el modelo propio con las formas normales de la teoría de bases de datos. |

### Reflexión final de la fase

_Pendiente._

---

## Entrega 3 — Implementación e integración (23/11/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Daniel Stiven Bahamon Quintero |
| Entrega N.° | 3 |
| Periodo cubierto | 27/10/2026 – 23/11/2026 |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 05-06/11/2026 | Daniel Stiven Bahamon | Claude | Investigación: cómo se conecta un microservicio de Express con un gateway de Laravel. | Cómo reenvía el gateway las peticiones, cómo se autentica el microservicio y qué cabeceras viajan entre ellos. | Medio | Uso investigativo: sirvió para entender la comunicación gateway-microservicio antes de diseñar el reenvío. Revisé las respuestas antes de usarlas. |
| 07/11/2026 | Daniel Stiven Bahamon | Claude (chat web) y Claude Code | Preparación de la rama daniel para desarrollar ms-productos y ms-inventario. | Fusionar en daniel la rama de Andrés para partir de su trabajo y revisar el estado del repositorio. | Medio | Fusión sin conflictos, verificada con git status y git log. Aprendizaje: cómo se fusionan ramas y cómo comprobar el resultado. Revisé el resultado antes de aceptarlo y autoricé cada paso. |
| 07/11/2026 | Daniel Stiven Bahamon | Claude (chat web) y Claude Code | Análisis del contrato de ms-productos y ms-inventario según el diseño de la Entrega 2 y la plantilla del front. | Extraer rutas, campos, modelo de datos, eventos y reglas de ambos servicios, compararlos con lo que espera el front y resolver las ambigüedades. | Medio | Se obtuvo el contrato y una lista de diferencias con el front; se aceptaron 23 decisiones de implementación. Las que afectan a otros servicios (formato de listados, token compartido, permisos del dashboard) quedan por acordar con el equipo. Aprendizaje: la plantilla del front simula la lógica en memoria, así que las reglas de saldo y costo promedio se programan en los servicios. Revisé el resultado antes de aceptarlo y autoricé cada paso. |
| 07/11/2026 | Daniel Stiven Bahamon | Claude (chat web) y Claude Code | Esqueleto de ms-productos (Flask): token de servicio, errores en JSON, GET /health, formato de JSON, pruebas y docker-compose.yml con MySQL. | Crear solo el esqueleto según el contrato; revisar el código y aplicar ajustes (decimales y fechas, pruebas de errores, validación del docker-compose). | Medio | Claude Code generó el código y las 24 pruebas pasan. En la revisión se detectó que Flask serializaba los Decimal como texto y las fechas en un formato no ISO, contrario al contrato, y se corrigió con un proveedor JSON propio. El docker-compose se validó con docker compose config. Aprendizaje: cómo viaja una petición (token, before_request, manejo de errores), que sigue el patrón de token de servicio del material de clase Middleware_flask.pdf (token en .env, @app.before_request y hmac.compare_digest). Revisé el resultado antes de aceptarlo y autoricé cada paso. |
| 13-14/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | ms-inventario: bodegas, stock, cliente HTTP a ms-productos, motor de movimientos con costo promedio ponderado, movimientos, kardex, traslados y devoluciones de cliente. | Con Claude redacté las indicaciones por etapa (contrato y decisiones); Claude Code escribió el código y las pruebas, incluidas pruebas de concurrencia (salidas simultáneas, traslados cruzados, reintento por interbloqueo). | Medio | 17 endpoints con sus pruebas en verde. Aprendizaje: bloqueo de filas (FOR UPDATE / FOR SHARE), orden de bloqueo para evitar interbloqueos y por qué la consulta a otro servicio va antes de la transacción. Revisé las decisiones de cada etapa, corrí las pruebas, autoricé cada commit e hice el push de los dos microservicios. |
| 14/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | API Gateway en Laravel (tarea asignada por el equipo): Docker, Sanctum, roles y permisos, administración de usuarios, reenvío a los microservicios y composición de productos por proveedor. | Indicaciones por etapa con la matriz de permisos del diseño; Claude Code escribió el código y las pruebas de Laravel. | Medio | Gateway funcionando en Docker con sus pruebas en verde. Aprendizaje: autenticación con tokens de Sanctum, middleware de permisos y reenvío con token de servicio. Revisé cada etapa, corrí las pruebas y autoricé los commits. |
| 14/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | RabbitMQ en ms-inventario: publicación de MovimientoRegistrado y StockBajoUmbral y consumidor de q.inventario con idempotencia. | Publicar después del commit, consumir con ack manual y no aplicar dos veces el mismo evento. | Medio | Funciona de punta a punta. Hallazgos: el broker de infra arrancaba sin usuario (había que crearlo) y RabbitMQ 4.4 no cuenta los nack con reentrega, así que un mensaje fallido se reintentaba sin fin; se corrigió contando los intentos en el consumidor. Revisé la prueba de punta a punta, decidí cómo crear el usuario y autoricé los commits. |
| 15-16/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | Pruebas de rendimiento con Locust (bloque B, corrida de humo) y datos iniciales con arranque automático de los contenedores. | Scripts de Locust y de datos de prueba; datos iniciales de supermercado y entrypoint que migra y siembra solo con la base vacía. | Medio | Corrida de humo sin errores y arranque en limpio verificado (los conteos no cambian al reiniciar). Dos pruebas de búsqueda dependían de que la base estuviera vacía y se ajustaron. Revisé los resultados, decidí cómo corregir las pruebas y autoricé los commits. |
| 17/11/2026 | Daniel Stiven Bahamon | Claude | Diagnóstico de por qué no se podía entrar al sistema desplegado en Google Cloud con los usuarios por rol. | Por qué fallaba el login de los usuarios por rol en el sistema desplegado. | Medio | Se encontró que gateway/.env no tenía USUARIOS_INICIALES_PASSWORD, por eso esos usuarios no existían, y que la contraseña del administrador era débil. Probé el login contra el servidor con curl y revisé mi .env. |
| 19/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | Revisión de los cambios de los compañeros en los docker-compose y guía de estudio de los archivos de los microservicios para la sustentación. | Revisar los docker-compose actualizados y explicar cada archivo de ms-productos y ms-inventario y el recorrido de dos peticiones. | Medio | Hallazgo en los docker-compose: valores por defecto y puertos publicados que convenía revisar. La guía quedó como material de estudio personal. Revisé los hallazgos y la guía. |
| 21/11/2026 | Daniel Stiven Bahamon | Claude y Claude Code (VS Code) | Ampliación del bloque B a 6 pruebas (gateway, ms-productos y ms-inventario) y corridas completas (18) con su resumen. | Agregar pruebas que separen el costo de cada capa y correr los escenarios normal, pico y estrés. | Medio | Resultados en pruebas/resultados/resumen.md. Cumplen el criterio (p95 menor a 2 s y menos de 1 % de errores) 9 de las 12 corridas N y P; no cumplen B4-P, B5-N y B5-P (salidas y traslados). Puntos de quiebre en estrés: B1 no se rompió hasta 200 usuarios; B2 a 120, B3 a 100, B4 a 20, B5 a 60 y B6 a 120 usuarios. Revisé los resultados y autoricé los commits. |

### Reflexión final de la fase

La IA aceleró la escritura de código y pruebas, pero las decisiones de diseño, la revisión y la integración con el equipo las hice yo.

---

## Entrega 4 — Cierre y sustentación final (12/12/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Daniel Stiven Bahamon Quintero |
| Entrega N.° | 4 |
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa] |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Daniel Stiven Bahamon | | | | | |

### Reflexión final de la fase

_Pendiente. En esta entrega la bitácora se consolida y se agrega una reflexión final sobre el uso de IA en todo el proyecto._
