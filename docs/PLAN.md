# Afterimage — Plan

Source: `docs/BRIEF.md` · Deadline: 2026-10-26 23:45 -07:00 (2026-10-27 03:45 -03:00) · Hours left at writing: 631

> Adopted from the implemented system on 2026-09-30. Units U1–U16 and U18 describe what is already built
> and tested; U17, U19, and U20 are the remaining work before submission. The stage-by-stage build history is
> preserved in [BUILD_LOG.md](BUILD_LOG.md).

## Summary

The product is built, deployed from `main`, and was submitted on 7 September. What is left is
delivery hygiene: one public claim that overstates the product (U17) and bringing the video and the Devpost entry up to the current interface (U19, U20). U17 is the only
must; nothing remaining blocks the demo.

## Key technical decisions

- Branches are decided only in the policy module from measured values; the model picks arguments and
  phrasing, and a submit that disagrees with the last verdict is rejected. settled: inherited from BRIEF
- The trace is an append-only event file with a hash chain, not an OpenTelemetry pipeline. settled: inherited from BRIEF
- Alignment uses OpenCV 5 `Features` with ALIKED and LightGlue ONNX, falling back to ORB only when the
  weights are missing. settled: plan-time
- One arm64 Lambda container behind a Function URL, deployed by CloudFormation on every push to
  `main`. settled: plan-time
- Without `GOOGLE_API_KEY` the loop runs a scripted policy-following model, so tests and evaluation
  stay deterministic and offline. settled: plan-time
- Jev checks are optional, time-bounded, and can never move a branch. settled: plan-time

## Units

### U1. Quality gate
- **Goal:** an unusable capture ends `recapture` with the deciding value, and memory is untouched.
- **Covers:** R2 · F2
- **Files:** `services/perception/quality.py`, `services/agent/policy.py`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: blurred capture through the loop → branch `recapture`, no inspection stored (`services/agent/tests/test_loop.py::test_blurred_capture_ends_in_recapture`). Covers AE1.
  - edge: overexposed capture → `recapture` (`services/agent/tests/test_policy.py::test_overexposure_triggers_recapture`)
  - error: a blurred image → lower Laplacian variance than its sharp source (`services/perception/tests/test_quality.py::test_blur_lowers_the_variance`)

### U2. Alignment and unrecognized asset
- **Goal:** a capture that does not align with the asset's reference ends `unrecognized_asset` after one classic retry.
- **Covers:** R3 · F5
- **Files:** `services/perception/alignment.py`, `services/perception/weights.py`, `services/agent/policy.py`
- **Depends on:** U1
- **Status:** done
- **Tests:**
  - happy: photo of another panel under a known asset ID → neural attempt, classic retry, `unrecognized_asset`, nothing stored (`services/agent/tests/test_loop.py::test_unknown_panel_retries_then_unrecognized`). Covers AE2.
  - edge: foreign input → does not align (`services/perception/tests/test_alignment.py::test_foreign_input_does_not_align`). Covers AE2.
  - error: second tool error in a run → run fails with the tool message (`services/agent/tests/test_loop.py::test_a_second_tool_error_fails_the_run_with_the_tool_message`)

### U3. Change, rescan, and severity
- **Goal:** a weak change is rescanned over its region before severity; a strong one goes straight to severity.
- **Covers:** R4 · F3
- **Files:** `services/perception/diffing.py`, `services/perception/severity.py`, `services/perception/evidence.py`, `services/agent/policy.py`
- **Depends on:** U2
- **Status:** done
- **Tests:**
  - happy: faint change → `crop_and_rescan` with the region's box (`services/agent/tests/test_policy.py::test_faint_change_triggers_rescan_with_bbox`). Covers AE3.
  - edge: strong change → confirmed without rescan (`services/agent/tests/test_policy.py::test_strong_change_is_confirmed_without_rescan`)
  - error: unchanged crop → severity score 0 (`services/perception/tests/test_severity.py::test_unchanged_crop_scores_zero`)

### U4. Policy-enforced loop
- **Goal:** the model cannot skip the mandated next tool or submit a branch other than the last verdict.
- **Covers:** R7 · F3
- **Files:** `services/agent/loop.py`, `services/agent/llm.py`, `services/agent/scripted.py`
- **Depends on:** U1, U2, U3
- **Status:** done
- **Tests:**
  - happy: model submits a branch different from the verdict → submit rejected and recorded (`services/agent/tests/test_loop.py::test_submit_with_wrong_branch_is_rejected`). Covers AE5.
  - edge: the same verdict repeated → one decision recorded (`services/agent/tests/test_hitl.py::test_repeating_the_same_verdict_records_one_decision`)
  - error: no submit within the turn budget → run ends `failed`

