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

`Cmd+Shift+5`, microphone **off**, and **pick the Chrome window explicitly** — not the screen, and
not a selected region. Claude drives the clicks; you press record and stop. Save as `video/raw.mov`.

**This is the rule that cost the most.** On the 6 September take the capture was not scoped to the
window, and six seconds of WhatsApp — contact names, message previews, a shared map location — came
to the front and were recorded. It was caught by sweeping the file afterwards and cut out, but a
region capture cannot promise what a window capture promises: nothing that is not the browser can
ever enter the frame.

**Kill the debugger banner first.** Claude drives the tab through `chrome.debugger`, so Chrome raises
*"Claude started debugging this browser"* between the address bar and the page — where no crop can
remove it without also removing the URL. Quit Chrome completely (`Cmd+Q`; closing the windows leaves
the process alive) and relaunch it with the flag:

```bash
open -a "Google Chrome" --args --silent-debugger-extension-api
ps -o args= -p $(pgrep -x "Google Chrome" | head -1) | tr ' ' '\n' | grep silent-debugger
```

`open --args` is ignored in silence if Chrome is already running, so verify from the shell. Claude's
screenshots capture page content only, never browser chrome, so Claude cannot see the banner — you
confirm it is gone.

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

Each upload still takes **20–30 s** to finish (`align_to_baseline` alone is 13 s), but that is no
longer dead screen time. `POST /inspections` now only opens the run and redirects, and the trace
page fires the execution itself and polls, so the trace appears immediately and fills in span by
span while the agent works. Let it run — the filling-in **is** the money shot, and the old advice
to compress this stretch in the fit no longer applies.

**Shot 6.** `/queue` used to reload itself whole every five seconds, and that reload cancelled an
approval already in flight — five clicks in a row were swallowed during the first rehearsal. Fixed
on 5 September by standing the timer down as soon as the page starts navigating, and since the
front end moved to one unified poller it no longer reloads at all: it swaps the queue in place, so
the scroll position and the theme hold. Opening `what it measured` before approving is still worth doing on
camera — it now reads as four questions in plain English with the number that answered each, not
as raw JSON, so it survives being on screen for a second.

**A defect upload takes ~33 s** end to end; the clean baseline takes ~6 s. Do not navigate away
before the trace appears, or the inspection is cancelled and nothing is written.

The centred column is **1120 px** on the trace, the asset history and the queue; only the home page
is the narrow 760. So the corner is no longer guaranteed empty background — check the PiP against
the trace and the queue before committing to `PIP_POS=tl`, because the hero panel and the
comparison figures now reach further out than they did.

### Sweep the recording before assembling

```bash
ffmpeg -hide_banner -nostats -i video/raw.mov \
  -vf "fps=2,scale=480:-1,select='gt(scene,0.02)',showinfo" -f null - 2>&1 |
  grep -oE "pts_time:[0-9.]+"
```

Every scene change in the take, in seconds. Pull a frame at each one and look at it. A notification,
another window, a tab you forgot — anything that is not the browser on the expected page — has to be
found here, because after the assemble it is buried inside a 7x speed-up.

Cutting a span out is cheap and invisible when both sides show the same page:

```bash
ffmpeg -i video/raw-uncut.mov -filter_complex \
  "[0:v]trim=0:A,setpts=PTS-STARTPTS[a];[0:v]trim=B,setpts=PTS-STARTPTS[b];\
   [a][b]concat=n=2:v=1:a=0,scale=1920:-2,fps=30[v]" -map "[v]" -an \
  -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p video/raw.mov
```

Cut from the **original** every time, never from an already-cut file: one generation of encoding
instead of two. And subtract what you removed from every beat mark after it.

## 5. Assemble

```bash
bash video/assemble.sh "0,14,34,76.5,385.5,428.5,476.5"    # the 6 September take
```

The argument is the recording timestamp where each of the **seven** beats starts — shots 0, 1, 2,
3, 8, 9 and 10 above — read off a timestamped contact sheet of `raw.mov`, not guessed.

The script fits the screencast to your voice beat by beat, lays one continuous box over it, joins
the hook to the front and writes `video/out/demo.mp4` plus `demo.en.srt`.

Knobs: `PIP_W` (default 300), `PIP_MARGIN` (default 24), `PIP_POS` (`tl` or `tr`, default `tl`).

## The take, 6 September — asset `panel-d4-south`

The shot list driven through the real UI against the public endpoint. Every number below is off the
screen, and every one of them is **identical** to the 5 September rehearsal: same images, same
deterministic pipeline, so the cold open's readouts and the demo cannot contradict each other.

```
1-blurred   run 45ceaea34b8e   blur_variance    3.6589 <  100.0 -> recapture
2-baseline  run 0ac678eec19f   blur_variance 2483.1292 >= 100.0 -> quality_ok   (first_baseline)
3-defect    run b022e78251f3   blur_variance 1064.0321 >= 100.0 -> quality_ok
                               inlier_ratio     0.9988 >=   0.9 -> aligned
                               mean_delta      67.7646 >=  35.0 -> change_confirmed
                               score            0.6798 >=   0.4 -> human_approval
approved                       baseline 0ac678eec19f -> superseded by b022e78251f3
```

The asset history shows **two** inspections for three uploads: the blurred one branched to
`recapture` and wrote nothing. That is the argument of the demo, proved on screen rather than
asserted.

### What the take cost, and what to do differently

