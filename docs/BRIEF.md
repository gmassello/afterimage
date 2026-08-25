# Instructivo — OpenCV AI Competition 2026

> Documento de trabajo para Claude Code. Contiene las reglas del certamen, el proyecto a construir, la arquitectura, el plan por semanas y los entregables.
> Guardalo en la raíz del repo como `CLAUDE.md` (o `docs/BRIEF.md` y referencialo desde `CLAUDE.md`).

---

## 0. Lo que hay que hacer HOY, antes de escribir código

**La propuesta del grant de compute.** Son 50 grants de US$150, revisión rolling desde el 18 de agosto, notificaciones desde el 25. No hay fecha de cierre publicada: se cierra cuando se acaban los cupos.

Formulario: https://www.jotform.com/form/262145877145059 — pide nombre, email, team name, país y **un PDF**.

El PDF necesita estos ocho puntos. Se paga 10% de la rúbrica del grant por "team strength and relevant previous work", así que los cuatro repos previos van con link:

1. **Team name** — el que elijas de la sección 9.
2. **Problema e impacto real** — dos párrafos.
3. **Qué análisis de imagen o video con OpenCV 5** — nombrar módulos concretos (`Features` con ALIKED/LightGlue, `dnn`, `imgproc`).
4. **Arquitectura y servicios AWS** — S3, ECS Fargate sobre Graviton, DynamoDB, API Gateway, CloudWatch/OTel.
5. **Diagrama de arquitectura** — uno solo, una página.
6. **Usuarios objetivo**.
7. **Método de evaluación y demo para los jueces** — dataset, métricas, endpoint público.
8. **Qué path elegís**: escribir explícitamente **"Agentic Vision path"** (o "both" si vas también por COOL).

Más: **bio con hackathons y competencias previas** — github.com/gmassello/recall, /hindsight, /aiquest-minitel-client, /ringdown.

**Y registrarse en Devpost ya**, aunque el proyecto no exista: `/updates` y Discussions están vacíos, el único canal de avisos que van a usar es el mail a inscriptos.

> La propuesta es para el grant, no para competir. Los no seleccionados siguen siendo elegibles para todos los premios. Pero mandarla es gratis y cierra el riesgo de la frase ambigua *"all teams that submitted the required proposal will build…"*.

---

## 1. Reglas del certamen — restricciones duras

Claude Code tiene que respetar esto en cada decisión de diseño.

| Regla | Detalle |
|---|---|
| **OpenCV 5 obligatorio** | Para *análisis sustantivo* de imagen o video. No alcanza con usarlo para leer un JPEG. |
| **Componente significativo en AWS** | El workload de visión corre en AWS. Un front en Vercel con la inferencia en AWS cumple; OpenCV en la notebook con AWS sirviendo estáticos, no. |
| **Sin hardware obligatorio** | "Any programming language or supporting hardware is allowed." No hace falta cámara ni dispositivo. |
| **Deadline** | 26 oct 23:59 PT = **martes 27 oct 03:59 ART**. |
| **Equipo** | 1 a 5 personas. Solo permitido. |
| **Repo** | Accesible a los jueces. **No tiene que ser open source** — puede ser privado con acceso. |
| **Video** | Máximo 5 minutos, **tiene que mostrar al equipo** (cara), la app funcionando, la arquitectura y los resultados. |
| **Demo** | Web endpoint funcionando o screen-share en vivo coordinada. |
| **Anti-trampa del Agentic Award** | *"Using an AI coding assistant to write the entry does not qualify as an agentic workflow."* El loop agéntico va **en el producto**, no en el proceso de desarrollo. |
| **GPU** | El nuevo engine DNN de OpenCV 5 **todavía no tiene GPU**. Diseñar para CPU/Graviton. |

### Rúbrica overall — dónde se juega el puntaje

| Criterio | Peso |
|---|---|
| Ejecución técnica | 30% |
| Innovación | 20% |
| Impacto real | 20% |
| Experiencia de usuario | 10% |
| Documentación y presentación | 10% |
| Cloud, reproducibilidad y operación responsable | 10% |

**El 60% es juicio subjetivo.** La narrativa y el video pesan tanto como el código.

### Rúbrica del Agentic Vision Award (US$1.000 extra)

