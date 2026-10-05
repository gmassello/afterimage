# Afterimage — Use cases

Source: `docs/BRIEF.md` (requirements, flows, acceptance examples) · `docs/PLAN.md` (units and cut line)

How the system is proven to do what the brief says. Requirements, flows, and acceptance examples
are cited by ID and never redefined here. Happy-path data comes from the bundled samples
(`sample-baseline`, `sample-blurred`, `sample-defect`, `sample-foreign`) and from the manual
walkthrough in [E2E.md](E2E.md).

## Features

Priority follows the PLAN: every unit behind these features is `done`, so a feature is `must` when
it moves a judging criterion and appears in the demo or the video, and `should` otherwise. Video
means the cut published on 6 September; features built after it are shown by the live tour.

| ID | Feature | Actor | Priority | Criterion | In video |
|---|---|---|---|---|---|
| R1, R9 · F1 | Longitudinal memory: each capture judged against the asset's previous accepted state, history with superseded references | A1 | must | Innovation; Real-world impact | yes |
| R2 · F2 | Quality gate and recapture | A1 | must | Substantive OpenCV 5 and agent integration | yes |
| R3 · F5 | Unrecognized asset refused instead of compared | A1 | must | Technical execution | yes |
| R4 · F3 | Active rescan of a weak change | A1 | must | Orchestration and appropriate autonomy | yes |
| R5 · F4 | Human gate with approval, rejection reason, and read-back | A1, A2 | must | Failure handling, observability, security, and human control | yes |
| R6, R7 | Deciding number on every branch; model cannot override the policy | A1 | must | Failure handling, observability, security, and human control; Orchestration and appropriate autonomy | yes |
| R8 · F5 | Asset recognition without an ID | A1 | must | Orchestration and appropriate autonomy | no (live tour) |
| R10 · F7 | Retry of a failed run, original preserved | A1 | should | Failure handling, observability, security, and human control | no |
| R11 · F6 | Guided demo tour from the landing | A3 | must | User experience | no (live tour) |
| R12 | Language, register, theme, keyboard | A3 | must | User experience | no (live tour) |
| R13 | Reproducible evaluation with failure cases | — | must | Task effectiveness and evaluation | yes |
| R14 | Public AWS deployment with calibration gate and stated cost | A3 | must | Cloud delivery, reproducibility, and responsible operation | yes |
| R15 | Report, diagrams, pinned instructions | — | must | Documentation and presentation | yes |
| R16 | Perception tools over MCP for outside agents | A4 | should | Substantive OpenCV 5 and agent integration | no |
| R17 | Activity search | A1 | should | User experience, documentation, and demonstration | no |

## Happy paths

### F1. First reference — R1, R9

Initial state: service running, asset `panel-d4-south` with no history.

1. Open `/app`, type `panel-d4-south`, choose `sample-baseline`, start the inspection.
2. The trace runs `assess_quality`; the remaining stages read `not run · first_baseline`.
3. Open `/assets/panel-d4-south`: one inspection, ringed as the baseline in force.

| Acceptance | How it is proven |
|---|---|
| proposed: Given an asset with no history, when its first usable capture is inspected, then the run ends `first_baseline` and the history shows it as the baseline. | `cases/small-synthetic-panel/checks.py` `check_first_capture_becomes_the_baseline`; `services/memory/tests/test_longitudinal.py::test_second_inspection_compares_against_the_first`; E2E path B |

### F2. Recapture — R2, R6

Initial state: `panel-d4-south` holds the `sample-baseline` reference.

1. Inspect `sample-blurred` under `panel-d4-south`.
2. The trace stops at `assess_quality` with `blur_variance` below `100.0` and the instruction to recapture.
3. The history still holds one inspection.

| Acceptance | How it is proven |
|---|---|
| AE1. Given an asset with a reference, when a blurred sample is inspected, then the run ends `recapture`, the trace shows the blur value below its threshold, and the history is unchanged. | `services/agent/tests/test_loop.py::test_blurred_capture_ends_in_recapture`; `cases/small-synthetic-panel/checks.py` `check_flat_capture_is_sent_back_with_its_number`; E2E path C (`blur_variance 3.6589 < 100.0`) |

### F3. Change recorded — R1, R4, R6, R9

Initial state: asset `e2e-synthetic` holds the generated plain panel as its reference (E2E path J).

1. Inspect the faint-spot panel (E2E `5-synth-faint.png`).
2. The trace runs `diff_against_memory`, finds `mean_delta` between `30` and `35`, calls `crop_and_rescan`, then `classify_severity`.
3. Severity is under `0.4`: the run ends `auto_write` and the capture becomes the new reference.

