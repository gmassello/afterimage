# Plan — paying down the front-end architecture debt

Status: **not started.** Written after a review of the front-end architecture; scheduled for a later session.

## Context

The front end works and is verified, but it builds HTML by concatenating strings in Python. Reviewing the architecture surfaced four real weaknesses:

1. **Escaping is a convention, not a guarantee.** 44 manual `html.escape` calls across `services/observability/render.py` and `services/api/pages.py`. They are all in place today, but one future omission is an XSS, and the only thing covering it is a single-case test.
2. **CSS ships inline on every response.** 6,345 B of `BASE_STYLE` plus 3,751 B (`_TRACE_STYLE`) or 3,276 B (`_PAGES_STYLE`) per page. Since `/traces/{id}` is polled every 1.5 s while an inspection runs, those ~10 KB are re-sent on every poll and the browser cannot cache them. The Google Fonts `@import` also lives inside the `<style>` block, so the font is only requested after the CSS is parsed — two serialized round-trips on first load.
3. **The layering is inverted.** `render.py` lives in `services/observability/` but owns the chrome for all four views, including the queue's approval buttons. `services/api/pages.py` (the API layer) imports presentation from the observability layer.
4. **Two different polling mechanisms**: `_REFRESH` reloads the whole page on the queue, `_LIVE_SCRIPT` swaps a fragment on the trace.

**Intended outcome:** HTML comes from autoescaping templates, CSS and JS are served cached from a static route, presentation lives in its own layer, and there is a single poller. No visual change: all four screens must look exactly as they do today.

## Assumptions

- No behavioural or visual change. This work is structural: same views, same data, same routes, same look in dark and light.
- The deploy and the `docs/img/` recapture remain pending and blocked on credentials. This plan leaves them untouched.

## Constraints that shape the design

- **`Dockerfile:18` runs `COPY services/ services/`** with no extension filter, so any file under `services/` reaches the image without touching the Dockerfile. But **`.dockerignore:10` excludes `web`**, so the new package is named **`services/ui/`**, not `web/`, to avoid depending on how Docker interprets that pattern.
- **The `python -m services.observability.render RUN_ID` CLI is documented** in `docs/index.html:972-974` and `docs/PLAN.md:190-191`. That entry point does not move: `render_text`, `causal_line`, `load_run` and `main()` stay where they are.
- **There is no CloudFront**, only the Function URL (`infra/template.yaml:32-33`), so static CSS is served from the Lambda itself. Browser caching is what avoids repeat invocations, and the pattern already exists at `services/api/app.py:96` (`Cache-Control: public, max-age=86400` for images).
- **No lint or type-check in CI**: `make test` runs `pytest services/ eval/` inside the arm64 container. A new `services/ui/tests/` is collected automatically.

## Steps

### A. Dependency and structure

- Add `jinja2` to `requirements.txt` pinned to an exact version, like every other entry.
- Create `services/ui/` with:
  - `views.py` — the four view builders
  - `templates/` — `base.html`, `index.html`, `asset.html`, `queue.html`, `trace.html` and `partials/`
  - `static/app.css` and `static/app.js`
- No `__init__.py`: the rest of `services/` uses implicit namespace packages.

### B. Autoescaping templates — weakness 1

- Jinja2 environment in `services/ui/views.py`: `Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)`. The path resolves from `__file__` — the pattern already used by `eval/scenarios.py:8` — not from the CWD.
- `base.html` absorbs `shell()` (`render.py:380`): doctype, head, the CSS `<link>`, the inline theme bootstrap, the header with brand + nav + toggle, and the `body` and `script` blocks.
- Functions that currently return HTML return **data** instead: `_hero`, `_path`, `_details`, `_comparison`, `_cta`, `_footer`, `_timeline_entry` and `_queue_entry` build dicts and lists; the markup lives in the templates.
- Bar geometry (`_scale`, `_pct` at `render.py:293-303`) stays in Python and hands over precomputed percentages; the template only places them.
- Shared components (`threshold_bar`, `comparison_figures`, `approval_forms`, `region_tag`) become partials included from both sides.
- **All 44 `html.escape` calls disappear.** Any fragment that must go out unescaped has to be an explicit, localized `Markup` — not the default.

### C. Static CSS and JS — weaknesses 2 and 4

