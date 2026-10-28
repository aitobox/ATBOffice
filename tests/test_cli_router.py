"""Tests for CLI argument router and module dispatching."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from atboffice.__main__ import (
    main,
    main_lectern,
    main_ledger,
    main_quire,
    parse_cli_args,
)


def test_parse_cli_args_empty() -> None:
    """Empty args should default to start_center action."""
    action, path = parse_cli_args([])
    assert action == "start_center"
    assert path is None


def test_parse_cli_args_start_center_flags() -> None:
    """-s and --start-center flags should route to start_center."""
    action, path = parse_cli_args(["-s"])
    assert action == "start_center"
    assert path is None

    action, path = parse_cli_args(["--start-center"])
    assert action == "start_center"
    assert path is None


def test_parse_cli_args_subcommands() -> None:
    """Subcommands quire, ledger, lectern (and dashed forms) should parse action and path."""
    action, path = parse_cli_args(["quire", "mydoc.docx"])
    assert action == "quire"
    assert path == "mydoc.docx"

    action, path = parse_cli_args(["--quire", "mydoc.docx"])
    assert action == "quire"
    assert path == "mydoc.docx"

    action, path = parse_cli_args(["ledger"])
    assert action == "ledger"
    assert path is None

    action, path = parse_cli_args(["--ledger", "sheet.xlsx"])
    assert action == "ledger"
    assert path == "sheet.xlsx"

    action, path = parse_cli_args(["lectern"])
    assert action == "lectern"
    assert path is None

    action, path = parse_cli_args(["--lectern", "slides.pptx"])
    assert action == "lectern"
    assert path == "slides.pptx"


def test_parse_cli_args_direct_file() -> None:
    """Positional file argument should parse to file action."""
    action, path = parse_cli_args(["spreadsheet.xlsx"])
    assert action == "file"
    assert path == "spreadsheet.xlsx"

    action, path = parse_cli_args(["/path/to/my document.docx"])
    assert action == "file"
    assert path == "/path/to/my document.docx"


def test_parse_cli_args_version_and_help() -> None:
    """Version and help flags should parse accordingly."""
    action, path = parse_cli_args(["-v"])
    assert action == "version"
    assert path is None

    action, path = parse_cli_args(["--version"])
    assert action == "version"
    assert path is None

    action, path = parse_cli_args(["-h"])
    assert action == "help"
    assert path is None

    action, path = parse_cli_args(["--help"])
    assert action == "help"
    assert path is None


def test_main_routes_to_start_center(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main() with no args routes to WindowManager.show_start_center()."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.show_start_center.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code = main([], exec_app=False)
        assert code == 0
        mock_wm.show_start_center.assert_called_once()


def test_main_routes_to_quire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main(['quire', 'doc.docx']) routes to WindowManager.open_quire()."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.open_quire.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code = main(["quire", "doc.docx"], exec_app=False)
        assert code == 0
        mock_wm.open_quire.assert_called_once_with("doc.docx")


def test_main_routes_to_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main(['ledger', 'data.xlsx']) routes to WindowManager.open_ledger()."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.open_ledger.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code = main(["ledger", "data.xlsx"], exec_app=False)
        assert code == 0
        mock_wm.open_ledger.assert_called_once_with("data.xlsx")


def test_main_routes_to_lectern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main(['lectern', 'pres.pptx']) routes to WindowManager.open_lectern()."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.open_lectern.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code = main(["lectern", "pres.pptx"], exec_app=False)
        assert code == 0
        mock_wm.open_lectern.assert_called_once_with("pres.pptx")


def test_main_routes_to_file_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running main(['file.xlsx']) routes to WindowManager.open_file_auto()."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.open_file_auto.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code = main(["file.xlsx"], exec_app=False)
        assert code == 0
        mock_wm.open_file_auto.assert_called_once_with("file.xlsx")


def test_convenience_wrappers() -> None:
    """Convenience functions main_quire, main_ledger, main_lectern dispatch correctly."""
    mock_wm = MagicMock()
    mock_win = MagicMock()
    mock_wm.open_quire.return_value = mock_win
    mock_wm.open_ledger.return_value = mock_win
    mock_wm.open_lectern.return_value = mock_win

    with patch("atboffice.core.window_manager.WindowManager.get_instance", return_value=mock_wm):
        code1 = main_quire(["note.docx"], exec_app=False)
        assert code1 == 0
        mock_wm.open_quire.assert_called_once_with("note.docx")

        code2 = main_ledger(["calc.xlsx"], exec_app=False)
        assert code2 == 0
        mock_wm.open_ledger.assert_called_once_with("calc.xlsx")

        code3 = main_lectern(["talk.pptx"], exec_app=False)
        assert code3 == 0
        mock_wm.open_lectern.assert_called_once_with("talk.pptx")


def test_version_and_help_output(capsys: pytest.CaptureFixture[str]) -> None:
    """main with -v / --version or -h / --help prints output and exits 0."""
    code_ver = main(["--version"], exec_app=False)
    assert code_ver == 0
    captured_ver = capsys.readouterr()
    assert "ATBOffice" in captured_ver.out

    code_help = main(["--help"], exec_app=False)
    assert code_help == 0
    captured_help = capsys.readouterr()
    assert "Usage" in captured_help.out
