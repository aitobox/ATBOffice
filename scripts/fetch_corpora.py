#!/usr/bin/env python3
"""Office Test Corpora Fetch & Curation Tool.

Ports and extends .vibeoffice/tools/ooxml/corpora.py to Python 3.12+.
Fetches pinned, sparse public test files from LibreOffice, Apache POI, and Open-XML-SDK
into a local, gitignored corpus directory and curates representative fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from typing import Any

# Pinned upstream repositories and commits known to contain high-value Office fixtures
SOURCES: dict[str, tuple[str, str, list[str]]] = {
    "libreoffice": (
        "https://github.com/LibreOffice/core",
        "2821d29a87b28785d74fa64d975465e4c99d4416",
        ["sw/qa", "sc/qa", "sd/qa", "oox/qa"],
    ),
    "poi": (
        "https://github.com/apache/poi",
        "ae62bb5116b9aee19ebd5834e3a82066132c9f7f",
        ["test-data"],
    ),
    "openxml-sdk": (
        "https://github.com/dotnet/Open-XML-SDK",
        "431ab05cf160248cc3885a4a766026d4f8243792",
        ["test"],
    ),
}

EXTENSIONS: dict[str, list[str]] = {
    "word": ["docx", "docm", "dotx", "dotm", "doc", "dot"],
    "excel": ["xlsx", "xlsm", "xltx", "xltm", "xls", "xlt"],
    "powerpoint": ["pptx", "pptm", "ppsx", "ppsm", "potx", "potm", "ppt", "pot", "pps"],
}

BY_EXT: dict[str, str] = {
    "." + ext.lower(): app for app, exts in EXTENSIONS.items() for ext in exts
}

LEDGER_FEATURES: list[tuple[str, str, str, str]] = [
    (
        "XLibur/XLibur",
        "cc7547ff9bf67077e47fbffc38d313b3c6cd31aa",
        "XLibur.Tests/Resource/TryToLoad/SlicersOnPivotAndTable.xlsx",
        "4dc1bd8cac0c5c50d15c7460ce2c5479974442c4ea6c7f441f35f3f77c70a280",
    ),
    (
        "XLibur/XLibur",
        "cc7547ff9bf67077e47fbffc38d313b3c6cd31aa",
        "XLibur.Tests/Resource/TryToLoad/Timelines_Missing_21232.xlsx",
        "662c40550a6b296deee93c744bc7bcb37a93196104ef907cd2dafea5a167f6b9",
    ),
    (
        "Ryvier/CoffeeSalesProject",
        "4b94ad3d35d7f50f385051d5adaac426d391e03f",
        "coffeeSalesProject.xlsx",
        "d8e288300dfb18e1912289ccfb4e346398667afd928151193be9868f9aaee048",
    ),
]


def get_app_for_extension(ext: str) -> str | None:
    """Return the application category ('word', 'excel', 'powerpoint') for a file extension."""
    if not ext:
        return None
    normalized = ext.strip().lower()
    if not normalized.startswith("."):
        normalized = "." + normalized
    return BY_EXT.get(normalized)


def git(folder: Path, *args: str, check: bool = True) -> str | None:
    """Execute a git command within the given directory."""
    res = subprocess.run(
        ["git", "-C", str(folder), *args],
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return res.stdout.strip() if res.returncode == 0 else None


def link_or_copy(source: Path, target: Path) -> None:
    """Safely create a relative symlink or copy the file if symlinks fail."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        target.unlink()
    try:
        # Use relative symlink
        rel_target = os.path.relpath(source, target.parent)
        os.symlink(rel_target, target)
    except (OSError, NotImplementedError):
        shutil.copy2(source, target)


