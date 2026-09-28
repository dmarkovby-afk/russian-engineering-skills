#!/usr/bin/env python3
"""Overlay source raster vs DXF preview: red = source only, cyan = DXF only, dark = match."""

from __future__ import annotations

import argparse

import numpy as np
from PIL import Image


def overlay(source_path: str, preview_path: str, out_path: str) -> None:
    source = Image.open(source_path).convert("L")
    preview = Image.open(preview_path).convert("L")
    if preview.size != source.size:
        preview = preview.resize(source.size, Image.Resampling.BILINEAR)
    src = np.asarray(source, dtype=np.float32)
    prv = np.asarray(preview, dtype=np.float32)
    src_ink = np.clip((210.0 - src) / 210.0, 0.0, 1.0)
    prv_ink = np.clip((210.0 - prv) / 210.0, 0.0, 1.0)
    rgb = np.empty(src.shape + (3,), dtype=np.uint8)
    rgb[:, :, 0] = np.clip(255.0 * (1.0 - prv_ink), 0, 255).astype(np.uint8)
    rgb[:, :, 1] = np.clip(255.0 * (1.0 - src_ink), 0, 255).astype(np.uint8)
    rgb[:, :, 2] = np.clip(255.0 * (1.0 - src_ink), 0, 255).astype(np.uint8)
    Image.fromarray(rgb, mode="RGB").save(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Make red/cyan overlay of source vs DXF preview")
    parser.add_argument("source")
    parser.add_argument("preview")
    parser.add_argument("output")
    args = parser.parse_args()
    overlay(args.source, args.preview, args.output)
    print(f"OVERLAY={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
