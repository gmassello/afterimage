# Video v2 — cold open, revised script, face always in the box

Agreed 5 September, built 6 September. Every step that is code is done and verified; the two that
need you in front of a camera are not.

| Step | State |
|---|---|
| 1. `video/hook.py` — the cold open | **done** — `out/hook.mov` 14.0 s, 1920×1080 @ 30, `out/hook.wav` |
| 2. `video/script.tsv` — the review | **done** — 63 rows → 58; opening 7→4, close 7→5, four `en` rows that under-said the Spanish |
| 3. Record the seven clips | **yours** |
| 4. `video/build-face-audio.py` | **done** — one narration track, `timing.txt`, the hook in front |
| 5. The screencast — eleven shots | **yours** |
| 6. `video/assemble.sh` | **done** — one continuous box, hook + body |
| 7. A test for the figures spoken on camera | **done** — `test_the_video_script_only_speaks_measured_figures` |
| 8. Documentation | **done** |

One thing not in the plan came out of its own verification gate, and it is a real bug that was
already shipping: subtitle times were computed from the arithmetic of the trim plan, while the
narration is built from the rendered clips. Each trim snaps to a frame, so the two timebases drifted
apart — by beat 6 the captions were far enough off the voice that the long-pause rehearsal put them
inside speech. The cues are now anchored to the rendered clips. Both rehearsal modes report
**0 failures**; before the fix the long-pause mode reported 12 at `HEAD`.

## Context

A finished video exists: `video/out/demo.mp4`, 4:44.9, your voice in Spanish, burned-in English
subtitles, your face full screen at the opening and the close and in a box in between.

It works, but it opens with you introducing yourself — *"I'm Germán Massello, and I built
afterimage"* — which is the weakest possible cold open for a jury working through dozens of entries
back to back.

Three changes: a hook that lands before you speak, a review of the whole script, and your face
**always** in the small box.

The third one, besides being what you asked for, simplifies the assembly. Today `assemble.sh`
concatenates three segments (face / body with the box / face), normalising resolution and fps
between the webcam and the screencast. With the box permanent there is **one segment**: a
continuous screen layer with the box over it. A three-input `concat` leaves the filter graph.

Verified before writing this:

| Check | Result |
|---|---|
| Does `fit-to-audio.py` take 7 beats instead of 5? | **Yes**, untouched. It only requires `--beats` to carry as many marks as `--timing` has beats (`fit-to-audio.py:203`) |
| Does ffmpeg have what the hook needs? | **Yes.** `drawtext`, `zoompan`, `xfade`, `sine`, `aevalsrc`, `afade` all present in the `ffmpeg@7` the pipeline already uses |
| Fonts? | `SFNSMono.ttf` for the metric lines, `HelveticaNeue.ttc` for the titles |
| Are the script's figures true? | **All six.** `0.8696 0.9513 0.8258 0.6798 0.3412 0.9988` are all in `eval/results/latest/results.json` |
| Is there material for the hook? | Yes: 12 real licensed photographs in `eval/dataset/base/`, and `video/img/{1-blurred,2-baseline,3-defect}.png` |
| Does anything recorded get lost? | No. The original `.mov` files and the trimmed copies in `out/clips/` stay where they are until you overwrite them |

## Assumptions

- The hook carries **no voice**: picture, text and sound. It lands the same way muted, and it never
  enters the subtitle machinery as one more clip.
- The sound is **synthesised with ffmpeg**. No licensing risk in a competition, no dependencies, and
  the whole hook rebuilds from the repository with one command.
- You re-record **all seven clips in one session**. With the box permanent, a change of light
  between beats reads as a flicker at every cut.
- Filenames and beat labels (`0:00` … `4:35`) **do not change**. `rehearse.py` and `teleprompter.py`
  carry duplicates of that list; leaving it alone avoids touching three files for nothing.
- The screencast gets re-recorded: the screen layer now has to cover the opening and closing beats
  too, which today hold nothing because your face was there.

## The time budget

The hard cap is 300 s. The current cut sits at 284.9 s, so the hook does not fit without cutting.
It comes out of the opening, which is exactly what the hook makes redundant:

