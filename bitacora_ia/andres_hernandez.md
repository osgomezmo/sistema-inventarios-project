# Bitácora de uso de IA — Andrés Hernández

**Proyecto:** Sistema de Gestión de Inventarios – Supermercado mediano (caso de estudio)
**Integrante:** Andrés Hernández

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
| Integrante | Andrés Hernández |
| Entrega N.° | 1 |
| Periodo cubierto | 21/09/2026 – 19/10/2026 |

| Fecha      | Integrante       | Herramienta de IA    | Tarea / actividad apoyada                                                                                                                                                                    | Prompt utilizado (resumen)                                                                                                                                                                                                                                   | Nivel de intervención humana | Resultado / aprendizaje                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ---------- | ---------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 23/09/2026 | Andrés Hernández | Claude               | Definición del problema, alcance y requerimientos funcionales (RF01–RF14) y no funcionales (RNF01–RNF16) de la Entrega 1.                                                                    | Actuar como arquitecto de software y asesor del curso: con el enunciado, el avance y el checklist, definir el problema, el alcance y los RF/RNF para una empresa genérica, ajustados al checklist.                                                           | Medio                        | Quedaron inconsistencias por resolver (umbrales, ms-reportes, devoluciones, broker). Se optó por una empresa genérica. Aprendizaje: excluir ventas y facturación justifica 7 microservicios; RF04 difiere de RF10 (kardex); el stock bajo se detecta en ms-inventario. Pendiente: validar la numeración de los RNF.                                                                                                                                                                                                                         |
| 25/09/2026 | Andrés Hernández | Claude               | Corrección de la definición del problema, el alcance y los requerimientos RF/RNF de la Entrega 1.                                                                                            | Con el documento actualizado del proyecto y el ejemplo del API Gateway en Laravel, se pidió ajustar las secciones al caso de un supermercado, reemplazar JWT por tokens de Laravel Sanctum y eliminar la documentación OpenAPI y la idempotencia de eventos. | Alto                         | El equipo definió el supermercado como empresa, el uso de Sanctum y la exclusión de OpenAPI e idempotencia; la IA adaptó problemas, alcance, RF08, RNF03, RNF08, RNF10 y RNF13. Aprendizaje: los tokens de Sanctum son con estado (se guardan como hash SHA-256 y se revocan al cerrar sesión), a diferencia de JWT. Quedaron inconsistencias por resolver: la mitigación de idempotencia en la justificación, la autenticación en el gateway frente a ms-usuarios, las URL fijas (localhost) en Kubernetes y la exclusión de vencimientos. |
| 19/10/2026 | Andrés Hernández | Claude (Claude Code) | Revisión del documento de la Entrega 1 frente al enunciado, reestructuración en la plantilla institucional de presentación de trabajos y creación de las bitácoras individuales en Markdown. | Con el enunciado y la plantilla de presentación de trabajos, examinar el documento de la Entrega 1, reestructurarlo, generar el Word con la plantilla y crear una carpeta con una bitácora de IA en Markdown por integrante.                                 | Medio                        | La IA reorganizó el documento en capítulos numerados, agregó el cuadro comparativo de sistemas, las referencias que faltaban, el capítulo del repositorio y la reflexión de la fase, y corrigió inconsistencias (idempotencia, devoluciones, detección del stock bajo, autenticación). Señaló desviaciones frente al enunciado para decisión del equipo (OpenAPI, asociación producto–proveedor). Tras la revisión del equipo, la gestión de usuarios y la autenticación se ubicaron en el API Gateway y se eliminó ms-usuarios: quedan seis microservicios.                                                                                                           |

### Reflexión final de la fase

_Pendiente: escribir de 5 a 10 líneas sobre qué tareas se delegaron a la IA y por qué, qué se aprendió, qué errores o limitaciones se detectaron en sus respuestas y cómo se verificó o corrigió lo generado._

---

## Entrega 2 — Diseño y arquitectura (26/10/2026)