| Acceptance | How it is proven |
|---|---|
| AE3. Given a change whose strength is below the confirmation threshold, when the inspection runs, then the trace shows a rescan of that region before any severity step. | `services/agent/tests/test_policy.py::test_faint_change_triggers_rescan_with_bbox`; E2E path K (all five stages `done`) |

### F4. Human gate — R5, R6

Initial state: `panel-d4-south` holds the `sample-baseline` reference.

1. Inspect `sample-defect`: severity `score` at or above `0.4` → `human_approval`.
2. From the trace, reject with the reason `glare on the glass`: the history is unchanged.
3. Inspect `sample-defect` again: the same score, back in `/queue`; approve it.
4. The trace records the human decision and `baseline_verified`; the history shows the new reference and the previous one `superseded by`.

| Acceptance | How it is proven |
|---|---|
| AE4. Given a severe finding in the queue, when it is rejected with a reason, then the reference is unchanged and the reason appears with the decision. | `services/agent/tests/test_hitl.py::test_a_rejection_keeps_the_reviewer_reason`; `services/ui/tests/test_views.py::test_a_rejection_can_carry_the_reviewer_reason`; E2E paths D–H |
| AE5. Given any finished run, when its trace is opened, then every decision lists metric, value, threshold, and branch, and a model submission contradicting the last verdict appears as rejected. | `services/agent/tests/test_loop.py::test_submit_with_wrong_branch_is_rejected`; `services/observability/tests/test_trace.py::test_a_fresh_chain_verifies`; `cases/small-synthetic-panel/checks.py` `check_flat_capture_is_sent_back_with_its_number` |

### F5. Unknown asset — R3, R8

Initial state: `panel-d4-south` holds the `sample-baseline` reference; a second asset exists.

1. Inspect `sample-foreign` under `panel-d4-south`: the neural alignment falls short of `0.90`, the ORB retry falls short of `0.30`, and the run ends `unrecognized_asset`.
2. Upload `sample-baseline` with the asset ID empty: recognition names `panel-d4-south`, or ends `unidentified` without creating an asset.

| Acceptance | How it is proven |
|---|---|
| AE2. Given an asset with a reference, when a photo of a different object is inspected under that asset ID, then the run ends `unrecognized_asset` and nothing is stored. | `services/agent/tests/test_loop.py::test_unknown_panel_retries_then_unrecognized`; `services/perception/tests/test_alignment.py::test_foreign_input_does_not_align`; E2E path L |
| AE6. Given two stored assets, when a photo is uploaded without an ID, then the run either names the matching asset or ends `unidentified` and creates no asset. | `services/agent/tests/test_loop.py::test_a_capture_without_an_asset_is_identified_then_inspected`; `services/agent/tests/test_policy.py::test_too_few_or_too_split_votes_leave_the_capture_unidentified` |

### F6. Guided demo — R11, R12, R6

Initial state: a first-time visitor with no cookies; plain register, English.

1. Open `/` and press the primary button: `/app?sample=sample-baseline` opens with the sample chosen.
2. Run it (`first_baseline`); the trace offers `sample-defect`; approve it; the history offers `sample-blurred` (`recapture`), then `sample-foreign` (`unrecognized_asset`). The hot-spot and delamination sets (`sample-b-*`, `sample-c-*`, reached by swiping the carousel) walk the same four answers on their own demo assets; `services/agent/tests/test_loop.py::test_every_demo_group_reaches_its_four_answers` proves each set's branches.
3. Switch to Spanish, technical register, and dark theme on any page: the copy changes and the numbers stay.

| Acceptance | How it is proven |
|---|---|
| AE8. Given a first-time visitor, when they follow the tour from the landing, then they reach all four answers without typing an asset ID. | `services/ui/tests/test_views.py::test_the_demo_tour_offers_the_next_step_after_every_branch`; `services/ui/tests/test_views.py::test_the_next_step_sits_inside_the_hero_so_phones_see_it_first`; `screenshot` of the four terminal traces |
| AE9. Given any page, when language, register, or theme is toggled, then the copy changes, the numbers stay identical, and the document language attribute follows. | `services/ui/tests/test_language.py::test_every_string_exists_in_every_language`; `services/ui/tests/test_language.py::test_every_view_declares_the_language_it_was_rendered_in`; `screenshot` in both themes |

### F7. Failure and retry — R10, R17

Initial state: a run that ended `failed` (for example, a tool error twice in a row).

1. Open `/activity`, filter by status `failed`: the run shows a retry action.
2. Retry it: a new run opens on the same capture; the original trace is still readable.
3. Retry again: the same replacement comes back.

| Acceptance | How it is proven |
|---|---|
| AE7. Given a failed run, when it is retried, then a new run opens and the original trace is still readable and unchanged. | `services/api/tests/test_endpoints.py::test_failed_run_retry_is_idempotent_and_preserves_the_original`; `cases/small-synthetic-panel/checks.py` `check_finished_run_cannot_be_retried` |