### U5. Longitudinal memory and history
- **Goal:** each capture is compared with the accepted reference of the same asset; superseded references stay in the history.
- **Covers:** R1, R9 · F1, F3
- **Files:** `services/memory/store.py`, `services/memory/images.py`, `services/memory/backfill.py`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: second inspection of an asset → compared against the first (`services/memory/tests/test_longitudinal.py::test_second_inspection_compares_against_the_first`)
  - edge: first usable capture → becomes `first_baseline`
  - error: approval whose timestamp is older than the current baseline → stored without promotion

### U6. Human gate
- **Goal:** a severe finding waits in the queue; approval commits and reads memory back, rejection leaves memory unchanged with its reason.
- **Covers:** R5 · F4
- **Files:** `services/agent/hitl.py`, `services/api/app.py`, `services/ui/views.py`
- **Depends on:** U3, U5
- **Status:** done
- **Tests:**
  - happy: rejection with a reason → reason kept, baseline unchanged (`services/agent/tests/test_hitl.py::test_a_rejection_keeps_the_reviewer_reason`). Covers AE4.
  - edge: approval → reobservation recorded after the decision (`services/agent/tests/test_hitl.py::test_an_approval_records_the_reobservation_after_the_human_decision`)
  - error: failure after the commit → approval resumes instead of allowing a reject (`services/agent/tests/test_hitl.py::test_a_failure_after_the_commit_resumes_the_approval_instead_of_allowing_a_reject`)

### U7. Trace and replay
- **Goal:** every decision event carries metric, value, threshold, and branch; editing or removing an event is detected.
- **Covers:** R6 · F2, F3, F4
- **Files:** `services/observability/trace.py`, `services/observability/render.py`, `services/memory/runs.py`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: a fresh chain → verifies (`services/observability/tests/test_trace.py::test_a_fresh_chain_verifies`). Covers AE5.
  - edge: an edited decision → chain broken at that event (`services/observability/tests/test_trace.py::test_an_edited_decision_breaks_the_chain`)
  - error: a removed event → chain broken (`services/observability/tests/test_trace.py::test_a_removed_event_breaks_the_chain`)

### U8. Asset recognition
- **Goal:** without an asset ID, the agent names the stored asset the photo shows or ends `unidentified` without creating one.
- **Covers:** R8 · F5
- **Files:** `services/perception/recognition.py`, `services/perception/panels.py`, `services/agent/policy.py`
- **Depends on:** U2, U5
- **Status:** done
- **Tests:**
  - happy: capture without an asset → identified, then inspected (`services/agent/tests/test_loop.py::test_a_capture_without_an_asset_is_identified_then_inspected`). Covers AE6.
  - edge: clear vote → names that asset (`services/agent/tests/test_policy.py::test_a_clear_vote_identifies_the_asset_it_names`)
  - error: too few or split votes → `unidentified` (`services/agent/tests/test_policy.py::test_too_few_or_too_split_votes_leave_the_capture_unidentified`). Covers AE6.

### U9. Failure and retry
- **Goal:** a failed run can be retried once into a new run; the original trace stays readable and unchanged.
- **Covers:** R10 · F7
- **Files:** `services/api/app.py`, `services/memory/runs.py`
- **Depends on:** U7
- **Status:** done
- **Tests:**
  - happy: retry a failed run → new run, original preserved, retry idempotent (`services/api/tests/test_endpoints.py::test_failed_run_retry_is_idempotent_and_preserves_the_original`). Covers AE7.
  - edge: interrupted run gone stale → closed and retried once (`services/api/tests/test_endpoints.py::test_an_interrupted_run_is_closed_and_retried_once_it_goes_stale`)
  - error: retry of an unknown or non-failed run → structured error (`services/api/tests/test_endpoints.py::test_retry_rejects_unknown_and_non_failed_runs_with_structured_errors`)

### U10. Guided demo tour
- **Goal:** a first-time visitor reaches all four answers from the landing on bundled samples and a demo asset of their own.
- **Covers:** R11 · F6
- **Files:** `services/ui/views.py`, `services/ui/templates/`, `services/ui/static/app.js`, `services/ui/text.py`
- **Depends on:** U6, U8
- **Status:** done
- **Tests:**
  - happy: every branch of the tour → offers the next step (`services/ui/tests/test_views.py::test_the_demo_tour_offers_the_next_step_after_every_branch`). Covers AE8.
  - edge: the landing → opens the tour and uses the trace's vocabulary (`services/ui/tests/test_views.py::test_the_landing_opens_the_tour_and_speaks_the_trace_vocabulary`)
  - error: approving a demo finding → continues the tour (`services/api/tests/test_endpoints.py::test_approving_a_demo_finding_continues_the_tour`)

