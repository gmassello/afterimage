# End-to-end walkthrough

The suite in `services/` asserts that the markup and the JavaScript exist. It never clicks anything.
This is the walkthrough that does: sixteen inspection paths plus the public shell, activity,
failure, and recovery contracts in a real browser, run before a video take and before a deploy.

It is a checklist, not a runner. A browser runner would mean Node in an image that installs Python
and nothing else, so the driving is done by hand or by an agent with browser control, and the
assertions below are what it checks.

`make demo` covers the same agent branches by calling `loop.run()` directly. This covers the layer
above: the form, the poller, the rail, the comparator, the queue and the history.

## Preconditions

```bash
docker compose build app && docker compose up -d app localstack
docker compose exec -T app python -c \
  "from services.memory import store, images; store.ensure_table(); images.ensure_bucket()"
```

Do not run `docker compose down` against a shared development stack: LocalStack has no volume, so
removing its container deletes all local assets, histories, and runs. Use a dedicated disposable
environment when an empty gallery is required. On a shared stack, keep existing data and use a
unique asset prefix for each walkthrough; skip path A's empty-gallery assertion. Every test result is
then created through the browser, not seeded behind it. `/` is the public landing and does not
contain the upload form.

**Chrome must be visible.** With the window occluded or minimised `document.hidden` is `true`, the
poller backs off to five seconds and never fetches, so the rail never advances and half of this
walkthrough silently passes for the wrong reason. `open -a "Google Chrome"` is not enough — it
activates the app, not the window holding the tab:

```bash
osascript -e 'tell application "Google Chrome"
  activate
  repeat with w in windows
    set i to 0
    repeat with t in tabs of w
      set i to i + 1
      if URL of t contains "localhost:8000" then
        set active tab index of w to i
        set index of w to 1
      end if
    end repeat
  end repeat
end tell'
```

Confirm from the page itself: `document.hidden` has to read `false` before path C.

## Captures

Three already exist and are the ones the video uses — `video/img/1-blurred.png`, `2-baseline.png`,
`3-defect.png`, built from the real `crack-real-closeup` scenario by `video/make_demo_images.py`.

The four synthetic ones are generated in the container, because there is no `cv2` on the host:

```bash
docker compose exec -T app python -c "
import cv2, os
from services.perception.tests.panels import solar_panel, with_faint_spot, foreign_panel, shifted
os.makedirs('/tmp/e2e', exist_ok=True)
panel = solar_panel(seed=0)
for name, image in {
    '4-synth-baseline.png': panel,
    '5-synth-faint.png': shifted(with_faint_spot(panel, 3, 7)),
    '6-synth-foreign.png': foreign_panel(),
    '7-synth-same.png': shifted(panel),
}.items():
    cv2.imwrite('/tmp/e2e/' + name, image)"
docker cp afterimage-app-1:/tmp/e2e/. .scratchpad/e2e/
printf 'not an image\n' > .scratchpad/e2e/8-not-an-image.txt
```

`.scratchpad/` is already in `.gitignore`.

## The sixteen paths

Order matters. A fresh `asset_id` always lands on the `first_baseline` branch in
`services.agent.loop.run`,
so there is no way to reach ACTION 3 or 4 without passing through it. Without `GOOGLE_API_KEY` the
scripted LLM orders the calls and a run finishes in **0.4–1.9 s** — measured over the ten runs of a
full pass, `run_started` to `run_finished`. With a live model, budget for its round trips instead.
Navigating away does not lose the inspection (see the failure modes), but it does lose the live rail,
which is half of what this walkthrough checks.

### Asset `e2e-closeup` — the real photograph, the video's own three files

