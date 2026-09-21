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

Each inspection opens an MCP stdio subprocess implemented by `services/mcp_server/server.py`. The
subprocess exposes five tools and receives storage keys rather than image arrays.

## HTTP contract

| Method and path | Contract |
|---|---|
| `GET /health` | Returns liveness. It is also used by the production warmer. |
| `GET /` | Renders the public product landing without reading asset memory. |
| `GET /app` | Renders the upload form, sample captures, and asset gallery. |
| `GET /activity?q=&status=` | Renders at most 50 recent runs, newest first, after optional free-text and exact-status filters. |
| `GET /assets/{asset_id}` | Renders the chronological history and current baseline. |
| `POST /inspections` | Validates the asset ID and image, stores the capture, starts a trace, and redirects with 303. |
| `POST /runs/{run_id}/execute` | Claims and executes the opened run; returns 404 for unknown runs and 409 when already claimed. HTML receives a 303 back to the trace, so the run also starts without JavaScript. |
| `POST /runs/{run_id}/retry` | For a terminal failed run, idempotently opens its replacement. A run interrupted before it finished is closed as failed after 15 minutes of silence and then retried the same way. HTML receives a 303; JSON receives the new run contract. |
| `GET /queue` | Renders pending findings ordered for human review. |
| `POST /queue/{run_id}/{verdict}` | Accepts `approve` or `reject` and resolves a pending finding. |
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
include `invalid_asset_id`, `image_required`, `upload_too_large`, `invalid_image`, `asset_not_found`, `run_not_found`,
`run_already_started`, `run_not_failed`, `approval_not_found`, `trace_not_found`,
`static_asset_not_found`, `invalid_image_width`, `image_not_found`, and `internal_error`. Browser
upload validation is the deliberate exception: it re-renders `/app` with the asset ID and an inline
error because browsers cannot repopulate the rejected file input.

Language and reading-register preferences are resolved from query parameters, cookies, and, for
the initial language, `Accept-Language`. Middleware persists valid choices in one-year cookies.

Approval events identify the actor with a truncated SHA-256 fingerprint derived from request
metadata; raw IP addresses are not written to the trace.

## Agent loop

`services/agent/loop.py` creates 12-character hexadecimal run IDs, appends `run_started`, resumes an
opened run, and prevents ordinary duplicate execution through a claim derived from events. The claim
is not a distributed atomic lock.

Retry is separate from execution. `POST /runs/{run_id}/retry` accepts only a run whose final
`run_finished.status` is `failed`. It conditionally writes `retry.json` on that original run, then
opens a new `unstarted` run with the same `asset_id` and `capture_key` plus `retry_of`. A repeated or
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

1. `assess_quality`
2. `align_to_baseline` with ALIKED and LightGlue when weights are available, otherwise ORB
3. `align_to_baseline` with ORB only when the initial neural attempt requests the fallback
4. `diff_against_memory`
5. `crop_and_rescan` only for the uncertainty branch
6. `classify_severity`
7. `submit` with the branch already decided by policy

For a first capture, only quality is required before creating the baseline. Every later tool result
is passed to `services/agent/policy.py:evaluate`, which returns the deciding metric, value,
threshold, and branch. The loop rejects out-of-order calls and a submitted branch that differs from
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
Artifacts live at `runs/{run_id}/events.json`, `state.json`, `pending.json`, and, for a retried
failure, `retry.json`. The first file is the causal history; `state.json` and `pending.json` are
materialized terminal and approval state; `retry.json` is the write-once pointer to the replacement.

## Human approval

`services/agent/hitl.py` writes `pending.json` for `human_approval`. Approval persists the inspection
and promotes the capture if its timestamp permits it. Rejection records the decision without
changing the baseline. `auto_write` persists and promotes immediately; `no_change` persists the
inspection without promoting.

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
| Loop and policy | `services/agent/tests/test_loop.py`, `test_policy.py` |
| API and traces | `services/api/tests/test_endpoints.py`, `test_traces.py` |
| Memory and baselines | `services/memory/tests/` |
| Trace integrity and rendering | `services/observability/tests/` |
| Perception and import safety | `services/perception/tests/` |
| Published evaluation claims | `eval/tests/test_published_numbers.py` |

The supported verification sequence is `make build`, `make verify-runtime`, `make lint`,
`make typecheck`, and `make test`.