### U11. Language, register, theme, and keyboard
- **Goal:** every page reads in English or Spanish, plain or technical, light or dark, with identical numbers and a correct `lang`.
- **Covers:** R12
- **Files:** `services/ui/text.py`, `services/ui/templates/base.html`, `services/ui/static/app.js`, `services/ui/static/app.css`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: every key exists in both languages and every view declares its language (`services/ui/tests/test_language.py::test_every_string_exists_in_every_language`, `::test_every_view_declares_the_language_it_was_rendered_in`). Covers AE9.
  - edge: unknown language → English fallback (`services/ui/tests/test_language.py::test_a_language_nobody_ships_falls_back_to_english`)
  - error: register suffix reaching a template → resolved away first (`services/ui/tests/test_language.py::test_the_register_is_resolved_away_before_a_template_sees_it`)

### U12. Reproducible evaluation
- **Goal:** published metrics come from a rerunnable evaluation over the committed dataset, including failure cases.
- **Covers:** R13
- **Files:** `eval/run_eval.py`, `eval/metrics.py`, `eval/scenarios.py`, `eval/compare_results.py`, `eval/dataset/`, `eval/results/latest/`
- **Depends on:** U1, U2, U3, U8
- **Status:** done
- **Tests:**
  - happy: every published table row → matches the artefact (`eval/tests/test_published_numbers.py::test_every_published_table_row_matches_the_artefact`). Covers AE10.
  - edge: a fresh run that differs from the committed artefact → CI fails (`eval/tests/test_compare_results.py`)
  - error: a label never predicted → scores zero without dividing by zero (`eval/tests/test_metrics.py::test_a_label_never_predicted_scores_zero_without_dividing_by_zero`)

### U13. Public AWS deployment and calibration gate
- **Goal:** the service runs publicly on AWS without login, reports calibration on health, and refuses inspections when calibration fails.
- **Covers:** R14
- **Files:** `infra/template.yaml`, `infra/github-oidc.yaml`, `.github/workflows/deploy.yml`, `services/agent/calibration.py`, `services/api/app.py`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: health → reports the calibration behind it (`services/api/tests/test_endpoints.py::test_health_reports_the_calibration_that_backs_it`). Covers AE11.
  - edge: failed calibration → service out of rotation (`services/api/tests/test_endpoints.py::test_a_failed_calibration_takes_the_service_out_of_rotation`). Covers AE11.
  - error: built Lambda image without `aligned` calibration or the landing title → `make smoke` fails

### U14. Report, diagrams, and instructions
- **Goal:** a judge can rebuild, test, and deploy from the report, diagrams, and pinned instructions, and every published figure matches its artefact.
- **Covers:** R15
- **Files:** `README.md`, `docs/TECHNICAL_REPORT.md`, `docs/`, `requirements.txt`, `requirements.lock`, `Makefile`
- **Depends on:** U12, U13
- **Status:** done
- **Tests:**
  - happy: figures in README, EVALUATION, TECHNICAL_REPORT, and the video script → match `results.json` (`eval/tests/test_published_numbers.py`)
  - edge: a non-test module imported with a bare environment → no config, weights, or AWS needed (`services/perception/tests/test_import_safety.py`)
  - error: an unpinned direct dependency → image build diverges from `requirements.lock`

### U15. Perception tools over MCP
- **Goal:** the loop and any external agent call the same perception tools through MCP.
- **Covers:** R16
- **Files:** `services/mcp_server/server.py`
- **Depends on:** U1, U2, U3, U8
- **Status:** done
- **Tests:**
  - happy: an outside client over stdio → sees the same tools (`services/mcp_server/tests/test_server.py::test_the_same_tools_are_served_over_stdio_for_outside_clients`)
  - edge: —
  - error: severity with empty boxes → rejected (`services/mcp_server/tests/test_server.py::test_classify_severity_rejects_empty_bboxes`)

### U16. Activity search
- **Goal:** recent runs can be filtered by asset, run, branch, status, or message, with retry offered only where allowed.
- **Covers:** R17 · F7
- **Files:** `services/api/app.py`, `services/ui/views.py`, `services/ui/templates/`
- **Depends on:** U7, U9
- **Status:** done
- **Tests:**
  - happy: activity → lists recent runs and applies filters (`services/api/tests/test_endpoints.py::test_activity_lists_recent_runs_and_applies_filters`)
  - edge: human-gate statuses → translated (`services/ui/tests/test_views.py::test_activity_translates_human_gate_statuses`)
  - error: a run not eligible for retry → no retry offered (`services/ui/tests/test_views.py::test_activity_exposes_failed_runs_and_retry_only_when_allowed`)

### U17. Honest product claim in the README
- **Goal:** no public text says the product inspects video; it inspects still photographs.
- **Covers:** R15
- **Files:** `README.md`
- **Depends on:** —
- **Status:** done
- **Tests:**
  - happy: searching README, `docs/`, and the landing copy for a video-ingestion claim → none left
  - edge: references to the demo video itself → unchanged
  - error: a claim reintroduced later → caught by the closing audit (`hackathon-close`)

### U18. Tour step reachable on a phone
- **Goal:** on a phone the link that continues the tour and the approval panel sit inside the trace hero, above the deciding-number panel.
- **Covers:** R11 · F6
- **Files:** `services/ui/templates/trace.html`, `services/ui/views.py`, `services/ui/static/app.js`
- **Depends on:** U10
- **Status:** done (`0ab110c`, after the second UX review measured it at `d2deb93`)
- **Tests:**
  - happy: finished demo run → next step rendered inside the hero (`services/ui/tests/test_views.py::test_the_next_step_sits_inside_the_hero_so_phones_see_it_first`). Covers AE8.
  - edge: a locked sample tapped → status line explains why (`services/ui/tests/test_views.py::test_a_locked_sample_explains_itself_through_the_status_line`)
  - error: plain register → approval panel drops the model's English message (`services/ui/tests/test_views.py::test_the_approval_panel_keeps_the_model_message_for_the_technical_register`)

### U19. Re-record the demo video on the current interface
- **Goal:** a video of at most five minutes shows the team, the current landing, tour, and toggles, the architecture, and the principal results, with every spoken figure matching the artefact.
- **Covers:** R15 · F6
- **Files:** `video/script.tsv`, `video/`, `docs/VIDEO_SCRIPT.md`
- **Depends on:** U17
- **Status:** todo
- **Tests:**
  - happy: figures in the script → match `results.json` (`eval/tests/test_published_numbers.py`)
  - edge: final cut → duration ≤ 5:00
  - error: a non-browser window captured during the screencast → found by the scene-change sweep and cut

### U20. Refresh the Devpost entry
- **Goal:** the submission describes the current product (recognition, calibration gate, retry, tour, toggles) within the field limits, with every figure tied to its command.
- **Covers:** R15
- **Files:** `docs/DEVPOST.md` (not `docs/submission.md`: it collides with `docs/SUBMISSION.md` on case-insensitive filesystems)
- **Depends on:** U17
- **Status:** todo — text ready in `docs/DEVPOST.md`; pasting it into the Devpost form is pending
- **Tests:**
  - happy: every figure in the entry → found in `eval/results/latest/results.json` or the report's measured section
  - edge: the video link → still the current cut after U19
  - error: a feature named in the entry that the code does not have → removed before submit

## Cut line

| Tier | Units | Why |
|---|---|---|
| done | U1–U18 | built, tested, deployed at `2b79825` |
| must | — | U17 closed: the README no longer claims video input |
| should | U20, U19 | U20 raises Documentation and presentation; U19 is the largest and the 6 September video already meets the requirement |
| cut | — | none; 631 hours cover every remaining unit |

## Risks

- Endpoint sleeps or breaks during judging (2026-10-27 → 2026-11-09) — likelihood: baja — mitigation: warm `/health` every five minutes and budget AWS through 2026-11-10 — fallback: arranged live screen-share, which the rules accept.
- A late UI change lands after the re-recorded video — likelihood: media — mitigation: record U19 after U17 is merged and freeze the UI — fallback: the earlier cut stays published.
- Gemini quota or outage during a live demo — likelihood: media — mitigation: the scripted policy-following model runs the same branches without the key — fallback: show the deterministic run and its trace.
- Devpost form closes at 23:45 PDT, not 23:59 — likelihood: baja — mitigation: submit on 24–25 October — fallback: none.

## Out of scope

- Field validation beyond the committed dataset; signed audit log; authentication and multi-tenant access (BRIEF Deferred).
- Safety certification, autonomous maintenance, or diagnostic claims; video ingestion; the Best Use of COOL Award (BRIEF Outside this product).
