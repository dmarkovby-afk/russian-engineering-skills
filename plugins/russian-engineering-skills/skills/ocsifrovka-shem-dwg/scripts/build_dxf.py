#!/usr/bin/env python3
"""Build a native DXF from scene.json. No raster underlays."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import ezdxf
from ezdxf.enums import MTextEntityAlignment

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pid_symbols import ensure_symbol_block
from sceneutil import INSTR_TYPES, DEFAULT_LAYERS, as_xy, load_json, paper_size

LAYERS = [
    ("PIPES", 7, 35),
    ("FITTINGS", 7, 35),
    ("INSTR", 7, 25),
    ("TEXT", 7, 18),
    ("THIN", 7, 18),
    ("HATCH", 8, 18),
    ("FRAME", 7, 50),
    ("TITLE", 7, 35),
]

ALIGN = {
    ("left", "top"): MTextEntityAlignment.TOP_LEFT,
    ("center", "top"): MTextEntityAlignment.TOP_CENTER,
    ("right", "top"): MTextEntityAlignment.TOP_RIGHT,
    ("left", "middle"): MTextEntityAlignment.MIDDLE_LEFT,
    ("center", "middle"): MTextEntityAlignment.MIDDLE_CENTER,
    ("right", "middle"): MTextEntityAlignment.MIDDLE_RIGHT,
    ("left", "bottom"): MTextEntityAlignment.BOTTOM_LEFT,
    ("center", "bottom"): MTextEntityAlignment.BOTTOM_CENTER,
    ("right", "bottom"): MTextEntityAlignment.BOTTOM_RIGHT,
}

RASTER_TYPES = {"IMAGE", "WIPEOUT", "OLE2FRAME", "PDFUNDERLAY", "DGNUNDERLAY"}


def _lw(mm: float) -> int:
    return max(0, int(round(float(mm) * 100)))


def _layer_for(kind: str, item: dict) -> str:
    if item.get("layer"):
        return str(item["layer"])
    if kind == "symbols" and item.get("type") in INSTR_TYPES:
        return "INSTR"
    return DEFAULT_LAYERS[kind]


def _setup_doc():
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$MEASUREMENT"] = 1
    doc.header["$LWDISPLAY"] = 1
    if "GOST" not in doc.styles:
        doc.styles.new("GOST", dxfattribs={"font": "arial.ttf", "width": 0.8})
    for name, color, lineweight in LAYERS:
        if name in doc.layers:
            layer = doc.layers.get(name)
            layer.color = color
            layer.dxf.lineweight = lineweight
        else:
            doc.layers.add(name, color=color, lineweight=lineweight)
    return doc


def _add_pipe(msp, pipe: dict, default_width: float) -> None:
    points = [as_xy(pt, "pipe") for pt in pipe["points"]]
    width = float(pipe.get("width", default_width))
    layer = _layer_for("pipes", pipe)
    pline = msp.add_lwpolyline(points, dxfattribs={"layer": layer, "lineweight": _lw(width)})
    pline.dxf.const_width = 0


def _add_symbol(doc, msp, item: dict) -> None:
    kind = item["type"]
    pos = as_xy(item["pos"], "symbol")
    rotation = float(item.get("rotation", 0))
    scale = float(item.get("scale", 1))
    attrs = item.get("attrs") if isinstance(item.get("attrs"), dict) else {}
    name = ensure_symbol_block(doc, kind, attrs)
    layer = _layer_for("symbols", item)
    msp.add_blockref(
        name,
        pos,
        dxfattribs={
            "rotation": rotation,
            "xscale": scale,
            "yscale": scale,
            "layer": layer,
        },
    )


def _add_text(msp, item: dict, default_height: float) -> None:
    text = str(item.get("text") or "")
    pos = as_xy(item["pos"], "text")
    height = float(item.get("height", default_height))
    rotation = float(item.get("rotation", 0))
    layer = _layer_for("texts", item)
    align = ALIGN[(item.get("halign", "left"), item.get("valign", "bottom"))]
    mtext = msp.add_mtext(
        text,
        dxfattribs={
            "char_height": height,
            "style": "GOST",
            "layer": layer,
            "rotation": rotation,
            "lineweight": 18,
        },
    )
    mtext.set_location(pos, attachment_point=align)


def _add_arrow(msp, item: dict) -> None:
    x, y = as_xy(item["pos"], "arrow")
    rotation = math.radians(float(item.get("rotation", 0)))
    size = float(item.get("size", 3.0))
    layer = _layer_for("arrows", item)
    local = [(size, 0.0), (-size * 0.55, size * 0.32), (-size * 0.55, -size * 0.32)]
    pts = []
    cos_a, sin_a = math.cos(rotation), math.sin(rotation)
    for px, py in local:
        pts.append((x + px * cos_a - py * sin_a, y + px * sin_a + py * cos_a))
    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})
    msp.add_solid([pts[0], pts[1], pts[2], pts[2]], dxfattribs={"layer": layer})


def _add_hatch(msp, item: dict) -> None:
    points = [as_xy(pt, "hatch") for pt in item["points"]]
    layer = _layer_for("hatches", item)
    hatch = msp.add_hatch(color=7, dxfattribs={"layer": layer})
    hatch.set_pattern_fill(str(item.get("pattern") or "ANSI31"), scale=float(item.get("scale", 1.5)))
    hatch.paths.add_polyline_path(points, is_closed=True)


def _add_primitive(msp, item: dict) -> None:
    kind = item["kind"]
    layer = _layer_for("primitives", item)
    attribs = {"layer": layer}
    if kind == "line":
        msp.add_line(as_xy(item["p1"], "p1"), as_xy(item["p2"], "p2"), dxfattribs=attribs)
    elif kind == "rect":
        x1, y1 = as_xy(item["p1"], "p1")
        x2, y2 = as_xy(item["p2"], "p2")
        msp.add_lwpolyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
            close=True,
            dxfattribs=attribs,
        )
    elif kind == "circle":
        msp.add_circle(as_xy(item["center"], "center"), float(item["r"]), dxfattribs=attribs)
    elif kind == "arc":
        msp.add_arc(
            as_xy(item["center"], "center"),
            float(item["r"]),
            float(item["a1"]),
            float(item["a2"]),
            dxfattribs=attribs,
        )
    elif kind == "polyline":
        points = [as_xy(pt, "poly") for pt in item["points"]]
        msp.add_lwpolyline(points, close=bool(item.get("closed")), dxfattribs=attribs)
    else:
        raise ValueError(f"Unknown primitive kind: {kind}")


def build_dxf(scene: dict, out_path: Path) -> None:
    meta = scene.get("meta") or {}
    width, height, _fmt, _orient = paper_size(meta)
    default_width = float(meta.get("default_lineweight", 0.35))
    default_height = float(meta.get("text_height", 2.5))
    doc = _setup_doc()
    msp = doc.modelspace()
    if bool(meta.get("draw_frame", False)):
        msp.add_lwpolyline(
            [(0, 0), (width, 0), (width, height), (0, height)],
            close=True,
            dxfattribs={"layer": "FRAME", "lineweight": 50},
        )
    for pipe in scene.get("pipes") or []:
        _add_pipe(msp, pipe, default_width)
    for item in scene.get("symbols") or []:
        _add_symbol(doc, msp, item)
    for item in scene.get("texts") or []:
        _add_text(msp, item, default_height)
    for item in scene.get("leaders") or []:
        msp.add_line(
            as_xy(item["p1"], "leader p1"),
            as_xy(item["p2"], "leader p2"),
            dxfattribs={"layer": _layer_for("leaders", item), "lineweight": 18},
        )
    for item in scene.get("arrows") or []:
        _add_arrow(msp, item)
    for item in scene.get("hatches") or []:
        _add_hatch(msp, item)
    for item in scene.get("primitives") or []:
        _add_primitive(msp, item)
    for entity in msp:
        if entity.dxftype() in RASTER_TYPES:
            raise RuntimeError(f"Raster entity leaked into DXF: {entity.dxftype()}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build native DXF from scene.json")
    parser.add_argument("scene")
    parser.add_argument("dxf")
    args = parser.parse_args()
    scene = load_json(args.scene)
    out = Path(args.dxf)
    build_dxf(scene, out)
    print(f"DXF={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
