# UX review

Mode: improvement of an existing UI. Walked on 27 September 2026 in Chrome as a first-time judge,
in Spanish and the plain register, against a local build of `main` (the Chrome extension had no
access to the Lambda Function URL; the code is the same). Judging weights used for impact:
technique 30%, innovation 20%, real-world impact 20%, UX 10%, docs 10%, cloud 10%.

## Current flow

The happy path a judge films: reference photo, then the cracked panel, then approval.

1. `/app` opens on **New inspection**: a six-line paragraph (`upload_hint_plain`,
   `services/ui/text.py:48`), the asset id field, the file field and **inspect**
   (`services/ui/templates/index.html:6`). The four sample cards sit below, the fourth one wraps to a
   second row under the fold (`services/ui/static/app.css:318`).
2. Click sample **1 · the reference photo**. It fills the asset id (`demo-panel-<suffix>`) and the
   file, and shows a thumbnail. Click **inspect**. Two clicks.
3. `/traces/{id}` opens at once with a live rail of five tools and polls every 1.5 s. The run ends
   in about 1 s as `first_baseline`. The headline is the raw branch id, the pills are `first_baseline`
   and `completed`, and the big "number that decided it" is `blur_variance 2483.13`
   (`services/ui/views.py:547`), although what decided the branch was `baseline_exists 0`.
4. There is no next step on the trace. The judge has to find **assets** in the nav, go back to
   `/app` and pick sample 3. This is the first moment where it is unclear what to do.
5. Sample 3 + **inspect**: two clicks. The trace ends in `human_approval` with
   `score 0.6798 ≥ 0.4`, the annotated evidence figure, the image comparison slider and, at the very
   bottom of a long page, the **Waiting on a human** panel with **Approve write** and the reject
   reason (`services/ui/templates/trace.html:36`). The headline reads
   `inspection ended: human_approval` in English on the Spanish page (`services/ui/views.py:566`).
6. **Approve write** asks **Confirm?** in place; the second click redirects to `/queue`
   (`services/api/app.py:355`), which now says "nothing waiting for approval". The flow ends on an
   empty state.
7. The strongest artefact, `/assets/{id}` (timeline, superseded baseline, severity bar), is only
   reachable through the small **asset history** link in the trace footer or the gallery.

Clicks from landing on `/app` to an approved finding: 2 + 1 (nav) + 2 + 2 = 7, with one navigation
the judge has to discover.

## Findings

