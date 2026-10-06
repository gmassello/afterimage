# Backend guide

This document is the canonical guide to the web API, inspection loop, persistence, observability,
configuration, and backend tests.

## Runtime and entry points

| Entry point | Purpose |
|---|---|
| `services.api.app:app` | FastAPI application served by Uvicorn. |
| `python -m services.agent.run` | Run or resolve an inspection from the command line. |
| `python -m services.agent.demo` | Exercise the principal branches with sample data. |
| `python -m services.memory.backfill` | Populate missing asset summaries; supports `--dry-run`. |
| `python -m services.observability.render` | Render a stored trace. |

Each inspection opens an in-process MCP session to the server in `services/mcp_server/server.py`,
over the library's in-memory transport: same protocol, no subprocess, and the ONNX models stay
loaded between inspections. The server exposes six tools and receives storage keys rather than image
arrays; `python -m services.mcp_server.server` serves the same tools over stdio for outside clients.
Because the tools now share the API process, calls into ALIKED and LightGlue are serialised by one
lock and the decoded-image cache keeps the 32 most recent arrays.

## HTTP contract

| Method and path | Contract |
|---|---|
| `GET /health` | Returns `{"ok": bool, "calibration": decision}`. The calibration decision comes from `services/agent/calibration.py`, which aligns a synthetic panel against a shifted copy with the default detector and evaluates it with the `alignment` policy stage, once per process. Returns 503 when the branch is not `aligned`. It is also used by the production warmer. |
| `GET /` | Renders the public product landing without reading asset memory. |
| `GET /app` | Renders the upload form, sample captures, and asset gallery. |
| `GET /activity?q=&status=` | Renders at most 4 recent runs, newest first. Filters apply to the 200 most recent runs, not to the whole archive. |
| `GET /assets/{asset_id}?next=` | Renders the chronological history and current baseline. `next`, when it names a bundled sample of any set (`sample-defect`, `sample-b-blurred`, `sample-c-foreign`, …), adds a link that continues the demo tour. |
| `POST /inspections` | Validates the asset ID and image, stores the capture, starts a trace, and redirects with 303. The asset ID may be empty: the capture is then stored under `assets/_unassigned/` and the loop starts with `identify_asset`. Returns 503 `calibration_failed` while calibration is out of tolerance. |
| `POST /runs/{run_id}/execute` | Claims and executes the opened run; returns 404 for unknown runs and 409 when already claimed. HTML receives a 303 back to the trace, so the run also starts without JavaScript. |
| `POST /runs/{run_id}/retry` | For a terminal failed run, idempotently opens its replacement. A run interrupted before it finished is closed as failed after 15 minutes of silence and then retried the same way. HTML receives a 303; JSON receives the new run contract. |
| `GET /queue` | Renders pending findings ordered for human review. |
| `POST /queue/{run_id}/{verdict}` | Accepts `approve` or `reject` and resolves a pending finding. An optional `reason` form field, trimmed to 500 characters, is stored in `verdict.json` and in the human decision's `extra`. The response is a 303 to `/queue`; when the form carries `from=trace` (the trace's own CTA), an approval redirects to `/assets/{asset_id}` (with `?next=sample-blurred` for a `demo-panel-*` asset), the asset read from the run's `state.json`, and a rejection back to `/traces/{run_id}`. The verdict is claimed write-once and never released: repeating the same verdict resumes an interrupted resolution idempotently, and the opposite verdict returns 409. A claim whose S3 conditional write is still in flight also returns 409 instead of an error, and the queue shows an interrupted claim with only its own action. |
| `GET /traces/{run_id}` | Returns JSON by default or HTML when requested; `?format=json` forces JSON. |
| `GET /static/{name}` | Serves known content-hashed static assets with immutable caching. |
| `GET /images/{key:path}` | Serves stored PNG data or a fixed 180-pixel thumbnail. |

`POST /inspections` accepts asset IDs matching `^[a-z0-9-]{1,64}$`. The image is required, limited
to 6 MiB, and must decode successfully. Invalid IDs, missing images, and undecodable bodies produce
400 responses; oversized bodies produce 413. The route does not run the inspection loop inside the
upload request.

