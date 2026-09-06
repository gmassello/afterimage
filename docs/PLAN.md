# afterimage — master plan

Visual inspection agent with longitudinal memory for the OpenCV AI Competition 2026
(Agentic Vision path). Submit on **24 or 25 October**; the 26th is a cushion, not a working day.

The competition's week-by-week plan lives in `docs/BRIEF.md` §4. This file is the living state: what
is closed, what comes next, and the detail of the stages that already have a design.

**Stage 8 closed on 2 September** against a brief that schedules it for 14 – 20 October, so the
project is running **about six weeks ahead**. That margin is real and worth not spending.

---

## State

| # | Stage | State |
|---|---|---|
| 1 | Scaffolding — arm64 Docker, OpenCV 5, LocalStack, CI | **closed** |
| 2 | Perception — the five tools | **closed** |
| 2.5 | Publish the manual on GitHub Pages | **closed** — live at https://gmassello.github.io/afterimage/ |
| 3 | Memory bank — DynamoDB + S3 | **closed** |
| 4 | MCP + agentic loop + policy + human gate | **closed** |
| 5 | Observability — per-run event trace, trace endpoint | **closed** |
| 6 | AWS deploy + front end + public endpoint | **closed** — live at https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/ |
| 7 | Evaluation — dataset, metrics, failure cases | **closed** — 23 scenarios, branch accuracy 0.8696, see `docs/EVALUATION.md` |
| 8 | Technical report, diagrams and video script | **closed** — see `docs/TECHNICAL_REPORT.md` |
| 9 | Video, polish, submission | **wip** — first cut shot and assembled (4:44.9); being re-cut with a 14 s cold open and the face in the corner box throughout (`video/hook.py`, `video/PRODUCTION.md`). Outstanding: re-record the seven clips and the screencast, assemble, upload, and open the endpoint from another network |

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
| `EVENT#…` | reserved; stage 5 kept its events on disk (`runs/{run_id}/events.json`), so it stays unwritten unless a cloud consumer needs it |

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
`hitl.resolve()`, reached by `--resume RUN_ID --approve|--reject` or an interactive y/n. Stage 6
built exactly that queue: `GET /queue` lists the pending payloads (S3 prefix in prod, disk glob
locally) and `POST /queue/{run_id}/approve|reject` calls `resolve()`.

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

Deps added, pinned: `mcp==2.1.1`, `google-genai==2.20.0`. Model default `gemini-3.6-flash` (it was `gemini-2.5-flash`
until the stage-6 deploy hit its retirement — see "Closed in stage 6"),
overridable via `AFTERIMAGE_GEMINI_MODEL`; tests and the default demo use scripted drivers
(`ScriptedLLM`, `PolicyFollowingLLM`) — no network, no key, deterministic. `--live` switches the
same loop to the real API.

### Closed in stage 5

`services/observability/` + `services/api/`, **54 tests green in the arm64 container** (the trace
assertions live inside the two stage-4 loop tests that already exercised those branches, instead of
duplicating their expensive LocalStack runs). `make demo` now prints each scenario's full trace and
re-prints it after the human gate resolves; `make dev` serves the trace endpoint on port 8000.

The design decision, taken against the BRIEF's literal wording: **no OpenTelemetry SDK — a plain
persisted event log with span-shaped events.** What the judges see is the output of
`GET /traces/{run_id}`, not the SDK behind it; and OTel attributes cannot carry nested dicts, so
`args`, `metrics` and the verdict would have been `json.dumps`-ed into strings inside the span and
decoded back out — pure wrapping. If stage 8 wants the word "OpenTelemetry" in the report, an
adapter re-emitting the same events as OTel spans is one isolated file. Zero new deps for the
tracing itself.

Each `tool_call` event is the span: `tool`, `args`, `duration_ms`, `metrics` (or `error`) and the
policy verdict nested under `policy` — emitted as **one** event after the verdict is computed, so
the span→verdict link travels through data flow, not file position. `run_started`, `decision`
(first-baseline and the human resolution from `hitl.resolve`), `approval_requested` and
`run_finished` complete the log.

`hindsight`'s three debts, closed: the span stores the tool's arguments **and** what it returned;
`trace.emit` stamps every timestamp server-side; and disk is the source of truth
(`runs/{run_id}/events.json`), so the trace survives a restart and is shared by link.
`decisions.json` and `state.json` are written unchanged — `events.json` subsumes `decisions.json`
conceptually, but the dual write stays until a stage-6+ consumer justifies removing it.