| Criterio | Peso |
|---|---|
| Integración OpenCV 5 + agente | 30% |
| Orquestación y autonomía apropiada | 25% |
| Efectividad de tarea y evaluación | 20% |
| **Manejo de fallas, observabilidad, seguridad y control humano** | 15% |
| UX y documentación | 10% |

El umbral para calificar, textual:

> "…image or video results must influence a subsequent plan, tool call, action, or request for human approval. A chatbot that only explains a fixed vision result is not enough — **the visual evidence must change what the system does next**."

Evidencia extra obligatoria: diagrama del workflow percepción → decisión → acción, y **una traza que demuestre que el output de OpenCV cambió una decisión posterior**.

---

## 2. El proyecto

### Concepto: un agente de inspección visual que recuerda

Un agente que inspecciona activos físicos a partir de fotos o video, decide por sí mismo qué mirar después, y **conserva memoria de cada inspección anterior del mismo activo** para detectar degradación en el tiempo.

**Por qué este concepto y no otro:**

- **Ningún ganador anterior tuvo memoria longitudinal.** Todos los proyectos premiados analizan un frame o una sesión aislada. "El mismo activo, visto de nuevo tres meses después" es territorio vacío, y es exactamente Recall.
- **El loop percepción → decisión → acción sale natural**, no forzado. La calidad de la imagen decide si hay que pedir recaptura; la diferencia contra el baseline decide si hay que hacer zoom; la severidad decide si hay que pedir aprobación humana. Tres puntos donde la evidencia visual cambia lo que el sistema hace después.
- **El 15% de manejo de fallas y observabilidad es Hindsight con otro nombre.**
- **Impacto real defendible** (20% de la rúbrica) sin inventar: mantenimiento preventivo de infraestructura.

**Vertical sugerido:** inspección de **paneles solares** a partir de video o fotos (defectos: celdas rotas, hot spots visibles, suciedad, delaminación, desalineación). Es el que mejor combina dataset público disponible, degradación medible en el tiempo, y una historia de impacto clara.

**Verticales alternativos**, si preferís otro — la arquitectura no cambia:

- **Infraestructura vial** — relevamiento de baches y señalización desde video de dashcam, con seguimiento del mismo tramo en el tiempo.
- **Auditoría de góndola en retail** — cumplimiento de planograma y detección de deriva contra la referencia.
- **Inspección de tableros eléctricos / equipamiento industrial** — corrosión, cableado, etiquetas.

### El loop agéntico — lo que califica para el award

Este es el corazón del proyecto. Cada paso donde dice **ACCIÓN** es un punto donde el resultado visual cambia lo que pasa después.

```
   entra una captura (foto o frame) de un activo con ID conocido
              │
              ▼
   ┌──────────────────────────┐
   │ assess_quality()         │  OpenCV: blur (Laplaciano), exposición,
   │                          │  cobertura del encuadre
   └──────────┬───────────────┘
              │  ¿inservible?
              ├──────────────► ACCIÓN 1: pedir recaptura con instrucción
              │                concreta ("más cerca", "menos contraluz")
              ▼  sirve
   ┌──────────────────────────┐
   │ align_to_baseline()      │  OpenCV 5 Features: ALIKED + LightGlueMatcher
   │                          │  contra la imagen de referencia guardada
   └──────────┬───────────────┘  DEL MISMO activo → homografía
              │  ¿no alinea?
              ├──────────────► ACCIÓN 2: reintentar con otro detector, o
              │                declarar "activo no reconocido" y pedir confirmación
              ▼  alineado
   ┌──────────────────────────┐
   │ diff_against_memory()    │  comparación contra la última inspección:
   │                          │  regiones cambiadas, magnitud, tendencia
   └──────────┬───────────────┘
              │  ¿cambio detectado con confianza baja?
              ├──────────────► ACCIÓN 3: crop_and_rescan() sobre la ROI
              │                — percepción activa: el agente decide
              │                DÓNDE mirar más de cerca y vuelve a entrar al loop
              ▼  cambio confirmado
   ┌──────────────────────────┐
   │ classify_severity()      │  OpenCV + clasificador
   └──────────┬───────────────┘
              │  ¿severidad alta?
              ├──────────────► ACCIÓN 4: request_human_approval() antes de
              │                abrir el ticket. Autonomía graduada.
              ▼
   ┌──────────────────────────┐
   │ write_memory()           │  nuevo baseline + evento + trazabilidad
   └──────────────────────────┘
              │
              ▼  toda la ejecución emitida como traza OTel
```

