# Brief — OpenCV AI Competition 2026

> Working document for the build. It holds the competition rules, the project to build, the architecture, the weekly plan and the deliverables.
> Keep it at the repo root as `CLAUDE.md` (or as `docs/BRIEF.md`, referenced from `CLAUDE.md`).

---

## 0. What has to happen TODAY, before writing any code

**The compute grant proposal.** 50 grants of US$150, rolling review from 18 August, notifications from the 25th. No published closing date: it closes when the slots run out.

Form: https://www.jotform.com/form/262145877145059 — asks for name, email, team name, country and **a PDF**.

The PDF needs these eight points. 10% of the grant rubric goes to "team strength and relevant previous work", so all four prior repos go in with links:

1. **Team name** — whichever you pick from section 9.
2. **Problem and real-world impact** — two paragraphs.
3. **What image or video analysis with OpenCV 5** — name concrete modules (`Features` with ALIKED/LightGlue, `dnn`, `imgproc`).
4. **Architecture and AWS services** — S3, ECS Fargate on Graviton, DynamoDB, API Gateway, CloudWatch/OTel.
5. **Architecture diagram** — one only, one page.
6. **Target users**.
7. **Evaluation method and demo for the judges** — dataset, metrics, public endpoint.
8. **Which path you choose**: write **"Agentic Vision path"** explicitly (or "both" if you are also going for COOL).

Plus a **bio with previous hackathons and competitions** — github.com/gmassello/recall, /hindsight, /aiquest-minitel-client, /ringdown.

**And register on Devpost now**, even though the project does not exist yet: `/updates` and Discussions are empty, and the only announcement channel they will actually use is email to registrants.

> The proposal is for the grant, not to compete. Teams that are not selected remain eligible for every prize. But sending it costs nothing and closes the risk in the ambiguous sentence *"all teams that submitted the required proposal will build…"*.

---

## 1. Competition rules — hard constraints

Every design decision has to respect these.

| Rule | Detail |
|---|---|
| **OpenCV 5 mandatory** | For *substantive* image or video analysis. Using it to read a JPEG does not count. |
| **Significant component on AWS** | The vision workload runs on AWS. A front end on Vercel with inference on AWS qualifies; OpenCV on your laptop with AWS serving static files does not. |
| **No mandatory hardware** | "Any programming language or supporting hardware is allowed." No camera or device required. |
| **Deadline** | 26 Oct 23:59 PT = **Tuesday 27 Oct 03:59 ART**. |
| **Team** | 1 to 5 people. Solo is allowed. |
| **Repo** | Accessible to the judges. **It does not have to be open source** — it can be private with access granted. |
| **Video** | 5 minutes maximum, and it **must show the team** (your face), the app working, the architecture and the results. |
| **Demo** | A working web endpoint, or a coordinated live screen share. |
| **Agentic Award anti-cheat** | *"Using an AI coding assistant to write the entry does not qualify as an agentic workflow."* The agentic loop lives **in the product**, not in the development process. |
| **GPU** | The new OpenCV 5 DNN engine **has no GPU support yet**. Design for CPU/Graviton. |

### Overall rubric — where the score is won

| Criterion | Weight |
|---|---|
| Technical execution | 30% |
| Innovation | 20% |
| Real-world impact | 20% |
| User experience | 10% |
| Documentation and presentation | 10% |
| Cloud, reproducibility and responsible operation | 10% |

**60% is subjective judgement.** The narrative and the video weigh as much as the code.

### Agentic Vision Award rubric (US$1,000 extra)

| Criterion | Weight |
|---|---|
| OpenCV 5 + agent integration | 30% |
| Orchestration and appropriate autonomy | 25% |
| Task effectiveness and evaluation | 20% |
| **Failure handling, observability, security and human control** | 15% |
| UX and documentation | 10% |

The qualifying bar, verbatim:

> "…image or video results must influence a subsequent plan, tool call, action, or request for human approval. A chatbot that only explains a fixed vision result is not enough — **the visual evidence must change what the system does next**."

Mandatory extra evidence: a diagram of the perception → decision → action workflow, and **a trace proving that an OpenCV output changed a later decision**.

---

## 2. The project

### Concept: a visual inspection agent that remembers

An agent that inspects physical assets from photos or video, decides on its own what to look at next, and **keeps a memory of every previous inspection of the same asset** to detect degradation over time.

**Why this concept and not another:**