- Merge `BASE_STYLE` + `_TRACE_STYLE` + `_PAGES_STYLE` into `services/ui/static/app.css`. The Google Fonts `@import` leaves the CSS and becomes `<link rel="preconnect">` + `<link rel="stylesheet">` in `base.html`'s `<head>`, so the font and the CSS are fetched in parallel.
- `services/ui/static/app.js` holds the theme toggle, `placeBoxes()` and **a single poller**, which settles weakness 4: one function that swaps a container every N ms, carrying the guards `_REFRESH` has today (stop on submit or link click, do not reload while a `<details>` is open). The trace uses it on `.live` at 1.5 s; the queue on `.queue` at 5 s. `location.reload()` goes away, which also removes the queue's scroll jump and theme flash.
- The theme bootstrap **stays inline in `<head>`**: it is four lines and must run before first paint; moving it to an external file reintroduces the FOUC this design was avoiding.
- New route in `services/api/app.py`: `GET /static/{name}` serving both files with `Cache-Control: public, max-age=31536000, immutable`, following the pattern at `app.py:96`. URLs carry a short content hash computed at import (`/static/app.<sha8>.css`) so a deploy busts the cache. No route collision: `/assets/{asset_id}` and `/images/{key:path}` are taken, `/static/*` is free.

### D. Move presentation into its own layer — weakness 3

- `services/observability/render.py` keeps what belongs to observability: `load_run`, `causal_line`, `_text_line`, `render_text` and `main()`. It drops from 666 lines to roughly 90, and the documented CLI keeps working unchanged.
- `services/api/pages.py` **goes away**; its three views move into `services/ui/views.py` alongside the trace view.
- `services/api/app.py` imports `render_html`, `index_page`, `asset_page` and `queue_page` from `services.ui.views`. Those four symbols are the whole boundary.
- No import cycles: `services/ui` imports from `observability`, `agent.policy` and `memory.store`; none of them import `ui`.
- Tests: the three in `services/observability/tests/test_render.py` split — the `render_text` one stays, the two HTML ones move to `services/ui/tests/`. The `services/observability/tests/sample_run.py` fixture **does not move**: `services/api/tests/test_traces.py:7` imports it too.

## Documentation to update

- `docs/PLAN.md:190-191` — states that `render_text` and `render_html` coexist as pure renderers in the same module. Update to reflect that the HTML moved to `services/ui/`, why (inverted layering), and that it now comes from autoescaping templates.
- `docs/SUBMISSION.md:33` — cites `services/observability/` as evidence for the trace view; should name `services/ui/` as well.
- `docs/TECHNICAL_REPORT.md:154` — the route table gains `GET /static/{name}`.
- `docs/index.html:972-974` — **no change**: the CLI still lives at `services.observability.render`.
- `README.md` — mentions none of these modules; no change.
- `REVIEW-SIMPLIFY.md` — a historical report from a different review; leave it alone.

## Verification

1. **Tests.** Baseline: `63 passed, 17 skipped` (`pytest services/ eval/ -q`). Must stay equal or better. `test_queue_refresh_yields_to_an_in_flight_navigation` (`services/api/tests/test_endpoints.py`) asserts exact strings from the old `_REFRESH`: it **changes by design**, moving to the unified poller's guards.
2. **Widened escaping test.** The current `test_render_html_escapes_untrusted_strings` covers one field; extend it across all four views, injecting `<script>` into `asset_id`, `message`, `label` and the image keys. This is what demonstrates autoescape does its job.
3. **Visual parity — the real risk of this change.** Regenerate the local preview of all four views with the same sample data, serve it over `http.server` and compare in Chrome against today's screenshots, **in dark and light**. Nothing may shift.
4. **Live trace end to end**: local `uvicorn` with `AFTERIMAGE_RUNS_DIR`, a seeded run and events fed one at a time, confirming the page fills in on its own and the poller stops at `done`.
5. **CSS caching**: `curl -I` on `/static/app.<hash>.css` to check `Cache-Control`, and confirm none of the four pages still carries a `<style>` block with the full CSS.
6. **The image contains the new files**: `docker compose run --rm --build app ls services/ui/static services/ui/templates` proves `COPY services/` picked them up without a Dockerfile change.
7. `git diff --stat` to confirm the scope.

## Out of scope

- **Persisting the severity verdict.** Still the most important follow-up from the previous review: the timeline and the queue paint `Policy.from_env()` as of now next to a historical score, so moving the threshold relabels the past. Deliberately excluded — it changes the signatures of `store.put_inspection`, `hitl.commit` and `loop.conclude`, and combining a data-model change with a template migration in one pass doubles the risk right before a deploy.
- **The deploy and the `docs/img/` recapture.** Still pending, still blocked on credentials.
- **The narrated video.** Still recorded against the old look; re-recording is a separate production.
- **Lint and type-check.** They do not exist in this repo and are not introduced here.
- No changes to the data model, `policy.py`, the thresholds, or `infra/template.yaml`.