**Regla de oro:** cada decisión del agente tiene que ser reconstruible desde la traza. Si un juez pregunta "¿por qué hizo zoom acá?", la respuesta tiene que estar en el span, con el valor numérico que la disparó.

---

## 3. Arquitectura

```
┌─── Cliente ──────────────────────────────────────────────┐
│  Front mínimo (Next.js o Vite + React)                   │
│  · subir captura · ver historial del activo              │
│  · cola de aprobaciones humanas · visor de trazas        │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼──────────────────────────────────┐
│  API Gateway  →  FastAPI en ECS Fargate (arm64/Graviton) │
└───────┬──────────────────────────┬───────────────────────┘
        │                          │
        ▼                          ▼
┌────────────────────┐    ┌──────────────────────────────┐
│  Agent runtime     │    │  Perception service           │
│  · policy engine   │◄──►│  · OpenCV 5 (contenedor ARM)  │
│  · loop p→d→a      │MCP │  · assess_quality             │
│  · HITL gate       │    │  · align_to_baseline          │
└────────┬───────────┘    │  · diff_against_memory        │
         │                │  · crop_and_rescan            │
         │                │  · classify_severity          │
         │                └──────────────────────────────┘
         ▼
┌────────────────────────────────────────────────────────┐
│  Memory bank                                            │
│  · DynamoDB: activos, inspecciones, eventos, baselines  │
│  · S3: capturas originales, crops, imágenes de baseline │
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Observabilidad — OpenTelemetry                         │
│  · un span por tool call, con inputs, métricas y        │
│    la decisión que disparó                              │
│  · exporta a CloudWatch / OTLP collector                │
│  · endpoint /traces/{run_id} para que el juez la vea    │
└────────────────────────────────────────────────────────┘
```

### Stack

| Capa | Elección | Por qué |
|---|---|---|
| Visión | **OpenCV 5.0** (`opencv-python==5.0.0.93`) | Requisito duro |
| Runtime | Python 3.12 | SDK y ecosistema |
| API | FastAPI + uvicorn | Rápido de levantar, OpenAPI gratis |
| Contenedor | Docker `arm64`, base Ubuntu 24.04 | Graviton, y compatible con la AMI de COOL |
| Cómputo | **ECS Fargate ARM** o EC2 `c8g.large` | Graviton = requisito para el premio COOL |
| Storage | S3 (imágenes) + DynamoDB (memoria) | Serverless, barato, cabe en el grant |
| Agente | LLM vía API + herramientas expuestas por **MCP** | Las reglas permiten MCP explícitamente |
| Trazas | OpenTelemetry SDK → OTLP | El 15% del award |
| Front | Next.js o Vite + React, deploy estático | Suficiente para el endpoint público |
| IaC | Terraform o AWS CDK | Reproducibilidad = 10% de la nota |

### Advertencia de versiones para Claude Code

> **OpenCV 5 salió el 6 de junio de 2026.** Es posterior a los datos de entrenamiento de la mayoría de los modelos. **Verificá cada API contra https://docs.opencv.org/5.x/ antes de usarla.** No asumas que la firma de OpenCV 4 sigue valiendo.
>
> Cambios que rompen: se eliminó la API de C, el mínimo es C++17, ML y G-API se movieron a contrib, `Features2D` fue reemplazado por el módulo **`Features`**.
>
> Novedades a aprovechar: matching neuronal (`ALIKED`, `DISK`, `LightGlueMatcher`), DNN reescrito con 80%+ de cobertura ONNX y shapes dinámicos, LLM/VLM dentro del módulo `dnn` con tokenizer y KV-cache, tipos FP16/BF16/bool/int64, tensores 0D y 1D.

---

## 4. Plan por semanas

Nueve semanas, del 26 de agosto al 26 de octubre. Cada semana cierra con algo demostrable.

