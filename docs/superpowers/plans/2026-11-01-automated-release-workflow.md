# Automated Release Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated GitHub Actions release workflow that uses Nuitka to compile ATBOffice into a macOS ARM DMG (signed & notarized), Linux x86_64 AppImage, and Windows x64 portable Zip upon tag pushes (`x.x.x`, `vx.x.x`, `testx.x.x`), with independent local CLI entrypoints.

**Architecture:** A script-driven architecture where `scripts/build/` houses dedicated, locally testable Python build scripts (`build_macos.py`, `build_linux.py`, `build_windows.py`, and router `package.py`) backed by shared utilities (`common.py`). A thin `.github/workflows/release.yml` orchestrates runner matrices, injects signing secrets, caches build objects, and publishes the release.

**Tech Stack:** Python 3.12+, Nuitka, PySide6, `appimagetool` (Linux), `hdiutil` / `codesign` / `notarytool` (macOS), `zipfile` (Windows), GitHub Actions (`actions/checkout@v4`, `actions/setup-python@v5`, `softprops/action-gh-release@v2`).

**Spec:** `docs/superpowers/specs/2026-11-01-automated-release-workflow-design.md`

## Global Constraints

- Python version floor: `>=3.12`.
- GUI Framework: PySide6 (Nuitka flag `--enable-plugin=pyside6` is mandatory).
- Tag triggers: Exact patterns `[0-9]+.[0-9]+.[0-9]+*`, `v[0-9]+.[0-9]+.[0-9]+*`, `test*`.
- Pre-release rule: Tags starting with `test` must set `prerelease: true`; all others `prerelease: false`.
- Target platforms: macOS (ARM64 only), Linux (x86_64 only), Windows (x64 only).
- Package data: Must include package data (`locale/*.json`, `dict/*`) using `--include-package-data=atboffice`.

## Review Focus

- Missing macOS signing secrets during local execution: Must fallback to ad-hoc signing or pass without failing unless `--strict-signing` is requested.
- Missing `appimagetool` on Linux: Must provide automatic download or clear diagnostic instructions.
- Whitespace or special characters in project paths: Build scripts must correctly quote and handle arbitrary output directories.
- Windows console window suppression: Must supply `--windows-console-mode=disable` to avoid opening an empty terminal alongside the GUI.
- Tag name parsing: Pre-release check must accurately inspect `github.ref_name` or Git tag prefix `test`.

---

### Task 1: Common Build Utilities (`scripts/build/common.py`)

**Files:**
- Create: `scripts/build/common.py`
- Test: `tests/test_build_common.py`

**Interfaces:**
- Produces:
  - `get_project_root() -> Path`: Resolves repository root directory.
  - `get_app_version() -> str`: Reads `atboffice.__version__` or Git tag fallback.
  - `get_base_nuitka_args(output_dir: Path) -> list[str]`: Generates common Nuitka compilation flags.
  - `get_artifact_name(platform_name: str, arch: str, ext: str, version: str | None = None) -> str`: Returns standardized asset file names (e.g. `ATBOffice-0.1.0-macos-arm64.dmg`).
  - `ensure_clean_dir(path: Path) -> None`: Cleans and recreates target directory.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_common.py
from pathlib import Path
from scripts.build.common import (
    get_project_root,
    get_app_version,
    get_base_nuitka_args,
    get_artifact_name,
)

def test_get_project_root():
    root = get_project_root()
    assert (root / "pyproject.toml").exists()

def test_get_app_version():
    ver = get_app_version()
    assert isinstance(ver, str)
    assert len(ver.split(".")) >= 2

def test_get_artifact_name():
    name = get_artifact_name("macos", "arm64", "dmg", version="1.0.0")
    assert name == "ATBOffice-1.0.0-macos-arm64.dmg"

def test_get_base_nuitka_args(tmp_path):
    args = get_base_nuitka_args(tmp_path)
    assert "--standalone" in args
    assert "--enable-plugin=pyside6" in args
    assert "--include-package-data=atboffice" in args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_common.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.build')

- [ ] **Step 3: Implement `scripts/build/common.py`**

