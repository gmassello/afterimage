# End-to-end walkthrough

The suite in `services/` asserts that the markup and the JavaScript exist. It never clicks anything.
This is the walkthrough that does: ten paths through the four views in a real browser, run before a
video take and before a deploy.

It is a checklist, not a runner. A browser runner would mean Node in an image that installs Python
and nothing else, so the driving is done by hand or by an agent with browser control, and the
assertions below are what it checks.

`make demo` covers the same agent branches by calling `loop.run()` directly. This covers the layer
above: the form, the poller, the rail, the comparator, the queue and the history.

## Preconditions

```bash
docker compose down && docker compose up --build -d      # LocalStack has no volume: this empties it
docker compose exec -T app python -c \
  "from services.memory import store, images; store.ensure_table(); images.ensure_bucket()"
```

The gallery has to start empty. Every later state is built through the browser, not seeded behind it.

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

## The ten paths

Order matters. A fresh `asset_id` always lands on `first_baseline` (`services/agent/loop.py:226-238`),
so there is no way to reach ACTION 3 or 4 without passing through it. Each upload takes 20–30 s;
**do not navigate away before the trace appears**, or the inspection is cancelled and nothing is
written.

### Asset `e2e-closeup` — the real photograph, the video's own three files

| | Path | Upload | Assertion |
|---|---|---|---|
| **A** | empty gallery | — | the designed empty state: a dotted ring and `Nothing in memory yet` |
| **B** | `first_baseline` | `2-baseline.png` | trace ends `first_baseline`; the four stages that never ran read `not run · first_baseline`, not `not run · quality_ok`; the gallery gains a card with a thumbnail |
| **C** | ACTION 1 · `recapture` | `1-blurred.png` | **`blur_variance 3.6589 < 100.0 -> recapture`**; `assess_quality` warn, the other four `not run`; the history gains **nothing** |
| **D** | ACTION 4 · `human_approval` | `3-defect.png` | **`score 0.6798 >= 0.4 -> human_approval`**; `crop_and_rescan` reads `not run · change_confirmed`; the bounding box is drawn; `Waiting on a human` |
| **E** | the queue | — | one entry, `0.6798` large and in warn; open `what it measured`; **first click arms `Confirm?` and stays armed, second click posts**; the queue empties |
| **F** | the history | — | the new inspection, the baseline in force ringed and bordered, the previous one `superseded by` |

The two figures in bold are published in `video/PRODUCTION.md:167,169`. A different number means
either this walkthrough or the agent regressed, and both have to be known before a take.

### Asset `e2e-synthetic` — the generated panels

| | Path | Upload | Assertion |
|---|---|---|---|
| **G** | `first_baseline` | `4-synth-baseline.png` | as B |
| **H** | ACTION 3 · active perception | `5-synth-faint.png` | `crop_and_rescan` → `change_confirmed` → `auto_write`; **all five stages `done`** — the only path that lights the whole rail |
| **I** | ACTION 2 · foreign asset | `6-synth-foreign.png` | `retry_classic` → `unrecognized_asset`; `align_to_baseline` collapses both attempts and reads **`2 tries`** |
| **J** | `no_change` | `7-synth-same.png` | `no_change`; three stages `done`, two `not run · no_change` |

Run J before H: after H the baseline is the faint-spot capture, and the plain panel would then read
as a change.

## What only the browser can check

| Check | How | Assertion |
|---|---|---|
| comparator by keyboard | focus the range, 25 × `Right` | the wipe follows to 75 %; the changed region stays above it at every position; the focus ring is visible |
| drop zone | dispatch `dragover` + `drop` with a `DataTransfer` carrying a `File` | `dragover` adds `.over`, the drop clears it, the file lands in the real input and the preview renders from a blob URL |
| client validation | upload `8-not-an-image.txt` and submit | `checkValidity()` false, `validationMessage` is `not a decodable image` — the server's own wording — and the form does not navigate |
| the counter | watch the hero during D | it counts up and settles on exactly the served value, decimals included |
| theme | toggle, then wait out one poll swap on `/queue` | the choice survives the swap; `localStorage` holds it |
| the poller is alive | hold `/queue` for 7 s | the `[data-poll]` node is a different element afterwards |
| console and server | `read_console_messages`; `docker compose logs app` | no errors, no 5xx, no tracebacks |

## Known failure modes

- **`document.hidden` is `true`.** Everything still renders, so the walkthrough looks green while the
  poller has never fired. Check it explicitly, first.
- **An armed approve button freezes the queue.** Arming focuses the button, and the poller defers its
  swap while focus is inside the block — the same thing an open `details` already does. The queue
  stops refreshing until the focus moves, which is also what cancels the arming.
- **The trace page executes the run itself** through `POST /runs/{run_id}/execute`. `POST /inspections`
  only opens it and redirects. Closing the tab before the trace appears cancels the inspection.
- **`docker compose down` between runs empties the traces too**, not just the table: they live inside
  the container under `runs/`. Any `/traces/...` URL from a previous walkthrough dies with it.
