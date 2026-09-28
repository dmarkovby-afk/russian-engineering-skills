#!/usr/bin/env python3
"""Rasterize a DXF to PNG for overlay QA. Uses paper mm from calib.json when given."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import ezdxf
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sceneutil import load_json

ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")
ARIALI = Path(r"C:\Windows\Fonts\ariali.ttf")


def _calib_size(calib: dict, dpi: float) -> tuple[int, int, float, float]:
    width_mm = float(calib["width_mm"])
    height_mm = float(calib["height_mm"])
    if calib.get("width_px") and calib.get("height_px"):
        return int(calib["width_px"]), int(calib["height_px"]), width_mm, height_mm
    px_per_mm = dpi / 25.4
    return int(round(width_mm * px_per_mm)), int(round(height_mm * px_per_mm)), width_mm, height_mm


def _font(height_px: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(int(round(height_px)), 8)
    path = ARIAL if ARIAL.exists() else ARIALI
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _iter_entities(layout):
    for entity in layout:
        if entity.dxftype() == "INSERT":
            try:
                for child in entity.virtual_entities():
                    yield child
            except Exception:
                continue
        else:
            yield entity


def _to_px(x: float, y: float, width_mm: float, height_mm: float, w: int, h: int) -> tuple[int, int]:
    px = x / width_mm * (w - 1)
    py = (height_mm - y) / height_mm * (h - 1)
    return int(round(px)), int(round(py))


def _draw_entity(draw: ImageDraw.ImageDraw, entity, mapper, font_fn) -> None:
    kind = entity.dxftype()
    ink = (0, 0, 0)
    if kind == "LINE":
        draw.line([mapper(*entity.dxf.start.vec2), mapper(*entity.dxf.end.vec2)], fill=ink, width=1)
    elif kind in {"LWPOLYLINE", "POLYLINE"}:
        try:
            points = [mapper(p[0], p[1]) for p in entity.get_points("xy")]
        except Exception:
            if kind == "POLYLINE":
                points = [mapper(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            else:
                return
        if len(points) >= 2:
            if bool(getattr(entity, "closed", False)) or (hasattr(entity, "is_closed") and entity.is_closed):
                draw.polygon(points, outline=ink)
            else:
                draw.line(points, fill=ink, width=1)
    elif kind == "CIRCLE":
        cx, cy = mapper(*entity.dxf.center.vec2)
        r = abs(mapper(entity.dxf.center.x + entity.dxf.radius, entity.dxf.center.y)[0] - cx)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink)
    elif kind == "ARC":
        cx, cy, radius = entity.dxf.center.x, entity.dxf.center.y, entity.dxf.radius
        a1 = math.radians(entity.dxf.start_angle)
        a2 = math.radians(entity.dxf.end_angle)
        if a2 < a1:
            a2 += 2 * math.pi
        pts = []
        steps = max(8, int((a2 - a1) / math.radians(6)))
        for i in range(steps + 1):
            ang = a1 + (a2 - a1) * i / steps
            pts.append(mapper(cx + radius * math.cos(ang), cy + radius * math.sin(ang)))
        if len(pts) >= 2:
            draw.line(pts, fill=ink, width=1)
    elif kind in {"SOLID", "TRACE"}:
        pts = []
        for name in ("vtx0", "vtx1", "vtx2", "vtx3"):
            if hasattr(entity.dxf, name):
                loc = getattr(entity.dxf, name)
                pts.append(mapper(loc.x, loc.y))
        if len(pts) >= 3:
            draw.polygon(pts[:3] if pts[2] == pts[3] else pts, fill=ink)
    elif kind == "HATCH":
        try:
            for path in entity.paths:
                verts = []
                if hasattr(path, "vertices"):
                    verts = [mapper(v[0], v[1]) for v in path.vertices]
                if len(verts) >= 3:
                    draw.polygon(verts, outline=ink)
        except Exception:
            return
    elif kind in {"TEXT", "MTEXT"}:
        if kind == "MTEXT":
            text = entity.plain_text()
            height = float(entity.dxf.char_height)
            insert = entity.dxf.insert
            rotation = float(entity.dxf.rotation)
        else:
            text = entity.dxf.text
            height = float(entity.dxf.height)
            insert = entity.dxf.insert
            rotation = float(entity.dxf.rotation)
        x, y = mapper(insert.x, insert.y)
        px_h = abs(mapper(insert.x, insert.y)[1] - mapper(insert.x, insert.y + height)[1])
        font = font_fn(px_h)
        draw.text((x, y), text, font=font, fill=ink, anchor="ld")
        _ = rotation


def render(dxf_path: Path, png_path: Path, calib: dict | None, dpi: float) -> None:
    if calib:
        w, h, width_mm, height_mm = _calib_size(calib, dpi)
    else:
        width_mm, height_mm = 420.0, 297.0
        px_per_mm = dpi / 25.4
        w, h = int(round(width_mm * px_per_mm)), int(round(height_mm * px_per_mm))
    doc = ezdxf.readfile(dxf_path)
    image = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    def mapper(x, y):
        return _to_px(float(x), float(y), width_mm, height_mm, w, h)

    for entity in _iter_entities(doc.modelspace()):
        _draw_entity(draw, entity, mapper, _font)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render DXF preview PNG")
    parser.add_argument("dxf")
    parser.add_argument("png")
    parser.add_argument("--calib", help="work/calib.json from preprocess")
    parser.add_argument("--dpi", type=float, default=150.0)
    args = parser.parse_args()
    calib = load_json(args.calib) if args.calib else None
    render(Path(args.dxf), Path(args.png), calib, args.dpi)
    print(f"PNG={args.png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