| Semana | Fechas | Objetivo | Cierra con |
|---|---|---|---|
| **1** | 26 ago – 1 sep | Andamiaje. Repo, Docker arm64 con OpenCV 5, S3, CI. | Un contenedor que lee una imagen de S3 y devuelve un número calculado con OpenCV 5. |
| **2** | 2 – 8 sep | Herramientas de percepción. Las cinco funciones, con tests. | `pytest` verde sobre imágenes de fixture. |
| **3** | 9 – 15 sep | Memory bank. Esquema DynamoDB, baselines en S3, historial por activo. | Segunda inspección del mismo activo que compara contra la primera. |
| **4** | 16 – 22 sep | Servidor MCP + loop agéntico + política de autonomía + gate humano. | El loop completo corriendo local, con las cuatro acciones disparándose. |
| **5** | 23 – 29 sep | Observabilidad. Spans OTel por tool call, endpoint de trazas. | Una traza donde se ve que un valor de OpenCV cambió la decisión siguiente. ⚠️ Si tenés grant, acá cae el check-in por Zoom (21 sep – 2 oct). |
| **6** | 30 sep – 6 oct | Deploy completo en AWS + front + endpoint público. | URL pública funcionando que un juez puede usar. |
| **7** | 7 – 13 oct | Evaluación. Dataset, métricas, **casos de falla**. | Tabla de resultados con precisión, recall y limitaciones honestas. |
| **8** | 14 – 20 oct | Informe técnico, diagramas, deps pinneadas, instrucciones. Si vas por COOL: benchmark contra baseline. | Documentación completa en el repo. |
| **9** | 21 – 26 oct | Video, deck, pulido. **Submission el 24 o 25**, no el 26. | Entrega hecha con 48 h de margen. |

**Regla de margen:** la entrega se hace el sábado 24 o domingo 25. El 26 es colchón, no fecha de trabajo.

---

## 5. Estructura del repo

```
.
├── CLAUDE.md                     # este documento
├── README.md                     # qué es, cómo correrlo, arquitectura
├── docs/
│   ├── ARCHITECTURE.md           # diagrama + explicación de componentes
│   ├── AGENT_LOOP.md             # el diagrama percepción→decisión→acción
│   ├── EVALUATION.md             # dataset, métricas, casos de falla
│   ├── TECHNICAL_REPORT.md       # el informe que pide el certamen
│   └── diagrams/                 # fuentes (mermaid o excalidraw) + PNG
├── services/
│   ├── perception/               # OpenCV 5: las cinco herramientas
│   │   ├── quality.py
│   │   ├── alignment.py          # ALIKED + LightGlueMatcher
│   │   ├── diffing.py
│   │   ├── severity.py
│   │   └── tests/
│   ├── mcp_server/               # expone perception como herramientas MCP
│   ├── agent/
│   │   ├── loop.py               # percepción → decisión → acción
│   │   ├── policy.py             # umbrales, escalamiento, autonomía
│   │   └── hitl.py               # gate de aprobación humana
│   ├── memory/                   # DynamoDB + S3, baselines e historial
│   └── api/                      # FastAPI
├── web/                          # front mínimo
├── infra/                        # Terraform o CDK
├── eval/
│   ├── dataset/                  # fixtures y dataset de evaluación
│   ├── run_eval.py
│   └── results/                  # resultados versionados
├── observability/                # config OTel, dashboards
├── Dockerfile                    # arm64
├── docker-compose.yml            # entorno local completo
├── requirements.txt              # PINNEADO, exacto
└── Makefile                      # make dev, make test, make eval, make deploy
```

---

## 6. Los siete entregables y cómo se producen

| # | Entregable | Se produce en | Nota |
|---|---|---|---|
| 1 | Informe técnico | `docs/TECHNICAL_REPORT.md` | Problema, usuarios, arquitectura, implementación OpenCV 5, deploy AWS, evaluación, limitaciones, uso responsable. |
| 2 | Repositorio | GitHub | Puede ser privado con acceso para jueces. Si lo hacés público, cuidado con las credenciales en el historial. |
| 3 | Deps pinneadas + instrucciones | `requirements.txt` + `README.md` | Versiones exactas, no rangos. Que un juez lo levante con `make dev`. |
| 4 | Diagrama de arquitectura | `docs/diagrams/` | Dos: el de infraestructura y el del loop agéntico. El segundo es obligatorio para el award. |
| 5 | Web endpoint | Deploy en AWS | Que funcione sin login, o con credenciales de demo en el informe. |
| 6 | Video ≤ 5 min | — | Guion en la sección 7. **Tiene que aparecer tu cara.** |
| 7 | Evidencia de evaluación | `eval/results/` + `docs/EVALUATION.md` | Incluir **casos de falla**. Es un requisito explícito, y admitir límites suma en un jurado técnico. |

### Cómo mapear cada criterio a evidencia concreta

