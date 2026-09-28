#!/usr/bin/env python3
"""Shared paper sizes, scene loading, and pixel-to-mm mapping."""

from __future__ import annotations

import json
from pathlib import Path

PAPER_MM = {
    "A4": (210.0, 297.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
}

KNOWN_SYMBOLS = {
    "valve_ball",
    "valve_gate",
    "valve_globe",
    "valve_check",
    "valve_thermal",
    "valve_safety",
    "filter_gas",
    "reducer",
    "flange",
    "cap",
    "regulator",
    "meter_gas",
    "vent",
    "manometer",
    "manometer_diff",
}

INSTR_TYPES = {"manometer", "manometer_diff"}

DEFAULT_LAYERS = {
    "pipes": "PIPES",
    "arrows": "PIPES",
    "symbols": "FITTINGS",
    "texts": "TEXT",
    "leaders": "THIN",
    "hatches": "HATCH",
    "primitives": "0",
}


def load_json(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def save_json(path: str | Path, data: dict) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def paper_size(meta: dict | None) -> tuple[float, float, str, str]:
    meta = meta or {}
    paper = meta.get("paper") or {}
    fmt = str(paper.get("format") or "A3").upper()
    orient = str(paper.get("orientation") or "landscape").lower()
    if fmt == "CUSTOM":
        width = float(paper["width_mm"])
        height = float(paper["height_mm"])
        return width, height, fmt, orient
    if fmt not in PAPER_MM:
        raise ValueError(f"Unknown paper format: {fmt}")
    short, long = sorted(PAPER_MM[fmt])
    # PAPER_MM stores landscape-ish pairs already for A3+; A4 is portrait native.
    native_w, native_h = PAPER_MM[fmt]
    if orient == "portrait":
        width, height = min(native_w, native_h), max(native_w, native_h)
        if fmt == "A4":
            width, height = 210.0, 297.0
        elif fmt == "A3":
            width, height = 297.0, 420.0
        elif fmt == "A2":
            width, height = 420.0, 594.0
        elif fmt == "A1":
            width, height = 594.0, 841.0
    else:
        width, height = max(native_w, native_h), min(native_w, native_h)
        if fmt == "A4":
            width, height = 297.0, 210.0
        elif fmt == "A3":
            width, height = 420.0, 297.0
        elif fmt == "A2":
            width, height = 594.0, 420.0
        elif fmt == "A1":
            width, height = 841.0, 594.0
    if paper.get("width_mm") and paper.get("height_mm"):
        width = float(paper["width_mm"])
        height = float(paper["height_mm"])
    return width, height, fmt, orient


def infer_paper(width_px: int, height_px: int) -> tuple[str, str]:
    ratio = width_px / max(height_px, 1)
    orient = "landscape" if ratio >= 1 else "portrait"
    return "A3", orient


def px_to_mm(x_px: float, y_px: float, calib: dict) -> tuple[float, float]:
    width_px = float(calib["width_px"])
    height_px = float(calib["height_px"])
    width_mm = float(calib["width_mm"])
    height_mm = float(calib["height_mm"])
    x_mm = x_px * width_mm / width_px
    y_mm = height_mm - y_px * height_mm / height_px
    return x_mm, y_mm


def mm_to_px(x_mm: float, y_mm: float, calib: dict) -> tuple[int, int]:
    width_px = float(calib["width_px"])
    height_px = float(calib["height_px"])
    width_mm = float(calib["width_mm"])
    height_mm = float(calib["height_mm"])
    x_px = x_mm * width_px / width_mm
    y_px = (height_mm - y_mm) * height_px / height_mm
    return int(round(x_px)), int(round(y_px))


def as_xy(value, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must be [x, y]")
    return float(value[0]), float(value[1])
