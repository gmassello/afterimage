# afterimage — master plan

Visual inspection agent with longitudinal memory for the OpenCV AI Competition 2026
(Agentic Vision path). Submit on **24 or 25 October**; the 26th is a cushion, not a working day.

The competition's week-by-week plan lives in `docs/BRIEF.md` §4. This file is the living state: what
is closed, what comes next, and the detail of the stages that already have a design.

**Today is 25 August.** The brief's calendar starts week 1 on 26 August, so the project is running
**about ten days ahead**. That margin is real and worth not spending.

---

## State

| # | Stage | State |
|---|---|---|
| 1 | Scaffolding — arm64 Docker, OpenCV 5, LocalStack, CI | **closed** |
| 2 | Perception — the five tools | **closed** |
| 2.5 | Publish the manual on GitHub Pages | **files ready, commit and push pending** |
| 3 | Memory bank — DynamoDB + S3 | **closed** |
| 4 | MCP + agentic loop + policy + human gate | **closed** |
| 5 | Observability — OTel spans, trace endpoint | pending |
| 6 | AWS deploy + front end + public endpoint | pending |
| 7 | Evaluation — dataset, metrics, failure cases | pending |
| 8 | Technical report and documentation | pending |
| 9 | Video, polish, submission | pending |

### Closed in stage 1

An arm64 `Dockerfile` with `opencv-python-headless==5.0.0.93`, a `docker-compose.yml` with
LocalStack, a `Makefile`, CI on `ubuntu-24.04-arm`, and a smoke test S3 → Laplacian variance.

### Closed in stage 2

The five tools of `services/perception/`, green in an arm64 container (`aarch64`, OpenCV 5.0.0),
zero skips. Committed and pushed as `497f75d`.

The design decision that governs everything downstream: **perception reports numbers, not verdicts.**
Thresholds live in the policy (stage 4). Without that separation there is no way to demonstrate that
an OpenCV value changed a decision, which is the hard requirement of the Agentic award.

Measured numbers that stage 4 will need:

| pair | ORB | ALIKED + LightGlue |
|---|---|---|
| same panel, rotated and scaled | 0.409 | 0.997 |
| a different panel | 0.038 | 0.407 |
| pure noise | 0.020 | 0.000 |

⚠️ **`inlier_ratio` is not comparable across detectors.** A shared threshold would make the ORB
fallback declare "unrecognised asset" every time. The policy needs one threshold per detector.

Other facts verified against the binary, not against the docs: `AKAZE`/`KAZE`/`BRISK` moved to
contrib and are not in the headless wheel; ALIKED and LightGlue need two external ONNX files (52 MB,
sha1 verified by `make weights`); `setPairInfo` goes before every `match()`; alignment takes ~1.5 s
on CPU and the OpenCV 5 DNN engine has no GPU.

### Closed in stage 3

`services/memory/`, **22 tests green in an arm64 container, zero skips**. A single module touches
each backend, which is what makes them mockable: `store.py` is the only one with DynamoDB,
`images.py` the only one with S3.

Single table — everything belonging to an asset shares a partition key, so the complete history is
one `query` and nothing more:

| SK | What it is |
|---|---|
| `META` | the asset |
| `INSPECTION#<captured_at>#<inspection_id>` | one capture and its metrics |
| `BASELINE#<captured_at>` | the current baseline, carrying `superseded_by` once it stops being current |
| `EVENT#…` | reserved for stage 5, not written yet |

The baseline is an item of its own rather than a flag on the inspection: retrieving it is one small
read regardless of how many inspections exist, and the chain of superseded baselines *is* the
longitudinal history.

**No `valid_until`, unlike `recall`.** An expiry is a threshold, and thresholds live in `policy.py` —
the same rule that already governs perception. Memory stores `captured_at` and `quality_score`; who
decides that a baseline is stale is the policy.

DynamoDB rejects `float` and returns `Decimal`. A one-line round trip on each side, stdlib only:
`json.loads(json.dumps(item), parse_float=Decimal)` on write, `default=float` on read.

