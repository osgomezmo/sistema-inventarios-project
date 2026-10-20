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
| Periodo cubierto | [dd/mm/aaaa – dd/mm/aaaa]                                |

| Fecha | Integrante | Herramienta de IA | Tarea / actividad apoyada | Prompt utilizado (resumen) | Nivel de intervención humana | Resultado / aprendizaje |
|---|---|---|---|---|---|---|
| dd/mm/aaaa | Andrés Hernández | | | | | |

### Reflexión final de la fase

_Pendiente._

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
