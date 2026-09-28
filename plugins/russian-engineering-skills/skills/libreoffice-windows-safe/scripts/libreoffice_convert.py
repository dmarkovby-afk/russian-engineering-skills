import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def find_soffice() -> str:
    candidates = [shutil.which("soffice.com"), shutil.which("soffice")]
    for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(env_name)
        if root:
            candidates.append(str(Path(root) / "LibreOffice" / "program" / "soffice.com"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError("LibreOffice soffice.com was not found")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a file with an isolated LibreOffice profile")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--format", default="pdf")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    source = args.input.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice()

    with tempfile.TemporaryDirectory(prefix="soffice_profile_") as profile:
        profile_uri = Path(profile).resolve().as_uri()
        command = [
            soffice,
            f"-env:UserInstallation={profile_uri}",
            "--headless",
            "--invisible",
            "--norestore",
            "--nodefault",
            "--nofirststartwizard",
            "--convert-to",
            args.format,
            "--outdir",
            str(output_dir),
            str(source),
        ]
        if args.verbose:
            print("CMD:", subprocess.list2cmdline(command))
            print("PROFILE_URI:", profile_uri)
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")

    if args.verbose or result.returncode != 0:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())

    extension = args.format.split(":", 1)[0].strip()
    expected = output_dir / f"{source.stem}.{extension}"
    if result.returncode != 0 or not expected.is_file() or expected.stat().st_size == 0:
        raise SystemExit(f"LibreOffice conversion failed (exit {result.returncode}); expected {expected}")
    print(expected)


if __name__ == "__main__":
    main()
