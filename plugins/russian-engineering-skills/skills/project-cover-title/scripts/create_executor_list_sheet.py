#!/usr/bin/env python3
"""Create a Russian project executor-list sheet with frame and title block.

The script intentionally creates the framed sheet directly as PDF. For this
specific sheet type, DOCX footer tables are fragile: Word and LibreOffice may
reflow the right title-block cells differently during PDF export.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle


def register_fonts() -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\times.ttf")
    bold = Path(r"C:\Windows\Fonts\timesbd.ttf")
    if regular.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("TimesNewRoman", str(regular)))
        pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", str(bold)))
        return "TimesNewRoman", "TimesNewRoman-Bold"
    return "Helvetica", "Helvetica-Bold"


def centered(c: canvas.Canvas, text: str, x: float, y: float, w: float, font: str, size: float) -> None:
    c.setFont(font, size)
    c.drawCentredString(x + w / 2, y, text)


def draw_vertical(c: canvas.Canvas, text: str, x: float, y: float, font: str, size: float) -> None:
    c.saveState()
    c.translate(x, y)
    c.rotate(90)
    c.setFont(font, size)
    c.drawCentredString(0, 0, text)
    c.restoreState()


def build(output: Path, cipher: str, title: str, stage: str, org: str, date: str, people: list[tuple[str, str]]) -> None:
    regular, bold = register_fonts()
    output.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(output), pagesize=A4)
    width, height = A4
    left = 20 * mm
    right = width - 10 * mm
    bottom = 10 * mm
    top = height - 10 * mm

    c.setStrokeColor(colors.black)
    c.setLineWidth(1.2)
    c.rect(left, bottom, right - left, top - bottom)

    strip_x = 5 * mm
    strip_w = 15 * mm
    c.rect(strip_x, bottom, strip_w, 145 * mm)
    for y in [bottom + 26 * mm, bottom + 56 * mm, bottom + 86 * mm, bottom + 116 * mm]:
        c.line(strip_x, y, strip_x + strip_w, y)
    draw_vertical(c, "Инв. N подл.", strip_x + strip_w / 2, bottom + 18 * mm, regular, 8)
    draw_vertical(c, "Подп. и дата", strip_x + strip_w / 2, bottom + 48 * mm, regular, 8)
    draw_vertical(c, "Взам. инв. N", strip_x + strip_w / 2, bottom + 78 * mm, regular, 8)
    draw_vertical(c, "Согласовано", strip_x + strip_w / 2, bottom + 123 * mm, regular, 8)

    centered(c, "Список исполнителей", left, height - 42 * mm, right - left, bold, 14)
    style = ParagraphStyle("cell", fontName=bold, fontSize=12, leading=14, alignment=1)
    data = [
        [Paragraph("Должность", style), Paragraph("Подпись", style), Paragraph("Инициалы и фамилия", style)]
    ]
    for role, name in people:
        data.append([Paragraph(role, style), "", Paragraph(name, style)])

    table = Table(
        data,
        colWidths=[75 * mm, 35 * mm, 50 * mm],
        rowHeights=[14 * mm] + [18 * mm] * len(people),
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.8, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, left + 10 * mm, height - 126 * mm)

    stamp_h = 45 * mm
    sig_w = 70 * mm
    mid_w = 70 * mm
    right_w = (right - left) - sig_w - mid_w
    c.line(left, bottom + stamp_h, right, bottom + stamp_h)
    c.line(left + sig_w, bottom, left + sig_w, bottom + stamp_h)
    c.line(left + sig_w + mid_w, bottom, left + sig_w + mid_w, bottom + stamp_h)

    sig_cols = [12 * mm, 14 * mm, 14 * mm, 18 * mm, 12 * mm]
    x = left
    for col in sig_cols[:-1]:
        x += col
        c.line(x, bottom, x, bottom + stamp_h)
    for y in [bottom + 8 * mm, bottom + 16 * mm, bottom + 24 * mm, bottom + 32 * mm, bottom + 38 * mm]:
        c.line(left, y, left + sig_w, y)
    x = left
    for col, header in zip(sig_cols, ["Изм", "Колич", "Лист", "Подпись", "Дата"]):
        centered(c, header, x, bottom + 40 * mm, col, regular, 6)
        x += col

    stamp_rows = [("ГИП", people[0][1].split()[0] if people else "", date)]
    if len(people) > 1:
        stamp_rows.append(("Разраб", people[1][1], date))
    if len(people) > 2:
        stamp_rows.append(("Н. контр", people[-1][1], date))
    for n, row in enumerate(stamp_rows[:3]):
        y = bottom + (29 - 8 * n) * mm
        c.setFont(regular, 7)
        c.drawString(left + 1 * mm, y, row[0])
        c.drawString(left + 26 * mm, y, row[1])
        c.drawString(left + 58 * mm, y, row[2])

    centered(c, cipher, left + sig_w, bottom + 31 * mm, mid_w, bold, 12)
    centered(c, title, left + sig_w, bottom + 12 * mm, mid_w, regular, 10)

    r_x = left + sig_w + mid_w
    c.line(r_x, bottom + 25 * mm, right, bottom + 25 * mm)
    c.line(r_x, bottom + 14 * mm, right, bottom + 14 * mm)
    c.line(r_x + right_w / 3, bottom + 14 * mm, r_x + right_w / 3, bottom + 25 * mm)
    c.line(r_x + 2 * right_w / 3, bottom + 14 * mm, r_x + 2 * right_w / 3, bottom + 25 * mm)
    centered(c, "Стадия", r_x, bottom + 19 * mm, right_w / 3, regular, 9)
    centered(c, "Лист", r_x + right_w / 3, bottom + 19 * mm, right_w / 3, regular, 9)
    centered(c, "Листов", r_x + 2 * right_w / 3, bottom + 19 * mm, right_w / 3, regular, 9)
    centered(c, stage, r_x, bottom + 7 * mm, right_w / 3, bold, 11)
    centered(c, "1", r_x + right_w / 3, bottom + 7 * mm, right_w / 3, bold, 11)
    centered(c, "1", r_x + 2 * right_w / 3, bottom + 7 * mm, right_w / 3, bold, 11)
    centered(c, org, r_x, bottom + 2 * mm, right_w, regular, 10)

    c.showPage()
    c.save()


def parse_people(values: list[str]) -> list[tuple[str, str]]:
    people = []
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Bad --person value {value!r}. Use ROLE=NAME.")
        role, name = value.split("=", 1)
        people.append((role.strip(), name.strip()))
    return people


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cipher", required=True)
    parser.add_argument("--title", default="Список исполнителей")
    parser.add_argument("--stage", default="П")
    parser.add_argument("--org", default='ООО "ГазСнабПроект"')
    parser.add_argument("--date", default="30.10.25")
    parser.add_argument("--person", action="append", required=True, help="ROLE=NAME, repeat for each row")
    args = parser.parse_args()
    build(args.output, args.cipher, args.title, args.stage, args.org, args.date, parse_people(args.person))


if __name__ == "__main__":
    main()