#### The bug the closing test found

⚠️ **`warpPerspective` leaves black whatever the homography did not cover, and the diff read that as
the largest change in the frame.** With the panel rotated and scaled it was 8.96% of the frame; the
cracked cell (area 2923) was buried under a border blob of area 18010, and `classify_severity`
returned `unknown` instead of `crack`.

It was not a test artefact: any badly framed recapture produces it, and it inflates `changed_ratio`,
which is exactly the metric the policy branches on in stage 4.

The fix goes where every caller routes through: `align_to_baseline` also warps a white mask with the
same homography and erodes it by 9px — more than the diff's blur radius — and `diff_against_memory`
accepts that mask. With it there is **a single region left, the cracked cell**, and severity returns
to `crack` with `brightness_delta` −30.6, consistent with the −28.7 measured on fixtures.

`crop_and_rescan` does not take a mask yet: its regions already come from the masked diff. If the
crop margin reaches the invalid border, stage 4 will see it.

---

### Closed in stage 4

`services/mcp_server/` + `services/agent/`, **45 tests green in the arm64 container** (23 new), and
`make demo` drives the four action branches end to end against the real MCP server and LocalStack.

The design decision that satisfies the award's hard requirement: **the policy evaluates agent-side,
in code, after every tool result.** MCP tools return perception metrics only; `loop.py` runs
`policy.evaluate(stage, metrics)` and records `{"input_metric", "value", "threshold", "branch"}` —
pass verdicts included — before injecting the verdict into the function response the LLM sees. The
LLM (Gemini, `google-genai`, manual `FunctionDeclaration` conversion so its automatic function
calling can never bypass the injection) orchestrates and phrases the operator message; it cannot
override a verdict — a `submit` with the wrong branch comes back as an error tool result naming the
mandated one. Causality is a field, not prompt archaeology.

One threshold per detector, as stage 2 demanded: `inlier_ratio_min_neural=0.90`,
`inlier_ratio_min_classic=0.30`. The other defaults were pinned by measuring the fixtures in the
container, and two of them moved off the plan's guesses:

| metric | measured | default pinned |
|---|---|---|
| `blur_variance` clean / blurred / warped recapture | 367.6 / 1.8 / ~173 | `min 100` — the warp's interpolation eats half the variance |
| region `mean_delta` faint spot / crack | 32.7 / 46.6 | `confirm 35` — CLAHE amplifies the raw pixel delta of 22 |
| `coverage_ratio` clean panel | 0.001 | check disabled (0.0) — the contour heuristic reads ~0 on synthetic fixtures; ponytail-marked, raise via env on real captures |

The HITL gate is a partition, not a branch: on `human_approval` the loop persists
`runs/{run_id}/pending.json` and returns `awaiting_approval`; the memory write lives in
`hitl.resolve()`, reached by `--resume RUN_ID --approve|--reject` or an interactive y/n. Stage 6's
approval queue is "list `runs/*/pending.json`, call `resolve()`".

Facts verified against the binaries, not the docs:

- **`mcp` 2.x renamed FastMCP to `MCPServer`** (`mcp.server.mcpserver`); tool results arrive as JSON
  text content, and `structured_content` stays `None` unless the tool declares an output schema —
  the loop parses `content[0].text`.
- `Tool.input_schema` (snake_case) feeds `google-genai`'s `parameters_json_schema` directly — no
  hand-written schema conversion.
- ⚠️ **LocalStack state survives `docker-compose run`.** Only `down` clears it. The stage-4 tests use
  unique asset ids per run; `test_longitudinal.py` (stage 3) has fixed ids and fails against a warm
  LocalStack left by manual runs — `make test` is safe because it tears down, but a stray
  `docker-compose run` session before it is not.
- The "different panel" that alignment must reject needs different *geometry*
  (`solar_panel(seed=99, rows=4, cols=7, cell=80)`); a different seed with the same grid aligns at
  0.99+ because the cell layout is the feature.

