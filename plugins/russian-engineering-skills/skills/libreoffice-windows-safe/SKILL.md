---
name: libreoffice-windows-safe
description: Run and troubleshoot LibreOffice or soffice safely on Windows, especially for headless document conversion, DOCX rendering, PDF export, isolated user profiles, and false bootstrap.ini corruption errors. Use whenever Codex invokes LibreOffice on Windows directly or through a document-processing skill.
---

# Safe LibreOffice on Windows

Use a unique LibreOffice user profile for every headless process. Convert the absolute profile path to a file URI with `Path(profile).resolve().as_uri()`.

Never form `UserInstallation` by concatenating `file://` with a Windows path. `file://C:\\Users\\...` is invalid; LibreOffice requires `file:///C:/Users/...`. The invalid form can hang `soffice` and display a false error claiming `C:\\Program Files\\LibreOffice\\program\\bootstrap.ini` is corrupt.

Prefer `scripts/libreoffice_convert.py` for direct conversions. For DOCX visual QA, prefer the packaged documents skill's `render_docx.py`, which follows the same profile rule.

## Legacy Word templates and frames

LibreOffice is suitable for headless PDF/PNG verification, but it is not the
preferred authoring converter for old binary `.doc` templates containing
floating Word frames, VML shapes, title blocks, or legacy header/footer
objects. When Microsoft Word is installed, resave a working copy through Word
automation first and preserve that Word-native `.docx` as the editing base.
Use LibreOffice for a separate QA render; if frame geometry differs from the
original `.doc`, discard the LibreOffice-converted authoring copy and rebuild
from the native Word copy.

Resolve LibreOffice explicitly from `C:\\Program Files\\LibreOffice\\program\\soffice.com` or `ProgramFiles(x86)` when it is absent from `PATH`. Use `soffice.com` for captured headless diagnostics and `soffice.exe` only for interactive GUI launches.

Codex runtime updates may install a new `documents/<version>/skills/documents/render_docx.py` and reintroduce the old `file://` concatenation. Before using LibreOffice through the documents skill on Windows, inspect the active documents skill version. If needed, run `scripts/patch_documents_renderers.py` from this skill to patch all cached document renderers.

If the corruption dialog appears:

1. Record the hash and contents of the installed `bootstrap.ini`; do not edit it merely because the dialog names it.
2. Terminate only stale `soffice` processes created by the failed invocation.
3. Retry with a fresh profile and a valid URI.
4. Treat a non-empty expected output plus exit code 0 as success. LibreOffice may emit unrelated warnings on stderr.

Do not share a profile between concurrent conversions. Do not use the interactive user's default profile for automation.
