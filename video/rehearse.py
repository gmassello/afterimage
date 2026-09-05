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
GAP = 0.45
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
    print()
    subprocess.run([sys.executable, str(stage / BUILDER.name)], check=True)

    cues = parse_srt(stage / "out" / "captions.srt")
    expected = sum(len(v) for v in lines.values())
    assert len(cues) == expected, f"{len(cues)} cues, expected {expected}"

    worst, over, index, offset = 0.0, 0, 0, 0.0
    for beat, name in BEATS:
        spoken = truth[name]
        for i, (en, _) in enumerate(lines[beat]):
            assert cues[index + i][2] == en, f"caption out of order in {name} row {i}"
        elapsed = 0.0
        for i in range(len(spoken) - 1):
            elapsed += spoken[i]
            boundary = elapsed + i * GAP + GAP / 2
            error = abs((cues[index + i + 1][0] - offset) - boundary)
            worst = max(worst, error)
            over += error > TOLERANCE
        index += len(spoken)
        offset += duration(stage / name)

    print(f"  {len(cues)} cues, every caption in order")
    print(f"  worst boundary error {worst * 1000:.0f} ms, "
          f"{over} over the {TOLERANCE * 1000:.0f} ms tolerance\n")
    shutil.rmtree(stage, ignore_errors=True)
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