Deps added, pinned: `mcp==2.1.1`, `google-genai==2.20.0`. Model default `gemini-2.5-flash`,
overridable via `AFTERIMAGE_GEMINI_MODEL`; tests and the default demo use scripted drivers
(`ScriptedLLM`, `PolicyFollowingLLM`) — no network, no key, deterministic. `--live` switches the
same loop to the real API.

## Stage 2.5 — Publish the manual on GitHub Pages

Low cost, and it can happen any time before stage 8; doing it early gives a public URL to link from
everywhere else.

### Verified state of the repo

- `github.com/gmassello/afterimage` is **public**; `main` in sync.
- **Pages is not enabled** (the API returns 404).
- The `gh` token has `repo` scope, enough to enable it over the API.

### The format conflict, which is not obvious

Artifact and Pages want the **opposite** thing. The Artifact runtime wraps the file in its own
`<!doctype html>…<head>…</head><body>`, so the source file carries none of those tags. Pages serves
the file as-is: without `<meta name="viewport">` a phone renders it at 980px wide and you have to
pinch-zoom to read it.

Resolved in this order:

1. `docs/index.html` is **canonical**, a complete standard HTML document. The public destination wins.
2. Republish the Artifact from that same file and **open the URL to see how it came out**. Browsers
   tolerate nested `<html>`/`<head>`/`<body>`, so it will probably render fine — but that gets
   verified by looking, not by reasoning.
3. If the nesting breaks something, the Artifact is deprecated and Pages is the only destination. No
   second file kept in parallel.

### Changes

**`docs/index.html`** — the manual content wrapped in a complete document. The `<head>` gained:
`charset`, **`viewport`** (the one that decides whether it is readable on a phone), `<html lang="en">`,
`<meta name="description">`, Open Graph / Twitter card without `og:image` (there is no image worth
using, and a bad one is worse than none), `<link rel="canonical">`, and a three-line reset the
Artifact runtime gave for free and Pages does not. The Google Fonts `<link>` stays: on Pages there is
no CSP blocking it.

**`docs/.nojekyll`** — empty. Without it, Jekyll would try to render `BRIEF.md`, `PLAN.md` and
`SUBMISSION.md` as site pages. They stay readable in the repo, but they have no business being pages.
The deploy is also faster.

**`README.md`** — the link at the top, where it is visible without scrolling.

**Local commit, no push.** Agreed scope: the push and enabling Pages are done by hand.

### What gets run by hand

```bash
git push

# Settings → Pages → Source "Deploy from a branch" → main → /docs → Save
# or, equivalently:
gh api -X POST repos/gmassello/afterimage/pages \
  -f 'source[branch]=main' -f 'source[path]=/docs'

# optional, after the first deploy:
gh repo edit --homepage https://gmassello.github.io/afterimage/
```

### Verification, all of it done before pushing

`docs/index.html` was served over local HTTP and inspected in Chrome: the three IBM Plex faces load
for real (falling back shows up in the headings), the SVG renders complete, the tables do not
overflow. Dark theme forced, and no text ends up illegible — that is the classic failure mode of a
page built on colour tokens. Narrowed to phone width: the body does not scroll horizontally and the
diagram scrolls inside its own container.

⚠️ This is **not** the "working web endpoint" the rubric asks for. That one is the app on AWS, stage 6.

---

## Stages 5 to 9

Goal and closing condition for each, per `docs/BRIEF.md` §4, plus what is reusable from the author's
three previous repos (`recall`, `hindsight`, `ringdown`), already reviewed.

### 5 — Observability

One span per tool call with inputs, metrics and the resulting decision. `GET /traces/{run_id}`
readable by a human. Closes with a trace where an OpenCV value visibly changed the next decision.

The field `hindsight` **did not** have and that is mandatory here:

```json
{"input_metric": "inlier_ratio", "value": 0.259, "threshold": 0.5, "branch": "unrecognized_asset"}
```

