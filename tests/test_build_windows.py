# tests/test_build_windows.py
import zipfile
from unittest.mock import MagicMock, patch

from scripts.build.build_windows import build_windows, package_portable_zip


def test_package_portable_zip(tmp_path):
    dist_dir = tmp_path / "atboffice.dist"
    dist_dir.mkdir()
    (dist_dir / "atboffice.exe").write_text("dummy exe")

    zip_path = tmp_path / "out" / "ATBOffice-windows-x64.zip"
    package_portable_zip(dist_dir, zip_path)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        assert any(name.endswith("atboffice.exe") for name in names)
        # Ensure all entries use POSIX forward slashes, never backslashes
        assert all("\\" not in name for name in names)


@patch("subprocess.run")
def test_build_windows_creates_zip(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)

    with patch("scripts.build.build_windows.run_nuitka_build", return_value=tmp_path / "dist"):
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "atboffice.exe").write_text("dummy exe")
        zip_path = build_windows(output_dir=tmp_path)
        assert zip_path.name.endswith(".zip")
        assert "windows-x64" in zip_path.name
        assert zip_path.exists()
