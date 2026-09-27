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

Findings 4–5 are implemented as well: the deciding number is the decision whose branch the run ended
on (`baseline_exists 0` for a reference photo, with a plain tip), and the **Waiting on a human** panel
and the next-sample link sit directly under the hero instead of below the image comparison.

Finding 6 is implemented too: `upload_hint_plain` is one sentence plus the id rule. At 320 × 640 the
paragraph went from 288 px to 96 px and **inspect** from y=675, below the fold, to y=483.

## Review 2026-09-27 (second pass)

Walked again in Chrome on `localhost:8000/app` in Spanish, plain register, with cookies and storage
cleared, after findings 1–6 and the accessibility review were applied. The happy path (1 → 3 →
approve → asset history) now takes six clicks with no navigation to discover. This pass follows the
other two samples and what happens when a judge does not follow the numbering.

### Current flow

1. `/app` opens with a two-line hint, the form and the four samples in a 3 + 1 grid.
2. Sample 1 → **inspect** → "First photo of this asset, saved as its reference", deciding number
   `baseline_exists 0`, **Next: 3** under the hero.
3. **Next** → sample 3 preloaded → **inspect** → "A person has to look at this change", with the
   approval panel under the hero.
4. **Approve write** → **Confirm?** → `/assets/{id}`. This page has no way forward: no link to the
   workspace and no hint that samples 2 and 4 remain (`services/ui/templates/asset.html` has no
   `/app` link).
5. Reaching sample 2 means clicking **assets** in the nav and picking it: the trace ends in "This
   photo is too poor to judge", again with no next step.
6. Sample 4 the same way ends in "This is not the asset in memory", with `inspection ended:
   unrecognized_asset` in English under the Spanish title.
7. Out of order, on a fresh demo asset (measured with `curl` against the same server):

   | First upload | Second upload | Result of the second |
   |---|---|---|
   | sample 3 (cracked) | sample 1 (clean) | `human_approval`: the clean panel is flagged as damaged |
   | sample 4 (other panel) | sample 1 (clean) | `unrecognized_asset`: the real panel is rejected |
   | sample 2 (blurred) | — | `recapture`, harmless |

   The first sample a judge picks becomes the reference whatever it shows. A judge who starts with
   the most interesting card, the crack, sees the product call the clean panel defective.

### Findings

| # | Finding | Heuristic / law | Evidence | Proposal | Impact | Effort |
|---|---|---|---|---|---|---|
| 11 | Picking sample 3 or 4 first writes it as the reference, and the clean photo is then judged against it | H5 error prevention; Tesler's Law | step 7 above; samples render unconditionally at `services/ui/templates/index.html:8` | While the visitor's demo asset has no baseline (`sample_asset` not among `assets` in `index_page`), render samples 2–4 with `aria-disabled='true'` and a `sample_needs_reference` note ("después de la 1" / "after sample 1"), and have `app.js` ignore clicks on them | high — technique and impact (the demo shows a wrong verdict) | S |
| 12 | Only `first_baseline` offers a next step; sample 2 and sample 4 need the nav, and the asset history is a dead end | Goal-Gradient; H6 recognition over recall | `_next_sample` at `services/ui/views.py:781` covers one branch; `asset.html` links nowhere forward | Turn `_next_sample` into a map over the demo tour: `first_baseline` → sample 3, the approved run's asset page → sample 2, `recapture` → sample 4, `unrecognized_asset` → the asset history as the end frame. Render the asset-page step with the same `.cta` block when `asset_id` starts with `demo-panel-` | high — UX, video pacing (all four branches in one take) | S |
| 13 | The model's message sits under the localised title in English | H4 consistency; H2 | `services/ui/views.py:571` passes the message whenever an `outcome_*` title exists; scripted and Gemini messages are English | Render `hero.message` only in the technical register (`register == 'tech'`); the plain page keeps the localised title alone | medium — UX | S |
| 14 | The integrity line keeps the event count from page load ("los 1 pasos") on a run started from the page | H1 visibility of status; UX writing | the footer at `services/ui/templates/trace.html:41–44` is outside the `data-poll` block at `:4`; the same run reloaded reads "los 6 pasos" | Move the chain `<span>` into the polled block, or render it only when `run_state == 'done'`; add a singular form to `chain_intact_plain` | low — technique (an integrity claim that is wrong while it is watched) | S |
| 15 | "Four captures of the same demo panel" while card 4 is "another, completely different panel" | H4 consistency | `samples_hint` at `services/ui/text.py:151` and `:473` | `samples_hint`: "Four demo captures, in order: each lands on a different answer." / "Cuatro capturas de demo, en orden: cada una cae en una respuesta distinta." | low | S |
| 7 | (still open) The asset id placeholder is cut mid-sentence | H5; H4 | `asset_id_placeholder` at `services/ui/text.py:53` and `:374` | as proposed above: `panel-a7-north (optional)` / `panel-a7-norte (opcional)` | low | S |
| 8 | (still open) Stage cards and "what it ruled out" show tool and metric ids in plain | H2 | `services/ui/templates/trace.html:15` and `:17` | as proposed above | low | M |
| 10 | (still open) The fourth sample wraps alone onto a second row at 1512 px | Chunking | `services/ui/static/app.css:320` | `repeat(4, 1fr)` above the breakpoint, if the video is shot at desktop width | low | S |

Contrast, focus and keyboard were measured separately in `revision-ux-localhost-app.md` and are
not repeated here.

### Proposed flow

1. `/app`: sample 1 is the only live card until the reference exists; the other three read "after
   sample 1".
2. Sample 1 → **inspect** → "First photo of this asset, saved as its reference" → **Next: 3 · now
   cracked**.
3. Sample 3 preloaded → **inspect** → "A person has to look at this change" → **Approve write** →
   **Confirm?**
4. The asset history, with the new baseline in force → **Next: 2 · out of focus**.
5. Sample 2 → **inspect** → "This photo is too poor to judge" → **Next: 4 · another panel**.
6. Sample 4 → **inspect** → "This is not the asset in memory" → **See this asset's history**, the
   end frame: four answers, one memory, every number on screen.

Clicks from `/app` to the end frame: sample 1 and inspect (2), next and inspect (2), approve and
confirm (2), then next and inspect twice (4) and the history link (1), 11 in all, each on a
button already in view, and every branch the samples promise is reached in one take.

Findings 7, 8, 10 and 11–15 are implemented. Walked again in Chrome with fresh cookies:

- the samples 2–4 are locked until sample 1 sets the reference, and clicking sample 3 first loads nothing;
- the tour then runs 1 → **Next: 3** → approve → the asset history with **Next: 2** → "This photo is too
  poor to judge" with **Next: 4** → "This is not the asset in memory" with **See this asset's history**;
- the final history page shows no call to action.

In plain Spanish:

- no English message sits under a title, and the rail reads "calidad, alineación, cambio, mirada de
  cerca, severidad";
- the footer shows no chain line while a run is in flight;
- the placeholder reads `panel-a7 (opcional)` in full, and the samples sit in a 2 × 2 grid.