- **No previous winner had longitudinal memory.** Every awarded project analyses one frame or one isolated session. "The same asset, seen again three months later" is empty territory, and it is exactly Recall.
- **The perception → decision → action loop falls out naturally**, it is not forced. Image quality decides whether to ask for a recapture; the difference against the baseline decides whether to zoom; severity decides whether to ask for human approval. Three points where visual evidence changes what the system does next.
- **The 15% for failure handling and observability is Hindsight under another name.**
- **Defensible real-world impact** (20% of the rubric) without inventing anything: preventive maintenance of infrastructure.

**Suggested vertical:** inspection of **solar panels** from video or photos (defects: cracked cells, visible hot spots, soiling, delamination, misalignment). It is the one that best combines an available public dataset, degradation that is measurable over time, and a clear impact story.

**Alternative verticals**, if you prefer another — the architecture does not change:

- **Road infrastructure** — surveying potholes and signage from dashcam video, tracking the same stretch over time.
- **Retail shelf audit** — planogram compliance and drift detection against the reference.
- **Electrical panel / industrial equipment inspection** — corrosion, wiring, labels.

### The agentic loop — what qualifies for the award

This is the heart of the project. Every step marked **ACTION** is a point where the visual result changes what happens next.

```
   a capture (photo or frame) arrives for an asset with a known ID
              │
              ▼
   ┌──────────────────────────┐
   │ assess_quality()         │  OpenCV: blur (Laplacian), exposure,
   │                          │  framing coverage
   └──────────┬───────────────┘
              │  unusable?
              ├──────────────► ACTION 1: ask for a recapture with a concrete
              │                instruction ("closer", "less backlight")
              ▼  usable
   ┌──────────────────────────┐
   │ align_to_baseline()      │  OpenCV 5 Features: ALIKED + LightGlueMatcher
   │                          │  against the stored reference image
   └──────────┬───────────────┘  OF THE SAME asset → homography
              │  does not align?
              ├──────────────► ACTION 2: retry with another detector, or
              │                declare "unrecognised asset" and ask to confirm
              ▼  aligned
   ┌──────────────────────────┐
   │ diff_against_memory()    │  compared against the last inspection:
   │                          │  changed regions, magnitude, trend
   └──────────┬───────────────┘
              │  change found with low confidence?
              ├──────────────► ACTION 3: crop_and_rescan() over the ROI
              │                — active perception: the agent decides
              │                WHERE to look closer and re-enters the loop
              ▼  change confirmed
   ┌──────────────────────────┐
   │ classify_severity()      │  OpenCV + classifier
   └──────────┬───────────────┘
              │  high severity?
              ├──────────────► ACTION 4: request_human_approval() before
              │                opening the ticket. Graduated autonomy.
              ▼
   ┌──────────────────────────┐
   │ write_memory()           │  new baseline + event + traceability
   └──────────────────────────┘
              │
              ▼  the whole run emitted as an OTel trace
```

**Golden rule:** every agent decision has to be reconstructible from the trace. If a judge asks "why did it zoom in here?", the answer has to be in the span, with the numeric value that triggered it.

---

## 3. Architecture

```
┌─── Client ───────────────────────────────────────────────┐
│  Minimal front end (Next.js or Vite + React)             │
│  · upload a capture · view the asset history             │
│  · human approval queue · trace viewer                   │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTPS
┌───────────────────────▼──────────────────────────────────┐
│  API Gateway  →  FastAPI on ECS Fargate (arm64/Graviton) │
└───────┬──────────────────────────┬───────────────────────┘
        │                          │
        ▼                          ▼
┌────────────────────┐    ┌───────────────────────────────┐
│  Agent runtime     │    │  Perception service           │
│  · policy engine   │◄──►│  · OpenCV 5 (ARM container)   │
│  · p→d→a loop      │MCP │  · assess_quality             │
│  · HITL gate       │    │  · align_to_baseline          │
└────────┬───────────┘    │  · diff_against_memory        │
         │                │  · crop_and_rescan            │
         │                │  · classify_severity          │
         │                └───────────────────────────────┘
         ▼
┌────────────────────────────────────────────────────────┐
│  Memory bank                                           │
│  · DynamoDB: assets, inspections, events, baselines    │
│  · S3: original captures, crops, baseline images       │
└────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  Observability — OpenTelemetry                         │
│  · one span per tool call, with inputs, metrics and    │
│    the decision it triggered                           │
│  · exports to CloudWatch / OTLP collector              │
│  · /traces/{run_id} endpoint for the judge to read     │
└────────────────────────────────────────────────────────┘
```

### Stack