| | Path | Upload | Assertion |
|---|---|---|---|
| **A** | empty gallery | — | the designed empty state: a dotted ring and `Nothing in memory yet` |
| **B** | `first_baseline` | `2-baseline.png` | trace ends `first_baseline`; the four stages that never ran read `not run · first_baseline`, not `not run · quality_ok`; the gallery gains a card with a thumbnail |
| **C** | ACTION 1 · `recapture` | `1-blurred.png` | **`blur_variance 3.6589 < 100.0 -> recapture`**; `assess_quality` warn, the other four `not run`; the history gains **nothing** |
| **D** | ACTION 4 · `human_approval` | `3-defect.png` | **`score 0.6798 >= 0.4 -> human_approval`**; `crop_and_rescan` reads `not run · change_confirmed`; the bounding box is drawn; `Waiting on a human` |
| **E** | `reject`, from the trace's own CTA | — | the CTA carries the same two forms the queue does; `Reject` arms `Confirm?` exactly like the approve; after the redirect the queue is empty and the history gains **nothing** |
| **F** | the same capture again | `3-defect.png` | **`score 0.6798`, again** — identical bytes against a baseline E never moved, which is what proves the reject wrote nothing; back in the queue |
| **G** | the queue | — | one entry, `0.6798` large and in warn; open `what it measured`; **first click arms `Confirm?` and stays armed, second click posts**; the queue empties |
| **H** | the history | — | the new inspection, the baseline in force ringed and bordered, the previous one `superseded by` |
| **I** | the sparkline | `2-baseline.png` | the comparison run backwards: the clean capture against the defect baseline. It reaches `classify_severity` — `auto_write` or `human_approval` depending on the reverse delta; approve it if it lands in the queue. With **two** scored inspections `figure.spark` renders for the first time: one mark per inspection and the dashed approval threshold |

The two figures published in the C and D rows of `video/PRODUCTION.md` are the bold ones here. A different
number means either this walkthrough or the agent regressed, and both have to be known before a take.
F repeats D's on purpose: a reject that left anything behind would move it.

E and F are the only place `Reject` and the trace's own CTA are exercised at all; the queue's approve
is reached in G. There is no way to reach a second `human_approval` on this asset after G, because
approving promotes the defect capture to baseline and the same file then reads `no_change`.

### Asset `e2e-synthetic` — the generated panels

| | Path | Upload | Assertion |
|---|---|---|---|
| **J** | `first_baseline` | `4-synth-baseline.png` | as B |
| **K** | ACTION 3 · active perception | `5-synth-faint.png` | `crop_and_rescan` → `change_confirmed` → `auto_write`; **all five stages `done`** — the only path that lights the whole rail |
| **L** | ACTION 2 · foreign asset | `6-synth-foreign.png` | `retry_classic` → `unrecognized_asset`; `align_to_baseline` collapses both attempts and reads **`2 tries`** |
| **M** | `no_change` | `7-synth-same.png` | `no_change`; three stages `done`, two `not run · no_change` |

Run M before K: after K the baseline is the faint-spot capture, and the plain panel would then read
as a change.

### Asset `demo-panel-<suffix>` — the sample captures, driven from the workspace

Nothing is uploaded by hand here: both rows go through the sample strip under the drop zone, which
is the only entry route a first visitor has. The strip writes a demo asset of this browser's own,
named after the `demo` cookie, so the walkthrough starts from an empty memory on every fresh
browser profile.

| | Path | Sample | Assertion |
|---|---|---|---|
| **O** | the strip fills the form | 1 then 2 | clicking a sample writes this browser's `demo-panel-<suffix>` into an empty asset id, lands the file in the real input and renders the preview from a blob URL — the same `review()` a drop goes through. Sample 1 ends `first_baseline`; sample 2 then reads **`blur_variance 3.6589 < 100.0 -> recapture`**, the same figure C gets from `1-blurred.png`, which is what proves the committed copy has not drifted from `video/img/` |
| **P** | a sample the baseline will not recognise | 4 | `retry_classic` → `unrecognized_asset` against the baseline sample 1 left. The synthetic panel is a different image entirely, so this is the refusal reached without typing an id or opening a file picker |

Run O before P, and both before N. They leave the demo asset in the gallery with a thumbnail, which
is what `/app` is meant to look like when someone arrives.

### Asset `e2e-ghost` — a new asset whose very first capture is unusable

| | Path | Upload | Assertion |
|---|---|---|---|
| **N** | `first_baseline` + ACTION 1 | `1-blurred.png` | the one branch where a brand-new asset writes nothing at all: the trace closes on `recapture` with the same `blur_variance 3.6589`, the four stages that never ran read `not run · recapture`, and the gallery gains a card with **no thumbnail, no pill and `no inspection summary yet`** — `services.api.app.create_inspection` called `put_asset`, but the loop never called `put_inspection`. `/assets/e2e-ghost` answers 200 with `no history yet` |

Run N last. The card it leaves is the one broken-looking thing in the gallery, and nothing after it
should have it in frame.

## Product shell, activity, and recovery

