# Revisión /simplify — etapa 5 (observabilidad)

Alcance: diff sin commitear de la etapa 5 (event log + renderers + endpoint `GET /traces/{run_id}`).
Cuatro agentes en paralelo (reuse, simplificación, eficiencia, altitude). Suite tras aplicar: **54 tests verdes** en el contenedor arm64; `make demo` sigue mostrando la cadena causal completa.

## Aplicado

1. **Verdict fusionado dentro del span** (convergieron 3 agentes). `call()` ahora devuelve `(payload, span)` y `record()` emite un único evento `tool_call` con `policy` adentro. Mueren `trace.attach()`, el flag `span: bool` y el acoplamiento posicional "el verdict se pega al último evento emitido" — el vínculo span→verdict ahora viaja por flujo de datos, no por posición en el archivo. Los spans de error se siguen emitiendo desde `call()`.
2. **`started_at`/`ended_at` eliminados del span**: eran derivables (`ts` del emit + `duration_ms`); ahora la duración se mide con `time.perf_counter()`. También elimina el formato de timestamp duplicado entre `loop.py` y `trace.py`.
3. **`write_json` único**: vivía duplicado en `hitl.py` y `trace._write`; ahora es `trace.write_json` y `hitl`/`loop` lo importan de ahí.
4. **`render_text(events)`**: el parámetro `state` nunca se usaba; los callers (demo, CLI) ya no leen `state.json` al cuete.
5. **`_verdict_html` reusa `causal_line`**: el comparador `<`/`>=` y el formato de la línea causal existen una sola vez (se cambió el branch en bold por weight 600 en el band completo).
6. **`app.py` simplificado**: `HTTPException` en vez de helper `_not_found` + `JSONResponse` manual; el 404 sale de `load_run` devolviendo eventos vacíos (sin doble `exists()`); el dict se retorna directo. El patrón de `run_id` ahora es `trace.RUN_ID_PATTERN`, compartido en vez de re-codificado en el endpoint.
7. **Fixture compartida** `services/observability/tests/sample_run.py`: `STATE`/`EVENTS` estaban copy-pasteados entre `test_render.py` y `test_traces.py` y ya habían drifteado.
8. **`test_trace_loop.py` fusionado en `test_loop.py`**: sus dos escenarios re-corrían flujos completos contra LocalStack que `test_loop.py` ya ejercía; las assertions de `events.json` se movieron a esos tests existentes. Dos corridas caras menos y cero helpers duplicados (`localstack`, `PANEL`, `run_loop`, `unique`).

## No aplicado (con motivo)

- **`decisions.json` como proyección de `events.json`** (borrar el dual-write): cambio de contrato fuera del alcance del diff — `hitl.resolve`, `run.py` y tests existentes consumen `decisions.json`. Queda anotado como candidato para etapa 6+.
- **JSONL append-only para eventos**: `docs/PLAN.md` fija `events.json` como array persistido, y a ~15 eventos/run el read-modify-write es irrelevante (<1 ms acumulado por run). Se reevalúa si aparecen escritores concurrentes.
- **I/O sincrónico de `emit` dentro del loop async**: patrón preexistente en el repo (`write_json`, `store.put_inspection`), proceso mono-run; no accionable a esta escala.
- **Ramas fallback de tipos desconocidos en los renderers**: código muerto hoy, pero seguro de una línea; degradan con gracia ante tipos futuros.
- **Dispatch if/elif por tipo de evento en los dos renderers**: correcto a esta escala (5 tipos); un registry sería sobre-ingeniería.
- **Instrumentar en el server MCP en vez del cliente**: descartado por el reviewer de altitude — `loop.call` es el único choke point y captura la latencia real de transporte.
