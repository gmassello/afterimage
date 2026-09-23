# afterimage design system

Instructions for any agent or person changing the afterimage UI. Every value below is exact; do
not introduce colours, sizes, radii, fonts or effects that are not listed here. The live preview
is [`design-preview.html`](design-preview.html) and uses these tokens verbatim.

## 1. Context

- **Product**: afterimage, a visual inspection agent with longitudinal memory. An operator uploads
  a photo of a physical asset; the agent gates quality, aligns it to the stored baseline, diffs it
  against memory, scores severity, and either writes the result, asks for a recapture, or stops
  for a human. Every decision is recorded with the number that triggered it.
- **What the demo shows**: a capture going in, the trace filling in as the agent works, each
  decision rendered as `metric value vs threshold → branch`, and a human approving the finding in
  the queue.
- **Audience**: the OpenCV AI Competition 2026 judges (Agentic Vision path), watching a recorded
  video and then opening the live endpoint. They must be able to read a decision and its number
  in one glance.
- **Sources**:
  - **Base: Linear** (from `VoltAgent/awesome-design-md`, `design-md/linear.app/DESIGN.md`):
    4 px spacing scale, radius scale, surface ladder with hairline borders instead of shadows,
    focus ring, negative display tracking at weight 600 over body at 400, 1280 px container,
    breakpoints, and button states.
  - **Secondary: VoltAgent** (`design-md/voltagent/DESIGN.md`), exactly two traits:
    1. The terminal panel (hairline border, 8 px radius, 20 px padding, mono 13/18) used as the
       frame of the agent trace, with every measured number set in mono.
    2. The uppercase eyebrow with wide tracking (14 px, 600, 2.52 px) used as the stage label
       above each step: `QUALITY`, `ALIGNMENT`, `DIFF`, `SEVERITY`.
- **Originality changes**:
  - The accent is afterimage's own violet (`#5d5294` light, `#9184d9` dark), not the lavender of
    the base or the green of the secondary.
  - Mono is JetBrains Mono, not the system mono either source uses.
  - Light mode is the default. Neither source ships one; it is derived from the base's inverse
    surfaces.
  - Three semantic tones map to policy branches (`--ok`, `--warn`, `--danger`), which neither
    source defines.
  - The dark canvas is a violet-tinted near-black (`#0e0e14`), not the base's blue-black.

## 2. Stack

The repository already has a front end, and it wins:

- Server-rendered Jinja2 templates in `services/ui/templates/`, autoescaped, rendered by
  `services/ui/views.py`.
- One hand-written stylesheet, `services/ui/static/app.css`, driven by CSS custom properties.
- Vanilla JavaScript in `services/ui/static/app.js` and `landing.js`; no framework, no bundler.
- Static assets are served with hashed names by the FastAPI app.

There is no React, Tailwind or shadcn/ui, and none is to be added. Components are CSS classes plus
Jinja macros in `services/ui/templates/partials/components.html`. All copy lives in
`services/ui/text.py` (English and Spanish, `_plain` / `_tech` registers); no string literals in
templates.

## 3. Tokens

Colours are semantic custom properties on `:root` (light, the default) and overridden under
`[data-theme="dark"]`. Each block sets `color-scheme`. Never add a second stylesheet or duplicate
classes per theme.

```css
:root {
  color-scheme: light;
  --bg: #ffffff;
  --surface-1: #f5f6f6;
  --surface-2: #eceef0;
  --surface-3: #e3e5e8;
  --fg: #0f1011;
  --muted: #3e3e44;
  --subtle: #5f636b;
  --border: #e1e3e6;
  --border-strong: #8a8f98;
  --accent: #5d5294;
  --accent-hover: #4a4078;
  --accent-soft: #e9e6f8;
  --on-accent: #ffffff;
  --ring: #5d5294;
  --ok: #176b42;
  --warn: #8a5a06;
  --danger: #a03028;

  --font-sans: "Inter", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-24: 96px;

  --radius-xs: 4px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-pill: 9999px;

  --shadow-overlay: 0 12px 32px rgba(15, 16, 17, 0.12);
  --dur-fast: 140ms;
  --dur-live: 320ms;
  --dur-type: 28ms;
  --ease-out: cubic-bezier(0.2, 0.7, 0.2, 1);
}

[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0e0e14;
  --surface-1: #15151c;
  --surface-2: #1c1c25;
  --surface-3: #23232e;
  --fg: #f2f2f5;
  --muted: #c9cbd4;
  --subtle: #9194a5;
  --border: #262631;
  --border-strong: #6e7284;
  --accent: #9184d9;
  --accent-hover: #b5abfc;
  --accent-soft: #2a2545;
  --on-accent: #0e0e14;
  --ring: #9184d9;
  --ok: #6fce9f;
  --warn: #e8bd6b;
  --danger: #ffa198;
  --shadow-overlay: 0 12px 32px rgba(0, 0, 0, 0.6);
}

@media (prefers-reduced-motion: reduce) {
  :root { --dur-fast: 0ms; --dur-live: 0ms; --dur-type: 0ms; }
}
```