| Check | How | Assertion |
|---|---|---|
| public landing | open `/` | the page explains the problem, loop, evidence, stack, and limits; its primary action opens `/app`, and it does not show the asset gallery as its main content |
| application navigation | follow the landing CTA to `/app`, then open `/activity` from the header | both are full server-rendered pages; language, register, and theme choices survive the navigation |
| recent activity | create several runs, search for an asset or run ID, then select a status | query and status compose, matching values are retained in the form, and each result links to its trace; the page never renders more than 50 rows |
| negotiated error | request an unknown run once with `Accept: text/html` and once with `Accept: application/json` | HTML returns the themed error page; JSON returns the same status with `detail`, stable `code`, and `retryable` fields |
| failed-run retry | find a terminal failed run in `/activity` and submit retry twice before executing the replacement | both requests resolve to the same new `unstarted` run; its `run_started` event names the failed run in `retry_of`, and the original events are byte-for-byte unchanged |

Retry is available only for a terminal `failed` run. An active, completed, pending, or unknown target
must not create a replacement; a failed run already retried must resolve to the existing one.

## What only the browser can check

| Check | How | Assertion |
|---|---|---|
| comparator by keyboard | focus the range, 25 × `Right` | the wipe follows to 75 %; the changed region stays above it at every position; the focus ring is visible |
| drop zone | dispatch `dragover` + `drop` with a `DataTransfer` carrying a `File` | `dragover` adds `.over`, the drop clears it, the file lands in the real input and the preview renders from a blob URL |
| client validation | upload `8-not-an-image.txt` and submit | `checkValidity()` false, `validationMessage` is `not a decodable image` — the server's own wording — and the form does not navigate |
| the counter | watch the hero during D | it counts up and settles on exactly the served value, decimals included |
| theme | toggle, then wait out one poll swap on `/queue` | the choice survives the swap; `localStorage` holds it |
| the poller is alive | hold `/queue` for 7 s | the `[data-poll]` node is a different element afterwards |
| an asset nobody ever inspected | open `/assets/e2e-no-such-thing` | 200 with the designed `no history yet`, not a 404 — only an ID rejected by `ASSET_ID_PATTERN` is invalid |
| resolving the same run twice | after G, return to that run's trace tab and fire `Approve write` again | 404 themed error page with code `approval_not_found`; the trace and asset history stay unchanged |
| the language outlives the poller | `ES` in the header, then hold `/queue` for 7 s | `<html lang='es'>`, the cookie `afterimage-lang=es`, and the choice survives the swap — the poller fetches `location.pathname` without the query string, so only the cookie can carry it |
| the browser's own preference | `curl -H 'Accept-Language: es-AR' localhost:8000` with no cookie | Spanish, without anyone clicking anything; `fr,en` falls to English |
| the register switch | `technical` in the header, then open a trace | the prose swaps — `services/agent/policy.py` and the sha256 wording appear, the metric tips read in their technical form — while `inlier_ratio`, every number and the agent's own message are untouched. `plain` is what a first visitor gets, on its own cookie, independent of the language one |
| console and server | `read_console_messages`; `docker compose logs app` | no errors, no 5xx, no tracebacks |

## UX, UI, and accessibility checklist

Run this checklist in visible Chrome with the viewport set to **320×700**, **390×780**, and
**1440×731**. Record the actual dimensions reported by the browser. On every page, compare
`document.documentElement.scrollWidth` with `clientWidth`; a vertical scrollbar may make
`clientWidth` smaller than the requested viewport width.

| Area | Check | Pass condition |
|---|---|---|
| Reflow | inspect `/`, `/app`, `/activity`, `/queue`, an asset, and a trace at each viewport | no page-level horizontal overflow; no content or action becomes unreachable |
| Primary task | inspect the first screen of `/` and `/app` | at 1440×731 the landing CTA is fully visible; at 320×700 the Inspect button is fully visible in English and Spanish; the upload form has no horizontal overflow |
| Navigation | use Tab and Shift+Tab through header links and forms | focus order follows the visual/task order; hidden horizontal navigation links scroll into view when focused |
| Tabs | on `/`, focus a demo tab and press Left/Right, including at both ends | selection, `aria-selected`, roving `tabindex`, and the visible panel stay in sync |
| Comparator | focus the trace range and use arrow keys | the wipe changes, the focused slider remains visible, and the paired images remain understandable |
| Human approval | focus `Approve write`, activate once, then activate again with Enter | the first action arms confirmation, keeps focus, announces the next action, and does not write; the second resolves it |
| Status | watch the trace while a run completes and check the queue after approval | progress, completion, and confirmation are available through a status/live region; the queue reflects the result |
| Language and theme | inspect English and Spanish in light and dark themes | document language, visible labels, accessible control names, and contrast remain correct in all four combinations |
| Contrast | sample normal/large text and control/focus boundaries in both themes | text is at least 4.5:1 (3:1 for large text); required non-text boundaries are at least 3:1 |
| Touch targets | measure header links and buttons at 320 CSS px | each target is at least 24×24 CSS px, or demonstrably meets WCAG 2.2's spacing exception |
| Semantics | inspect the accessibility tree on every view | one visible `h1`, named landmarks/controls, meaningful image alternatives, and no unlabeled state changes |

