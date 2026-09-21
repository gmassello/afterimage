# Review de proyecto — afterimage

**Archivos revisados:** 55 de 156 versionados

Alcance: los 24 módulos no-test de `services/`, los 4 de `eval/`, las 9 plantillas Jinja, `app.js` y
`landing.js`, y la capa de build y despliegue (`Dockerfile`, `docker-compose.yml`, `Makefile`,
`deploy.sh`, `infra/template.yaml`, `pyproject.toml`, `.github/workflows/ci.yml`). Quedaron fuera
`video/` (utilidades de producción del demo), `docs/index.html` (landing estática de 1.257 líneas),
las 18 fotografías del dataset y los archivos de test, que se consultaron como evidencia pero no se
auditaron como código propio.

---

## Resumen

**Veredicto: tiene bloqueantes.** 1 crítico, 2 altos, 5 medios, 6 bajos.

afterimage es un agente de inspección visual con memoria longitudinal: una FastAPI `arm64` en Lambda
detrás de una Function URL sirve la UI y corre el loop del agente dentro del request; cinco tools de
percepción se exponen por MCP stdio; `policy.evaluate()` decide toda rama en código y graba el número
que la disparó; la memoria vive en una tabla DynamoDB más S3.

El diseño es sólido y las limitaciones aceptadas están declaradas con honestidad poco común: 21
comentarios `ponytail:` nombran techo y camino de mejora, y `docs/SECURITY.md` admite explícitamente
que la cadena de hash "is a chain, not a signature". Los hallazgos de abajo son, casi todos,
distancias entre lo que una garantía dice cubrir y lo que realmente cubre.

Dos temas concentran el peso. El primero es que un cache de proceso que nunca se invalida **trunca el
registro de auditoría en el flujo feliz del producto**, y el verificador de integridad que la UI
publica declara íntegro el resultado. El segundo es que **los guardianes de las cifras publicadas
tienen agujeros por el lado del denominador**: nueve de catorce regresiones de localización pasarían
el gate anti-drift sin ruido, y dos de ellas harían *subir* la métrica publicada.

---

## Hallazgos

### H-01 CRÍTICO — El cache de `append` trunca `events.json` entre contenedores, y la cadena de hash declara el resultado íntegro

**Archivo:** `services/memory/runs.py:19-101`, `services/observability/trace.py:61-76`

```python
# ponytail: unbounded per-process cache of append targets; entries are small JSON arrays
_append_cache: dict[tuple[str, str], list] = {}

def append(run_dir: Path, name: str, item) -> None:
    cache_key = (str(run_dir), name)
    items = _append_cache.get(cache_key)
    if items is None:
        items = _append_cache[cache_key] = read(run_dir, name) or []
    items.append(item)
    write(run_dir, name, items)          # reescribe el archivo ENTERO desde la copia en memoria

def last(run_dir: Path, name: str) -> Any:
    items = _append_cache.get((str(run_dir), name))
    if items is None:
        items = read(run_dir, name) or []
    return items[-1] if items else None   # trace.emit encadena `prev` desde acá
```

**Análisis inicial:** el comentario `ponytail:` declara como techo únicamente que el cache es
*unbounded* — un problema de **tamaño**. El defecto real es otro: el cache **nunca se invalida**.
`append()` lee de S3 una sola vez por clave y a partir de ahí la copia en memoria es la fuente de
verdad, y cada emisión reescribe el objeto completo desde ella. `last()`, que `trace.emit` usa para
encadenar el hash `prev`, también devuelve la copia en memoria.

En Lambda eso no es teórico: `AFTERIMAGE_RUNS_S3` está en `'1'` (`infra/template.yaml:30`), el
entorno de ejecución sobrevive entre invocaciones, hay un warmer cada 5 minutos
(`template.yaml:85-96`) y la cuota de la cuenta permite hasta 10 contenedores calientes rotando
requests. La clave del cache es `(str(run_dir), name)` y **todas** las rutas construyen el mismo
string `runs/{run_id}`: `loop.py:144`, `app.py:247`, `app.py:319`. Colisionan perfectamente.

**Análisis detallado:** reproducido en el host contra el código real de `trace.emit`, simulando dos
contenedores con el cache como única diferencia:

```
A escribio: ['run_started', 'run_finished']
B escribio: ['run_started', 'run_finished', 'decision'] | cadena rota en: None
tras A de nuevo: ['run_started', 'run_finished', 'run_finished']
evento de aprobacion presente: False
broken_at: None de 3 eventos
```

El evento de la decisión humana desaparece y **`broken_at` sigue devolviendo `None`**: como el
contenedor obsoleto reconstruye el encadenamiento entero desde su copia, el archivo truncado es
internamente consistente. `GET /traces/{id}` responde `{"verified": true}` (`app.py:353-355`) y la UI
imprime `chain_intact` (`views.py:735-739`) sobre un registro al que le falta justamente el evento
que se auditaría.

La secuencia más grave no requiere ninguna carrera: **es el flujo feliz del producto**.