| Token | Role |
|---|---|
| `--bg` | Page canvas. |
| `--surface-1` | Cards, panels, the terminal, inputs. |
| `--surface-2` | Hovered or selected card, featured panel, secondary button hover. |
| `--surface-3` | Popovers, tooltips, the threshold bar track. |
| `--fg` | Headlines and body text. |
| `--muted` | Secondary text: descriptions, captions of figures. |
| `--subtle` | Tertiary text: timestamps, run ids, eyebrows, disabled labels. |
| `--border` | 1 px hairline on every card, panel and divider. Decorative only. |
| `--border-strong` | Input and dropzone edges; any border that identifies a control (3:1). |
| `--accent` | Primary button, links, selected toggle, value marker on the threshold bar. |
| `--accent-hover` | Hover and pressed state of anything using `--accent`. |
| `--accent-soft` | Background of the selected nav item and of the region box label. |
| `--on-accent` | Text on `--accent` fills. |
| `--ring` | Focus ring colour. |
| `--ok` | Branches that let the run continue or write: `quality_ok`, `aligned`, `change_confirmed`, `no_change`, `auto_write`, `first_baseline`. |
| `--warn` | Branches that ask for more: `recapture`, `retry_classic`, `crop_and_rescan`, `human_approval`. |
| `--danger` | `unrecognized_asset`, failed tool calls, broken hash chain, errors. |

The branch-to-tone map lives in one place, `_TONE` in `services/ui/views.py`; templates and CSS
only consume the `ok` / `warn` / `bad` class it returns.

Theme application:

- The theme script runs inline in `<head>` **before** the stylesheet link, reads
  `localStorage["afterimage-theme"]` inside `try/catch`, and sets `data-theme` on `<html>`.
- With no stored value the page stays light: the explicit product decision is light by default,
  whatever `prefers-color-scheme` says.
- The toggle writes the new value inside `try/catch`; a blocked storage never breaks the toggle.

## 4. Typography

Two families only. The app self-hosts both, so no request leaves for a font CDN:
`static/inter.woff2` (variable, 100–900) and `static/jetbrains-mono-400.woff2` /
`jetbrains-mono-500.woff2`, declared with `@font-face` in `templates/base.html` and credited in
`NOTICE`. Only the standalone `design-preview.html` loads them from Google Fonts:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

| Token | Family | Size | Weight | Line height | Tracking | Use |
|---|---|---|---|---|---|---|
| `display` | sans | 3.5rem (56px) | 600 | 1.10 | -1.8px | Landing hero only |
| `h1` | sans | 2.5rem (40px) | 600 | 1.15 | -1.0px | Page title |
| `h2` | sans | 1.75rem (28px) | 600 | 1.20 | -0.6px | Section title, the verdict line on a trace |
| `h3` | sans | 1.375rem (22px) | 500 | 1.25 | -0.4px | Card title |
| `lead` | sans | 1.125rem (18px) | 400 | 1.50 | -0.1px | Intro paragraph under a title |
| `body` | sans | 1rem (16px) | 400 | 1.50 | -0.05px | Default text |
| `small` | sans | 0.875rem (14px) | 400 | 1.50 | 0 | Card body, nav links, hints |
| `caption` | sans | 0.75rem (12px) | 400 | 1.40 | 0 | Footnotes, figure credits |
| `button` | sans | 0.875rem (14px) | 500 | 1.20 | 0 | Every button label |
| `eyebrow` | sans | 0.875rem (14px) | 600 | 1.40 | 2.52px, uppercase | Stage labels, section kickers |
| `mono` | mono | 0.8125rem (13px) | 400 | 1.40 (18px) | 0 | Trace lines, run ids, keys |
| `metric` | mono | 2.5rem (40px) | 500 | 1.10 | -1.0px | Big numbers: severity score, landing counters |

Rules:

- Every measured number is set in `mono` or `metric`, never in the sans. That includes
  thresholds, run ids, hashes, S3 keys and metric names (`blur_variance`, `inlier_ratio`).
- Display and headings never go above 600, and body never above 400 except `button` (500).
- Below 480 px, `display` drops to 2.25rem (36px) and `h1` to 2rem (32px).
- Paragraph measure is capped at 64ch; hints at 52ch.

