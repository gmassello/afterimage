# OpenCV AI Competition 2026 — event brief

> Read from https://opencv26.devpost.com/, `/rules` and `/details/dates` on 2026-09-30. Values the
> pages do not publish are marked `not published`.

## Event

- **Name:** OpenCV AI Competition 2026, powered by AWS
- **URL:** https://opencv26.devpost.com/
- **Administrator:** OpenCV Foundation
- **Sponsor:** Amazon Web Services (AWS)
- **Format:** online, public; 3493 participants at the time of reading
- **Prize pool:** $20,250 listed on Devpost ($12,000 in cash awards plus 55 × $150 compute grants)
- **Our entry:** Agentic Vision path — https://devpost.com/software/afterimage-ibp376

## Timeline

Local zone is `America/Argentina/Buenos_Aires` (-03:00). Converted with `zoneinfo`.

| Stage | Event zone | Local |
|---|---|---|
| Submissions open | 2026-08-26 00:00 -07:00 | 2026-08-26 04:00 -03:00 |
| **Submissions close** | **2026-10-26 23:45 -07:00** | **2026-10-27 03:45 -03:00** |
| Public voting | 2026-10-26 00:00 -07:00 → 2026-11-09 23:45 -08:00 | 2026-10-26 04:00 -03:00 → 2026-11-10 04:45 -03:00 |
| Judging | 2026-10-27 00:00 -07:00 → 2026-11-09 23:45 -08:00 | 2026-10-27 04:00 -03:00 → 2026-11-10 04:45 -03:00 |
| Winners announced | 2026-11-10 09:00 -08:00 | 2026-11-10 14:00 -03:00 |

The overview text says final projects are due "October 26, 2026, at 11:59 p.m. Pacific Time"; the
Devpost schedule closes the form at 23:45 PDT. The earlier time (23:45) is the binding one.

Winners are announced during an OpenCV Live! webinar or another announced OpenCV channel. Grant
recipients must complete a 30-minute Zoom check-in between October 7 and 14 (hour and zone
`not published`) to receive the second 50% of the grant.

## Prizes and tracks

| Prize | Amount | Winners | Qualifies when |
|---|---|---|---|
| First Place | $5,000 | 1 | Overall rubric |
| Second Place | $3,000 | 1 | Overall rubric |
| Third Place | $2,000 | 1 | Overall rubric |
| Best Use of COOL Award | $1,000 | 1 | COOL executes the claimed core workload on AWS Graviton or the Arm component of a documented hybrid architecture |
| Agentic Vision Award | $1,000 | 1 | Image or video results influence a subsequent plan, tool call, action, or request for human approval |
| Compute Grant for AWS | $150 | 55 | Selected from grant proposals |

"An entry may receive no more than one Overall Award and may also receive one or both Special
Awards." A special award "may remain unawarded" if no entry satisfies its qualifying requirements.

**Agentic Vision path** — "A chatbot that only explains a fixed vision result is not enough—the
visual evidence must change what the system does next." "Using an AI coding assistant to write the
entry does not qualify as an agentic workflow." Additional evidence required:

- An agent workflow diagram showing perception, decision or orchestration, and action.
- A trace or demonstration showing that OpenCV 5 output changes a later decision, tool call, or action.
- Evaluation of task success, failure handling, observability, and appropriate human control.

**COOL path** — additional evidence: the COOL version and AWS instance or deployment configuration;
a reproducible evaluation method, inputs, baselines, and results; evidence that COOL executes the
claimed core workload.

## Judging criteria

Each entry receives at least two independent, conflict-free scores; rankings use their average.
Overall ties break by Technical execution, then Real-world impact.

### Overall rubric

