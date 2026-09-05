import os
import re
import subprocess
import sys
from pathlib import Path

VIDEO = Path(__file__).parent
OUT = VIDEO / "out"
SCRIPT = VIDEO / "script.tsv"

MAX_SECONDS = 300.0
NOISE_DB = os.environ.get("NOISE_DB", "-30dB")
MIN_SILENCE = float(os.environ.get("MIN_SILENCE", "0.20"))
EDGE_GUARD = 0.15

BEATS = [
    ("0:00", "face-open.mov"),
    ("0:25", "body-1.mov"),
    ("1:00", "body-2.mov"),
    ("1:30", "body-3.mov"),
    ("3:15", "body-4.mov"),
    ("4:00", "body-5.mov"),
    ("4:35", "face-close.mov"),
]
BODY = BEATS[1:6]


def load_lines():
    rows = SCRIPT.read_text().splitlines()[1:]
    lines = {}
    for row in rows:
        beat, en, es = row.split("\t")
        lines.setdefault(beat, []).append((en, es))
    return lines


def stream_format(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,sample_rate,channels", "-of", "csv=p=0:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return " ".join(out.stdout.split())


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def silences(path):
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-af", f"silencedetect=noise={NOISE_DB}:d={MIN_SILENCE}", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", proc.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    return list(zip(starts, ends))


def proportional(span, texts):
    weights = [len(t) for t in texts]
    total = sum(weights)
    cuts, running = [], 0
    for w in weights[:-1]:
        running += w
        cuts.append(span * running / total)
    return cuts


def boundaries(dur, gaps, texts):
    if len(texts) < 2:
        return [], "single", 0
    inner = [g for g in gaps if g[0] > EDGE_GUARD and g[1] < dur - EDGE_GUARD]
    needed = len(texts) - 1
    if len(inner) < needed:
        return proportional(dur, texts), "proportional", len(inner)
    longest = sorted(inner, key=lambda g: g[1] - g[0], reverse=True)[:needed]
    return [(a + b) / 2 for a, b in sorted(longest)], "silence", len(inner)


def dead_air(dur, gaps):
    lead = next((e for s, e in gaps if s < 0.05), 0.0)
    tail = next((dur - s for s, e in gaps if e > dur - 0.05), 0.0)
    return lead, tail


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def concat_audio(clips, dest):
    inputs = []
    for clip in clips:
        inputs += ["-i", str(clip)]
    fixed = "".join(
        f"[{i}:a]aformat=sample_rates=48000:channel_layouts=mono[a{i}];"
        for i in range(len(clips))
    )
    streams = "".join(f"[a{i}]" for i in range(len(clips)))
    graph = (f"{fixed}{streams}concat=n={len(clips)}:v=0:a=1[c];"
             "[c]loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", graph,
         "-map", "[a]", "-ar", "48000", "-ac", "1", str(dest)],
        check=True,
    )


def main():
    lines = load_lines()
    missing = [name for _, name in BEATS if not (VIDEO / name).exists()]

    measured, offset, cues, formats = [], 0.0, [], {}
    print()
    print(f"  {'clip':<16}{'beat':<7}{'length':>8}{'lines':>7}{'pauses':>8}  {'method':<13}{'dead air':>10}")
    for beat, name in BEATS:
        path = VIDEO / name
        if not path.exists():
            print(f"  {name:<16}{beat:<7}{'--':>8}{len(lines[beat]):>7}{'--':>8}  {'not recorded':<13}")
            continue
        dur = duration(path)
        fmt = stream_format(path)
        formats.setdefault(fmt, []).append(name)
        gaps = silences(path)
        texts = [es for _, es in lines[beat]]
        cuts, method, found = boundaries(dur, gaps, texts)
        lead, tail = dead_air(dur, gaps)
        measured.append((beat, name, dur))

        edges = [0.0] + cuts + [dur]
        for i, (en, _) in enumerate(lines[beat]):
            cues.append((offset + edges[i], offset + edges[i + 1], en))
        offset += dur

        flag = "" if method == "silence" or len(texts) < 2 else "  <-- CHECK"
        print(f"  {name:<16}{beat:<7}{dur:>7.1f}s{len(texts):>7}{found:>8}  {method:<13}"
              f"{lead + tail:>9.1f}s{flag}")
    print()

    if len(formats) > 1:
        print("  the clips are not all the same format — fix this before recording the screencast:")
        for fmt, names in formats.items():
            print(f"    {fmt:<28}{', '.join(names)}")
        print()

    if missing:
        print(f"  pending: {', '.join(missing)}")
        print("  nothing written until all seven clips exist.\n")
        return 1

    total = sum(d for _, _, d in measured)
    body = [(b, n, d) for b, n, d in measured if (b, n) in BODY]

    OUT.mkdir(parents=True, exist_ok=True)
    concat_audio([VIDEO / n for _, n in BODY], OUT / "body.wav")
    concat_audio([VIDEO / n for _, n in BEATS], OUT / "narration.wav")

    rows, start = ["  beat    starts      ends   length"], 0.0
    for beat, _, dur in body:
        rows.append(f"  {beat:<8}{start:>6.1f}{start + dur:>10.1f}{dur:>9.1f}")
        start += dur
    (OUT / "body-timing.txt").write_text("\n".join(rows) + "\n")

    srt = []
    for i, (a, b, text) in enumerate(cues, 1):
        srt.append(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n")
    (OUT / "captions.srt").write_text("\n".join(srt))

    print(f"  body   {sum(d for _, _, d in body):6.1f} s   -> out/body.wav, out/body-timing.txt")
    print(f"  total  {total:6.1f} s   =  {int(total // 60)}:{total % 60:04.1f}   "
          f"-> out/narration.wav, out/captions.srt ({len(cues)} cues)")
    over = total - MAX_SECONDS
    print(f"  HARD CAP 5:00 — " + ("OK" if over < 0 else f"OVER by {over:.1f} s, CUT A BEAT"))
    print()
    return 0 if total < MAX_SECONDS else 1


if __name__ == "__main__":
    raise SystemExit(main())