## 5. Spacing, grid, radii and shadows

- **Spacing**: 4 px base. Use only `--space-1` (4), `-2` (8), `-3` (12), `-4` (16), `-5` (20),
  `-6` (24), `-8` (32), `-12` (48), `-24` (96).
  - Card padding: `--space-6`. Terminal padding: `--space-5`. Landing hero bands: `--space-24`
    top and bottom.
  - Gap between stacked blocks inside a card: `--space-4`; between cards: `--space-6`; between
    page sections: `--space-12`.
- **Container**: max width 1280 px, centred, side gutter `--space-8` (32 px) at desktop and
  `--space-4` (16 px) under 768 px. Reading pages (trace, queue item) cap at 880 px.
- **Grid**: card grids are 3-up above 1024 px, 2-up from 768 to 1024 px, 1-up below 768 px, with a
  `--space-6` gap. The baseline/capture comparison is 2-up above 768 px and stacks below.
- **Breakpoints**: 1024 px, 768 px, 480 px. No others.
- **Radii**: `--radius-xs` (4) status chips and the region label; `--radius-sm` (6) inline code;
  `--radius-md` (8) buttons, inputs, the terminal; `--radius-lg` (12) cards; `--radius-xl` (16)
  image panels and the dropzone; `--radius-pill` branch pills and toggles only.
- **Elevation**: depth comes from the surface ladder plus a 1 px `--border` hairline. There are
  no drop shadows on cards or buttons. The single shadow, `--shadow-overlay`, is reserved for
  floating layers (tooltip, popover). Emphasis on a card uses a 2 px `--accent` left border, never
  a shadow.

## 6. Components

Each component lists its states. Focus is always `outline: 2px solid var(--ring);
outline-offset: 2px`, applied with `:focus-visible`, and never removed.

### Buttons

Height 40 px (44 px under 768 px), padding 8px 14px, `--radius-md`, `button` type.

| Variant | Default | Hover | Pressed | Disabled | Loading |
|---|---|---|---|---|---|
| Primary | `--accent` fill, `--on-accent` text | `--accent-hover` fill | `--accent-hover` fill, `translateY(1px)` | `--surface-3` fill, `--subtle` text, `cursor: not-allowed` | label kept, a 12 px mono spinner `⠋⠙⠹⠸` before it, `aria-busy="true"`, not clickable |
| Secondary | `--surface-1` fill, `--fg` text, 1 px `--border-strong` | `--surface-2` fill | `--surface-3` fill | as primary | as primary |
| Ghost | transparent, `--accent` text | underline | `--accent-hover` text | `--subtle` text | as primary |

- Error: buttons do not turn red. The error goes in the status line next to them (see Status
  line).
- Destructive or memory-writing actions (approve) use the existing two-step arm: the first click
  changes the label to "Confirm?", the second commits. The armed state keeps the primary fill and
  adds a 2 px `--warn` outline.

### Input (asset id)

- Height 40 px (44 px touch), padding 8px 12px, `--surface-1` fill, 1 px `--border-strong`,
  `--radius-md`, `body` type; the value is set in `mono` because it is an identifier.
- Hover: border `--fg`. Focus: ring. Disabled: `--surface-3` fill, `--subtle` text.
- Error: border `--danger`, and a `small` message in `--danger` below, linked with
  `aria-describedby`. The field keeps the value.
- Loading does not apply to inputs; the form's submit button carries it.

### Dropzone (capture upload)

- `--surface-1` fill, 1 px dashed `--border-strong`, `--radius-xl`, min height 180 px, centred
  `small` hint in `--muted`.
- Hover and drag-over: border solid `--accent`, fill `--accent-soft`. Focus: ring on the wrapper.
- Picked: shows the preview image filling the zone with `object-fit: contain`.
- Error (too large, wrong type): border `--danger`, message in `--danger` below.
- Disabled while a run starts: 60% opacity, no pointer events.

### Card

- `--surface-1` fill, 1 px `--border`, `--radius-lg`, padding `--space-6`.
- Hover (only when the whole card is a link): `--surface-2` fill. Focus: ring on the card.
- Selected or featured: 2 px `--accent` left border.
- Loading: the body is replaced by two 12 px bars in `--surface-3`, no shimmer animation.
- Error: 2 px `--danger` left border and the error text in `--danger`.

### Terminal (trace panel)

The frame of the agent trace, and the demo's protagonist.

- `--surface-1` fill, 1 px `--border`, `--radius-md`, padding `--space-5`, `mono` type,
  horizontal scroll inside the panel, never on the page.