| | |
|---|---|
| Camera, 7 clips | 21.3 + 26.5 + 37.7 + 111.6 + 44.2 + 56.3 + 35.9 s raw, all `fitted` first take |
| Screencast | 555.7 s raw for 279.6 s of picture |
| Removed in post | 9.0 s (an app window came to the front) + 20.5 s (a wrong turn looking for a page) |
| Compression on the demo beat | 309 s into 91.2 s — **7.6x**, against a cap of 8 |

That 7.6x is the number to watch. It is compressing the upload waits, which are static, so it does
not show — but there is no headroom left. Next time either dwell less between uploads or split the
demo across two beats.

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

## 6. The README captures

`docs/img/demo.gif` is the first thing a judge sees, in the README and on Devpost, with
`trace.png` and `history.png` beside it. The GIF had no recipe: the original was made by hand and
the method was lost, which is why it was still showing the pre-Nocturne look months after the
front end was redesigned, while the two PNGs had already been retaken. This section exists so
that does not happen again.

The arc, the frame count and the palette below are the GIF's. Everything else — the state the
endpoint needs, the three lines before each shot, what may appear in the frame, and the trim —
is how any of the three is captured, including a retake of the PNGs on their own.

**The arc**, eight frames, ten seconds:

1. the asset list and the upload form
2. the form filled — asset id and the capture chosen
3. the trace, open and empty, the moment the run starts
4. the trace filled in: the deciding number, the four-tool path, the branches not taken
5. the comparison with the changed region boxed, and `Waiting on a human`
6. the queue: baseline against capture, the score under the threshold, `Approve write`
7. the queue empty
8. the asset history: the new baseline current, the old one `superseded by`

**The state it needs.** The upload has to land on an asset whose **current baseline is a clean
panel**, or the capture matches what memory already holds and the run ends in `no_change` with
nothing to approve — the demo assets are all sitting on defect baselines from previous takes, so
seed a fresh one first, off camera:

    python3 video/make_demo_images.py        # writes video/img/{1-blurred,2-baseline,3-defect}.png
    # upload 2-baseline.png to a new asset id -> first_baseline
    # then record, uploading 3-defect.png to that same asset -> crack, human_approval

That fresh asset is not in the `KEEP` default of `reset-demo.sh`, so the next run of it deletes the
asset the GIF is showing. Either name it in `KEEP` or accept that the recording outlives the row.

**Before the take, and after every navigation in it.** Three lines in the driven tab:

    localStorage.setItem('afterimage-theme', 'light');
    Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
    document.querySelector('.page').style.paddingRight = '140px';

The first pins the theme. With nothing in `localStorage['afterimage-theme']` the first visit follows
`prefers-color-scheme`, so a fresh profile shows whatever the machine is set to; the key has to be
set before the navigation, because the inline script in `base.html` reads it on the first paint.
The narrated video and everything published before 11 September are dark.

The second keeps the trace page polling. It stops while `document.hidden` is true, a driven tab
reports itself hidden permanently, and the page never fills in — the central beat is lost. The swap
that follows is the page's own, unmodified.

The third re-centres the page inside what is actually captured, which is narrower than the viewport:
above roughly 1045 px of captured width the right tenth is dropped silently, enough to cut the
right-hand figure of the comparison in half without anything looking broken. Verify it once with a
fixed bar at each edge of the viewport and check both appear. Shrinking the page beats resizing the
window, which macOS will not always do, and 140 px is the knob — it depends on the window.

**Capture each beat as a still, not as a recording.** Save each one to disk and build the GIF from
the numbered sequence: the arc is then exactly what the frame list says it is. The browser GIF
recorder samples frames from the actions it sees and drops some without saying so — the 12 September
retake asked for fifteen and got seven, and every one it dropped was a trace beat, the middle of the
arc.

**Encoding.** The stills arrive at more than one size and the image sequence demuxer refuses a size
change mid-stream, so normalise first — scale to width 1000, crop to the shortest — and number them
from `01`. Then reduce with a dedicated palette rather than the default web one:

    ffmpeg -y -i shot.png -vf "scale=1000:-2:flags=lanczos,crop=1000:602:0:0" frames/NN.png
    ffmpeg -y -i frames/%02d.png -vf "palettegen=max_colors=128:stats_mode=diff" palette.png
    ffmpeg -y -framerate 0.8 -i frames/%02d.png -i palette.png \
    -lavfi "[0:v][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" docs/img/demo.gif

The frame rate belongs to the second pass only: on `palettegen` it changes nothing, and neither does
`-loop 0`, which is already the muxer's default.

Keep it under a megabyte and expect to spend it: the light theme is a pale gradient wash where the
dark one was flat, and lossless stills cost more again than a recorder's already-quantised frames.
The 12 September retake measured 778 / 860 / 908 / 945 KB at 96 / 128 / 160 / 192 colours over eight
1000x602 frames, and shipped 128 at 870 KB. Re-measure that ladder each take rather than reusing the
number. The width is what the README asks for plus headroom for a dense display, so read the `width`
of the `<img>` in `README.md` before changing it.

**Nothing in the frame but the page.** The cursor is not an overlay a tool can strip — it is in the
frame, so park it in a corner the crop discards before each still, or a stray arrow lands in the
middle of the hero image and has to be patched out afterwards from the same region of an adjacent
frame. Whatever records the frames, strip every overlay it adds: watermarks, click indicators,
action labels, progress bars. This is submission material.

Trim the capture to the content before shipping it. The padding of the third line above stays in the
shot as a dead band on the right, and a PNG that carries one renders smaller than the one beside it
in the README's two-column table.

**When the front end changes, this file and `docs/img/` change with it.** Retaking the two PNGs
and forgetting the GIF is the exact mistake this section documents.
