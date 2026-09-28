"""Extract a conservative, machine-readable drawing inventory.

DXF is inspected directly with ezdxf. DWG is deliberately not decoded by a
third-party parser: the script reports what is available and leaves the actual
DWG export to Core Console/COM so critical data is not silently lost.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path


def inspect_dxf(path: Path) -> dict[str, object]:
    import ezdxf

    doc = ezdxf.readfile(path)
    counts: collections.Counter[str] = collections.Counter()
    layers: collections.Counter[str] = collections.Counter()
    for entity in doc.modelspace():
        counts[entity.dxftype()] += 1
        layers[entity.dxf.get("layer", "0")] += 1
    layouts = []
    for layout in doc.layouts:
        layouts.append({"name": layout.name, "entity_count": len(layout)})
    return {
        "status": "ok",
        "format": "dxf",
        "path": str(path.resolve()),
        "version": doc.dxfversion,
        "units": doc.header.get("$INSUNITS"),
        "modelspace": {"entity_counts": dict(sorted(counts.items())),
                       "layer_counts": dict(sorted(layers.items()))},
        "layers": sorted(layer.dxf.name for layer in doc.layers),
        "blocks": sorted(block.name for block in doc.blocks),
        "layouts": layouts,
        "warnings": [],
    }


def inspect(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower()
    if not path.exists():
        return {"status": "error", "path": str(path), "error": "Файл не найден"}
    if suffix in {".dxf", ".dxfu"}:
        try:
            return inspect_dxf(path)
        except Exception as exc:
            return {"status": "error", "format": "dxf", "path": str(path),
                    "error": str(exc)}
    if suffix == ".dwg":
        return {
            "status": "requires_backend_export",
            "format": "dwg",
            "path": str(path.resolve()),
            "recommended_backend": "core_console_then_com",
            "available_data": {"file_size": path.stat().st_size},
            "warnings": [
                "DWG нельзя безопасно читать как DXF без проверки потери данных",
                "Для полного inventory нужен LISP/COM экспорт через AutoCAD backend",
            ],
        }
    return {"status": "error", "path": str(path),
            "error": f"Неподдерживаемое расширение: {suffix}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = inspect(args.drawing)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
