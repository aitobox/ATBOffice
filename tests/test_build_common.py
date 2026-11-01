# tests/test_build_common.py
from scripts.build.common import (
    ensure_clean_dir,
    get_app_version,
    get_artifact_name,
    get_base_nuitka_args,
    get_nuitka_env,
    get_project_root,
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

def test_get_nuitka_env():
    env = get_nuitka_env()
    root = get_project_root()
    assert "PYTHONPATH" in env
    assert str(root / "src") in env["PYTHONPATH"]

def test_ensure_clean_dir(tmp_path):
    target = tmp_path / "subdir"
    target.mkdir()
    (target / "dummy.txt").write_text("dummy")
    ensure_clean_dir(target)
    assert target.exists()
    assert list(target.iterdir()) == []
