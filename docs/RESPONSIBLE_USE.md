# Responsible use

What this system is for, what it is not, and what its numbers do and do not authorise anyone to
claim. Written to be read before the technical report, not after it.

## What it does

afterimage compares a new photograph of a physical asset against the stored baseline of that same
asset and reports what changed, by how much, and which threshold that value crossed. Every branch it
takes is decided in code by `services/agent/policy.py` and recorded with the number that triggered
it, so any run can be replayed from its trace.

## What it is not

- **It assists an inspection; it does not sign one off.** A defect classification here is a
  prioritisation signal for a technician — look at this module before that one — not a certification
  of a module's condition, and not an input to a warranty, insurance or safety decision on its own.
- **It is not a detector of naturally occurring defects.** Every lesion in the evaluation was injected
  by us. That is what makes the ground truth exact, and it is also what limits the claim: the numbers
  describe whether the thresholds survive real photographic texture, not field detection rates. No
  public dataset offers what the longitudinal claim needs — the same physical panel photographed
  twice, months apart.
- **It is not a monitoring service.** It is a competition demonstrator on a free-tier account, with a
  public endpoint and 180-day data expiry.

## Where a human stays in the loop

On a severe finding the run stops at `awaiting_approval` and **nothing is written to memory** until
someone resolves it (`services/agent/hitl.py`). Both approval and rejection are recorded in the trace.

Two honest qualifications:

- The gate stops the machine from writing on its own. It does not authenticate an operator — the
  endpoint is public, so the person resolving it is any visitor holding the URL. See
  [`SECURITY.md`](SECURITY.md).
- The gate fires on a policy threshold, not on model judgement. Raising or lowering
  `severity_score_approve` changes how much a human sees; the model cannot change it either way.

## Bounded by construction, not by trust

Branch verdicts are computed in code. The language model chooses tool arguments and phrasing; it
cannot move a threshold, and the loop refuses a submission whose branch differs from the last policy
verdict (`services/agent/loop.py`). So the system's decisions do not depend on the model provider,
its version, or prompt phrasing — and the evaluation, which substitutes a scripted driver for the
model, measures the same decisions the public endpoint makes. See
[`AI_DISCLOSURE.md`](AI_DISCLOSURE.md).

## What the published numbers allow you to say

The full method, the per-class tables and the five analysed failures are in
[`EVALUATION.md`](EVALUATION.md). In short:

- **Fair:** "on 29 scenarios, 18 of them built on photographs of real photovoltaic modules, the agent
  picked the right branch 86% of the time, and never asked a human to look at something that did not
  warrant it."
- **Not fair:** "it detects 86% of defects in the field." Nothing here measures that.

Known limits are listed in full in `EVALUATION.md` and in §9 of the
[technical report](TECHNICAL_REPORT.md). The ones that bear on how much to trust an output:

- Defect classification is a threshold heuristic over OpenCV features, not a trained classifier, and
  one of its rules — soiling, recognised by the area a change covers — does not transfer from the
  generated panel to a photograph.
- Severity scores how much changed and ignores the label its own classifier produced, so a small but
  serious defect can be filed automatically instead of escalated. Observed once, at 0.3412 against a
  0.40 threshold.
- Frame-coverage checking ships disabled: across healthy real photographs it reads anywhere from
  0.0032 to 0.6357, so no single global default separates a good capture from a badly framed one.
- The sample is small. One scenario moves accuracy by 3.4 points.

## Images and privacy

Uploads are public to anyone holding the endpoint URL and expire after 180 days. The approver of a
human-gated inspection is recorded as an unsalted fingerprint of address and user agent — enough to
tell two actors apart in a trace, not an anonymity guarantee. Do not upload photographs containing
people, plates, documents or anything else you would not publish. Details in
[`SECURITY.md`](SECURITY.md).