`GET /traces/{run_id}` (`services/api/app.py`, FastAPI): JSON by default, HTML when the request
sends `Accept: text/html`, 404 both for a run with no events on disk and for anything not matching
`^[0-9a-f]{12}$` (the path-traversal boundary, shared as `trace.RUN_ID_PATTERN`). It reads from
disk on every request — idempotent by construction. Runs root via `AFTERIMAGE_RUNS_DIR`.

From `hindsight`, the good part, kept: **one event generator** (`trace.emit`) and renderers as pure
functions over the same events — `render_text` (CLI: `python -m services.observability.render
RUN_ID`) and `render_html` (the endpoint). **SSE deferred to stage 6** with the front end that will
consume it: re-read `events.json`, emit the delta, ~20 lines.

Deps added, pinned: `fastapi==0.141.1`, `uvicorn==0.52.4`, `httpx==0.28.1` (the TestClient
transport).

### Closed in stage 6

`services/api/` grew from one endpoint to the whole product, `infra/` holds the two stacks, and
**62 tests green in the arm64 container** (8 new). The public app: `/` (assets + upload),
`/assets/{id}` (history with baselines), `/queue` (the human gate), `/traces/{run_id}` (unchanged),
`/health`, `/images/{key}`.

The compute decision, taken against the brief's literal wording: **Lambda container image arm64 +
Lambda Web Adapter + Function URL, not ECS Fargate.** Same Graviton silicon, near-zero cost, no
ALB, and the existing Dockerfile gained only two lines (the LWA extension copy and a `CMD`); the
compose stack is untouched because the extension is inert outside the Lambda runtime. Cold start is
mitigated by an EventBridge rule that replays a `/health` Function URL event every 5 minutes.

The consequence: `runs/` left the local disk. `services/memory/runs.py` is the single storage seam —
disk by default (tests, demo, CLI unchanged), S3 under `runs/{run_id}/` in the app bucket when
`AFTERIMAGE_RUNS_S3=1` (the Lambda env). The env var is read inside each call, never at import —
the module-level trap that would have frozen the choice at first import. `trace.emit`, the loop,
`hitl` and the renderers all route through it; traces now survive redeploys and are shared by link.

The judge-facing run is **live Gemini**: `POST /inspections` runs the loop synchronously inside the
request (BackgroundTasks dies when the Lambda sandbox freezes; the Function URL allows up to 15
minutes and a live run takes ~30-60 s) and 303-redirects to the trace. Without `GOOGLE_API_KEY`
the same endpoint falls back to the deterministic `PolicyFollowingLLM` — which is what the endpoint
tests exercise, no network, no key.

Anti-abuse, deliberately minimal: 6 MB upload cap (`services/api/app.py`, the Function URL body limit), `^[a-z0-9-]{1,64}$` on asset ids, and
`ReservedConcurrentExecutions: 10` as an infra-level rate limit. No auth — Basic Auth breaks the
video recording (a lesson already paid for).

IaC split: the app stack (`infra/template.yaml`, SAM) owns table, bucket
(`afterimage-${AccountId}`, 60-day lifecycle so nothing expires inside the judging window), log
retention and the warmer; `infra/github-oidc.yaml` (one manual deploy, `CAPABILITY_NAMED_IAM`)
owns the OIDC provider, the deploy role and the permissions boundary scoped to exactly the table
and bucket. `ensure_table`/`ensure_bucket` remain LocalStack-only — the Lambda role cannot create
resources, by design. ECR is created idempotently by `deploy.sh`, which also carries recall's
lessons: credential preflight, `ROLLBACK_COMPLETE` deletion, secrets via a deleted temp file, and
`--provenance=false` on buildx — **Lambda rejects buildx manifest lists**.

Facts verified against the binaries, not the docs:

- `ensure_bucket()` was broken outside us-east-1 (`create_bucket` needs `CreateBucketConfiguration`
  there) and only caught `BucketAlreadyOwnedByYou`; fixed for both.
- FastAPI needs `python-multipart` for `Form`/`File` — added, pinned (`0.0.32`).
- The sub claim in the OIDC trust policy uses immutable IDs:
  `repo:gmassello@12966514/afterimage@1344329963:ref:refs/heads/main`.

