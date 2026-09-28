"""Run AutoCAD Core Console without bringing AutoCAD GUI to the foreground."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-console", required=True, type=Path)
    parser.add_argument("--drawing", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path, help=".scr or .lsp file")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    for path in (args.core_console, args.drawing, args.script):
        if not path.exists():
            raise SystemExit(f"Не найден файл: {path}")
    args.workdir.mkdir(parents=True, exist_ok=True)
    source = args.drawing.resolve()
    copy = args.workdir / source.name
    if source != copy:
        shutil.copy2(source, copy)
    log = args.workdir / f"core-console-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.log"
    # Core Console uses /i for the input drawing and /s for a command script.
    # The wrapper always points /i at the working copy, never at the source.
    command = [str(args.core_console), "/i", str(copy), "/s", str(args.script.resolve())]
    started = datetime.now(timezone.utc).isoformat()
    try:
        completed = subprocess.run(command, cwd=args.workdir, capture_output=True,
                                   text=True, timeout=args.timeout, check=False)
        status = "ok" if completed.returncode == 0 else "error"
    except subprocess.TimeoutExpired as exc:
        completed = exc
        status = "timeout"
    payload = {
        "status": status,
        "backend": "core_console",
        "command": command,
        "source": str(source),
        "working_copy": str(copy),
        "script": str(args.script.resolve()),
        "started_at": started,
        "returncode": getattr(completed, "returncode", None),
        "stdout": getattr(completed, "stdout", "") or "",
        "stderr": getattr(completed, "stderr", "") or "",
    }
    log.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
