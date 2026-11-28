# tests/test_build_macos.py
import json
import plistlib
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.build.build_macos import (
    DEFAULT_ENTITLEMENTS_PATH,
    _is_macho_file,
    _resolve_macos_bundle_version,
    build_macos,
    notarize_and_staple,
    setup_temp_keychain,
    sign_app_bundle,
)

MACHO_64_LE = b"\xcf\xfa\xed\xfe" + b"\x00" * 12
FAT_MACHO_BE = b"\xca\xfe\xba\xbe\x00\x00\x00\x02" + b"\x00" * 8
JAVA_CLASS = b"\xca\xfe\xba\xbe\x00\x00\x00\x3d" + b"\x00" * 8


def _write_file(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _build_mock_app(tmp_path: Path) -> dict[str, Path]:
    app_path = tmp_path / "ATBOffice.app"
    contents = app_path / "Contents"
    _write_file(
        contents / "Info.plist",
        plistlib.dumps({"CFBundleExecutable": "ATBOffice"}),
    )

    main_exec = _write_file(contents / "MacOS" / "ATBOffice", MACHO_64_LE)
    qt_so = _write_file(contents / "MacOS" / "PySide6" / "QtCore.abi3.so", MACHO_64_LE)
    qt_so.chmod(0o444)
    qt_dylib = _write_file(
        contents / "MacOS" / "PySide6" / "qt-plugins" / "platforms" / "libqcocoa.dylib",
        MACHO_64_LE,
    )

    fw_root = contents / "Frameworks" / "QtWebEngineCore.framework"
    fw_bin = _write_file(fw_root / "Versions" / "A" / "QtWebEngineCore", MACHO_64_LE)
    helper_app = fw_root / "Versions" / "A" / "Helpers" / "QtWebEngineProcess.app"
    helper_exec = _write_file(
        helper_app / "Contents" / "MacOS" / "QtWebEngineProcess",
        MACHO_64_LE,
    )
    (fw_root / "Versions" / "Current").symlink_to("A")
    (fw_root / "Helpers").symlink_to("Versions/Current/Helpers")

    json_file = _write_file(contents / "Resources" / "locale" / "en.json", b"{}")

    return {
        "app": app_path,
        "main_exec": main_exec,
        "qt_so": qt_so,
        "qt_dylib": qt_dylib,
        "fw_root": fw_root,
        "fw_bin": fw_bin,
        "helper_app": helper_app,
        "helper_exec": helper_exec,
        "json_file": json_file,
    }


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
    app_bundle = tmp_path / "ATBOffice.app"
    app_bundle.mkdir()

    with patch("scripts.build.build_macos.run_nuitka_build", return_value=app_bundle):
        dmg_path = build_macos(output_dir=tmp_path, skip_signing=True, skip_notarize=True)
        assert dmg_path.name.endswith(".dmg")
        assert "macos-arm64" in dmg_path.name


def test_entitlements_plist_is_valid_and_notarizable():
    assert DEFAULT_ENTITLEMENTS_PATH.is_file()
    data = plistlib.loads(DEFAULT_ENTITLEMENTS_PATH.read_bytes())
    assert data["com.apple.security.cs.allow-jit"] is True
    assert data["com.apple.security.cs.allow-unsigned-executable-memory"] is True
    assert data["com.apple.security.cs.disable-library-validation"] is True
    assert "com.apple.security.get-task-allow" not in data


def test_is_macho_file(tmp_path):
    macho = _write_file(tmp_path / "bin_le", MACHO_64_LE)
    fat_macho = _write_file(tmp_path / "bin_fat", FAT_MACHO_BE)
    java_cls = _write_file(tmp_path / "Test.class", JAVA_CLASS)
    text_file = _write_file(tmp_path / "readme.txt", b"hello world")
    symlink_macho = tmp_path / "bin_link"
    symlink_macho.symlink_to(macho)

    assert _is_macho_file(macho) is True
    assert _is_macho_file(fat_macho) is True
    assert _is_macho_file(java_cls) is False
    assert _is_macho_file(text_file) is False
    assert _is_macho_file(symlink_macho) is False


def test_resolve_macos_bundle_version():
    assert _resolve_macos_bundle_version("v0.4.0") == "0.4.0"
    assert _resolve_macos_bundle_version("0.4.0") == "0.4.0"
    with patch("scripts.build.build_macos.get_app_version", return_value="0.4.0"):
        assert _resolve_macos_bundle_version("test1.0.0") == "0.4.0"
        assert _resolve_macos_bundle_version(None) == "0.4.0"


@patch("subprocess.run")
def test_sign_app_bundle_inside_out_with_developer_id(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    paths = _build_mock_app(tmp_path)
    keychain = tmp_path / "build.keychain"
    keychain.write_text("", encoding="utf-8")

    sign_app_bundle(
        paths["app"],
        identity="Developer ID Application: Test (TEAM123)",
        keychain_path=keychain,
    )

    calls = [call.args[0] for call in mock_run.call_args_list]
    assert Path(calls[0][0]).name == "xattr"
    assert calls[0][1:] == ["-cr", str(paths["app"])]

    verify_cmd = calls[-1]
    assert Path(verify_cmd[0]).name == "codesign"
    assert "--verify" in verify_cmd
    assert "--deep" in verify_cmd
    assert "--strict" in verify_cmd
    assert verify_cmd[-1] == str(paths["app"])

    sign_calls = calls[1:-1]
    assert sign_calls, "Expected codesign invocations"

    signed_targets = [cmd[-1] for cmd in sign_calls]
    assert str(paths["qt_so"]) in signed_targets
    assert str(paths["qt_dylib"]) in signed_targets
    assert str(paths["fw_bin"]) in signed_targets
    assert str(paths["helper_exec"]) in signed_targets
    assert str(paths["helper_app"]) in signed_targets
    assert str(paths["fw_root"]) in signed_targets
    assert signed_targets[-1] == str(paths["app"])

    # Symlinks, main_exec (signed via outer app bundle), and JSON must not be signed directly.
    assert str(paths["json_file"]) not in signed_targets
    assert str(paths["main_exec"]) not in signed_targets
    assert all("Current" not in t for t in signed_targets)
    assert all(not t.endswith("/Helpers") for t in signed_targets)

    # Read-only .so must have been made user-writable before signing.
    assert bool(paths["qt_so"].stat().st_mode & stat.S_IWUSR)

    # Inside-out ordering: leaf Mach-O -> helper app -> framework -> outer app.
    idx = {target: i for i, target in enumerate(signed_targets)}
    assert idx[str(paths["helper_exec"])] < idx[str(paths["helper_app"])]
    assert idx[str(paths["helper_app"])] < idx[str(paths["fw_root"])]
    assert idx[str(paths["fw_bin"])] < idx[str(paths["fw_root"])]
    assert idx[str(paths["fw_root"])] < idx[str(paths["app"])]
    assert idx[str(paths["qt_so"])] < idx[str(paths["app"])]
    assert idx[str(paths["qt_dylib"])] < idx[str(paths["app"])]

    for cmd in sign_calls:
        target = cmd[-1]
        assert Path(cmd[0]).name == "codesign"
        assert "--deep" not in cmd
        assert "--force" in cmd
        assert "--timestamp" in cmd
        assert "--options" in cmd and "runtime" in cmd
        assert "--keychain" in cmd and str(keychain) in cmd

        if target in {str(paths["qt_so"]), str(paths["qt_dylib"]), str(paths["fw_root"])}:
            assert "--entitlements" not in cmd
        elif target in {
            str(paths["helper_exec"]),
            str(paths["helper_app"]),
            str(paths["app"]),
        }:
            assert "--entitlements" in cmd
            assert str(DEFAULT_ENTITLEMENTS_PATH) in cmd


@patch("subprocess.run")
def test_sign_app_bundle_adhoc_omits_runtime_timestamp_entitlements(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    paths = _build_mock_app(tmp_path)

    sign_app_bundle(paths["app"], identity="-")

    sign_calls = [call.args[0] for call in mock_run.call_args_list][1:-1]
    assert sign_calls
    for cmd in sign_calls:
        assert "--timestamp" not in cmd
        assert "--options" not in cmd
        assert "--entitlements" not in cmd
        assert "--deep" not in cmd


@patch("subprocess.run")
def test_notarize_and_staple_accepted(mock_run, tmp_path):
    dmg_path = tmp_path / "ATBOffice-0.4.0-macos-arm64.dmg"
    dmg_path.write_bytes(b"dmg")

    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout=json.dumps({"id": "sub-123", "status": "Accepted"}),
            stderr="",
        ),
        MagicMock(returncode=0),
        MagicMock(returncode=0),
    ]

    with patch.dict(
        "os.environ",
        {
            "APPLE_ID": "dev@example.com",
            "APPLE_PASSWORD": "secret-app-password",
            "APPLE_TEAM_ID": "TEAM123",
        },
        clear=True,
    ):
        notarize_and_staple(dmg_path)

    calls = [call.args[0] for call in mock_run.call_args_list]
    assert calls[0][:4] == ["xcrun", "notarytool", "submit", str(dmg_path)]
    assert "--output-format" in calls[0] and "json" in calls[0]
    assert calls[1] == ["xcrun", "stapler", "staple", str(dmg_path)]
    assert calls[2] == ["xcrun", "stapler", "validate", str(dmg_path)]


@patch("subprocess.run")
def test_notarize_and_staple_invalid_fetches_log_and_fails(mock_run, tmp_path, capsys):
    dmg_path = tmp_path / "ATBOffice-0.4.0-macos-arm64.dmg"
    dmg_path.write_bytes(b"dmg")
    secret = "super-secret-password"

    mock_run.side_effect = [
        MagicMock(
            returncode=0,
            stdout=json.dumps({"id": "sub-invalid-999", "status": "Invalid"}),
            stderr="",
        ),
        MagicMock(
            returncode=0,
            stdout=json.dumps({"status": "Invalid", "issues": [{"message": "unsigned dylib"}]}),
            stderr="",
        ),
    ]

    with patch.dict(
        "os.environ",
        {
            "APPLE_ID": "dev@example.com",
            "APPLE_PASSWORD": secret,
            "APPLE_TEAM_ID": "TEAM123",
        },
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="sub-invalid-999") as exc_info:
            notarize_and_staple(dmg_path)

    assert secret not in str(exc_info.value)
    captured = capsys.readouterr()
    assert "unsigned dylib" in captured.err
    assert secret not in captured.out
    assert secret not in captured.err

    calls = [call.args[0] for call in mock_run.call_args_list]
    assert len(calls) == 2
    assert calls[1][:4] == ["xcrun", "notarytool", "log", "sub-invalid-999"]


@patch("subprocess.run")
def test_notarize_and_staple_nonzero_returncode_fails_without_secret_leak(
    mock_run, tmp_path, capsys
):
    dmg_path = tmp_path / "ATBOffice-0.4.0-macos-arm64.dmg"
    dmg_path.write_bytes(b"dmg")
    secret = "super-secret-password"

    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="Error: HTTP 401 unauthorized",
    )

    with patch.dict(
        "os.environ",
        {
            "APPLE_ID": "dev@example.com",
            "APPLE_PASSWORD": secret,
            "APPLE_TEAM_ID": "TEAM123",
        },
        clear=True,
    ):
        with pytest.raises(RuntimeError, match="Apple notarization failed") as exc_info:
            notarize_and_staple(dmg_path)

    assert secret not in str(exc_info.value)
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
