"""Validate a DWG/DXF result without replacing the source file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def validate(path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "path": str(path.resolve()),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "extension": path.suffix.lower(),
        "sha256": None,
        "readable": False,
        "ezdxf_check": None,
        "warnings": [],
    }
    if not path.exists():
        result["warnings"].append("Файл результата отсутствует")
        return result
    if path.stat().st_size == 0:
        result["warnings"].append("Файл имеет нулевой размер")
        return result
    result["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result["readable"] = True
    if path.suffix.lower() in {".dxf", ".dxfu"}:
        try:
            import ezdxf
            doc = ezdxf.readfile(path)
            result["ezdxf_check"] = {"ok": True, "version": doc.dxfversion,
                                      "layouts": list(doc.layouts.names())}
        except Exception as exc:
            result["ezdxf_check"] = {"ok": False, "error": str(exc)}
            result["warnings"].append("DXF не прошёл проверку ezdxf")
    else:
        result["warnings"].append("Для DWG требуется повторное открытие через AutoCAD/Core Console")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("drawing", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate(args.drawing)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["exists"] and result["size_bytes"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
