import json
import subprocess
from pathlib import Path

VIDEO = Path(__file__).parent
SCRIPT = VIDEO / "script.tsv"
OUT = VIDEO / "out" / "teleprompter.html"
HOOK = VIDEO / "out" / "hook.mov"


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())

CHARS_PER_SECOND = 13.5
PAUSE = 0.45

CLIPS = [
    ("0:00", "face-open.mov", "Opening, to camera"),
    ("0:25", "body-1.mov", "The problem"),
    ("1:00", "body-2.mov", "Architecture"),
    ("1:30", "body-3.mov", "The demo"),
    ("3:15", "body-4.mov", "The trace"),
    ("4:00", "body-5.mov", "Evaluation"),
    ("4:35", "face-close.mov", "Close, to camera"),
]

TEMPLATE = r"""<title>Afterimage Teleprompter</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
  :root {
    --ground: #0b0e13;
    --surface: #141922;
    --rule: #242c38;
    --dim: #5d6875;
    --mid: #8e9aa8;
    --text: #e9eef5;
    --amber: #ffc24d;
    --amber-soft: #ffc24d26;
    --red: #ff8f7a;
    --scale: 1;
    --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    --sans: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--text);
    font-family: var(--sans);
    display: grid;
    grid-template-rows: auto 1fr auto;
    overflow: hidden;
  }

  .rail {
    display: flex;
    gap: 1px;
    background: var(--rule);
    border-bottom: 1px solid var(--rule);
    overflow-x: auto;
  }
  .tab {
    flex: 1 1 0;
    min-width: 92px;
    background: var(--ground);
    border: 0;
    border-top: 2px solid transparent;
    color: var(--dim);
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: .04em;
    padding: 10px 8px 9px;
    text-align: left;
    cursor: pointer;
    display: grid;
    gap: 3px;
    transition: color .15s, background .15s;
  }
  .tab:hover { color: var(--mid); background: var(--surface); }
  .tab:focus-visible { outline: 2px solid var(--amber); outline-offset: -2px; }
  .tab[aria-current="true"] {
    background: var(--surface);
    border-top-color: var(--amber);
    color: var(--text);
  }
  .tab b { font-weight: 500; font-size: 13px; }
  .tab[aria-current="true"] b { color: var(--amber); }
  .tab b, .tab span, .tab { white-space: nowrap; text-overflow: ellipsis; overflow: hidden; }
  .tab span { font-size: 10px; color: var(--dim); }

  main {
    display: grid;
    align-content: center;
    gap: clamp(14px, 2.2vh, 26px);
    padding: clamp(20px, 4vh, 52px) clamp(20px, 5vw, 76px);
    overflow-y: auto;
    text-align: center;
  }
  main.mirror { transform: scaleX(-1); }

  .ctx {
    font-size: calc(clamp(.8rem, 1.5vw, 1.15rem) * var(--scale));
    color: var(--dim);
    line-height: 1.45;
    max-width: 60ch;
    margin-inline: auto;
    min-height: 1.45em;
  }
  .ctx.next { color: var(--mid); }

  #line {
    font-size: calc(var(--fit, 1) * clamp(1.5rem, 3.5vw, 3.2rem) * var(--scale));
    font-weight: 600;
    line-height: 1.24;
    letter-spacing: -.015em;
    text-wrap: balance;
    max-width: 22ch;
    margin-inline: auto;
    animation: rise .34s ease-out;
  }
  #line.wide { max-width: 34ch; }
  @keyframes rise { from { opacity: 0; transform: translateY(9px); } }

  .sub {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--dim);
    max-width: 72ch;
    margin-inline: auto;
    padding-top: clamp(6px, 1.4vh, 16px);
    border-top: 1px solid var(--rule);
    line-height: 1.5;
  }
  .sub em { color: var(--mid); font-style: normal; }

  footer {
    border-top: 1px solid var(--rule);
    background: var(--surface);
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 9px 16px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--dim);
    flex-wrap: wrap;
  }
  .pips { display: flex; gap: 4px; flex: 1 1 240px; align-items: center; }
  .pip {
    height: 4px; flex: 1 1 auto; min-width: 3px;
    background: var(--rule); border-radius: 2px;
    transition: background .18s;
  }
  .pip.done { background: var(--dim); }
  .pip.now { background: var(--amber); }
  .count { color: var(--mid); font-variant-numeric: tabular-nums; }
  .clock {
    font-size: 21px;
    font-weight: 500;
    color: var(--text);
    font-variant-numeric: tabular-nums;
    letter-spacing: .01em;
    line-height: 1;
  }
  .clock small { font-size: 12px; font-weight: 400; color: var(--dim); }
  .clock.warn { color: var(--amber); }
  .clock.warn small { color: var(--amber); opacity: .7; }
  .clock.over { color: var(--red); }
  .clock.over small { color: var(--red); opacity: .7; }

  .btns { display: flex; gap: 6px; }
  .btns button {
    background: var(--ground);
    border: 1px solid var(--rule);
    color: var(--mid);
    font-family: var(--mono);
    font-size: 11px;
    padding: 5px 10px;
    border-radius: 4px;
    cursor: pointer;
  }
  .btns button:hover { color: var(--text); border-color: var(--dim); }
  .btns button:focus-visible { outline: 2px solid var(--amber); outline-offset: 1px; }
  .btns button[aria-pressed="true"] { color: var(--amber); border-color: var(--amber); background: var(--amber-soft); }

  .hint { color: var(--dim); }
  .hint kbd {
    font-family: var(--mono);
    background: var(--ground);
    border: 1px solid var(--rule);
    border-radius: 3px;
    padding: 1px 5px;
    color: var(--mid);
  }

  .cue {
    position: fixed;
    inset-inline: 0;
    bottom: 74px;
    text-align: center;
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: .22em;
    text-transform: uppercase;
    color: var(--amber);
    pointer-events: none;
    opacity: 0;
  }
  .cue.show { animation: cue 1s ease-out; }
  @keyframes cue { 0% { opacity: .85; } 100% { opacity: 0; } }

  @media (prefers-reduced-motion: reduce) {
    #line { animation: none; }
    .cue.show { animation: none; }
  }
  @media (max-width: 620px) {
    .tab span { display: none; }
    .hint { display: none; }
  }
</style>

<nav class="rail" id="rail" aria-label="Clips"></nav>

<main id="stage">
  <p class="ctx prev" id="prev"></p>
  <p id="line"></p>
  <p class="ctx next" id="next"></p>
  <p class="sub" id="sub"></p>
</main>

<div class="cue" id="cue">pausá</div>

<footer>
  <span class="count" id="count">1 / 7</span>
  <span class="pips" id="pips"></span>
  <span class="clock" id="clock">0:00</span>
  <span class="btns">
    <button id="prevBtn" type="button">◀ atrás</button>
    <button id="nextBtn" type="button">siguiente ▶</button>
    <button id="mirrorBtn" type="button" aria-pressed="false">espejo</button>
    <button id="smaller" type="button" aria-label="Achicar el texto">A−</button>
    <button id="bigger" type="button" aria-label="Agrandar el texto">A+</button>
  </span>
  <span class="hint"><kbd>espacio</kbd> avanza · <kbd>↑</kbd> vuelve · <kbd>◀ ▶</kbd> cambia de clip · <kbd>R</kbd> reinicia el reloj</span>
</footer>

<script>
const CLIPS = __CLIPS__;

const $ = (id) => document.getElementById(id);
const stage = $("stage"), lineEl = $("line"), cue = $("cue");

let clip = 0, row = 0, scale = 1, mirror = false;
let startedAt = null, ticker = null;

function load() {
  try {
    const s = JSON.parse(localStorage.getItem("prompter") || "{}");
    clip = Math.min(s.clip ?? 0, CLIPS.length - 1);
    row = Math.min(s.row ?? 0, CLIPS[clip].lines.length - 1);
    scale = s.scale ?? 1;
    mirror = !!s.mirror;
  } catch (e) { /* first run, or storage blocked */ }
}
function save() {
  try {
    localStorage.setItem("prompter", JSON.stringify({ clip, row, scale, mirror }));
  } catch (e) { /* storage blocked; the page still works */ }
}

function buildRail() {
  $("rail").innerHTML = "";
  CLIPS.forEach((c, i) => {
    const b = document.createElement("button");
    b.className = "tab";
    b.type = "button";
    b.innerHTML = `<b>${c.beat}</b>${c.file}` +
      `<span>${c.title} · ${c.lines.length} · ${fmt(c.target)}</span>`;
    b.onclick = () => go(i, 0);
    $("rail").appendChild(b);
  });
}

function fmt(s) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

function tick() {
  const el = startedAt ? (Date.now() - startedAt) / 1000 : 0;
  const target = CLIPS[clip].target;
  const c = $("clock");
  c.innerHTML = `${fmt(el)} <small>/ ${fmt(target)}</small>`;
  c.classList.toggle("warn", el > target);
  c.classList.toggle("over", el > target * 1.15);
}

function resetClock() {
  startedAt = null;
  clearInterval(ticker);
  ticker = null;
  tick();
}

function render() {
  const c = CLIPS[clip], lines = c.lines, l = lines[row];

  [...$("rail").children].forEach((t, i) =>
    t.setAttribute("aria-current", String(i === clip)));

  $("prev").textContent = row > 0 ? lines[row - 1].es : "";
  $("next").textContent = row < lines.length - 1 ? lines[row + 1].es : "";

  lineEl.textContent = l.es;
  lineEl.classList.toggle("wide", l.es.length > 95);
  lineEl.style.setProperty("--fit", Math.min(1, Math.max(0.52, 78 / l.es.length)).toFixed(3));
  lineEl.style.animation = "none";
  void lineEl.offsetWidth;
  lineEl.style.animation = "";

  $("sub").innerHTML = `<em>subtítulo</em> &nbsp;${l.en.replace(/[<>&]/g, (m) =>
    ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[m]))}`;

  $("count").textContent = `${c.file} · ${row + 1} / ${lines.length}`;
  $("pips").innerHTML = lines.map((_, i) =>
    `<i class="pip ${i < row ? "done" : i === row ? "now" : ""}"></i>`).join("");

  $("prevBtn").disabled = clip === 0 && row === 0;
  document.documentElement.style.setProperty("--scale", scale);
  stage.classList.toggle("mirror", mirror);
  $("mirrorBtn").setAttribute("aria-pressed", String(mirror));
  tick();
  save();
}

function go(nextClip, nextRow) {
  const changedClip = nextClip !== clip;
  clip = nextClip;
  row = nextRow;
  if (changedClip) resetClock();
  render();
}

function advance(step) {
  const lines = CLIPS[clip].lines;
  if (step > 0 && !startedAt) {
    startedAt = Date.now();
    ticker = setInterval(tick, 250);
  }
  if (row + step >= 0 && row + step < lines.length) {
    row += step;
    render();
    if (step > 0) {
      cue.classList.remove("show");
      void cue.offsetWidth;
      cue.classList.add("show");
    }
    return;
  }
  if (step > 0 && clip < CLIPS.length - 1) go(clip + 1, 0);
  else if (step < 0 && clip > 0) go(clip - 1, CLIPS[clip - 1].lines.length - 1);
}

function resize(delta) {
  scale = Math.min(1.8, Math.max(0.6, +(scale + delta).toFixed(2)));
  render();
}

$("nextBtn").onclick = () => advance(1);
$("prevBtn").onclick = () => advance(-1);
$("bigger").onclick = () => resize(0.1);
$("smaller").onclick = () => resize(-0.1);
$("mirrorBtn").onclick = () => { mirror = !mirror; render(); };
stage.onclick = () => advance(1);

document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "BUTTON" && (e.key === " " || e.key === "Enter")) return;
  const k = e.key;
  if (k === " " || k === "ArrowDown" || k === "PageDown") { e.preventDefault(); advance(1); }
  else if (k === "ArrowUp" || k === "PageUp") { e.preventDefault(); advance(-1); }
  else if (k === "ArrowRight") { e.preventDefault(); if (clip < CLIPS.length - 1) go(clip + 1, 0); }
  else if (k === "ArrowLeft") { e.preventDefault(); if (clip > 0) go(clip - 1, 0); }
  else if (k === "+" || k === "=") resize(0.1);
  else if (k === "-") resize(-0.1);
  else if (k.toLowerCase() === "m") { mirror = !mirror; render(); }
  else if (k.toLowerCase() === "r") resetClock();
  else if (k === "Home") go(clip, 0);
});

load();
buildRail();
render();
tick();
</script>
"""