For this pass, the browser run and measured findings are recorded in
[`revision-ux-afterimage.md`](../revision-ux-afterimage.md). This checklist is manual; the
`services/` suite does not automate browser interaction.

## Known failure modes

- **`document.hidden` is `true`.** Everything still renders, so the walkthrough looks green while the
  poller has never fired. Check it explicitly, first.
- **An armed approve button freezes the queue.** Arming focuses the button, and the poller defers its
  swap while focus is inside the block — the same thing an open `details` already does. The queue
  stops refreshing until the focus moves, which is also what cancels the arming.
- **Leaving the trace page does not cancel the run.** The page executes it through
  `POST /runs/{run_id}/execute`; `POST /inspections` only opens it and redirects. Uvicorn does not
  abort the handler when the client goes away, so the inspection finishes server-side and writes its
  result — verified three times, by cutting the request at 0.3 s of a 1.8 s run and by navigating away
  the instant the trace loaded. What is lost is the live view, not the work. A second `POST` to the
  same run answers `409 run already started`, because the claim in `trace.run_state` has advanced.
- **A run that is opened but never executed stays `unstarted` indefinitely.** `POST /inspections`
  writes only `run_started`; the execute comes from the page's own JS
  (`services/ui/static/app.js`, the `unstarted` execution block). Reopening that URL later does run it, because the JS fires on
  `unstarted` — so an abandoned run is a dormant one, not a lost one.
- **Error representation follows `Accept`.** Browser navigation must send `text/html` to receive the
  themed page. A client that sends JSON or no HTML preference receives the structured
  `{detail, code, retryable}` body instead; that is content negotiation, not a rendering failure.
- **Path L needs the weights.** Without the `.onnx` files
  `services.perception.alignment.default_detector()` returns `orb+bf`, there is no `retry_classic`, and `align_to_baseline` reads
  `1 try` instead of `2 tries`. `make weights` is a precondition of that assertion, not of the run.
- **The `N assets in memory` line on an empty queue is memoised for a minute** by
  `services.api.app._assets_in_memory`. It can lag a full 60 s behind the table; that is not a symptom.
- **The sample strip needs JavaScript.** The buttons fetch the PNG and hand it to the file input;
  without JS they are inert and the only way in is the file picker. The primer above them is a plain
  `<details>` and still opens.
- **The samples are committed copies, not the files the video uses.**
  `services/ui/static/sample-*.png` are written by `video/make_demo_images.py` alongside
  `video/img/`, which is gitignored. Regenerate both in the same run, or path O stops reproducing
  `3.6589` while path C still does.
- **`docker compose down` between runs empties the traces too**, not just the table: they live inside
  the container under `runs/`. Any `/traces/...` URL from a previous walkthrough dies with it.

## Deliberately not covered

| Left out | Why |
|---|---|
| the other four `recapture` causes — too dark, too bright, clipped dark, clipped bright (`services.agent.policy.evaluate`) | the rail and the `assess_quality` card render the same whichever one fires. The eval reaches overexposure (`recapture-overexposed-*`); too dark and clipped dark have no scenario anywhere |
| `coverage_ratio_min` | dead at its default of `0.0` in `services.agent.policy.Policy`: no value is below it |
| `rescan → no_change` (`services.agent.policy.evaluate`) | needs a change small enough to survive the crop and then vanish; no eval scenario reaches it either, so it is a product gap, not a front-end one |
| `baseline: historical` (`services.memory.store.promote_baseline`) | needs a capture approved after a newer one already promoted. Three uploads and an interleaved approval for one pill |
| `WRONG_TOOL`, `WRONG_BRANCH`, `PREMATURE_SUBMIT`, `NUDGE` | unreachable without `GOOGLE_API_KEY`: `scripted.PolicyFollowingLLM` cannot emit them by construction |
| `AFTERIMAGE_RUNS_S3=1` | this walkthrough always runs traces and the queue off the local disk |
| no JavaScript, `prefers-reduced-motion` | neither can be toggled from browser control; the CSS fallbacks are covered by `services/ui/tests/` |