- A header row with three 8 px dots in `--border-strong` and the run id in `--subtle`.
- One line per tool call:
  `<tool>  <metric> <value> <op> <threshold>  → <branch>`, where the tool is `--muted`, the value
  `--fg` at weight 500, and the branch coloured by its semantic token.
- Loading (run in progress): the lines already recorded are shown; each new event adds one line,
  typed in.
- Error: the failing line ends in `✕ <error>` in `--danger`; later lines are not drawn.

### Branch pill

- `--radius-pill`, padding 2px 8px, `caption` type in mono, 1 px border in the semantic colour,
  text in the same colour, transparent fill.
- Pending (not reached yet): `--subtle` text and `--border` border.

### Threshold bar

Shows `value` against `threshold` for one decision.

- Track: 6 px high, `--surface-3`, `--radius-pill`. Fill from 0 to the value in the branch's
  semantic colour. A 2 px `--fg` tick marks the threshold.
- Ends are `mono` captions: `0` on the left, the value (bold) and the threshold label
  ("threshold" / "umbral" from `text.py`) on the right.
- One causal line below in `mono`, `--muted`: `score 0.6798 ≥ 0.4 → human_approval`.

### Navigation

- Top bar: height 56 px, `--bg` fill, 1 px `--border` bottom, sticky.
- Left: the wordmark "afterimage" in sans 500 1.125rem, tracking -0.3px, `--fg`. No logo glyph.
- Centre: links (`small`, `--muted`); the current page is `--accent` on an `--accent-soft`
  pill.
- Right: the three toggles required by the project, in `mono` `caption`:
  - language `EN | ES` and register `plain | technical` are segmented controls of
    `--radius-pill` links inside a 1 px `--border` pill; the current one has `--accent-soft`
    fill, `--accent` text and `aria-current`.
  - theme is a single `--radius-pill` button whose localized label names the theme it switches
    to.
- Under 768 px the links collapse into a `<details>` menu; the toggles stay visible.

### Status line

A single `small` line under an action, with `role="status"` and `aria-live="polite"`. Text in
`--muted` while working, `--ok` on success, `--danger` on error. This is where every button and
form reports errors.

### Image comparison

- Two `--radius-xl` panels on `--surface-1`, each with a `mono` `caption` under it (the S3 key).
- The changed region is a 2 px `--accent` box with its label on an `--accent-soft` chip
  (`--radius-xs`, mono caption).
- The split slider has a 2 px `--fg` handle and a visible focus ring.

## 7. Screens

Routes are the ones served by `services/api/app.py`.

| Screen | Route | Structure | Components |
|---|---|---|---|
| Landing | `/` | Hero band (display title, lead, primary and secondary buttons) beside the scenario demo rail, a row of four counters, how-it-works cards, memory, stack and limits, final call to action | Navigation, buttons, counters, card, branch pill |
| Upload | `/app` | Page title, the asset id input, the dropzone, sample capture buttons, submit, status line | Input, dropzone, buttons, status line |
| Trace | `/traces/{run_id}` | Verdict line (h2 plus branch pill), severity metric, threshold bar, the stage rail, the terminal with one line per tool call, one card per tool call with its threshold bar, image comparison, approve/reject bar when awaiting approval, hash-chain footer | Terminal, branch pill, threshold bar, image comparison, buttons, status line |
| Queue | `/queue` | Title with count, one card per pending finding ordered by severity: comparison, metric, threshold bar, approve/reject | Card, image comparison, threshold bar, buttons |
| Activity | `/activity` | Filter row, then one row per run: run id, asset, time, branch pill, retry when failed | Input, branch pill, ghost button |
| Asset history | `/assets/{asset_id}` | Timeline of inspections and baselines; the baseline in force is marked with the accent left border | Card, branch pill, image thumbnails |
| Gallery | the asset index rendered by `index_page` | 3-up grid of asset cards: latest capture thumbnail, asset id in mono, last branch pill | Card, branch pill |
| Error | any `ApiError` in HTML | Title, the bilingual message, a ghost link back | Card, ghost button |

## 8. Effects

Two protagonists, nothing else animates except state transitions at `--dur-fast`.

### Terminal that types itself (protagonist)

- **Where**: the trace page (`/traces/{run_id}`), section "decisions, one per line". Lines come
  from the run's own `tool_call` events, built by `_terminal` in `services/ui/views.py`; a live
  run types only the lines that arrived since the last poll. The landing keeps its scenario rail
  instead: replaying a run there would mean hard-coding published figures outside
  `eval/results/latest/results.json`.
