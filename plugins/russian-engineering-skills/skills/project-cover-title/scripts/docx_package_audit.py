#!/usr/bin/env python
import argparse
import sys
from pathlib import Path
from zipfile import ZipFile


CRITICAL_PREFIXES = (
    "word/media/",
    "word/_rels/",
)

CRITICAL_SUBSTRINGS = (
    "header",
    "footer",
    "drawing",
    "vmlDrawing",
)


def list_parts(path: Path) -> set[str]:
    with ZipFile(path) as zf:
        return set(zf.namelist())


def critical(parts: set[str]) -> set[str]:
    selected = set()
    for name in parts:
        if any(name.startswith(prefix) for prefix in CRITICAL_PREFIXES):
            selected.add(name)
        elif name.startswith("word/") and any(token in name for token in CRITICAL_SUBSTRINGS):
            selected.add(name)
        elif name in {"[Content_Types].xml", "_rels/.rels"}:
            selected.add(name)
    return selected


def count_prefix(parts: set[str], prefix: str) -> int:
    return sum(1 for name in parts if name.startswith(prefix))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit DOCX package preservation after cover/title edits.")
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    template_parts = list_parts(args.template)
    output_parts = list_parts(args.output)

    missing = sorted(critical(template_parts) - output_parts)
    extra = sorted(critical(output_parts) - template_parts)

    print(f"Template parts: {len(template_parts)}")
    print(f"Output parts:   {len(output_parts)}")
    print(f"Template media: {count_prefix(template_parts, 'word/media/')}")
    print(f"Output media:   {count_prefix(output_parts, 'word/media/')}")
    print(f"Template rels:  {sum(1 for p in template_parts if p.endswith('.rels'))}")
    print(f"Output rels:    {sum(1 for p in output_parts if p.endswith('.rels'))}")

    if missing:
        print("\nMissing critical parts:")
        for name in missing:
            print(f"  - {name}")
    if extra:
        print("\nExtra critical parts:")
        for name in extra:
            print(f"  + {name}")

    if missing:
        print("\nFAIL: output is missing critical DOCX parts from the template.")
        return 1

    print("\nOK: no critical DOCX package parts are missing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
