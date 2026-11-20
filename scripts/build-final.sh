#!/bin/bash
# Final assembly: concat segments, burn subtitles, mix BGM, fades,
# loudness to -14 LUFS / TP -1 dBTP, then a 540p delivery copy + 704p master.
#
# Usage: ./build-final.sh [shot-map.txt]
#
# Layout (relative to the project root this script runs in):
#   segments/<SHOT>.mp4   from build-segments.sh
#   subs.srt              from gen-subs.py
#   bgm.mp3               background music file (piano + strings in the example)
#
# Loudness chain (see docs/WORKFLOW.md stage 9.3):
#   1. measure the pre-loudness master with loudnorm (I=-14, TP=-1, LRA=11)
#   2. apply loudnorm dual-pass with measured params, targets I=-11.5 / TP=-2.2
#      (below target, leaving headroom for the limiter)
#   3. pure limiter: alimiter=limit=0.80:level=false
#      *** level=false is MANDATORY. The default level=true applies automatic
#      makeup gain (measured +1.79 LU in the example production) and pushes
#      the master OVER the target instead of limiting it. ***
#   4. verify by measuring the final file again; 540p is scaled from the
#      master with audio copied (-c:a copy), so its loudness is identical.
#
# NOTE: an earlier version of this script in the example production still
# contains the buggy `alimiter=limit=0.80` (no level=false) in its FIX1 step;
# the correction was applied in a separate pass. This generalized script
# already contains the fix — do not "simplify" it away.
set -u
cd "$(dirname "$0")/.."   # run from the project root; adjust if laid out otherwise

SHOT_MAP="${1:-shot-map.txt}"
SEG_DIR="${SEG_DIR:-segments}"
SUBS="${SUBS:-subs.srt}"
BGM="${BGM:-bgm.mp3}"
FONT_NAME="${FONT_NAME:-Noto Sans CJK SC}"
OUT_704="${OUT_704:-final-704p.mp4}"
OUT_540="${OUT_540:-final-540p.mp4}"
BGM_VOL="${BGM_VOL:-0.12}"
SHOT_SECONDS="${SHOT_SECONDS:-9}"

COUNT=$(wc -l < "$SHOT_MAP")
TOTAL=$(awk -v n="$COUNT" -v s="$SHOT_SECONDS" 'BEGIN { printf "%d", n * s }')
FADE_OUT_START=$(awk -v t="$TOTAL" 'BEGIN { printf "%.1f", t - 1.5 }')
BGM_FADE_START=$(awk -v t="$TOTAL" 'BEGIN { printf "%.1f", t - 5 }')
echo "shots: $COUNT  total: ${TOTAL}s  fade-out from: ${FADE_OUT_START}s"

> concat.txt
while read -r id src; do
  echo "file '$SEG_DIR/$id.mp4'" >> concat.txt
done < "$SHOT_MAP"
echo "concat list: $(wc -l < concat.txt) lines"

ffmpeg -y -nostdin -v error -f concat -safe 0 -i concat.txt -c copy \
  -video_track_timescale 24 final-nosubs.mp4 || { echo "CONCAT FAIL"; exit 1; }
echo "--- nosubs master ---"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 final-nosubs.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames,width,height,codec_name -of default=noprint_wrappers=1 final-nosubs.mp4

STYLE="FontName=$FONT_NAME,FontSize=22,PrimaryColour=&HFFFFFF,OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=30"
ffmpeg -y -nostdin -v error -stream_loop -1 -i "$BGM" -i final-nosubs.mp4 -filter_complex \
  "[1:v]subtitles=$SUBS:force_style='$STYLE'[vsub];[vsub]fade=t=in:st=0:d=1,fade=t=out:st=$FADE_OUT_START:d=1.5[v];[0:a]volume=$BGM_VOL,afade=t=in:st=0:d=2,afade=t=out:st=$BGM_FADE_START:d=5,atrim=0:$TOTAL,asetpts=PTS-STARTPTS[bgm];[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[amix];[amix]afade=t=in:st=0:d=1,afade=t=out:st=$FADE_OUT_START:d=1.5[aout]" \
  -map "[v]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -t "$TOTAL" final-preloud.mp4 \
  || { echo "BURN+FADES FAIL"; exit 1; }
echo "--- preloud master ---"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 final-preloud.mp4

echo "--- loudnorm measure ---"
ffmpeg -nostdin -i final-preloud.mp4 -vn -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null - 2> loudnorm-measure.txt
python3 - <<'PYEOF'
import json, re
txt = open('loudnorm-measure.txt', encoding='utf-8').read()
m = re.search(r'\{[^}]*"input_i"[^}]*\}', txt, re.S)
if not m:
    raise SystemExit('loudnorm JSON not found')
d = json.loads(m.group(0))
print('measured:', d)
open('loudnorm-params.txt', 'w').write(
    f"{d['input_i']} {d['input_tp']} {d['input_lra']} {d['input_thresh']} {d['target_offset']}")
PYEOF
set -- $(cat loudnorm-params.txt)
MI="$1"; MTP="$2"; MLRA="$3"; MTH="$4"; OFF="$5"

echo "--- loudnorm apply (I=-11.5 TP=-2.2) ---"
ffmpeg -y -nostdin -v error -i final-preloud.mp4 -map 0:v -map 0:a -filter:a \
  loudnorm=I=-11.5:TP=-2.2:LRA=11:measured_I=$MI:measured_TP=$MTP:measured_LRA=$MLRA:measured_thresh=$MTH:offset=$OFF:linear=true \
  -c:v copy -c:a aac -b:a 128k final-loud.mp4 || { echo "LOUDNORM FAIL"; exit 1; }

echo "--- limiter: alimiter 0.80 level=false (see header note) ---"
ffmpeg -y -nostdin -v error -i final-loud.mp4 -map 0:v -map 0:a -filter:a \
  alimiter=limit=0.80:level=false -c:v copy -c:a aac -b:a 128k "$OUT_704" \
  || { echo "LIMITER FAIL"; exit 1; }
echo "--- 704p master ---"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT_704"
ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames,width,height,codec_name -of default=noprint_wrappers=1 "$OUT_704"

echo "--- verify loudness of final ---"
ffmpeg -nostdin -i "$OUT_704" -vn -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null - 2> loudnorm-final.txt
grep -E '"input_i"|"input_tp"|"input_lra"' loudnorm-final.txt

ffmpeg -y -nostdin -v error -i "$OUT_704" -vf "scale=540:960:flags=lanczos" \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -c:a copy "$OUT_540" \
  || { echo "540P FAIL"; exit 1; }
echo "--- 540p delivery ---"
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1 "$OUT_540"
ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames,width,height,codec_name -of default=noprint_wrappers=1 "$OUT_540"
echo "FINAL BUILD DONE"
