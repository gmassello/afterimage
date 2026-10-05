#!/usr/bin/env bash
set -euo pipefail
B=http://127.0.0.1:8000; S="${1:-video/out/readme}"; ST=services/ui/static; A="${2:-demo-panel-b-$(openssl rand -hex 3)}"
mkdir -p "$S/frames"
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
shot(){ "$C" --headless=new --disable-gpu --hide-scrollbars --force-prefers-reduced-motion --force-device-scale-factor=2 --window-size=1250,753 --virtual-time-budget=${3:-6000} --user-data-dir=$S/prof-$1 --screenshot=$S/$1.png "$2" >/dev/null 2>&1 & local p=$!; for i in $(seq 1 40); do [ -s $S/$1.png ] && sleep 1 && break; sleep 0.5; done; kill $p 2>/dev/null || true; wait $p 2>/dev/null || true; }
post(){ curl -s -o /dev/null -w '%{redirect_url}' -F "asset_id=$1" -F "image=@$2;type=image/png" -H 'Accept: application/json' $B/inspections | sed 's|.*/traces/||'; }
run(){ curl -s -X POST -H 'Accept: application/json' $B/runs/$1/execute; echo; }
shot 01-landing "$B/?lang=en"
shot 02-app "$B/app?lang=en"
r1=$(post $A $ST/sample-b-baseline.png); run $r1; shot 03-baseline "$B/traces/$r1?lang=en"
r2=$(post $A $ST/sample-b-defect.png); run $r2 >/dev/null &
for i in $(seq 1 60); do curl -s $B/queue | grep -q $r2 && break; sleep 1; done
shot 05-approval "$B/traces/$r2?lang=en"
curl -s -o /dev/null -X POST -F from=trace $B/queue/$r2/approve
shot 06-history "$B/assets/$A?lang=en"
r3=$(post $A $ST/sample-b-blurred.png); run $r3; shot 07-recapture "$B/traces/$r3?lang=en"
r4=$(post $A $ST/sample-b-foreign.png); run $r4; shot 08-refused "$B/traces/$r4?lang=en"
echo "$r1 $r2 $r3 $r4"
i=1
for f in 01-landing 02-app 03-baseline 05-approval 06-history 07-recapture 08-refused; do
  ffmpeg -v error -y -i "$S/$f.png" -vf "scale=1000:-2:flags=lanczos,crop=1000:602:0:0" "$S/frames/$(printf %02d $i).png"
  i=$((i + 1))
done
ffmpeg -v error -y -i "$S/frames/%02d.png" -vf "palettegen=max_colors=160:stats_mode=diff" "$S/palette.png"
ffmpeg -v error -y -framerate 0.8 -i "$S/frames/%02d.png" -i "$S/palette.png" \
  -lavfi "[0:v][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" docs/img/demo.gif
ffmpeg -v error -y -i "$S/05-approval.png" -vf "scale=1400:-2:flags=lanczos" docs/img/trace.png
ffmpeg -v error -y -i "$S/06-history.png" -vf "crop=2500:1300:0:0,scale=1400:-2:flags=lanczos" docs/img/history.png
