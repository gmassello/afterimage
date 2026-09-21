# Evaluation — dataset, metrics and failure cases

Regenerate everything here with `make eval`. It writes `eval/results/latest/results.json` (one
record per scenario, including the full decision path) and `eval/results/latest/summary.md` (the
tables below). Both are committed, so every number on this page can be traced to the run that
produced it — `eval/tests/test_published_numbers.py` fails the suite if this page and the artefact
ever disagree.

## What this measures, and what it does not

The harness runs the **real agent loop** end to end: the same `services/agent/loop.py`, the same MCP
perception tools, the same `services/agent/policy.py` thresholds that the public endpoint runs. What
it substitutes is the language model, replaced by the scripted driver in
`services/agent/scripted.py`.

That substitution costs nothing in validity and buys reproducibility. Branch verdicts are computed
in code by `policy.evaluate()`, never by the model, and the loop rejects a submit that names the
wrong branch (`loop.WRONG_BRANCH`, in `services/agent/loop.py`). The model supplies tool arguments and the final
submit; it cannot move a threshold. So these numbers measure perception and policy — which is what
"task effectiveness" means here — and they are identical on every run, with no network and no tokens.

What the harness does **not** measure: detection of naturally occurring defects. Every lesion is
injected by us, which is what makes the ground truth exact, and also what makes this a measurement
of whether the thresholds survive real photographic texture rather than a field trial. The
distinction matters and is not papered over anywhere below.

## The dataset

29 scenarios, declared in `eval/dataset/scenarios.json` — a manifest, not code, so a judge can read
what was tested without reading Python.

| Source | Scenarios | Base images |
|---|---:|---|
| Synthetic | 11 | `services/perception/panels.py`, the same generator the unit tests use |
| Real photographs | **18** | 18 Wikimedia Commons photos of photovoltaic modules, committed under `eval/dataset/base/` |

Every photo's author and licence is listed in `eval/dataset/SOURCES.md`. They are committed rather
than downloaded so `make eval` is offline and deterministic.

Each scenario names a base image, a chain of transformations, and what the agent is expected to do.
The expectations encode what the system **should** do — a crack should escalate to a human — not
what it was observed doing. Five of them are currently wrong, and that is the point of the failure
section.

## Results

29 scenarios — 11 synthetic, 18 on real photographs. **24 passed** every assertion (branch, defect
class and required decision path). **Most of the suite runs on photographs**: 18 of 29.

Branch accuracy **0.8621**, macro F1 **0.8624**. Defect accuracy **0.9231**, macro F1 **0.8753**.

### Agent branch

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `auto_write` | 3 | 0.75 | 1.0 | 0.8571 |
| `first_baseline` | 1 | 1.0 | 1.0 | 1.0 |
| `human_approval` | 14 | 1.0 | 0.8571 | 0.9231 |
| `no_change` | 3 | 1.0 | 1.0 | 1.0 |
| `recapture` | 6 | 0.8 | 0.6667 | 0.7273 |
| `unrecognized_asset` | 2 | 0.5 | 1.0 | 0.6667 |

`human_approval` keeps **precision 1.0** over 14 scenarios: the agent never asked a human to look at
something that did not warrant it. Its recall of 0.8571 is the cost, and both misses are analysed
below.

### Defect class

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `NONE` | 12 | 0.9231 | 1.0 | 0.96 |
| `crack` | 4 | 1.0 | 1.0 | 1.0 |
| `delamination` | 4 | 1.0 | 1.0 | 1.0 |
| `hotspot` | 4 | 0.75 | 0.75 | 0.75 |
| `soiling` | 2 | 1.0 | 0.5 | 0.6667 |

The three `faint-spot` scenarios are excluded from this table (`"score_defect": false` in the
manifest). They inject a marginal darkening to exercise the zoom branch, not a member of the
taxonomy; scoring them against a class the fixture does not represent would inflate the numbers.

### Localisation

Mean IoU **0.7875** over the 14 scenarios where a region was both injected and detected, 12 of them
at IoU ≥ 0.5. Ground truth is the region actually altered, not the bounding box passed to the
injector — `faint_spot_at` darkens 35% of its box and `hotspot_at` draws an inscribed circle, so
`eval/scenarios.py:_altered_region` narrows the truth accordingly. Scoring against the full box
instead reported mean IoU 0.6515, which measured the harness rather than the detector.

## Where it fails

