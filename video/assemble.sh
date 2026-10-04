#!/bin/bash
set -euo pipefail

[ -d /opt/homebrew/opt/ffmpeg@7/bin ] && PATH="/opt/homebrew/opt/ffmpeg@7/bin:$PATH"

VIDEO_DIR="${VIDEO_DIR:-$PWD/video}"
OUT="$VIDEO_DIR/out"
SKILL="${SKILL:-$HOME/.claude/skills/hackathon-record-video/scripts}"
PIP_W="${PIP_W:-300}"
PIP_MARGIN="${PIP_MARGIN:-24}"
PIP_POS="${PIP_POS:-tl}"
CLOSE_IMAGE="${CLOSE_IMAGE:-}"
RAW="${RAW:-$VIDEO_DIR/raw.mov}"
BEATS="${1:-}"

CLIPS=(face-open.mov body-1.mov body-2.mov body-3.mov body-4.mov body-5.mov face-close.mov)

probe() { ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$1"; }

CUT="$OUT/clips"
for f in "${CLIPS[@]}"; do
  [ -f "$CUT/$f" ] || { echo "ERROR: $CUT/$f not found. Run build-face-audio.py first."; exit 1; }
done
for f in narration.wav captions.srt timing.txt; do
  [ -f "$OUT/$f" ] || { echo "ERROR: $OUT/$f not found. Run build-face-audio.py first."; exit 1; }
done
[ -f "$OUT/hook.mov" ] || { echo "ERROR: $OUT/hook.mov not found. Run hook.py first."; exit 1; }

if [ -n "$BEATS" ]; then
  VIDEO_DIR="$VIDEO_DIR" python3 "$SKILL/fit-to-audio.py" "$RAW" \
    --audio "$OUT/narration.wav" --timing "$OUT/timing.txt" --beats "$BEATS"
fi
[ -f "$OUT/raw-fitted.mov" ] || { echo "ERROR: $OUT/raw-fitted.mov not found. Pass the --beats marks as \$1."; exit 1; }

HOOK_DUR=$(probe "$OUT/hook.mov")
BODY_DUR=$(probe "$OUT/raw-fitted.mov")
printf 'hook %.1f s   screencast %.1f s   narration %.1f s\n' \
  "$HOOK_DUR" "$BODY_DUR" "$(probe "$OUT/narration.wav")"

FIT="scale=1920:1080:force_original_aspect_ratio=decrease,\
pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30"

INPUTS=(-i "$OUT/raw-fitted.mov" -i "$OUT/hook.mov")
if [ -n "$CLOSE_IMAGE" ]; then
  CLOSE_AT=$(awk 'NR>1 {last=$2} END {print last}' "$OUT/timing.txt")
  CLOSE_LEN=$(awk "BEGIN {print $BODY_DUR - $CLOSE_AT}")
  INPUTS+=(-loop 1 -t "$CLOSE_LEN" -i "$CLOSE_IMAGE")
  GRAPH="[0:v]trim=0:${CLOSE_AT},setpts=PTS-STARTPTS,${FIT}[shot];[2:v]${FIT}[close];[shot][close]concat=n=2:v=1:a=0[screen];"
  i=3
else
  GRAPH="[0:v]${FIT}[screen];"
  i=2
fi
GRAPH+="[1:v]setsar=1,fps=30,format=yuv420p[hook];"
PIPCHAIN=""
for clip in "${CLIPS[@]}"; do
  INPUTS+=(-i "$CUT/$clip")
  GRAPH+="[${i}:v]crop='min(iw,ih)':'min(iw,ih)',scale=${PIP_W}:${PIP_W},setsar=1,fps=30[p$i];"
  PIPCHAIN+="[p$i]"
  i=$((i + 1))
done
GRAPH+="${PIPCHAIN}concat=n=${#CLIPS[@]}:v=1:a=0,\
drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=3[pip];"
case "$PIP_POS" in
  tl) PIP_X="${PIP_MARGIN}" ;;
  tr) PIP_X="W-w-${PIP_MARGIN}" ;;
  *)  echo "ERROR: PIP_POS must be tl or tr."; exit 1 ;;
esac
GRAPH+="[screen][pip]overlay=x=${PIP_X}:y=${PIP_MARGIN}:eof_action=pass,\
tpad=stop_mode=clone:stop_duration=2,trim=0:${BODY_DUR},setpts=PTS-STARTPTS[body];"
GRAPH+="[hook][body]concat=n=2:v=1:a=0[out]"

echo "compositing the hook, the screencast and the permanent box ..."
ffmpeg -y -v error -stats "${INPUTS[@]}" -filter_complex "$GRAPH" \
  -map "[out]" -an -c:v libx264 -preset veryfast -crf 16 -pix_fmt yuv420p "$OUT/full.mov"

printf '\nfull.mov %.1f s   narration.wav %.1f s\n\n' "$(probe "$OUT/full.mov")" "$(probe "$OUT/narration.wav")"

VIDEO_DIR="$VIDEO_DIR" MAX_SECONDS=300 NOFIT=1 bash "$SKILL/build-video.sh" "$OUT/full.mov"
