# Devpost entry — afterimage

Text to paste into https://devpost.com/software/afterimage-ibp376 (edit view). Adopted from the
entry published on 7 September and brought up to the current product. Field limits are `not
published` (see [HACKATHON.md](HACKATHON.md)), so headings carry `(-)`. Each figure carries its
source in an HTML comment; comments are not pasted.

## Project name (-)
afterimage

## Elevator pitch (-)
A visual inspection agent that remembers. It aligns every photo to the stored baseline of the same asset with OpenCV 5, and a measured number decides what it does next.

## Inspiration (-)
Every prior OpenCV competition winner analyses one frame, or one session. None of them remember.

But what matters in industrial inspection is not what a panel looks like today — it is what changed since the last time anyone looked at it. Photovoltaic degradation is the clearest case: potential-induced degradation costs affected modules around 15% a year and is partially reversible if caught before saturation, soiling costs 5–20% of annual energy, and a utility-scale plant carries roughly 2,900 modules per MW. <!-- src: docs/TECHNICAL_REPORT.md §1–§2, IEA-PVPS T13-09:2017 and reference [1] --> Nobody can look at them all, twice.

So the question was never "can a model find a crack". It was: can an agent keep the memory of an asset across inspections, and act on the difference?

## What it does (-)
afterimage inspects physical assets from still photographs and compares every capture against the memory of the same asset. Each branch is decided by a number, and the number is on screen:

- **It gates its own input.** `blur_variance` under 100, or a frame too dark, too bright or clipped, and the capture is sent back for a recapture instead of being scored. <!-- src: services/agent/policy.py Policy.blur_variance_min -->
- **It knows which asset it is looking at.** Leave the asset ID empty and it votes among the stored baselines; a split or thin vote ends `unidentified` instead of a guess. <!-- src: services/agent/policy.py identity_* -->
- **It anchors to memory.** OpenCV 5 `Features` (ALIKED + LightGlue) aligns the new capture to the stored baseline. Under an `inlier_ratio` of 0.90 it retries with ORB, and under 0.30 it refuses the asset rather than comparing the wrong one. <!-- src: services/agent/policy.py inlier_ratio_min_neural, inlier_ratio_min_classic -->
- **It looks closer on its own.** A `mean_delta` between 30 and 35 is uncertain, so it crops the region and rescans it at twice the resolution on each axis instead of reporting a maybe. <!-- src: services/agent/policy.py diff_delta_threshold, mean_delta_confirm; services/perception/diffing.py scale=2.0 -->
- **It escalates to a human.** A severity score at or above 0.4 waits in an approval queue before anything is written to memory. A rejection keeps the reviewer's reason; an approval is followed by reading memory back to confirm the baseline that was written. <!-- src: services/agent/policy.py severity_score_approve -->

Every decision is a trace event carrying `{metric, value, threshold, branch}`, hash-chained so an edit or a removed event is detected, and any run can be replayed from it. A language model orders the tool calls over MCP and phrases the result; it cannot move a threshold, skip the mandated next tool, or submit a branch the evidence did not produce.

A judge can walk it in a minute: the landing opens a guided tour that runs the first baseline, a recapture, a human-gated crack and a foreign panel on bundled samples, over a demo asset of their own. The interface reads in English or Spanish, in plain or technical language, in a light or dark theme, and works by keyboard.

## How we built it (-)
Six perception tools — identify, quality, alignment, diff against memory, crop-and-rescan, severity — run in an arm64 OpenCV 5 container on AWS Lambda (Graviton) and are exposed over MCP. <!-- src: services/mcp_server/server.py --> The loop opens an in-process MCP session to them, and the same server answers any outside MCP client over stdio.

Memory is a single DynamoDB table that returns an asset's whole history in one query, with images in S3 and baselines that are superseded rather than overwritten. The policy lives in one file: perception reports numbers, and how they combine and what threshold each meets is the policy's business and nothing else's.

Delivery is CloudFormation from GitHub Actions over OIDC with a permissions boundary, exact pins, an image retention policy, and a calibration check that takes the service out of rotation if the alignment stack stops answering as expected. A failed run can be retried into a new run without touching the original record. An inspection takes 20.4 s and bills $0.0005 at list price. <!-- src: README.md footer; docs/TECHNICAL_REPORT.md §7, Lambda REPORT lines and the Price List API -->

