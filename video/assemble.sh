#!/bin/bash
set -euo pipefail

[ -d /opt/homebrew/opt/ffmpeg@7/bin ] && PATH="/opt/homebrew/opt/ffmpeg@7/bin:$PATH"

VIDEO_DIR="${VIDEO_DIR:-$PWD/video}"
OUT="$VIDEO_DIR/out"
SKILL="${SKILL:-$HOME/.claude/skills/personal-record-video/scripts}"
PIP_W="${PIP_W:-320}"
PIP_MARGIN="${PIP_MARGIN:-32}"
BEATS="${1:-}"

BODY_CLIPS=(body-1.mov body-2.mov body-3.mov body-4.mov body-5.mov)

probe() { ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$1"; }

CUT="$OUT/clips"
for f in face-open.mov face-close.mov "${BODY_CLIPS[@]}"; do
  [ -f "$CUT/$f" ] || { echo "ERROR: $CUT/$f not found. Run build-face-audio.py first."; exit 1; }
done
for f in narration.wav captions.srt body.wav body-timing.txt; do
  [ -f "$OUT/$f" ] || { echo "ERROR: $OUT/$f not found. Run build-face-audio.py first."; exit 1; }
done

if [ -n "$BEATS" ]; then
  VIDEO_DIR="$VIDEO_DIR" python3 "$SKILL/fit-to-audio.py" "$VIDEO_DIR/raw.mov" \
    --audio "$OUT/body.wav" --timing "$OUT/body-timing.txt" --beats "$BEATS"
fi
[ -f "$OUT/raw-fitted.mov" ] || { echo "ERROR: $OUT/raw-fitted.mov not found. Pass the --beats marks as \$1."; exit 1; }

BODY_DUR=$(probe "$OUT/body.wav")
printf 'body audio %.1f s   screencast %.1f s\n' "$BODY_DUR" "$(probe "$OUT/raw-fitted.mov")"

FIT="scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30"

INPUTS=(-i "$OUT/raw-fitted.mov" -i "$CUT/face-open.mov" -i "$CUT/face-close.mov")
GRAPH="[0:v]${FIT}[screen];"
i=3
PIPCHAIN=""
for clip in "${BODY_CLIPS[@]}"; do
  INPUTS+=(-i "$CUT/$clip")
  GRAPH+="[${i}:v]scale=${PIP_W}:-2,setsar=1,fps=30[p$i];"
  PIPCHAIN+="[p$i]"
  i=$((i + 1))
done
GRAPH+="${PIPCHAIN}concat=n=${#BODY_CLIPS[@]}:v=1:a=0,\
drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=3[pip];"
GRAPH+="[screen][pip]overlay=x=W-w-${PIP_MARGIN}:y=${PIP_MARGIN}:eof_action=pass,\
tpad=stop_mode=clone:stop_duration=2,trim=0:${BODY_DUR},setpts=PTS-STARTPTS[body];"
GRAPH+="[1:v]${FIT}[open];[2:v]${FIT}[close];"
GRAPH+="[open][body][close]concat=n=3:v=1:a=0[out]"

echo "compositing picture-in-picture and the three segments ..."
ffmpeg -y -v error -stats "${INPUTS[@]}" -filter_complex "$GRAPH" \
  -map "[out]" -an -c:v libx264 -preset veryfast -crf 16 -pix_fmt yuv420p "$OUT/full.mov"

printf '\nfull.mov %.1f s   narration.wav %.1f s\n\n' "$(probe "$OUT/full.mov")" "$(probe "$OUT/narration.wav")"

VIDEO_DIR="$VIDEO_DIR" MAX_SECONDS=300 NOFIT=1 bash "$SKILL/build-video.sh" "$OUT/full.mov"
