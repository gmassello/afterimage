# Pendiente — cierre OpenCV AI Competition 2026

Cierre: **2026-10-26 23:45 -07:00** (2026-10-27 03:45 -03:00). Competencia:
<https://opencv26.devpost.com/> · Submission: <https://devpost.com/software/afterimage-ibp376> · PR: no aplica.

Etapas (de la pagina de fechas del evento; en Devpost, `/details/dates`): submissions hasta 2026-10-26 23:45 -07:00, judging 2026-10-27 00:00 -07:00 → 2026-11-09 23:45 -08:00,
ganadores 2026-11-10 09:00 -08:00.

Estado del codigo en una linea: 380 tests verdes (cobertura 92.62%, `make test` del 2026-10-01); producto completo (U1-U18 del PLAN `done`); faltan U19 (regrabar video) y U20 (pegar la ficha).

---

## Superficies

| Superficie | Donde | Estado | Verificado |
|---|---|---|---|
| Repo y CI | `gmassello/afterimage` @ `bc9418b` | pusheado; CI verde | 2026-10-04 `gh run list --commit` |
| Sitio | https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/ | ok — sirve `bc9418b` (deploy manual, run 37232578711): cinco juegos con su rubro en el título, el tercero una fisura en un muro de hormigón | 2026-10-04 `/app` muestra "Hormigón: una grieta en el muro" y sirve `sample-e-defect-thumb.1621b31d.png` `200 image/png` |
| Submission | https://devpost.com/software/afterimage-ibp376 | publicada el 7 Sep, desactualizada (dice video, cinco tools, 23 escenarios); texto nuevo en `docs/submission.md` | 2026-10-01 lectura de la pagina publica |
| Tarjeta en la galeria | https://opencv26.devpost.com/project-gallery | no verificada | — |
| PR upstream | no aplica | — | — |
| Segundo checkout | no aplica | — | — |
| Video | `zUFR96a33IM` (4:53.6) | cumple el requisito; muestra la UI del 6 Sep, anterior a landing, tour y toggles | 2026-10-01 embed en la ficha |
| Deck | no lo pide el evento | — | `docs/HACKATHON.md` |

## Hechos duplicados

| Hecho | Valor real | Comando que lo produce | Copias |
|---|---|---|---|
| Cantidad de tests | 363 | `make test` | ninguna publicada |
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

- **Envio del formulario de Devpost antes de las 23:45 PDT** (no 23:59 como dice el overview) — fallback: enviarlo el 24-25 Oct y editar despues; Devpost permite editar hasta el cierre.
- **Video publico o unlisted, accesible sin login** — fallback: subir la misma toma a un segundo host y poner ambos links.
- **Endpoint vivo durante todo el judging (27 Oct → 9 Nov)** — fallback: ofrecer screen-share en vivo, que la regla acepta.
- **Check-in de Zoom 7-14 Oct, solo si hay compute grant** — fallback: ninguno; confirmar si aplica.