Expected HTTP failures share one representation selected by `Accept`. Requests accepting
`text/html` receive the server-rendered error page with the original status. Other clients receive
`{"detail": string, "code": string, "retryable": boolean}`, where `retryable` is always `false`
today because the retry lives on the activity row, not on the error itself. Application codes
include `invalid_asset_id`, `image_required`, `upload_too_large`, `image_too_many_pixels`, `invalid_image`, `asset_not_found`, `run_not_found`,
`run_already_started`, `run_not_failed`, `calibration_failed`, `retry_in_progress`, `approval_not_found`, `approval_already_resolved`,
`trace_not_found`,
`static_asset_not_found`, `invalid_image_width`, `image_not_found`, and `internal_error`. Browser
upload validation is the deliberate exception: it re-renders `/app` with the asset ID and an inline
error because browsers cannot repopulate the rejected file input.

Language and reading-register preferences are resolved from query parameters, cookies, and, for
the initial language, `Accept-Language`. Middleware persists valid choices in one-year cookies.

Approval events identify the actor with a truncated SHA-256 fingerprint derived from request
metadata; raw IP addresses are not written to the trace.

## Agent loop

`services/agent/loop.py` creates 12-character hexadecimal run IDs, appends `run_started`, resumes an
opened run, and prevents duplicate execution by writing `claim.json` write-once before the first
tool runs; a second execute finds it and returns 409.

Retry is separate from execution. `POST /runs/{run_id}/retry` accepts only a run whose final
`run_finished.status` is `failed`. It conditionally writes `retry.json` on that original run, then
opens a new `unstarted` run with the same `asset_id` and `capture_key` plus `retry_of`; when it
executes, the loop copies the capture into the retry's own `assets/{asset_id}/{run_id}/` folder so
its derived images never overwrite the original run's evidence. A repeated or
concurrent request reads the marker and returns the same replacement. The JSON response is:

```json
{
  "retry_of": "failed-run-id",
  "run_id": "replacement-id",
  "status": "unstarted",
  "trace_url": "/traces/replacement-id",
  "execute_url": "/runs/replacement-id/execute"
}
```

The driver is `GeminiLLM` when `GOOGLE_API_KEY` is configured and `PolicyFollowingLLM` otherwise.
The loop enforces a maximum of 12 turns and the following order:

0. `identify_asset`, called by the loop itself before the LLM starts and only when the upload named
   no asset. It builds a `cv2.ANNIndex` over the descriptors of every current baseline
   (`services/perception/recognition.py`); each capture keypoint votes for the asset of its nearest
   neighbour when it passes a ratio test against the nearest keypoint of a different asset. The
   `identity` stage returns `identified` (enough votes and vote share) or `unidentified`, which ends
   the run and never creates an asset. On `identified` the capture is copied under that asset's
   prefix; alignment then verifies the guess geometrically, so a wrong one ends as
   `unrecognized_asset`. Baseline descriptors are cached in S3 as `descriptors-<detector>.npy` next
   to the baseline image and computed on first use.
1. `assess_quality`
2. `align_to_baseline` with ALIKED and LightGlue when weights are available, otherwise ORB
3. `align_to_baseline` with ORB only when the initial neural attempt requests the fallback
4. `diff_against_memory`
5. `crop_and_rescan` only for the uncertainty branch
6. `classify_severity`, which also stores `evidence.png` (the aligned capture with the region boxed
   and labelled through `cv2.FontFace`) and returns its `evidence_key`
7. `submit` with the branch already decided by policy

When `AI_GATEWAY_API_KEY` is set, a `submit` naming the right branch passes one more check before it
is accepted: `services/agent/jev.py` asks Jev whether the message overstates the last verdict, and the
`phrasing` stage compares the probability with `jev_floor`. `phrasing_rejected` returns the submit to
the model as an error; `phrasing_ok` accepts it. The call is recorded as a `jev_guard` tool event.
Jev calls use a 2-second timeout and no retry; any failure is recorded as a tool error and the run
continues as if no key were set.

The rescan result keeps `zoom_area_ratio` for the crop-relative confirmation threshold and passes
full-frame `area_ratio` to severity classification.

For a first capture, only quality is required before creating the baseline. Every later tool result
is passed to `services/agent/policy.py:evaluate`, which returns the decision record
`{input_metric, value, threshold, branch}`. The loop rejects out-of-order calls and a submitted branch that differs from
the last policy verdict.

## Persistence