In `hindsight` causality ran through the prompt, not through a field: you could not *prove* that a
value changed the decision, only infer it. Its other three debts, all to avoid: the trace stored the
tool's arguments but not what it returned; the browser set the timestamp; and the store was an
in-memory dict with a one-shot stream, so the trace did not survive a restart and could not be shared
by link. Hence: persisted `events.json` + `state.json`, and an idempotent `GET /traces/{run_id}`.

From `hindsight`, the good part: **one event generator, three renderers** (CLI, SSE and file) with no
extra code.

### 6 — AWS deploy + front end + public endpoint

ECS Fargate arm64 or equivalent, S3 + DynamoDB, IaC, minimal front end. Closes with a public URL a
judge can use.

From `recall`: a GitHub OIDC stack **separate from the app stack**, with a permissions boundary — it
saves half a day, and the trap in the `sub` claim (GitHub emits immutable IDs, not names) is
documented. Plus an idempotent `deploy.sh`: credential preflight, detecting and deleting a stack in
`ROLLBACK_COMPLETE`, arm64 build.

From `ringdown`: the entire front end is 123 lines of FastAPI returning HTML, with 13 of CSS and a
3-line auto-refresh. For "history + approval queue" that is literally enough.

⚠️ **The endpoint cannot go to sleep.** Judging runs from 27 October to 9 November and a judge will
open the link. Budget AWS through 10 November.
⚠️ **No Basic Auth**: it opens a native dialog that blocks browser automation, and that breaks both
the video recording and any screenshot.

### 7 — Evaluation

Dataset, metrics, **failure cases** (an explicit requirement). Closes with a table of precision,
recall and honest limitations.

From `hindsight`: declarative failure scenarios in YAML with `prepare`/`run`/`reset` — they map
directly onto a blurry photo, an overexposed one, a missing panel, a missing baseline. **Deterministic
replay** from the run artefact, with no network and no model, which then feeds the video demo without
depending on live infrastructure. And **verification through a second channel**: re-reading every
write by a different route than the one that wrote it — in `hindsight` that found a real bug the
agent was reporting as a success.

This is also where it gets decided whether the threshold heuristic in `severity.py` holds up or needs
a trained classifier. The `# ponytail:` comment in the code marks that ceiling.

### 8 — Technical report and documentation

A complete `docs/TECHNICAL_REPORT.md`, both diagrams, pinned deps, instructions that work on a clean
machine. `docs/SUBMISSION.md` already exists and has been filling up since stage 2.

From `hindsight`: `test_readme_claims.py`, which parses the README's results table and checks every
cell against the run artefacts — if a number in the README lies, CI fails. And the sections that win
rubric points: a claim → file-where-it-is-verified table, and `Known ceilings` with no makeup on.

### 9 — Video, polish, submission

A video ≤ 5 min **with the author's face** (an explicit requirement). The script gets written in
stage 7 so that development aims at making the demo look good.

From `recall` and `hindsight`: the complete working pipeline — `narration.tsv` (4 columns, phonetic
`speak`) → `build-audio.sh` → `build-video.sh`. **Audio is built first and is authoritative**, the
video stretches to fit. Subtitles burned in, not just an `.srt`, for the judge who hits play without
sound. Copy the scripts, rewrite only the TSV.

---

## Anti-patterns seen in the three previous repos

- **Always test the container locally.** `ringdown` could not and trusted the provider's build. Here
  it is arm64 + OpenCV 5 + 52 MB of ONNX: that road ends with a build failing in CI three days before
  the deadline. (Colima was down; it was brought up and the build was verified.)
- **Validate the key integration early.** `ringdown`'s central thesis failed against the real provider
  and it was discovered during video week. That is why the ALIKED spike is already done.
- **One LLM provider only.** `hindsight` has 337 lines for four and used one; `recall` three. It is
  the largest block of unexercised code in both.
- **Do not abstract with a single case.** `recall` has a `Protocol` with one implementation and admits
  it in its own SUBMISSION.
- **One `requirements.txt` only.** `recall` kept two, they diverged, and the deploy failed on import.
- **Do not squash git history.** In a competition the history *is* evidence.
- **Deterministic demo.** `recall`'s video story depended on a score tuned by hand.
