import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VIDEO = Path(__file__).parent
BUILDER = VIDEO / "build-face-audio.py"
SCRIPT = VIDEO / "script.tsv"

BEATS = [
    ("0:00", "face-open.mov"),
    ("0:25", "body-1.mov"),
    ("1:00", "body-2.mov"),
    ("1:30", "body-3.mov"),
    ("3:15", "body-4.mov"),
    ("4:00", "body-5.mov"),
    ("4:35", "face-close.mov"),
]
GAP = float(os.environ.get("REHEARSAL_GAP", "0.45"))
VOICE = "Mónica"
WPM = "180"
TOLERANCE = 0.25


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def load_lines():
    lines = {}
    for row in SCRIPT.read_text().splitlines()[1:]:
        beat, en, es = row.split("\t")
        lines.setdefault(beat, []).append((en, es))
    return lines


def speak(stage, lines):
    truth = {}
    silence = stage / "gap.wav"
    run("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "anullsrc=r=22050:cl=mono", "-t", str(GAP), str(silence))
    for beat, name in BEATS:
        parts, spoken = [], []
        for i, (_, es) in enumerate(lines[beat]):
            aiff, wav = stage / f"{name}-{i}.aiff", stage / f"{name}-{i}.wav"
            run("say", "-v", VOICE, "-r", WPM, "-o", str(aiff), es)
            run("ffmpeg", "-y", "-v", "error", "-i", str(aiff),
                "-ar", "22050", "-ac", "1", str(wav))
            spoken.append(duration(wav))
            if parts:
                parts.append(silence)
            parts.append(wav)
        listing = stage / f"{name}.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        track = stage / f"{name}.wav"
        run("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
            "-i", str(listing), "-c", "copy", str(track))
        run("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
            "color=c=black:s=320x240:r=30", "-i", str(track), "-shortest",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(stage / name))
        truth[name] = spoken
        print(f"  spoke {name}")
    return truth


def silences(path):
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-af", "silencedetect=noise=-30dB:d=0.20", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    )
    return list(zip([float(x) for x in re.findall(r"silence_start: ([\d.]+)", proc.stderr)],
                    [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]))


def parse_srt(path):
    def secs(stamp):
        h, m, rest = stamp.split(":")
        s, ms = rest.split(",")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    cues = []
    for block in path.read_text().strip().split("\n\n"):
        rows = block.split("\n")
        start, end = rows[1].split(" --> ")
        cues.append((secs(start), secs(end), rows[2]))
    return cues


def main():
    if not shutil.which("say"):
        sys.exit("needs macOS: this rehearsal speaks the script with `say`")

    lines = load_lines()
    stage = Path(tempfile.mkdtemp(prefix="afterimage-rehearsal-"))
    print(f"\n  staging in {stage}\n")
    truth = speak(stage, lines)

    shutil.copy(BUILDER, stage)
    shutil.copy(SCRIPT, stage)
    hook, lead = VIDEO / "out" / "hook.wav", 0.0
    if hook.exists():
        (stage / "out").mkdir(parents=True, exist_ok=True)
        shutil.copy(hook, stage / "out" / hook.name)
        lead = duration(hook)
        print(f"  hook {lead:.1f} s in front — the cues have to come back shifted")
    print()
    subprocess.run([sys.executable, str(stage / BUILDER.name)], check=True)

    cues = parse_srt(stage / "out" / "captions.srt")
    expected = sum(len(v) for v in lines.values())
    assert len(cues) == expected, f"{len(cues)} cues, expected {expected}"

    shrunk = sum(duration(stage / n) - duration(stage / "out" / "clips" / n)
                 for _, n in BEATS)
    trimmed = shrunk > 0.5

    failures, worst, index, offset = 0, 0.0, 0, lead
    longest_pause = 0.0
    for beat, name in BEATS:
        cut = stage / "out" / "clips" / name
        span = duration(cut)
        gaps = silences(cut)
        n = len(lines[beat])

        for i, (en, _) in enumerate(lines[beat]):
            if cues[index + i][2] != en:
                print(f"  FAIL: caption out of order in {name} row {i}")
                failures += 1

        for i in range(1, n):
            t = cues[index + i][0] - offset
            if not any(a - 0.06 <= t <= b + 0.06 for a, b in gaps):
                print(f"  FAIL: {name} boundary {i} at {t:.2f}s lands in speech")
                failures += 1

        inner = [b - a for a, b in gaps if a > 0.15 and b < span - 0.15]
        longest_pause = max([longest_pause] + inner)

        if not trimmed:
            spoken, elapsed = truth[name], 0.0
            for i in range(len(spoken) - 1):
                elapsed += spoken[i]
                want = elapsed + i * GAP + GAP / 2
                error = abs((cues[index + i + 1][0] - offset) - want)
                worst = max(worst, error)
                if error > TOLERANCE:
                    failures += 1

        index += n
        offset += span

    print(f"  {len(cues)} cues, every caption inside a real silence")
    if trimmed:
        print(f"  trimming removed {shrunk:.1f} s, longest surviving pause {longest_pause:.2f} s")
        if longest_pause > 1.0:
            print(f"  FAIL: a {longest_pause:.2f} s pause survived the cap")
            failures += 1
    else:
        print(f"  worst boundary error {worst * 1000:.0f} ms "
              f"(tolerance {TOLERANCE * 1000:.0f} ms)")
    print(f"  {failures} failures\n")
    shutil.rmtree(stage, ignore_errors=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
