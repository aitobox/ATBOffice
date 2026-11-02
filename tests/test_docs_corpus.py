import json
import subprocess
from pathlib import Path

import pytest


def test_docs_directory_structure():
    base = Path(__file__).parent / "docs"
    assert base.exists(), "tests/docs directory should exist"
    for category in ["word", "excel", "powerpoint"]:
        cat_dir = base / category
        assert cat_dir.is_dir(), f"{category} directory missing"


def test_full_corpus_gitignored():
    repo_root = Path(__file__).resolve().parents[1]
    res = subprocess.run(
        ["git", "check-ignore", "tests/docs/full_corpus/dummy.docx"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, "tests/docs/full_corpus/ must be ignored by git"


def test_extension_mapping():
    from scripts.fetch_corpora import get_app_for_extension
    assert get_app_for_extension(".docx") == "word"
    assert get_app_for_extension(".DOC") == "word"
    assert get_app_for_extension(".xlsx") == "excel"
    assert get_app_for_extension(".xls") == "excel"
    assert get_app_for_extension(".pptx") == "powerpoint"
    assert get_app_for_extension(".ppt") == "powerpoint"
    assert get_app_for_extension(".txt") is None


def test_pinned_sources_defined():
    from scripts.fetch_corpora import EXTENSIONS, SOURCES

    assert "libreoffice" in SOURCES
    assert "poi" in SOURCES
    assert "openxml-sdk" in SOURCES
    assert "word" in EXTENSIONS
    assert "excel" in EXTENSIONS
    assert "powerpoint" in EXTENSIONS


def test_full_corpus_manifest_if_downloaded():
    manifest_path = Path(__file__).parent / "docs" / "full_corpus" / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("Full corpus not downloaded yet")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(data) > 3000, "Corpus should contain over 3000 files"
    for item in data[:20]:
        assert "sha256" in item
        assert "file" in item
        assert (Path(__file__).parent / "docs" / "full_corpus" / item["file"]).exists()


def test_curated_docs_presence_and_size():
    base = Path(__file__).parent / "docs"
    total_size = 0
    file_count = 0
    extensions_found = set()
    for cat in ["word", "excel", "powerpoint"]:
        cat_dir = base / cat
        files = [p for p in cat_dir.rglob("*") if p.is_file() and not p.name.startswith(".")]
        assert len(files) >= 10, f"Expected at least 10 curated files in {cat}"
        for f in files:
            file_count += 1
            total_size += f.stat().st_size
            extensions_found.add(f.suffix.lower())

    assert {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}.issubset(extensions_found)
    assert total_size < 15 * 1024 * 1024, (
        f"Curated files total {total_size / (1024 * 1024):.2f}MB, exceeds 15MB"
    )


def test_curated_files_format_integrity():
    import zipfile

    base = Path(__file__).parent / "docs"
    valid_ooxml_count = 0
    valid_ole2_count = 0
    fuzz_malformed_count = 0

    for cat in ["word", "excel", "powerpoint"]:
        for f in (base / cat).rglob("*"):
            if not f.is_file() or f.name.startswith("."):
                continue
            assert f.stat().st_size > 0, f"File {f} is unexpectedly 0 bytes"
            ext = f.suffix.lower()
            if ext in {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm"}:
                try:
                    with zipfile.ZipFile(f) as z:
                        if "[Content_Types].xml" in z.namelist():
                            valid_ooxml_count += 1
                        else:
                            fuzz_malformed_count += 1
                except Exception:
                    fuzz_malformed_count += 1
            elif ext in {".doc", ".xls", ".ppt"}:
                with open(f, "rb") as fp:
                    hdr = fp.read(8)
                    if hdr == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" or hdr.startswith(b"\t\x00"):
                        valid_ole2_count += 1
                    else:
                        fuzz_malformed_count += 1

    assert valid_ooxml_count >= 70, (
        f"Expected at least 70 valid OOXML files, got {valid_ooxml_count}"
    )
    assert valid_ole2_count >= 60, (
        f"Expected at least 60 valid OLE2 files, got {valid_ole2_count}"
    )
    # Intentionally malformed/fuzz files from Bugzilla CVEs should also be present
    # for robustness testing
    assert fuzz_malformed_count > 0, (
        "Expected some real-world fuzz/corrupted test files from corpora"
    )
