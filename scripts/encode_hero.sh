#!/usr/bin/env bash
# Turn the hero loop rendered by blender/build_cinematic.py into the files the landing page uses.
#
#   python blender/build_cinematic.py --frames /tmp/hero --res 1600x900   # 240 PNG frames, 24 fps
#   python blender/build_cinematic.py --stills /tmp/hero-stills           # posters, 128 samples
#   scripts/encode_hero.sh /tmp/hero /tmp/hero-stills /tmp/hero-master
#
# Writes
#   frontend/assets/video/hero-loop.webm   VP9, two-pass constrained quality (Chrome, Firefox, Edge)
#   frontend/assets/video/hero-loop.mp4    H.264 High, fast start (Safari and everything else)
#   frontend/assets/img/bg-hero-desktop.webp / bg-hero-mobile.webp   the stills (first frame)
#   <master dir>/hero-loop-master.mp4      near-lossless H.264 master (CRF 12), not shipped
#
# No audio track. A keyframe every 2 s; the loop is seamless because the render is (every motion is
# a sine of the loop phase), so no cross-fade is added here.
set -euo pipefail
FRAMES=${1:?frames dir}
STILLS=${2:?stills dir}
MASTER=${3:-/tmp}
cd "$(dirname "$0")/.."
VID=frontend/assets/video
IMG=frontend/assets/img
mkdir -p "$VID" "$MASTER"
IN=(-hide_banner -loglevel error -y -framerate 24 -i "$FRAMES/f%04d.png")

ffmpeg "${IN[@]}" -an -c:v libx264 -preset slow -crf 12 -pix_fmt yuv420p "$MASTER/hero-loop-master.mp4"

ffmpeg "${IN[@]}" -an -c:v libx264 -profile:v high -level:v 4.0 -preset veryslow -tune film -crf 25 \
  -pix_fmt yuv420p -g 48 -keyint_min 48 -movflags +faststart "$VID/hero-loop.mp4"

LOG=$(mktemp -d)/vp9
ffmpeg "${IN[@]}" -an -c:v libvpx-vp9 -b:v 0 -crf 35 -pix_fmt yuv420p -g 48 -row-mt 1 -tile-columns 2 \
  -deadline good -cpu-used 4 -pass 1 -passlogfile "$LOG" -f null /dev/null
ffmpeg "${IN[@]}" -an -c:v libvpx-vp9 -b:v 0 -crf 35 -pix_fmt yuv420p -g 48 -row-mt 1 -tile-columns 2 \
  -deadline good -cpu-used 1 -auto-alt-ref 1 -lag-in-frames 25 -pass 2 -passlogfile "$LOG" "$VID/hero-loop.webm"

# posters: same sizes as the stills they replace (2400x1350 desktop, 828x1792 phone)
ffmpeg -hide_banner -loglevel error -y -i "$STILLS/hero-desktop.png" -c:v libwebp -quality 82 -compression_level 6 "$IMG/bg-hero-desktop.webp"
ffmpeg -hide_banner -loglevel error -y -i "$STILLS/hero-phone.png" -c:v libwebp -quality 80 -compression_level 6 "$IMG/bg-hero-mobile.webp"

ls -l "$VID" "$IMG"/bg-hero-*.webp "$MASTER/hero-loop-master.mp4"
