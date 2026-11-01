"""Linux Nuitka build and AppImage packaging script."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import urllib.request
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

# Minimal 1x1 or transparent valid PNG as fallback icon
DEFAULT_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 \x08\x06"
    b"\x00\x00\x00szz\xf4\x00\x00\x00\x19tEXtSoftware\x00Adobe ImageReadyq"
    b"\xc9e<\x00\x00\x00\x1fIDATx\xdabb\xf8\xcf\xc0\xc0\xc0\x0f\xc4\x10\x10"
    b"\x10\x02\xa4\x18\x90\x00\x00j\x01\x01\x01\xa8f\x80\xb2\x00\x00\x00\x00IEND\xaeB`\x82"
)


def run_nuitka_build(output_dir: Path) -> Path:
    """Run Nuitka to build the standalone Linux binary and distribution directory."""
    base_args = get_base_nuitka_args(output_dir)
    env = get_nuitka_env()
    print(f"Running Nuitka Linux build:\n{' '.join(base_args)}")
    subprocess.run(base_args, check=True, env=env)

    dist_dir = output_dir / "__main__.dist"
    if not dist_dir.exists():
        dist_dir = output_dir / "atboffice.dist"
    return dist_dir


def prepare_appdir(dist_dir: Path, appdir: Path) -> Path:
    """Assemble the AppDir structure according to AppImage specifications."""
    ensure_clean_dir(appdir)

    usr_bin = appdir / "usr" / "bin"
    usr_bin.mkdir(parents=True, exist_ok=True)

    if dist_dir.is_dir():
        for item in dist_dir.iterdir():
            target = usr_bin / item.name
            if item.is_dir():
                shutil.copytree(item, target, symlinks=True)
            else:
                shutil.copy2(item, target)
    else:
        shutil.copy2(dist_dir, usr_bin / "atboffice")

    main_bin = usr_bin / "__main__.bin"
    atb_bin = usr_bin / "atboffice"
    if main_bin.exists() and not atb_bin.exists():
        main_bin.rename(atb_bin)
    elif (usr_bin / "__main__").exists() and not atb_bin.exists():
        (usr_bin / "__main__").rename(atb_bin)

    if atb_bin.exists():
        atb_bin.chmod(atb_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    apprun = appdir / "AppRun"
    apprun.write_text(
        "#!/bin/sh\n"
        'HERE="$(dirname "$(readlink -f "${0}")")"\n'
        'export PATH="${HERE}/usr/bin:${PATH}"\n'
        'export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"\n'
        'exec "${HERE}/usr/bin/atboffice" "$@"\n',
        encoding="utf-8",
    )
    apprun.chmod(apprun.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    desktop = appdir / "atboffice.desktop"
    desktop.write_text(
        "[Desktop Entry]\n"
        "Name=ATBOffice\n"
        "Comment=ATBOffice Suite\n"
        "Exec=atboffice %F\n"
        "Icon=atboffice\n"
        "Terminal=false\n"
        "Type=Application\n"
        "Categories=Office;\n",
        encoding="utf-8",
    )

    icon = appdir / "atboffice.png"
    icon.write_bytes(DEFAULT_PNG_BYTES)

    return appdir


def get_or_download_appimagetool(custom_path: Path | None = None) -> Path:
    """Find or download appimagetool."""
    if custom_path and custom_path.exists():
        return custom_path

    which_path = shutil.which("appimagetool")
    if which_path:
        return Path(which_path)

    download_dir = get_project_root() / "build" / "tools"
    download_dir.mkdir(parents=True, exist_ok=True)
    tool_path = download_dir / "appimagetool-x86_64.AppImage"

    if not tool_path.exists():
        url = (
            "https://github.com/AppImage/appimagetool/releases/download/continuous/"
            "appimagetool-x86_64.AppImage"
        )
        print(f"Downloading appimagetool from {url}...")
        try:
            urllib.request.urlretrieve(url, tool_path)
            tool_path.chmod(tool_path.stat().st_mode | stat.S_IEXEC)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to download appimagetool: {exc}. Please install appimagetool."
            ) from exc

    return tool_path


def build_linux(
    output_dir: Path,
    appimagetool_path: Path | None = None,
    version: str | None = None,
) -> Path:
    """Build standalone Linux binary, create AppDir, and package into .AppImage."""
    output_dir.mkdir(parents=True, exist_ok=True)
    nuitka_dir = output_dir / "nuitka_linux"
    ensure_clean_dir(nuitka_dir)

    dist_dir = run_nuitka_build(nuitka_dir)

    appdir = output_dir / "ATBOffice.AppDir"
    prepare_appdir(dist_dir, appdir)

    appimagetool = get_or_download_appimagetool(appimagetool_path)

    image_name = get_artifact_name("linux", "x86_64", "AppImage", version=version)
    target_image = output_dir / image_name

    env = os.environ.copy()
    env["ARCH"] = "x86_64"
    env["APPIMAGE_EXTRACT_AND_RUN"] = "1"

    cmd = [str(appimagetool), str(appdir), str(target_image)]
    print(f"Executing appimagetool:\n{' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)

    if target_image.exists():
        target_image.chmod(
            target_image.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH
        )
    print(f"Successfully generated Linux AppImage at: {target_image}")
    return target_image


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Linux AppImage for ATBOffice.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=get_project_root() / "dist",
        help="Directory to place the final AppImage artifact.",
    )
    parser.add_argument(
        "--appimagetool",
        type=Path,
        default=None,
        help="Path to appimagetool executable.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string for the release artifact.",
    )

    args = parser.parse_args(argv)
    build_linux(
        output_dir=args.output_dir,
        appimagetool_path=args.appimagetool,
        version=args.version,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