def main():
    rows = {}
    for line in SCRIPT.read_text().splitlines()[1:]:
        beat, en, es = line.split("\t")
        rows.setdefault(beat, []).append({"en": en, "es": es})

    missing = [b for b, _, _ in CLIPS if b not in rows]
    if missing:
        raise SystemExit(f"script.tsv has no rows for {', '.join(missing)}")

    data = []
    for beat, name, title in CLIPS:
        lines = rows[beat]
        spoken = sum(len(row["es"]) for row in lines) / CHARS_PER_SECOND
        target = round(spoken + (len(lines) - 1) * PAUSE)
        data.append({"beat": beat, "file": name, "title": title,
                     "lines": lines, "target": target})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(TEMPLATE.replace("__CLIPS__", json.dumps(data, ensure_ascii=False, indent=1)))
    budget = sum(c["target"] for c in data)
    print(f"{OUT}  {len(data)} clips, {sum(len(c['lines']) for c in data)} lines")
    for c in data:
        print(f"  {c['file']:<16}{c['target']:>4} s")
    hook = round(duration(HOOK)) if HOOK.exists() else 0
    if hook:
        print(f"  {'hook':<16}{hook:>4} s   out/hook.mov, no voice")
    else:
        print(f"  {'hook':<16}{'--':>4}     out/hook.mov not built — run video/hook.py")
    total = budget + hook
    print(f"  {'TOTAL':<16}{total:>4} s = {total // 60}:{total % 60:02d}"
          f"   ({300 - total} s under the cap)")


if __name__ == "__main__":
    raise SystemExit(main())