| Layer | Choice | Why |
|---|---|---|
| Vision | **OpenCV 5.0** (`opencv-python==5.0.0.93`) | Hard requirement |
| Runtime | Python 3.12 | SDK and ecosystem |
| API | FastAPI + uvicorn | Fast to stand up, OpenAPI for free |
| Container | Docker `arm64`, Ubuntu 24.04 base | Graviton, and compatible with the COOL AMI |
| Compute | **ECS Fargate ARM** or EC2 `c8g.large` | Graviton = requirement for the COOL prize |
| Storage | S3 (images) + DynamoDB (memory) | Serverless, cheap, fits inside the grant |
| Agent | LLM over the API + tools exposed through **MCP** | The rules allow MCP explicitly |
| Traces | OpenTelemetry SDK → OTLP | The 15% of the award |
| Front end | Next.js or Vite + React, static deploy | Enough for the public endpoint |
| IaC | Terraform or AWS CDK | Reproducibility = 10% of the score |

### Version warning

> **OpenCV 5 was released on 6 June 2026.** It is later than the training data of most models. **Verify every API against https://docs.opencv.org/5.x/ before using it.** Do not assume an OpenCV 4 signature still holds.
>
> Breaking changes: the C API was removed, the minimum is C++17, ML and G-API moved to contrib, and `Features2D` was replaced by the **`Features`** module.
>
> New things worth using: neural matching (`ALIKED`, `DISK`, `LightGlueMatcher`), a rewritten DNN with 80%+ ONNX coverage and dynamic shapes, LLM/VLM inside the `dnn` module with tokenizer and KV-cache, FP16/BF16/bool/int64 types, 0D and 1D tensors.

---

## 4. Weekly plan

Nine weeks, from 26 August to 26 October. Every week closes with something demonstrable.

| Week | Dates | Goal | Closes with |
|---|---|---|---|
| **1** | 26 Aug – 1 Sep | Scaffolding. Repo, arm64 Docker with OpenCV 5, S3, CI. | A container that reads an image from S3 and returns a number computed with OpenCV 5. |
| **2** | 2 – 8 Sep | Perception tools. The five functions, with tests. | Green `pytest` over fixture images. |
| **3** | 9 – 15 Sep | Memory bank. DynamoDB schema, baselines in S3, per-asset history. | A second inspection of the same asset that compares against the first. |
| **4** | 16 – 22 Sep | MCP server + agentic loop + autonomy policy + human gate. | The full loop running locally, with all four actions firing. |
| **5** | 23 – 29 Sep | Observability. OTel spans per tool call, trace endpoint. | A trace where an OpenCV value visibly changed the next decision. ⚠️ If you have a grant, the Zoom check-in lands here (21 Sep – 2 Oct). |
| **6** | 30 Sep – 6 Oct | Full AWS deploy + front end + public endpoint. | A working public URL a judge can use. |
| **7** | 7 – 13 Oct | Evaluation. Dataset, metrics, **failure cases**. | A results table with precision, recall and honest limitations. |
| **8** | 14 – 20 Oct | Technical report, diagrams, pinned deps, instructions. If going for COOL: benchmark against a baseline. | Complete documentation in the repo. |
| **9** | 21 – 26 Oct | Video, deck, polish. **Submit on the 24th or 25th**, not the 26th. | Submission done with 48 h to spare. |

**Margin rule:** the submission goes in on Saturday the 24th or Sunday the 25th. The 26th is a cushion, not a working day.

---

## 5. Repo structure

```
.
├── CLAUDE.md                     # this document
├── README.md                     # what it is, how to run it, architecture
├── docs/
│   ├── ARCHITECTURE.md           # diagram + component walkthrough
│   ├── AGENT_LOOP.md             # the perception→decision→action diagram
│   ├── EVALUATION.md             # dataset, metrics, failure cases
│   ├── TECHNICAL_REPORT.md       # the report the competition asks for
│   └── diagrams/                 # sources (mermaid or excalidraw) + PNG
├── services/
│   ├── perception/               # OpenCV 5: the five tools
│   │   ├── quality.py
│   │   ├── alignment.py          # ALIKED + LightGlueMatcher
│   │   ├── diffing.py
│   │   ├── severity.py
│   │   └── tests/
│   ├── mcp_server/               # exposes perception as MCP tools
│   ├── agent/
│   │   ├── loop.py               # perception → decision → action
│   │   ├── policy.py             # thresholds, escalation, autonomy
│   │   └── hitl.py               # human approval gate
│   ├── memory/                   # DynamoDB + S3, baselines and history
│   └── api/                      # FastAPI
├── web/                          # minimal front end
├── infra/                        # Terraform or CDK
├── eval/
│   ├── dataset/                  # fixtures and evaluation dataset
│   ├── run_eval.py
│   └── results/                  # versioned results
├── observability/                # OTel config, dashboards
├── Dockerfile                    # arm64
├── docker-compose.yml            # full local environment
├── requirements.txt              # PINNED, exact
└── Makefile                      # make dev, make test, make eval, make deploy
```