- **Content**: real decisions only, never invented. For example, the `crack-real-closeup`
  evaluation scenario renders as:

  ```
  assess_quality       blur_variance 1064.0321 ≥ 100.0  → quality_ok
  align_to_baseline    inlier_ratio 0.9988 ≥ 0.9        → aligned
  diff_against_memory  mean_delta 67.7646 ≥ 35.0        → change_confirmed
  classify_severity    score 0.6798 ≥ 0.4               → human_approval
  awaiting a human · nothing written to memory
  ```

- **Implementation**:
  - Render every line in the HTML from the start, so the text is readable without JavaScript and
    by screen readers. Wrap the panel in `aria-live="off"` and give it an accessible label.
  - The script reveals each line with `clip-path: inset(0 calc(100% - var(--shown)) 0 0)`, one
    character (`1ch`) every `--dur-type` (28 ms). Lines play in sequence, 350 ms apart.
  - Progress is computed from `performance.now()`, not by counting timer ticks, so a throttled
    background tab catches up instead of typing several lines at once.
  - It starts on page load and again after each live swap, for the new lines only.
- **Reduced motion**: under `prefers-reduced-motion: reduce`, every line is shown complete at
  once, with no delay.

### Animated counters (secondary)

- **Where**: the landing counter row only.
- **Values**: the published evaluation figures (branch accuracy, defect macro F1, mean IoU,
  real photographs out of scenarios). They come from `eval/results/latest/results.json` and are
  already checked by `eval/tests/test_published_numbers.py`; never type them by hand anywhere
  else.
- **Implementation**:
  - The final value is in the HTML.
  - The script counts from 0 to it over 900 ms with `--ease-out` when the row enters the
    viewport, keeping the same number of decimals throughout so the width never jumps. The digits
    use `font-variant-numeric: tabular-nums`.
- **Reduced motion**: the final value is shown as is; no count.

## 9. Rules

Do:

- Use only the tokens in section 3 and the type scale in section 4. When something seems
  missing, reuse the nearest existing token and flag it; do not add one silently.
- Colour a branch only through `--ok`, `--warn` or `--danger`, and always pair the colour with
  the branch name in text. Colour is never the only signal.
- Put every number in mono, and show it next to its threshold wherever a decision is displayed.
- Keep all copy in `services/ui/text.py`, in English and Spanish, with `_plain` / `_tech` only
  where the prose really differs. Measurements, metric names and trace messages are never
  translated.
- Keep the three toggles (language, register, theme) on every page.
- Default to the light theme; the dark theme is a full peer and must be checked on every change.

Don't:

- Don't add a second accent, a gradient, a glow, a spotlight card, glassmorphism or any
  background image. The only images are the captures themselves.
- Don't add drop shadows to cards or buttons, or round a button into a pill.
- Don't use `--accent` as a section or card background; `--accent-soft` is the only tinted fill.
- Don't add a font, an icon library or a front-end dependency.
- Don't animate anything beyond the two effects in section 8, and never without the reduced-motion
  variant.
- Don't use a brand logo, brand name or brand typeface from the source systems.

## 10. Verification checklist

Run each item in both themes before calling a UI change done.

- [ ] **Theme**: the page loads light with no stored preference, the toggle switches to dark and
  back, the choice survives a reload, and there is no flash of the wrong theme on first paint.
- [ ] **Contrast (light)**: `--fg`, `--muted`, `--subtle`, `--accent`, `--ok`, `--warn` and
  `--danger` reach 4.5:1 on `--bg`, `--surface-1`, `--surface-2` and `--surface-3`.
  `--on-accent` reaches 4.5:1 on `--accent` and `--accent-hover`. `--border-strong` and `--ring`
  reach 3:1 on `--bg` and `--surface-1`.
- [ ] **Contrast (dark)**: the same pairs, measured again with the dark values; a token that
  passes in one theme proves nothing about the other.
- [ ] **Keyboard**: every control is reachable with Tab in visual order, shows the 2 px focus
  ring, and works with Enter/Space; the two-step approve can be armed and confirmed from the
  keyboard.
- [ ] **Responsive**: no horizontal page scroll at 375, 768, 1024 and 1440 px; the terminal
  scrolls inside its panel; touch targets are at least 44 px under 768 px.
- [ ] **Reduced motion**: with `prefers-reduced-motion: reduce`, the terminal shows every line at
  once and the counters show their final values.
- [ ] **Language**: switching to ES updates `<html lang>`, and numbers and dates follow the same
  locale.
- [ ] **Numbers**: every figure on the landing matches `eval/results/latest/results.json` (the
  published-numbers test passes).
