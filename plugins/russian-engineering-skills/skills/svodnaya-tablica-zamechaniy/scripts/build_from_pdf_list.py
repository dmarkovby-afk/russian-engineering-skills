# -*- coding: utf-8 -*-
"""Build a remarks summary workbook from an explicit list of expert-remark PDFs."""
from __future__ import annotations

import argparse
import json
import re
from copy import copy
from datetime import datetime
from pathlib import Path

import fitz
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from pypdf import PdfReader

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "template-summary-remarks.xlsx"
SERVICE_PHRASE = "Требуется внесение изменений или добавлений в документацию."


def layout_text(page: fitz.Page) -> str:
    words = page.get_text("words")
    if not words:
        return page.get_text("text") or ""
    words = sorted(words, key=lambda w: (round(w[1], 1), w[0]))
    lines = []
    current_y = None
    current = []
    last_x1 = None
    for x0, y0, x1, y1, word, *_ in words:
        ykey = round(y0, 1)
        if current_y is None or abs(ykey - current_y) > 2.5:
            if current:
                lines.append("".join(current).rstrip())
            current = [word]
            current_y = ykey
            last_x1 = x1
            continue
        gap = x0 - (last_x1 or x0)
        spaces = 1 if gap < 3 else max(1, int(round(gap / 3.2)))
        current.append(" " * spaces + word)
        last_x1 = x1
    if current:
        lines.append("".join(current).rstrip())
    return "\n".join(lines)


def extract_pdf(pdf_path: Path) -> tuple[str, str, str]:
    doc = fitz.open(pdf_path)
    layout_pages = []
    pymupdf_pages = []
    for i, page in enumerate(doc, 1):
        layout_pages.append(f"===== PAGE {i} =====\n{layout_text(page)}\n")
        pymupdf_pages.append(f"===== PAGE {i} =====\n{page.get_text('text') or ''}\n")
    doc.close()
    reader = PdfReader(str(pdf_path))
    pypdf_pages = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            text = f"[PAGE_EXTRACT_ERROR: {exc}]"
        pypdf_pages.append(f"===== PAGE {i} =====\n{text}\n")
    return "\n".join(layout_pages), "\n".join(pymupdf_pages), "\n".join(pypdf_pages)


def normalize(value: str) -> str:
    if value is None:
        return ""
    v = value.replace("\u0000", " ").replace("\r", " ").replace("\u00a0", " ")
    v = re.sub(r"[ \t]+\n", "\n", v)
    v = re.sub(r"\n[ \t]+", "\n", v)
    v = re.sub(r"===== PAGE \d+ =====", "\n", v)
    v = re.sub(r"([A-Za-zА-Яа-я0-9.])-\n([A-Za-zА-Яа-я0-9])", r"\1-\2", v)
    v = v.replace("\n", " ")
    v = re.sub(r"([A-ZА-Я0-9.])-\s+([A-Za-zА-Яа-я0-9])", r"\1-\2", v)
    v = re.sub(r"\s{2,}", " ", v)
    return v.strip()


def form_only(text: str) -> str:
    text = re.sub(r"===== PAGE \d+ =====\n?", "\n", text)
    return re.split(r"\nОбсуждение\n", text, maxsplit=1)[0]


def extract_discussion(text: str) -> str:
    text = re.sub(r"===== PAGE \d+ =====\n?", "\n", text)
    parts = re.split(r"\nОбсуждение\n", text, maxsplit=1)
    if len(parts) < 2:
        return ""
    disc = parts[1]
    pattern = re.compile(
        r"([^\n]+?→[^\n]+)\n(\d{2}\.\d{2}\.[0-9]{4}(?:\s+\d{2}:\d{2})?)\n"
    )
    matches = list(pattern.finditer(disc))
    if not matches:
        return normalize(disc)
    chunks = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(disc)
        body = normalize(disc[start:end])
        who = normalize(m.group(1))
        when = m.group(2)
        chunks.append(f"{who}, {when}: {body}" if body else f"{who}, {when}:")
    return "\n".join(chunks)


def regex_group(text: str, pattern: str) -> str:
    m = re.search(pattern, text, flags=re.S)
    return normalize(m.group(1)) if m else ""