Five scenarios out of 29, each with the number that decided it.

| Scenario | Expected | Got | Deciding number |
|---|---|---|---|
| `recapture-partial-frame-synthetic` | recapture | unrecognized_asset | `inlier_ratio` 0.0602 vs 0.3 |
| `recapture-partial-frame-real-arapaho` | recapture | unrecognized_asset | `inlier_ratio` 0.1232 vs 0.3 |
| `hotspot-real-plain` | human_approval / hotspot | recapture / NONE | `clipped_bright_ratio` 0.3086 vs 0.3 |
| `delamination-real-packed` | human_approval / delamination | auto_write | `score` 0.3412 vs 0.4 |
| `soiling-real-forest` | human_approval / soiling | human_approval / hotspot | `area_ratio` 0.0759 vs 0.25 |

**1. A partially framed capture is rejected for the wrong reason.** The quality gate should catch a
frame that only contains a quarter of the panel, but `coverage_ratio_min` is disabled by default, so
quality passes; alignment then fails on the shrunken panel and the run ends in `unrecognized_asset`.
The operator is told the wrong thing: "this is not the asset you think it is" instead of "step
back and reframe". The outcome is safe — nothing is written to memory — but the diagnosis is wrong.
See the coverage verdict below for why the gate is still off. The photographic twin of this scenario
fails the same way (`inlier_ratio` 0.1232), which is the useful part: the diagnosis is not an
artefact of the generated panel, it is the gate ordering itself.

**2. A bright defect can trip the exposure gate before it is ever assessed.** Injecting a hotspot
onto an already bright photograph pushed `clipped_bright_ratio` to 0.3086, just over the 0.30 limit,
so the agent asked for a recapture and never reached severity. This is arguably correct behaviour —
the image genuinely is clipped, and measuring a defect through blown highlights would be worse — but
it is a real ordering effect: gates fire in sequence, and an early gate can mask a later finding.
It is the single reason `hotspot` recall is 0.75 rather than 1.0.

**3. Severity underestimates a defect that covers a small area.** A delamination on a real
photograph scored 0.3412, under the 0.40 approval threshold, so it was written automatically instead
of escalating. Root cause is structural, not a bad threshold: `score` is
`mean_delta / severity_full_scale_delta` in `severity.classify_severity` and **ignores the label
the classifier just produced**. The
classifier is confident enough to say "delamination" and the score does not use that at all. Raising
the threshold would not fix it; making the score class-aware would. That change is not made here —
this stage produces the evidence, and rewriting the scoring function on the strength of one scenario
would be exactly the overfitting this dataset exists to prevent.

**4. Soiling is recognised by area, and the area threshold does not survive a photograph.** The
classifier calls a change `soiling` when the changed region covers more than 25% of the frame
(`AREA_RATIO_SOILING`), a threshold measured on the synthetic panel, where the blurred dust ellipse
clears the diff threshold across most of the image. On a photograph the same ellipse only clears it
over the darkest cells, the change breaks into fragments, and the largest one reaches 0.0759 — so
the frame falls through to the brightness rule and is labelled `hotspot`. The branch is still right
(`human_approval`, score 0.684), and nothing is written without a person; the label is wrong. This
was measured across all six new photographs and none of them reached 0.25, so it is a property of
the rule, not of one image. The fix is to test soiling against the total changed fraction rather
than the largest connected component — left unmade here for the same reason as the one above.

## The two verdicts this stage owed

### `severity.py`: the threshold heuristic holds

`severity._label` carried a note saying to replace the heuristic with a trained
classifier if the evaluation showed the classes did not separate. They mostly separate: macro F1
**0.8753**, precision 1.0 on `crack` and `delamination` and at least 0.75 on all four classes. The
two misses are not confusions between neighbouring classes — one (case 2 above) is an exposure gate
firing first, and one (case 4) is the soiling rule's area threshold failing to transfer from the
generated panel to a photograph. **Still no classifier is warranted**: both are rules that can be
stated and fixed, not a boundary a model would have to learn. The note stays in the code, now with a
measured reason to leave it unspent and a named condition — if the soiling rule is rewritten and the
classes still collide, that is when it gets spent.

### `coverage_ratio_min`: cannot be enabled with one global default

`Policy.coverage_ratio_min` disables the frame-coverage check because the contour heuristic reads
approximately zero on synthetic fixtures. Real photographs let us test that for the first time, and
the finding is worse than "the synthetic images are unrepresentative":