Implement path detection, version loading, argument generation, and directory sanitation.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_build_common.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build/common.py tests/test_build_common.py
git commit -m "feat(build): add common build utilities for nuitka packaging"
```

---

### Task 2: macOS Build & Notarization Script (`scripts/build/build_macos.py`)

**Files:**
- Create: `scripts/build/build_macos.py`
- Test: `tests/test_build_macos.py`

**Interfaces:**
- Consumes: `get_project_root`, `get_app_version`, `get_base_nuitka_args`, `get_artifact_name` from `scripts.build.common`
- Produces:
  - `build_macos(output_dir: Path, skip_signing: bool, skip_notarize: bool) -> Path`: Executes Nuitka compilation, app bundle creation, signing, DMG creation, and optional notarization. Returns path to output `.dmg`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_macos.py
from unittest.mock import patch, MagicMock
from pathlib import Path
from scripts.build.build_macos import build_macos, setup_temp_keychain

def test_setup_temp_keychain_skip_when_no_secrets():
    with patch.dict("os.environ", {}, clear=True):
        keychain = setup_temp_keychain()
        assert keychain is None

@patch("subprocess.run")
def test_build_macos_skip_signing_generates_dmg(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    # Mock existence of compiled app bundle
    app_bundle = tmp_path / "ATBOffice.app"
    app_bundle.mkdir()
    
    with patch("scripts.build.build_macos.run_nuitka_build", return_value=app_bundle):
        dmg_path = build_macos(output_dir=tmp_path, skip_signing=True, skip_notarize=True)
        assert dmg_path.name.endswith(".dmg")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_macos.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.build.build_macos')

- [ ] **Step 3: Implement `scripts/build/build_macos.py`**

Implement:
1. `setup_temp_keychain()`: Imports `MAC_CERTS_P12_BASE64` using `security import`.
2. `cleanup_temp_keychain()`: Deletes temporary keychain.
3. `sign_app_bundle()`: Invokes `codesign --deep --force --options runtime --sign`.
4. `create_dmg()`: Uses `hdiutil create` with `-volname ATBOffice -srcfolder`.
5. `notarize_and_staple()`: Invokes `xcrun notarytool` and `xcrun stapler`.
6. CLI entrypoint with `argparse`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_build_macos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build/build_macos.py tests/test_build_macos.py
git commit -m "feat(build): add macOS Nuitka build, codesign, and DMG packaging script"
```

---

### Task 3: Linux AppImage Script (`scripts/build/build_linux.py`)

**Files:**
- Create: `scripts/build/build_linux.py`
- Test: `tests/test_build_linux.py`

**Interfaces:**
- Consumes: `get_project_root`, `get_app_version`, `get_base_nuitka_args`, `get_artifact_name` from `scripts.build.common`
- Produces:
  - `build_linux(output_dir: Path, appimagetool_path: Path | None) -> Path`: Executes Nuitka compilation, constructs `ATBOffice.AppDir`, packages into `.AppImage`. Returns path to `.AppImage`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_linux.py
from unittest.mock import patch, MagicMock
from pathlib import Path
from scripts.build.build_linux import build_linux, prepare_appdir

def test_prepare_appdir(tmp_path):
    dist_dir = tmp_path / "dist_test"
    dist_dir.mkdir()
    (dist_dir / "atboffice.bin").touch()
    appdir = prepare_appdir(dist_dir, tmp_path / "AppDir")
    
    assert (appdir / "AppRun").exists()
    assert (appdir / "atboffice.desktop").exists()
    assert (appdir / "usr/bin").exists()

@patch("subprocess.run")
def test_build_linux_invokes_appimagetool(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    fake_tool = tmp_path / "appimagetool"
    fake_tool.touch()
    
    with patch("scripts.build.build_linux.run_nuitka_build", return_value=tmp_path / "dist"):
        (tmp_path / "dist").mkdir()
        img_path = build_linux(output_dir=tmp_path, appimagetool_path=fake_tool)
        assert img_path.name.endswith(".AppImage")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_linux.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.build.build_linux')

- [ ] **Step 3: Implement `scripts/build/build_linux.py`**

Implement AppDir assembly, default `.desktop` file and icon creation, `appimagetool` execution, and CLI entrypoint.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_build_linux.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build/build_linux.py tests/test_build_linux.py
git commit -m "feat(build): add Linux Nuitka build and AppImage packaging script"
```

---

### Task 4: Windows Portable ZIP Script (`scripts/build/build_windows.py`)

**Files:**
- Create: `scripts/build/build_windows.py`
- Test: `tests/test_build_windows.py`

**Interfaces:**
- Consumes: `get_project_root`, `get_app_version`, `get_base_nuitka_args`, `get_artifact_name` from `scripts.build.common`
- Produces:
  - `build_windows(output_dir: Path) -> Path`: Executes Nuitka compilation with console disabled, compresses standalone dist into a portable `.zip`. Returns path to `.zip`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_windows.py
from unittest.mock import patch
from pathlib import Path
from scripts.build.build_windows import build_windows, package_portable_zip

def test_package_portable_zip(tmp_path):
    dist_dir = tmp_path / "atboffice.dist"
    dist_dir.mkdir()
    (dist_dir / "atboffice.exe").write_text("dummy exe")
    
    zip_path = tmp_path / "out" / "ATBOffice-windows-x64.zip"
    package_portable_zip(dist_dir, zip_path)
    
    assert zip_path.exists()
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        assert "atboffice/atboffice.exe" in z.namelist() or "atboffice.exe" in z.namelist()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_build_windows.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.build.build_windows')

- [ ] **Step 3: Implement `scripts/build/build_windows.py`**

Implement Windows standalone compilation with `--windows-console-mode=disable`, zip packaging, and CLI entrypoint.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_build_windows.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build/build_windows.py tests/test_build_windows.py
git commit -m "feat(build): add Windows Nuitka build and portable zip packaging script"
```

---

### Task 5: Unified CLI Router (`scripts/build/package.py`)

**Files:**
- Create: `scripts/build/package.py`
- Test: `tests/test_package_cli.py`

**Interfaces:**
- Dispatches user command `python scripts/build/package.py <platform>` to the target builder.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package_cli.py
from unittest.mock import patch
import pytest
from scripts.build.package import main

def test_package_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0

@patch("scripts.build.build_macos.build_macos")
def test_package_cli_dispatch_macos(mock_macos):
    main(["macos", "--skip-signing", "--skip-notarize"])
    assert mock_macos.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_package_cli.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'scripts.build.package')