def fetch_ledger_features(dest_dir: Path) -> list[dict[str, Any]]:
    """Download supplemental feature workbooks (slicers, timelines) with SHA-256 validation."""
    dest = dest_dir / "ledger-features"
    dest.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    for repo, commit, source_path, expected_digest in LEDGER_FEATURES:
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{source_path}"
        file_path = dest / Path(source_path).name
        if file_path.exists():
            data = file_path.read_bytes()
        else:
            try:
                with urllib.request.urlopen(url, timeout=60) as resp:
                    data = resp.read()
            except Exception as e:
                print(f"Warning: Failed to fetch {url}: {e}", file=sys.stderr)
                continue

        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_digest:
            raise ValueError(
                f"Fixture hash mismatch for {file_path.name}: expected {expected_digest}, got {digest}"
            )

        if not file_path.exists():
            file_path.write_bytes(data)

        manifest.append(
            {
                "file": f"excel/{file_path.name}",
                "repo": repo,
                "commit": commit,
                "path": source_path,
                "url": url,
                "sha256": digest,
                "size": len(data),
            }
        )

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def fetch_source(root: Path, name: str, url: str, commit: str, folders: list[str]) -> None:
    """Fetch sparse repository checkout for a specific source."""
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)

    git_dir = folder / ".git"
    if not git_dir.exists():
        if any(folder.iterdir()):
            raise ValueError(f"Refusing to replace non-empty directory {folder}")
        git(folder, "init", "-q")
        git(folder, "remote", "add", "origin", url)

    remote_url = git(folder, "remote", "get-url", "origin") or ""
    if remote_url.removesuffix(".git").rstrip("/") != url.removesuffix(".git").rstrip("/"):
        raise ValueError(f"Unexpected remote in {folder}: {remote_url} != {url}")

    current_head = git(folder, "rev-parse", "--verify", "HEAD", check=False)
    if current_head != commit:
        # Build patterns for all relevant extensions
        all_exts = sorted({k[1:] for k in BY_EXT} | {k[1:].upper() for k in BY_EXT})
        patterns = [f"/{d}/**/*.{ext}" for d in folders for ext in all_exts]
        git(folder, "sparse-checkout", "set", "--no-cone", *patterns)
        print(f"Fetching {name} at commit {commit}...", flush=True)
        git(folder, "fetch", "--depth=1", "--filter=blob:none", "origin", commit)
        git(folder, "checkout", "--detach", commit)

    print(f"[{name}] Ready at {commit}", flush=True)


