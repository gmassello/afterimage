# Pendiente — cierre OpenCV AI Competition 2026

Cierre: **2026-10-26 23:45 -07:00** (2026-10-27 03:45 -03:00). Competencia:
<https://opencv26.devpost.com/> · Submission: <https://devpost.com/software/afterimage-ibp376> · PR: no aplica.

Etapas (de la pagina de fechas del evento; en Devpost, `/details/dates`): submissions hasta 2026-10-26 23:45 -07:00, judging 2026-10-27 00:00 -07:00 → 2026-11-09 23:45 -08:00,
ganadores 2026-11-10 09:00 -08:00.

Estado del codigo en una linea: 380 tests verdes (cobertura 92.62%, `make test` del 2026-10-05); producto completo (U1-U18 del PLAN `done`); U19 y U20 hechos (video regrabado y ficha pegada el 4 Oct).

---

## Superficies

| Superficie | Donde | Estado | Verificado |
|---|---|---|---|
| Repo y CI | `gmassello/afterimage` @ `c7f0536` | arbol limpio, sincronizado con `origin`; `ci` y Pages verdes en `c7f0536`; `ci` corre en push a `main` y en PRs | 2026-10-05 `git status`, `gh run list --commit` |
| Sitio | https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/ | ok — sirve `24b329a` (deploy run 37247899968; lo posterior es solo docs): `/`, `/app`, `/activity`, `/queue` y `/health` en 200, los 55 assets de `/` y `/app` en 200, calibracion `aligned` 0.9975; field manual en Pages con el contenido del commit | 2026-10-05 curl sin sesion |
| Submission | https://devpost.com/software/afterimage-ibp376 | ok — 1294 palabras, la tagline de `docs/submission.md`, 6 capturas, 14 tags, video `_fJo29SdoaU` (embed y historial de envios), inscripta en la competencia; Testing instructions del envio con el recorrido de ejemplos | 2026-10-05 curl sin sesion + `parse_ficha` |
| Tarjeta en la galeria | https://opencv26.devpost.com/project-gallery | no accesible — Devpost no publica la galeria mientras el concurso esta abierto | 2026-10-05 `gallery.py opencv26` |
| PR upstream | no aplica | — | — |
| Segundo checkout | no aplica | — | — |
| Video | `_fJo29SdoaU` (3:06.6, publico) | ok — mismo ID en README, ficha, deck, field manual y envio; carga (oEmbed 200); render del 4 Oct posterior a `results.json` (26 Sep); cifras del `.srt` 0.3412 0.5945 0.7875 0.8542 0.8621 4.1446, todas en `results.json` o en la toma | 2026-10-05 |
| Deck | no lo pide el evento; `docs/deck.pdf` en el repo | el PDF de `main` es identico al local (sha1 `8ae327a2d7f3`) y linkea el video nuevo | 2026-10-05 raw.githubusercontent |

## Hechos duplicados

| Hecho | Valor real | Comando que lo produce | Copias |
|---|---|---|---|
| Cantidad de tests | 380 | `make test` | `docs/deck.html` (coincide) |
| Escenarios / pasan | 29 / 24 | `make eval` → `eval/results/latest/results.json` | README, EVALUATION, TECHNICAL_REPORT, `docs/submission.md` (ancladas por `test_published_numbers`, salvo la ficha) |
| Tools MCP | 6 | `services/mcp_server/server.py` | README, landing, `docs/submission.md`, descripcion del repo en GitHub (corregida 2026-10-01) |

## Lo que no cierra

- **Efectividad de campo** — lo publicado vale para el dataset comprometido, no es precision en planta; haria falta imagery de planta fuera del dataset.
- **Cinco escenarios fallan** — cada uno con su causa raiz publicada en `docs/EVALUATION.md` (gate de cobertura global, gate de exposicion antes de severidad, severidad que ignora la clase, regla de soiling calibrada en sintetico).
- **Log de auditoria** — la cadena de hashes detecta edicion comun, no es un log firmado.
- **Endpoint publico sin login** — es una demostracion acotada.
- **Impacto sin cifra externa de costo de inspeccion** — solo el costo propio medido ($0.0005 por inspeccion); pregunta abierta en `docs/BRIEF.md`.

## No romper esto al volver

- `docs/submission.md` (la ficha) y el checklist viejo `docs/DELIVERY.md` estaban como `SUBMISSION.md`: en macOS ese nombre pisa la ficha, no recrearlo.
- `test_the_stylesheet_carries_the_design_system_tokens_verbatim` exige que `app.css` empiece con el bloque css de `docs/DESIGN.md` §3: un token nuevo va en los dos.
- Cifras de evaluacion: solo via `make eval`; `test_published_numbers` y el job `eval` de CI fallan si se escriben a mano.
- `make test` y `make dev` necesitan el daemon de Docker (`colima start`).

## Fuera de mi control

No son tareas: son riesgos. Cada uno con su fallback.

- **Envio del formulario de Devpost antes de las 23:45 PDT** (no 23:59 como dice el overview) — ya figura `SUBMITTED` (5/5 pasos); cualquier edicion posterior al cierre no llega al jurado.
- **Video publico o unlisted, accesible sin login** — fallback: subir la misma toma a un segundo host y poner ambos links.
- **Endpoint vivo durante todo el judging (27 Oct → 9 Nov)** — fallback: ofrecer screen-share en vivo, que la regla acepta.
- **Check-in de Zoom 7-14 Oct, solo si hay compute grant** — fallback: ninguno; confirmar si aplica.
