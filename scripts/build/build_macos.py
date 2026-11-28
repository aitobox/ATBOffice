"""macOS Nuitka build, codesigning, DMG packaging, and Apple notarization script."""

from __future__ import annotations

import argparse
import base64
import json
import os
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

# Ensure repository root is in sys.path for direct script execution
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.build.common import (  # noqa: E402
    ensure_clean_dir,
    get_app_version,
    get_artifact_name,
    get_base_nuitka_args,
    get_nuitka_env,
    get_project_root,
)

MACOS_BUNDLE_IDENTIFIER = "com.aitobox.atboffice"
DEFAULT_ENTITLEMENTS_PATH = Path(__file__).resolve().parent / "entitlements.plist"

_MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
}
_FAT_MACHO_BE_MAGICS = {b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}
_FAT_MACHO_LE_MAGICS = {b"\xbe\xba\xfe\xca", b"\xbf\xba\xfe\xca"}
_NESTED_BUNDLE_SUFFIXES = {".framework", ".app", ".xpc", ".appex", ".plugin", ".bundle"}
_EXECUTABLE_BUNDLE_SUFFIXES = {".app", ".xpc", ".appex"}
_LIBRARY_SUFFIXES = {".dylib", ".so"}
_BUNDLE_VERSION_RE = re.compile(r"^\d+(?:\.\d+){0,2}$")


class KeychainContext(NamedTuple):
    keychain_path: Path
    keychain_password: str
    identity: str


def _codesign_bin() -> str:
    """Return Apple's system codesign path when present to avoid conda shims."""
    system_codesign = Path("/usr/bin/codesign")
    return str(system_codesign) if system_codesign.exists() else "codesign"


def _xattr_bin() -> str:
    """Return Apple's system xattr path when present."""
    system_xattr = Path("/usr/bin/xattr")
    return str(system_xattr) if system_xattr.exists() else "xattr"


def _normalize_bundle_version(raw_version: str) -> str:
    ver = raw_version.strip()
    if len(ver) > 1 and ver[0] in "vV" and ver[1].isdigit():
        ver = ver[1:]
    return ver


def _resolve_macos_bundle_version(version: str | None) -> str:
    """Resolve a numeric CFBundleShortVersionString-compatible version string."""
    if version:
        candidate = _normalize_bundle_version(version)
        if _BUNDLE_VERSION_RE.fullmatch(candidate):
            return candidate

    fallback = _normalize_bundle_version(get_app_version())
    if _BUNDLE_VERSION_RE.fullmatch(fallback):
        return fallback
    return "0.1.0"


def _is_macho_file(path: Path) -> bool:
    """Return True if path is a regular Mach-O or universal fat Mach-O file."""
    if path.is_symlink() or not path.is_file():
        return False

    try:
        with path.open("rb") as fh:
            header = fh.read(8)
    except OSError:
        return False

    if len(header) < 4:
        return False

    magic = header[:4]
    if magic in _MACHO_MAGICS:
        return True

    if len(header) == 8 and magic in _FAT_MACHO_BE_MAGICS:
        nfat_arch = struct.unpack(">I", header[4:8])[0]
        return 1 <= nfat_arch <= 20

    if len(header) == 8 and magic in _FAT_MACHO_LE_MAGICS:
        nfat_arch = struct.unpack("<I", header[4:8])[0]
        return 1 <= nfat_arch <= 20

    return False


def _ensure_writable(path: Path) -> None:
    """Ensure the owner write bit is set so codesign can embed signatures."""
    if path.is_symlink() or not path.exists():
        return
    mode = path.stat().st_mode
    if not (mode & stat.S_IWUSR):
        path.chmod(mode | stat.S_IWUSR)


def _get_bundle_main_executable(app_path: Path) -> Path | None:
    """Return the main executable path declared in Contents/Info.plist, if any."""
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.is_file():
        return None
    try:
        data = plistlib.loads(info_plist.read_bytes())
    except (OSError, plistlib.InvalidFileException, ValueError):
        return None
    if isinstance(data, dict):
        executable_name = data.get("CFBundleExecutable")
        if isinstance(executable_name, str) and executable_name:
            return app_path / "Contents" / "MacOS" / executable_name
    return None