---

## 6. The seven deliverables and how they get produced

| # | Deliverable | Produced in | Note |
|---|---|---|---|
| 1 | Technical report | `docs/TECHNICAL_REPORT.md` | Problem, users, architecture, OpenCV 5 implementation, AWS deploy, evaluation, limitations, responsible use. |
| 2 | Repository | GitHub | Can be private with access for the judges. If you make it public, watch for credentials in the history. |
| 3 | Pinned deps + instructions | `requirements.txt` + `README.md` | Exact versions, not ranges. A judge should get it up with `make dev`. |
| 4 | Architecture diagram | `docs/diagrams/` | Two of them: infrastructure and the agentic loop. The second is mandatory for the award. |
| 5 | Web endpoint | Deployed on AWS | Working without a login, or with demo credentials stated in the report. |
| 6 | Video ≤ 5 min | — | Script in section 7. **Your face has to appear.** |
| 7 | Evaluation evidence | `eval/results/` + `docs/EVALUATION.md` | Include **failure cases**. It is an explicit requirement, and admitting limits scores well with a technical jury. |

### How to map each criterion to concrete evidence

| Criterion | Weight | What demonstrates it |
|---|---|---|
| Technical execution | 30% | Green tests, the OpenCV 5 `Features` module used seriously, clean architecture, evaluation with numbers. |
| Innovation | 20% | **Longitudinal memory.** It is what no previous winner had. Say it explicitly in the report and in the video. |
| Real-world impact | 20% | A use case with numbers: how many assets, what manual inspection costs, what it saves. |
| UX | 10% | The approval queue and the history being understandable without explanation. |
| Documentation | 10% | The report and the README. It is cheap and plenty of people neglect it. |
| Cloud and responsible operation | 10% | Terraform, OTel traces, secret handling, image retention policy. |
| **Agentic (separate award)** | — | The trace where an OpenCV number visibly changed the next decision. **Record it and show it in the video.** |

---

## 7. Video script (5 minutes)

| Time | Content |
|---|---|
| 0:00 – 0:25 | **Face to camera.** Who you are, what you built, in one sentence. Explicit requirement. |
| 0:25 – 1:00 | The problem, with one concrete number. |
| 1:00 – 1:30 | Architecture diagram, 30 seconds, without dwelling on every box. |
| 1:30 – 3:15 | **The demo.** Upload a capture, the agent asks for a recapture, upload a good one, it detects the change against the previous inspection, it zooms in on its own, it asks for approval. This is the heart. |
| 3:15 – 4:00 | **The trace.** Show the span where the OpenCV value triggered the decision. This is the award evidence. |
| 4:00 – 4:35 | Evaluation results, including a failure case. |
| 4:35 – 5:00 | What comes next, and close. |

Record it in week 9 but **write the script in week 7**, so development aims at making the demo look good.

---

## 8. Risks and traps

| Risk | Mitigation |
|---|---|
| **Hallucinated OpenCV 5 APIs** | Verify everything against `docs.opencv.org/5.x`. Models know OpenCV 4. |
| **No GPU in the DNN engine** | Design for CPU/Graviton from day one. Do not plan anything that needs CUDA. |
| **The agentic loop ends up decorative** | If the agent always does the same thing, it does not qualify. There have to be real, demonstrable branches. Test all four paths. |
| **Confusing "I used an AI coding assistant" with "it is agentic"** | Explicitly disqualified. The loop lives in the product. |
| **COOL charges by itself** | 7-day free trial that converts to paid. If you try it, set a reminder to cancel. |
| **Last-minute documentation** | It is 20% of the score. Write the report in week 8, not week 9. |
| **The public endpoint goes down during judging** | Judging runs from 27 October to 9 November. Budget AWS so it stays alive until 10 November. |
| **Official rules still unpublished** | Check `/updates` on Devpost every week. When they land, check applicable law, jurisdiction and the country list. |

---

## 9. Names for the repo