| Campo            | Valor                                                    |
| ---------------- | -------------------------------------------------------- |
| Proyecto         | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante       | Andrés Hernández                                         |
| Entrega N.°      | 2                                                        |
| Periodo cubierto | 19/10/2026 – 26/10/2026                                  |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| 19/10/2026 | Andrés Hernández | Claude (Claude Code) | Comprensión de la mensajería asíncrona por eventos, como preparación del diseño de la Entrega 2. | Explicar qué hace la mensajería asíncrona por eventos del diagrama de contextos, si es un microservicio o algo separado de las API, y si complementa el ejemplo de arquitectura bancaria visto en clase (Laravel, Flask, Express, MySQL y Firebase; sin Django) o es un tema nuevo. | Medio | El broker de mensajería no es un microservicio: es infraestructura aparte que guarda los eventos y los entrega a los servicios suscritos. Las API REST sirven para consultas que esperan respuesta; los eventos, para avisar que algo pasó (MercanciaRecibida, StockBajoUmbral). Es un complemento del ejemplo de clase, que solo usa REST y menciona la mensajería "cuando sea necesario", no un tema nuevo. Como en clase no se ha visto un broker (RNF19), la opción propuesta es implementar los eventos con una tabla de eventos pendientes en MySQL, un proceso en segundo plano y llamadas HTTP con reintentos e idempotencia, y consultar al docente si se permite RabbitMQ o Redis. Pendientes para la Entrega 2: decidir el mecanismo, definir los datos de cada evento y asignar framework a cada microservicio. |
| 19/10/2026 | Andrés Hernández | Claude (Claude Code) | Organización del repositorio y registro automático de la bitácora de IA. | Crear un .gitignore que excluya la bóveda de Obsidian y la plantilla de presentación, ordenar los documentos en una carpeta y hacer que los avances significativos de las sesiones de Andrés se registren automáticamente en su bitácora. | Medio | Se creó el .gitignore (.obsidian/, .trash/, plantilla, temporales de Word y configuración local de Claude Code) y la carpeta docs/ con la Entrega 1 y el enunciado. Se configuró un hook local de Claude Code (UserPromptSubmit) que, en cada mensaje, recuerda registrar aquí los avances significativos. Aprendizaje: la configuración local (.claude/settings.local.json) no se versiona y solo aplica a la sesión de cada integrante. |
| 20/10/2026 | Andrés Hernández | Claude (Claude Code) | Planificación de la Entrega 2, decisiones de diseño y generación del documento de la entrega. | Enumerar los puntos de la Entrega 2 según el enunciado y preguntar paso a paso lo que se desarrolla, consolidándolo en un borrador nuevo y, al final, generar el Word con la plantilla institucional. | Alto | La IA listó los 7 entregables y las decisiones pendientes de la Entrega 1, y propuso opciones para cada decisión. El equipo eligió: Laravel solo para el API Gateway, Flask para productos, inventario, compras y reportes, y Express para proveedores y notificaciones con Firebase, con MySQL en todos (la IA había propuesto Laravel también para inventario y compras y el equipo lo corrigió); RabbitMQ como broker de eventos, contratos de API en tablas en vez de OpenAPI y solo el diagrama de arquitectura lógica como imagen. La IA generó el diagrama (docs/figuras/e2_arquitectura_logica.png), propuso las convenciones de RabbitMQ (exchange topic, una cola por consumidor, sobre JSON con id de evento), el descubrimiento de servicios por DNS de Kubernetes, los encabezados de identidad del gateway y un catálogo de 5 eventos, 3 de ellos nuevos (MovimientoRegistrado, OrdenCompraActualizada, DevolucionProveedorRegistrada), pendientes de aprobación. Para el modelo de datos, el equipo decidió ubicar la relación proveedor–producto en ms-proveedores, valorizar con costo promedio ponderado y usar la notación entidad-relación de Chen; la IA propuso las entidades y atributos de cada servicio, el equipo los aprobó junto con el diagrama y los 5 eventos, y la IA generó los 7 diagramas entidad-relación en notación de Chen (docs/figuras/e2_er_*.png, con sus scripts en docs/figuras/fuentes/), revisando visualmente y corrigiendo solapamientos. Para los contratos, el equipo aprobó la matriz de permisos por rol, rutas al estilo del ejemplo de clase (/api/<recurso>) y detalle completo; la IA redactó las convenciones (errores, paginación, token de servicio, /health), el enrutamiento del gateway, los endpoints de los 7 componentes y el formato de los eventos con cola de errores. Al hacerlo detectó que ms-reportes no usaba MercanciaRecibida y la quitó de sus consumidores. Para Docker y Kubernetes, el equipo aprobó los contratos, eligió un MySQL por servicio, dejó sin definir la distribución de Kubernetes y pidió exponer todo en puertos locales; la IA redactó la estrategia: imágenes base, Dockerfiles de ejemplo por framework, puertos de Docker Compose, objetos de Kubernetes con sondas, HPA para ms-inventario, NodePort/port-forward para el gateway, consumidores en Deployments propios, manifiestos de ejemplo y estimación de recursos. Para las pruebas de rendimiento, el equipo eligió Locust y una carga de referencia de 20, 50 y hasta 200 usuarios, y dejó pendientes los responsables y el entorno; la IA organizó las 45 pruebas en 3 bloques de 15 (15 endpoints × escenarios normal, pico y estrés), con métricas, criterio de aprobación (p95 < 2 s y < 1 % de errores), datos de prueba y registro de resultados. Todo quedó en docs/Entrega_2_borrador.md. Para el cierre, el equipo pidió mostrar en GitHub el estado actual y un plan, indicó que Daniel y Oscar aún no registran su bitácora de esta fase y pidió un borrador de la reflexión; la IA revisó el historial de todas las ramas y generó el Word de la entrega con la plantilla institucional (docs/Entrega_2_Proyecto_ISW2_Sistema_Gestion_Inventarios.docx, 49 páginas, 23 tablas y 8 figuras), verificó cada referencia en la documentación oficial y revisó el PDF página por página. Al verificar versiones encontró que Node.js 20 y MySQL 8.0 ya no tienen soporte y que RabbitMQ 3 ya no figura entre las imágenes con soporte, así que cambió las imágenes a node:24-alpine, mysql:8.4 y rabbitmq:4-management, y precisó que la cola de errores usa colas quorum con límite de entregas. Aprendizaje: el broker, Gunicorn y la exclusión de OpenAPI son riesgos frente al enunciado y deben confirmarse con el docente; las versiones de las imágenes se deben verificar contra su fecha de fin de soporte. |
| 20/10/2026 | Andrés Hernández | Claude (Claude Code) | Preparación de las preguntas para el docente antes de la sustentación de la Entrega 2. | Indicar qué se le debe preguntar y dejar claro al profesor, con base en el enunciado y en el diseño de la Entrega 2. | Medio | La IA contrastó el diseño con el enunciado y organizó las consultas en tres grupos: las que cambian el diseño (broker, OpenAPI frente a tablas, herramientas no vistas en clase, Firebase fuera de contenedor, un MySQL por servicio), las de formato de la entrega y de las pruebas, y las decisiones que se deben informar. Encontró vacíos nuevos que el diseño no cubría: el registro centralizado de logs (RNF10), el envío real de correos para la recuperación de contraseña, la tecnología de la interfaz web y la posible lectura de "endpoints que él mismo defina" como endpoints de los servicios de cada integrante. Aprendizaje: el propio enunciado menciona "colas de mensajería" en RNF03 y "o equivalente" en RNF08, argumentos útiles para la consulta. |