| Paso | Endpoint | Contenedor | Efecto |
|---|---|---|---|
| 1 | `POST /inspections` (`app.py:213`) | A | `loop.start` emite `run_started`; A cachea `["run_started"]` |
| 2 | `POST /runs/X/execute` (`app.py:222`) | B | cache miss, lee de S3, corre el loop entero, deja N eventos + `state.json` + `pending.json` |
| 3 | `POST /queue/X/approve` (`app.py:313`) | A | `hitl.resolve` lee `pending.json` fresco (no cachea) y commitea bien a DynamoDB; después `trace.emit` (`hitl.py:58`) encadena desde el `run_started` viejo y **reescribe `events.json` con 2 eventos** |

El daño no queda contenido en la traza. Tras el paso 3, `events.json` ya no tiene `run_finished`, así
que `runs.stale()` (`runs.py:133-138`) vuelve a marcar la corrida como `retryable` (`runs.py:164`) y
`POST /runs/X/retry` la cierra como fallida **aunque ya fue aprobada y ya movió el baseline en
DynamoDB**. La divergencia entre la traza y la memoria queda permanente.

Hay una segunda ruta, idéntica en mecanismo: `/inspections` en A, `/execute` en B que muere por
timeout, y quince minutos después `/runs/X/retry` en A, cuyo `loop.close_as_failed`
(`app.py:256-258`) trunca `events.json` a dos eventos — borrando exactamente el registro que uno
querría leer para saber por qué se interrumpió.

Lo declarado en el repo no cubre esto. El `ponytail:` de `loop.py:108-109` y
`docs/ARCHITECTURE.md:141` cubren el **claim** no atómico, no la corrupción del registro; el
`ponytail:` de `trace.py:62-63` admite que un truncado al final no se detecta, pero lo atribuye a la
falta de un head firmado, no a una reescritura desde memoria obsoleta.

**Veredicto:** el sistema publica una garantía de integridad verificable y su propio cache la vacía de
contenido en la ruta más común. Que el commit a DynamoDB sea correcto agrava el cuadro en vez de
aliviarlo: la decisión humana ocurrió y movió el baseline, pero el único registro que la prueba
desapareció sin dejar rastro detectable. Para un proyecto cuya tesis es "toda decisión del agente es
reconstruible desde una traza", este es el defecto que más contradice la propuesta.

**Recomendación:** que `append()` deje de ser autoritativo sobre el contenido remoto. La opción de
menor diff es releer siempre en modo S3 y usar el cache solo cuando `_on_s3()` es falso, aceptando el
GET extra por emisión. Si el costo importa, `write_once`/`IfNoneMatch` ya existe en el módulo
(`runs.py:56-70`): sirve de base para un append condicional por `ETag` que reintente ante conflicto.
En cualquier caso, corregir el `ponytail:` de `runs.py:19` para que nombre la coherencia y no el
tamaño — hoy declara el techo equivocado y eso fue lo que dejó pasar el defecto.

---

### H-02 ALTO — `/activity` lee todas las corridas del bucket en cada request, y `/queue` repite el listado completo cada 5 segundos

**Archivo:** `services/memory/runs.py:111-180`, `services/api/app.py:157-163`, `services/ui/templates/queue.html:4`

```python
def recent(root, limit: int = 50, q: str = "", status: str = "") -> list[dict]:
    items = [item for run_id in _run_ids(root) if (item := _summary(root, run_id))]
    ...
    return sorted(items, key=lambda item: item["updated_at"], reverse=True)[:limit]
```

**Análisis inicial:** el `limit=50` se aplica en la última línea, después de haber materializado
todas las corridas. `_run_ids` pagina el prefijo `runs/` completo sin `MaxKeys` ni corte temprano, y
`_summary` hace dos lecturas por corrida (`read(run_dir, EVENTS)` y `read(run_dir, STATE)`), que en
modo S3 son dos `GetObject` — `read()` no consulta `_append_cache`, siempre va a la red.

**Análisis detallado:** una corrida típica deja 2 objetos bajo `runs/{run_id}/` (`events.json` y
`state.json`; `pending.json` se borra al resolver en `hitl.py:62`). Con 500 corridas acumuladas, un
solo `GET /activity` cuesta ~2 páginas de `ListObjectsV2` más **1000 `GetObject` secuenciales**
dentro del request HTTP. Los `state.json` inexistentes de las corridas en curso cuestan un round trip
igual: se descubren por excepción `NoSuchKey` (`runs.py:40-41`). No hay paginación en el endpoint, ni
cursor, ni cache: el único `lru_cache` del API es `_assets_in_memory` (`app.py:288-292`) y cuenta
ítems de DynamoDB para `/queue`, no corridas.

La acumulación es el régimen normal, no un caso extremo: el lifecycle del bucket
(`template.yaml:77-83`) expira todo a los 180 días y no hay ningún job de limpieza ni TTL más corto
para artefactos de corrida. El lifecycle acota el crecimiento a seis meses de tráfico; no lo hace
barato.

