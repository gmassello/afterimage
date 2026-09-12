# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# afterimage

Visual inspection agent with longitudinal memory, built for the OpenCV AI Competition 2026.

Full brief, rules, architecture and weekly plan: see `docs/BRIEF.md`.

## Hard rules for every coding session

- OpenCV 5 only. Verify every OpenCV API against https://docs.opencv.org/5.x/ before using it — model training data covers OpenCV 4, and OpenCV 5 broke compatibility (`Features2D` replaced by `Features`, C API removed, ML/G-API moved to contrib).
- Design for CPU/Graviton (arm64). The OpenCV 5 DNN engine has no GPU support.
- The agentic loop lives in the product, not in the development process. Every agent decision must be reconstructible from a trace, with the numeric value that triggered it.
- Pin dependencies to exact versions in `requirements.txt`.
- All repo output in English: code, docs, commits, CI.

## Commands

Everything runs in the arm64 container — there is no local `cv2`, so plain `pytest` on the host will not work.

```bash
make weights   # ALIKED + LightGlue ONNX weights into models/ (52 MB, sha1 verified); prerequisite of every other target
make dev       # compose up: LocalStack (S3 + DynamoDB) + uvicorn on :8000
make test      # full suite (services/ + eval/) in the container, then compose down
make demo      # scripted driver through the four action branches
make eval      # score the 23 scenarios; writes eval/results/latest/  (ARGS=... is forwarded)
make deploy    # ECR + buildx arm64 + CloudFormation; needs GOOGLE_API_KEY
```

One test, one file, one keyword:

```bash
docker compose run --rm --build app python -m pytest services/agent/tests/test_loop.py::test_name -v
```

`make demo` uses the scripted driver. To let Gemini order the tool calls, set `GOOGLE_API_KEY` and add `--live`.

## Architecture

One FastAPI app (`services/api/app.py`) serves the UI and runs the agent loop inside the request, deployed as a single arm64 Lambda container behind a Function URL.

- `services/perception/` — pure numpy/OpenCV functions (quality, alignment, diffing, severity). They return raw metrics and never decide anything. Alignment uses OpenCV 5 `Features` (ALIKED + LightGlue ONNX), with ORB as the fallback when weights are missing (`weights.neural_weights_available()`).
- `services/mcp_server/server.py` — the five perception tools over MCP stdio, taking S3 keys instead of arrays. This is the only surface the LLM sees.
- `services/agent/policy.py` — the single place a branch is decided. `Policy` holds every threshold; `evaluate(stage, metrics, policy)` returns a `decision()` record carrying metric, value, threshold and branch. Nothing else in the codebase may compare a metric to a constant.
- `services/agent/loop.py` — orchestration. The LLM picks arguments and phrasing; the loop enforces which tool comes next (`NEXT_TOOL`) and refuses a `submit` whose branch differs from the last policy verdict. Without `GOOGLE_API_KEY` it falls back to `scripted.PolicyFollowingLLM`, so tests and eval run deterministically without a model.
- `services/memory/` — one DynamoDB table (`pk=ASSET#id`, `sk` in `META` / `INSPECTION#ts#id` / `BASELINE#ts`) returning an asset's whole history in one query; images in S3 under `assets/{asset_id}/{inspection_id}/{name}.png`; baselines superseded, never overwritten. `runs.py` reads/writes run artefacts to the local FS or to S3 under `runs/` when `AFTERIMAGE_RUNS_S3=1`.
- `services/observability/trace.py` — append-only `events.json` per run (`run_started`, `tool_call`, `decision`, `approval_requested`, `run_finished`). The trace is the only record of a run; run state is derived from it, including the claim that stops a run being executed twice.
- `services/agent/hitl.py` — the human gate. A severe finding writes `pending.json` instead of committing; approval commits the inspection and promotes the baseline.
- `services/ui/` — Jinja2 templates with autoescaping plus hashed static assets, rendered by `views.py` and served through the API.

Environment: `AFTERIMAGE_TABLE`, `AFTERIMAGE_BUCKET`, `AFTERIMAGE_WEIGHTS_DIR`, `AFTERIMAGE_RUNS_DIR`, `AFTERIMAGE_RUNS_S3`, `AFTERIMAGE_GEMINI_MODEL`, `GOOGLE_API_KEY`. Any `Policy` field is overridable as `AFTERIMAGE_<FIELD_NAME_UPPER>` (`Policy.from_env()`).

## Gates that will fail on you

- `eval/tests/test_published_numbers.py` asserts the figures in `README.md`, `docs/EVALUATION.md`, `docs/TECHNICAL_REPORT.md` and `video/script.tsv` against `eval/results/latest/results.json`. Touch a threshold or a perception metric → rerun `make eval` and update every published number.
- `services/perception/tests/test_import_safety.py` imports every non-test module under `services/` with a bare environment: no module may need configuration, weights or AWS at import time (hence the `lru_cache`d client factories).
- `docs/` and the README are part of the deliverable. A change to the loop, a threshold or an endpoint usually means editing `docs/TECHNICAL_REPORT.md` and the README flowchart too.

Deliberate shortcuts are marked with `ponytail:` comments naming the ceiling and the upgrade path; keep that convention when you cut a corner on purpose.
