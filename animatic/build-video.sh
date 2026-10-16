#!/usr/bin/env bash
# Assemble the Fuzzlings animatic: PNG frame sequence + SFX cue sheet -> MP4.
#
#   ./build-video.sh [FRAMES_DIR] [OUT_MP4]
#
# Defaults: frames from /tmp/fz-frames, output ../media/animatic.mp4
# Requires: ffmpeg, python3. Frames come from render-frames.mjs, sounds from
# make-sfx.py (both must have run first).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMES="${1:-/tmp/fz-frames}"
OUT="${2:-$HERE/../media/animatic.mp4}"
FPS=20
SFX_DIR="$HERE/sfx"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$(dirname "$OUT")"

count=$(find "$FRAMES" -name '*.png' | wc -l)
echo "frames: $count  (expect 2400 for 120 s @ ${FPS}fps)"
[ "$count" -gt 2000 ] || { echo "too few frames; run render-frames.mjs first" >&2; exit 1; }

# ---- 1. audio: lay every cue on a 120 s bed -------------------------------
echo "building audio timeline..."
python3 "$HERE/mix-audio.py" --sfx "$SFX_DIR" --out "$WORK/audio.m4a"

# ---- 2. video: frame sequence -> H.264 -----------------------------------
echo "encoding video..."
ffmpeg -y -loglevel warning -framerate "$FPS" -i "$FRAMES/%05d.png" \
  -i "$WORK/audio.m4a" \
  -map 0:v -map 1:a \
  -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p \
  -vf "fps=25,format=yuv420p" \
  -profile:v high -level 4.0 -movflags +faststart \
  -c:a aac -b:a 128k -ar 44100 -ac 2 \
  -shortest "$OUT"

# ---- 3. poster frame -----------------------------------------------------
POSTER="$(dirname "$OUT")/animatic-poster.jpg"
ffmpeg -y -loglevel error -ss 57 -i "$OUT" -frames:v 1 -q:v 4 "$POSTER"

echo "---- ffprobe ----"
ffprobe -v error -show_entries format=duration,size,bit_rate \
  -show_entries stream=index,codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels \
  -of default=noprint_wrappers=1 "$OUT"
ls -l "$OUT" "$POSTER"