### Reflexión final de la fase

_Borrador del 20/10/2026, pendiente de revisión del equipo (es el mismo de la sección 8.3 del Word):_

En esta fase el equipo usó la IA como asistente de diseño. Le delegó la propuesta de opciones para cada decisión, la redacción de los contratos, los manifiestos y el plan de pruebas, y el dibujo de los diagramas a partir de las entidades aprobadas, porque son productos extensos que siguen convenciones conocidas. Las decisiones de fondo las tomó el equipo: Laravel solo en el gateway, RabbitMQ, contratos en tablas, la relación proveedor–producto en ms-proveedores, el costo promedio ponderado, la notación de Chen, un MySQL por servicio y Locust. La IA se equivocó al proponer Laravel para inventario y compras, en contra de la regla del equipo, y al incluir a ms-reportes como consumidor de un evento que no usaba, error que ella misma detectó al redactar los contratos; además, sus primeros diagramas tenían textos superpuestos que se corrigieron tras revisarlos. Cada propuesta se aprobó antes de consolidarla y las referencias técnicas se verificaron en la documentación oficial. El principal aprendizaje es que la IA acelera el diseño detallado, pero las restricciones del curso, como las tecnologías vistas en clase, las identifica y decide el equipo; por eso quedaron como consultas al docente.

---

## Entrega 3 — Implementación e integración (23/11/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Andrés Hernández |
| Entrega N.° | 3 |
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa] |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Andrés Hernández | | | | | |

### Reflexión final de la fase

_Pendiente._

---

## Entrega 4 — Cierre y sustentación final (12/12/2026)

| Campo | Valor |
|---|---|
| Proyecto | Sistema de Gestión de Inventarios – Supermercado mediano |
| Integrante | Andrés Hernández |
| Entrega N.° | 4 |
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa] |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Andrés Hernández | | | | | |

### Reflexión final de la fase

_Pendiente. En esta entrega la bitácora se consolida y se agrega una reflexión final sobre el uso de IA en todo el proyecto._
