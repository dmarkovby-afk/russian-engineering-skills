#!/usr/bin/env python3
"""Validate scene.json before DXF build."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sceneutil import (
    INSTR_TYPES,
    KNOWN_SYMBOLS,
    as_xy,
    load_json,
    paper_size,
)

PRIMITIVE_KINDS = {"line", "rect", "circle", "arc", "polyline"}


def _as_list(data: dict, key: str, required: bool) -> list:
    if key not in data:
        if required:
            raise ValueError(f"missing required array: {key}")
        return []
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"{key} must be an array")
    return value


def _in_paper(x: float, y: float, width: float, height: float, margin: float = 8.0) -> bool:
    return -margin <= x <= width + margin and -margin <= y <= height + margin


def validate(scene: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta = scene.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        meta = {}
    try:
        width, height, fmt, _orient = paper_size(meta)
    except Exception as exc:
        errors.append(f"paper: {exc}")
        width, height, fmt = 420.0, 297.0, "A3"

    for key in ("pipes", "symbols", "texts"):
        try:
            _as_list(scene, key, required=True)
        except ValueError as exc:
            errors.append(str(exc))

    pipes = scene.get("pipes") if isinstance(scene.get("pipes"), list) else []
    symbols = scene.get("symbols") if isinstance(scene.get("symbols"), list) else []
    texts = scene.get("texts") if isinstance(scene.get("texts"), list) else []
    leaders = scene.get("leaders") if isinstance(scene.get("leaders"), list) else []
    arrows = scene.get("arrows") if isinstance(scene.get("arrows"), list) else []
    hatches = scene.get("hatches") if isinstance(scene.get("hatches"), list) else []
    primitives = scene.get("primitives") if isinstance(scene.get("primitives"), list) else []
    unreadable = scene.get("unreadable") if isinstance(scene.get("unreadable"), list) else []

    ids: dict[str, str] = {}

    def take_id(item: dict, kind: str, index: int) -> None:
        ident = item.get("id")
        if ident is None or ident == "":
            return
        ident = str(ident)
        if ident in ids:
            errors.append(f"duplicate id {ident!r} ({ids[ident]} and {kind}[{index}])")
        else:
            ids[ident] = f"{kind}[{index}]"

    def check_xy(value, label: str) -> None:
        try:
            x, y = as_xy(value, label)
        except ValueError as exc:
            errors.append(str(exc))
            return
        if not _in_paper(x, y, width, height):
            warnings.append(f"{label} outside paper {fmt} {width:g}x{height:g} mm: [{x:g}, {y:g}]")

    for i, pipe in enumerate(pipes):
        if not isinstance(pipe, dict):
            errors.append(f"pipes[{i}] must be an object")
            continue
        take_id(pipe, "pipes", i)
        points = pipe.get("points")
        if not isinstance(points, list) or len(points) < 2:
            errors.append(f"pipes[{i}].points needs at least two points")
            continue
        for j, pt in enumerate(points):
            check_xy(pt, f"pipes[{i}].points[{j}]")

    for i, sym in enumerate(symbols):
        if not isinstance(sym, dict):
            errors.append(f"symbols[{i}] must be an object")
            continue
        take_id(sym, "symbols", i)
        kind = sym.get("type")
        if kind not in KNOWN_SYMBOLS:
            errors.append(f"symbols[{i}].type unknown: {kind!r}")
        if "pos" not in sym:
            errors.append(f"symbols[{i}] missing pos")
        else:
            check_xy(sym.get("pos"), f"symbols[{i}].pos")
        if kind in INSTR_TYPES and not sym.get("layer"):
            pass

    for i, text in enumerate(texts):
        if not isinstance(text, dict):
            errors.append(f"texts[{i}] must be an object")
            continue
        if not str(text.get("text") or "").strip():
            warnings.append(f"texts[{i}] is empty")
        if "pos" not in text:
            errors.append(f"texts[{i}] missing pos")
        else:
            check_xy(text.get("pos"), f"texts[{i}].pos")
        halign = text.get("halign", "left")
        valign = text.get("valign", "bottom")
        if halign not in ("left", "center", "right"):
            errors.append(f"texts[{i}].halign invalid: {halign!r}")
        if valign not in ("bottom", "middle", "top"):
            errors.append(f"texts[{i}].valign invalid: {valign!r}")

    for i, leader in enumerate(leaders):
        if not isinstance(leader, dict):
            errors.append(f"leaders[{i}] must be an object")
            continue
        check_xy(leader.get("p1"), f"leaders[{i}].p1")
        check_xy(leader.get("p2"), f"leaders[{i}].p2")

    for i, arrow in enumerate(arrows):
        if not isinstance(arrow, dict):
            errors.append(f"arrows[{i}] must be an object")
            continue
        check_xy(arrow.get("pos"), f"arrows[{i}].pos")

    for i, hatch in enumerate(hatches):
        if not isinstance(hatch, dict):
            errors.append(f"hatches[{i}] must be an object")
            continue
        points = hatch.get("points")
        if not isinstance(points, list) or len(points) < 3:
            errors.append(f"hatches[{i}].points needs at least three points")
            continue
        for j, pt in enumerate(points):
            check_xy(pt, f"hatches[{i}].points[{j}]")

    for i, prim in enumerate(primitives):
        if not isinstance(prim, dict):
            errors.append(f"primitives[{i}] must be an object")
            continue
        kind = prim.get("kind")
        if kind not in PRIMITIVE_KINDS:
            errors.append(f"primitives[{i}].kind unknown: {kind!r}")
            continue
        if kind in ("line", "rect"):
            check_xy(prim.get("p1"), f"primitives[{i}].p1")
            check_xy(prim.get("p2"), f"primitives[{i}].p2")
        elif kind in ("circle", "arc"):
            check_xy(prim.get("center"), f"primitives[{i}].center")
            if "r" not in prim:
                errors.append(f"primitives[{i}] missing r")
        elif kind == "polyline":
            points = prim.get("points")
            if not isinstance(points, list) or len(points) < 2:
                errors.append(f"primitives[{i}].points needs at least two points")
            else:
                for j, pt in enumerate(points):
                    check_xy(pt, f"primitives[{i}].points[{j}]")

    for i, item in enumerate(unreadable):
        if not isinstance(item, dict):
            errors.append(f"unreadable[{i}] must be an object")
            continue
        region = item.get("region")
        if not isinstance(region, list) or len(region) != 4:
            errors.append(f"unreadable[{i}].region must be [xmin, ymin, xmax, ymax]")
            continue
        try:
            xmin, ymin, xmax, ymax = (float(v) for v in region)
        except (TypeError, ValueError):
            errors.append(f"unreadable[{i}].region must be four numbers")
            continue
        check_xy([xmin, ymin], f"unreadable[{i}].region-min")
        check_xy([xmax, ymax], f"unreadable[{i}].region-max")
        if not str(item.get("note") or "").strip():
            warnings.append(f"unreadable[{i}] has no note")

    if unreadable:
        warnings.append(f"{len(unreadable)} unreadable region(s) must be listed in report.md")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scheme scene.json")
    parser.add_argument("scene")
    args = parser.parse_args()
    scene = load_json(args.scene)
    errors, warnings = validate(scene)
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"INVALID: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"OK: {args.scene} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