| Beat | Today | New | |
|---|---:|---:|---|
| hook | — | 14.0 | new |
| 0:00 opening | 27.8 | ~13 | the hook already stated the thesis; 7 rows become 4 |
| 0:25 the problem | 31.3 | 31.3 | |
| 1:00 architecture | 23.4 | 23.4 | |
| 1:30 the demo | 81.6 | 81.6 | |
| 3:15 the trace | 32.7 | 32.7 | |
| 4:00 evaluation | 62.2 | 62.2 | |
| 4:35 close | 25.9 | ~18 | 7 rows become 5 |
| **total** | **284.9** | **~276** | 4:36, 24 s of margin |

## Steps

### 1. `video/hook.py` — the cold open

Writes `out/hook.mov` (1920×1080, 30 fps) and `out/hook.wav`, cached against a `.plan` sidecar the
same way `render()` does in `build-face-audio.py`, so it is not re-rendered for nothing.

```
0.0  real solar array (eval/dataset/base/), slow push-in     deep impact
     1,700,000 panels
3.0  CUT · video/img/1-blurred.png                           impact
     blur_variance    3.66  <   100.0   ->  recapture
6.0  CUT · video/img/3-defect.png, box over the crack        impact
     score           0.6798  >=    0.40  ->  human_approval
9.5  CUT to black                                            silence
11.0 afterimage
     it does not guess. it measures.
14.0 the voice comes in
```

The three metric lines are set in `SFNSMono` and are the ones read off screen against the public
endpoint, not invented — they are in `PRODUCTION.md`, section *Verified through the browser*.

Sound: `sine=f=120` with `volume='exp(-8*t)'` for each hit, over a `sine=f=55` drone through
`lowpass`. The silence from 9.5 to 11.0 is part of the design, not a hole.

The box coordinates over the crack come from looking at `3-defect.png`, not from guessing.

### 2. `video/script.tsv` — the script review

Proposed row by row for your approval. The rule applied throughout: **the English may be shorter
than the Spanish, it may never say something different.** There are four rows today where a muted
viewer gets a different video from a listening one:

| Row | Problem |
|---|---|
| `PID runs ~15% a year` | the Spanish expands the acronym, the English leaves it cold |
| `A delamination scored 0.3412…` | the Spanish adds the consequence — *it was auto-filed instead of escalated* — which is the entire point of the failure |
| `I didn't fix it here` | the Spanish says *"I know how to fix it"* first, and that is the line carrying the credibility |
| `Mean IoU 0.8258` | the Spanish says *what it localises*, the English never says what it measures |

And the two beats that get rewritten outright:

**Opening, 7 rows → 4.** No longer starts with your name; starts by cashing in what the hook showed.

```
Those numbers decided what happened next    Esos números decidieron qué pasaba después.
I'm Germán Massello. This is afterimage     Soy Germán Massello. Esto es afterimage.
It compares a panel against that same       Compara un panel contra ese mismo panel,
panel, last time                            la última vez.
Not "is it broken". What changed            No pregunta si está roto. Pregunta qué cambió.
```

**Close, 7 rows → 5.** *"Thanks for watching"* goes: it is dead time at the end of a competition
video. It ends by paying the hook back.

```
…and watch a number decide what it does     …y mirá cómo un número decide qué hace.
```

### 3. Record the seven clips

One session. `python3 video/teleprompter.py` regenerates `out/teleprompter.html` from the new
`.tsv`, per-clip targets recalculated on its own. The reading rule is unchanged: **pause between one
row and the next**, which is what tells the assembler where each subtitle changes.

The names stay `face-open.mov`, `body-1..5.mov`, `face-close.mov`. All seven go to the box now;
"face" only means there is no demo to show on that beat.

**Gate:** record `body-1.mov` first and only that, and run the assembler over it. If your reading
does not produce clean boundaries it shows up on one 30-second clip.

### 4. `video/build-face-audio.py` — three changes

1. `BODY` goes away. All seven beats are body now, so `body.wav` and `body-timing.txt` collapse into
   `narration.wav` and `timing.txt`. One `concat_audio` call and one constant leave.
2. `narration.wav` starts with `out/hook.wav`. Audio and video then come out exactly the same
   length and nothing has to be mixed downstream: one track, no `amix`, no `adelay`.
3. The SRT cues shift by the hook's length, and the 300 s check includes it. If `out/hook.mov` does
   not exist yet the shift is 0 and the report says so.

