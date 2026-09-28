#!/usr/bin/env python3
"""Replace names in PDF title-block stamps with small raster text overlays."""

from __future__ import annotations

import argparse
import base64
import io
import pathlib
import shutil
import sys
from dataclasses import dataclass

import fitz
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Operation:
    page_index: int
    old: str
    new: str
    rect: fitz.Rect
    size: float
    rotate: int


def parse_replacement(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("replacement must be OLD=NEW")
    old, new = value.split("=", 1)
    old = old.strip()
    new = new.strip()
    if not old or not new:
        raise argparse.ArgumentTypeError("replacement must contain non-empty OLD and NEW")
    return old, new


def make_text_png(text: str, font_path: pathlib.Path, point_size: float, rotate: int, scale: int) -> tuple[bytes, float, float]:
    pixel_size = max(1, int(round(point_size * scale)))
    font = ImageFont.truetype(str(font_path), pixel_size)
    probe = Image.new("RGBA", (10, 10), (255, 255, 255, 0))
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    pad = max(2, int(pixel_size * 0.18))

    image = Image.new("RGBA", (width + 2 * pad, height + 2 * pad), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=(0, 0, 0, 255))

    if rotate == 90:
        image = image.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    elif rotate == 270:
        image = image.rotate(270, expand=True, resample=Image.Resampling.BICUBIC)

    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue(), image.size[0] / scale, image.size[1] / scale


def span_style(page: fitz.Page, rect: fitz.Rect) -> tuple[float, int]:
    textdict = page.get_text("dict")
    probe = rect + (-3, -3, 3, 3)
    size = max(rect.height, 8.0)
    direction = (1.0, 0.0)

    for block in textdict["blocks"]:
        for line in block.get("lines", []):
            if not fitz.Rect(line["bbox"]).intersects(probe):
                continue
            for span in line.get("spans", []):
                if fitz.Rect(span["bbox"]).intersects(probe):
                    size = float(span.get("size", size))
                    direction = tuple(line.get("dir", direction))
                    break
            break
        else:
            continue
        break

    rotate = 0
    if abs(direction[1]) > abs(direction[0]):
        rotate = 270 if direction[1] > 0 else 90
    return size, rotate


def collect_operations(doc: fitz.Document, replacements: list[tuple[str, str]]) -> list[Operation]:
    operations: list[Operation] = []
    for page_index, page in enumerate(doc):
        for old, new in replacements:
            for rect in page.search_for(old):
                size, rotate = span_style(page, rect)
                operations.append(Operation(page_index, old, new, fitz.Rect(rect), size * 0.86, rotate))
    return operations


def apply_operations(doc: fitz.Document, operations: list[Operation], font_path: pathlib.Path, scale: int) -> None:
    by_page: dict[int, list[Operation]] = {}
    for op in operations:
        by_page.setdefault(op.page_index, []).append(op)

    for page_index, page_ops in by_page.items():
        page = doc[page_index]
        for op in page_ops:
            page.add_redact_annot(op.rect + (-0.5, -0.5, 0.5, 0.5), fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    for page_index, page_ops in by_page.items():
        page = doc[page_index]
        for op in page_ops:
            max_width = 48 if page.rect.width < 700 else 52
            max_height = op.rect.height * 0.92
            png, width, height = make_text_png(op.new, font_path, op.size, op.rotate, scale)
            if op.rotate == 0 and width > max_width:
                png, width, height = make_text_png(op.new, font_path, op.size * (max_width / width), op.rotate, scale)
            if op.rotate != 0 and height > max_width:
                png, width, height = make_text_png(op.new, font_path, op.size * (max_width / height), op.rotate, scale)
            if height > max_height and op.rotate == 0:
                png, width, height = make_text_png(op.new, font_path, op.size * (max_height / height), op.rotate, scale)
            if op.rotate == 0:
                target = fitz.Rect(op.rect.x0, op.rect.y0 - 2.1, op.rect.x0 + width, op.rect.y0 - 2.1 + height)
            elif op.rotate == 270:
                target = fitz.Rect(op.rect.x0 - 0.2, op.rect.y0, op.rect.x0 - 0.2 + width, op.rect.y0 + height)
            else:
                target = fitz.Rect(op.rect.x1 - width + 0.2, op.rect.y1 - height, op.rect.x1 + 0.2, op.rect.y1)
            page.insert_image(target, stream=png, keep_proportion=False, overlay=True)


def render_qa(doc: fitz.Document, operations: list[Operation], render_dir: pathlib.Path, zoom: float) -> None:
    render_dir.mkdir(parents=True, exist_ok=True)
    by_page: dict[int, list[Operation]] = {}
    for op in operations:
        by_page.setdefault(op.page_index, []).append(op)

    for page_index, page_ops in by_page.items():
        page = doc[page_index]
        clip = fitz.Rect(page_ops[0].rect)
        for op in page_ops[1:]:
            clip |= op.rect
        clip = (clip + (-90, -70, 180, 70)) & page.rect
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
        pix.save(render_dir / f"page_{page_index + 1}_stamp_after.png")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, help="PDF to edit")
    parser.add_argument("--replace", action="append", type=parse_replacement, required=True, help="Replacement as OLD=NEW")
    parser.add_argument("--output", help="Optional output PDF; default edits input in place")
    parser.add_argument("--backup-suffix", default=" - backup before stamp names", help="Suffix for in-place backup")
    parser.add_argument("--font", default=r"C:\Windows\Fonts\calibrii.ttf", help="TrueType/OpenType font for raster overlays")
    parser.add_argument("--scale", type=int, default=6, help="Raster overlay scale")
    parser.add_argument("--render-dir", help="Directory for QA PNG crops")
    parser.add_argument("--render-zoom", type=float, default=4.0, help="Zoom for QA PNG crops")
    args = parser.parse_args()

    pdf_path = pathlib.Path(args.pdf)
    output_path = pathlib.Path(args.output) if args.output else pdf_path
    font_path = pathlib.Path(args.font)

    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2
    if not font_path.exists():
        print(f"Font not found: {font_path}", file=sys.stderr)
        return 2

    if output_path == pdf_path:
        backup = pdf_path.with_name(pdf_path.stem + args.backup_suffix + pdf_path.suffix)
        if not backup.exists():
            shutil.copy2(pdf_path, backup)
            print(f"backup={backup}")
        else:
            print(f"backup_exists={backup}")

    doc = fitz.open(pdf_path)
    operations = collect_operations(doc, args.replace)
    if not operations:
        print("No matching names found; no changes written.", file=sys.stderr)
        return 1

    for op in operations:
        print(
            f"page={op.page_index + 1} old={op.old!r} new={op.new!r} "
            f"rect=({op.rect.x0:.1f},{op.rect.y0:.1f},{op.rect.x1:.1f},{op.rect.y1:.1f}) rotate={op.rotate}"
        )

    apply_operations(doc, operations, font_path, args.scale)

    temp_path = output_path.with_name(output_path.stem + ".__stamp_tmp__" + output_path.suffix)
    if temp_path.exists():
        temp_path.unlink()
    doc.save(temp_path, garbage=4, deflate=True, clean=True)
    doc.close()
    shutil.move(str(temp_path), str(output_path))

    verify = fitz.open(output_path)
    for old, _new in args.replace:
        count = sum(len(page.search_for(old)) for page in verify)
        print(f"remaining_old[{old}]={count}")
    if args.render_dir:
        render_qa(verify, operations, pathlib.Path(args.render_dir), args.render_zoom)
        print(f"render_dir={args.render_dir}")
    print(f"saved={output_path}")
    print(f"pages={verify.page_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
