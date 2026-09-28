from __future__ import annotations

import hashlib
import sys
from pathlib import Path


EXPECTED = {
    "МЧРГ Боброво 76,7 м3ч II категория с приложением ТЗ подписи.docx":
        "8886656DCE6D1330570CDEBE15A857CD72D6B9938EE3DF772C6FFBC6AD8E8EAE",
    "Шаблон МЧРГ - 1 здание (пример Боброво).docx":
        "36086CBC83C39C2612094CA5C597FD6EE7894522F357A3DEB3DEBDBE850AF250",
    "Шаблон МЧРГ - несколько зданий.docx":
        "BB280237C279457A0C1EF71AEAFE07EC9F4949BBD8C9B8599DF4578DAE672DE5",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    templates = Path(__file__).resolve().parent.parent / "assets" / "templates"
    failed = False
    for name, expected in EXPECTED.items():
        path = templates / name
        if not path.is_file():
            print(f"[FAIL] отсутствует: {path}")
            failed = True
            continue
        actual = sha256(path)
        if actual != expected:
            print(f"[FAIL] изменен: {name}")
            print(f"  ожидается: {expected}")
            print(f"  фактически: {actual}")
            failed = True
            continue
        print(f"[OK] {name}: {actual}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