### 5. The screencast — seven shots

As before (`Cmd+Shift+5` in window mode, microphone off, Claude drives Chrome) plus two new shots,
one at each end, because those beats are no longer covered by your face:

| # | Beat | On screen |
|---|---|---|
| **0** | **0:00** | **the public endpoint loading, the asset list** |
| 1–7 | 0:25 … 4:00 | the nine-shot list already in `PRODUCTION.md`, unchanged |
| **8** | **4:35** | **GitHub Pages: the diagram, the evaluation tables, the public URL in shot** |

### 6. `video/assemble.sh` — it gets shorter

```bash
bash video/assemble.sh "0,42,100,158,216,274,332"    # seven marks now, not five
```

1. `fit-to-audio.py` with the seven marks against `timing.txt` → `raw-fitted.mov`.
2. The seven trimmed clips, concatenated, scaled to `PIP_W`, overlaid top-left. One continuous
   layer.
3. A two-input `concat`: hook + body. **The three-segment concat goes**, and with it the fps
   normalisation that existed only to join the face segments.
4. `build-video.sh` with `NOFIT=1`, which burns the subtitles with the calibrated style, scales to
   1080p, writes the sidecar SRT and checks the cap.

### 7. A test for the figures spoken on camera

`eval/tests/test_published_numbers.py` already defends the README, `EVALUATION.md` and the technical
report against `results.json`. The video is the highest-stakes surface and the only one with no
guard: a figure misspoken on camera is not fixed by a commit.

Add a test taking every four-decimal number from the `en` column of `script.tsv` and requiring it to
appear in `results.json` or in the set verified on camera. It reuses the `_claim()` pattern and the
`measured` fixture already in that file.

### 8. Close the documentation

- `video/PRODUCTION.md` — rewritten: the hook, seven clips all in the box, the nine shots.
- `docs/VIDEO_SCRIPT.md` — the beat→timestamp mapping, which changes entirely.
- `docs/SUBMISSION.md` — the three rubric rows and deliverable 6 go back to `wip` with the old cut's
  timestamps until the new one exists; closed with the real ones at the end.
- `docs/PLAN.md` — row 9.

## Documentation

`video/PRODUCTION.md`, `docs/VIDEO_SCRIPT.md`, `docs/SUBMISSION.md`, `docs/PLAN.md` — step 8.

`README.md`, `docs/TECHNICAL_REPORT.md`, `docs/index.html` — unchanged; the video link is added only
once it is published.

The `personal-record-video` skill — **out of scope unless asked**. Generalising the hook and the
permanent-box variant is worth doing, but only once this video has shipped and we know what survived.

## Verification

1. `python3 video/hook.py` → `out/hook.mov`, 14.0 s, with audio, 1920×1080 at 30 fps.
2. `python3 video/rehearse.py` and `REHEARSAL_GAP=1.4 python3 video/rehearse.py` → **0 failures** in
   both modes. This is the proof that the hook's offset did not misalign the subtitles.
3. `python3 video/build-face-audio.py` → all seven beats say `fitted` (none `proportional`) and the
   verdict reads `HARD CAP 5:00 — OK`.
4. `ffprobe` on `out/demo.mp4` → **≤ 300 s**, matching the length of `narration.wav`.
5. Watch it end to end **with the sound off**. With a Spanish voice track and an English-speaking
   jury this is mandatory: the hook and the subtitles have to carry the story alone.
6. Lip sync on the first and last second of a middle beat, where a cut could have shifted the audio.
7. The box covers nothing on the trace (3:15), the densest shot. Every page in the app is a 760 px
   centred column, so the corner is clear — already measured, 21 px of air.
8. `make test` — green, including the new test from step 7.

## Out of scope

- **Uploading to YouTube** and **publishing on Devpost** — they need your login and stay yours.
- **Touching the product to make the demo look better.** If real, documented behaviour shows up on
  camera, it stands; a threshold is not adjusted for the take.
- Generalising the skill. After submission.
- The two rehearsal assets (`rehearsal-1788476935`, `rehearsal-1788476996`) visible in the list at
  ~0:30, which read as test junk. There is no delete endpoint; removing them would mean touching
  DynamoDB by hand. Noted, not acted on.