- [ ] **Step 3: Implement `scripts/build/package.py`**

Implement `argparse` subcommands for `macos`, `linux`, `windows`, and `auto` (auto-detect current OS).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_package_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build/package.py tests/test_package_cli.py
git commit -m "feat(build): add unified packaging CLI dispatcher"
```

---

### Task 6: GitHub Actions Automated Release Workflow (`.github/workflows/release.yml`)

**Files:**
- Create: `.github/workflows/release.yml`
- Test: `tests/test_release_workflow.py` (Validates YAML schema and tag logic)

**Interfaces:**
- Produces: GitHub Actions Release Pipeline triggered on `[0-9]+.[0-9]+.[0-9]+*`, `v[0-9]+.[0-9]+.[0-9]+*`, and `test*`.

- [ ] **Step 1: Write the workflow verification test**

```python
# tests/test_release_workflow.py
from pathlib import Path
import yaml

def test_release_workflow_syntax():
    workflow_path = Path(".github/workflows/release.yml")
    assert workflow_path.exists()
    data = yaml.safe_load(workflow_path.read_text())
    
    # Verify triggers
    tags = data["on"]["push"]["tags"]
    assert "test*" in tags
    assert "v[0-9]+.[0-9]+.[0-9]+*" in tags
    
    # Verify jobs
    jobs = data["jobs"]
    assert "build-macos" in jobs
    assert "build-linux" in jobs
    assert "build-windows" in jobs
    assert "publish-release" in jobs
    assert jobs["publish-release"]["needs"] == ["build-macos", "build-linux", "build-windows"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_release_workflow.py -v`
Expected: FAIL (AssertionError: File does not exist)

- [ ] **Step 3: Create `.github/workflows/release.yml`**

Implement complete multi-platform release workflow:
1. `build-macos` on `macos-14`: Sets up Python 3.12, installs build dependencies (`nuitka`, `pyside6`, `zstandard`), maps `APPLE_*` and `MAC_*` secrets, calls `python scripts/build/build_macos.py`, uploads `.dmg` as workflow artifact.
2. `build-linux` on `ubuntu-22.04`: Sets up Python 3.12, installs Linux Qt system dependencies (`libegl1`, `libxkbcommon-x11-0`, etc.), installs `appimagetool`, calls `python scripts/build/build_linux.py`, uploads `.AppImage` as workflow artifact.
3. `build-windows` on `windows-latest`: Sets up Python 3.12, installs build dependencies, calls `python scripts/build/build_windows.py`, uploads `.zip` as workflow artifact.
4. `publish-release`: Needs `[build-macos, build-linux, build-windows]`, downloads all artifacts, checks if tag starts with `test` for `prerelease: true`, uses `softprops/action-gh-release@v2` to publish the release with all 3 files.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_release_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml tests/test_release_workflow.py
git commit -m "ci: add automated cross-platform release workflow for git tags"
```

---

### Task 7: End-to-End Build CLI Dry-Run & Documentation Update

**Files:**
- Modify: `README.md`
- Test: Local CLI execution check

- [ ] **Step 1: Test local execution of packaging CLI on current machine**

Run: `python scripts/build/package.py --help`
Expected: Lists all commands and options cleanly.

- [ ] **Step 2: Update `README.md` with release and packaging instructions**

Document how developers can run manual builds locally and how the automated release workflow works.

- [ ] **Step 3: Run all new and existing tests**

Run: `PYTHONPATH=src python -m pytest tests/test_build_* tests/test_package_* tests/test_release_* -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document release workflow and local packaging commands"
```