`/queue` comparte el listado completo del prefijo (`runs.pending` → `_run_ids`) pero solo lee los
pendientes, que en régimen normal son 0-3. El agravante está en la frecuencia: `queue.html:4` declara
`data-poll='5000'`, así que **cada pestaña abierta en la cola dispara un listado completo de `runs/`
cada 5 segundos**, indefinidamente. El `ponytail:` de `app.py:288-289` anticipó justamente este
patrón para el contador de DynamoDB y lo memoizó por minuto; el listado de S3, que es el más caro de
los dos, quedó sin esa protección.

**Veredicto:** es el crecimiento no acotado más caro del sistema y el único de los grandes que ningún
`ponytail:` ni documento declara. Con 500 corridas la página de actividad suma del orden de 10-20
segundos de latencia solo en round trips a S3, y escala lineal con el historial.

**Recomendación:** dado que las claves de S3 bajo `runs/` son ordenables y el `run_id` no codifica
tiempo, lo más barato es cortar antes de leer: ordenar los keys que devuelve el paginador por
`LastModified` (que `list_objects_v2` ya devuelve, sin costo extra) y hacer `_summary` solo sobre los
primeros `limit`. Eso deja `/activity` en ~2 LIST + 100 GET constantes. Los filtros `q` y `status`
seguirían siendo post-lectura sobre esa ventana, que es lo que ya son hoy. Para `/queue`, memoizar el
listado por minuto como se hizo con `_assets_in_memory` alcanza; el poll de 5 s es de la UI y no
necesita precisión de segundo.

---

### H-03 ALTO — El gate anti-drift no vigila el denominador de la localización: 9 de 14 regresiones pasan en silencio, y 2 mejoran la métrica publicada

**Archivo:** `eval/compare_results.py:5-20`, `eval/tests/test_published_numbers.py`

```python
EXACT = ("scenarios", "real", "synthetic", "passed")
TOLERANCE = 0.01

def figures(summary: dict) -> dict:
    return {
        "branch.accuracy": ..., "branch.macro.f1": ...,
        "defect.accuracy": ..., "defect.macro.f1": ...,
        "localisation.mean_iou": summary["localisation"]["mean_iou"],
    }
```

**Análisis inicial:** `AGENTS.md` designa a `test_published_numbers.py` y `compare_results.py` como
las compuertas obligatorias que impiden que las cifras publicadas se despeguen de una corrida fresca.
De `localisation` solo vigilan `mean_iou`. Ni `measured` ni `at_least_half` aparecen en `EXACT`, ni
en `figures()`, ni en ningún test — y los tres números se publican juntos, en la misma frase, en
cuatro archivos del entregable.

**Análisis detallado:** el artefacto comiteado trae `localisation = {"measured": 14,
"mean_iou": 0.7875, "at_least_half": 12}` sobre 29 escenarios. El denominador está publicado en:

- `eval/results/latest/summary.md:32` — "Mean IoU **0.7875** over 14 scenarios where a region was both injected and detected; 12 of them at IoU ≥ 0.5."
- `docs/EVALUATION.md:83-84`, `docs/TECHNICAL_REPORT.md:467`, `README.md:79` — las mismas dos cifras.

Barrido completo sobre los 14 IoU reales: si un escenario dejara de localizar (su `iou` pasa a
`null`), el nuevo `mean_iou` se mueve así.

| Escenario que deja de localizar | nuevo `mean_iou` | delta | ¿lo atrapa el gate? |
|---|---:|---:|:--|
| delamination-real-packed | 0.7865 | 0.0010 | **no** |
| crack-real-closeup | 0.7863 | 0.0012 | **no** |
| hotspot-real-cleaning | 0.7898 | 0.0023 | **no** |
| hotspot-real-ogiinuur | 0.7898 | 0.0023 | **no** |
| delamination-real-jetion | 0.7840 | 0.0035 | **no** |
| delamination-real-bifacial | 0.7840 | 0.0035 | **no** |
| hotspot-synthetic | 0.7825 | 0.0050 | **no** |
| faint-spot-real-hannover-roof | 0.7926 | 0.0051 | **no** |
| delamination-synthetic | 0.7790 | 0.0085 | **no** |
| crack-real-israel-center | 0.7758 | 0.0117 | sí |
| faint-spot-synthetic | 0.7754 | 0.0121 | sí |
| crack-synthetic | 0.7739 | 0.0136 | sí |
| faint-spot-real-et-solar | 0.8124 | 0.0249 | sí, pero **sube** el mean |
| crack-real-tororo | 0.8131 | 0.0256 | sí, pero **sube** el mean |

Nueve de catorce quedan por debajo de `TOLERANCE = 0.01`. Y los dos casos de mayor delta son
precisamente los dos únicos escenarios con IoU bajo 0.5 (`0.4642` y `0.4541`): al dejar de
localizarse, **suben** el promedio. Es decir, la regresión se presenta como mejora. Los dos números
que sí delatarían cualquiera de los catorce casos — `measured` bajando de 14 a 13 y `at_least_half`
quedándose quieto mientras el promedio sube — son exactamente los dos que ningún guardián mira.