| Criterio | Peso | Qué lo demuestra |
|---|---|---|
| Ejecución técnica | 30% | Tests verdes, el módulo `Features` de OpenCV 5 usado en serio, arquitectura limpia, evaluación con números. |
| Innovación | 20% | **La memoria longitudinal.** Es lo que ningún ganador anterior tuvo. Decirlo explícitamente en el informe y en el video. |
| Impacto real | 20% | Un caso de uso con números: cuántos activos, cuánto cuesta la inspección manual, qué ahorra. |
| UX | 10% | Que la cola de aprobaciones y el historial se entiendan sin explicación. |
| Documentación | 10% | El informe y el README. Es barato y mucha gente lo descuida. |
| Cloud y operación responsable | 10% | Terraform, trazas OTel, manejo de secretos, política de retención de imágenes. |
| **Agentic (award aparte)** | — | La traza donde se ve que un número de OpenCV cambió la decisión siguiente. **Grabala y mostrala en el video.** |

---

## 7. Guion del video (5 minutos)

| Tiempo | Contenido |
|---|---|
| 0:00 – 0:25 | **Cara a cámara.** Quién sos, qué construiste en una frase. Requisito explícito. |
| 0:25 – 1:00 | El problema, con un número concreto. |
| 1:00 – 1:30 | Diagrama de arquitectura, 30 segundos, sin detenerse en cada caja. |
| 1:30 – 3:15 | **La demo.** Subir una captura, que el agente pida recaptura, subir una buena, que detecte el cambio contra la inspección anterior, que haga zoom solo, que pida aprobación. Este es el corazón. |
| 3:15 – 4:00 | **La traza.** Mostrar el span donde el valor de OpenCV disparó la decisión. Es la evidencia del award. |
| 4:00 – 4:35 | Resultados de evaluación, incluyendo un caso de falla. |
| 4:35 – 5:00 | Qué sigue y cierre. |

Grabar en la semana 9 pero **escribir el guion en la semana 7**, para que el desarrollo apunte a que la demo se vea bien.

---

## 8. Riesgos y trampas

| Riesgo | Mitigación |
|---|---|
| **APIs de OpenCV 5 alucinadas** | Verificar todo contra `docs.opencv.org/5.x`. Los modelos conocen OpenCV 4. |
| **Sin GPU en el DNN engine** | Diseñar para CPU/Graviton desde el día uno. No planificar nada que necesite CUDA. |
| **El loop agéntico queda decorativo** | Si el agente siempre hace lo mismo, no califica. Tiene que haber ramas reales y demostrables. Testear los cuatro caminos. |
| **Confundir "usé Claude Code" con "es agéntico"** | Está descalificado explícitamente. El loop va en el producto. |
| **COOL se cobra solo** | Free trial de 7 días que se convierte a pago. Si lo probás, poné un recordatorio para cancelarlo. |
| **Documentación a último momento** | Es el 20% de la nota. Escribir el informe en la semana 8, no en la 9. |
| **El endpoint público se cae en judging** | El judging va del 27 de octubre al 9 de noviembre. Presupuestar AWS para que siga vivo hasta el 10 de noviembre. |
| **Reglas oficiales todavía sin publicar** | Revisar `/updates` en Devpost cada semana. Cuando salgan, chequear ley aplicable, jurisdicción y lista de países. |

---

## 9. Nombres para el repo

Todos disponibles como nombre de repo (verificá en GitHub antes de fijar). Siguen el patrón de los tuyos: una sola palabra en inglés, evocativa.

### La familia de recall y hindsight

| Nombre | Por qué |
|---|---|
| **afterimage** | Lo que queda visible después de dejar de mirar. Es literalmente memoria visual persistente — el concepto del proyecto en una palabra. **Mi favorito.** |
| **revisit** | El acto central: volver a ver el mismo activo. Simple y exacto. |
| **foresight** | Cierra la trilogía con hindsight. Riesgo: sugiere predicción, y el proyecto detecta, no predice. |
| **retrace** | Volver sobre lo ya recorrido. Funciona con la idea de historial. |

### Del vocabulario de la visión

| Nombre | Por qué |
|---|---|
| **saccade** | El movimiento rápido del ojo para redirigir la mirada. Es la percepción activa: el agente decide dónde mirar después. Técnicamente preciso y poco usado. |
| **fovea** | La zona de la retina de máxima agudeza. Encaja con el `crop_and_rescan`: enfocar donde importa. |
| **parallax** | Ver lo mismo desde otro punto — o desde otro momento. Elegante, quizá demasiado abstracto. |

