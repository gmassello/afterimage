# Video v2 — cold open, revised script, face always in the box

Agreed 5 September, shot and cut 6 September. **Done** — `video/out/demo.mp4`, 4:53.6.

| Step | State |
|---|---|
| 1. `video/hook.py` — the cold open | **done** — 14.0 s, 1920×1080 @ 30, sound mastered to a measured level |
| 2. `video/script.tsv` — the review | **done** — 63 rows → 58, then a plain-language pass over every beat |
| 3. Record the seven clips | **done** — all seven `fitted` on the first take |
| 4. `video/build-face-audio.py` | **done** — one narration track, `timing.txt`, the hook in front |
| 5. The screencast — eleven shots | **done** — asset `panel-d4-south`, every figure matching the script |
| 6. `video/assemble.sh` | **done** — `"0,14,34,76.5,385.5,428.5,476.5"` |
| 7. A test for the figures spoken on camera | **done** |
| 8. Documentation | **done** |

Three bugs surfaced from the verification gates rather than from review, and all three were already
shipping:

- **Subtitle drift.** Cue times came from the arithmetic of the trim plan while the narration is
  built from the rendered clips; each trim snaps to a frame, so by beat 6 the captions were landing
  on top of words. The long-pause rehearsal reported 12 failures at `HEAD`; cues are now anchored to
  the rendered clip and both modes report 0.
- **The narration was 3.7 dB under its own target.** `loudnorm=I=-16` delivered −19.7 in a single
  pass. Replaced with a measured linear gain, the same method the cold open uses, because loudnorm
  reaches the number by compressing — which flattens the hits.
- **Six seconds of a chat app** came to the front during the screencast, with contact names and a
  shared map location, because the capture was not scoped to the browser window. Found by sweeping
  the file for scene changes, cut out of the original. That sweep is now a documented step, and so is
  the window-capture rule.

