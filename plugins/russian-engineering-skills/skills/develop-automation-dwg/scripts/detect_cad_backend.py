"""Detect installed AutoCAD/CAD backends without starting AutoCAD.

The script is intentionally diagnostic-only. It does not open drawings, modify
the registry, launch GUI processes, or change user configuration.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _which(name: str) -> str | None:
    value = shutil.which(name)
    return str(Path(value).resolve()) if value else None


def _registry_autocad() -> list[dict[str, str]]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []
    found: list[dict[str, str]] = []
    for hive in (winreg.HKEY_CLASSES_ROOT, winreg.HKEY_LOCAL_MACHINE):
        roots = ["AutoCAD.Application"] if hive == winreg.HKEY_CLASSES_ROOT else [
            r"SOFTWARE\Autodesk\AutoCAD",
            r"SOFTWARE\WOW6432Node\Autodesk\AutoCAD",
        ]
        for root in roots:
            try:
                with winreg.OpenKey(hive, root) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for index in range(count):
                        name = winreg.EnumKey(key, index)
                        if hive == winreg.HKEY_CLASSES_ROOT:
                            if not name.startswith("AutoCAD.Application"):
                                continue
                            try:
                                with winreg.OpenKey(key, name + r"\CurVer") as cur:
                                    version = str(winreg.QueryValue(cur, ""))
                            except OSError:
                                version = name
                            found.append({"progid": name, "version": version})
                        else:
                            found.append({"registry_path": root + "\\" + name})
            except OSError:
                continue
    unique = {(item.get("progid"), item.get("registry_path")): item for item in found}
    return list(unique.values())


def _candidate_files() -> list[dict[str, str]]:
    names = ("acad.exe", "acadlt.exe", "accoreconsole.exe")
    roots = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Autodesk",
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Autodesk",
    ]
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            for path in root.rglob(name):
                resolved = str(path.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    result.append({"name": name, "path": resolved})
    for name in names:
        path = _which(name)
        if path and path not in seen:
            seen.add(path)
            result.append({"name": name, "path": path})
    return result


def _python_capabilities() -> dict[str, object]:
    return {
        "available": True,
        "executable": sys.executable,
        "version": platform.python_version(),
        "pywin32": bool(importlib.util.find_spec("win32com")),
        "pythoncom": bool(importlib.util.find_spec("pythoncom")),
        "ezdxf": bool(importlib.util.find_spec("ezdxf")),
    }


def detect() -> dict[str, object]:
    files = _candidate_files()
    acad = [item for item in files if item["name"] in ("acad.exe", "acadlt.exe")]
    core = [item for item in files if item["name"] == "accoreconsole.exe"]
    com_registered = _registry_autocad()
    py = _python_capabilities()
    backends: list[dict[str, object]] = []
    if core:
        backends.append({"name": "core_console", "available": True, "headless": True,
                         "reason": "accoreconsole.exe найден"})
    if py["pywin32"] and com_registered:
        backends.append({"name": "com", "available": True, "headless": True,
                         "reason": "pywin32 и AutoCAD COM ProgID доступны"})
    if acad:
        backends.append({"name": "autocad_gui", "available": True, "headless": False,
                         "reason": "исполняемый AutoCAD/AutoCAD LT найден"})
    if py["ezdxf"]:
        backends.append({"name": "ezdxf", "available": True, "headless": True,
                         "reason": "ezdxf доступен; безопасен для DXF, но не является DWG backend"})
    return {
        "schema_version": 1,
        "platform": {"system": platform.system(), "release": platform.release()},
        "autocad": {
            "installed": bool(acad),
            "executables": acad,
            "core_console": core,
            "com_registered": com_registered,
            "version_hint": "2018" if any("2018" in x["path"] for x in files) else None,
        },
        "python": py,
        "autolisp": {"available": bool(core or acad), "execution": "through AutoCAD/Core Console"},
        "scr": {"available": bool(core or acad), "execution": "through AutoCAD/Core Console"},
        "backends": backends,
        "recommended_order": ["core_console", "com", "autolisp", "scr", "ezdxf", "autocad_gui"],
        "windows_cua": {"available": False, "reason": "исключён политикой DWG-навыка"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="write JSON to this path")
    args = parser.parse_args()
    data = detect()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
