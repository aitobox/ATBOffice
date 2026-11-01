"""macOS Nuitka build, codesigning, DMG packaging, and Apple notarization script."""

from __future__ import annotations

import argparse
import base64
import os
import shutil
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
    get_artifact_name,
    get_base_nuitka_args,
    get_nuitka_env,
    get_project_root,
)


class KeychainContext(NamedTuple):
    keychain_path: Path
    keychain_password: str
    identity: str


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
        print(f"Warning: Failed to set up temporary keychain: {exc}", file=sys.stderr)
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


def run_nuitka_build(output_dir: Path) -> Path:
    """Run Nuitka to build the standalone macOS app bundle."""
    base_args = get_base_nuitka_args(output_dir)
    macos_args = [
        "--macos-create-app-bundle",
        "--macos-app-name=ATBOffice",
        "--macos-app-mode=gui",
        "--macos-target-arch=arm64",
    ]
    cmd = base_args + macos_args
    env = get_nuitka_env()
    print(f"Running Nuitka macOS build:\n{' '.join(cmd)}")
    subprocess.run(cmd, check=True, env=env)

    app_path = output_dir / "ATBOffice.app"
    if not app_path.exists():
        alt_app = output_dir / "__main__.app"
        if alt_app.exists():
            alt_app.rename(app_path)
    return app_path


def sign_app_bundle(app_path: Path, identity: str = "-", keychain_path: Path | None = None) -> None:
    """Codesign the macOS app bundle with hardened runtime."""
    sign_cmd = [
        "codesign",
        "--deep",
        "--force",
        "--options",
        "runtime",
        "--timestamp",
        "--sign",
        identity,
    ]
    if keychain_path and keychain_path.exists():
        sign_cmd.extend(["--keychain", str(keychain_path)])
    sign_cmd.append(str(app_path))

    print(f"Signing app bundle with identity '{identity}'...")
    subprocess.run(sign_cmd, check=True)


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
        print(f"Creating DMG at {dmg_output_path}...")
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
        print("Apple credentials missing; skipping notarization.")
        return

    print("Submitting DMG to Apple Notary Service (this may take a few minutes)...")
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
    ]
    subprocess.run(notary_cmd, check=True)

    print("Stapling notarization ticket to DMG...")
    staple_cmd = ["xcrun", "stapler", "staple", str(dmg_path)]
    subprocess.run(staple_cmd, check=True)


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

        app_bundle = run_nuitka_build(nuitka_dir)

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
            subprocess.run(
                [
                    "codesign",
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

        # Notarization
        if not skip_notarize:
            if strict_signing and not (
                os.environ.get("APPLE_ID")
                and os.environ.get("APPLE_PASSWORD")
                and os.environ.get("APPLE_TEAM_ID")
            ):
                raise RuntimeError("Apple credentials missing, but --strict-signing was specified.")
            notarize_and_staple(dmg_path)

        print(f"Successfully generated macOS DMG at: {dmg_path}")
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