## Challenges we ran into (-)
OpenCV 5 broke compatibility with everything the models know: `Features2D` is now `Features`, the C API is gone, ML and G-API moved to contrib. Every API had to be verified against the 5.x docs rather than recalled. The OpenCV 5 DNN engine has no GPU support, so the system was designed for CPU on Graviton from the first commit instead of being ported later.

The harder problem was honesty. It is easy to build a demo where the agent looks decisive. It is much harder to make every decision reconstructible — which is why the causal link is a field in the trace, not something a judge has to infer by reading several events in order:

`{"input_metric": "inlier_ratio", "value": 0.0385, "threshold": 0.3, "branch": "unrecognized_asset"}` <!-- src: published entry, 7 September trace -->

## Accomplishments that we're proud of (-)
29 scenarios, 18 of them on licensed photographs of real photovoltaic modules. 24 pass every assertion: branch, defect class and required decision path. <!-- src: make eval → eval/results/latest/results.json summary.scenarios, summary.real, summary.passed -->

| Metric | Score |
|---|---|
| Branch accuracy | 0.8621 (macro F1 0.8624) |
| Defect macro F1 | 0.8542 (precision 0.75 or better on every defect class) |
| Mean IoU | 0.7875 |
| Scenarios passed | 24 / 29 |

<!-- src: make eval → eval/results/latest/results.json summary.branch, summary.defect, summary.iou; anchored by eval/tests/test_published_numbers.py -->

The five failures are published, each traced to a root cause rather than explained away. The test suite fails if any headline figure drifts from the evaluation artefact, so the README cannot quietly disagree with the numbers.

## What we learned (-)
The interesting part of an agent is not the reasoning, it is the refusal. An unusable capture sent back, an unrecognised asset refused instead of guessed, a severe finding that waits for a human — those are the behaviours that make the loop the product rather than the demo.

And a verification gate catches what review does not. Several bugs shipped past careful reading and were caught only by a check that ran the real thing.

## What's next for afterimage (-)
The published failures are the roadmap: a coverage gate that cannot take one global default, an exposure gate firing before severity is ever assessed, a severity score that ignores the class the classifier just produced, and a soiling rule calibrated on a synthetic panel that does not survive real texture. Beyond that: field validation on plant imagery outside the committed dataset.

Known limitations: the published effectiveness applies to the committed dataset only and is not field accuracy; the trace's hash chain detects ordinary editing but is not a signed audit log; the public deployment has no login and is a bounded demonstration.

## Built With (-)
opencv, amazon-web-services, aws-lambda, amazon-dynamodb, amazon-s3, aws-cloudformation, arm64, onnx, mcp, gemini, python, fastapi, docker, github-actions

## Try it out (-)
- https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/
- https://github.com/gmassello/afterimage
- https://gmassello.github.io/afterimage/

## Video demo link (-)
https://www.youtube.com/watch?v=zUFR96a33IM

## Criteria coverage
| Criterion | Weight | Paragraph |
|---|---|---|
| Technical execution | 30% | What it does; How we built it; Accomplishments |
| Innovation | 20% | Inspiration; What it does (memory, active rescan) |
| Real-world impact | 20% | Inspiration |
| User experience | 10% | What it does (guided tour, toggles) |
| Documentation and presentation | 10% | Accomplishments (figures anchored by tests); Try it out; Video |
| Cloud delivery, reproducibility, and responsible operation | 10% | How we built it (delivery, calibration, cost); Known limitations |
| Substantive OpenCV 5 and agent integration | 30% | What it does; How we built it (six MCP tools) |
| Orchestration and appropriate autonomy | 25% | What it does (enforced order, model cannot move a threshold) |
| Task effectiveness and evaluation | 20% | Accomplishments |
| Failure handling, observability, security, and human control | 15% | What it does (trace, human gate, reobservation); How we built it (retry) |
| User experience, documentation, and demonstration | 10% | What it does (tour); Video |
