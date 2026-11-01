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

@patch("scripts.build.build_linux.build_linux")
def test_package_cli_dispatch_linux(mock_linux):
    main(["linux"])
    assert mock_linux.called

@patch("scripts.build.build_windows.build_windows")
def test_package_cli_dispatch_windows(mock_windows):
    main(["windows"])
    assert mock_windows.called