Deps added, pinned: `python-multipart==0.0.32`.

### Deployed — what the first deploy cost, in facts

Live at **<https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/>** in account `236058984017`
(the same one `recall` uses), us-east-1, deployed 2 September from GitHub Actions over OIDC. The
bootstrap ran once by hand from CloudShell, so no AWS credential ever touched a local disk.

Four things only a real deploy could have found. The first two were caught before spending a
deploy, by reading the account instead of trusting the template:

- ⚠️ **The OIDC provider already existed.** `recall/infra/github-oidc.yaml` creates
  `AWS::IAM::OIDCProvider` for `token.actions.githubusercontent.com`, and AWS allows exactly one
  per URL per account. The resource left this template; the role now references the deterministic
  ARN `arn:aws:iam::${AWS::AccountId}:oidc-provider/token.actions.githubusercontent.com`.
- ⚠️ **The S3 lifecycle expired inside the judging window.** `ExpirationInDays: 60` from a
  2 September deploy deletes everything on 31 October — judging runs 27 October to 9 November, so
  the demo baselines and traces would have vanished mid-evaluation. Now 180.
- ⚠️ **`ReservedConcurrentExecutions: 10` cannot be set in this account.** Its Lambda quota *is* 10
  concurrent executions and AWS refuses to reserve any while keeping 10 unreserved, so no value is
  valid. Dropped: the account limit already imposes the same ceiling the property was buying.
