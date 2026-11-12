#!/usr/bin/env bash
# Review overlays comparing a masks run with a reference run, for any frame
# (the stage's own overlays/ covers only a sample of frames).
#
#   overlay.sh IMAGES_DIR REF_MASKS_DIR NEW_MASKS_DIR OUT_DIR FRAME...
#
# IMAGES_DIR is the frames run's images/; the two masks dirs are masks runs' masks/
# (COLMAP masks: black = ignored). FRAME is a name without extension (00035).
# Writes OUT_DIR/<frame>.jpg, 1000 px wide:
#   red   = masked by the new run
#   blue  = masked by the new run but not by the reference (added)
#   green = masked by the reference but not by the new run (released)
# Needs ImageMagick 7 (magick).
set -euo pipefail
[ $# -ge 5 ] || { sed -n '2,13p' "$0" >&2; exit 2; }
images=$1 ref=$2 new=$3 out=$4
shift 4
mkdir -p "$out"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# tint <paint-mask: white = paint> <colour> <base> <out>
tint() {
  local size
  size=$(magick identify -format '%wx%h' "$3")
  magick "$3" \( -size "$size" "xc:$2" \) \( "$1" -evaluate multiply 0.5 \) -composite "$4"
}

for frame in "$@"; do
  img="$images/$frame.jpg"
  m_ref="$ref/$frame.jpg.png"
  m_new="$new/$frame.jpg.png"
  magick "$m_new" -negate "$tmp/masked_new.png"
  magick "$m_ref" "$tmp/masked_new.png" -compose multiply -composite "$tmp/added.png"
  magick \( "$m_ref" -negate \) "$m_new" -compose multiply -composite "$tmp/released.png"
  tint "$tmp/masked_new.png" red "$img" "$tmp/a.png"
  tint "$tmp/added.png" blue "$tmp/a.png" "$tmp/b.png"
  tint "$tmp/released.png" lime "$tmp/b.png" "$tmp/c.png"
  magick "$tmp/c.png" -resize 1000x -quality 85 "$out/$frame.jpg"
  echo "$out/$frame.jpg"
done