| Capture | `coverage_ratio` |
|---|---:|
| Partially framed panel (the case the gate exists to catch) | 0.0000 |
| Good synthetic panel | 0.0009 |
| Good real photograph, worst case (`no-change-real-warehouse`) | 0.0032 |
| Good real photograph, best case (`delamination-real-jetion`) | 0.6357 |

Real captures span **0.0032 to 0.6357**, a 200-fold spread across images that are all perfectly
usable. Any threshold low enough not to reject the good real photographs is also low enough to admit
a good synthetic panel at 0.0009 — and the degraded capture reads exactly 0.0000, so there is a
window, but it is narrower than the spread of the healthy population. The metric is measuring
"how much contrast the largest contour encloses", which depends on the framing and background of a
given site far more than on whether the panel is fully in frame.

**Verdict: the default stays 0.0.** It is documented as a per-deployment setting, calibrated from a
sample of that site's own captures, with 0.0032 as the measured floor to start from. The alternative
is swapping the contour heuristic for segmentation, which is the upgrade path the code comment
already names.

## `crop_and_rescan` (ACTION 3), reproduced

Stage 6 could not reproduce the zoom branch against the public endpoint: four attempts at deltas 10,
16 and 22 landed on either side of the window. The harness found it, on both a synthetic fixture and
a real photograph, and measured the window exactly. Sweeping the injected darkening on
`module_et_solar_1.jpg`:

| Injected delta | `mean_delta` | Path |
|---:|---:|---|
| 10, 12, 14 | — | no region detected → `no_change` |
| **16** | **33.34** | `crop_and_rescan` → `change_confirmed` → `auto_write` |
| **18** | **34.37** | `crop_and_rescan` → `change_confirmed` → `auto_write` |
| 20 | 35.54 | crosses `mean_delta_confirm`, confirms without zooming |

The branch is not rare, it is **narrow**: a change has to be strong enough to clear the diff's
`diff_delta_threshold` of 30 and weak enough to stay under `mean_delta_confirm` of 35. Stage 6 was
sampling a two-point-wide window by hand.

Both `faint-spot-synthetic` and `faint-spot-real-et-solar` now walk
`quality_ok → aligned → crop_and_rescan → change_confirmed → auto_write` on every run.

With the window known, the branch was then reproduced **against the public endpoint**, which is what
stage 6 left open. Two `POST /inspections` on a fresh asset, baseline then the delta-16 capture:

```
assess_quality       blur_variance     2237.0408 vs 100.0  -> quality_ok
align_to_baseline    inlier_ratio            1.0 vs 0.9    -> aligned
diff_against_memory  mean_delta          33.3427 vs 35.0   -> crop_and_rescan
crop_and_rescan      area_ratio           0.1702 vs 0.02   -> change_confirmed
classify_severity    score                0.2596 vs 0.4    -> auto_write
```

Live trace: <https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/traces/90472757e472>.
Every value above is identical to the one the local container recorded for the same scenario —
`blur_variance` 2237.0408, `inlier_ratio` 1.0, `mean_delta` 33.3427, `area_ratio` 0.1702, `score`
0.2596, to four decimals on all five. That is the second-channel check this stage owed: the numbers
that drive the decisions do not move between where they are measured and where they are served.

## Limits of this evaluation

- **The defects are injected, not natural.** That is what makes the ground truth exact, and it means
  these numbers describe threshold robustness on real texture, not field detection rates. No public
  dataset offers what the longitudinal claim needs — the same physical panel photographed twice.
- **29 scenarios is a small sample.** A single scenario moves accuracy by 3.4 points. The per-class
  figures on `soiling` (support 2) are indicative at best.
- **One base photograph per real scenario.** Backgrounds, angles and lighting vary across the
  eighteen — close-range modules, ground-mounted rows, rooftop and warehouse arrays, a marine
  installation, panels under forest canopy — but no scenario is repeated across them, so per-class
  results on real photos are not averaged over conditions.
- **Alignment is exercised, not stressed.** Captures are shifted by a fixed affine warp
  (`shifted()`: 6°, 3% scale, 12 px). Real revisits three months apart will differ by more.
- **The scripted driver takes the policy's own advice.** It follows the branch the policy names, so
  it cannot demonstrate recovery from a model that goes off-script. The loop's guardrails against
  that are covered by `services/agent/tests/test_loop.py`, not by this harness.