| Criterion | Weight | Rule text |
|---|---|---|
| Technical execution | 30% | "correctness and depth of the OpenCV 5 implementation, architecture, reliability, and evaluation." |
| Innovation | 20% | "originality and thoughtful use of computer vision or AI." |
| Real-world impact | 20% | "importance of the problem, usefulness, and evidence of potential benefit." |
| User experience | 10% | "usability, accessibility, and quality of interaction." |
| Documentation and presentation | 10% | "clarity of the report, code, architecture, instructions, and video." |
| Cloud delivery, reproducibility, and responsible operation | 10% | "AWS deployment quality, repeatability, observability, security, and responsible-use practices." |

"COOL or agentic methods are not required for the Overall Awards. When present, judges will credit
them within the applicable overall criteria only to the extent that they improve the project."

### Agentic Vision Award rubric

| Criterion | Weight |
|---|---|
| Substantive OpenCV 5 and agent integration | 30% |
| Orchestration and appropriate autonomy | 25% |
| Task effectiveness and evaluation | 20% |
| Failure handling, observability, security, and human control | 15% |
| User experience, documentation, and demonstration | 10% |

### Best Use of COOL Award rubric

| Criterion | Weight |
|---|---|
| Verified COOL integration on AWS Graviton, or on the Arm component of a documented hybrid architecture | 30% |
| Architecture and technical quality | 25% |
| Measured performance, cost, reliability, or developer-productivity value | 20% |
| Innovation | 15% |
| Reproducibility and demonstration | 10% |

Judges listed: Phil Nelson (Director of Content & Creative, OpenCV) and Gary Bradski (Founder,
OpenCV). AWS may nominate up to two judges.

## Required tech

- **OpenCV 5** — "Every entry must use OpenCV 5 for substantive image or video analysis." Proven
  through the technical report, the code repository, and the architecture diagram.
- **AWS** — "run a meaningful component on AWS." Proven through the AWS deployment section of the
  report, the architecture diagram, and a working web endpoint.
- **COOL** — only for the COOL award; not used by this entry.

Any programming language or supporting hardware is allowed.

## Submission requirements

- A technical report describing the problem, users, architecture, OpenCV 5 implementation, AWS
  deployment, evaluation, limitations, and responsible-use considerations. Format `not published`.
- A public or private judge-accessible code repository or archive (need not be open source).
- Pinned dependencies plus clear build, deployment, and test instructions.
- An architecture diagram showing the OpenCV 5 and AWS components and, where relevant, COOL or
  agent components.
- A working web endpoint or an arranged live screen-share demonstration.
- A public or unlisted judge-accessible video of **no more than five minutes** that shows the team,
  the application working, its architecture, and its principal results. Format and host `not published`.
- Evaluation evidence appropriate to the project, including failure cases or limitations.
- Deck: `not published` (not required).
- Devpost form field character limits: `not published` on the public pages.

## Disqualifiers

- Participants must be at least 13; minors need parent or guardian permission. Every team member
  must be eligible; the team designates one representative.
- Excluded: employees and contractors directly involved in administering or judging, and their
  household members; countries under Devpost's standard exceptions.
- Manipulating registration, voting, judging, or platform traffic. Disclosed agents integral to the
  project are allowed.
- Judges may reject an entry that uses data, models, or media without rights or consent; creates
  safety, privacy, security, discrimination, or surveillance risks without safeguards; contains
  abusive content; **misrepresents capabilities, results, benchmarks, or the role of human review**;
  or violates OpenCV, AWS, Devpost, or third-party terms.
- The organizers may disqualify an ineligible, incomplete, misleading, unsafe, unlawful, or
  rules-violating entry.
- Public repository, new-code-during-event, team size and license rules: `not published`.
- Submitted materials (report, presentation, video) are licensed to OpenCV and AWS perpetually and
  royalty-free; the code itself is not.

## Blockers

- Devpost submission must be completed and submitted by the team representative before
  2026-10-26 23:45 -07:00.
- The video must be uploaded as public or unlisted and reachable without login.
- The web endpoint must be live throughout judging (2026-10-27 → 2026-11-09), or a live screen-share
  must be arranged with the organizers.
- If this entry holds a compute grant: the Zoom check-in between October 7 and 14.
