# Functional guide

This document is the canonical description of what Afterimage does from an operator's point of
view. Implementation details live in [ARCHITECTURE.md](ARCHITECTURE.md),
[BACKEND.md](BACKEND.md), and [FRONTEND.md](FRONTEND.md).

## Purpose

Afterimage inspects a physical asset repeatedly from photographs. It compares each usable capture
with the accepted baseline of the same asset, records the evidence behind every decision, and keeps
a longitudinal history instead of judging each image in isolation.

The current evaluation domain is photovoltaic modules. The product assists an inspection; it is not
a safety certification, autonomous maintenance system, or field-validated diagnostic device. See
[RESPONSIBLE_USE.md](RESPONSIBLE_USE.md) for the operating boundary.

## Core concepts

| Concept | Meaning |
|---|---|
| Asset | The physical object identified by a stable, operator-supplied ID. |
| Capture | The uploaded PNG or JPEG being inspected. |
| Inspection | The persisted result, metrics, label, branch, and capture for one accepted run. |
| Run | One execution of the inspection loop, including its trace and terminal state. |
| Baseline | The accepted reference image against which the next capture is aligned and compared. |
| Pending approval | A severe finding that cannot update memory until a human approves it. |
| Retry | A new run opened from a failed run, reusing its asset and capture without changing the original trace. |

Baselines are superseded rather than overwritten. The asset history therefore records which image
was the reference at each point in time.

## Operator journey

1. Open the public landing page at `/` to understand the product, evidence, and limits.
2. Enter the inspection workspace at `/app` and provide an asset ID.
3. Upload a capture or choose one of the included sample images.
4. Confirm the image and start the inspection.
5. Follow the live trace while the loop assesses quality, alignment, change, and severity.
6. Act on the terminal result. Severe findings appear in the approval queue; accepted findings
   appear in the asset history.
7. Use `/activity` to find recent runs by asset, run ID, branch, status, or message. A failed run can
   be retried from its trace without changing or replaying the original record.

The upload and execution are deliberately separate. `POST /inspections` validates and stores the
capture, opens a run, and redirects to its trace. The trace page then starts the long-running loop
through `POST /runs/{run_id}/execute`.

## Inspection outcomes

| Outcome | What it means | Effect on memory |
|---|---|---|
| `first_baseline` | The asset had no baseline and the first capture passed quality checks. | Stores the inspection and promotes the capture. |
| `recapture` | The image is too blurred, dark, bright, clipped, or otherwise unsuitable. | Stores no inspection and leaves the baseline unchanged. |
| `unrecognized_asset` | The capture cannot be aligned reliably with the stored baseline. | Stores no inspection and leaves the baseline unchanged. |
| `no_change` | The aligned capture contains no material change. | Stores the inspection without promoting a new baseline. |
| `auto_write` | A change exists but remains below the human-approval threshold. | Stores the inspection and promotes the capture. |
| `human_approval` | A severe change requires a person to decide. | Writes a pending item; approval stores it and promotes it when its timestamp permits, while rejection leaves memory unchanged. |

`failed` is a run status rather than an inspection outcome. It preserves the trace up to the error,
writes nothing to asset memory, appears in `/activity`, and is the only status eligible for retry.

Perception functions only return measurements. Branches are decided in
`services/agent/policy.py`, and every decision event records its metric, measured value, threshold,
and chosen branch.

## Product surfaces

| Page | Purpose |
|---|---|
| `/` | Public explanation of the problem, workflow, measured evidence, stack, and limits. |
| `/app` | Inspection workspace with upload form, sample captures, and an asset gallery filterable by ID or latest branch. |
| `/activity` | Searchable and filterable list of the 50 most recent runs. |
| `/traces/{run_id}` | Live progress, tool calls, deciding values, image comparison, and integrity status. |
| `/queue` | Findings waiting for human approval or rejection. |
| `/assets/{asset_id}` | Baseline and chronological inspection history for one asset. |

The interface supports English and Spanish, plain and technical reading registers, light and dark
themes, keyboard navigation, reduced motion, and a progressively enhanced upload flow. English and
plain language are the defaults.

## Trust and limits

- The language model may choose tool arguments and wording, but it cannot set thresholds, change
  the enforced tool order, or submit a branch that disagrees with policy.
- Retrying is recovery, not history rewriting: only a terminal failed run is eligible, and the
  original trace remains available while a write-once marker identifies its one replacement run.
- A trace provides causal evidence for the run and a hash chain that detects ordinary editing,
  reordering, or removal in the middle of the event stream. It is not a signed audit log.
- The public deployment has no login and is intended as a bounded demonstration.
- Published effectiveness applies only to the committed evaluation dataset and must not be
  presented as field accuracy.

See [EVALUATION.md](EVALUATION.md) for current results and failure cases, [E2E.md](E2E.md) for the
browser walkthrough, and [SECURITY.md](SECURITY.md) for deployment and data-handling constraints.
