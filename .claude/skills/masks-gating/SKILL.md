---
name: masks-gating
description: Measure and tune the masks stage's water gating — dump the segment tool's class scores for chosen frames, list each water region's size and probability, sweep the bridge and seed thresholds against hand-labelled regions, and review before/after overlays for any frame. Use when water is left unmasked, ground is masked as water, a [masks] water_* default is questioned, or a new clip's masks look wrong.
allowed-tools: Bash, Read, Edit
created: 2026-11-12
modified: 2026-11-12
reviewed: 2026-11-12
---

# Water gating: measure before changing a threshold

The gating rules and their history are in ADR-0006 (`docs/adr/0006-masks-segmentation-container.md`);
the code is `containers/segmentation/regions.py`. This skill is the procedure and the scripts
(`.claude/skills/masks-gating/scripts/`) for checking a change against real frames. All commands
run from the repository root.

## Facts that shape the procedure

- **A threshold change needs no image rebuild.** The masks stage passes all four
  `--water-*` flags from `[masks]`, so editing `configs/defaults.toml` and running
  `target/release/shoreline-recon run configs/<dataset>.toml --stage masks --tools configs/tools.toml`
  tests it with the pinned image (docker, CPU, about 4 s per frame). A change to `regions.py`
  or `segment.py` logic does need a new image, which publishes only from `main`.
- **`segment.py` repeats the defaults** for standalone runs, and three more places pin them:
  `docs/kickoff.md`, the defaults test in `crates/core/src/config.rs`, and
  `segment_args_default_vector` in `crates/masks/src/lib.rs`. Change all of them together.
- **The stage's `overlays/` holds about 10 sampled frames.** Use `overlay.sh` for the others.
- **The gating only removes argmax-water pixels.** Water the model labels as another class
  cannot be masked by any threshold (#128).
- **A gap is not a bridge value.** `region_stats.py` prints the smallest pixel distance from a
  dropped region to the kept water. The disk closing joins straight edges up to about twice
  the bridge apart and corners only when closer, so pick a bridge from `sweep.py`.

## Procedure

1. **Find the frames.** Join two runs' `masks.csv` and sort by the change in masked fraction;
   a first gated run against an ungated one (`water_min_prob = 0`, `water_min_area = 0`) shows
   where the gating acts.
2. **Dump the scores** for those frames plus a few unaffected ones:

   ```sh
   .claude/skills/masks-gating/scripts/probe.sh work/<dataset>/frames/<tag>/images tmp/gating/<dataset> 00035 00040 00044
   ```

   Keep one dump directory per dataset: frame names repeat across datasets.
3. **List the regions** with the current thresholds:

   ```sh
   uv run --no-project --with numpy --with scipy python .claude/skills/masks-gating/scripts/region_stats.py tmp/gating/<dataset> --bridge 0.03 --seed-prob 0.6
   ```

4. **Label the dropped regions by eye.** Look at each one in the frame (crop the original;
   `overlay.sh` shows where it is) and note which are real water.
5. **Sweep**, passing the water regions by the centre `region_stats.py` printed:

   ```sh
   uv run --no-project --with numpy --with scipy python .claude/skills/masks-gating/scripts/sweep.py tmp/gating/<dataset> --base-bridge 0.03 --base-seed-prob 0.6 --water 00035:0.69,0.27
   ```

   A usable setting masks every water region and no ground region on **both** datasets, and
   sits inside a range that does, not at its edge.
6. **Re-run the masks stage on every dataset** with the candidate defaults, then join the new
   `masks.csv` with the previous run's. Check that the frames whose ground was released did
   not change, and review every frame that did:

   ```sh
   .claude/skills/masks-gating/scripts/overlay.sh work/<dataset>/frames/<tag>/images work/<dataset>/masks/<old>/masks work/<dataset>/masks/<new>/masks tmp/gating/overlays-<dataset> 00035 00053
   ```

   Red is masked, blue is newly masked, green is newly released.
7. **Record the measured ranges in ADR-0006**, with the frame count and the method, and say
   which frames were not reviewed.

## Checks

- `region_stats.py` and `sweep.py` import the shipped `regions.py`, and `dump_scores.py`
  imports the image's `segment` module. Do not copy the gating into a probe.
- `sweep.py` exits with an error when a `--water` label matches no dropped region; a silent
  mismatch would count that water as ground.
- The dumps are about 5 MB per frame. Keep them under `tmp/`, which is not committed.
