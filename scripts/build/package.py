"""Unified CLI entry point for building ATBOffice platform packages."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure repository root is in sys.path for direct script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.build.common import get_project_root  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Unified packaging tool for ATBOffice cross-platform releases."
    )
    subparsers = parser.add_subparsers(dest="platform", required=True, help="Target platform")

    # Global options
    default_out = get_project_root() / "dist"

    # macOS subparser
    macos_parser = subparsers.add_parser("macos", help="Build macOS DMG")
    macos_parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Directory to place the final DMG.",
    )
    macos_parser.add_argument(
        "--skip-signing",
        action="store_true",
        help="Skip codesigning (or use ad-hoc signing).",
    )
    macos_parser.add_argument(
        "--skip-notarize",
        action="store_true",
        help="Skip Apple notarization step.",
    )
    macos_parser.add_argument(
        "--strict-signing",
        action="store_true",
        help="Fail build if Developer ID certificate or Apple credentials are missing.",
    )
    macos_parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string.",
    )

    # Linux subparser
    linux_parser = subparsers.add_parser("linux", help="Build Linux AppImage")
    linux_parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Directory to place the final AppImage.",
    )
    linux_parser.add_argument(
        "--appimagetool",
        type=Path,
        default=None,
        help="Custom path to appimagetool.",
    )
    linux_parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string.",
    )

    # Windows subparser
    windows_parser = subparsers.add_parser("windows", help="Build Windows portable ZIP")
    windows_parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Directory to place the final ZIP.",
    )
    windows_parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string.",
    )

    # Auto subparser
    auto_parser = subparsers.add_parser("auto", help="Auto-detect current OS and build")
    auto_parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Directory to place the final package.",
    )
    auto_parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string.",
    )

    args = parser.parse_args(argv)

    target_platform = args.platform
    if target_platform == "auto":
        if sys.platform == "darwin":
            target_platform = "macos"
        elif sys.platform.startswith("linux"):
            target_platform = "linux"
        elif sys.platform in ("win32", "cygwin"):
            target_platform = "windows"
        else:
            print(f"Error: Unsupported operating system: {sys.platform}", file=sys.stderr)
            return 1

    if target_platform == "macos":
        from scripts.build.build_macos import build_macos

        build_macos(
            output_dir=args.output_dir,
            skip_signing=getattr(args, "skip_signing", False),
            skip_notarize=getattr(args, "skip_notarize", False),
            strict_signing=getattr(args, "strict_signing", False),
            version=getattr(args, "version", None),
        )
    elif target_platform == "linux":
        from scripts.build.build_linux import build_linux

        build_linux(
            output_dir=args.output_dir,
            appimagetool_path=getattr(args, "appimagetool", None),
            version=getattr(args, "version", None),
        )
    elif target_platform == "windows":
        from scripts.build.build_windows import build_windows

        build_windows(
            output_dir=args.output_dir,
            version=getattr(args, "version", None),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
