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

### Reflexión final de la fase

_Pendiente._

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
