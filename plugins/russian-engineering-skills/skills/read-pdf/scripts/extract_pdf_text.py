from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def extract_text(pdf_path: Path) -> list[str]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - best effort helper
            text = f"[PAGE_EXTRACT_ERROR: {exc}]"
        pages.append(f"===== PAGE {i} =====\n{text}\n")
    return pages


def find_matches(lines: list[str], patterns: list[str]) -> list[str]:
    lowered = [p.lower() for p in patterns]
    matches: list[str] = []
    for idx, line in enumerate(lines, 1):
        hay = line.lower()
        if any(p in hay for p in lowered):
            matches.append(f"{idx}: {line}")
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a local PDF file.")
    parser.add_argument("pdf_path", help="Path to the source PDF file")
    parser.add_argument(
        "--output",
        help="Optional output text file path. Defaults to <pdf>.txt next to the PDF.",
    )
    parser.add_argument(
        "--find",
        action="append",
        default=[],
        help="Keyword to search in extracted text. Can be passed multiple times.",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).expanduser().resolve()
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else pdf_path.with_suffix(".txt")
    )

    pages = extract_text(pdf_path)
    output_path.write_text("\n".join(pages), encoding="utf-8")
    print(f"[OK] Extracted text to: {output_path}")

    if args.find:
        lines = output_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        matches = find_matches(lines, args.find)
        print(f"[INFO] Matches found: {len(matches)}")
        for item in matches[:200]:
            print(item)
        if len(matches) > 200:
            print("[INFO] Output truncated to 200 matches.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
