# Review de proyecto — afterimage

**Archivos revisados:** 71 de 125 archivos de texto (152 versionados, 27 binarios de dataset/fuentes/modelos).
Alcance: los 33 módulos no-test de `services/`, los 26 archivos de test, `eval/`, `infra/`, los dos
workflows, `Makefile`, `Dockerfile`, `deploy.sh`, `requirements.txt`, `pyproject.toml` y las páginas de
`docs/` en lo referido a las afirmaciones que se verificaron. Fuera de alcance: `video/` (utilería de
producción del demo) y los binarios del dataset.

---

## Resumen

**Veredicto: necesita cambios acotados, sin bloqueantes.** 3 altos, 12 medios, 10 bajos.

afterimage es un agente de inspección visual con memoria longitudinal: una FastAPI arm64 en Lambda
sirve la UI y corre el loop del agente dentro del request, cinco herramientas de percepción se exponen
por MCP stdio, `policy.evaluate()` decide toda rama en código y graba el número que la disparó, y la
memoria vive en una tabla DynamoDB más imágenes y trazas en S3.

El nivel de honestidad del entregable es inusualmente alto: 18 comentarios `ponytail:` declaran techo y
camino de upgrade, `docs/SECURITY.md` y la sección 9 de `docs/TECHNICAL_REPORT.md` declaran límites que
la mayoría de los proyectos esconde, y varios hallazgos de la auditoría previa (baseline invertido,
`PowerUserAccess` sin boundary, umbrales fuera de `Policy`, `threshold: 0.0` en `no_change`, actor de la
compuerta humana sin registrar) están efectivamente cerrados. Lo que sigue abierto se concentra en tres
temas: **el camino de error no está ejercitado** (los tres altos), **techos declarados con el
denominador equivocado** que truncan en silencio, y **afirmaciones de superficie que el código sostiene
sólo en parte** (landing y copy).

---

## Hallazgos

### H-01 ALTO — El driver determinista explota con `KeyError: 'policy'` ante cualquier error de herramienta

**Archivo:** `services/agent/scripted.py:29-31`, `services/agent/loop.py:294-296`

```python
        name, payload = last_tool_entry["responses"][-1]
        verdict = payload["policy"]
        branch = verdict["branch"]
```

**Análisis inicial.** El loop tiene un mecanismo deliberado para que el modelo vea el error de una
herramienta y reaccione: `loop.py:294-296` adjunta la respuesta cruda al historial.

```python
                    metrics, span = await call(tool_call.name, tool_call.args)
                    if "error" in metrics:
                        responses.append((tool_call.name, metrics))
                        continue
```

Ese payload es `{"error": "<texto>"}`, sin clave `policy`. `PolicyFollowingLLM` lo lee con acceso
directo por índice y no distingue error de veredicto.

**Análisis detallado.** Verificado ejecutando el módulo con `cv2`/`boto3` stubbeados (no hay OpenCV en
el host): con un historial cuyo último `role: tool` es
`("assess_quality", {"error": "s3://afterimage/... does not exist"})`, `generate()` levanta
`KeyError: 'policy'`. No hay guard aguas arriba: `loop.run()` no envuelve `llm.generate` (línea 267),
así que la excepción sale de `run()`.

| Camino | Qué pasa con un error de herramienta |
|---|---|
| `POST /runs/{id}/execute` → `loop.resume` | `loop.py:117-119` atrapa y llama `_close_as_failed`, que escribe `message = "KeyError: 'policy'"`. `views._hero` usa ese mensaje como **`<h1>` de la página de traza**: el operador lee la excepción de Python, no la causa. |
| `eval/run_eval.py:55` y `services/agent/demo.py:44` (llaman `loop.run()` directo) | la excepción sale sin envolver (ver H-02) |
| Gemini (`GOOGLE_API_KEY` presente) | no afecta: el modelo sí puede leer el error. La rama de recuperación del loop es, en la práctica, código muerto para el driver por defecto |

Disparadores alcanzables, no hipotéticos: objeto S3 faltante o expirado (ver H-05), un error transitorio
de S3 dentro de una herramienta, `_bbox()` rechazando una lista de longitud ≠ 4
(`services/mcp_server/server.py:10-12`), o un `cv2.error` sobre un recorte degenerado.

Descartados por estar bloqueados aguas arriba: `aligned_key=None` con rama `ALIGNED` (`inlier_ratio` es
0.0 sin homografía y `policy.py:85` corta antes), `verdict["extra"]["bbox"]` ausente (`policy.py:98-101`
y `112-114` siempre adjuntan `extra` en esas ramas) y `responses[-1]` con varias respuestas (el driver
emite siempre una sola llamada).

**Veredicto:** defecto real con causa raíz clara — el driver asume que toda respuesta de herramienta
trae veredicto, y el único mecanismo de recuperación del loop nunca se ejercita con él.

**Recomendación:** en `generate()`, si el último payload trae `error`, devolver un `submit` con una rama
terminal y el texto del error como mensaje (o una `Turn` sin llamadas para que el loop nudge-ee), de
modo que la causa raíz llegue al operador. Sumar un test que corra el loop con una herramienta que
falla: hoy no existe ninguno.

---

### H-02 ALTO — Una excepción en un escenario descarta la corrida completa de evaluación

**Archivo:** `eval/run_eval.py:181-191`

```python
    records = []
    for index, scenario in enumerate(scenarios, 1):
        record = run_scenario(scenario, out / "runs")
        records.append(record)
```

**Análisis.** No hay aislamiento por escenario ni escritura incremental: `results.json` y `summary.md` se
escriben recién al final. Una excepción en el escenario 28 tira los 27 anteriores y no deja artefacto;
como `runs/` está en `.gitignore`, tampoco queda rastro de lo que sí corrió. El disparador más probable
es justamente H-01, que además reemplaza el mensaje de la herramienta por un `KeyError` opaco.

