# Submission checklist — OpenCV AI Competition 2026

Track: **Agentic Vision path**. Deadline 26 Oct 23:59 PT (27 Oct 03:59 ART); submit 24–25 Oct.

This file is a build checklist first and a deliverable second. Every row names where a judge
sees the evidence — a file and line, a URL, or a timestamp in the video. A row without evidence
is unfinished work, not a formatting gap.

Status: `done` · `wip` · `todo`

## Overall rubric

| Criterion | Weight | How we demonstrate it | Where the judge sees it | Status |
|---|---|---|---|---|
| Technical execution | 30% | OpenCV 5 `Features` used substantively — ALIKED + LightGlue align each capture to the stored baseline of the same asset; green suite on arm64 | `services/perception/alignment.py`, `services/perception/tests/`, video 1:29–3:00 (`inlier_ratio 0.9988` on screen) | done |
| Innovation | 20% | **Longitudinal memory.** No previous winner kept state across inspections of the same asset; every prior project analyses one frame or one session. A second inspection retrieves the baseline from memory, aligns to it and locates the new defect | `services/memory/`, `services/memory/tests/test_longitudinal.py`, [`docs/TECHNICAL_REPORT.md` §3](TECHNICAL_REPORT.md#3-what-makes-this-different-longitudinal-memory), video 1:29–3:00 | done |
| Real-world impact | 20% | Preventive maintenance of solar plants, argued from cited primary sources: ~2,900 modules per MW, PID degrading ~15%/year in affected modules and partially reversible if caught before saturation, soiling at 5–20% annual loss — every figure with organism, year and URL, and the absence of a published early-detection ROI stated rather than invented | [`docs/TECHNICAL_REPORT.md` §2](TECHNICAL_REPORT.md#2-why-change-over-time-is-the-right-thing-to-measure) | done |
| User experience | 10% | Approval queue and asset history legible without explanation | public endpoint (`/`, `/queue`, `/assets/{id}`), video 1:22–2:44 — three uploads, a live approval and the baseline chain, no narration of the UI needed | done |
| Documentation and presentation | 10% | A judge-first README — the loop in a GIF captured from the live endpoint, measured results and failure cases above the fold, the weekly log folded away — plus a self-contained technical report and both diagrams, the infrastructure one also published on GitHub Pages | `README.md`, [`docs/TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md), <https://gmassello.github.io/afterimage/> | done |
| Cloud, reproducibility, responsible operation | 10% | IaC, exact pins, OIDC with a permissions boundary, image retention policy, per-run event traces | `infra/template.yaml`, `infra/github-oidc.yaml`, `deploy.sh`, `requirements.txt`, video 0:55–1:29 (the infrastructure diagram) and 3:00–3:35 (a run trace) | done |

## Agentic Vision Award

The bar, verbatim: *"image or video results must influence a subsequent plan, tool call, action,
or request for human approval. A chatbot that only explains a fixed vision result is not enough —
the visual evidence must change what the system does next."*

| Criterion | Weight | How we demonstrate it | Where the judge sees it | Status |
|---|---|---|---|---|
| OpenCV 5 + agent integration | 30% | Five perception tools exposed over MCP; every one returns the numeric metrics the agent branches on | `services/perception/`, `services/mcp_server/server.py` | done |
| Orchestration and appropriate autonomy | 25% | Four branches that actually fire: recapture, retry with another detector, zoom on an uncertain region, ask a human — `make demo` drives all four; every decision recorded as `{input_metric, value, threshold, branch}` | `services/agent/loop.py`, `services/agent/policy.py`, `services/agent/tests/test_loop.py` | done |
| Task effectiveness and evaluation | 20% | 23 scenarios, 12 of them on real photographs: branch accuracy 0.8696, defect macro F1 0.9513, mean IoU 0.8258, and three failure cases analysed to root cause | `docs/EVALUATION.md`, `eval/results/latest/` | done |
| Failure handling, observability, security, human control | 15% | One span per tool call carrying args, metrics, duration and the verdict that the value triggered, persisted per run and served as JSON or a human-readable page | `services/observability/`, `services/api/app.py`, `GET /traces/{run_id}` | done |
| UX and documentation | 10% | Agent loop diagram plus the trace viewer | [`docs/TECHNICAL_REPORT.md` §6](TECHNICAL_REPORT.md#6-the-agentic-loop) and the field manual §03, `GET /traces/{run_id}` with `Accept: text/html` | done |

### The trace that has to exist

The award needs one trace where an OpenCV number visibly changed a later decision, and a judge
must see it **without inferring**. So the causal link is a field, not something reconstructed by
reading several events in order. Since stage 5 it exists: every `tool_call` event in
`runs/{run_id}/events.json` nests the verdict under `policy`, and `make demo` prints this line,
measured, not invented:

```json
{"input_metric": "inlier_ratio", "value": 0.0385, "threshold": 0.3, "branch": "unrecognized_asset"}
```

The metric names are already fixed by the week 2 dataclasses — `blur_variance`, `inlier_ratio`,
`area_ratio`, `mean_delta`, `score` — precisely so this field can reference them. Perception
reports those numbers and nothing else: how they combine into a confidence, and what threshold
each one is compared against, is the policy's business.

| Branch | Metric that triggers it | Measured on fixtures |
|---|---|---|
| ACTION 1 — request recapture | `blur_variance` | falls under `GaussianBlur` |
| ACTION 2 — retry with another detector / unrecognized asset | `inlier_ratio` | 0.997 same panel vs 0.407 different panel (ALIKED) |
| ACTION 3 — crop and rescan | `area_ratio` | 0.0008 of the frame → 0.68 of the crop, measured with 4× the pixels. Reproduced against the public endpoint on 2 September: `mean_delta` 33.3427 vs 35.0 → `crop_and_rescan`, then `area_ratio` 0.1702 vs 0.02 ([live trace](https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/traces/90472757e472)) |
| ACTION 4 — request human approval | `score` | rises with the magnitude of the change |

## Deliverables

- [x] 1. Technical report — [`docs/TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md): problem, users, real-world impact with cited sources, architecture, OpenCV 5 implementation, the agentic loop, AWS deploy, evaluation, limitations, responsible use. Self-contained; the headline evaluation figures in it are asserted against `eval/results/latest/results.json` by `eval/tests/test_published_numbers.py`
- [x] 2. Repository accessible to judges — public, and now licensed: `LICENSE` (MIT), so GitHub reports the licence rather than `null` and a judge knows what they may reuse
- [x] 3. Exact pins in `requirements.txt` and build/run instructions that work on a clean machine
- [x] 4. Two diagrams: infrastructure **and** the agent loop, both as Mermaid in [`docs/TECHNICAL_REPORT.md`](TECHNICAL_REPORT.md) §4 and §6. The loop is additionally drawn as inline SVG in the field manual §03, and the infrastructure diagram is published on GitHub Pages §11
- [x] 5. Public web endpoint, no login — **<https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/>**
      (Lambda container on Graviton + Function URL, no auth). Judge's path: `/` → upload a capture →
      the live trace → `/queue` to approve → `/assets/{id}` for the longitudinal history.
      Deployed 2 September from GitHub Actions over OIDC; every branch below was walked against
      this URL, not against localhost
- [x] 6. Video ≤ 5 min, **showing the author's face**, public or unlisted — **published 7 September at
      https://youtu.be/zUFR96a33IM**, public, 4:53.6, 1920×1080, with `demo.en.srt` as the English
      caption track. It opens on fourteen seconds with no voice: a real array and its scale, then
      two decisions the system actually made with the numbers that caused them, then the name — so
      the thesis lands before anyone introduces themselves. The author's face is in the corner box
      from the first frame to the last, which means the big frame is always the product or the
      documentation. Narration in Spanish, English subtitles burned in. Every frame of the demo is
      the public endpoint, driven live on asset `panel-d4-south`. Assembled by the pipeline in
      [`video/PRODUCTION.md`](../video/PRODUCTION.md) from [`video/script.tsv`](../video/script.tsv).

      | | Beat |
      |---|---|
      | 0:00–0:14 | **Cold open**, no voice — two decisions and the numbers behind them |
      | 0:14–0:31 | Opening |
      | 0:31–0:55 | The problem |
      | 0:55–1:29 | Architecture, the infrastructure diagram |
      | 1:29–3:00 | **The demo** — three uploads, a live approval, the baseline chain |
      | 3:00–3:35 | **The trace**, on the span that decided |
      | 3:35–4:25 | Evaluation, including a failure |
      | 4:25–4:54 | The close — the evaluation tables and the public URL |
- [x] 7. Evaluation evidence in `eval/results/latest/` and `docs/EVALUATION.md`, **including failure cases** —
      23 scenarios (11 synthetic, 12 on licensed real photographs), branch accuracy 0.8696, defect macro F1 0.9513.
      Three failures analysed to root cause, and `eval/tests/test_published_numbers.py` fails CI if the page and
      the artefact disagree

## Final checklist

- [x] Endpoint tested from another network — reached from mobile data on 7 September, off the WiFi the deploy was made
      from — and budgeted to stay alive until 10 November (judging runs 27 Oct – 9 Nov).
      Cost measured, not estimated: the account billed $0.0138 in August with the sibling `recall` stack running all month;
      afterimage adds ~$1/month, almost all of it ECR storage for the 2 GB arm64 image
- [x] No credentials anywhere in git history — swept the full history for key patterns and credential filenames; the only match is `AWS_SECRET_ACCESS_KEY=test`, the LocalStack dummy
- [x] The trace linked from the report — [`docs/TECHNICAL_REPORT.md` §6](TECHNICAL_REPORT.md#observability) links two live traces: the zoom branch, and the run the video shows stopping for a human
- [x] Video recorded against the public URL, not localhost — the address bar is legible in every browser shot, and the
      runs it shows (`45ceaea34b8e`, `0ac678eec19f`, `b022e78251f3` on asset `panel-d4-south`, recorded 6 September)
      are still live on the endpoint

## Known limitations

Written as we go, not the night before. Admitting a limit costs less than a judge finding it.

- Defect classification is a threshold heuristic over OpenCV features, not a trained classifier.
  Stage 7 measured it rather than assuming: macro F1 0.9513 with precision 1.0 on all four classes,
  so no classifier is warranted. See `docs/EVALUATION.md`.
- `severity.score` is `mean_delta / 64.0` and ignores the label the classifier just produced, so a
  defect covering a small area can score under the approval threshold and be written automatically —
  measured once, at 0.3412 vs 0.40, on a real photograph.
- `crop_and_rescan` re-measures the same capture at higher resolution. It buys measurement
  precision on a marginal region, not new optical detail — it cannot resolve what the original
  capture never recorded.
- `inlier_ratio` is not comparable across detectors — ORB scores 0.41 where ALIKED scores 0.997 on
  the same pair, because a repetitive cell grid produces ambiguous ORB matches. The policy needs one
  threshold per detector.
- Frame coverage is estimated from the bounding box of the largest edge contour, which will misread
  panels against cluttered backgrounds.
- Alignment costs ~1.5 s per pair on CPU. The DNN engine in OpenCV 5 has no GPU support.
- The frame-coverage quality check is disabled by default (`coverage_ratio_min=0.0`). Stage 7
  measured it on real photographs: healthy captures span 0.0032 to 0.6357, a 200-fold spread, so no
  single global default works. It is a per-deployment setting, calibrated from a sample of that
  site's own captures.
- Policy thresholds (`blur_variance_min=100`, `mean_delta_confirm=35`, `severity_score_approve=0.4`)
  were calibrated on synthetic fixtures and then checked against 12 real photographs in stage 7.
  `mean_delta_confirm` leaves the zoom branch a two-point-wide window (33.34 and 34.37 enter it,
  35.54 does not), which is narrow but reproducible on demand.
- Tests and the default demo drive the loop with a scripted policy-following LLM; `--live` runs the
  same loop against Gemini. The branch verdicts are computed in code either way — the LLM cannot
  override a policy verdict, so determinism of the decisions does not depend on the model.
