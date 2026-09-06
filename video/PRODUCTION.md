# Video production — afterimage

A 14-second cold open with no voice, then your voice in Spanish end to end, English burned-in
subtitles, and your face in a box in the corner **for the whole video** — the big frame is always
showing the product or the documentation.

The script is `video/script.tsv`: one row per subtitle, `en` is what the viewer reads, `es` is what
you say. 58 rows.

## 1. Build the cold open

```bash
python3 video/hook.py
```

Writes `video/out/hook.mov` (1920×1080, 30 fps, no voice) and `video/out/hook.wav`. Both are
rebuilt only when the spec in `hook.py` changes — the plan is cached in `out/hook.plan`.

```
0.0  a real solar array from eval/dataset/base/, slow push-in     deep impact
     1,700,000 panels
3.0  cut · video/img/1-blurred.png                                impact
     blur_variance    3.6589  <   100.0   ->  recapture
6.0  cut · video/img/3-defect.png, a box on the crack             impact
     score            0.6798  >=    0.4    ->  human_approval
9.5  cut to black                                                 silence
11.0 afterimage
     it does not guess. it measures.
14.0 your voice comes in
```

The two metric lines are the ones read off the screen during the browser rehearsal below, not
invented. The sound is synthesised by ffmpeg — a low drone with a hit on each cut — so there is no
licence to clear and the whole thing rebuilds from the repository.

`drawtext` is not compiled into the Homebrew `ffmpeg` 8 default, so `hook.py` puts
`/opt/homebrew/opt/ffmpeg@7/bin` in front of `PATH`, the same as `assemble.sh`.

## 2. Record seven clips

QuickTime Player → *File* → *New Movie Recording*, webcam and microphone on. All seven in the same
session: same chair, same framing, same light. The box is on screen from the first frame to the
last, so a change of light between clips flickers at every beat change.

| File | Beat | Content | Rows |
|---|---|---|---|
| `face-open.mov` | 0:00 | Opening | 4 |
| `body-1.mov` | 0:25 | The problem | 6 |
| `body-2.mov` | 1:00 | Architecture | 4 |
| `body-3.mov` | 1:30 | **The demo** | 22 |
| `body-4.mov` | 3:15 | **The trace** | 8 |
| `body-5.mov` | 4:00 | Evaluation and the failure | 9 |
| `face-close.mov` | 4:35 | Close | 5 |

"face" only means that beat has no demo to show; all seven go into the box.

Seven separate recordings, not one long take: a clip that goes wrong is re-recorded on its own.

### The one rule that makes the subtitles land

**Pause between one row and the next**, the way you read a list. Those pauses are what tells the
assembler where each subtitle changes. Inside a row, speak normally.

Do not worry about how long the pauses are: anything over 0.55 s is cut back afterwards, audio and
picture together, and so is dead air at the top and tail of each clip. Two real takes ran long at
1.1 s and 1.5 s per pause; trimming brought them under target without a re-record. A pause that is
too *short* is the one that cannot be fixed later, so err long.

Read the `es` column from a teleprompter placed directly under the lens, large type
(`python3 video/teleprompter.py` regenerates `out/teleprompter.html` from the `.tsv`, with the
per-clip targets recalculated).

### Your lines

```bash
awk -F'\t' 'NR>1 && $1=="0:00" {print NR-1". "$3}' video/script.tsv    # opening
awk -F'\t' 'NR>1 && $1=="4:35" {print NR-1". "$3}' video/script.tsv    # close
awk -F'\t' 'NR>1 {print $1"  "$3}' video/script.tsv                    # everything
```

The opening no longer starts with your name — it starts by cashing in what the hook just showed,
so land *"Esos números decidieron qué pasaba después."* as an answer, not as an introduction.

## 3. Build the audio and the subtitles

```bash
python3 video/build-face-audio.py
```