### R13–R16. Evaluation, deployment, documentation, MCP

| Acceptance | How it is proven |
|---|---|
| AE10. Given the committed dataset, when the evaluation is rerun, then its results match the published ones. | `make eval ARGS="--out eval/results/ci"` then `python3 eval/compare_results.py eval/results/latest eval/results/ci`; `eval/tests/test_published_numbers.py::test_every_published_table_row_matches_the_artefact` |
| AE11. Given the public deployment, when its health check is requested, then it reports calibration aligned; when calibration fails, inspections are refused. | `cases/small-synthetic-panel/checks.py` `check_health_reports_aligned_calibration`; `services/api/tests/test_endpoints.py::test_a_failed_calibration_takes_the_service_out_of_rotation`; `make smoke` |
| proposed: Given an outside MCP client, when it connects over stdio, then it sees the same perception tools the loop uses. | `services/mcp_server/tests/test_server.py::test_the_same_tools_are_served_over_stdio_for_outside_clients` |

## Test cases

### Small — `cases/small-synthetic-panel/`

A trivial scenario of our own: two generated 256 × 256 PNGs (a checkerboard and a flat gray) under a
fresh asset, crossing upload validation, storage, the loop over MCP, the policy, the trace, and memory.
Spec in [SPEC.md](../cases/small-synthetic-panel/SPEC.md). Units: U1, U5, U7, U9, U13.

| Layer | Criterion | How it is proven |
|---|---|---|
| Product | the checkerboard becomes the first baseline and its history renders | `python3 cases/small-synthetic-panel/checks.py http://localhost:8000` → `check_first_capture_becomes_the_baseline` |
| Product | the flat capture is sent back with `input_metric`, value, and threshold (AE1) | same run → `check_flat_capture_is_sent_back_with_its_number` |
| Product | invalid asset ID and undecodable image are refused with the shared error shape | same run → `check_invalid_asset_id_is_refused`, `check_undecodable_image_is_refused` |
| System | health reports `aligned` calibration (AE11) and the landing is this product | same run → `check_health_reports_aligned_calibration`, `check_landing_names_the_product` |
| System | unknown and finished runs are refused with stable codes | same run → `check_unknown_run_cannot_execute`, `check_finished_run_cannot_be_retried` |
| System | no human intervention, no model key needed | the run above passes without `GOOGLE_API_KEY` (scripted model) |

### Medium — the real-photograph scenarios

The 18 scenarios on licensed photographs of real photovoltaic modules in `eval/dataset/`: imagery we
did not produce, with defects we did not draw. The event publishes no sample suite, so this is the
closest suite not shaped by us. It brings its own runner, so it needs no `checks.py`. Units: U1–U3,
U8, U12. Re-run at closing as evidence that nothing was tuned by hand for the large case.

| Layer | Criterion | How it is proven |
|---|---|---|
| Product | branch, defect class, and decision path per scenario | `make eval ARGS="--out eval/results/ci"` → `eval/results/ci/results.json` |
| Product | published figures match a fresh run | `make eval ARGS="--out eval/results/ci"` then `python3 eval/compare_results.py eval/results/latest eval/results/ci` exits 0 (the CI `eval` job) |
| System | failures are published with their deciding number, not hidden | `README.md` "Where it fails" rows match `results.json`; `eval/tests/test_published_numbers.py` |
| System | deterministic and offline: no network, no model key | `make eval` without `GOOGLE_API_KEY` reproduces the committed artefact |

### Large — the full delivery

What is judged: the public endpoint, the repository, the report, the video, and the Devpost entry.
Units: all.

| Layer | Criterion | How it is proven |
|---|---|---|
| Product | the small case passes against the public endpoint | `python3 cases/small-synthetic-panel/checks.py https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws` (writes `case-small-*` assets to the demo memory) |
| Product | the four answers are reachable by a first-time visitor | F6 walked on the public URL; `screenshot` of each terminal trace |
| Product | full suite and evaluation green on `main` | `make test`; CI `ci` and `eval` jobs at HEAD |
| System | the deployed image is `main` and its calibration is aligned | `gh run list --commit $(git rev-parse HEAD)` shows `Deploy` success; `make smoke` |
| System | every submission requirement in `docs/HACKATHON.md` has its artefact | `hackathon-close` audit, recorded in `docs/STATUS.md` |
| System | the video is at most five minutes and reachable without login | video duration on the public page; `hackathon-close` |

## Out of scope

No feature is `cut`. Outside the product, as in the brief: field validation beyond the committed
dataset, a signed audit log, authentication, video ingestion, and the COOL award.