All available as repo names (verify on GitHub before committing to one). They follow the pattern of your existing ones: a single evocative English word.

### The recall and hindsight family

| Name | Why |
|---|---|
| **afterimage** | What stays visible after you stop looking. It is literally persistent visual memory — the project concept in one word. **My favourite.** |
| **revisit** | The central act: seeing the same asset again. Simple and exact. |
| **foresight** | Closes the trilogy with hindsight. Risk: it suggests prediction, and the project detects, it does not predict. |
| **retrace** | Going back over ground already covered. Works with the history idea. |

### From the vocabulary of vision

| Name | Why |
|---|---|
| **saccade** | The rapid eye movement that redirects the gaze. It is active perception: the agent decides where to look next. Technically precise and rarely used. |
| **fovea** | The area of the retina with the sharpest acuity. Fits `crop_and_rescan`: focusing where it matters. |
| **parallax** | Seeing the same thing from another point — or from another moment. Elegant, perhaps too abstract. |

### From the vocabulary of inspection

| Name | Why |
|---|---|
| **vigil** | Watching sustained over time. Short, serious, memorable. |
| **stakeout** | Prolonged observation of a single target. Informal but very clear. |
| **watchpost** | An observation post. Less original than the others. |

### Recommendation

**`afterimage`** for the repo. It says memory and vision at the same time, it is one word, it is not worn out, and it explains itself in one line in the video: *"an afterimage is what your eye still sees after you look away — this agent keeps one for every asset it inspects."*

If the vertical ends up being solar panels and you want something more literal, **`revisit`** is the runner-up and needs no explanation.

---

## 10. Kickoff prompts

**Session 1 — scaffolding**

> Read `CLAUDE.md`. Build the project scaffolding: the folder structure from section 5, a `Dockerfile` for arm64 on Ubuntu 24.04 with Python 3.12 and `opencv-python==5.0.0.93`, a `docker-compose.yml` with LocalStack for S3 and DynamoDB, a `Makefile` with `dev/test/eval/deploy`, and a test that verifies OpenCV 5 imports and reports version 5.x. Before using any OpenCV API, verify it against docs.opencv.org/5.x — your OpenCV knowledge is from version 4.

**Session 2 — perception**

> Implement the five tools of `services/perception/` per section 2. For `align_to_baseline` use the OpenCV 5 `Features` module with ALIKED and LightGlueMatcher — verify the signatures in the 5.x documentation. Each function returns a dataclass with the result *and* the numeric metrics that will feed the agent's decision. Tests with fixture images.

**Session 3 — memory**

> Implement `services/memory/`: a DynamoDB schema for assets, inspections, events and baselines; image storage in S3; and the "give me the last inspection of this asset" query. Design the keys so that fetching an asset's complete history is a single query.

**Session 4 — agent**

> Implement the MCP server that exposes the perception tools, and the `services/agent/` loop with the four actions from the diagram. The threshold policy lives in `policy.py`, configurable, not hardcoded in the loop. Every decision has to record which value triggered it.

**Session 5 — traces**

> Instrument everything with OpenTelemetry: one span per tool call with inputs, output metrics and the resulting decision. Add `GET /traces/{run_id}` returning the trace in a human-readable format. This endpoint is evidence for the award — it has to look good.

---

## 11. Submission checklist

Before hitting submit, on Saturday 24 or Sunday 25 October:

- [ ] Repo accessible to the judges (public, or private with access granted)
- [ ] `requirements.txt` with exact versions
- [ ] `README.md` with build, deploy and test instructions that work on a clean machine
- [ ] `docs/TECHNICAL_REPORT.md` complete, with limitations and responsible use
- [ ] Architecture diagram **and** agentic loop diagram
- [ ] Public endpoint working, tested from another network
- [ ] Video of at most 5 minutes, with your face, uploaded public or unlisted
- [ ] `docs/EVALUATION.md` with metrics and **failure cases**
- [ ] The trace proving OpenCV changed a decision — linked from the report
- [ ] AWS budget with margin through 10 November (judging runs that long)
- [ ] No credentials in the git history

---

## References

- Competition: https://opencv26.devpost.com/ · rules: https://opencv26.devpost.com/rules
- Official site (has details Devpost does not carry): https://opencv.org/opencv-ai-competition-2026/
- Grant proposal: https://www.jotform.com/form/262145877145059
- OpenCV 5: https://opencv.org/opencv-5/ · docs: https://docs.opencv.org/5.x/
- COOL: https://opencv.org/cool/ · AMI: https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs
