#!/usr/bin/env python3
"""Per-region statistics of the argmax-water candidates in probe dumps.

    region_stats.py DUMPS_DIR [--min-prob P] [--min-area A] [--bridge B] [--seed-prob S]

For every DUMPS_DIR/*.npz (from probe.sh) prints one line per bridged candidate
region covering at least 0.05% of the image: area fraction, mean water
probability, share of pixels at or above --min-prob, centre (x,y as fractions),
whether the given thresholds keep it masked, and for a dropped region the gap:
the smallest pixel distance to the kept water, as a fraction of the image
width. The gap does not predict what a bridge joins (the disk closing reaches
about twice the bridge across straight edges, less at corners); use sweep.py
for that.

The thresholds default to the values this script was last used with; pass the
current [masks] values from configs/defaults.toml. Run from the repository
root with numpy and scipy:

    uv run --no-project --with numpy --with scipy python .claude/skills/masks-gating/scripts/region_stats.py DUMPS_DIR
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, "containers/segmentation")
import regions  # noqa: E402  (the shipped gating, not a copy)

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("dumps", type=Path)
ap.add_argument("--min-prob", type=float, default=0.5)
ap.add_argument("--min-area", type=float, default=0.02)
ap.add_argument("--bridge", type=float, default=0.03)
ap.add_argument("--seed-prob", type=float, default=0.6)
args = ap.parse_args()

for path in sorted(args.dumps.glob("*.npz")):
    d = np.load(path)
    best, prob = d["best_class"], d["water_prob"].astype(np.float32)
    h, w = best.shape
    cand = np.isin(best, list(d["water_ids"]))
    seed = regions.keep_connected(regions.gate_by_probability(cand, prob, args.min_prob), args.min_area)
    kept = regions.grow(seed, cand, args.bridge * w, prob, args.seed_prob)
    dist = ndimage.distance_transform_edt(~kept) if kept.any() else np.full(kept.shape, np.inf)
    labels, n = ndimage.label(regions.bridge(cand | seed, args.bridge * w))
    print(f"== {path.name.split('.')[0]}  candidates {cand.mean():.4f}  kept {kept.mean():.4f}")
    for i in range(1, n + 1):
        region = (labels == i) & cand
        area = region.sum() / cand.size
        if area < 0.0005:
            continue
        p = prob[region]
        ys, xs = np.nonzero(region)
        is_kept = bool(kept[region].any())
        gap = "" if is_kept else f"  gap {dist[region].min() / w:.3f}"
        print(
            f"   area {area:.4f}  mean {p.mean():.2f}  >={args.min_prob:g} {np.mean(p >= args.min_prob):.2f}"
            f"  centre {xs.mean() / w:.2f},{ys.mean() / h:.2f}  kept {is_kept}{gap}"
        )
