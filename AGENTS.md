# Repository Guidelines

## Project Overview

Afterimage is a visual inspection agent with longitudinal memory, built for the OpenCV AI Competition 2026. Use the documentation map below for the implemented system; `docs/BRIEF.md` and `docs/PLAN.md` are historical planning records.

## Documentation Map

Current system documentation:

- [Functional guide](docs/FUNCTIONAL.md) — product concepts, operator journey, outcomes, and limits.
- [Technology stack](docs/STACK.md) — runtime, dependencies, data services, delivery, and configuration.
- [Architecture](docs/ARCHITECTURE.md) — module boundaries, data flow, deployment, guarantees, and known limits.
- [Backend guide](docs/BACKEND.md) — HTTP contracts, agent loop, persistence, observability, and backend tests.
- [Frontend guide](docs/FRONTEND.md) — pages, rendering, browser behavior, internationalization, accessibility, and UI tests.

Specialized references:

- [Evaluation](docs/EVALUATION.md) — current dataset, metrics, failure cases, and limitations.
- [End-to-end walkthrough](docs/E2E.md) — manual browser paths and expected behavior.
- [Security](docs/SECURITY.md) — public endpoint, deployment controls, retention, and data handling.
- [Responsible use](docs/RESPONSIBLE_USE.md) — intended use, claims, human gate, and boundaries.
- [AI disclosure](docs/AI_DISCLOSURE.md) — model responsibilities in the product and its development.

Historical and delivery records include `docs/BRIEF.md`, `docs/PLAN.md`, `docs/SUBMISSION.md`, and the video-production documents. They preserve decisions and evidence from a point in time and are not sources of current architecture.

## Hard Rules

- Use OpenCV 5 only. Verify every OpenCV API against https://docs.opencv.org/5.x/ before using it. OpenCV 5 replaced `Features2D` with `Features`, removed the C API, and moved ML/G-API to contrib.
- Design for CPU/Graviton (`arm64`). The OpenCV 5 DNN engine has no GPU support.
- Keep the agentic loop in the product, not in the development process. Every agent decision must be reconstructible from a trace, including the numeric value that triggered it.
- Pin dependencies to exact versions in `requirements.txt`. The image installs `requirements.lock`
  with `--no-deps`, so after changing a direct dependency regenerate it with
  `docker compose run --rm --no-deps app pip freeze > requirements.lock`.
- Keep all repository output in English: code, docs, commits, and CI. The only exception is UI copy in `services/ui/text.py`, which must be bilingual English/Spanish. English is both the default and the per-key fallback. Plain and technical registers use `_plain` and `_tech` key suffixes resolved by `strings(lang, register)` before templates receive the copy. Plain is the default. Add register variants only when prose genuinely differs; button labels, units, and metric names do not need variants.

## Project Structure & Module Organization

Application code lives under `services/`, split by responsibility: `agent/` orchestrates inspections, `perception/` analyzes images, `memory/` persists runs and assets, `observability/` records traces, `api/` exposes endpoints, and `ui/` contains views, templates, and static assets. Keep tests beside their module in `services/<module>/tests/`. Evaluation code, scenarios, datasets, and published results belong in `eval/`. Infrastructure is under `infra/`; project documentation is under `docs/`; demo-production utilities live in `video/`.

## Build, Test, and Development Commands

The supported workflow uses Docker Compose and `make`:

- `make weights` downloads the 52 MB ALIKED and LightGlue ONNX weights and verifies their SHA-1 hashes.
- `make dev` starts LocalStack with S3 and DynamoDB, then serves Uvicorn on port 8000.
- `make build` builds the application container.
- `make test` runs all `pytest` suites in the container, enforces 90% service coverage, and stops Docker Compose afterward.
- `make lint` checks `services/` and `eval/` with Ruff.
- `make typecheck` runs mypy over `services/` and `eval/`.
- `make verify-runtime` confirms the required OpenCV 5 runtime.
- `make demo` runs the scripted driver through the four action branches. To use Gemini, set `GOOGLE_API_KEY` and run `docker compose run --rm app python -m services.agent.demo --live`.
- `make eval` scores the 29 reproducible scenarios and updates `eval/results/latest/`; additional options can be passed through `ARGS`.
- `make deploy` deploys through ECR, buildx for `arm64`, and CloudFormation; it requires `GOOGLE_API_KEY`.

Run everything in the `arm64` container. There is no local `cv2`, so plain host-side `pytest` does not work. Neural-path tests and the `dev`, `test`, `demo`, `eval`, and `deploy` workflows require the downloaded weights. To run one test:

```bash
docker compose run --rm --build app python -m pytest services/agent/tests/test_loop.py::test_name -v
```

Before submitting a change, run the checks relevant to it; for code changes, prefer the full CI sequence: build, runtime verification, lint, type-check, and tests.

## Architecture

One FastAPI application in `services/api/app.py` serves the UI and runs the agent loop inside the request. It is deployed as a single `arm64` Lambda container behind a Function URL.