Reads the seven clips and writes `video/out/narration.wav`, `timing.txt`, `captions.srt`, and a
trimmed copy of each clip under `video/out/clips/`. Everything downstream uses the trimmed copies —
`assemble.sh` included — so the originals are never touched.

`narration.wav` starts with `out/hook.wav`, so the audio and the assembled picture come out exactly
the same length and nothing has to be mixed downstream. If the hook has not been built the report
says so and the offset is zero.

`timing.txt` holds the seven beat lengths of the picture only (no hook); it is what
`fit-to-audio.py` locks the screencast to.

Subtitle times are anchored to the **rendered** clips, not to the arithmetic of the trim plan: each
trim snaps to a frame, and over seven beats that rounding used to push the last subtitles a few
hundred milliseconds off the voice.

The report shows raw length, tight length and what trimming saved. Trimming also re-encodes ProRes
to H.264, which takes each 600 MB clip down to about 25 MB; a clip is only re-rendered when its
trim plan changes.

**Record `body-1.mov` first and run this on it alone.** If your reading does not produce clean
boundaries, it shows up on one 25-second clip instead of five. Every beat must say `fitted`; a beat
that says `proportional` means the pauses were not found and its subtitles are estimated.

If a room noise floor swallows the pauses, raise the threshold: `NOISE_DB=-25dB python3 …`.

The verdict line has to read `HARD CAP 5:00 — OK`, and it counts the hook.

## 4. The screencast

`Cmd+Shift+5` in **window mode**, microphone **off**. Window mode captures only the browser, so the
terminal never appears. Claude drives the clicks; you press record and stop. Save as `video/raw.mov`.

The box is permanent now, so every beat needs something on the screen behind it — including the
opening and the close, which used to be your face full frame.

**Reset the endpoint first, and again between takes.**

```bash
bash video/reset-demo.sh            # report only
bash video/reset-demo.sh --apply    # delete
```

Evaluation runs, README captures and rehearsals leave assets behind, and on camera they read as test
scaffolding. In the 5 September state the list held eleven assets and eight of them were scaffolding
— and the list is now the very first screen of the video, not a glance at 0:30. The script keeps
`panel-a7-north`, `panel-b3-east` and `panel-c2-west` and removes the rest. It touches DynamoDB
only: every `/traces/{run_id}` URL already published stays reachable, including the two linked from
the technical report.

Then walk the whole story through the real UI once, the day before, and write the run IDs down. A
take is a performance of a known path, not an experiment.

| # | Beat | On screen | Money shot |
|---|---|---|---|
| 0 | 0:00 | The endpoint loading, the URL legible, the upload form | |
| 1 | 0:25 | The asset list — the real assets, and the one this take is about | |
| 2 | 1:00 | Infrastructure diagram, GitHub Pages §11 | |
| 3 | 1:30 | Upload `1-blurred.png` → trace opens | **`blur_variance 3.6589 vs 100.0 -> recapture`** |
| 4 | 1:30 | Upload `2-baseline.png` → first baseline | |
| 5 | 1:30 | Upload `3-defect.png` → trace opens | **`score 0.6798 vs 0.4 -> human_approval`** |
| 6 | 1:30 | `/queue`, approve live | **the approval landing** |
| 7 | 1:30 | `/assets/{id}` history | **the older baseline marked `superseded by`** |
| 8 | 3:15 | The trace, scrolled to `classify_severity` | **`score 0.6798 >= 0.4 -> human_approval`** |
| 9 | 4:00 | `docs/EVALUATION.md` results and failure tables | |
| 10 | 4:35 | GitHub Pages: the diagram, the tables, the public URL in shot | |

Dwell ~4 s on each money shot. Natural pace elsewhere — the fit compresses the dead waiting
afterwards, so only the ORDER has to be right.

Each upload takes **20–30 s** before the trace appears (`align_to_baseline` alone is 13 s). That is
dead screen time the fit removes afterwards — do not fill it, just wait.

