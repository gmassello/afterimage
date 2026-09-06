# Video script — 5 minutes

For the OpenCV AI Competition 2026 submission. Structure follows `docs/BRIEF.md` §7.

**Hard requirements:** at most 5 minutes, the author's face must appear, public or unlisted, and it
must be recorded **against the public endpoint** — not localhost.

**Every number spoken here is measured.** Sources: `eval/results/latest/results.json`,
`docs/EVALUATION.md`, and the citations in `docs/TECHNICAL_REPORT.md` §2. Nothing is rounded up for
the camera.

---

## How it is recorded

This document is the **content**. The delivered video changes the delivery, not the substance:

| | |
|---|---|
| Voice | The author's own, in Spanish, end to end. No synthetic narration |
| Subtitles | English, burned in, plus a sidecar `demo.en.srt`. The text below is the subtitle text |
| Cold open | 14 s before the first word: a real array, two measured decisions, the name. No voice, so it lands muted — `video/hook.py` |
| Face | A box in the corner from the first frame to the last; the big frame is always the product or the documentation |
| Assembly | Seven camera clips, one per beat, fitted to the screencast — `video/PRODUCTION.md` |

**The 5 September cut (4:44.9) is superseded.** It opened with the author introducing himself and
put the face full screen at both ends. The beat→timestamp mapping below is filled in once the new
cut exists.

| Script | Video | |
|---|---|---|
| — | 0:00–0:14 | Cold open, no voice |
| 0:00 | | Opening |
| 0:25 | | The problem |
| 1:00 | | Architecture |
| 1:30 | | The demo |
| 3:15 | | The trace |
| 4:00 | | Evaluation |
| 4:35 | | The close |

The cut runs shorter than the script's marks because the recorded reading is faster than the
budget assumed, and because pauses over 0.55 s are trimmed out of the clips.

The competition rules require the author's face, the app, the architecture and the results, and set
no language requirement (`docs/BRIEF.md` §1). A real voice and a face on screen throughout carry
more in a competition video than a synthetic reading, and the subtitles carry the content in full.

Subtitle timings come from silence detection over the recorded voice, not from an estimate.
`video/build-face-audio.py` weighs two things against each other for every candidate boundary: how
long the pause is, and how well the resulting split matches the length of the text on either side.
Pause length alone is not enough — a reader who hesitates mid-sentence for longer than they pause
between rows will fool it, which is exactly what the first real take did. Rehearsed against
synthetic speech with known ground truth, the worst boundary lands **39 ms** off
(`python3 video/rehearse.py`).

---

## Before recording — the state the demo needs

The demo is three uploads against <https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/>.
Walk it once end to end the day before and **write down the run IDs**, so the recording is a
performance of a known path, not an experiment.

1. A fresh `asset_id` nobody has used — the browser history and `/queue` must be clean on camera.
2. **Upload 1: a blurred capture.** Must land on `recapture`. Verify `blur_variance` comes back
   under 100.
3. **Upload 2: the same panel, in focus.** Lands on `first_baseline`. This is the moment the memory
   is created — say so out loud, it is the whole thesis.
4. **Upload 3: the same panel with a visible defect.** Must land on `human_approval`. Verify
   `score` clears 0.40.
5. Leave `/queue` **unresolved** going in, so the approval can be clicked live at 3:05.
6. Have the trace of the zoom branch open in a second tab as a fallback:
   <https://jgmzrkpa344jwixw7nbulgh2ju0mojcb.lambda-url.us-east-1.on.aws/traces/90472757e472>

If upload 3 lands on `auto_write` instead of `human_approval`, the defect is too small — that is the
measured limitation in `docs/EVALUATION.md` §"Where it fails", case 3. Use a larger or darker defect
rather than changing the threshold for the video.

---

## 0:00 – 0:14 · Cold open, no voice

A real solar array and the number of panels in it. Cut, on a low hit: a blurred capture, and beside
it the number the system measured and the branch that number chose — `blur_variance 3.6589 < 100.0
-> recapture`. Cut: the same panel with a crack, boxed, and `score 0.6798 >= 0.4 ->
human_approval`. Black. Then the name, and *it does not guess. it measures.*

Both figures were read off the public endpoint during the browser rehearsal, not invented.

## 0:14 – 0:27 · Opening

> Those numbers decided what happened next. I'm Germán Massello, this is afterimage, and it compares
> a panel against that same panel, last time. It doesn't ask whether the panel is broken. It asks
> what changed.

*On screen: the public endpoint loading, the URL legible. Face in the corner box, as everywhere.*

## 0:25 – 1:00 · The problem, with a number

> Solar Star, in California, is one and a seven-tenths million solar panels. At that scale a plant is
> a field of near-identical objects that degrade slowly, and independently.
>
> Existing automated inspection asks "is this panel broken?" — one frame, against a generic idea of a
> healthy panel. But the failure literature is clear that a defect is a curve, not an event.
> Potential-induced degradation runs about fifteen percent a year in an affected module, and it's
> partly reversible if you catch it before it saturates. A microcrack under eight percent of the cell
> area costs you nothing today, and may cost you the module after enough thermal cycling.
>
> So the useful question isn't "is this broken". It's "what changed since last time" — and answering
> that means remembering what this specific panel looked like before.