En el mismo barrido aparecieron otras cifras publicadas sin cobertura, menores pero del mismo tipo:
`README.md:80` desglosa los aprobados en "14 real-photograph and 10 synthetic", un corte que
`summarise()` no calcula ni guarda; `README.md:52` publica `inlier_ratio` 0.997 contra 0.409 sin
respaldo en `results.json`; y `test_the_video_script_only_speaks_measured_figures` valida los
decimales del guion con un `substring in` sobre el JSON crudo, que acepta un `0.8621` atribuido a la
métrica equivocada.

**Veredicto:** el gate cumple con la letra de `AGENTS.md` y no con su intención. Protege el numerador
y deja libre el denominador, que se publica con el mismo énfasis y en la misma oración.

**Recomendación:** agregar `localisation.measured` y `localisation.at_least_half` a `EXACT` en
`compare_results.py` — son enteros, comparación exacta, y el cambio es de una línea. Con eso los
catorce casos del barrido pasan a fallar el gate. Sumarlos también a la aserción de
`test_published_numbers.py` que hoy cubre `mean_iou`, para que la prosa de los cuatro deliverables no
pueda quedar desfasada del artefacto.

---

### H-04 MEDIO — El generador del dataset de evaluación vive bajo `tests/`, y por eso los tres gates de calidad lo ignoran

**Archivo:** `services/perception/tests/panels.py`, `eval/scenarios.py:6`, `services/agent/demo.py:13-20`, `pyproject.toml`

```python
# eval/scenarios.py
from services.perception.tests import panels

# services/agent/demo.py
from services.perception.tests.panels import (blurred, foreign_panel, shifted, solar_panel, ...)
```

**Análisis inicial:** `panels.py` (118 líneas) no es un helper de tests: es la dependencia de runtime
que materializa los 11 escenarios sintéticos de `make eval` y las cuatro ramas de `make demo`. Vive
bajo `services/perception/tests/`, y esa ubicación lo excluye de los tres controles que el repo
aplica a su código:

- cobertura — `pyproject.toml` `[tool.coverage.run] omit = ["*/tests/*"]`, así que no entra en el piso del 90 %;
- tipos — `[tool.mypy] exclude = ["/tests/"]`, así que `make typecheck` no lo mira;
- ubicación — `AGENTS.md` dice "Evaluation code, scenarios, datasets, and published results belong in `eval/`".

**Veredicto:** un bug en `panels.py` altera las cifras publicadas de la evaluación sin que ninguno de
los gates que existen para proteger esas cifras lo detecte. `video/make_demo_images.py` y el ejemplo
de `docs/E2E.md:62` importan de la misma ruta, así que el acoplamiento ya se propagó a tres
consumidores fuera de los tests.

**Recomendación:** mover el módulo a `eval/panels.py` y dejar en `services/perception/tests/` solo el
import que lo reexporte, para no tocar las ocho suites que hoy lo consumen. Con eso queda dentro de
`ruff`/`mypy` (que ya corren sobre `eval/`) y alineado con lo que `AGENTS.md` pide.

---

### H-05 MEDIO — La UI no distingue un error HTTP del arranque de una corrida, y el mensaje que existe para eso es inalcanzable

**Archivo:** `services/ui/static/app.js:179-184`, `services/api/app.py:217-229`

```js
if (page.dataset.runState === 'unstarted' && page.dataset.executeUrl) {
  fetch(page.dataset.executeUrl, { method: 'POST' }).catch(() => {
    stopClock();
    say(T.runStartFailed);
  });
}
```

**Análisis inicial:** `fetch` solo rechaza ante un fallo de red; una respuesta 4xx/5xx resuelve
normalmente y el `.catch` no corre. No hay chequeo de `res.ok`.

**Análisis detallado:** `execute_run` tiene un camino de 500 real y no cubierto por
`close_as_failed`: el `try` de `app.py:221-226` solo captura `FileNotFoundError` y `AlreadyStarted`,
y `loop.resume` empieza leyendo `events.json` de S3 *antes* de su propio `try` (`loop.py:104-112`).
Un error de S3 que no sea `NoSuchKey` — throttling, timeout — propaga al handler global, devuelve 500
y deja la corrida en `unstarted` sin ningún evento nuevo.

Del lado del navegador no pasa nada visible. El disparo del `fetch` ocurre una sola vez al cargar, y
el poller reemplaza el bloque pero no lo reintenta. El usuario ve el cronómetro corriendo hasta
agotar `cap = 400` intentos (`app.js:188`) a `data-poll='1500'` (`trace.html:4`): **10 minutos de
spinner** antes de que aparezca `js_poll_timeout`. `T.runStartFailed` / `js_run_start_failed` está
traducido a los dos idiomas (`text.py:314` y `:634`) y es, en la práctica, código muerto para el caso
más probable.

**Veredicto:** el proyecto ya escribió el mensaje correcto y lo dejó detrás de la única condición que
casi nunca se cumple. El costo para el operador son diez minutos mirando un reloj que avanza sobre
una corrida que nunca arrancó.