- ⚠️ **`gemini-2.5-flash` is retired for new users** (`404 NOT_FOUND`, "Please update your code to
  use models/gemini-3.6-flash"). Migrating the default surfaced the real bug below.

#### The bug the deploy found

⚠️ **Gemini 3.x signs every `functionCall` it emits, and the loop threw the signature away.**
`llm._content()` rebuilt each model turn with `types.Part.from_function_call(name, args)` — which
carries no signature — so the next request came back `400 INVALID_ARGUMENT: Function call is
missing a thought_signature in functionCall parts`. It never appeared under `gemini-2.5-flash`,
which signs nothing; it is structural to thinking models and would have broken every multi-turn run.

The fix travels through data, like the policy verdict does: `ToolCall` gained
`thought_signature: bytes | None`, `generate()` reads `part.thought_signature` off the response and
`_content()` assigns it back onto the rebuilt part. Verified against the SDK, not the docs: the
field is `Part.thought_signature` (`bytes`), `from_function_call()` does not accept it, and the
round trip serialises `{function_call, thought_signature}` to the wire.

#### Verified against the public URL, not localhost

Six of the seven branches, driven by real Gemini and real captures over HTTPS:

| branch | the number that triggered it |
|---|---|
| `first_baseline` | `baseline_exists` 0 vs 1 |
| `recapture` (ACTION 1) | `blur_variance` 1.77 vs 100 |
| `aligned` | `inlier_ratio` 1.0 vs 0.90 — ALIKED + LightGlue, 23.3 s on Graviton |
| `change_confirmed` → `human_approval` (ACTION 4) | `mean_delta` 60.65 vs 35, then `score` 0.449 vs 0.40 |
| resolved gate | `human_approved` 1.0 → `approved` |
| `auto_write` | `score` 0.285 vs 0.40 |
| `no_change` | `changed_ratio` 0.0002 |

`blur_variance` read 368.5 on a clean panel against the 367.6 measured on fixtures in stage 2 —
OpenCV 5 behaves identically on Graviton. And the trace of each run was read back by a **different**
Lambda invocation than the one that wrote it, which is what proves `AFTERIMAGE_RUNS_S3=1` works.

**`crop_and_rescan` (ACTION 3) was not reproduced against the endpoint during this stage.** It needs
a change large enough for the diff to find a region but with `mean_delta` under 35, and four fixtures
at `with_faint_spot` deltas 10, 16 and 22 landed on either side. Stage 7 found the window and closed
this — see below.

**Cost, measured rather than estimated.** Cost Explorer over the account: $0 in June, $0.0020 in
July, **$0.0138 in August** with `recall` running the whole month. afterimage is the first
container-image workload in the account — there was no ECR repository at all — so it adds roughly
$1/month, nearly all of it ECR storage for the ~2 GB arm64 image under the 5-image lifecycle.
Lambda itself stays inside the perpetual free tier: the 5-minute warmer burns ~1,700 GB-s a month
against 400,000 free.

**Still pending**: open the URL from another network (mobile data, not WiFi).

### Closed in stage 7

`make eval` runs 23 declarative scenarios from `eval/dataset/scenarios.json` through the real agent
loop — same `loop.py`, same MCP tools, same policy thresholds the endpoint runs — with the scripted
driver in place of Gemini. That substitution costs nothing: `policy.evaluate()` computes every
branch in code and the loop rejects a submit naming the wrong branch, so the model cannot move a
threshold. It buys a table that is identical on every run, with no network and no tokens.

Eleven scenarios are synthetic; twelve run on **real photographs of photovoltaic modules** from
Wikimedia Commons, committed under `eval/dataset/base/` with per-file attribution in `SOURCES.md`.
Lesions are injected, which is what makes the ground truth exact and what limits the claim: this
measures whether the thresholds survive real photographic texture, not field detection rates.

| Metric | Value |
|---|---|
| Scenarios passing every assertion | 20 / 23 |
| Branch accuracy · macro F1 | 0.8696 · 0.8815 |
| Defect accuracy · macro F1 | 0.9524 · 0.9513 |
| Mean IoU of the located region | 0.8258 (9 of 10 at ≥ 0.5) |
| `human_approval` precision | 1.0 — it never escalated something that did not warrant it |

**The two verdicts the stage owed, both now answered with a number:**

- **`severity.py` holds.** The `# ponytail:` note said to replace the heuristic with a trained
  classifier if the classes did not separate. Macro F1 0.9513, precision 1.0 on all four classes,
  and the single recall miss is an exposure gate firing first, not a class confusion. **No
  classifier is warranted**, and the note now has a measured reason to stay unspent.
- **`coverage_ratio_min` stays at 0.0.** Real photographs gave the first honest reading and it is
  worse than "synthetic images are unrepresentative": healthy captures span **0.0032 to 0.6357**, a
  200-fold spread, while a good synthetic panel reads 0.0009. No global default separates them. It
  is documented as a per-deployment setting with 0.0032 as the measured floor, or the contour
  heuristic gets replaced by segmentation — the upgrade path the code comment already names.

**ACTION 3 reproduced, and the window measured.** Sweeping the injected darkening on a real photo:
deltas 10–14 detect no region at all, **16 → `mean_delta` 33.34** and **18 → 34.37** both take the
zoom branch, and 20 → 35.54 crosses `mean_delta_confirm` and confirms without zooming. The branch is
not rare, it is **two points wide** — stage 6 was sampling it by hand. It then ran green against the
public endpoint with **all five decision values identical to the local container to four decimals**
(`blur_variance` 2237.0408, `inlier_ratio` 1.0, `mean_delta` 33.3427, `area_ratio` 0.1702, `score`
0.2596) — the second-channel check: the numbers that drive the decisions do not move between where
they are measured and where they are served.
[Live trace](https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/traces/90472757e472).

**Three failures, kept and analysed rather than tuned away.** A partially framed capture is rejected
for the wrong reason (`inlier_ratio` 0.0602, so the operator hears "wrong asset" instead of "step
back"); a bright defect can trip the exposure gate before it is ever assessed
(`clipped_bright_ratio` 0.3086 vs 0.30), which is the only reason `hotspot` recall is 0.6667; and
severity underestimates a small-area defect (`score` 0.3412 vs 0.40) because `score` is
`mean_delta / 64.0` and **ignores the label the classifier just produced**. That third one is
structural, not a bad threshold — and it is deliberately not fixed here, because rewriting a scoring
function on the strength of one scenario is the overfitting this dataset exists to prevent.

Anti-drift, borrowed from `hindsight`: `eval/tests/test_published_numbers.py` parses every headline
figure and every table row out of `docs/EVALUATION.md` and fails the suite if the page and
`eval/results/latest/results.json` disagree. Verified by falsifying a number and watching it fail.

### Closed in stage 8

`docs/TECHNICAL_REPORT.md` — the self-contained document a judge reads end to end, in the order
`SUBMISSION.md` demands: problem and users, real-world impact, longitudinal memory, architecture, the
OpenCV 5 implementation, the agentic loop, deploy and responsible operation, evaluation, limitations,
and how to reproduce it. It links out for detail rather than duplicating; the only figures it repeats
are the headline ones, and those are now asserted by the test suite.

**Both mandatory diagrams, in Mermaid inside the report** — no build step, no new dependency, and
GitHub renders them natively. §4 is the infrastructure; §6 is the agent loop with every branch
labelled by the metric and threshold that trigger it.

**The impact section is argued from primary literature, and says what it could not find.** The
sources that survived vetting are IEA-PVPS Task 13 (T13-09:2017 and T13-30:2025), Jordan et al. 2016
on degradation rates, and Köntges et al. 2011 on microcracks. They support the one claim the project
actually needs: **a defect is a curve, not an event** — PID runs ~15%/year in affected modules and is
partially reversible before saturation, a microcrack under 8% of cell area costs nothing today and
may cost the module later, soiling costs 5–20% a year depending on site. All of which is an argument
for measuring against the same asset's past.

Rejected on the way in, and the report says so: every inspection-cost figure that only appears on the
blog of a vendor selling inspections, and the NREL and EPRI cost reports we could identify but not
open to verify. **There is no published ROI for early detection** — the literature documents the
mechanism, not the money — and inventing one would have been the easiest thing in the report to
disprove.

**One diagram went to GitHub Pages, not two.** The plan said both; §03 of the manual already draws
the agent loop as hand-written inline SVG, so a Mermaid twin of it would have been the same picture
twice, drawn two ways, drifting apart. Only the infrastructure diagram was missing, so only that one
was added — as §11, with `mermaid.run()` called manually and the theme read from the page's own CSS
custom properties, so it follows the light and dark palettes instead of hard-coding a third one. It
is the first `<script>` this page has ever carried, and it is deferred to the end of `<body>`: if the
CDN is unreachable the rest of the manual is unaffected.

**Verified by rendering, not by assuming.** Both diagram sources were fed through `mermaid.parse()`
in a browser, and the page was served over local HTTP and screenshotted in dark theme to confirm the
subgraph titles fit and nothing overlaps. The first attempt failed that check — long subgraph titles
were clipped and the nested cluster label collided with its first node — and the titles were
shortened until it passed.

`docs/VIDEO_SCRIPT.md` — the five minutes, timed against `BRIEF.md` §7, with the words to say, the
action on screen for each block, and a pre-flight list of the state the demo needs. It names the
failure case to show on camera, because a judge trusts a project that shows where it breaks.

**El README, rediseñado desde Claude Design.** `Readme.dc.html` del proyecto "Mejorar el README"
portado a markdown de GitHub: hero centrado, badges, un GIF del loop, los resultados medidos y los
tres casos de falla arriba, y el log semanal plegado en un `<details>`. El kit centra con clases CSS
que GitHub borra, así que el port usa `align="center"`, y `Alert type="tip"` pasa a la sintaxis
nativa `> [!TIP]`.

Dos cosas que el diseño destapó y no se dejaron pasar. El badge decía `license MIT` con el repo sin
`LICENSE` y `licenseInfo: null` en GitHub — se agregó el archivo, así que la etiqueta pasó de
decorativa a cierta. Y el diagrama omitía el reintento con ORB: ahora `inlier_ratio` bajo 0.90
reintenta con el detector clásico y recién bajo 0.30 declara el activo desconocido, que es ACTION 2
de las cuatro.

Las tres imágenes de `docs/img/` se capturaron del endpoint público, no se dibujaron: una corrida
real sobre `crack-real-closeup` que terminó en `score 0.6798 >= 0.4 -> human_approval`, con su
aprobación resuelta en la cola para que el historial mostrara la cadena de baselines con el anterior
`superseded_by`.

Anti-drift extended: `eval/tests/test_published_numbers.py` now also parses the report's headline
figures and scenario counts, so neither published page can drift from the artefact.


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

⚠️ This is **not** the "working web endpoint" the rubric asks for. That one is the app on AWS,
built in stage 6 (pending its first deploy).

---

## Stages 7 to 9

Goal and closing condition for each, per `docs/BRIEF.md` §4, plus what is reusable from the author's
three previous repos (`recall`, `hindsight`, `ringdown`), already reviewed. (Stage 6 was built as
planned from `recall` and `ringdown` — see "Closed in stage 6".)

⚠️ Standing rules for the endpoint, still in force through judging: **it cannot go to sleep**
(judging runs 27 October – 9 November; budget AWS through 10 November) and **no Basic Auth**
(it opens a native dialog that blocks browser automation, breaking the video recording and any
screenshot).

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
