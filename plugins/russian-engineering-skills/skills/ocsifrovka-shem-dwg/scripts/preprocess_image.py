#!/usr/bin/env python3
"""Enhance a photo/scan of a drawing and write mm calibration + guide overlay."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sceneutil import PAPER_MM, infer_paper, paper_size, px_to_mm, save_json


def _order_corners(pts: np.ndarray) -> np.ndarray:
    pts = pts.reshape(4, 2).astype(np.float32)
    summed = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).ravel()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(summed)]
    ordered[2] = pts[np.argmax(summed)]
    ordered[1] = pts[np.argmin(diff)]
    ordered[3] = pts[np.argmax(diff)]
    return ordered


def _find_paper_quad(gray: np.ndarray) -> np.ndarray | None:
    h, w = gray.shape[:2]
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 40, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0.0
    min_area = 0.35 * w * h
    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4 or not cv2.isContourConvex(approx):
            continue
        area = abs(cv2.contourArea(approx))
        if area > best_area and area >= min_area:
            best = approx
            best_area = area
    if best is None:
        return None
    return _order_corners(best)


def _warp_to_paper(image: np.ndarray, quad: np.ndarray, width_mm: float, height_mm: float) -> np.ndarray:
    px_per_mm = 8.0
    out_w = max(int(round(width_mm * px_per_mm)), 800)
    out_h = max(int(round(height_mm * px_per_mm)), 600)
    dest = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(quad, dest)
    return cv2.warpPerspective(image, matrix, (out_w, out_h))


def _enhance(gray: np.ndarray) -> np.ndarray:
    blur = cv2.GaussianBlur(gray, (0, 0), 21)
    blur = np.maximum(blur, 1)
    flat = cv2.divide(gray, blur, scale=128)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    out = clahe.apply(flat)
    out = cv2.normalize(out, None, 0, 255, cv2.NORM_MINMAX)
    return out


def _draw_guide(gray: np.ndarray, width_mm: float, height_mm: float) -> np.ndarray:
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    h, w = gray.shape[:2]
    step = 20
    label_step = 40
    color = (40, 170, 255)
    font = cv2.FONT_HERSHEY_SIMPLEX
    for x_mm in range(0, int(width_mm) + 1, step):
        x = int(round(x_mm * w / width_mm))
        cv2.line(vis, (x, 0), (x, h - 1), color, 1, cv2.LINE_AA)
        if x_mm % label_step == 0:
            cv2.putText(vis, str(x_mm), (x + 3, 22), font, 0.5, (0, 90, 220), 1, cv2.LINE_AA)
    for y_mm in range(0, int(height_mm) + 1, step):
        y = int(round((height_mm - y_mm) * h / height_mm))
        cv2.line(vis, (0, y), (w - 1, y), color, 1, cv2.LINE_AA)
        if y_mm % label_step == 0:
            cv2.putText(vis, str(y_mm), (6, max(y - 4, 14)), font, 0.5, (0, 90, 220), 1, cv2.LINE_AA)
    return vis


def preprocess(source: Path, out_dir: Path, paper: str, orientation: str, no_warp: bool) -> dict:
    image = cv2.imdecode(np.fromfile(str(source), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {source}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    meta = {"paper": {"format": paper, "orientation": orientation}}
    width_mm, height_mm, fmt, orient = paper_size(meta)

    warped = False
    work_color = image
    if not no_warp:
        quad = _find_paper_quad(gray)
        if quad is not None:
            work_color = _warp_to_paper(image, quad, width_mm, height_mm)
            warped = True
    work_gray = cv2.cvtColor(work_color, cv2.COLOR_BGR2GRAY)
    enhanced = _enhance(work_gray)
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 8
    )
    guide = _draw_guide(enhanced, width_mm, height_mm)

    out_dir.mkdir(parents=True, exist_ok=True)
    work_path = out_dir / "source_work.png"
    bin_path = out_dir / "source_bin.png"
    guide_path = out_dir / "source_guide.png"
    def _imwrite(path: Path, image: np.ndarray) -> None:
        ok, buf = cv2.imencode(path.suffix, image)
        if not ok:
            raise RuntimeError(f"Cannot encode image: {path}")
        path.write_bytes(buf.tobytes())

    _imwrite(work_path, enhanced)
    _imwrite(bin_path, binary)
    _imwrite(guide_path, guide)

    h, w = enhanced.shape[:2]
    calib = {
        "source": str(source),
        "width_px": w,
        "height_px": h,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "format": fmt,
        "orientation": orient,
        "warped": warped,
        "origin": "bottom-left-mm",
        "image_origin": "top-left-px",
        "files": {
            "work": str(work_path),
            "binary": str(bin_path),
            "guide": str(guide_path),
        },
    }
    save_json(out_dir / "calib.json", calib)
    return calib


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a scheme photo for CAD reconstruction")
    parser.add_argument("source", nargs="?", help="Input JPG/PNG/TIF")
    parser.add_argument("--out-dir", help="Output folder for work images and calib.json")
    parser.add_argument("--paper", default="A3", help="A4/A3/A2/A1")
    parser.add_argument("--orientation", default="landscape", choices=("landscape", "portrait"))
    parser.add_argument("--no-warp", action="store_true", help="Do not try perspective crop")
    args = parser.parse_args()
    if not args.source or not args.out_dir:
        parser.error("source and --out-dir are required")
    source = Path(args.source)
    out_dir = Path(args.out_dir)
    paper = args.paper.upper()
    if paper not in PAPER_MM:
        raise SystemExit(f"Unknown paper: {paper}")
    calib = preprocess(source, out_dir, paper, args.orientation, args.no_warp)
    print(f"work={calib['files']['work']}")
    print(f"guide={calib['files']['guide']}")
    print(f"calib={out_dir / 'calib.json'}")
    print(f"paper={calib['format']} {calib['orientation']} {calib['width_mm']}x{calib['height_mm']} mm")
    print(f"warped={calib['warped']}")
    print("px_to_mm: x_mm = x_px * width_mm / width_px ; y_mm = height_mm - y_px * height_mm / height_px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