**Recomendación:** dos líneas — `const res = await fetch(...)` y `if (!res.ok) { stopClock();
say(T.runStartFailed); }`, conservando el `catch` para el fallo de red. Vale excluir el 409
(`run_already_started`), que no es un error: significa que otro cliente ya la arrancó y el polling va
a ver el resultado.

---

### H-06 MEDIO — Dos aprobaciones concurrentes no están protegidas, y `write_once` ya existe en el módulo

**Archivo:** `services/agent/hitl.py:36-62`, `services/api/app.py:313-325`

**Análisis inicial:** `hitl.resolve` lee `pending.json`, commitea y recién al final lo borra
(`hitl.py:62`). Entre la lectura y el borrado no hay ninguna condición.

**Análisis detallado:** el caso secuencial está cubierto: un segundo `approve`/`reject` posterior
encuentra el pending ya borrado y recibe 404 `approval_not_found`. El concurrente no: si dos requests
leen `pending.json` antes de que el primero lo borre, ambos ejecutan `hitl.commit` — doble
`put_inspection` y doble `promote_baseline` — y ambos emiten su propio `decision`. Las escrituras a
DynamoDB son idempotentes porque comparten `sk`, así que el daño en la memoria es nulo; el daño está
en la traza, donde queda registrada la decisión del que escriba último y, si los dos contenedores
difieren, el truncado de H-01 decide cuál sobrevive.

Lo que lo vuelve accionable es que el remedio ya está escrito en el mismo paquete: `runs.write_once`
(`runs.py:56-70`) implementa exactamente esta exclusión con `IfNoneMatch="*"` en S3 y `os.link` en
local, y hoy se usa para un solo caso — el marcador `retry.json` de `app.py:263-267`.

**Veredicto:** ventana pequeña y consecuencia acotada, pero es la compuerta humana del sistema: el
único punto donde un operador autoriza que una inspección mueva el baseline. Merece la misma
exclusión que ya se le dio al retry.

**Recomendación:** claimear la resolución con `write_once` sobre un marcador antes de commitear, y
devolver 409 cuando el claim ya existe. Reusa el mecanismo tal cual está.

---

### H-07 MEDIO — Los pesos neuronales se descargan de la rama `main` de un repositorio personal de terceros

**Archivo:** `services/perception/weights.py:7-12`, `Makefile:5-6,14`

```python
WEIGHTS = {ALIKED_FILE: "41faa7bf...", LIGHTGLUE_FILE: "02723aa5..."}
BASE_URL = "https://raw.githubusercontent.com/YangGuanyuhan/lightglue_opencv_project/main/model"
```

**Análisis inicial:** la URL apunta a una rama móvil (`main`) de un repositorio personal, no a un tag,
un release ni un SHA de commit. La verificación SHA-1 está bien puesta y hace que un cambio upstream
**falle** en vez de envenenar el build, que es el comportamiento correcto; el riesgo que queda no es
de integridad sino de disponibilidad.

**Análisis detallado:** las dos URLs responden 200 hoy (6.438.045 y 45.837.864 bytes, que coinciden
con las copias de `models/`). El repositorio upstream es de un usuario individual, tiene **0
estrellas, 0 forks, 0 watchers, sin descripción y sin licencia declarada** (la API devuelve
`"license": null` y `/license` responde 404), con último push hace tres meses. No es un fork ni está
archivado: es un proyecto personal que su dueño puede borrar, volver privado o reescribir sin aviso.

No hay red de contención en ningún nivel:

- `models/` está en `.gitignore:6`, así que los 52 MB **no están versionados** — no hay copia local que sobreviva al borrado;
- ninguno de los dos workflows usa `actions/cache`, así que cada corrida de CI los baja de nuevo desde ese repositorio;
- `weights.py:42` llama `urllib.request.urlopen` sin `try`, y `BASE_URL` es una sola URL sin fallback.

El alcance del fallo es total, no gradual. `make weights` es prerrequisito de `build`, `test`, `dev`,
`demo` y `eval` (`Makefile:8,11,14,26,29`), así que un 404 rompe: el job `test` del CI en su paso 2,
el job `eval` en paralelo por el prerrequisito de `Makefile:29`, y el deploy manual, que corre
`make test` y además invoca `make -C "$ROOT" weights` en `deploy.sh:31`. El fallback ORB que existe en
runtime (`weights.py:27`, `alignment.py:13-14`) no ayuda: el gate está en el build, antes de que
cualquier código corra.

**Veredicto:** para un entregable de competencia que un jurado debe poder reproducir meses después,
es la dependencia más frágil del proyecto. Y es el único de los huecos grandes que el repo no declara
bajo su propia convención: hay 21 comentarios `ponytail:` en el código, cuatro de ellos en
`services/perception/`, y `weights.py` no tiene ninguno; la sección "Limitations" de
`docs/TECHNICAL_REPORT.md:520-547` enumera once limitaciones, todas de producto o medición, y ninguna
de cadena de suministro. Peor, `docs/TECHNICAL_REPORT.md:379` cuenta el sha1 de `make weights` como
evidencia de reproducibilidad sin mencionar que la fuente es una rama móvil ajena.