| # | Finding | Heuristic / law | Evidence | Proposal | Impact | Effort |
|---|---|---|---|---|---|---|
| 1 | The filmed flow ends on an empty queue instead of the result | Peak-End Rule; H1 visibility of status | `services/api/app.py:355` redirects every verdict to `/queue` | When the verdict comes from the trace, redirect to `/assets/{asset_id}` (the timeline with the new baseline and `baseline_verified`); keep `/queue` as the target only when the form was posted from the queue page | high — innovation (memory is the product's thesis) | S |
| 2 | No next step after `first_baseline`; the judge must find the nav and go back | H6 recognition over recall; Goal-Gradient | `services/ui/templates/trace.html:36` renders a CTA only for `human_approval` | On a terminal trace of a demo asset, render a `next_sample` CTA ("Next: 3 · the same panel, now cracked") that opens `/app` with that sample preselected | high — UX, video pacing | S |
| 3 | Headline and pills mix English machine ids into the Spanish plain page | H2 match with the real world; H4 consistency | `services/ui/views.py:566` uses the model's message or the raw branch; pills show `completed`, `awaiting_approval` | Headline from a localised `branch_<name>` copy key (e.g. `branch_human_approval_plain`: "A person has to look at this change"); the model's message moves to the lede; status pills use the existing `status_*` keys | medium — UX | S |
| 4 | The big "number that decided it" on `first_baseline` is the blur score, not the rule that decided | H1 visibility; H2 | `services/ui/views.py:547` takes the last non-audit decision | Pick the decision whose `branch` equals the run's branch; for `first_baseline` show `baseline_exists 0` with a plain tip ("no earlier photo to compare with") | medium — technique (every decision traceable to its number) | S |
| 5 | The approve/reject panel sits below a full-width image, off-screen on a laptop | Fitts's Law; Serial Position | `services/ui/templates/trace.html:36` is the last section | Move the **Waiting on a human** panel directly under the hero when the run is `awaiting_approval`; keep the image comparison below it | medium — UX, video | S |
| 6 | Six lines of instructions before the only CTA, and they tell the user to type a name that is optional | H8 minimalist design; Paradox of the Active User | `services/ui/text.py:48` and `:356` (`upload_hint_plain`) | Cut `upload_hint_plain` to one line ("Pick a sample below or drop a photo; the agent opens the result at once") and move the limits to the field hints; drop "give it a name" since the id is optional | medium — UX | S |
| 7 | The asset id placeholder is cut mid-sentence | H5 error prevention; H4 | `services/ui/text.py:363` (`asset_id_placeholder`) is wider than the field | Shorten to `panel-a7-norte (opcional)` / `panel-a7-north (optional)` | low | S |
| 8 | Stage cards and "what it ruled out" show tool and metric ids in the plain register | H2 | `services/ui/templates/trace.html:13` and `:15` render `assess_quality`, `blur_variance` | In plain, label the rail with existing question keys (the same ones `_stage_rows` already uses) and keep ids for `_tech` | low — UX | M |
| 9 | Integrity line says "los 1 pasos" on a five-tool run | H4; UX writing (plurals) | `services/ui/views.py:778` passes `len(events)` into `chain_intact_plain` (`services/ui/text.py:570`) | Verify what `events` holds at render time and pass the chain length; add a singular variant of the key | low — technique (integrity claim must be right) | S |
| 10 | Sample 4 wraps alone under the fold | Chunking; Serial Position | `services/ui/static/app.css:318` (`minmax(260px, 1fr)`) | Four columns at desktop width (`repeat(4, 1fr)` above the breakpoint) so the whole sequence reads as one row | low | S |

Contrast, focus order and keyboard behaviour are out of scope here; they go to
`hackathon-ux-ud-review`.

## Proposed flow

1. `/app`: one line of guidance, the four samples in one row, the upload form beside them.
2. Sample 1 + **inspect** → trace ends in "First photo of this panel, saved as its reference" with
   `baseline_exists 0` as the deciding number, and a **Next: 3 · now cracked** CTA.
3. **Next** → `/app` with sample 3 preselected → **inspect**. The trace shows "A person has to look
   at this change", `score 0.6798 ≥ 0.4`, and the approval panel right under the hero, next to the
   evidence figure.
4. **Approve write** → **Confirm?** → lands on `/assets/{id}`: the timeline with the new baseline in
   force, the superseded one below it, and the re-observation result. That page is the end frame.

Clicks from `/app` to the end frame: 2 + 1 + 1 + 2 = 6, with no navigation to discover, and the
flow closes on the memory rather than on an empty queue.

## Review 2026-09-27

Findings 1–3 are implemented:

1. A verdict given on the trace (`from=trace`) lands on `/assets/{asset_id}` after an approval and
   back on the trace after a rejection; the queue's own forms still return to `/queue`.
2. A demo asset's `first_baseline` trace offers `next_sample`, which opens `/app?sample=sample-defect`
   with that capture already loaded.
3. The trace title comes from `outcome_<status>` / `outcome_<branch>` in the active language, the
   model's message sits beneath it, and the status pill uses `status_*`.

Walked again in Spanish on `localhost:8000`: sample 1 → trace titled "Primera foto de este activo,
guardada como referencia" → **Siguiente** → sample 3 preloaded → "Una persona tiene que mirar este
cambio" → approve → the asset history with the new baseline in force. Six clicks from `/app`.