**Shot 6.** `/queue` refreshes itself every five seconds, and that reload used to cancel an
approval already in flight — five clicks in a row were swallowed during the first rehearsal. Fixed
and deployed on 5 September: the timer stands down the moment the page starts navigating, and the
same click then landed first try. Opening `metrics` before approving is still worth doing on camera
— the numbers behind the decision belong on screen before the human acts on them.

**A defect upload takes ~33 s** end to end; the clean baseline takes ~6 s. Do not navigate away
before the trace appears, or the inspection is cancelled and nothing is written.

Every page in the app is a 760 px centred column, so the corner is empty background: the box covers
nothing, not even on the trace.

## 5. Assemble

```bash
bash video/assemble.sh "0,42,100,158,216,274,332"
```

The argument is the recording timestamp where each of the **seven** beats starts — shots 0, 1, 2,
3, 8, 9 and 10 above — read off a timestamped contact sheet of `raw.mov`, not guessed.

The script fits the screencast to your voice beat by beat, lays one continuous box over it, joins
the hook to the front and writes `video/out/demo.mp4` plus `demo.en.srt`.

Knobs: `PIP_W` (default 300), `PIP_MARGIN` (default 24), `PIP_POS` (`tl` or `tr`, default `tl`).

## Verified through the browser, 5 September

The full shot list driven through the real UI against the public endpoint, asset `panel-a7-north`.
Every number below was read off the screen, not the API:

```
1-blurred   run 466670cb2e85   blur_variance    3.6589 <  100.0 -> recapture
2-baseline  run 7537a2cfd8c2   blur_variance 2483.1292 >= 100.0 -> quality_ok   (first_baseline)
3-defect    run 02fb84c00e01   blur_variance 1064.0321 >= 100.0 -> quality_ok
                               inlier_ratio     0.9988 >=   0.9 -> aligned
                               mean_delta      67.7646 >=  35.0 -> change_confirmed
                               score            0.6798 >=   0.4 -> human_approval
approved                       baseline 7537a2cfd8c2 -> superseded by 02fb84c00e01
```

Both money shots fit on screen without scrolling. `eval/tests/test_published_numbers.py` holds the
`en` column of `script.tsv` to this set and to `eval/results/latest/results.json`: a four-decimal
figure spoken on camera that nothing measured fails the suite.

Two things the rehearsal changed:

- The trace renders a policy decision as **one line** (`score 0.6798 >= 0.4 -> human_approval`), not
  as four labelled fields. `input_metric` / `value` / `threshold` / `branch` are field names in the
  JSON only. The narration for beat 3:15 was rewritten to describe the line that is actually on
  screen.
- The `/queue` reload, which turned out to be a real bug rather than a tooling artifact: an
  approval POST that had not returned when the timer fired was cancelled, silently. Fixed and
  verified in a browser — see the commit.

## Pipeline rehearsed end to end

```bash
python3 video/rehearse.py
```

Speaks `script.tsv` with a Spanish TTS voice into seven synthetic clips, runs the real
`build-face-audio.py` over them, and checks the subtitles it produced against timings it knows to
be true: 58 cues, every caption inside a real silence, **worst boundary error 39 ms**. If
`out/hook.wav` exists it is put in front, exactly as in the real build, so the run also proves the
cold open did not push the subtitles off the voice. Needs macOS, takes about a minute, and leaves
nothing behind.

`REHEARSAL_GAP=1.4 python3 video/rehearse.py` runs the same check against clips with long pauses,
which is what exercises the trimming: it verifies the cap held and that every subtitle still changes
inside a real silence rather than over a word. **This is the mode that caught the frame-snapping
drift** — the cues are anchored to the rendered clips because of it.

Synthetic speech pauses evenly, so the default run only proves the precise case. The messy case — a
reader who hesitates mid-sentence — is what the real takes test, and it is why a boundary is chosen
by pause length *and* by how well the split matches the length of the text around it. `LONG_BONUS`
sets the balance; anywhere from 25 to 200 satisfies both cases, and it ships at 60.
