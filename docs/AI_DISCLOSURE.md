# Use of AI

Two different things get called "AI use" in a project like this, and they deserve separate answers:
what a model does **inside the product**, and what assistance was used **to build it**.

## 1. In the product

A large language model (Gemini, reached over MCP) selects the next allowed tool call and its
arguments during a run. The loop enforces the stage order. That is the agentic part, and it is
deliberately fenced:

- **It cannot move a threshold.** Every branch verdict is computed in code by
  `services/agent/policy.py`, which is the only place a metric is compared to a constant.
- **It cannot misreport one.** The loop enforces which tool may come next and refuses a submission
  whose branch differs from the last policy verdict (`services/agent/loop.py`).
- **It is not required.** Without `GOOGLE_API_KEY` the loop falls back to
  `services/agent/scripted.py`, a deterministic policy-following driver. Tests, `make demo` and the
  whole evaluation run that way, with no network and no tokens — which is why the published numbers
  are reproducible.

The consequence worth stating plainly: the system's decisions do not depend on the model provider,
its version or prompt phrasing. Swapping the model changes the phrasing of a run, not its outcome.

Nothing is sent to the model provider except the tool names, their arguments and the numeric metrics
the perception tools return. Images are not sent to it; they stay in S3 and are read by the OpenCV
tools running inside the container.

## 2. In building it

This project was written with the help of LLM-based coding assistants. Stating that is the point of
this file; what matters more is which parts were verified by hand rather than accepted.

**What the assistance was used for:** drafting and refactoring code, writing and revising
documentation, and generating test scaffolding.

**What was verified rather than trusted:**

- **Every OpenCV 5 API.** Model training data covers OpenCV 4, and OpenCV 5 broke compatibility, so
  each API was checked against the 5.x documentation and against a running `5.0.0` build on
  `aarch64`. Three behaviours that the documentation did not settle were measured against the binary
  and written down in §5 of the [technical report](TECHNICAL_REPORT.md).
- **Every published number.** Figures in the README, this repository's documentation, the public page
  and the video script are asserted against `eval/results/latest/results.json` by
  `eval/tests/test_published_numbers.py`, which fails the suite if a number goes stale. The
  evaluation that produces that artefact runs the real loop, the real tools and the real thresholds.
- **Every claim about the system's behaviour**, by running it: `make test`, `make eval` and
  `make demo` against the container, and the failure cases reproduced against the public endpoint.

**What this is not:** using a coding assistant is not what makes this project agentic. The
competition says so explicitly, and so does this repository — the agentic loop lives in the product,
in `services/agent/`, where a visual measurement changes what the system does next. The development
process is not part of that claim.

**Responsibility.** The author is responsible for everything in this repository: the design, the
thresholds, the claims and the errors. Where the system is wrong, the five analysed failures in
[`EVALUATION.md`](EVALUATION.md) say so with the number that caused each one.