def _discover_signing_targets(app_path: Path) -> tuple[list[Path], list[Path]]:
    """Discover nested Mach-O binaries and sub-bundles sorted deepest-first."""
    main_exec = _get_bundle_main_executable(app_path)
    macho_files: list[Path] = []
    nested_bundles: list[Path] = []

    for root, dirnames, filenames in os.walk(app_path, topdown=True, followlinks=False):
        root_path = Path(root)
        kept_dirs: list[str] = []
        for dirname in dirnames:
            if dirname == "_CodeSignature":
                continue
            dir_path = root_path / dirname
            if dir_path.is_symlink():
                continue
            kept_dirs.append(dirname)
            if dir_path.suffix.lower() in _NESTED_BUNDLE_SUFFIXES:
                nested_bundles.append(dir_path)
        dirnames[:] = kept_dirs

        for filename in filenames:
            file_path = root_path / filename
            if main_exec is not None and file_path == main_exec:
                continue
            if _is_macho_file(file_path):
                macho_files.append(file_path)

    macho_files.sort(key=lambda p: (-len(p.parts), str(p)))
    nested_bundles.sort(key=lambda p: (-len(p.parts), str(p)))
    return macho_files, nested_bundles


def setup_temp_keychain() -> KeychainContext | None:
    """Create a temporary macOS keychain and import the Developer ID certificate.

    Returns:
        KeychainContext if credentials exist, None otherwise.
    """
    p12_base64 = os.environ.get("MAC_CERTS_P12_BASE64")
    p12_password = os.environ.get("MAC_CERTS_PASSWORD")

    if not p12_base64 or not p12_password:
        return None

    temp_dir = Path(tempfile.mkdtemp(prefix="atb_keychain_"))
    keychain_path = temp_dir / "build.keychain"
    keychain_password = "temp_build_password_123"

    try:
        # Create temp keychain
        subprocess.run(
            ["security", "create-keychain", "-p", keychain_password, str(keychain_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["security", "set-keychain-settings", "-lut", "21600", str(keychain_path)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["security", "unlock-keychain", "-p", keychain_password, str(keychain_path)],
            check=True,
            capture_output=True,
        )

        # Decode p12
        p12_file = temp_dir / "certificate.p12"
        p12_file.write_bytes(base64.b64decode(p12_base64))

        # Import p12 into keychain
        subprocess.run(
            [
                "security",
                "import",
                str(p12_file),
                "-k",
                str(keychain_path),
                "-P",
                p12_password,
                "-T",
                "/usr/bin/codesign",
                "-T",
                "/usr/bin/productsign",
            ],
            check=True,
            capture_output=True,
        )

        # Allow codesign access without prompts
        subprocess.run(
            [
                "security",
                "set-key-partition-list",
                "-S",
                "apple-tool:,apple:,codesign:",
                "-s",
                "-k",
                keychain_password,
                str(keychain_path),
            ],
            check=True,
            capture_output=True,
        )

        # Add to keychain search list safely (handling paths with spaces)
        current_list = [
            line.strip().strip('"')
            for line in subprocess.run(
                ["security", "list-keychains", "-d", "user"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            if line.strip()
        ]

        if str(keychain_path) not in current_list:
            subprocess.run(
                ["security", "list-keychains", "-d", "user", "-s", str(keychain_path)]
                + current_list,
                check=True,
                capture_output=True,
            )

        # Find Developer ID Application identity
        identities_out = subprocess.run(
            ["security", "find-identity", "-v", "-p", "codesigning", str(keychain_path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        identity = "-"  # fallback to ad-hoc
        for line in identities_out.splitlines():
            if "Developer ID Application:" in line:
                start = line.find('"')
                end = line.rfind('"')
                if start != -1 and end != -1:
                    identity = line[start + 1 : end]
                    break

        return KeychainContext(keychain_path, keychain_password, identity)

    except Exception as exc:
        print(f"Warning: Failed to set up temporary keychain: {exc}", file=sys.stderr, flush=True)
        cleanup_temp_keychain(keychain_path)
        return None


def cleanup_temp_keychain(keychain_path: Path | None) -> None:
    """Delete the temporary keychain and its directory."""
    if not keychain_path or not keychain_path.exists():
        return
    try:
        subprocess.run(["security", "delete-keychain", str(keychain_path)], capture_output=True)
    except Exception:
        pass
    try:
        if keychain_path.parent.exists():
            shutil.rmtree(keychain_path.parent, ignore_errors=True)
    except Exception:
        pass


def run_nuitka_build(output_dir: Path, version: str | None = None) -> Path:
    """Run Nuitka to build the standalone macOS app bundle."""
    base_args = get_base_nuitka_args(output_dir)
    bundle_version = _resolve_macos_bundle_version(version)
    macos_args = [
        "--macos-create-app-bundle",
        "--output-filename=ATBOffice",
        "--macos-app-name=ATBOffice",
        f"--macos-signed-app-name={MACOS_BUNDLE_IDENTIFIER}",
        f"--macos-app-version={bundle_version}",
        "--macos-app-mode=gui",
        "--macos-target-arch=arm64",
    ]
    cmd = base_args + macos_args
    env = get_nuitka_env()
    print(f"Running Nuitka macOS build:\n{' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)

    app_path = output_dir / "ATBOffice.app"
    if not app_path.exists():
        alt_app = output_dir / "__main__.app"
        if alt_app.exists():
            alt_app.rename(app_path)
    return app_path


def sign_app_bundle(
    app_path: Path,
    identity: str = "-",
    keychain_path: Path | None = None,
    entitlements_path: Path | None = None,
) -> None:
    """Codesign the macOS app bundle inside-out with hardened runtime and entitlements."""
    resolved_entitlements = (
        entitlements_path if entitlements_path is not None else DEFAULT_ENTITLEMENTS_PATH
    )
    codesign = _codesign_bin()

    def _run_codesign(target: Path, *, use_entitlements: bool) -> None:
        cmd = [codesign, "--force"]
        if identity != "-":
            cmd.extend(["--options", "runtime", "--timestamp"])
            if use_entitlements and resolved_entitlements.exists():
                cmd.extend(["--entitlements", str(resolved_entitlements)])
            if keychain_path and keychain_path.exists():
                cmd.extend(["--keychain", str(keychain_path)])
        cmd.extend(["--sign", identity, str(target)])
        subprocess.run(cmd, check=True)

    print(f"Signing app bundle inside-out with identity '{identity}'...", flush=True)
    subprocess.run([_xattr_bin(), "-cr", str(app_path)], check=True)

    macho_files, nested_bundles = _discover_signing_targets(app_path)
    print(
        f"Signing {len(macho_files)} nested Mach-O files and "
        f"{len(nested_bundles)} nested bundles...",
        flush=True,
    )

    for macho_file in macho_files:
        _ensure_writable(macho_file)
        _run_codesign(
            macho_file,
            use_entitlements=macho_file.suffix.lower() not in _LIBRARY_SUFFIXES,
        )

    for bundle in nested_bundles:
        _run_codesign(
            bundle,
            use_entitlements=bundle.suffix.lower() in _EXECUTABLE_BUNDLE_SUFFIXES,
        )

    main_exec = _get_bundle_main_executable(app_path)
    if main_exec is not None:
        _ensure_writable(main_exec)

    _run_codesign(app_path, use_entitlements=True)

    print("Verifying app bundle signature...", flush=True)
    subprocess.run(
        [codesign, "--verify", "--deep", "--strict", "--verbose=2", str(app_path)],
        check=True,
    )


def create_dmg(app_path: Path, dmg_output_path: Path) -> Path:
    """Package the .app bundle into a .dmg image using hdiutil."""
    temp_dmg_dir = Path(tempfile.mkdtemp(prefix="atb_dmg_"))
    try:
        target_app = temp_dmg_dir / app_path.name
        shutil.copytree(app_path, target_app, symlinks=True)

        apps_link = temp_dmg_dir / "Applications"
        if not apps_link.exists():
            try:
                os.symlink("/Applications", str(apps_link))
            except OSError:
                pass

        if dmg_output_path.exists():
            dmg_output_path.unlink()

        hdiutil_cmd = [
            "hdiutil",
            "create",
            "-volname",
            "ATBOffice",
            "-srcfolder",
            str(temp_dmg_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_output_path),
        ]
        print(f"Creating DMG at {dmg_output_path}...", flush=True)
        subprocess.run(hdiutil_cmd, check=True)
        return dmg_output_path
    finally:
        shutil.rmtree(temp_dmg_dir, ignore_errors=True)


def notarize_and_staple(dmg_path: Path) -> None:
    """Notarize the DMG with Apple Notary Service and staple the ticket."""
    apple_id = os.environ.get("APPLE_ID")
    apple_password = os.environ.get("APPLE_PASSWORD")
    apple_team_id = os.environ.get("APPLE_TEAM_ID")

    if not apple_id or not apple_password or not apple_team_id:
        print("Apple credentials missing; skipping notarization.", flush=True)
        return

    print("Submitting DMG to Apple Notary Service (this may take a few minutes)...", flush=True)
    notary_cmd = [
        "xcrun",
        "notarytool",
        "submit",
        str(dmg_path),
        "--apple-id",
        apple_id,
        "--password",
        apple_password,
        "--team-id",
        apple_team_id,
        "--wait",
        "--output-format",
        "json",
    ]
    result = subprocess.run(notary_cmd, capture_output=True, text=True, check=False)

    payload: dict[str, object] = {}
    if result.stdout and result.stdout.strip():
        try:
            parsed = json.loads(result.stdout)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass

    submission_id = payload.get("id")
    status = payload.get("status")
    print(f"Notarization result: id={submission_id}, status={status}", flush=True)

    if result.returncode != 0 or status != "Accepted":
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr, flush=True)
        if not payload and result.stdout and result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr, flush=True)

        if submission_id:
            print(
                f"Fetching Apple notarization log for submission {submission_id}...",
                file=sys.stderr,
                flush=True,
            )
            log_res = subprocess.run(
                [
                    "xcrun",
                    "notarytool",
                    "log",
                    str(submission_id),
                    "--apple-id",
                    apple_id,
                    "--password",
                    apple_password,
                    "--team-id",
                    apple_team_id,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if log_res.stdout and log_res.stdout.strip():
                print(log_res.stdout.strip(), file=sys.stderr, flush=True)
            if log_res.stderr and log_res.stderr.strip():
                print(log_res.stderr.strip(), file=sys.stderr, flush=True)

        raise RuntimeError(
            f"Apple notarization failed for {dmg_path.name} (id={submission_id}, status={status})."
        )

    print("Stapling notarization ticket to DMG...", flush=True)
    subprocess.run(["xcrun", "stapler", "staple", str(dmg_path)], check=True)
    print("Validating stapled DMG...", flush=True)
    subprocess.run(["xcrun", "stapler", "validate", str(dmg_path)], check=True)


def build_macos(
    output_dir: Path,
    skip_signing: bool = False,
    skip_notarize: bool = False,
    strict_signing: bool = False,
    version: str | None = None,
) -> Path:
    """Build, sign, package, and notarize the macOS ARM64 DMG."""
    output_dir.mkdir(parents=True, exist_ok=True)
    nuitka_dir = output_dir / "nuitka_macos"
    ensure_clean_dir(nuitka_dir)

    keychain_ctx: KeychainContext | None = None
    try:
        if not skip_signing:
            keychain_ctx = setup_temp_keychain()
            if strict_signing and (not keychain_ctx or keychain_ctx.identity == "-"):
                raise RuntimeError(
                    "Signing secrets (MAC_CERTS_P12_BASE64 / MAC_CERTS_PASSWORD) or "
                    "Developer ID certificate missing, but --strict-signing was specified."
                )

        app_bundle = run_nuitka_build(nuitka_dir, version=version)

        # Signing
        if not skip_signing:
            identity = keychain_ctx.identity if keychain_ctx else "-"
            keychain_path = keychain_ctx.keychain_path if keychain_ctx else None
            sign_app_bundle(app_bundle, identity=identity, keychain_path=keychain_path)

        # DMG Creation
        dmg_name = get_artifact_name("macos", "arm64", "dmg", version=version)
        dmg_path = output_dir / dmg_name
        create_dmg(app_bundle, dmg_path)

        # Sign DMG if identity exists
        if not skip_signing and keychain_ctx and keychain_ctx.identity != "-":
            codesign = _codesign_bin()
            subprocess.run(
                [
                    codesign,
                    "--force",
                    "--timestamp",
                    "--sign",
                    keychain_ctx.identity,
                    "--keychain",
                    str(keychain_ctx.keychain_path),
                    str(dmg_path),
                ],
                check=True,
            )
            subprocess.run(
                [codesign, "--verify", "--verbose=2", str(dmg_path)],
                check=True,
            )

        # Notarization
        if not skip_notarize:
            if strict_signing and not (
                os.environ.get("APPLE_ID")
                and os.environ.get("APPLE_PASSWORD")
                and os.environ.get("APPLE_TEAM_ID")
            ):
                raise RuntimeError("Apple credentials missing, but --strict-signing was specified.")
            notarize_and_staple(dmg_path)

        print(f"Successfully generated macOS DMG at: {dmg_path}", flush=True)
        return dmg_path

    finally:
        if keychain_ctx:
            cleanup_temp_keychain(keychain_ctx.keychain_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build macOS DMG for ATBOffice.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=get_project_root() / "dist",
        help="Directory to place the final DMG artifact.",
    )
    parser.add_argument(
        "--skip-signing",
        action="store_true",
        help="Skip codesigning (or use ad-hoc signing).",
    )
    parser.add_argument(
        "--skip-notarize",
        action="store_true",
        help="Skip Apple notarization step.",
    )
    parser.add_argument(
        "--strict-signing",
        action="store_true",
        help="Fail build if Developer ID certificate or Apple credentials are missing.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Explicit version string for the release artifact.",
    )

    args = parser.parse_args(argv)
    build_macos(
        output_dir=args.output_dir,
        skip_signing=args.skip_signing,
        skip_notarize=args.skip_notarize,
        strict_signing=args.strict_signing,
        version=args.version,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