**Veredicto:** defecto real, y el acoplamiento con H-01 es lo que lo vuelve probable: el pipeline que
produce todas las cifras publicadas es todo-o-nada.

**Recomendación:** envolver `run_scenario` en un `try/except` que registre el escenario como fallado con
la excepción y siga; escribir `results.json` de forma incremental o volcar los registros parciales en el
`except` de arriba. Un escenario caído tiene que aparecer como fila roja en el reporte, no borrarlo.

---

### H-03 ALTO — La cola de aprobación humana pierde ítems en silencio: `pending()` no pagina

**Archivo:** `services/memory/runs.py:108-124`

```python
def pending(runs_dir: str | Path = "runs") -> list[dict]:
    if _on_s3():
        # ponytail: single list page (1000 keys); paginate if the queue outgrows it
        listing = images._s3().list_objects_v2(Bucket=images.BUCKET, Prefix="runs/")
        run_ids = [
            o["Key"].split("/")[1]
            for o in listing.get("Contents", [])
            if o["Key"].endswith(f"/{PENDING}")
        ]
```

**Análisis inicial.** El techo declarado sugiere que el límite se alcanza cuando *la cola* crece. No es
así: los 1000 keys de una página de `list_objects_v2` los consumen **todos los artefactos de todas las
corridas** bajo `runs/`, no sólo los `pending.json`.

**Análisis detallado.** Medido sobre las cuatro corridas locales del repo: cada corrida terminada deja
exactamente 2 objetos (`events.json` + `state.json`).

| Corridas en el bucket | Keys bajo `runs/` | Qué ve `/queue` |
|---|---|---|
| ~100 | ~200 | todo |
| ~500 | ~1000 | el borde de la página |
| >500 | >1000 | los `pending.json` cuyo `run_id` cae después del corte **desaparecen de la cola, sin error** |

Como `run_id` es hex aleatorio (`uuid4().hex[:12]`), el orden lexicográfico de los keys es efectivamente
aleatorio: lo que se pierde es una cola aleatoria, no la más vieja. Y el ciclo de vida de S3 conserva los
objetos 180 días, así que las corridas acumulan durante ese plazo. La asimetría interna lo confirma como
descuido y no como decisión: `_run_ids()`, veinte líneas más abajo (`runs.py:128-137`), **sí** usa
`get_paginator("list_objects_v2")` para lo mismo.

**Veredicto:** defecto real en la superficie más sensible del sistema. Un hallazgo severo que la política
se negó a escribir sin humano queda invisible en `/queue`; sigue apareciendo en `/activity` con estado
`awaiting_approval`, que es la única mitigación, y nadie la busca ahí.

**Recomendación:** usar el mismo paginador de `_run_ids`. El techo real que hay que declarar (si se deja
así) no es "cuando la cola crezca" sino "cuando el bucket pase ~500 corridas".

---

### H-04 MEDIO — La galería pierde activos en silencio, y el techo declarado está mal cuantificado

**Archivo:** `services/memory/store.py:161-164`

```python
def list_assets() -> list[dict]:
    # ponytail: full table scan; fine at demo scale, add an index if assets pass a few thousand
    items = _table().scan(FilterExpression=Attr("sk").eq(META))["Items"]
```

**Análisis detallado.** Dos cosas: no se mira `LastEvaluatedKey`, y el corte de 1 MB del scan se aplica a
los ítems **leídos antes del filtro** — es decir a toda la partición, incluidos los `INSPECTION#...` con
sus métricas completas. Medido sobre los eventos de las cuatro corridas locales, un ítem de inspección de
pipeline completo pesa **1.3–1.5 KB** serializado, así que una página de 1 MB cubre ~700 ítems. Con
META + INSPECTION + BASELINE por activo con una sola inspección, la galería empieza a perder tarjetas
alrededor de los **200–350 activos**, no de "a few thousand". El mismo error afecta al contador
`_assets_in_memory` de `/queue` (`services/api/app.py:274-278`).

