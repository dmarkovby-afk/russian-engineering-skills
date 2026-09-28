from __future__ import annotations

import re
from pathlib import Path


CODEX_HOME = Path.home() / ".codex"
DOCS_CACHE = CODEX_HOME / "plugins" / "cache" / "openai-primary-runtime" / "documents"


def patch_renderer(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    if "from pathlib import Path" not in text:
        text = text.replace(
            "from os.path import abspath, basename, exists, expanduser, join, splitext\n",
            "from os.path import abspath, basename, exists, expanduser, join, splitext\n"
            "from pathlib import Path\n",
        )

    text = text.replace(
        "    python_root = os.path.dirname(os.path.dirname(sys.executable))\n",
        "    python_root = os.path.dirname(sys.executable)\n",
    )

    if 'runtime_bins.append(os.path.join(dependencies_root, "native", "poppler", "Library", "bin"))' not in text:
        text = text.replace(
            '            runtime_bins.append(os.path.join(dependencies_root, "bin", "override"))\n',
            '            runtime_bins.append(os.path.join(dependencies_root, "bin", "override"))\n'
            '            runtime_bins.append(os.path.join(dependencies_root, "native", "poppler", "Library", "bin"))\n',
        )
        text = text.replace(
            '            runtime_bins.append(os.path.join(current, "dependencies", "bin", "override"))\n',
            '            runtime_bins.append(os.path.join(current, "dependencies", "bin", "override"))\n'
            '            runtime_bins.append(os.path.join(current, "dependencies", "native", "poppler", "Library", "bin"))\n',
        )

    text = text.replace(
        '        os.environ["PATH"] = os.pathsep.join([runtime_bin, *remaining_path_entries])\n        return\n',
        '        path_entries = [runtime_bin, *remaining_path_entries]\n    os.environ["PATH"] = os.pathsep.join(path_entries)\n',
    )

    if "def _find_soffice()" not in text:
        marker = "\n\ndef calc_dpi_via_ooxml_docx"
        helper = '''

def _find_soffice() -> str:
    """Resolve LibreOffice explicitly on Windows when it is absent from PATH."""

    candidates = [shutil.which("soffice.com"), shutil.which("soffice")]
    if os.name == "nt":
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if root:
                candidates.append(str(Path(root) / "LibreOffice" / "program" / "soffice.com"))
                candidates.append(str(Path(root) / "LibreOffice" / "program" / "soffice.exe"))

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return "soffice"


def _lo_user_installation_uri(user_profile: str) -> str:
    """Return a LibreOffice-safe UserInstallation URI.

    On Windows, `file://` + `C:\\\\...` is invalid and LibreOffice may show a
    false dialog saying the installed `bootstrap.ini` is corrupt. `Path.as_uri`
    produces the required `file:///C:/...` form.
    """

    return Path(user_profile).resolve().as_uri()
'''
        text = text.replace(marker, helper + marker)

    if "user_installation = _lo_user_installation_uri(user_profile)" not in text:
        text = text.replace(
            "    env = _build_lo_env(user_profile)\n    logs: list[str] = []\n",
            "    env = _build_lo_env(user_profile)\n"
            "    soffice = _find_soffice()\n"
            "    user_installation = _lo_user_installation_uri(user_profile)\n"
            "    logs: list[str] = []\n",
        )

    text = text.replace('"soffice",\n        "-env:UserInstallation=file://" + user_profile,', 'soffice,\n        f"-env:UserInstallation={user_installation}",')
    text = text.replace('"soffice",\n            "-env:UserInstallation=file://" + user_profile,', 'soffice,\n            f"-env:UserInstallation={user_installation}",')

    if text != original:
        path.write_text(text, encoding="utf-8", newline="")
        return True
    return False


def main() -> None:
    patched = []
    for renderer in DOCS_CACHE.glob("*/skills/documents/render_docx.py"):
        if patch_renderer(renderer):
            patched.append(renderer)

    if patched:
        print("Patched renderers:")
        for item in patched:
            print(item)
    else:
        print("No renderer changes needed.")

    stale = []
    for renderer in DOCS_CACHE.glob("*/skills/documents/render_docx.py"):
        text = renderer.read_text(encoding="utf-8")
        if re.search(r"UserInstallation=file://\" \\+ user_profile|UserInstallation=file://\\\" \\+ user_profile", text):
            stale.append(renderer)
    if stale:
        raise SystemExit("Stale unsafe renderers remain: " + ", ".join(map(str, stale)))


if __name__ == "__main__":
    main()
