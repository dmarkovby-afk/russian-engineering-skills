#!/usr/bin/env python3
"""Inspect a Russian estimate GGE/XML package for common completeness issues."""

from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def fix_text(value: str | None) -> str:
    if not value:
        return ""
    try:
        return value.encode("latin1").decode("utf-8")
    except Exception:
        return value


def schema(root: ET.Element) -> str:
    return root.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation", "")


def parse_gge(path: Path) -> tuple[ET.Element | None, str | None]:
    try:
        return ET.parse(path).getroot(), None
    except Exception as exc:
        return None, str(exc)


def norm_num(text: str) -> str:
    text = fix_text(text).strip()
    for prefix in ("ЛС ", "ЛСР ", "ВОР-"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.strip()


def inspect(root_dir: Path) -> int:
    files = sorted([p for p in root_dir.rglob("*") if p.is_file()])
    gge_files = [p for p in files if p.suffix.lower() in {".gge", ".xml"}]
    just_files = [p for p in files if p.suffix.lower() not in {".gge", ".xml"}]

    rows: list[dict[str, str]] = []
    local_estimates: dict[str, Path] = {}
    summary_refs: list[str] = []
    qtf_summaries: list[dict[str, str | int]] = []
    vor_summaries: list[dict[str, str | int]] = []
    schemas = Counter()

    for path in gge_files:
        root, err = parse_gge(path)
        if err or root is None:
            rows.append({"file": str(path), "schema": "PARSE_ERROR", "num": "", "name": err or ""})
            continue

        sc = schema(root)
        schemas[sc] += 1
        num = fix_text(root.findtext("Num"))
        name = fix_text(root.findtext("Name"))
        rows.append({"file": str(path), "schema": sc, "num": num, "name": name})

        if "LocalEstimate" in sc:
            local_estimates[norm_num(num)] = path
            qtf_items = 0
            qtf_full = 0
            qtf_files = Counter()
            for item in root.iter("Item"):
                qtf = item.find("QTF")
                if qtf is None:
                    continue
                qtf_items += 1
                file_name = fix_text(qtf.findtext("FileNameQTF")).strip()
                qtf_num = fix_text(qtf.findtext("NumQTF")).strip()
                if file_name and qtf_num:
                    qtf_full += 1
                    qtf_files[file_name] += 1
            qtf_summaries.append(
                {
                    "num": norm_num(num),
                    "file": path.name,
                    "items_with_qtf": qtf_items,
                    "filled_qtf": qtf_full,
                    "qtf_files": "; ".join(f"{k}:{v}" for k, v in qtf_files.items()),
                }
            )

        if "SummaryEstimate" in sc:
            for reason in root.iter("Reason"):
                text = norm_num(reason.text or "")
                if text and text[:2].isdigit() and "-" in text:
                    summary_refs.append(text)

        if "QuantityTakeoff" in sc:
            works = []
            for work in root.iter("Work"):
                n = fix_text(work.findtext("Num")).strip()
                if n:
                    works.append(n)
            unique = sorted(set(works), key=lambda x: int(x) if x.isdigit() else 999999)
            vor_summaries.append(
                {
                    "num": norm_num(num),
                    "file": path.name,
                    "works": len(works),
                    "first": unique[0] if unique else "",
                    "last": unique[-1] if unique else "",
                }
            )

    print("GGE/XML schemas:")
    for sc, count in schemas.most_common():
        print(f"  {count:>3}  {sc}")

    print("\nDocuments:")
    writer = csv.DictWriter(sys.stdout, fieldnames=["schema", "num", "name", "file"], delimiter="\t")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    print("\nSummary estimate references vs local estimates:")
    unique_refs = sorted(set(summary_refs))
    missing = [ref for ref in unique_refs if ref not in local_estimates]
    print("  References in SSR:", ", ".join(unique_refs) if unique_refs else "none found")
    print("  Local estimates present:", ", ".join(sorted(local_estimates)) if local_estimates else "none found")
    print("  Missing referenced LSR:", ", ".join(missing) if missing else "none")

    print("\nLSR QTF/VOR links:")
    for row in qtf_summaries:
        print(
            f"  {row['num']}: {row['filled_qtf']}/{row['items_with_qtf']} filled"
            f" | {row['qtf_files']} | {row['file']}"
        )

    print("\nVOR files:")
    for row in vor_summaries:
        print(f"  {row['num']}: works={row['works']} range={row['first']}..{row['last']} | {row['file']}")

    kac_like = [p for p in gge_files if any(token in p.name.lower() for token in ("ка", "kac", "kats", "конъюн"))]
    print("\nKAC / price justification quick check:")
    print(f"  KAC-like GGE/XML files: {len(kac_like)}")
    for path in kac_like:
        print(f"    {path}")
    print(f"  Non-GGE/XML justification-like files: {len(just_files)}")
    for path in just_files[:30]:
        print(f"    {path}")
    if len(just_files) > 30:
        print(f"    ... {len(just_files) - 30} more")

    return 1 if missing else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Folder containing GGE/XML estimate package")
    args = parser.parse_args()

    if not args.root.exists():
        print(f"Path does not exist: {args.root}", file=sys.stderr)
        return 2
    return inspect(args.root)


if __name__ == "__main__":
    raise SystemExit(main())
