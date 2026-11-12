#!/usr/bin/env python3
"""Probe for #12: dump the per-pixel argmax class and water probability the
segment tool computes, so gating rules can be tried offline with regions.py.

Runs inside the segmentation container and reuses the shipped segment module
(class_scores, label_name, MODEL) rather than a copy of it.

    dump_scores.py IMAGES OUT

Writes OUT/<image name>.npz with best_class (uint8), water_prob (float16),
water_ids and other_ids.
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, "/usr/local/bin")
loader = importlib.machinery.SourceFileLoader("segment", "/usr/local/bin/segment")
spec = importlib.util.spec_from_loader("segment", loader)
segment = importlib.util.module_from_spec(spec)
loader.exec_module(segment)

from transformers import OneFormerForUniversalSegmentation, OneFormerProcessor

CLASSES = ["water", "sea", "river", "lake", "sky", "person", "boat"]

images_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
processor = OneFormerProcessor.from_pretrained(segment.MODEL)
model = OneFormerForUniversalSegmentation.from_pretrained(segment.MODEL).eval()
ids = sorted(i for i, label in model.config.id2label.items() if segment.label_name(label) in CLASSES)
water_ids = [i for i in ids if segment.label_name(model.config.id2label[i]) in segment.WATER_CLASSES]
other_ids = [i for i in ids if i not in water_ids]
for path in sorted(images_dir.glob("*.jpg")):
    image = Image.open(path).convert("RGB")
    inputs = processor(images=image, task_inputs=["semantic"], return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    best_class, water_prob = segment.class_scores(outputs, image.size[::-1], water_ids)
    np.savez_compressed(
        out / f"{path.name}.npz",
        best_class=best_class.astype(np.uint8),
        water_prob=water_prob.astype(np.float16),
        water_ids=np.array(water_ids),
        other_ids=np.array(other_ids),
    )
    print(path.name, flush=True)