def build_corpus_manifest(
    root: Path, selected_sources: list[str], source_root: Path | None = None
) -> list[dict[str, Any]]:
    """Scan checked-out files and link them into word/excel/powerpoint directories with manifest."""
    manifest: list[dict[str, Any]] = []
    base_source = source_root or root

    for name in selected_sources:
        folder = base_source / name
        if not (folder / ".git").exists():
            continue
        commit = git(folder, "rev-parse", "--verify", "HEAD", check=False) or ""
        raw_files = subprocess.check_output(["git", "-C", str(folder), "ls-files", "-z"]).decode(
            "utf-8", errors="surrogateescape"
        )
        files = [f for f in raw_files.split("\0") if f]

        for rel in sorted(files):
            file_path = folder / rel
            app = get_app_for_extension(file_path.suffix)
            if not app or not file_path.is_file():
                continue

            try:
                data = file_path.read_bytes()
            except OSError:
                continue

            path_key = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]
            target_link = root / app / f"{name}__{path_key}__{file_path.name}"
            link_or_copy(file_path, target_link)

            manifest.append(
                {
                    "source": name,
                    "commit": commit,
                    "path": rel,
                    "file": str(target_link.relative_to(root)),
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

    # Add ledger features into excel directory if downloaded
    lf_manifest = base_source / "ledger-features" / "manifest.json"
    if lf_manifest.exists():
        try:
            lf_data = json.loads(lf_manifest.read_text(encoding="utf-8"))
            for item in lf_data:
                src = base_source / "ledger-features" / Path(item["path"]).name
                if src.exists():
                    target = root / "excel" / f"supplemental__{src.name}"
                    link_or_copy(src, target)
                    manifest.append(
                        {
                            "source": "ledger-features",
                            "commit": item.get("commit", ""),
                            "path": item.get("path", ""),
                            "file": str(target.relative_to(root)),
                            "size": item.get("size", src.stat().st_size),
                            "sha256": item.get("sha256", ""),
                        }
                    )
        except Exception as e:
            print(f"Warning: Failed to parse ledger-features manifest: {e}", file=sys.stderr)

    manifest_file = root / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def curate_representative_samples(
    full_corpus_dir: Path,
    curated_base_dir: Path,
    per_category_limit: int = 25,
    max_total_bytes: int = 14 * 1024 * 1024,
) -> list[Path]:
    """Select a diverse, lightweight subset of real office documents for git commit."""
    manifest_path = full_corpus_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found in {full_corpus_dir}")

    manifest: list[dict[str, Any]] = json.loads(manifest_path.read_text(encoding="utf-8"))
    curated_files: list[Path] = []
    total_bytes = 0

    # Ensure target subdirectories exist
    categories = {
        "word": ["docx", "doc"],
        "excel": ["xlsx", "xls"],
        "powerpoint": ["pptx", "ppt"],
    }
    for cat, subdirs in categories.items():
        for s in subdirs:
            (curated_base_dir / cat / s).mkdir(parents=True, exist_ok=True)

    # Group files by (app, subformat)
    by_bucket: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in manifest:
        file_path = full_corpus_dir / item["file"]
        if not file_path.exists():
            continue
        ext = file_path.suffix.lower()
        size = item["size"]
        # Skip overly large individual files (> 1MB) to keep curated set bounded
        if size > 1024 * 1024 or size < 100:
            continue

        app = get_app_for_extension(ext)
        if not app:
            continue

        # Bucket into modern (docx/xlsx/pptx) or legacy (doc/xls/ppt)
        if ext in {".docx", ".docm"}:
            bucket = ("word", "docx")
        elif ext in {".doc", ".dot"}:
            bucket = ("word", "doc")
        elif ext in {".xlsx", ".xlsm"}:
            bucket = ("excel", "xlsx")
        elif ext in {".xls", ".xlt"}:
            bucket = ("excel", "xls")
        elif ext in {".pptx", ".pptm"}:
            bucket = ("powerpoint", "pptx")
        elif ext in {".ppt", ".pps"}:
            bucket = ("powerpoint", "ppt")
        else:
            continue

        by_bucket.setdefault(bucket, []).append(item)

    for (app, subformat), items in by_bucket.items():
        # Pick diverse selection: sort by size to take diverse range from small to medium
        sorted_items = sorted(items, key=lambda x: x["size"])
        # Take evenly spaced samples up to per_category_limit
        step = max(1, len(sorted_items) // per_category_limit)
        chosen = sorted_items[::step][:per_category_limit]

        for c in chosen:
            if total_bytes + c["size"] > max_total_bytes:
                break
            src = full_corpus_dir / c["file"]
            # Clean target filename: keep source and name
            target_name = f"{c['source']}__{Path(c['path']).name}"
            dst = curated_base_dir / app / subformat / target_name
            shutil.copy2(src, dst)
            curated_files.append(dst)
            total_bytes += c["size"]

    print(
        f"Curated {len(curated_files)} files into {curated_base_dir} (total {total_bytes / (1024 * 1024):.2f}MB)",
        flush=True,
    )
    return curated_files


def main() -> None:
    default_cache = Path(os.environ.get("ATBOFFICE_CORPORA_CACHE", Path.home() / ".cache" / "atboffice_corpora"))
    parser = argparse.ArgumentParser(description="Fetch and manage Office test corpora.")
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("tests/docs/full_corpus"),
        help="Destination directory for the full corpus.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=default_cache,
        help="Persistent cache directory outside repository for git checkouts.",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=list(SOURCES) + ["ledger-features"],
        default=list(SOURCES) + ["ledger-features"],
        help="Sources to fetch.",
    )
    parser.add_argument(
        "--curate",
        action="store_true",
        help="Curate representative samples into tests/docs/ after fetching.",
    )
    parser.add_argument(
        "--curate-dest",
        type=Path,
        default=Path("tests/docs"),
        help="Destination for curated files.",
    )
    args = parser.parse_args()

    dest = args.dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    cache_dir = args.cache_dir.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    sources_to_fetch = [s for s in args.sources if s in SOURCES]
    for s in sources_to_fetch:
        url, commit, folders = SOURCES[s]
        fetch_source(cache_dir, s, url, commit, folders)

    if "ledger-features" in args.sources:
        fetch_ledger_features(cache_dir)

    print("Building full corpus layout and manifest...", flush=True)
    manifest = build_corpus_manifest(dest, sources_to_fetch, source_root=cache_dir)
    print(f"Total corpus files indexed: {len(manifest)}", flush=True)

    for app in EXTENSIONS:
        count = sum(m["file"].startswith(app + "/") for m in manifest)
        print(f"  {app}: {count} files")

    if args.curate:
        print("Curating representative samples...", flush=True)
        curate_representative_samples(dest, args.curate_dest.resolve())


if __name__ == "__main__":
    main()
