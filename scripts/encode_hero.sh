#!/usr/bin/env bash
# Turn the hero loop rendered by blender/build_cinematic.py into the files the landing page uses.
#
#   python blender/build_cinematic.py --frames /tmp/hero --res 1600x900 --step 3   # every 3rd of 240 frames
#   python blender/build_cinematic.py --stills /tmp/hero-stills           # posters, 128 samples
#   scripts/encode_hero.sh /tmp/hero /tmp/hero-stills /tmp/hero-master
#
# Writes
#   frontend/assets/video/hero-loop.webm   VP9, two-pass constrained quality (Chrome, Firefox, Edge)
#   frontend/assets/video/hero-loop.mp4    H.264 High, fast start (Safari and everything else)
#   frontend/assets/img/bg-hero-desktop.webp / bg-hero-mobile.webp   the stills (first frame)
#   <master dir>/hero-loop-master.mp4      near-lossless H.264 master (CRF 12), not shipped
#
# Only every STEP-th frame of the 24 fps loop is rendered (8 fps by default): the camera moves slowly
# and smoothly, so ffmpeg's motion-compensated interpolation makes the 60 fps film from them. Checked
# against real renders of the in-between frames: SSIM 0.98-0.99, PSNR 41-43 dB. Frame 0 is appended
# after the last key so the interpolation also bridges the loop point; that copy is dropped again.
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
STEP=${STEP:-3}
FPS=${FPS:-60}
LOOP_FRAMES=${LOOP_FRAMES:-240}          # rendered loop length at 24 fps
KEYS=$(mktemp -d)
n=0
for ((i = 0; i < LOOP_FRAMES; i += STEP)); do cp "$FRAMES/$(printf 'f%04d.png' $i)" "$KEYS/$(printf 'k%04d.png' $n)"; n=$((n + 1)); done
cp "$FRAMES/f0000.png" "$KEYS/$(printf 'k%04d.png' $n)"                      # the loop point
KFPS=$((24 / STEP))
OUTN=$((LOOP_FRAMES * FPS / 24))
# lossless intermediate at the final frame rate: keys -> interpolated, minus the repeated frame 0
MID="$KEYS/mid.mkv"
ffmpeg -hide_banner -loglevel error -y -framerate "$KFPS" -i "$KEYS/k%04d.png" \
  -vf "minterpolate=fps=$FPS:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1" -frames:v "$OUTN" \
  -c:v ffv1 -pix_fmt yuv444p "$MID"
IN=(-hide_banner -loglevel error -y -i "$MID")

ffmpeg "${IN[@]}" -an -c:v libx264 -preset slow -crf 12 -pix_fmt yuv420p "$MASTER/hero-loop-master.mp4"

ffmpeg "${IN[@]}" -an -c:v libx264 -profile:v high -level:v 4.2 -preset veryslow -tune film -crf 25 \
  -pix_fmt yuv420p -g $((FPS * 2)) -keyint_min $((FPS * 2)) -movflags +faststart "$VID/hero-loop.mp4"

LOG=$(mktemp -d)/vp9
ffmpeg "${IN[@]}" -an -c:v libvpx-vp9 -b:v 0 -crf 35 -pix_fmt yuv420p -g $((FPS * 2)) -row-mt 1 -tile-columns 2 \
  -deadline good -cpu-used 4 -pass 1 -passlogfile "$LOG" -f null /dev/null
ffmpeg "${IN[@]}" -an -c:v libvpx-vp9 -b:v 0 -crf 35 -pix_fmt yuv420p -g $((FPS * 2)) -row-mt 1 -tile-columns 2 \
  -deadline good -cpu-used 1 -auto-alt-ref 1 -lag-in-frames 25 -pass 2 -passlogfile "$LOG" "$VID/hero-loop.webm"

# posters: same sizes as the stills they replace (2400x1350 desktop, 828x1792 phone)
ffmpeg -hide_banner -loglevel error -y -i "$STILLS/hero-desktop.png" -c:v libwebp -quality 82 -compression_level 6 "$IMG/bg-hero-desktop.webp"
ffmpeg -hide_banner -loglevel error -y -i "$STILLS/hero-phone.png" -c:v libwebp -quality 80 -compression_level 6 "$IMG/bg-hero-mobile.webp"

ls -l "$VID" "$IMG"/bg-hero-*.webp "$MASTER/hero-loop-master.mp4"
