# Submission checklist — OpenCV AI Competition 2026

Track: **Agentic Vision path**. Deadline 26 Oct 23:59 PT (27 Oct 03:59 ART); submit 24–25 Oct.

This file is a build checklist first and a deliverable second. Every row names where a judge
sees the evidence — a file and line, a URL, or a timestamp in the video. A row without evidence
is unfinished work, not a formatting gap.

Status: `done` · `wip` · `todo`

## Overall rubric

| Criterion | Weight | How we demonstrate it | Where the judge sees it | Status |
|---|---|---|---|---|
| Technical execution | 30% | OpenCV 5 `Features` used substantively — ALIKED + LightGlue align each capture to the stored baseline of the same asset; green suite on arm64 | `services/perception/alignment.py`, `services/perception/tests/` | wip |
| Innovation | 20% | **Longitudinal memory.** No previous winner kept state across inspections of the same asset; every prior project analyses one frame or one session. A second inspection retrieves the baseline from memory, aligns to it and locates the new defect | `services/memory/`, `services/memory/tests/test_longitudinal.py`, `docs/TECHNICAL_REPORT.md`, video 1:30–3:15 | wip |
| Real-world impact | 20% | Preventive maintenance of solar plants, with numbers: assets per site, cost of manual inspection, what the agent saves | `docs/TECHNICAL_REPORT.md` | todo |
| User experience | 10% | Approval queue and asset history legible without explanation | public endpoint (`/`, `/queue`, `/assets/{id}`) | wip |
| Documentation and presentation | 10% | README, technical report, both diagrams | `README.md`, `docs/` | wip |
| Cloud, reproducibility, responsible operation | 10% | IaC, exact pins, OIDC with a permissions boundary, image retention policy, per-run event traces | `infra/template.yaml`, `infra/github-oidc.yaml`, `deploy.sh`, `requirements.txt` | wip |

## Agentic Vision Award

The bar, verbatim: *"image or video results must influence a subsequent plan, tool call, action,
or request for human approval. A chatbot that only explains a fixed vision result is not enough —
the visual evidence must change what the system does next."*

| Criterion | Weight | How we demonstrate it | Where the judge sees it | Status |
|---|---|---|---|---|
| OpenCV 5 + agent integration | 30% | Five perception tools exposed over MCP; every one returns the numeric metrics the agent branches on | `services/perception/`, `services/mcp_server/server.py` | done |
| Orchestration and appropriate autonomy | 25% | Four branches that actually fire: recapture, retry with another detector, zoom on an uncertain region, ask a human — `make demo` drives all four; every decision recorded as `{input_metric, value, threshold, branch}` | `services/agent/loop.py`, `services/agent/policy.py`, `services/agent/tests/test_loop.py` | done |
| Task effectiveness and evaluation | 20% | Precision and recall on the evaluation set, **including failure cases** | `docs/EVALUATION.md`, `eval/results/` | todo |
| Failure handling, observability, security, human control | 15% | One span per tool call carrying args, metrics, duration and the verdict that the value triggered, persisted per run and served as JSON or a human-readable page | `services/observability/`, `services/api/app.py`, `GET /traces/{run_id}` | done |
| UX and documentation | 10% | Agent loop diagram plus the trace viewer | `docs/AGENT_LOOP.md`, `GET /traces/{run_id}` with `Accept: text/html` | wip |

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
| ACTION 3 — crop and rescan | `area_ratio` | 0.0008 of the frame → 0.68 of the crop, measured with 4× the pixels. ⚠️ Green in tests; **not yet reproduced against the public endpoint** — see stage 7 |
| ACTION 4 — request human approval | `score` | rises with the magnitude of the change |

## Deliverables

- [ ] 1. Technical report — `docs/TECHNICAL_REPORT.md`: problem, users, architecture, OpenCV 5 implementation, AWS deploy, evaluation, limitations, responsible use
- [ ] 2. Repository accessible to judges (public, or private with access granted)
- [x] 3. Exact pins in `requirements.txt` and build/run instructions that work on a clean machine
- [ ] 4. Two diagrams: infrastructure **and** the agent loop — the second is mandatory for the award
- [x] 5. Public web endpoint, no login — **<https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/>**
      (Lambda container on Graviton + Function URL, no auth). Judge's path: `/` → upload a capture →
      the live trace → `/queue` to approve → `/assets/{id}` for the longitudinal history.
      Deployed 2 September from GitHub Actions over OIDC; every branch below was walked against
      this URL, not against localhost
- [ ] 6. Video ≤ 5 min, **showing the author's face**, public or unlisted
- [ ] 7. Evaluation evidence in `eval/results/` and `docs/EVALUATION.md`, **including failure cases**

## Final checklist

- [ ] Endpoint tested from another network, and budgeted to stay alive until 10 November (judging runs 27 Oct – 9 Nov).
      Cost measured, not estimated: the account billed $0.0138 in August with the sibling `recall` stack running all month;
      afterimage adds ~$1/month, almost all of it ECR storage for the 2 GB arm64 image
- [ ] No credentials anywhere in git history
- [ ] The trace linked from the report
- [ ] Video recorded against the public URL, not localhost

## Known limitations

Written as we go, not the night before. Admitting a limit costs less than a judge finding it.

- Defect classification is a threshold heuristic over OpenCV features, not a trained classifier.
  Thresholds are calibrated on synthetic fixtures; see `services/perception/severity.py`.
- `crop_and_rescan` re-measures the same capture at higher resolution. It buys measurement
  precision on a marginal region, not new optical detail — it cannot resolve what the original
  capture never recorded.
- `inlier_ratio` is not comparable across detectors — ORB scores 0.41 where ALIKED scores 0.997 on
  the same pair, because a repetitive cell grid produces ambiguous ORB matches. The policy needs one
  threshold per detector.
- Frame coverage is estimated from the bounding box of the largest edge contour, which will misread
  panels against cluttered backgrounds.
- Alignment costs ~1.5 s per pair on CPU. The DNN engine in OpenCV 5 has no GPU support.
- The frame-coverage quality check is disabled by default (`coverage_ratio_min=0.0`): the contour
  heuristic reads ~0 on synthetic fixtures. On real captures it must be re-enabled via env and
  recalibrated.
- Policy thresholds (`blur_variance_min=100`, `mean_delta_confirm=35`, `severity_score_approve=0.4`)
  are calibrated on synthetic fixtures, like the severity heuristic they gate.
- Tests and the default demo drive the loop with a scripted policy-following LLM; `--live` runs the
  same loop against Gemini. The branch verdicts are computed in code either way — the LLM cannot
  override a policy verdict, so determinism of the decisions does not depend on the model.