**Recomendación:** el propio repo ya nombró la mitigación y no la usó. `NOTICE:14-16` dice:

> OpenCV pins the same two files and the same two sha1 digests for its own DNN test data, in
> `opencv_extra/testdata/dnn/download_models.py` on the 5.x branch.

Es decir, existe una segunda fuente de los mismos bytes, respaldada por el proyecto OpenCV, y los
sha1 que ya están en `weights.py:8-9` permiten intercambiarlas sin riesgo. Convertir `BASE_URL` en una
tupla de orígenes con esa como primaria, cayendo al repositorio personal solo si falla, resuelve el
problema con pocas líneas y sin infraestructura propia. Como mínimo, fijar la URL actual a un SHA de
commit en vez de `main` y dejar un `ponytail:` junto a la constante que nombre el techo.

Vale destacar, en la otra dirección, que la **atribución** está impecable: `NOTICE:11-16` ya declara
que el repositorio upstream "declares no license of its own" y acredita las licencias de los modelos
originales. Se verificó contra la API y es exacto. Lo que falta es la declaración del riesgo
operativo, no la de la licencia.

---

### H-08 MEDIO — El proyecto reclama reproducibilidad con un lockfile que no tiene un solo paquete

**Archivo:** `uv.lock`, `Dockerfile:9-14`, `docs/TECHNICAL_REPORT.md:379`

```toml
version = 1
revision = 3
requires-python = ">=3.12"
```

**Análisis inicial:** ese es el contenido **completo** de `uv.lock` — 52 bytes, cero tablas
`[[package]]`. Es el esqueleto que `uv` escribe antes de resolver nada: un lockfile sin lock. No
existe `requirements.lock`, `poetry.lock` ni equivalente, y `uv.lock` no se copia en el `Dockerfile`
ni se usa en ningún comando del `Makefile`.

**Análisis detallado:** las 14 dependencias directas de `requirements.txt` sí están pineadas con `==`
a una versión exacta, sin excepciones, lo que cumple al pie de la letra `AGENTS.md:32`. El problema
es el árbol transitivo. `Dockerfile:9-11` instala con `pip install -r requirements.txt` sin
`--require-hashes` y sin `--no-deps`, así que en cada build se vuelve a resolver todo lo que arrastran
esas catorce: `botocore`, `s3transfer` y `jmespath` por `boto3`; `starlette`, `pydantic` y
`pydantic-core` por `fastapi`; `google-auth`, `requests` y `websockets` por `google-genai`;
`httpcore`, `h11`, `anyio` y `certifi` por `httpx`; `MarkupSafe` por `jinja2`. Ninguna está fijada.

Dos builds de la misma imagen separados por semanas pueden diferir en esa mitad del árbol, y la
imagen se etiqueta con el git short SHA, lo que sugiere una correspondencia uno a uno entre commit e
imagen que el build no garantiza. En el mismo renglón, `Dockerfile:14` trae el Lambda adapter por tag
mutable (`public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1`) en vez de por digest `@sha256:`.

**Veredicto:** el `uv.lock` vacío es peor que no tener archivo, porque sugiere que el locking existe.
Y `docs/TECHNICAL_REPORT.md:379` lo capitaliza: la fila "Reproducibility" del reporte técnico cita
"Exact pins in `requirements.txt`" como evidencia, cuando la mitad transitiva del árbol flota libre.
Es el mismo patrón de H-03 y H-07 — una garantía publicada cuyo alcance real es menor que el
declarado — aplicado esta vez al build.

**Recomendación:** o se completa el lock (`uv lock` o `pip-compile --generate-hashes` a un
`requirements.lock`) y el `Dockerfile` instala desde ahí con `--require-hashes`, o se borra el
`uv.lock` vacío y se ajusta la fila del reporte técnico para que diga lo que el build realmente
garantiza. Lo que no conviene es dejar el archivo insinuando una garantía que no existe. Fijar el
adapter por digest es una línea y va en el mismo cambio.

---

### H-09 BAJO — `docs/EVALUATION.md` dice "dos escenarios faint-spot" y son tres

**Archivo:** `docs/EVALUATION.md:77`, `eval/dataset/scenarios.json:222,415,635`

> The two `faint-spot` scenarios are excluded from this table (`"score_defect": false` in the manifest).

**Análisis inicial:** el manifiesto tiene `"score_defect": false` en tres escenarios —
`faint-spot-synthetic`, `faint-spot-real-et-solar` y `faint-spot-real-hannover-roof` — y el artefacto
lo confirma por aritmética: 29 escenarios contra 26 pares de defecto puntuados.

**Veredicto:** es una exclusión de la tabla de clasificación de defectos, o sea exactamente el tipo
de número que `test_published_numbers.py` existe para custodiar. Nadie valida `scenarios -
len(defect_pairs)`, así que la afirmación se pudrió en silencio cuando se agregó el tercer escenario.