### DynamoDB

`services/memory/store.py` stores asset metadata, inspections, and baselines in one table. A history
is one partition query; the gallery uses a table scan over denormalized `META` summaries. Conditional
updates prevent an older inspection from replacing newer summary fields. Inspection and summary
writes are not transactional. List and query operations page through every result.

### Images

`services/memory/images.py` writes normalized PNG images to
`assets/{asset_id}/{inspection_id}/{name}.png`, reads them through S3, and can generate thumbnails on
demand. It also maintains process-local caches.

### Runs

`services/memory/runs.py` selects local storage by default and S3 when `AFTERIMAGE_RUNS_S3=1`.
Artifacts live at `runs/{run_id}/events.json`, `state.json`, `pending.json`, `verdict.json` for a
resolved approval, and, for a retried failure, `retry.json`. The first file is the causal history; `state.json` and `pending.json` are
materialized terminal and approval state; `retry.json` is the write-once pointer to the replacement.
Every append reads the stored file again, so a process never rewrites the log from a stale copy; two
concurrent appends on one run still keep the last writer only. On S3 the run listing is ordered by
`LastModified` and truncated before any object is read, and `GET /queue` memoizes that listing for 15
seconds, dropping it as soon as a run starts or a verdict lands.

## Human approval

`services/agent/hitl.py` writes `pending.json` for `human_approval`. Approval persists the inspection
and promotes the capture if its timestamp permits it. Rejection records the decision without
changing the baseline. `auto_write` persists and promotes immediately; `no_change` persists the
inspection without promoting.

After an approval, `reobserve` reads memory back (`store.history`, `store.current_baseline`,
`images.exists`) and the `reobserve` stage records `baseline_verified` when the stored state matches
what the commit expected, or `baseline_drift` otherwise. The human decision and this check are each
emitted once, so a repeated verdict does not duplicate them. A rejection with a reason, when a Jev key
is configured, is classified by the `rejection` stage as `rejected_capture_artefact` or
`rejected_asset_finding` and recorded as a `jev_rejection` tool event. Neither check changes the
committed outcome. `policy.AUDIT_METRICS` names the metrics these checks record, so the trace
headline keeps showing the verdict they follow.

## Observability

`services/observability/trace.py` owns the logically append-only event log. Events include `run_started`, `tool_call`,
`decision`, `approval_requested`, and `run_finished`. Tool events carry arguments, duration,
metrics, and the policy record. `broken_at` reports the first invalid link in the hash chain.

This is a purpose-built event trace, not an OpenTelemetry implementation. While a run is active,
the UI derives state from events. Once finished, `state.json` provides the terminal summary.

## Configuration and failures

The application uses the environment variables listed in [STACK.md](STACK.md). AWS client factories
are lazy and cached so importing modules does not require credentials, configuration, or model
weights. Exceptions are allowed to propagate to explicit HTTP or run failure states rather than
being silently discarded. If execution raises unexpectedly, `resume` appends a failed
`run_finished`, materializes `state.json`, and re-raises; the execute endpoint therefore returns
HTTP 500 while preserving the failed run for inspection.

Operational limitations include a public unauthenticated endpoint, a long synchronous execution
request, no distributed run lock, non-transactional summary writes, and bounded
integrity guarantees. Deployment controls and retention are described in [SECURITY.md](SECURITY.md).

## Test map

| Area | Tests |
|---|---|
| Loop and policy | `services/agent/tests/test_loop.py`, `test_policy.py`, `test_hitl.py`, `test_calibration.py`, `test_jev.py` |
| API and traces | `services/api/tests/test_endpoints.py`, `test_traces.py` |
| Memory and baselines | `services/memory/tests/` |
| Trace integrity and rendering | `services/observability/tests/` |
| Perception and import safety | `services/perception/tests/` |
| Published evaluation claims | `eval/tests/test_published_numbers.py` |
| Jev tooling | `eval/tests/test_jev_tools.py` |

The supported verification sequence is `make build`, `make verify-runtime`, `make lint`,
`make typecheck`, and `make test`. `make smoke` builds the Lambda image, runs it, and requires
`/health` to report calibration `aligned` and the landing to render. `make smoke-jev` measures Jev's
recall and precision at `jev_floor` on labelled sentences and needs `AI_GATEWAY_API_KEY`.