Los dos ponytail hermanos sí nombran su corte real (`store.py:166` "single page, paginate when one asset
passes 1 MB of history"; `runs.py:110` "1000 keys"). Éste es el único de los tres mal cuantificado. Del
lado de la documentación la categoría está declarada —`docs/ARCHITECTURE.md:147` "Asset scans, history
queries, and the approval listing do not implement full pagination", `docs/BACKEND.md:99-101`— pero
ninguna superficie da un número, y la sección 9 del informe técnico no menciona paginación.

**Veredicto:** defecto real de magnitud, no de categoría. El síntoma es el peor posible para un producto
cuya promesa es la memoria: activos que desaparecen de la galería sin ningún error.

**Recomendación:** paginar con `LastEvaluatedKey` en `list_assets` y `history`, y corregir el techo del
comentario a los ítems de la tabla (no a los activos).

---

### H-05 MEDIO — S3 expira a 180 días, DynamoDB no expira nunca: un activo queda inservible

**Archivo:** `infra/template.yaml:74-80`, `services/memory/store.py:120-148`, `services/agent/loop.py:201`

```yaml
      LifecycleConfiguration:
        Rules:
          - Id: expire-everything
            Status: Enabled
            ExpirationInDays: 180
```

**Análisis.** La regla no tiene filtro de prefijo: a los 180 días se van las imágenes (`assets/`) **y**
las trazas (`runs/`). Los ítems de DynamoDB no tienen TTL y sobreviven indefinidamente apuntando a
objetos que ya no existen. Consecuencias concretas, en orden de gravedad:

| Efecto | Mecanismo |
|---|---|
| Un activo cuyo baseline expiró queda **inservible**: toda captura nueva falla | `loop.py:201` `store.current_baseline()` devuelve el ítem con su `image_key`; `align_to_baseline` llama `images.get_image(baseline_key)` → `get_png` levanta `ValueError` → error de herramienta → `KeyError` con el driver por defecto (H-01), o 12 turnos en vano con Gemini. En ningún caso el mensaje nombra la causa |
| Links de traza muertos desde el timeline del activo | `asset.html:8` renderiza `trace_link(e.trace_id)` y `GET /traces/{id}` devuelve 404 `trace_not_found` porque `events.json` ya no está |
| Miniaturas roas en la galería y en el timeline | `/images/{key}` → 404 |

Un activo estable es el caso más expuesto: el baseline sólo se re-promueve en `auto_write` o en una
aprobación humana, así que un activo que siempre da `no_change` conserva el mismo `image_key` hasta que
expira. La retención de 180 días está declarada en cinco lugares (`docs/SECURITY.md:62`,
`docs/STACK.md:35`, `docs/TECHNICAL_REPORT.md:384`, `docs/RESPONSIBLE_USE.md:24`, `docs/index.html:1070`)
y `docs/PLAN.md:299` explica que se eligió para cubrir la ventana de evaluación; ninguna superficie
declara qué pasa después con la memoria que sobrevive.

**Veredicto:** decisión de infraestructura correcta con una consecuencia no manejada en el código.

**Recomendación:** dos arreglos independientes, ninguno excluyente. (1) Tratar el baseline ausente como
un estado del dominio: si `current_baseline()` apunta a un objeto que no está, terminar con una rama y un
mensaje que lo digan (no re-baselinear en silencio, que borraría la historia de comparación). (2) Alinear
las retenciones: TTL en los ítems de DynamoDB, o excluir `assets/` de la regla de ciclo de vida. Nótese
que subir el plazo de la regla **no** arregla nada: sólo mueve la fecha.

---

### H-06 MEDIO — Sin JavaScript la inspección se acepta y nunca arranca

**Archivo:** `services/api/app.py:202-205`, `services/ui/static/app.js:179-184`, `docs/FRONTEND.md:53,61-64`

```python
    store.put_asset(asset_id)
    capture_key = images.put_image(asset_id, uuid.uuid4().hex[:12], "capture", capture)
    started = loop.start(asset_id, capture_key, runs_dir=runs.runs_dir())
    return RedirectResponse(f"/traces/{started['run_id']}", status_code=303)
```

El arranque del loop es un `POST` separado que sólo emite el navegador:

```javascript
if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => { ... });
```

**Análisis.** Sin JS el formulario se envía igual, el activo se crea en DynamoDB, la captura se escribe en
S3 y se emite `run_started`; después nada. La página de traza muestra "inspection in progress" para
siempre y la corrida queda `unstarted` en `/activity`, donde tampoco se puede reintentar (el botón de
retry exige estado `failed`, ver H-07). `docs/FRONTEND.md:61-64` enumera qué sobrevive sin JS —
"navigation, history, approval forms, language selection, and ordinary file upload remain server
functions" — y qué no: "Sample selection, live polling, and enhanced previews require JavaScript". El
arranque de la corrida no está en esa lista y en `:53` aparece clasificado como mejora progresiva
("After the upload redirect, the trace page starts the run with a separate POST request"), cuando es la
función central. El resto del frontend sí degrada bien: verificado que `.landing-demo-ready`
(`app.css:411`) es lo que condiciona el atenuado del rail, así que sin JS el demo se ve completo.

**Veredicto:** hueco real de mejora progresiva, además mal declarado en la documentación.

**Recomendación:** un `<noscript>` en la página de traza con un formulario `POST` a `execute_url`. Tres
líneas de plantilla, y corregir la lista de `FRONTEND.md`.

---

### H-07 MEDIO — Una corrida interrumpida queda `running` para siempre y no se puede reintentar

**Archivo:** `services/agent/loop.py:110-111`, `services/memory/runs.py:163`, `services/api/app.py:231-246`

```python
    if trace.run_state(events) != trace.UNSTARTED:
        raise AlreadyStarted(run_id)
```

```python
        "retryable": status == "failed",
```

**Análisis.** Si el proceso muere sin emitir `run_finished` —el caso ya declarado en la sección 9 del
informe técnico: "A full inspection peaked at 1,891 MB of the 2,048 configured... a larger capture is an
out-of-memory kill rather than a degraded result, and Lambda answers one with a 502 and no trace"— la
corrida queda con eventos de herramienta y sin cierre. Entonces `run_state` devuelve `RUNNING`, que
bloquea `resume` con 409 `run_already_started`, y `retryable` es falso porque el estado no es `failed`,
así que `POST /runs/{id}/retry` responde 409 `run_not_failed`. La corrida es visible en `/activity` como
`running` y no hay ninguna acción disponible sobre ella. `README.md:68` afirma "A failed run remains
immutable and can be retried from recent activity"; una corrida abortada nunca llega a `failed`.

**Veredicto:** defecto real en un escenario que el propio entregable documenta como alcanzable.

**Recomendación:** darle al estado `running` sin eventos nuevos una salida: permitir `resume` (o el retry)
cuando el último evento tiene más de N minutos, y emitir en ese momento el `run_finished` fallado que
faltó. Ojo con el remedio equivocado: relajar el claim de `resume` sin el criterio de antigüedad
reintroduce la doble ejecución que el `ponytail:` de `loop.py:108` acota a propósito.

---

### H-08 MEDIO — Las cuatro muestras prometen cuatro resultados que sólo valen para el primer visitante

**Archivo:** `services/ui/views.py:50-56`, `services/ui/text.py:164-174,469-479`

```python
SAMPLE_ASSET = "demo-panel"
```

```python
    "samples_hint": "Four captures of the same demo panel, in order. Each one lands on a "
                    "different answer. Pick one, then press inspect.",
    "sample_1_label": "1 · the reference photo",
    "sample_1_note": "nothing to compare against yet, so it becomes the baseline",
```

**Análisis.** El strip escribe siempre el mismo `asset_id` fijo (`demo-panel`) y la memoria del endpoint
público es global. Las promesas valen exactamente una vez:

| Situación | Muestra 1 | Muestra 3 |
|---|---|---|
| `demo-panel` vacío (primer visitante) | `first_baseline`, como dice el copy | `human_approval` |
| `demo-panel` ya tiene baseline = muestra 1 | alineación perfecta → diff sin regiones → **`no_change`** | `human_approval` |
| alguien aprobó la muestra 3 antes | `change_confirmed`/`human_approval` | el panel fisurado **es** el baseline → `no_change` |
| stack recién desplegado y el visitante empieza por la muestra 4 | el panel ajeno se convierte en el baseline; después la muestra 1 lee `unrecognized_asset` | — |

La muestra 2 (`recapture`) es la única estable, porque la compuerta de calidad corre antes de tocar la
memoria. El límite no está declarado en ninguna superficie: `docs/SECURITY.md:13-16` declara visibilidad
y ausencia de autenticación, `docs/RESPONSIBLE_USE.md:33-34` que cualquiera puede resolver un pendiente,
pero nada dice que el estado sea *consumible*. Lo más cerca que llega es `docs/E2E.md:122-133`, que ordena
el recorrido manual precisamente porque el estado se consume ("Run O before P, and both before N") y
resuelve la colisión con "use a unique asset prefix for each walkthrough" — remedio que el visitante del
endpoint público no tiene, porque el botón escribe `demo-panel` fijo. La única pista en todo el
entregable es incidental: `README.md:66` dice "so a first visitant can drive the whole loop".

**Veredicto:** defecto real de producto, y el más caro en contexto de competencia: el jurado llega
después del autor.

**Recomendación:** sufijar el activo de las muestras por sesión (`demo-panel-<sufijo aleatorio>`, que
`ASSET_ID_PATTERN` admite) para que cada visitante recorra su propia memoria; o, si se quiere memoria
compartida a propósito, cambiar el copy de promesa por descripción ("esta captura es la referencia" en
lugar de "pasa a ser el baseline") y declararlo en `FUNCTIONAL.md`.

---

### H-09 MEDIO — El demo del landing es un camino escrito a mano, presentado como un replay

**Archivo:** `services/ui/templates/landing.html:52-65`, `services/ui/text.py:79-81,127-130`

```jinja
        {% if scenario == 1 %}
          {% set state = 'done' if step == 1 else 'skipped' %}
        {% elif scenario == 2 %}
          {% set state = 'bad' if step == 1 else 'skipped' %}
        {% elif scenario == 3 %}
          {% set state = 'warn' if step == 5 else ('skipped' if step == 4 else 'done') %}
```

**Análisis.** Los cinco estados de cada escenario y sus cuatro resultados
(`landing_scenario_N_outcome` = `first_baseline`, `recapture`, `human_approval`,
`unrecognized_asset`) son literales de plantilla y de tabla de textos. No salen de una traza, de
`eval/results/latest/` ni de una corrida: son una ilustración. El copy que los enmarca dice otra cosa —
`landing_demo_kicker` "RECONSTRUCTIBLE DECISION", `landing_demo_title` "Every answer carries the number
that triggered it", `landing_demo_hint` "Choose a capture and **replay the path** without writing
anything to memory"— y el widget no muestra un solo número, que es justamente la propiedad que el
proyecto vende (AGENTS.md: "Every agent decision must be reconstructible from a trace, including the
numeric value that triggered it").

Nada lo ata al pipeline. Los tests fijan estructura, no contenido:
`services/ui/tests/test_language.py:81-86` verifica que haya cuatro `data-landing-tab=` y que
`landing.js` no tenga `fetch(` ni `submit(`; ningún test pinea los estados del rail ni los resultados.
El único gate de las cuatro muestras contra el pipeline real es **manual**: `docs/E2E.md:129`
("Sample 1 ends `first_baseline`; sample 2 then reads `blur_variance 3.6589 < 100.0 -> recapture`").
Un cambio de umbral en `policy.py` deja el landing afirmando ramas que el sistema ya no toma, con el CI
en verde.

**Veredicto:** defecto real, mitad deriva latente y mitad sobreafirmación.

**Recomendación:** la salida barata es de copy: presentarlo como explicación ("cómo se vería el
recorrido") y sacar "replay" y "the number that triggered it" de ese bloque. La salida que sostiene la
promesa es derivar el rail de una traza comiteada de cada muestra y mostrar el número que decidió cada
paso; si se toma, el gate natural es extender `eval/tests/test_published_numbers.py`, que ya valida
`services/ui/views.py`.

---

### H-10 MEDIO — El CI nunca recalcula los números publicados

**Archivo:** `.github/workflows/ci.yml`, `eval/tests/test_published_numbers.py:36-37`

**Análisis.** El CI corre `make weights`, `make build`, `make verify-runtime`, `make lint`,
`make typecheck` y `make test`, cada uno como paso propio, sin `|| true` ni exit codes ignorados, y
`Makefile:15` propaga bien el estado. El piso de cobertura del 90% está activo y los tests de `eval/`
corren. Lo que no corre es `make eval`: el gate de números publicados compara los documentos contra el
**`results.json` comiteado**, nunca contra el código.

```python
@pytest.fixture(scope="module")
def measured():
    return json.loads(RESULTS.read_text())["summary"]
```

Es decir: cambiar un umbral en `policy.py` o una métrica en `services/perception/` y no re-correr
`make eval` deja el CI verde con cifras viejas en README, EVALUATION, TECHNICAL_REPORT, `docs/index.html`,
`video/script.tsv` y la landing. AGENTS.md lo pide a mano ("After changing a threshold or perception
metric, rerun `make eval`"), así que el gate depende de disciplina, no del CI. Vale reconocer lo que sí
cubre y creció desde la auditoría previa: el gate ahora valida también `docs/index.html` (`SITE`) y los
cuatro números de la landing en `services/ui/views.py` (`test_the_application_landing_restates_measured_figures`).

**Veredicto:** hueco real de gate, en el pipeline que produce las cifras del entregable.

**Recomendación:** un paso de CI que corra `make eval` cuando el diff toca `services/perception/`,
`services/agent/policy.py` o `eval/` y falle si el artefacto cambia. Advertencia sobre el remedio: si las
cifras no son bit-determinísticas entre el runner `ubuntu-24.04-arm` y la máquina del autor, un
`git diff --exit-code` va a parpadear; en ese caso comparar con tolerancia sobre los campos del
`summary`, no byte a byte.

---

### H-11 MEDIO — `macro()` promedia clases fantasma con soporte 0

**Archivo:** `eval/metrics.py:1-2,37-43`, `eval/run_eval.py:86`

```python
def labels(pairs) -> list[str]:
    return sorted({label for pair in pairs for label in pair})
```

```python
    return {
        metric: round(sum(row[metric] for row in report.values()) / len(report), 4)
        for metric in ("precision", "recall", "f1")
    }
```

**Análisis.** `labels()` une esperados y predichos, así que una etiqueta sólo predicha entra en
`per_class` con `support = 0`, `precision = recall = f1 = 0.0` (vía `_ratio(0, 0) → 0.0`), y `macro()` la
cuenta en el denominador como una fila de ceros. El disparador concreto está en el mismo pipeline:

```python
    branch_pairs = [(r["expected_branch"], r["branch"] or "failed") for r in records]
```

`r["branch"]` es `None` cuando el loop cierra con `finish("failed", None, ...)` (`loop.py:232`,
`loop.py:311`, `_close_as_failed`). Una sola corrida caída inyecta la clase `"failed"` con soporte 0:
con las 6 clases de rama actuales, el macro F1 pasa de `suma/6` a `suma/7`, un **−14% relativo** que es
puro artefacto de conteo, encima del efecto legítimo de la corrida perdida. En la corrida publicada las 6
clases tienen soporte ≥ 1, así que el defecto está latente — pero está en el camino que produce números
publicados, y H-01/H-02 son exactamente lo que lo despierta. `eval/tests/test_metrics.py:28` cubre el
caso inverso (etiqueta nunca predicha) y no éste.

**Veredicto:** defecto real latente en una cifra publicada.

**Recomendación:** promediar en `macro()` sólo las filas con `support > 0`. Menor del mismo archivo, sin
impacto en lo publicado (<1e-4) pero vale registrarlo: `metrics.py:32` calcula F1 a partir de
`precision` y `recall` ya redondeados, y `macro()` promedia valores redondeados.

---

### H-12 MEDIO — `candidates[0]` sin guard y sin reintento ante un 429/503

**Archivo:** `services/agent/llm.py:70`

```python
        parts = response.candidates[0].content.parts or []
        text = " ".join(part.text for part in parts if part.text) or None
```

**Análisis.** Con `candidates` vacío o `None` (filtro de seguridad, `RECITATION`, error de prompt) esto es
`IndexError`/`TypeError`; con `candidates[0].content is None` (caso conocido de `finish_reason=MAX_TOKENS`)
es `AttributeError`. El `or []` sólo cubre el caso más benigno. Por el camino de la API la excepción queda
registrada (`resume` → `_close_as_failed` marca la corrida como fallada con el mensaje), así que no es
silenciosa; en `services/agent/run.py` y `make demo --live` aborta con traceback. Tampoco hay
retry/backoff, así que un 429 o 503 transitorio mata la inspección entera.

Lo que **no** es un problema, verificado: la selección de driver es única y previa
(`loop.py:242-247`, por presencia de `GOOGLE_API_KEY`), nunca se cae al determinista a mitad de corrida.
El scripted no puede enmascarar un fallo del LLM real.

**Veredicto:** defecto real en un borde que el proveedor produce de forma habitual.

**Recomendación:** tratar la respuesta vacía como una vuelta sin llamadas (el loop ya tiene el `NUDGE`
para eso) y sumar un reintento con backoff para 429/503.

---

### H-13 MEDIO — Los dos gates de calidad no verifican lo que AGENTS.md declara

**Archivo:** `pyproject.toml:1-15`, `Makefile:24`

```toml
[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]
```

```toml
[tool.mypy]
exclude = ["/tests/"]
follow_imports = "silent"
ignore_missing_imports = true
```

**Análisis.** Dos verificaciones que pasan en verde sin verificar lo declarado:

1. **mypy.** Sin `disallow_untyped_defs` ni `check_untyped_defs`, el modo por defecto no analiza el
   cuerpo de las funciones sin anotar. Todo `services/agent/scripted.py` queda afuera (sus métodos no
   tienen anotaciones) — es decir, precisamente el archivo de H-01. Y `Makefile:24` corre
   `mypy services/`: `eval/` no se type-checkea nunca, ni `run_eval.py` ni `metrics.py` (H-02, H-11).
2. **ruff.** `E501` (line-too-long) vive en `E5`, que no está seleccionado, así que `line-length = 100`
   sólo afecta al formateador. AGENTS.md afirma "Ruff enforces import ordering and selected E, F, and I
   rules with a 100-character line limit": el límite no se enforcea. Contadas 17 líneas por encima de 100
   sólo en los archivos revisados (`services/agent/demo.py:25,35,36`, `eval/run_eval.py` ×11,
   `eval/scenarios.py:23`, `services/observability/render.py:27`, `services/agent/policy.py:29`).

**Veredicto:** defecto real de gate más una afirmación falsa en la guía del repo.

**Recomendación:** agregar `check_untyped_defs = true` y extender el comando a `eval/`; sumar `E5` al
`select` de ruff (o corregir la frase de AGENTS.md, pero el límite ya está escrito en la config).

---

### H-14 MEDIO — `urlopen` sin timeout en el primer paso del CI y del deploy

**Archivo:** `services/perception/weights.py:42`

```python
    with urllib.request.urlopen(f"{BASE_URL}/{name}") as response:
        payload = response.read()
```

**Análisis.** Sin `timeout=`, hereda el default global de socket, que es `None`: bloqueante indefinido.
`make weights` es el paso 1 de `ci.yml` y el paso 2 de `deploy.sh:31`; si el host acepta la conexión y no
responde, el job cuelga hasta el timeout de GitHub Actions (6 h) en vez de fallar en segundos, y el grupo
de concurrencia del workflow queda tomado. El resto de `_download` está bien: verifica SHA-1 antes de
escribir y aborta con `SystemExit` ante mismatch, sin degradar en silencio.

**Recomendación:** `urlopen(..., timeout=30)`.

---

### H-15 BAJO — El registro por defecto afirma que la traza está "sellada"

**Archivo:** `services/ui/text.py:261,566`, `README.md:62`

```python
    "chain_intact_plain": "the {n} steps of this run are sealed: none was edited afterwards",
```

**Análisis.** La cadena vive completa —eventos, `prev` y `hash`— dentro del mismo `events.json`: quien
pueda escribirlo reescribe todo y re-encadena, y `broken_at` sigue diciendo "intacta". El propio repo lo
declara con precisión en cinco lugares (`docs/SECURITY.md:35-39` "it does not stop anyone who can rewrite
every hash from the genesis link", más ARCHITECTURE, FUNCTIONAL, TECHNICAL_REPORT e `index.html`), lo que
hace del texto de la UI una inconsistencia interna: el registro `_tech` es literal y correcto
("sha256 chain intact over {n} events"), y el que sobreafirma es `_plain`, que es el registro por
defecto. `README.md:62` enuncia la propiedad sin calificarla y el README no tiene sección de límites
propia.

**Recomendación:** que el texto `plain` describa lo que la cadena prueba ("los {n} pasos cierran entre
sí: ninguno se editó de forma aislada") y una cláusula en `README.md:62` apuntando a SECURITY.md.

---

### H-16 BAJO — En el rail del landing, el paso que decide dice "esperando"

**Archivo:** `services/ui/templates/landing.html:64-65`, `services/ui/text.py:93-95`

```jinja
          <span class='landing-rail-state'>{{ t.landing_state_done if state == 'done' else
            (t.landing_state_waiting if state in ('warn', 'bad') else t.landing_state_skipped) }}</span>
```

**Análisis.** Sólo hay tres textos de estado (`done`, `skipped`, `waiting`) para cuatro estados de
plantilla. El paso decisivo de los escenarios 2 y 4 (calidad mala, alineación fallida) se rotula
"waiting"/"esperando" mientras los siguientes dicen "skipped"/"omitido": el lector ve que el paso que
justamente resolvió el escenario nunca terminó. En el escenario 3 (`human_approval`) "esperando" es
defendible; en los otros dos contradice el resultado que el mismo panel muestra abajo.

Segunda divergencia con el rail real, del mismo bloque: el landing pinta `recapture` como `bad`
(`landing.html:55`) mientras `views.py:97` lo clasifica `warn`, y el rail real muestra esa etapa como
`done` con su rama al lado (`test_views.py:389-392`). El mismo estado se ve rojo en la portada y ámbar
adentro.

**Recomendación:** un cuarto texto para `bad` (p. ej. "detenido"/"stopped"), usar "esperando" sólo en
`warn`, y alinear el tono de `recapture` con `_TONE` de `views.py`.

---

### H-17 BAJO — Las pestañas del demo truncan su etiqueta en todo ancho

**Archivo:** `services/ui/static/app.css:372-376`, `services/ui/templates/landing.html:26-31`

```css
.landing-scenario-tabs { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px; padding: 3px; ... }
.landing-scenario-tab { min-width: 0; padding: 8px; ... font: 500 .72rem/1.25 var(--font-body);
  text-align: left; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
```

**Análisis (aritmética de ancho, no verificado en navegador).** A 1440 px: `.wrap` tope 1120; el hero es
`minmax(0,.9fr) minmax(520px,1.1fr)` con `gap: 56px`, así que la columna del demo mide ~585 px; menos el
`padding: 24px` de `.landing-demo` quedan ~537 px para cuatro columnas con `padding: 8px` cada una →
~118 px de texto por pestaña. A 0.72 rem (~11.5 px), eso son ~13–14 caracteres para etiquetas como
"1 · the reference photo" (23) o "2 · el mismo panel, fuera de foco" (32): con `nowrap` + `ellipsis`, las
cuatro pestañas quedan cortadas en todos los anchos, y a ≤620 px con dos columnas también.

**Recomendación:** etiquetas cortas propias para las pestañas (el texto largo ya se repite dentro del
panel en `.landing-capture-label`), o permitir dos líneas quitando `white-space: nowrap`.

---

### H-18 BAJO — `ApiError.retryable` y `retry_url` nunca se usan: la rama del template es código muerto

**Archivo:** `services/api/app.py:42-48`, `services/ui/templates/error.html:3`, `services/ui/text.py:147,450`

```python
class ApiError(HTTPException):
    def __init__(self, status_code: int, detail: str, code: str,
                 retryable: bool = False, retry_url: str = ""):
```

**Análisis.** Ninguno de los `raise ApiError(...)` del módulo pasa `retryable` o `retry_url`, así que el
botón "Retry safely" / "Reintentar de forma segura" de la página de error es inalcanzable, y los tests lo
pinean como tal (`test_endpoints.py:94,408,424` afirman `"retryable": False`). Queda el campo en el
contrato JSON —documentado en BACKEND, ARCHITECTURE, FRONTEND y E2E— siempre en falso, más dos parámetros,
una rama de plantilla y dos claves de i18n sin consumidor. Es exactamente la configurabilidad
especulativa que la guía del repo rechaza.

**Recomendación:** o se cablea donde tiene sentido (el 409 `run_already_started` apuntando a
`/traces/{id}`), o se borran los dos parámetros, la rama del template y las dos claves.

---

### H-19 BAJO — `/queue` hereda el timeout del poller de la traza y anuncia una corrida que no existe

**Archivo:** `services/ui/static/app.js:186-227`, `services/ui/templates/queue.html:4`

```javascript
    if (++attempts >= cap) {
      stopClock();
      say(T.pollTimeout);
```

**Análisis.** `queue.html` declara `data-poll='5000'` y la página no pasa `run_state`, así que
`page.dataset.runState` es `undefined` y el poller nunca se detiene por estado. A los 400 intentos —unos
33 minutos de pestaña abierta— escribe en la línea de estado de la cola "the run did not answer in time —
open activity to check it", un mensaje sobre una corrida que en esa página no existe.

**Recomendación:** que el mensaje de timeout venga del bloque que se está poleando (un `data-poll-timeout`
por página) en vez de una sola clave global.

---

### H-20 BAJO — `mean_reprojection_error` se mide, se persiste y se muestra, pero ninguna rama la usa

**Archivo:** `services/perception/alignment.py:116-122,133`, `services/mcp_server/server.py:62-65`,
`services/agent/policy.py:83-88`

**Análisis.** Es la única señal disponible de una homografía degenerada y ninguna rama de `policy.py` la
compara con nada. El riesgo que cubriría está en el mismo archivo: `cv2.perspectiveTransform(corners,
homography).astype(np.int32)` alimenta `fillConvexPoly` sin validar la forma del cuadrilátero, así que una
homografía torcida que igual pase el gate de `inlier_ratio` (≥ 0.90 neural, ≥ 0.30 classic) puede producir
esquinas fuera del rango de int32 (cast indefinido en numpy) o un cuadrilátero auto-intersectado; el
`valid_mask` resultante enmascara la región equivocada y el diff puede reportar `NO_CHANGE` sobre un
defecto real. Probabilidad baja. `inlier_ratio` sí está protegido de división por cero: la línea 132 sólo
corre con `len(matches) >= MIN_MATCHES = 4`.

**Recomendación:** un umbral de `mean_reprojection_error` en `Policy` que derive a `retry_classic` /
`unrecognized_asset`, que es además donde AGENTS.md pide que vivan los umbrales.

---

### H-21 BAJO — `backfill.py` valida a medias justo sobre la población que existe para reparar

**Archivo:** `services/memory/backfill.py:10,21,30`

**Análisis.** La línea 10 usa `max(inspections, key=lambda item: item.get("captured_at", ""))`, tolerando
la ausencia del atributo; las líneas 21 y 30 acceden `item["captured_at"]` sin guard. `store.py:107`
siempre lo escribe hoy, así que sólo se dispara con ítems de un esquema viejo — que es exactamente la
población que este script existe para rellenar.

**Recomendación:** una sola forma de leer el campo; si falta, saltar el ítem informándolo.

---

### H-22 BAJO — Higiene de build

**Archivo:** `Makefile:11-12,17-18`, `requirements.txt:4-7`

- `build:` no declara `weights` como prerequisito, pero `Dockerfile:17` hace `COPY models/ /opt/models/`:
  en un clone limpio falla con un error de COPY que no dice que falta `make weights`. `dev`, `test`,
  `demo` y `eval` sí lo declaran.
- `verify-runtime` corre sin `--no-deps` (levanta LocalStack) y, a diferencia de `test`/`demo`/`eval`, no
  hace `$(COMPOSE) down`: deja el contenedor corriendo entre pasos del CI.
- `pytest`, `pytest-cov`, `mypy` y `ruff` se instalan en la misma imagen que se despliega como Lambda
  (un solo `Dockerfile`, sin stage de build): tamaño de imagen y superficie, con el arranque en frío como
  costo visible.

---

### H-23 BAJO — Dos directorios vacíos versionados que ninguna documentación menciona

**Archivo:** `observability/.gitkeep`, `web/.gitkeep`

**Análisis.** Ambos están versionados desde los primeros commits y quedaron sin uso: la observabilidad
real vive en `services/observability/` y el frontend en `services/ui/`. La sección "Project Structure" de
AGENTS.md no los nombra. Para un repo que es parte del entregable, sugieren un layout abandonado.

**Recomendación:** borrarlos.

---

### H-24 MEDIO — Jinja sin `StrictUndefined`: una clave de copy renombrada deja media portada en blanco

**Archivo:** `services/ui/views.py:37-42`

```python
_env = Environment(
    loader=FileSystemLoader(HERE / "templates"),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)
```

**Análisis.** Con el `Undefined` por defecto, `{{ t.landing_hero_title }}` con la clave renombrada
renderiza cadena vacía, sin error. Y no hay red debajo: ningún test asserta contenido del landing —
`test_views.py:302` verifica un solo `<main>` y un solo `<h1>`, `test_language.py:81-87` cuenta cuatro
`data-landing-tab=` y que `landing.js` no traiga `fetch(`/`submit(`, `test_endpoints.py:328-334` que
`GET /` dé 200. El chequeo de paridad de claves (`test_language.py:8-12`) tampoco lo agarra, porque un
renombre simétrico en los dos idiomas sigue siendo paritario. Resultado: el hero, las cuatro tarjetas de
métricas o los outcomes del demo pueden quedar vacíos en la página pública con el CI en verde. Las
únicas dos claves que sí reventarían son las de lista (`landing_stack_items`, `landing_limits_items`,
`landing.html:133,137`), porque se iteran.

**Veredicto:** falta un guard barato en el punto donde toda la UI pasa.

**Recomendación:** `undefined=StrictUndefined` en el `Environment`. Es seguro hoy: la verificación
mecánica de esta review resolvió `strings()` en las cuatro combinaciones de idioma y registro y ninguna
de las 168 claves que usan las plantillas y `views.py` falta, así que activarlo no rompe nada y convierte
cada futura clave ausente en un error de render en vez de un hueco silencioso.

---

### H-25 BAJO — `_verdict_from_trace` cachea el `None` sin invalidación

**Archivo:** `services/ui/views.py:291-305`

```python
@lru_cache(maxsize=128)
def _verdict_from_trace(run_dir: str) -> dict | None:
```

**Análisis.** El `ponytail:` de arriba justifica el cache con que "a finished trace never changes", que es
cierto, pero el cache también guarda el `None` de una traza que todavía no tiene decisión de severidad:
ese contenedor Lambda sirve esa fila sin umbral para siempre. El alcance real es chico —las entradas de
`/queue` traen el verdict en `pending.json` y las inspecciones lo traen persistido desde
`put_inspection`—, así que el caso vivo es el de ítems de esquema viejo o del camino `first_baseline`,
donde no hay severidad que mostrar. Ningún test cubre la transición: `test_views.py:137` y `:152` tocan
los dos resultados pero nunca el mismo `run_dir` dos veces.

**Recomendación:** no cachear el `None` (devolver temprano sin memorizar cuando no hay decisión de
severidad).

---

## Resumen de Veredicto

| Severidad | Cantidad | Items |
|-----------|----------|-------|
| Alto      | 3        | H-01 `KeyError: 'policy'` ante cualquier error de herramienta, H-02 una excepción descarta la corrida entera de eval, H-03 la cola de aprobación pierde ítems sin paginar |
| Medio     | 12       | H-04 galería truncada en silencio, H-05 S3 expira y DynamoDB no, H-06 sin JS la corrida no arranca, H-07 corrida interrumpida irrecuperable, H-08 las muestras sólo valen para el primer visitante, H-09 el demo del landing es ilustración presentada como replay, H-10 el CI no recalcula los números publicados, H-11 macro con clases fantasma, H-12 `candidates[0]` sin guard, H-13 mypy y ruff no verifican lo declarado, H-14 descarga de pesos sin timeout, H-24 Jinja sin `StrictUndefined` |
| Bajo      | 10       | H-15 copy "sellado", H-16 el paso decisivo dice "esperando", H-17 pestañas truncadas, H-18 `retryable` muerto, H-19 timeout de poller en `/queue`, H-20 error de reproyección sin usar, H-21 `backfill` sin guard, H-22 higiene de build, H-23 directorios vacíos, H-25 `_verdict_from_trace` cachea `None` |

**Recomendación general.** No hay bloqueantes. Los tres altos son un solo tema —el camino de error del
loop no está ejercitado— y se cierran con un cambio chico en `scripted.py`, un `try/except` por escenario
en `run_eval.py` y el paginador que ya existe veinte líneas más abajo en `runs.py`. El grupo más valioso
después de eso es el de los techos: H-04 y H-03 truncan en silencio con un denominador distinto al
declarado, y H-05 le pone fecha de vencimiento a la promesa central del producto. De los medios de
superficie, H-08 y H-09 son los que un jurado ve primero.

Vale decir qué se revisó y salió limpio: `services/perception/quality.py`,
`services/observability/render.py`, `services/agent/run.py`, `services/agent/demo.py`,
`eval/scenarios.py`, `deploy.sh` (incluido el manejo de la API key por `mktemp` + `trap`, sin fugas por
argv), `docker-compose.yml`, `Dockerfile` y `.github/workflows/deploy.yml`; la paridad de las 229 claves
de i18n en los dos idiomas y los dos registros, verificada ejecutando `strings()` para las cuatro
combinaciones; y el escape de plantillas, con autoescape activo y `Markup` usado sólo sobre literales
propios.

---

## Verificaciones ejecutadas

- **H-01 reproducido.** Sin OpenCV en el host, `services.agent.scripted` se importó con `cv2`, `boto3`,
  `boto3.dynamodb.conditions`, `botocore` y `numpy` stubbeados vía `PYTHONPATH`; con un historial cuyo
  último `role: tool` es `("assess_quality", {"error": ...})`, `generate()` levanta `KeyError: 'policy'`.
- **i18n.** `services.ui.text` se importó con un `markupsafe.Markup = str` falso y se comparó el conjunto
  de claves resueltas por `strings(lang, register)` en las cuatro combinaciones contra las claves que
  usan las plantillas y `views.py`: 229 claves, simetría exacta EN/ES, ningún faltante por registro.
- **H-04, H-03.** Tamaño de un ítem de inspección medido sobre los `events.json` de las cuatro corridas
  locales (1.3–1.5 KB en pipeline completo) y conteo de objetos por corrida (2: `events.json` +
  `state.json`).
- **Cifra publicada de localización, descartada como hallazgo.** `mean_iou 0.7875` se calcula sobre 14 de
  los 15 escenarios con lesión inyectada. El excluido es `hotspot-real-plain`, cuya rama es `recapture`:
  la compuerta de calidad rechazó la captura y el localizador nunca corrió, así que contarlo como IoU 0
  le imputaría al localizador una decisión de otra etapa. El denominador está declarado en las tres
  superficies que publican el número (`docs/EVALUATION.md:83`, `eval/results/latest/summary.md:32`,
  `README.md:79`). No es un hallazgo.

## Obstáculos encontrados

- No hay OpenCV ni `markupsafe` en el host, así que casi nada de `services/` importa tal cual. Las dos
  verificaciones ejecutadas se hicieron con módulos falsos inyectados por `PYTHONPATH` desde el
  scratchpad, sin tocar el repo.
- `rtk proxy` fue necesario para leer el CSS y los `sed` puntuales; un `grep -r` sobre la raíz del repo se
  cuelga contra los binarios del dataset (usar `git grep`).
