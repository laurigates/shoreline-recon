#!/usr/bin/env bash
# Dump the segment tool's per-pixel argmax class and water probability for a set of frames,
# using the segmentation image pinned in configs/tools.toml (docker, CPU, ~4 s per frame).
#
#   probe.sh IMAGES_DIR OUT_DIR [FRAME...]
#
# IMAGES_DIR is a frames run's images/ directory; FRAME is a name without extension (00035).
# With no FRAME, every *.jpg is dumped. Writes OUT_DIR/<frame>.jpg.npz (see dump_scores.py).
# Run from the repository root.
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,9p' "$0" >&2; exit 2; }
images=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
shift 2
here=$(cd "$(dirname "$0")" && pwd)

image=$(grep -m1 -oE 'ghcr\.io/laurigates/shoreline-segmentation@sha256:[0-9a-f]{64}' configs/tools.toml || true)
[ -n "$image" ] || { echo "probe: no shoreline-segmentation pin in configs/tools.toml" >&2; exit 1; }

input=$images
if [ $# -gt 0 ]; then
  input=$(mktemp -d)
  trap 'rm -rf "$input"' EXIT
  for frame in "$@"; do cp "$images/$frame.jpg" "$input/"; done
fi

docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
  -v "$here:/probe:ro" -v "$input:/in:ro" -v "$out:/out" \
  "$image" python /probe/dump_scores.py /in /out