**Recomendación:** corregir a "three" y, ya que el test de esa tabla existe, agregarle la aserción del
conteo de exclusiones para que no vuelva a desalinearse.

---

### H-10 BAJO — `_pct` divide sin el guard que su función hermana sí tiene

**Archivo:** `services/ui/views.py:230-238,407-415`

```python
def _scale(value: float, threshold: float) -> float:
    top = max(abs(value), abs(threshold))
    if top == 0.0:        # el guard está acá
        return 1.0
    return 1.0 if top <= 1.0 else top * 1.5

def _pct(value: float, scale: float) -> float:
    return max(0.0, min(100.0, value / scale * 100.0))   # y acá no
```

**Análisis inicial:** `_plot_y` llama `_pct(value, top)` con el `top` que calcula `_sparkline`, que
no pasa por `_scale` y por lo tanto no tiene el guard.

**Análisis detallado:** reproducido en el host: con `AFTERIMAGE_SEVERITY_SCORE_APPROVE=0` y todos los
scores de un activo en cero, `_sparkline` levanta `ZeroDivisionError` y `GET /assets/{id}` devuelve
500. Requiere un override de entorno a cero, así que el camino es estrecho.

**Veredicto:** bajo por alcanzabilidad, pero es una inconsistencia real: dos funciones adyacentes
resuelven el mismo borde y solo una lo cubre.

**Recomendación:** mover el guard a `_pct` (`if not scale: return 0.0`), que es donde está la
división, y dejar que `_scale` lo herede.

---

### H-11 BAJO — `s3_smoke.py` es código muerto que reimplementa `images.get_png` y `images.decode`

**Archivo:** `services/perception/s3_smoke.py`

**Análisis inicial:** el módulo mantiene su propio cliente S3 memoizado, su propio `get_object` y su
propio `cv2.imdecode` con validación — las tres cosas ya existen en `services/memory/images.py:15-17`,
`:70-74` y `:63-67`. El único consumidor en todo el repo es su propio test
(`services/perception/tests/test_s3_smoke.py:9`).

**Veredicto:** duplicación que cuenta para el piso de cobertura del 90 % sin cubrir ninguna ruta de
producción. Su test verifica la pila S3+OpenCV, que es un propósito legítimo, pero no hace falta un
módulo paralelo para eso.

**Recomendación:** borrar el módulo y reescribir el smoke test sobre `images.get_image` +
`quality.laplacian_variance`, que es la ruta que el sistema realmente usa.

---

### H-12 BAJO — La imagen de Lambda se publica con la suite de tests adentro

**Archivo:** `Dockerfile:18`, `.dockerignore`

```
COPY services/ services/
```

**Análisis inicial:** `.dockerignore` excluye `docs`, `infra`, `video`, `web`, `eval/results` y
`runs`, pero no `services/*/tests/`. La imagen que corre detrás de la Function URL pública incluye
las ~2.000 líneas de tests y sus fixtures.

**Veredicto:** no abre ninguna ruta de ejecución — nada los importa desde `app.py` — pero engordan el
artefacto y el arranque en frío sin aportar nada en producción. La excepción a tener en cuenta es
`panels.py` (H-04), que sí es runtime de `demo`/`eval` y debería seguir viajando en la imagen; por
eso conviene resolver H-04 primero.

**Recomendación:** agregar `services/**/tests` al `.dockerignore` una vez que `panels.py` se haya
mudado a `eval/`.

---

### H-13 BAJO — `eval/run_eval.py` asume que todo `tool_call` trae métricas

**Archivo:** `eval/run_eval.py:19-30`

```python
def _quality_metrics(events) -> dict:
    for event in events:
        if event.get("tool") == "assess_quality":
            return event["metrics"]
    return {}
```

**Análisis inicial:** un `tool_call` que falló se emite con `error` y **sin** `metrics`
(`loop.py:224-225`), pero conserva su campo `tool`. El acceso por corchete levanta `KeyError` en vez
de degradar. Lo mismo en `_severity_label` (`run_eval.py:22`).

**Veredicto:** el daño está contenido — el `try/except` de `main` (`run_eval.py:210-213`) lo convierte
en un `_failed_record` y la corrida sigue — pero el escenario se reporta como "crashed" con un
`KeyError: 'metrics'` en la columna `deciding_number`, escondiendo el error de percepción real que
sería el dato útil.

**Recomendación:** `event.get("metrics") or {}` en las dos funciones. Con eso el registro conserva la
rama y el error verdadero llega al reporte.

---

### H-14 BAJO — La cobertura mide `services/` pero recolecta tests de `eval/`, y el verificador del gate queda sin piso

**Archivo:** `Makefile:14-15`, `pyproject.toml`

```make
test: weights
	$(COMPOSE) run --rm --build app python -m pytest services/ eval/ -v --cov=services ... --cov-fail-under=90
```

