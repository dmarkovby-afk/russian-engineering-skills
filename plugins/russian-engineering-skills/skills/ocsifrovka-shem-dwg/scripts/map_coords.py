#!/usr/bin/env python3
"""Convert image pixel coordinates to CAD millimetres using calib.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sceneutil import load_json, px_to_mm


def parse_point(raw: str) -> tuple[float, float]:
    text = raw.replace(";", ",").strip()
    if "," in text:
        left, right = text.split(",", 1)
        return float(left), float(right)
    raise ValueError(f"Expected x,y got {raw!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Map photo pixels to scene.json millimetres")
    parser.add_argument("calib", help="work/calib.json")
    parser.add_argument("points", nargs="+", help="Pixel pairs x,y")
    args = parser.parse_args()
    calib = load_json(args.calib)
    for raw in args.points:
        x_px, y_px = parse_point(raw)
        x_mm, y_mm = px_to_mm(x_px, y_px, calib)
        print(f"{x_px:g},{y_px:g}px -> [{round(x_mm, 2)}, {round(y_mm, 2)}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
