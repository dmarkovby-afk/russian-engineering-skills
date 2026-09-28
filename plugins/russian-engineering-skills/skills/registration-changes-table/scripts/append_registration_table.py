#!/usr/bin/env python3
"""Append a filled Russian registration changes sheet to a PDF.

The template is a rendered sheet copied from the user's TBE example. This script
keeps that visual template and fills only the first registration row plus the
bottom designation/sheet cells.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


DPI = 300
SCALE = DPI / 72.0


def pt(value: float) -> int:
    return int(round(value * SCALE))


def u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def font(size_pt: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"
    return ImageFont.truetype(path, int(round(size_pt * SCALE)))


def draw_center(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    text: str,
    size: float = 6.5,
    bold: bool = False,
    spacing: float = 1.0,
) -> None:
    fnt = font(size, bold)
    x1, y1, x2, y2 = [pt(v) for v in box]
    lines = str(text).split("\n") if text else [""]
    line_height = int(size * SCALE * spacing)
    total_height = line_height * len(lines)
    y = y1 + (y2 - y1 - total_height) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=fnt)
        width = bbox[2] - bbox[0]
        x = x1 + (x2 - x1 - width) // 2
        draw.text((x, y), line, font=fnt, fill=(0, 0, 0))
        y += line_height


def fill_template(
    template: Path,
    image_out: Path,
    *,
    changed: str,
    replaced: str,
    new: str,
    annulled: str,
    total: str,
    doc_number: str,
    signature: str,
    date: str,
    designation: str,
    sheet: str,
) -> None:
    img = Image.open(template).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Exact table coordinates from the TBE registration sheet PDF.
    cols = [55.6, 113.0, 171.1, 229.1, 287.0, 345.0, 404.8, 463.9, 521.4, 581.4]
    row_y1, row_y2 = 116.1, 133.3
    values = ["1", changed, replaced, new, annulled, total, doc_number, signature, date]
    for i, value in enumerate(values):
        draw_center(
            draw,
            (cols[i], row_y1, cols[i + 1], row_y2),
            value,
            size=6.0 if i == 1 else 6.4,
            spacing=0.9,
        )

    # Bottom stamp cells: designation, "Лист", and sheet number.
    draw_center(draw, (241.3, 787.75, 553.1, 830.25), designation, size=12)
    draw_center(draw, (553.0, 787.75, 581.35, 807.6), u("\\u041b\\u0438\\u0441\\u0442"), size=6.5)
    draw_center(draw, (553.05, 807.6, 581.4, 830.3), sheet, size=8)
    img.save(image_out, dpi=(DPI, DPI))


def append_sheet(input_pdf: Path, output_pdf: Path, image_path: Path) -> None:
    doc = fitz.open(input_pdf)
    page_width, page_height = 595.3198852539062, 841.919921875
    page = doc.new_page(width=page_width, height=page_height)
    page.insert_image(fitz.Rect(0, 0, page_width, page_height), filename=str(image_path))
    doc.save(output_pdf, garbage=4, deflate=True)
    doc.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--template", type=Path, default=Path(__file__).resolve().parents[1] / "assets" / "registration-table-template.png")
    parser.add_argument("--changed", required=True, help="Changed sheets, e.g. 'ТЧ л.1,3,5;\\nГЧ л.3'")
    parser.add_argument("--replaced", default="-")
    parser.add_argument("--new", default="-")
    parser.add_argument("--annulled", default="-")
    parser.add_argument("--total", required=True)
    parser.add_argument("--doc-number", default="И1")
    parser.add_argument("--signature", default="")
    parser.add_argument("--date", required=True)
    parser.add_argument("--designation", required=True)
    parser.add_argument("--sheet", default="1")
    parser.add_argument("--image-out", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    image_out = args.image_out or args.output_pdf.with_suffix(".registration-table.png")
    fill_template(
        args.template,
        image_out,
        changed=args.changed,
        replaced=args.replaced,
        new=args.new,
        annulled=args.annulled,
        total=args.total,
        doc_number=args.doc_number,
        signature=args.signature,
        date=args.date,
        designation=args.designation,
        sheet=args.sheet,
    )
    append_sheet(args.input_pdf, args.output_pdf, image_out)


if __name__ == "__main__":
    main()