- `services/perception/` contains pure NumPy/OpenCV functions for quality, alignment, diffing, and severity. They return raw metrics and never make decisions. Alignment uses OpenCV 5 `Features` with ALIKED and LightGlue ONNX, falling back to ORB when `weights.neural_weights_available()` reports missing weights.
- `services/mcp_server/server.py` exposes the five perception tools over MCP stdio using S3 keys instead of arrays. This is the only surface visible to the LLM.
- `services/agent/policy.py` is the only place where branches are decided. `Policy` owns every threshold, and `evaluate(stage, metrics, policy)` returns a `decision()` record with the metric, value, threshold, and branch. No other code may compare a metric to a constant.
- `services/agent/loop.py` orchestrates execution. The LLM selects arguments and phrasing; the loop enforces the next tool through `NEXT_TOOL` and rejects a `submit` whose branch differs from the last policy verdict. Without `GOOGLE_API_KEY`, it uses `scripted.PolicyFollowingLLM` so tests and evaluation remain deterministic.
- `services/memory/` uses one DynamoDB table with `pk=ASSET#id` and `sk` values `META`, `INSPECTION#ts#id`, or `BASELINE#ts`, returning an asset's history in one query. `META` stores the latest inspection's capture key, timestamp, label, and branch, allowing the `/` gallery to use one scan without per-asset queries. Run `python -m services.memory.backfill [--dry-run]` once to fill summaries for older assets. Images live in S3 at `assets/{asset_id}/{inspection_id}/{name}.png`; baselines are superseded, never overwritten. `runs.py` stores run artifacts locally or in S3 under `runs/` when `AFTERIMAGE_RUNS_S3=1`.
- `services/observability/trace.py` writes append-only `events.json` files per run with `run_started`, `tool_call`, `decision`, `approval_requested`, and `run_finished` events. Events are the causal record and the source of in-progress state, including the claim that prevents ordinary duplicate execution. Finished and pending runs also use `state.json` and `pending.json` materializations.
- `services/agent/hitl.py` implements the human gate. A severe finding writes `pending.json` instead of committing; approval commits the inspection and promotes the baseline.
- `services/ui/` contains autoescaped Jinja2 templates and hashed static assets, rendered by `views.py` and served through the API.

Environment variables are `AFTERIMAGE_TABLE`, `AFTERIMAGE_BUCKET`, `AFTERIMAGE_WEIGHTS_DIR`, `AFTERIMAGE_RUNS_DIR`, `AFTERIMAGE_RUNS_S3`, `AFTERIMAGE_GEMINI_MODEL`, and `GOOGLE_API_KEY`. Override any `Policy` field with `AFTERIMAGE_<FIELD_NAME_UPPER>` through `Policy.from_env()`.

## Coding Style & Naming Conventions

Use Python 3.12, four-space indentation, descriptive `snake_case` names for functions and modules, and `PascalCase` for classes. Ruff enforces import ordering and the selected `E`, `F`, and `I` rules; the 100-character limit in `pyproject.toml` is the formatter's, not an enforced lint. Keep modules focused on one responsibility, reuse shared logic, and do not hide exceptions. Avoid comments or docstrings that merely restate the code.

## Testing Guidelines

Tests use `pytest`; files and test functions follow `test_*.py`. Add focused regression tests beside the affected module. Preserve deterministic, offline evaluation data and update published metrics only through `make eval`. Coverage must remain at or above 90% for `services/` and `eval/` together, the same scope lint and type checking use.

## Required Gates

- `eval/tests/test_published_numbers.py` validates figures in `README.md`, `docs/EVALUATION.md`, `docs/TECHNICAL_REPORT.md`, and `video/script.tsv` against `eval/results/latest/results.json`. The `eval` job in CI scores the dataset again and `eval/compare_results.py` fails when the committed artefact no longer matches a fresh run. After changing a threshold or perception metric, rerun `make eval` and update every published number.
- `services/perception/tests/test_import_safety.py` imports every non-test module under `services/` with a bare environment. No module may require configuration, weights, or AWS at import time; use cached client factories.
- `docs/` and `README.md` are part of the deliverable. Changes to the loop, a threshold, or an endpoint usually require updates to `docs/TECHNICAL_REPORT.md` and the README flowchart.

Deliberate shortcuts use `ponytail:` comments that name the limitation and its upgrade path. Preserve this convention when intentionally accepting a limitation.

## Commit & Pull Request Guidelines

Write concise, imperative commit subjects such as `Add six real photographs.` or `Refactor frontend architecture.` Keep each commit scoped to one coherent change. Pull requests should explain user-visible behavior, list verification commands, link relevant issues, and include screenshots or trace evidence for UI or inspection-flow changes. CI must pass before merge.

## Security & Configuration

Never commit API keys, AWS credentials, or generated secrets. Supply `GOOGLE_API_KEY` through the environment and follow `docs/SECURITY.md` plus the OIDC deployment guidance in `README.md`.