*On screen: a photovoltaic plant, then the degradation-curve idea. Keep it to two visuals.*

## 1:00 – 1:30 · Architecture, 30 seconds

> One container on a Lambda function, ARM Graviton, CPU only — OpenCV 5's DNN engine has no GPU.
> Five perception tools exposed over MCP. Every one of them returns numbers and no verdicts.
>
> The thresholds live somewhere else, in a policy that runs in code, agent-side. That separation is
> the whole design, and I'll show you why in a minute.
>
> Memory is DynamoDB and S3: one row per inspection, and a chain of baselines where each one is
> retired rather than overwritten. That chain is the longitudinal record.

*On screen: the infrastructure diagram — <https://gmassello.github.io/afterimage/> section 11, or
§4 of the technical report. Do not walk box by box.*

## 1:30 – 3:15 · The demo — the heart of the video

*On screen: the public URL, live, in a browser. No terminal.*

**Upload 1 — the blurred capture.**

> First capture. It's out of focus.

*(the run finishes, the trace opens)*

> The agent didn't try to analyse it. `blur_variance` came back under a hundred, the policy compared
> it against the threshold, and the branch is `recapture` — go take another photo. The operator is
> still standing in front of the panel; that's the moment that request is worth anything.

**Upload 2 — the same panel, in focus.**

> Same panel, in focus. There's nothing to compare against yet, so this capture becomes the baseline.
> That's the memory being created. Everything afterwards is measured against this image.

**Upload 3 — the same panel, with a defect.**

> Now the same panel, some time later.
>
> It aligns this capture to the stored baseline — ALIKED keypoints matched with LightGlue, OpenCV 5's
> `Features` module — so the two images are in the same frame of reference. Then it diffs against
> memory, finds the region that changed, and classifies it.
>
> And here it stops. The severity score cleared the approval threshold, so it did not write anything.
> It's waiting for a person.

**Resolve the approval.**

*(open `/queue`, approve, then open the asset history)*

> I approve it — and only now does the inspection get committed, and this capture become the new
> baseline for the next one. That's the full history of this panel: every inspection, every baseline.

## 3:15 – 4:00 · The trace — this is the award evidence

*On screen: `/traces/{run_id}`, scrolled to the decisive span.*

> Every tool call is one span, with its arguments, its metrics, its duration, and the verdict the
> policy reached. And the causal link is a field, not something you reconstruct by reading the events
> in order:
>
> `input_metric`, `value`, `threshold`, `branch`.
>
> The model orchestrates the calls and writes the message the operator reads. It does not decide.
> If it submits a branch other than the one the policy computed, the loop rejects it and hands back
> the branch it's required to use. It cannot move a threshold.
>
> That's what I mean by the vision result changing what the system does: it's a number, in a field,
> next to the action it caused.

*If time allows, show the zoom branch on the second tab: `mean_delta` 33.34 against a threshold of
35 — not confident enough — so the agent re-measured that one region with four times the pixels
before deciding. That is the agent choosing to gather more evidence.*

## 4:00 – 4:35 · Evaluation, including a failure

> Twenty-three scenarios, twelve of them on real licensed photographs of solar modules. Branch
> accuracy point eight seven. Defect classification macro F1 point nine five. Mean IoU point eight
> three on locating the region. And precision one point zero on calling a human: it never interrupted
> someone for nothing.
>
> Three of the twenty-three fail, and they're in the report, because the interesting one is
> structural. A delamination over a small area scored point three four against a threshold of point
> four, so it got filed automatically instead of escalated. The root cause is that the severity score
> is a function of how much changed, and it ignores the label its own classifier just produced.
>
> I know how to fix that. I didn't fix it here, because rewriting a scoring function to satisfy one
> failing case is exactly the overfitting the dataset exists to catch.

*On screen: the results table, then the failure table from `docs/EVALUATION.md`.*

## 4:35 – 5:00 · What's next, and close

> Next is making severity class-aware, and calibrating frame coverage per site — I measured that one
> and there is no global default that works: healthy real captures span a two-hundred-fold range.
>
> Everything is open: the repository, the evaluation, the traces, and a public endpoint with no
> login. Upload your own photograph and watch a number decide what it does.

*On screen: GitHub Pages — the infrastructure diagram, the evaluation tables, and the public URL
held long enough to read. The close pays the cold open back: it ends on the same idea it opened on,
a number deciding.*

---

## Notes for the edit

- Total spoken word count is budgeted at roughly 150 words per minute. If a block runs long, cut from
  1:00–1:30 first — the architecture is the most compressible part.
- Never cut the trace block. It is the Agentic Vision award evidence and it is 15% of that rubric on
  its own.
- Show the failure. A judge trusts a project that shows where it breaks more than one that doesn't.
- Say the numbers as words, not by reading a table aloud.
