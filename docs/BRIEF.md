# Afterimage — Brief

> Product contract for the OpenCV AI Competition 2026 entry, adopted from the implemented system
> ([FUNCTIONAL.md](FUNCTIONAL.md), [README.md](../README.md), `services/agent/policy.py`). The
> pre-implementation proposal is preserved as [PROPOSAL.md](PROPOSAL.md). Event rules and criteria
> live in [HACKATHON.md](HACKATHON.md) and [judging.tsv](judging.tsv).

## Summary

An inspection agent that looks at the same physical asset again and again, compares each new photo
with the accepted reference of that asset, and decides from measured evidence whether to ask for a
recapture, record the change, or stop for a human. Every decision can be replayed from its trace,
including the number that chose it.

## Problem frame

Periodic visual inspection of assets such as photovoltaic modules is judged one image at a time: a
technician or a model looks at today's photo and decides whether it shows a defect. That throws
away the most informative evidence available — what this same asset looked like last time — so
slow degradation is missed and one-off artefacts (glare, blur, a different framing) are mistaken for
damage. An automated agent that acts on its own adds a second problem: nobody can tell afterwards
why it wrote, skipped, or escalated a finding.

The evidence available for the size of that cost is thin: no inspection-cost figure could be
verified line by line (see [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) §2). What is measured is the
agent's own cost per inspection.

## Actors

- A1. Operator — uploads captures of an asset, follows the inspection, and acts on its result.
- A2. Approver — decides on severe findings before they change the asset's memory.
- A3. Judge or first-time visitor — arrives at the public landing and walks the demo without an
  account or prior asset.
- A4. External agent — drives the same perception tools the product's loop uses, without the UI.

## Requirements

- R1. The operator sees each capture judged against the previous accepted state of the same asset, not in isolation. [criterion: Innovation]
- R2. A capture that is too blurred, dark, bright, or clipped is refused with a concrete instruction to recapture, and memory is not touched. [criterion: Substantive OpenCV 5 and agent integration]
- R3. A capture that cannot be aligned reliably with the asset's reference is refused as an unrecognized asset instead of being compared. [criterion: Technical execution]
- R4. When a detected change is weak, the agent looks closer at the changed region before deciding, and only a confirmed change reaches severity. [criterion: Orchestration and appropriate autonomy]
- R5. A severe finding waits for a person; approving it updates memory, rejecting it leaves memory unchanged and keeps the stated reason. [criterion: Failure handling, observability, security, and human control]
- R6. Every branch the agent takes shows the metric, the measured value, and the threshold that chose it, and the whole run can be replayed from its trace. [criterion: Failure handling, observability, security, and human control]
- R7. The language model can phrase results and pick arguments but cannot override the branch that the measured evidence mandates. [criterion: Orchestration and appropriate autonomy]
- R8. When no asset ID is given, the agent identifies which stored asset the photo shows, or says it cannot, without guessing. [criterion: Orchestration and appropriate autonomy]
- R9. The asset keeps a chronological history in which superseded references remain visible. [criterion: Real-world impact]
- R10. A failed run can be retried without changing or hiding the original record. [criterion: Failure handling, observability, security, and human control]
- R11. A first-time visitor can walk all four answers over bundled samples on a demo asset of their own, guided from the landing page. [criterion: User experience]
- R12. The interface reads in English or Spanish, in a plain or technical register, in a light or dark theme, and works by keyboard. [criterion: User experience]
- R13. Published effectiveness comes from a reproducible evaluation over a committed dataset, including its failure cases. [criterion: Task effectiveness and evaluation]
- R14. The product runs publicly on AWS without a login, refuses inspections while its own calibration check fails, and states its per-inspection cost. [criterion: Cloud delivery, reproducibility, and responsible operation]
- R15. A judge can rebuild, test, and deploy the system from the report, the architecture diagrams, and pinned instructions. [criterion: Documentation and presentation]
- R16. An external agent can call the same perception tools the loop uses, over a standard tool protocol. [criterion: Substantive OpenCV 5 and agent integration]
- R17. Recent runs can be found by asset, run, branch, status, or message. [criterion: User experience, documentation, and demonstration]

## Key flows

- F1. **First reference** — the operator uploads the first usable capture of an asset → quality
  passes → the capture becomes the reference → the history shows it. (A1; R1, R9)
- F2. **Recapture** — a blurred or badly exposed capture arrives → quality fails → the trace shows
  the value against its threshold and the instruction to recapture → memory is unchanged. (A1; R2, R6)
- F3. **Change recorded** — a capture of a known asset arrives → it aligns → a change is found and,
  if weak, rescanned → severity is below the approval threshold → the inspection is stored and
  becomes the new reference. (A1; R1, R4, R6, R9)
- F4. **Human gate** — a severe change is found → the run waits in the approval queue → the approver
  approves (memory updated and read back) or rejects with a reason (memory unchanged). (A1, A2; R5, R6)
- F5. **Unknown asset** — a capture of a different object arrives → alignment fails, or recognition
  finds no clear match → the run ends without writing anything. (A1; R3, R8)
- F6. **Guided demo** — a visitor opens the landing → starts the tour → walks first reference,
  recapture, human gate, and unknown asset on bundled samples → ends on the trace that shows the
  deciding number. (A3; R11, R6)
- F7. **Failure and retry** — a run fails mid-way → the trace shows where → the operator retries it
  → a new run opens and the original stays readable. (A1; R10, R17)

## Acceptance examples

- AE1. **Covers R2.** Given an asset with a reference, when a blurred sample is inspected, then the
  run ends `recapture`, the trace shows the blur value below its threshold, and the history is unchanged.
- AE2. **Covers R3.** Given an asset with a reference, when a photo of a different object is
  inspected under that asset ID, then the run ends `unrecognized_asset` and nothing is stored.
- AE3. **Covers R4.** Given a change whose strength is below the confirmation threshold, when the
  inspection runs, then the trace shows a rescan of that region before any severity step.
- AE4. **Covers R5.** Given a severe finding in the queue, when it is rejected with a reason, then
  the reference is unchanged and the reason appears with the decision.
- AE5. **Covers R6, R7.** Given any finished run, when its trace is opened, then every decision
  lists metric, value, threshold, and branch, and a model submission contradicting the last verdict
  appears as rejected.
- AE6. **Covers R8.** Given two stored assets, when a photo is uploaded without an ID, then the run
  either names the matching asset or ends `unidentified` and creates no asset.
- AE7. **Covers R10.** Given a failed run, when it is retried, then a new run opens and the
  original trace is still readable and unchanged.
- AE8. **Covers R11.** Given a first-time visitor, when they follow the tour from the landing, then
  they reach all four answers without typing an asset ID.
- AE9. **Covers R12.** Given any page, when language, register, or theme is toggled, then the copy
  changes, the numbers stay identical, and the document language attribute follows.
- AE10. **Covers R13.** Given the committed dataset, when the evaluation is rerun, then its results
  match the published ones.
- AE11. **Covers R14.** Given the public deployment, when its health check is requested, then it
  reports calibration aligned; when calibration fails, inspections are refused.

## Key decisions

- Branches are decided by one policy module from measured values; the model only phrases and picks
  arguments — chosen over letting the model decide, because every decision must be reconstructible
  and the Agentic Vision rule requires visual evidence to change what happens next. settled: user-directed
- Longitudinal memory per asset is the product's core — chosen over single-image defect
  classification, because no previous winner had it and it is what the Innovation criterion rewards. settled: user-directed
- Photovoltaic modules are the evaluation domain — chosen over roads, retail shelves, or industrial
  panels, because of available imagery and measurable degradation. settled: user-directed
- Severe findings always pass a human gate before changing memory — chosen over full autonomy,
  because of the human-control criterion and the rule against misrepresenting the role of review. settled: user-directed
- The trace is an append-only event record with a hash chain, not an OpenTelemetry pipeline —
  chosen over OTel because it is the causal record the UI and retry read. settled: user-directed
- Entry targets the Overall awards and the Agentic Vision Award, not the COOL award. settled: user-directed

## Scope boundaries

### Deferred

- Field validation on real plant imagery beyond the committed dataset.
- Signed audit log; the hash chain detects ordinary editing only.
- Authentication and multi-tenant access; the public deployment is a bounded demonstration.

### Outside this product

- Safety certification, autonomous maintenance, or diagnostic claims.
- Video ingestion; the product inspects still photographs.
- The Best Use of COOL Award: the entry does not run COOL.

## Assumptions

- Operators revisit the same asset from a comparable viewpoint; if framing varies too much,
  alignment fails and most captures end `unrecognized_asset`.
- Comparing against the previous state is worth more to an O&M technician than a stronger
  single-image classifier. No external cost figure backs this; if it is false, the Real-world impact
  story rests only on the agent's own measured cost.

## Outstanding questions

- What does an O&M technician do today to inspect a module, and what does it cost, from a source
  that can be verified? — blocks: R9 | resolve before planning: no