def block_between(text: str, start_pat: str, end_pats: list[str]) -> str:
    s = re.search(start_pat, text, flags=re.S)
    if not s:
        return ""
    tail = text[s.end() :]
    end = len(tail)
    for ep in end_pats:
        m = re.search(ep, tail, flags=re.S)
        if m and m.start() < end:
            end = m.start()
    return normalize(tail[:end])


def interleaved(layout: str, start_pat: str, end_pat: str, remove_pats: list[str] | None = None) -> str:
    m = re.search(start_pat + r"(.*?)" + end_pat, layout, flags=re.S)
    if not m:
        return ""
    v = m.group(1)
    for rp in remove_pats or []:
        v = re.sub(rp, " ", v, flags=re.S)
    return normalize(v)


def section_from_name(stem: str) -> str:
    m = re.search(r"_Раздел\s+(.+?)_Пакет_", stem)
    if m:
        return normalize(re.sub(r"^Раздел\s+", "", m.group(1)))
    return ""


def or_none(v: str) -> str:
    return v if v else "Не указано"


def parse_texts(stem: str, layout: str, pymu: str, plain: str) -> dict:
    form_plain = form_only(plain)
    form_layout = form_only(layout)
    form_pymu = form_only(pymu)
    discussion = extract_discussion(plain) or extract_discussion(pymu)

    date_val = regex_group(form_plain, r"Замечание\s+от\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?)")
    if not date_val:
        date_val = regex_group(form_layout, r"от\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?)")

    direction = interleaved(form_layout, r"Направление\s+деятельности", r"эксперта\s*:")
    if not direction:
        direction = block_between(form_plain, r"эксперта\s*:\s*", [r"Тип\s+несоответствия"])

    conclusion = block_between(form_plain, r"Вывод\s+о\s+несоответствии\s*:", [r"Ссылка\s+на\s+материалы"])
    if not conclusion:
        conclusion = block_between(form_pymu, r"Вывод\s+о\s+несоответствии\s*:", [r"Ссылка\s+на\s+материалы"])

    norm = interleaved(
        form_layout,
        r"Ссылка\s+на\s+конкретное",
        r"экспертизы\s*:",
        [r"требование,\s*несоответствие", r"которому\s+было\s+выявлено\s+в\s+ходе"],
    )
    norm_plain = block_between(form_plain, r"экспертизы\s*:\s*", [r"Предложения\s+по\s+отработке"])
    if len(norm_plain) > len(norm):
        norm = norm_plain

    proposal_mid = interleaved(form_layout, r"Предложения\s+по\s+отработке", r"замечани[яй]\s*:")
    proposal_tail = block_between(
        form_plain,
        r"Предложения\s+по\s+отработке[\s\S]*?замечани[яй]\s*:",
        [r"Требуется внесение изменений", r"===== PAGE"],
    )
    if proposal_mid and proposal_tail:
        proposal = proposal_tail if proposal_tail.lower().startswith(proposal_mid.lower()) else normalize(proposal_mid + " " + proposal_tail)
    else:
        proposal = proposal_mid or proposal_tail
    proposal = re.sub(r"\s{2,}", " ", proposal.replace(SERVICE_PHRASE, "")).strip()

    return {
        "source": stem,
        "Дата": or_none(date_val),
        "Направление деятельности эксперта": or_none(direction),
        "Раздел": or_none(section_from_name(stem)),
        "Вывод о несоответствии": or_none(conclusion),
        "Ссылка на требования / нормативы": or_none(norm),
        "Предложения по отработке замечания": or_none(proposal),
        "Ответ исполнителя": discussion,
    }


def copy_row_style(ws, src_row: int, dst_row: int, cols: int = 8) -> None:
    ws.row_dimensions[dst_row].height = ws.row_dimensions[src_row].height
    for col in range(1, cols + 1):
        s = ws.cell(src_row, col)
        d = ws.cell(dst_row, col)
        if s.has_style:
            d.font = copy(s.font)
            d.border = copy(s.border)
            d.fill = copy(s.fill)
            d.number_format = s.number_format
            d.protection = copy(s.protection)
            d.alignment = copy(s.alignment)


def estimate_row_height(ws, row: int) -> float:
    max_lines = 1
    for col in range(1, 9):
        text = str(ws.cell(row, col).value or "")
        if not text:
            continue
        width = ws.column_dimensions[get_column_letter(col)].width or 10
        lines = 0
        for part in text.split("\n"):
            lines += max(1, int((len(part) / max(width * 0.95, 1)) + 0.999))
        max_lines = max(max_lines, lines)
    return min(409.0, max(22.0, 6 + max_lines * 15))


