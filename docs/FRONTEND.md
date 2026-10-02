# Frontend guide

This document is the canonical guide to the server-rendered interface, browser behavior,
internationalization, accessibility, and frontend tests.

## Rendering architecture

The frontend is server-rendered HTML. There is no client framework or compilation step.

```text
FastAPI route → services/ui/views.py view model → Jinja2 template → HTML
                                                        ↓
                                              app.css + app.js
```

All pages use the shared assets. The landing additionally loads `landing.js`, a small controller for
its scenario tabs; it does not call the API or write product data.

`services/ui/views.py` converts domain records into presentation-specific structures. Templates
remain small and autoescaped, and shared markup lives in `templates/partials/components.html`.
`services/ui/text.py` resolves all product copy before the template receives it.

## Pages

| Template | Visible behavior |
|---|---|
| `landing.html` | Public product explanation, workflow, evaluation evidence, stack, limits, and entry points. Both primary buttons open `/app?sample=sample-baseline`, so the tour starts one click from **inspect**. The illustration names stages with the trace's `step_<tool>` copy and results with `outcome_<branch>`; metric labels have plain and technical wordings over the same numbers. |
| `index.html` | Inspection workspace, three sets of four sample captures in a horizontal carousel, and asset gallery. The asset ID is optional; its placeholder says an empty field asks the agent to recognise the asset. |
| `activity.html` | Recent-run search and status filter, capped at 4 rows. |
| `trace.html` | Live run state, enforced path, tool details, deciding value, image region, and next action. The title is the localised `outcome_<status>` or `outcome_<branch>` copy, with the model's message beneath it, and the status pill uses `status_*`. The pending verdict and the next-sample link sit inside the hero's text column, under the pills, so a phone reaches them before the deciding-number panel; in the plain register neither carries the model's message; like the queue, an interrupted verdict offers only its claimed action. The `classify_severity` card shows the annotated evidence image (`evidence_key`) as a figure linking to the full-size PNG. The deciding number is the decision whose branch the run ended on (`baseline_exists` for a `first_baseline`), falling back to the last one, and skips `policy.AUDIT_METRICS`, so a re-observation or Jev check never replaces the verdict it follows. |
| `queue.html` | Pending comparisons with approve and reject actions; the reject form carries an optional `reason` field (500 characters). An interrupted verdict shows only the claimed action and a note to repeat it. |
| `asset.html` | Longitudinal timeline, severity trend, current baseline, and superseded baselines. |
| `error.html` | Consistent browser error with a stable code, explanation, and recovery action when available. |
| `base.html` | Document shell, initial theme selection, navigation, and static assets. |
| `partials/header.html` | Language, reading register, and theme controls. |
| `partials/components.html` | Reused figures, labels, tips, metrics, and decision components. |

## Interaction model

`services/ui/static/app.js` progressively enhances usable server-rendered pages:

- The upload control supports file selection, drag and drop, preview, and the 6 MiB client-side
  limit. The server repeats all authoritative validation.
- Sample buttons fetch bundled captures and place them into the same upload path as a local file.
  `/app?sample=<stem>` preselects one of them on load; any other value is ignored.
  The chosen card gets `aria-pressed=true` and an accent border, a server-rendered `role=status`
  line says which sample loaded, and the form scrolls back into view.
- The samples come in three sets of four — crack (`sample-*`), hot spot (`sample-b-*`) and
  delamination (`sample-c-*`) — each a `<section class='group'>` in a horizontal scroll-snap track.
  Swipe, trackpad, the ‹ › buttons or the arrow keys on the focused track move one set; the
  buttons carry `aria-disabled` at either end and a `role=status` line names the visible set.
  `?sample=` of another set scrolls there before selecting it.
- Each set writes to its own demo asset: `demo-panel-<suffix>`, `demo-panel-b-<suffix>` and
  `demo-panel-c-<suffix>`, all from the same `demo` cookie. Picking a sample of another set swaps a
  demo asset id already in the field, never one the visitor typed.
- Until a set's demo asset has a baseline, its samples 2–4 carry `aria-disabled=true` and the
  `sample_needs_reference` note; a click on one only writes `js_sample_locked` to the status line.
- A demo asset walks a tour within its own set: `first_baseline` → sample 3, the approval → the
  asset history with `?next=<set>-blurred` → sample 2, `recapture` → sample 4, `unrecognized_asset` → the asset
  history, which is the end frame. Approving from the trace's own CTA lands on the asset history;
  the queue's forms return to the queue.
- In the plain register the rail and "what it ruled out" name steps with `step_<tool>` copy, and the
  model's message under the title is shown only in the technical register. The footer's integrity
  line appears once the run is done, so it never shows a partial count.
- Asset search and latest-branch filtering run entirely over the gallery already rendered in `/app`;
  they do not issue an API request.
- The landing demo switches among the four bundled scenarios with an ARIA tablist. Arrow keys,
  Home, and End move its single tab stop; each selection reveals a static five-stage explanation
  without opening a run.
- The selected image is previewed before upload; approve and reject actions use a two-step
  confirmation before submission.
- After the upload redirect, the trace page starts the run with a separate POST request. Without
  JavaScript the same request is a `<noscript>` form the operator submits.
- A terminal failed activity row offers retry. The browser follows the redirect to the replacement
  trace; repeated submissions resolve to that same replacement run.
- Active traces poll every 1.5 seconds; the approval queue polls every 5 seconds.
- Polling pauses while the user is interacting with focusable or expanded content and preserves
  relevant browser state when replacing markup.
- Region overlays use the recorded bounding box and the rendered image dimensions.
- View transitions and animated counters are optional enhancements.

Without JavaScript, navigation, history, approval forms, language selection, ordinary file
upload, and starting the uploaded run remain server functions. The landing, application, activity filters, error recovery, and
failed-run retry are ordinary links or forms. Sample selection, live polling, and enhanced previews
require JavaScript.

The public landing and the operational workspace are intentionally separate. `/` explains the
system without touching storage; `/app` is the working surface; `/activity` provides the run-level
view that the asset gallery does not. All three use full-page navigation and the same server-rendered
shell rather than a client-side router.

## Language and reading register

`services/ui/text.py` supports English and Spanish. English is the default and the per-key fallback.
The `plain` register is the default; `tech` exposes implementation terminology where the prose
genuinely differs. Metric names, IDs, units, recorded model text, and numeric evidence are not
translated into less precise substitutes.

The resolution order is:

- Language: valid query parameter, then cookie, then `Accept-Language`, then English.
- Register: valid query parameter, then cookie, then plain.

The API stores valid preferences in independent one-year cookies. Poll requests omit query strings,
so cookies carry the selected preferences across live updates.

## Theme and responsive behavior

The light theme is the default and lives on `:root`; dark overrides it under
`[data-theme="dark"]`. An inline head script, placed before the stylesheet, applies a saved
`localStorage` choice of dark before paint. The operating-system preference is deliberately
ignored (see `docs/DESIGN.md`). The theme control updates the root attribute and persists the
choice locally.

`services/ui/static/app.css` provides the layout, light and dark tokens, responsive rules, visible
focus styles, high-contrast decision states, tooltip behavior, and reduced-motion alternatives.
Decision tones come from a branch map in `services/ui/views.py`: `identified`, `baseline_verified` and
`phrasing_ok` render as `ok`; `rejected_capture_artefact` and `rejected_asset_finding` as `warn`;
`unidentified`, `baseline_drift` and `phrasing_rejected` as `bad`.
The tokens at the top of the stylesheet are copied verbatim from `docs/DESIGN.md`, and a test
fails if they drift. Inter and JetBrains Mono are self-hosted and attributed in `NOTICE`.
The trace renders a terminal of decisions, one line per tool call, that types itself in; the
landing counts its evaluation figures up when they scroll into view. Both show their final state
under reduced motion.

The landing uses a wide two-column hero with the scenario demo as its primary evidence, followed by
the published metrics, the three-step flow, baseline history, stack and limits, and a final `/app`
action. At 900 px the major grids become one column; at 620 px metrics, filters, activity actions,
and error layout stack; the 390 px rule reduces the capture preview. Primary landing actions keep a
44-pixel minimum height, and motion-related transitions are disabled under `prefers-reduced-motion`.

## Security and caching

- Jinja2 autoescaping is enabled and view tests exercise untrusted strings on every page.
- Static filenames include the first eight characters of their SHA-256 digest and are cached as
  immutable for one year.
- Stored images are served through the application rather than exposed as a public S3 bucket and
  use a shorter cache policy.
- Browser checks improve usability but do not replace API validation.
- Browser requests receive the themed HTML error page. Invalid browser uploads instead return the
  workspace with its form values and an inline alert, because the file must be selected again.
  Programmatic clients receive stable `detail`, `code`, and `retryable` fields as JSON.

## Adding or changing UI behavior

- Put user-facing copy in `services/ui/text.py`, with complete English coverage and Spanish values.
- Add register variants only when plain and technical prose should differ.
- Build presentation data in `services/ui/views.py`; do not query storage from templates.
- Reuse macros for repeated markup and preserve autoescaping.
- Keep essential actions available as HTML forms or links when practical.
- Test keyboard focus, the narrowest supported layout, both themes, both languages, and both
  reading registers when the affected surface uses them.

## Test map

| Area | Tests |
|---|---|
| View models, escaping, layout contracts, polling, and rendering | `services/ui/tests/test_views.py` |
| Translation coverage, fallbacks, registers, and samples | `services/ui/tests/test_language.py` |
| Route negotiation, cookies, upload, execution, queue, static files, and images | `services/api/tests/test_endpoints.py` |
| Trace JSON and integrity presentation | `services/api/tests/test_traces.py` |

The manual browser paths and known failure modes are maintained in [E2E.md](E2E.md).
