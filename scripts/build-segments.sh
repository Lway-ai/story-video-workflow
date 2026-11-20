#!/bin/bash
# Build one 9 s segment per shot: trim to 9s, scale/pad to 704x1248, mix
# narration over ambient audio.
#
# Usage: ./build-segments.sh [shot-map.txt]
#   shot-map.txt: one line per shot: "<SHOT> <video file>" or "<SHOT> BLACK"
#   (produced by gen-subs.py). Missing shots (BLACK) become 9 s black video
#   with narration over silence — the slot is kept, never filled with other
#   footage.
#
# Layout (all relative to the project directory this script runs in):
#   <NARRATION_DIR>/NN-<SHOT>.wav   narration WAVs (from tts-narration.py)
#   <SEG_DIR>/<SHOT>.mp4            segment outputs
#
# Per-segment mix: source ambient audio x0.35 + narration delayed 200 ms.
# Sign text (OPTIONAL step, off by default): if SIGN_SHOT is set, that shot
# gets text composited onto a sign IN POST (drawtext from SIGN_TEXT_FILE).
# Measure the sign's position from an actual frame first (example: a blue
# sign spanning x 295-433, y 757-819 in a 704x1248 frame -> fontsize 16,
# x=316, y=768). Never let the video model draw the text.
set -u
cd "$(dirname "$0")/.."   # run from the project root; adjust if laid out otherwise

SHOT_MAP="${1:-shot-map.txt}"
NARRATION_DIR="${NARRATION_DIR:-narration}"
SEG_DIR="${SEG_DIR:-segments}"
FONT="${FONT:-/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc}"

# --- OPTIONAL sign-text compositing (leave empty to disable) ----------------
SIGN_SHOT="${SIGN_SHOT:-}"            # e.g. S804
SIGN_TEXT_FILE="${SIGN_TEXT_FILE:-}"   # e.g. sign-text.txt (one line per row)
SIGN_FONTSIZE="${SIGN_FONTSIZE:-16}"
SIGN_X="${SIGN_X:-316}"
SIGN_Y="${SIGN_Y:-768}"
# ----------------------------------------------------------------------------

mkdir -p "$SEG_DIR"
fail=0
i=0
while read -r id src; do
  i=$((i+1))
  nn=$(printf "%02d" $i)
  nar="$NARRATION_DIR/$nn-$id.wav"
  out="$SEG_DIR/$id.mp4"
  if [ -f "$out" ]; then echo "skip $id (exists)"; continue; fi
  if [ ! -f "$nar" ]; then echo "NO NARRATION: $id"; fail=$((fail+1)); continue; fi

  if [ "$src" = "BLACK" ]; then
    ffmpeg -y -nostdin -v error -f lavfi -i color=c=black:s=704x1248:r=24:d=9 \
      -f lavfi -i anullsrc=r=48000:cl=stereo -i "$nar" -filter_complex \
      "[0:v]setpts=PTS-STARTPTS[v];[1:a]atrim=0:9,asetpts=PTS-STARTPTS[a0];[2:a]adelay=200|200,apad[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]" \
      -map "[v]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 24 -c:a aac -b:a 128k -ar 48000 -ac 2 -t 9 "$out" \
      || { echo "SEG FAIL: $id"; fail=$((fail+1)); }
    echo "seg done $id (black)"
    continue
  fi

  vf="trim=0:9,setpts=PTS-STARTPTS,scale=704:1248:force_original_aspect_ratio=decrease:flags=lanczos,pad=704:1248:(ow-iw)/2:(oh-ih)/2,fps=24"
  if [ -n "$SIGN_SHOT" ] && [ "$id" = "$SIGN_SHOT" ]; then
    vf="$vf,drawtext=fontfile=$FONT:textfile=$SIGN_TEXT_FILE:fontsize=$SIGN_FONTSIZE:fontcolor=white:borderw=1:bordercolor=black@0.6:x=$SIGN_X:y=$SIGN_Y:line_spacing=4"
  fi
  ffmpeg -y -nostdin -v error -i "$src" -i "$nar" -filter_complex \
    "[0:v]$vf[v];[0:a]volume=0.35,atrim=0:9,asetpts=PTS-STARTPTS[a0];[1:a]adelay=200|200,apad[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]" \
    -map "[v]" -map "[aout]" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 24 -c:a aac -b:a 128k -ar 48000 -ac 2 -t 9 "$out" \
    || { echo "SEG FAIL: $id"; fail=$((fail+1)); }
  echo "seg done $id"
done < "$SHOT_MAP"
echo "SEGMENTS DONE, failures: $fail, files: $(ls "$SEG_DIR"/*.mp4 2>/dev/null | wc -l)"
