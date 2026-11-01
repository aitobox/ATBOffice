# tests/test_build_linux.py
from unittest.mock import MagicMock, patch

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
        assert "linux-x86_64" in img_path.name

        # Verify environment passed to subprocess.run has APPIMAGE_EXTRACT_AND_RUN=1
        called_env = mock_run.call_args[1].get("env", {})
        assert called_env.get("APPIMAGE_EXTRACT_AND_RUN") == "1"
        assert called_env.get("ARCH") == "x86_64"
