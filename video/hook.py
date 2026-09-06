import json
import os
import subprocess
from pathlib import Path

VIDEO = Path(__file__).parent
ROOT = VIDEO.parent
OUT = VIDEO / "out"
STAGE = OUT / "hook"

MONO = "/System/Library/Fonts/SFNSMono.ttf"
SANS = "/System/Library/Fonts/HelveticaNeue.ttc"

W, H, FPS = 1920, 1080, 30
PAD = 14

SHOTS = [
    {
        "image": ROOT / "eval/dataset/base/array_ground_mounted.jpg",
        "seconds": 3.0,
        "push": 0.08,
        "headline": "1,700,000 panels",
    },
    {
        "image": VIDEO / "img/1-blurred.png",
        "seconds": 3.0,
        "metric": "blur_variance    3.6589  <   100.0   ->  recapture",
    },
    {
        "image": VIDEO / "img/3-defect.png",
        "seconds": 3.5,
        "source_box": (342, 213, 104, 72),
        "metric": "score            0.6798  >=    0.4    ->  human_approval",
    },
    {"seconds": 1.5},
    {"seconds": 3.0, "title": "afterimage", "subtitle": "it does not guess. it measures."},
]

HITS = [0.0, 3.0, 6.0]
SECONDS = sum(shot["seconds"] for shot in SHOTS)
DRONE_OUT = 8.9
SWELL_AT = 11.0


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def probe_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    w, h = out.stdout.strip().split(",")
    return int(w), int(h)


def text_layer(name, body, font, size, x, y, extra=""):
    path = STAGE / f"{name}.txt"
    path.write_text(body)
    return (f"drawtext=textfile='{path}':fontfile='{font}':fontsize={size}:"
            f"fontcolor=white:x={x}:y={y}{extra}")


def fill(path):
    src_w, src_h = probe_size(path)
    scaled_h = round(src_h * W / src_w)
    return f"scale={W}:{scaled_h},crop={W}:{H}", W / src_w, (scaled_h - H) // 2


def shot_filter(index, shot):
    chain = []
    if "image" in shot:
        chain.append(fill(shot["image"])[0])
        if shot.get("push"):
            zoom = shot["push"]
            frames = round(shot["seconds"] * FPS)
            chain.append(
                f"scale={round(W * (1 + zoom))}:{round(H * (1 + zoom))},"
                f"zoompan=z='1+{zoom}*on/{frames}':x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS}"
            )
    if "source_box" in shot:
        _, scale, offset = fill(shot["image"])
        bx, by, bw, bh = shot["source_box"]
        chain.append(
            f"drawbox=x={round(bx * scale) - PAD}:y={round(by * scale) - offset - PAD}:"
            f"w={round(bw * scale) + 2 * PAD}:h={round(bh * scale) + 2 * PAD}:"
            f"color=#ff3b30@0.95:t=4:enable='gte(t,0.4)'"
        )
    if "headline" in shot:
        chain.append(text_layer(
            f"{index}-headline", shot["headline"], SANS, 96, 120, f"{H}-260",
            ":box=1:boxcolor=black@0.55:boxborderw=28",
        ))
    if "metric" in shot:
        chain.append(text_layer(
            f"{index}-metric", shot["metric"], MONO, 44, 120, f"{H}-230",
            ":box=1:boxcolor=black@0.65:boxborderw=26:enable='gte(t,0.4)'",
        ))
    if "title" in shot:
        chain.append(text_layer(
            f"{index}-title", shot["title"], SANS, 140, "(w-text_w)/2", "(h-text_h)/2-70",
        ))
        chain.append(text_layer(
            f"{index}-subtitle", shot["subtitle"], MONO, 46, "(w-text_w)/2", "(h-text_h)/2+90",
        ))
        chain.append("fade=t=in:st=0:d=0.5")
    chain.append(f"setsar=1,fps={FPS},format=yuv420p")
    return ",".join(chain)


def render_shot(index, shot):
    dest = STAGE / f"{index}.mp4"
    if "image" in shot:
        source = ["-loop", "1", "-t", str(shot["seconds"]), "-i", str(shot["image"])]
    else:
        source = ["-f", "lavfi", "-i",
                  f"color=c=black:s={W}x{H}:r={FPS}:d={shot['seconds']}"]
    ffmpeg(*source, "-vf", shot_filter(index, shot), "-t", str(shot["seconds"]),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
           "-pix_fmt", "yuv420p", "-r", str(FPS), str(dest))
    return dest


def render_video(dest):
    parts = [render_shot(i, shot) for i, shot in enumerate(SHOTS)]
    listing = STAGE / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(dest))


def render_audio(dest):
    inputs, graph, mixed = [], [], []
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=48000:duration={SECONDS}"]
    graph.append(f"[0:a]lowpass=f=180,volume=0.30,afade=t=in:st=0:d=0.6,"
                 f"afade=t=out:st={DRONE_OUT}:d=0.6[drone]")
    mixed.append("[drone]")

    inputs += ["-f", "lavfi", "-i", "sine=frequency=120:sample_rate=48000:duration=1.6"]
    taps = "".join(f"[h{i}]" for i in range(len(HITS)))
    graph.append(f"[1:a]volume='exp(-5*t)':eval=frame,asplit={len(HITS)}{taps}")
    for i, at in enumerate(HITS):
        graph.append(f"[h{i}]adelay={round(at * 1000)}:all=1[d{i}]")
        mixed.append(f"[d{i}]")

    swell = SECONDS - SWELL_AT
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=55:sample_rate=48000:duration={swell}"]
    graph.append(f"[2:a]lowpass=f=180,volume=0.22,afade=t=in:st=0:d=1.2,"
                 f"adelay={round(SWELL_AT * 1000)}:all=1[swell]")
    mixed.append("[swell]")

    graph.append(f"{''.join(mixed)}amix=inputs={len(mixed)}:normalize=0:duration=longest,"
                 f"apad,atrim=0:{SECONDS},alimiter=limit=0.9,"
                 f"aformat=sample_rates=48000:channel_layouts=mono[a]")
    ffmpeg(*inputs, "-filter_complex", ";".join(graph), "-map", "[a]",
           "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(dest))


def spec():
    return json.dumps(
        {"shots": [{k: str(v) for k, v in s.items()} for s in SHOTS],
         "hits": HITS, "size": [W, H, FPS], "pad": PAD,
         "drone_out": DRONE_OUT, "swell_at": SWELL_AT},
        sort_keys=True,
    )


def main():
    if "/opt/homebrew/opt/ffmpeg@7/bin" not in os.environ["PATH"]:
        os.environ["PATH"] = "/opt/homebrew/opt/ffmpeg@7/bin:" + os.environ["PATH"]

    video, audio = OUT / "hook.mov", OUT / "hook.wav"
    plan, want = OUT / "hook.plan", spec()
    if video.exists() and audio.exists() and plan.exists() and plan.read_text() == want:
        print(f"\n  hook up to date — {video}, {audio}\n")
        return 0

    STAGE.mkdir(parents=True, exist_ok=True)
    render_video(video)
    render_audio(audio)
    plan.write_text(want)
    print(f"\n  hook  {SECONDS:.1f} s   {W}x{H} @ {FPS}   -> out/hook.mov, out/hook.wav\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