def apply_column_widths(ws) -> None:
    cfg = {1: (6, 8), 2: (16, 24), 3: (24, 56), 4: (10, 24), 5: (30, 95), 6: (26, 90), 7: (30, 95), 8: (30, 95)}
    end = ws.max_row
    for col, (min_w, max_w) in cfg.items():
        max_len = len(str(ws.cell(1, col).value or ""))
        for r in range(2, end + 1):
            for part in str(ws.cell(r, col).value or "").split("\n"):
                max_len = max(max_len, len(part))
        ws.column_dimensions[get_column_letter(col)].width = max(min_w, min(max_w, 2 + max_len * 0.9))


def save_workbook(rows: list[dict], out_path: Path) -> Path:
    if not TEMPLATE.is_file():
        raise SystemExit(f"Template not found: {TEMPLATE}")
    wb = load_workbook(TEMPLATE)
    keep = wb.sheetnames[0]
    for name in list(wb.sheetnames):
        if name != keep:
            del wb[name]
    ws = wb[keep]
    sample_row = 2
    needed = 1 + len(rows)
    while ws.max_row < needed:
        copy_row_style(ws, ws.max_row, ws.max_row + 1)
    for r in range(2, needed + 1):
        copy_row_style(ws, sample_row, r)
    for idx, item in enumerate(rows, start=1):
        r = idx + 1
        values = [
            idx,
            item["Дата"],
            item["Направление деятельности эксперта"],
            item["Раздел"],
            item["Вывод о несоответствии"],
            item["Ссылка на требования / нормативы"],
            item["Предложения по отработке замечания"],
            item["Ответ исполнителя"],
        ]
        for col, val in enumerate(values, start=1):
            cell = ws.cell(r, col)
            cell.value = val if val != "" else None
            cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
    if ws.max_row > needed:
        ws.delete_rows(needed + 1, ws.max_row - needed)
    apply_column_widths(ws)
    for r in range(2, needed + 1):
        ws.row_dimensions[r].height = estimate_row_height(ws, r)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:H{needed}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A3
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = "1:1"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    target = out_path
    try:
        with open(out_path, "a+b"):
            pass
        wb.save(out_path)
    except PermissionError:
        target = out_path.with_name(out_path.stem + " " + datetime.now().strftime("%H%M%S") + ".xlsx")
        wb.save(target)
    return target


def default_out_path(pdfs: list[Path]) -> Path:
    sections = []
    for pdf in pdfs:
        sec = section_from_name(pdf.stem)
        if sec and sec not in sections:
            sections.append(sec)
    label = " ".join(sections) if sections else "замечаний"
    stamp = datetime.now().strftime("%Y-%m-%d")
    return pdfs[0].parent / f"Сводная таблица замечаний {label} {stamp}.xlsx"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an 8-column remarks summary from listed PDFs.")
    parser.add_argument("pdfs", nargs="+", help="PDF files with expert remarks")
    parser.add_argument("--out", help="Output xlsx path")
    parser.add_argument("--no-discussion", action="store_true", help="Leave Ответ исполнителя empty")
    args = parser.parse_args()

    pdfs = [Path(p).expanduser().resolve() for p in args.pdfs]
    missing = [str(p) for p in pdfs if not p.is_file()]
    if missing:
        raise SystemExit("PDF not found:\n" + "\n".join(missing))

    rows = []
    for pdf in pdfs:
        layout, pymu, plain = extract_pdf(pdf)
        row = parse_texts(pdf.stem, layout, pymu, plain)
        if args.no_discussion:
            row["Ответ исполнителя"] = ""
        rows.append(row)
        print(f"OK {pdf.name} section={row['Раздел']} discussion={'yes' if row['Ответ исполнителя'] else 'no'}")

    out_path = Path(args.out).expanduser().resolve() if args.out else default_out_path(pdfs)
    saved = save_workbook(rows, out_path)
    sidecar = saved.with_suffix(".parsed.json")
    sidecar.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"SAVED {saved}")
    print(f"ROWS {len(rows)}")


if __name__ == "__main__":
    main()
