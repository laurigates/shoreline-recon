#!/usr/bin/env python3
"""Sweep --water-bridge and --water-seed-prob over probe dumps against hand labels.

    sweep.py DUMPS_DIR --water FRAME:X,Y [--water ...] [--base-bridge B] [--base-seed-prob S]
             [--bridges 0.02,0.03,...] [--seed-probs 0.7,0.6,...]

The regions under test are those the base thresholds drop (list them with
region_stats.py, same --bridge/--seed-prob). Each --water names one of them
that is real water, by frame and the centre region_stats.py printed
(00035:0.69,0.27); every other dropped region counts as ground. For each
parameter pair the script runs the shipped regions.grow and prints how many
water regions end up masked (want all) and how many ground regions (want
none). min_prob and min_area stay at 0.5 and 0.02.

Run from the repository root:

    uv run --no-project --with numpy --with scipy python .claude/skills/masks-gating/scripts/sweep.py DUMPS_DIR --water 00035:0.69,0.27
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, "containers/segmentation")
import regions  # noqa: E402  (the shipped gating, not a copy)


def floats(text: str) -> list[float]:
    return [float(x) for x in text.split(",")]


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("dumps", type=Path)
ap.add_argument("--water", action="append", default=[], metavar="FRAME:X,Y")
ap.add_argument("--base-bridge", type=float, default=0.02)
ap.add_argument("--base-seed-prob", type=float, default=0.7)
ap.add_argument("--bridges", type=floats, default=[0.02, 0.025, 0.03, 0.035, 0.04])
ap.add_argument("--seed-probs", type=floats, default=[0.7, 0.6, 0.55, 0.5, 0.45])
args = ap.parse_args()

water = set()
for label in args.water:
    frame, xy = label.split(":")
    x, y = xy.split(",")
    water.add((frame, round(float(x), 2), round(float(y), 2)))

frames, found = [], set()
for path in sorted(args.dumps.glob("*.npz")):
    d = np.load(path)
    best, prob = d["best_class"], d["water_prob"].astype(np.float32)
    h, w = best.shape
    cand = np.isin(best, list(d["water_ids"]))
    seed = regions.keep_connected(regions.gate_by_probability(cand, prob, 0.5), 0.02)
    kept = regions.grow(seed, cand, args.base_bridge * w, prob, args.base_seed_prob)
    labels, n = ndimage.label(regions.bridge(cand | seed, args.base_bridge * w))
    targets = []
    for i in range(1, n + 1):
        region = (labels == i) & cand
        if region.sum() / cand.size < 0.0005 or kept[region].any():
            continue
        ys, xs = np.nonzero(region)
        key = (path.name.split(".")[0], round(float(xs.mean() / w), 2), round(float(ys.mean() / h), 2))
        targets.append((key, region, key in water))
        found.add(key)
    frames.append((cand, seed, prob, w, targets))

missing = water - found
if missing:
    sys.exit(f"sweep: --water labels match no dropped region: {sorted(missing)}")

print("bridge seed_prob  water masked  ground masked  ground regions wrongly masked")
for bridge in args.bridges:
    for seed_prob in args.seed_probs:
        water_ok = water_n = ground_bad = ground_n = 0
        bad = []
        for cand, seed, prob, w, targets in frames:
            kept = regions.grow(seed, cand, bridge * w, prob, seed_prob)
            for key, region, is_water in targets:
                frac = kept[region].mean()
                if is_water:
                    water_n += 1
                    water_ok += frac > 0.9
                else:
                    ground_n += 1
                    if frac > 0.1:
                        ground_bad += 1
                        bad.append(f"{key[0]}:{key[1]},{key[2]}")
        print(f"{bridge:<6g} {seed_prob:<9g} {water_ok}/{water_n}           {ground_bad}/{ground_n}           {' '.join(bad)}")
