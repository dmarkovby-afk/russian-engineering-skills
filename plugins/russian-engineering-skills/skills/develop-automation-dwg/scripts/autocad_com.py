"""Small, non-GUI-first AutoCAD COM helper.

COM is optional. The module never starts AutoCAD unless ``launch=True`` is
passed explicitly by the caller.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def connect(progid: str = "AutoCAD.Application", launch: bool = False) -> Any:
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("pywin32 не установлен; COM backend недоступен") from exc
    if not launch:
        try:
            return win32com.client.GetActiveObject(progid)
        except Exception as exc:
            raise RuntimeError(f"Запущенный COM-экземпляр не найден: {progid}") from exc
    app = win32com.client.Dispatch(progid)
    try:
        app.Visible = False
    except Exception:
        pass
    return app


def open_copy(app: Any, source: Path, destination: Path) -> Any:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())
    document = app.Documents.Open(str(destination.resolve()))
    return document


def close_document(document: Any, save: bool = True) -> None:
    document.Close(save)
