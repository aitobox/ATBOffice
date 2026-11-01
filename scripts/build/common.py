"""Common utilities for Nuitka packaging and distribution scripts."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    current_file = Path(__file__).resolve()
    return current_file.parent.parent.parent


def get_app_version() -> str:
    """Resolve the application version from package or environment fallback."""
    project_root = get_project_root()
    sys_path_added = False
    src_dir = project_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
        sys_path_added = True

    try:
        from atboffice import __version__
        return __version__
    except ImportError:
        # Fallback to reading pyproject.toml or env
        pyproject = project_root / "pyproject.toml"
        if pyproject.exists():
            for line in pyproject.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version ="):
                    return line.split("=")[1].strip().strip('"\'')
        return os.environ.get("RELEASE_VERSION", "0.1.0")
    finally:
        if sys_path_added and str(src_dir) in sys.path:
            sys.path.remove(str(src_dir))


def get_artifact_name(platform_name: str, arch: str, ext: str, version: str | None = None) -> str:
    """Generate standardized artifact name: ATBOffice-<version>-<platform>-<arch>.<ext>."""
    ver = version or get_app_version()
    ext_clean = ext.lstrip(".")
    return f"ATBOffice-{ver}-{platform_name}-{arch}.{ext_clean}"


def ensure_clean_dir(path: Path) -> None:
    """Ensure a directory exists and is empty."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def get_nuitka_env() -> dict[str, str]:
    """Return environment dictionary with src/ injected into PYTHONPATH."""
    env = os.environ.copy()
    src_dir = str(get_project_root() / "src")
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pythonpath}"
    else:
        env["PYTHONPATH"] = src_dir
    return env


def get_base_nuitka_args(output_dir: Path) -> list[str]:
    """Return base Nuitka flags common to all platforms."""
    project_root = get_project_root()
    main_script = project_root / "src" / "atboffice" / "__main__.py"

    return [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--enable-plugin=pyside6",
        "--include-package-data=atboffice",
        "--assume-yes-for-downloads",
        "--show-memory",
        "--show-progress",
        f"--output-dir={output_dir}",
        str(main_script),
    ]
