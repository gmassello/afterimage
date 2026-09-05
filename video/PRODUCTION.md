# Video production — afterimage

Your voice, in Spanish, end to end. English burned-in subtitles. Your face full screen at the
opening and the close, and in a box in the top-right corner for everything in between.

The script is `video/script.tsv`: one row per subtitle, `en` is what the viewer reads, `es` is what
you say. 63 rows.

## 1. Record seven clips

QuickTime Player → *File* → *New Movie Recording*, webcam and microphone on. All seven in the same
session: same chair, same framing, same light. If the light changes between clips the box flickers
every time the beat changes.

| File | Beat | Content | Rows |
|---|---|---|---|
| `face-open.mov` | 0:00 | Opening, to camera | 7 |
| `body-1.mov` | 0:25 | The problem | 6 |
| `body-2.mov` | 1:00 | Architecture | 4 |
| `body-3.mov` | 1:30 | **The demo** | 22 |
| `body-4.mov` | 3:15 | **The trace** | 8 |
| `body-5.mov` | 4:00 | Evaluation and the failure | 9 |
| `face-close.mov` | 4:35 | Close, to camera | 7 |

Seven separate recordings, not one long take: a clip that goes wrong is re-recorded on its own.

### The one rule that makes the subtitles land

**Pause between one row and the next**, the way you read a list. Those pauses are what tells the
assembler where each subtitle changes. Inside a row, speak normally.

Do not worry about how long the pauses are: anything over 0.7 s is cut back to 0.7 s afterwards,
audio and picture together, and so is dead air at the top and tail of each clip. Two real takes ran
long at 1.1 s and 1.5 s per pause; trimming brought them under target without a re-record. A pause
that is too *short* is the one that cannot be fixed later, so err long.

Read the `es` column from a teleprompter placed directly under the lens, large type. On the two
face clips the eyes-off-lens drift is visible; inside the small box it is not.

### Your lines

Print them with:

```bash
awk -F'\t' 'NR>1 && $1=="0:00" {print NR-1". "$3}' video/script.tsv    # opening
awk -F'\t' 'NR>1 && $1=="4:35" {print NR-1". "$3}' video/script.tsv    # close
awk -F'\t' 'NR>1 {print $1"  "$3}' video/script.tsv                    # everything
```

The last line of the opening — *"Te muestro."* — is the handoff into the demo. Land it and hold
still for a beat before stopping the recording.

## 2. Build the audio and the subtitles

```bash
python3 video/build-face-audio.py
```

Reads the seven clips and writes `video/out/narration.wav`, `body.wav`, `body-timing.txt`,
`captions.srt`, and a trimmed copy of each clip under `video/out/clips/`. Everything downstream uses
the trimmed copies — `assemble.sh` included — so the originals are never touched.

The report shows raw length, tight length and what trimming saved. Trimming also re-encodes ProRes
to H.264, which takes each 600 MB clip down to about 25 MB; a clip is only re-rendered when it is
newer than its trimmed copy.

**Record `body-1.mov` first and run this on it alone.** If your reading does not produce clean
boundaries, it shows up on one 25-second clip instead of five. Every beat must say `fitted`; a beat
that says `proportional` means the pauses were not found and its subtitles are estimated.

If a room noise floor swallows the pauses, raise the threshold: `NOISE_DB=-25dB python3 …`.

The verdict line has to read `HARD CAP 5:00 — OK`. Over the cap, a beat gets cut and that one clip
gets re-recorded — before the screencast exists, not after.

## 3. The screencast

`Cmd+Shift+5` in **window mode**, microphone **off**. Window mode captures only the browser, so the
terminal never appears. Claude drives the clicks; you press record and stop. Save as `video/raw.mov`.

| # | Beat | On screen | Money shot |
|---|---|---|---|
| 1 | 0:25 | The public endpoint, asset list | |
| 2 | 1:00 | Infrastructure diagram, GitHub Pages §11 | |
| 3 | 1:30 | Upload `1-blurred.png` → trace opens | **`blur_variance 3.6589 vs 100.0 -> recapture`** |
| 4 | 1:30 | Upload `2-baseline.png` → first baseline | |
| 5 | 1:30 | Upload `3-defect.png` → trace opens | **`score 0.6798 vs 0.4 -> human_approval`** |
| 6 | 1:30 | `/queue`, approve live | **the approval landing** |
| 7 | 1:30 | `/assets/{id}` history | **the older baseline marked `superseded by`** |
| 8 | 3:15 | The trace, scrolled to `classify_severity` | **`score 0.6798 >= 0.4 -> human_approval`** |
| 9 | 4:00 | `docs/EVALUATION.md` results and failure tables | |

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

Every page in the app is a 760 px centred column, so the top-right corner is empty background: the
box covers nothing, not even on the trace.

## 4. Assemble

```bash
bash video/assemble.sh "0,58,116,174,232"
```

The argument is the recording timestamp where each of the five body beats starts, read off a
timestamped contact sheet of `raw.mov` — not guessed. The script fits the screencast to your voice,
overlays the box, joins the three segments and writes `video/out/demo.mp4` plus `demo.en.srt`.

Knobs: `PIP_W` (default 320), `PIP_MARGIN` (default 32).

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

Both money shots fit on screen without scrolling. Every page is a 760 px centred column, so the
corner box covers only background — confirmed on the trace, which is the densest shot.

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
be true: 63 cues, every caption in order, **worst boundary error 39 ms**. Needs macOS, takes about
a minute, and leaves nothing behind.

`REHEARSAL_GAP=1.4 python3 video/rehearse.py` runs the same check against clips with long pauses,
which is what exercises the trimming: it verifies the cap held and that every subtitle still changes
inside a real silence rather than over a word.

Synthetic speech pauses evenly, so the default run only proves the precise case. The messy case — a reader who
hesitates mid-sentence — is what the real takes test, and it is why a boundary is chosen by pause
length *and* by how well the split matches the length of the text around it. `LONG_BONUS` sets the
balance; anywhere from 25 to 200 satisfies both cases, and it ships at 60.

The assembly was rehearsed the same way against a stand-in screencast: `demo.mp4` came out
1920×1080 at exactly the length of the voice track, with the box and the burned-in subtitles in
place.