### Del vocabulario de la inspección

| Nombre | Por qué |
|---|---|
| **vigil** | Vigilancia sostenida en el tiempo. Corto, serio, memorable. |
| **stakeout** | Observación prolongada de un mismo objetivo. Informal pero muy claro. |
| **watchpost** | Puesto de observación. Menos original que los anteriores. |

### Recomendación

**`afterimage`** para el repo. Dice memoria y visión al mismo tiempo, es una sola palabra, no está gastada, y se explica en una frase en el video: *"an afterimage is what your eye still sees after you look away — this agent keeps one for every asset it inspects."*

Si el vertical termina siendo paneles solares y querés algo más literal, **`revisit`** es la segunda opción y no necesita explicación.

---

## 10. Prompts de arranque para Claude Code

**Sesión 1 — andamiaje**

> Leé `CLAUDE.md`. Armá el andamiaje del proyecto: estructura de carpetas de la sección 5, `Dockerfile` para arm64 sobre Ubuntu 24.04 con Python 3.12 y `opencv-python==5.0.0.93`, `docker-compose.yml` con LocalStack para S3 y DynamoDB, `Makefile` con `dev/test/eval/deploy`, y un test que verifique que OpenCV 5 importa y reporta versión 5.x. Antes de usar cualquier API de OpenCV, verificala contra docs.opencv.org/5.x — tu conocimiento de OpenCV es de la versión 4.

**Sesión 2 — percepción**

> Implementá las cinco herramientas de `services/perception/` según la sección 2. Para `align_to_baseline` usá el módulo `Features` de OpenCV 5 con ALIKED y LightGlueMatcher — verificá las firmas en la documentación 5.x. Cada función devuelve un dataclass con el resultado *y* las métricas numéricas que van a alimentar la decisión del agente. Tests con imágenes de fixture.

**Sesión 3 — memoria**

> Implementá `services/memory/`: esquema de DynamoDB para activos, inspecciones, eventos y baselines; guardado de imágenes en S3; y la consulta "dame la última inspección de este activo". Diseñá las claves para que traer el historial completo de un activo sea una sola query.

**Sesión 4 — agente**

> Implementá el servidor MCP que expone las herramientas de percepción, y el loop de `services/agent/` con las cuatro acciones del diagrama. La política de umbrales va en `policy.py`, configurable, no hardcodeada en el loop. Cada decisión tiene que registrar qué valor la disparó.

**Sesión 5 — trazas**

> Instrumentá todo con OpenTelemetry: un span por tool call con inputs, métricas de salida y la decisión resultante. Agregá `GET /traces/{run_id}` que devuelva la traza en un formato legible para un humano. Este endpoint es evidencia para el premio, tiene que verse bien.

---

## 11. Checklist de submission

Antes de apretar enviar, el sábado 24 o domingo 25 de octubre:

- [ ] Repo accesible a los jueces (público, o privado con acceso concedido)
- [ ] `requirements.txt` con versiones exactas
- [ ] `README.md` con instrucciones de build, deploy y test que funcionan en una máquina limpia
- [ ] `docs/TECHNICAL_REPORT.md` completo, con limitaciones y uso responsable
- [ ] Diagrama de arquitectura **y** diagrama del loop agéntico
- [ ] Endpoint público funcionando, probado desde otra red
- [ ] Video de máximo 5 minutos, con tu cara, subido como público o unlisted
- [ ] `docs/EVALUATION.md` con métricas y **casos de falla**
- [ ] La traza que demuestra que OpenCV cambió una decisión — enlazada desde el informe
- [ ] Presupuesto de AWS con margen hasta el 10 de noviembre (dura el judging)
- [ ] Sin credenciales en el historial de git

---

## Referencias

- Competencia: https://opencv26.devpost.com/ · reglas: https://opencv26.devpost.com/rules
- Sitio oficial (tiene datos que Devpost no trae): https://opencv.org/opencv-ai-competition-2026/
- Propuesta del grant: https://www.jotform.com/form/262145877145059
- OpenCV 5: https://opencv.org/opencv-5/ · docs: https://docs.opencv.org/5.x/
- COOL: https://opencv.org/cool/ · AMI: https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs
