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
| `landing.html` | Public product explanation, workflow, evaluation evidence, stack, limits, and entry points. |
| `index.html` | Inspection workspace, four sample captures, and asset gallery. |
| `activity.html` | Recent-run search and status filter, capped at 50 rows. |
| `trace.html` | Live run state, enforced path, tool details, deciding value, image region, and next action. |
| `queue.html` | Pending comparisons with approve and reject actions. |
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

The document defaults to a light data attribute, then an inline head script applies the saved
`localStorage` choice or the operating-system preference before paint. The theme control updates
the root attribute and persists the choice locally.

`services/ui/static/app.css` provides the layout, light and dark tokens, responsive rules, visible
focus styles, high-contrast decision states, tooltip behavior, and reduced-motion alternatives.
The Inter font is self-hosted and attributed in `NOTICE`.

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
