#!/usr/bin/env python3
"""GOST-like P&ID block builders for ezdxf."""

from __future__ import annotations

from ezdxf.layouts import BlockLayout


def _pline(block: BlockLayout, points, closed: bool = True, layer: str = "0") -> None:
    block.add_lwpolyline(points, close=closed, dxfattribs={"layer": layer})


def _line(block: BlockLayout, p1, p2, layer: str = "0") -> None:
    block.add_line(p1, p2, dxfattribs={"layer": layer})


def _circle(block: BlockLayout, center, radius: float, layer: str = "0") -> None:
    block.add_circle(center, radius, dxfattribs={"layer": layer})


def _size(attrs: dict, default: float = 8.0) -> float:
    return float(attrs.get("size", default))


def valve_ball(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 8.0)
    w, h = s * 0.55, s * 0.4
    _pline(block, [(-w, -h), (-w, h), (0, 0)])
    _pline(block, [(w, -h), (w, h), (0, 0)])


def valve_gate(block: BlockLayout, attrs: dict) -> None:
    valve_ball(block, attrs)
    s = _size(attrs, 8.0)
    _line(block, (0, 0), (0, s * 0.7))
    _line(block, (-s * 0.18, s * 0.7), (s * 0.18, s * 0.7))


def valve_globe(block: BlockLayout, attrs: dict) -> None:
    valve_ball(block, attrs)
    s = _size(attrs, 8.0)
    _circle(block, (0, 0), s * 0.12)


def valve_check(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 8.0)
    w, h = s * 0.5, s * 0.38
    _pline(block, [(-w, -h), (-w, h), (w, 0)])
    _line(block, (w, -h), (w, h))


def valve_thermal(block: BlockLayout, attrs: dict) -> None:
    valve_gate(block, attrs)
    s = _size(attrs, 8.0)
    y = s * 0.85
    _line(block, (-s * 0.22, y), (s * 0.22, y))
    _line(block, (0, s * 0.7), (0, y))


def valve_safety(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 8.0)
    _pline(block, [(-s * 0.45, 0), (s * 0.2, s * 0.35), (s * 0.2, -s * 0.35)])
    _line(block, (s * 0.2, 0), (s * 0.2, s * 0.9))
    _pline(block, [(s * 0.05, s * 0.9), (s * 0.35, s * 0.9), (s * 0.2, s * 1.2)])


def filter_gas(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 9.0)
    r = s * 0.5
    _pline(block, [(0, r), (r, 0), (0, -r), (-r, 0)])
    _line(block, (-r * 0.45, r * 0.45), (r * 0.45, -r * 0.45))
    _line(block, (-r * 0.45, -r * 0.45), (r * 0.45, r * 0.45))


def reducer(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 10.0)
    _pline(
        block,
        [(-s * 0.6, s * 0.28), (s * 0.6, s * 0.14), (s * 0.6, -s * 0.14), (-s * 0.6, -s * 0.28)],
        closed=True,
    )


def flange(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 6.0)
    gap = s * 0.08
    h = s * 0.35
    _line(block, (-gap, -h), (-gap, h))
    _line(block, (gap, -h), (gap, h))


def cap(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 6.0)
    _line(block, (0, -s * 0.35), (0, s * 0.35))
    _line(block, (0, s * 0.35), (s * 0.2, s * 0.2))
    _line(block, (0, -s * 0.35), (s * 0.2, -s * 0.2))


def regulator(block: BlockLayout, attrs: dict) -> None:
    valve_globe(block, attrs)
    s = _size(attrs, 10.0)
    _line(block, (0, s * 0.12), (0, s * 0.45))
    x0, y0, x1, y1 = -s * 0.28, s * 0.45, s * 0.28, s * 0.95
    _pline(block, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def meter_gas(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 12.0)
    _circle(block, (0, 0), s * 0.5)
    _circle(block, (0, 0), s * 0.32)
    _line(block, (-s * 0.5, 0), (s * 0.5, 0))


def vent(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 12.0)
    _line(block, (0, 0), (0, s))
    _pline(block, [(-s * 0.18, s), (s * 0.18, s), (0, s * 1.25)])
    box = s * 0.22
    _pline(block, [(-box, 0), (box, 0), (box, box * 1.4), (-box, box * 1.4)])
    _line(block, (-box, 0), (box, box * 1.4))
    _line(block, (-box, box * 0.45), (box, box * 0.95))


def manometer(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 7.0)
    stem = float(attrs.get("stem", s * 1.3))
    _line(block, (0, 0), (0, stem))
    _circle(block, (0, stem + s * 0.45), s * 0.45)
    _line(block, (0, stem + s * 0.45), (s * 0.22, stem + s * 0.7))


def manometer_diff(block: BlockLayout, attrs: dict) -> None:
    s = _size(attrs, 8.0)
    stem = float(attrs.get("stem", s * 1.1))
    _line(block, (-s * 0.25, 0), (-s * 0.25, stem * 0.4))
    _line(block, (s * 0.25, 0), (s * 0.25, stem * 0.4))
    _line(block, (-s * 0.25, stem * 0.4), (s * 0.25, stem * 0.4))
    _line(block, (0, stem * 0.4), (0, stem))
    _circle(block, (0, stem + s * 0.45), s * 0.45)


BUILDERS = {
    "valve_ball": valve_ball,
    "valve_gate": valve_gate,
    "valve_globe": valve_globe,
    "valve_check": valve_check,
    "valve_thermal": valve_thermal,
    "valve_safety": valve_safety,
    "filter_gas": filter_gas,
    "reducer": reducer,
    "flange": flange,
    "cap": cap,
    "regulator": regulator,
    "meter_gas": meter_gas,
    "vent": vent,
    "manometer": manometer,
    "manometer_diff": manometer_diff,
}


def _token(value) -> str:
    text = f"{float(value):g}".replace("-", "m").replace(".", "p")
    return text


def block_name(kind: str, attrs: dict | None) -> str:
    attrs = attrs or {}
    parts = [kind]
    if "size" in attrs:
        parts.append("s" + _token(attrs["size"]))
    if "stem" in attrs:
        parts.append("t" + _token(attrs["stem"]))
    return "_".join(parts)


def ensure_symbol_block(doc, kind: str, attrs: dict | None) -> str:
    if kind not in BUILDERS:
        raise KeyError(f"Unknown symbol type: {kind}")
    attrs = attrs or {}
    name = block_name(kind, attrs)
    if name not in doc.blocks:
        block = doc.blocks.new(name=name, base_point=(0, 0))
        BUILDERS[kind](block, attrs)
    return name


def ensure_blocks(doc) -> None:
    for name in BUILDERS:
        ensure_symbol_block(doc, name, {})
