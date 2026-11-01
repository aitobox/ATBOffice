"""Windows Nuitka build and portable ZIP packaging script."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zipfile
from pathlib import Path

# Ensure repository root is in sys.path for direct script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.build.common import (  # noqa: E402
    ensure_clean_dir,
    get_artifact_name,
    get_base_nuitka_args,
    get_nuitka_env,
    get_project_root,
)


def run_nuitka_build(output_dir: Path) -> Path:
    """Run Nuitka to build the standalone Windows executable and distribution directory."""
    base_args = get_base_nuitka_args(output_dir)
    windows_args = [
        "--windows-console-mode=disable",
    ]
    cmd = base_args + windows_args
    env = get_nuitka_env()
    print(f"Running Nuitka Windows build:\n{' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)

    dist_dir = output_dir / "__main__.dist"
    if not dist_dir.exists():
        dist_dir = output_dir / "atboffice.dist"

    main_exe = dist_dir / "__main__.exe"
    atb_exe = dist_dir / "atboffice.exe"
    if main_exe.exists() and not atb_exe.exists():
        main_exe.rename(atb_exe)

    return dist_dir


def package_portable_zip(dist_dir: Path, zip_path: Path) -> Path:
    """Compress the standalone distribution folder into a portable zip archive."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    print(f"Archiving {dist_dir} into {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dist_dir):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(dist_dir)
                # Nest under ATBOffice/ folder inside zip using POSIX forward slashes
                arcname = (Path("ATBOffice") / rel_path).as_posix()
                zf.write(file_path, arcname=arcname)

    print(f"Successfully created portable ZIP archive: {zip_path}")
    return zip_path


def build_windows(
    output_dir: Path,
    version: str | None = None,
) -> Path:
    """Build standalone Windows distribution and package into portable .zip."""
    output_dir.mkdir(parents=True, exist_ok=True)
    nuitka_dir = output_dir / "nuitka_windows"
    ensure_clean_dir(nuitka_dir)

    dist_dir = run_nuitka_build(nuitka_dir)

    zip_name = get_artifact_name("windows", "x64", "zip", version=version)
    target_zip = output_dir / zip_name
    package_portable_zip(dist_dir, target_zip)

    return target_zip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Windows portable ZIP for ATBOffice.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=get_project_root() / "dist",
        help="Directory to place the final ZIP artifact.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string for the release artifact.",
    )

    args = parser.parse_args(argv)
    build_windows(
        output_dir=args.output_dir,
        version=args.version,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