**Análisis inicial:** los tests se recolectan de dos directorios y la cobertura se mide de uno solo.
La decisión está declarada — `AGENTS.md` dice "Coverage must remain at or above 90% for `services/`"
— así que no es una omisión. Lo que sí es inconsistente es que los otros dos gates no la sigan:
`Makefile:21` corre `ruff check services/ eval/` y `Makefile:24` corre `mypy services/ eval/`. De los
tres controles, solo la cobertura excluye `eval/`.

**Veredicto:** dos efectos menores pero concretos. Primero, `eval/compare_results.py` — el script que
el CI usa como guardián de las cifras publicadas (`ci.yml:37`) y que H-03 señala como incompleto —
no tiene piso de cobertura propio, aunque `eval/tests/test_compare_results.py` lo ejercite.
Segundo, el sesgo corre a favor del número: un test que vive en `eval/` y ejercita código de
`services/` suma al numerador del 90 %, mientras que el código de `eval/` nunca entra al denominador.

**Recomendación:** `--cov=services --cov=eval` alinea la cobertura con lo que ya hacen lint y
typecheck. Si el piso del 90 % resultara inalcanzable para `eval/`, conviene al menos declarar la
asimetría donde hoy no está dicha.

---

## Resumen de Veredicto

| Severidad | Cantidad | Items |
|-----------|----------|-------|
| Crítico   | 1        | H-01 el cache de `append` trunca el registro de auditoría y la cadena de hash lo declara íntegro |
| Alto      | 2        | H-02 `/activity` lee todas las corridas del bucket en cada request, H-03 el gate anti-drift no vigila el denominador de la localización |
| Medio     | 5        | H-04 el generador del dataset queda fuera de los tres gates, H-05 error HTTP invisible al arrancar una corrida, H-06 aprobación concurrente sin exclusión, H-07 pesos desde la rama `main` de un repo personal de terceros, H-08 reproducibilidad reclamada con un lockfile vacío |
| Bajo      | 6        | H-09 "dos" escenarios excluidos que son tres, H-10 `_pct` sin guard de división, H-11 `s3_smoke.py` muerto, H-12 tests en la imagen de producción, H-13 `KeyError` sobre un `tool_call` fallido, H-14 la cobertura excluye `eval/` mientras lint y mypy lo incluyen |

**Recomendación general:** el proyecto no es apto para presentarse tal como está, pero está a poca
distancia de serlo. H-01 es el único bloqueante de fondo y toca la tesis central del trabajo —
"cada decisión es reconstruible desde una traza" — porque su flujo feliz destruye la traza sin que el
verificador lo note; conviene arreglarlo antes que cualquier otra cosa, y corregir de paso el
`ponytail:` que declaraba el techo equivocado. H-03 es el segundo en prioridad por ser el más barato
de todos: dos entradas en una tupla cierran los catorce casos del barrido. H-07 va tercero por una
razón de calendario más que técnica: es el único hallazgo cuya ventana de reparación depende de un
tercero, y si ese repositorio desaparece antes de la evaluación, el proyecto deja de compilar para
quien intente reproducirlo. H-02 no impide presentar pero degrada de forma visible en cualquier
demostración con historial acumulado. El resto es trabajo de acabado y no condiciona la entrega.

Conviene notar el hilo que une H-03, H-07 y H-08, porque sugiere dónde mirar en la próxima revisión:
los tres son garantías publicadas cuyo alcance real es menor que el declarado — el gate que vigila el
numerador y no el denominador, el sha1 que prueba integridad y se presenta como reproducibilidad, y
el lockfile que insinúa un locking que no existe. H-01 es la misma figura llevada al extremo: un
verificador de integridad que devuelve `verified: true` sobre un registro mutilado.

Fuera de los hallazgos, vale dejar constancia de lo que se auditó y resultó sano: el loop del agente
cierra correctamente todas sus ramas terminales y acota los errores de tool a dos intentos; el
encadenamiento de políticas (`NEXT_TOOL` / `expected_branch`) no admite bucles con el driver
determinista; la retención promete 180 días en `docs/SECURITY.md:61-64` y el código la implementa en
los dos almacenes; y el sistema de i18n tiene 214 claves con simetría exacta entre los cuatro pares
idioma/registro y ninguna clave faltante respecto de lo que las plantillas consumen.

---

## Obstáculos encontrados

- No hay `cv2`, `numpy`, `boto3`, `jinja2` ni `markupsafe` en el host, así que ningún módulo de
  `services/` importa directamente. Las verificaciones ejecutadas (H-01, H-09) corrieron con un
  `sitecustomize.py` en el scratchpad que stubbea esos módulos con un `ModuleType` que se autogenera
  atributos invocables, más `PYTHONPATH` apuntando ahí. Alcanza para todo lo que no toque píxeles.
- `grep -r` sobre la raíz se cuelga contra los binarios del dataset; `git grep` funciona bien.
- El `review-proyecto.md` de la ronda anterior fue borrado en el commit `b2c1287`, así que este
  reporte se construyó desde cero y no arrastra numeración previa.
