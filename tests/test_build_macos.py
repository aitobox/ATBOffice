# tests/test_build_macos.py
from unittest.mock import MagicMock, patch

import pytest

from scripts.build.build_macos import build_macos, setup_temp_keychain


def test_setup_temp_keychain_skip_when_no_secrets():
    with patch.dict("os.environ", {}, clear=True):
        keychain = setup_temp_keychain()
        assert keychain is None


def test_build_macos_strict_signing_raises_without_secrets(tmp_path):
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="Signing secrets"):
            build_macos(output_dir=tmp_path, strict_signing=True)


@patch("subprocess.run")
def test_build_macos_skip_signing_generates_dmg(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    # Mock existence of compiled app bundle
    app_bundle = tmp_path / "ATBOffice.app"
    app_bundle.mkdir()

    with patch("scripts.build.build_macos.run_nuitka_build", return_value=app_bundle):
        dmg_path = build_macos(output_dir=tmp_path, skip_signing=True, skip_notarize=True)
        assert dmg_path.name.endswith(".dmg")
        assert "macos-arm64" in dmg_path.name
