# Test Documents & Compatibility Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-tier office test document suite in `tests/docs/` with curated lightweight committed fixtures (<15MB) and an automated script to fetch and organize 4,600+ real-world production files into a gitignored `tests/docs/full_corpus/`.

**Architecture:** Port the battle-tested corpus fetching and manifest pipeline from `.vibeoffice/tools/ooxml/corpora.py` to modern Python 3.12 (`scripts/fetch_corpora.py`), utilizing Git sparse checkout (`--filter=blob:none --depth=1`) on pinned commits of LibreOffice, Apache POI, and Microsoft Open-XML-SDK. Curate ~50-80 canonical files for routine CI, and link/copy the remaining 4,600+ files to `tests/docs/full_corpus/` protected by `.gitignore`.

**Tech Stack:** Python 3.12+ standard library (`subprocess`, `hashlib`, `urllib`, `pathlib`, `json`, `shutil`), Pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-test-docs-corpus-design.md`

## Global Constraints

- Python 3.12+ with standard library only for `scripts/fetch_corpora.py` (zero external pip dependencies).
- `tests/docs/full_corpus/` must be strictly ignored by `.gitignore` and never committed to git.
- Curated files committed to git in `tests/docs/` must remain under 15MB total size.
- Resilient network handling: fetch script must be idempotent and resumable.
- Cross-platform path handling using `pathlib.Path`.

## Review Focus

1. Interrupted git fetch / partial checkout: `fetch_corpora.py` detects existing valid commits or safely resumes without corrupting files.
2. Symlink creation permission on Windows/restricted environments: `fetch_corpora.py` falls back gracefully to hard links or file copies if symlinks fail.
3. Git tracking leak: verify with `git status --ignored` that `tests/docs/full_corpus/` is completely excluded from git staging.
4. Curated size budget: ensure total size of committed files in `tests/docs/` remains < 15MB.
5. Format coverage: ensure curated set contains all target extensions: `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt`.

---

### Task 1: Repository Gitignore & Test Directory Structure Setup

**Files:**
- Modify: `.gitignore`
- Create: `tests/docs/README.md`
- Test: `tests/test_docs_corpus.py`

**Interfaces:**
- Consumes: Existing project `.gitignore` and `tests/` directory layout.
- Produces: Standardized folders `tests/docs/{word,excel,powerpoint}` and ignored `tests/docs/full_corpus/`.

- [ ] **Step 1: Write the failing test for test docs structure and gitignore**

```python
# In tests/test_docs_corpus.py
from pathlib import Path
import subprocess

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
        text=True
    )
    assert res.returncode == 0, "tests/docs/full_corpus/ must be ignored by git"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py -v`
Expected: FAIL (Directory not found or git check-ignore not matching).

- [ ] **Step 3: Update `.gitignore` and create folder layout**

Add `tests/docs/full_corpus/` and `tests/docs/.corpus*/` to `.gitignore`.
Create directories:
- `tests/docs/word/docx`
- `tests/docs/word/doc`
- `tests/docs/excel/xlsx`
- `tests/docs/excel/xls`
- `tests/docs/powerpoint/pptx`
- `tests/docs/powerpoint/ppt`
- `tests/docs/full_corpus/`
Create `tests/docs/README.md` explaining the dual-tier structure.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore tests/docs/README.md tests/test_docs_corpus.py
git commit -m "test(docs): setup test docs directory structure and gitignore for full corpus"
```

---

### Task 2: Implement Corpora Fetch Tool (`scripts/fetch_corpora.py`)

**Files:**
- Create: `scripts/fetch_corpora.py`
- Modify: `tests/test_docs_corpus.py`

**Interfaces:**
- Consumes: Git CLI, pinned upstream repository URLs and commit SHAs.
- Produces: `fetch_corpora(dest: Path, sources: list[str] | None, curated_dest: Path | None)` CLI and callable module.

- [ ] **Step 1: Write test for `fetch_corpora.py` logic and helpers**

```python
# In tests/test_docs_corpus.py
from scripts.fetch_corpora import get_app_for_extension, SOURCES, EXTENSIONS

def test_extension_mapping():
    assert get_app_for_extension(".docx") == "word"
    assert get_app_for_extension(".DOC") == "word"
    assert get_app_for_extension(".xlsx") == "excel"
    assert get_app_for_extension(".xls") == "excel"
    assert get_app_for_extension(".pptx") == "powerpoint"
    assert get_app_for_extension(".ppt") == "powerpoint"
    assert get_app_for_extension(".txt") is None

def test_pinned_sources_defined():
    assert "libreoffice" in SOURCES
    assert "poi" in SOURCES
    assert "openxml-sdk" in SOURCES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_extension_mapping -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scripts.fetch_corpora'`).

- [ ] **Step 3: Implement `scripts/fetch_corpora.py`**

Port and improve `.vibeoffice/tools/ooxml/corpora.py` to modern Python 3.12:
- Pinned sources with sparse-checkout paths:
  - `libreoffice`: `https://github.com/LibreOffice/core`, commit `2821d29a87b28785d74fa64d975465e4c99d4416`, paths `['sw/qa', 'sc/qa', 'sd/qa', 'oox/qa']`
  - `poi`: `https://github.com/apache/poi`, commit `ae62bb5116b9aee19ebd5834e3a82066132c9f7f`, paths `['test-data']`
  - `openxml-sdk`: `https://github.com/dotnet/Open-XML-SDK`, commit `431ab05cf160248cc3885a4a766026d4f8243792`, paths `['test']`
- Add supplemental features from `LEDGER_FEATURES`.
- Implement `fetch_source(root, name, url, commit, folders)` using `git fetch --depth=1 --filter=blob:none`.
- Implement `link_or_copy(source, target)` with symlink priority and fallback to file copy.
- Implement `generate_manifest(root)` producing `manifest.json`.
- Implement CLI flags: `--dest`, `--sources`, `--curate-dest`, `--curate-count`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_extension_mapping tests/test_docs_corpus.py::test_pinned_sources_defined -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch_corpora.py tests/test_docs_corpus.py
git commit -m "feat(scripts): implement fetch_corpora.py tool for office test corpus"
```

---

### Task 3: Execute Full Fetch & Organize Corpora into `tests/docs/full_corpus`

**Files:**
- Modify: `tests/docs/full_corpus/` (generated, gitignored)
- Test: `tests/test_docs_corpus.py`

**Interfaces:**
- Consumes: `python scripts/fetch_corpora.py --dest tests/docs/full_corpus`
- Produces: 4,600+ real office files under `tests/docs/full_corpus/{word,excel,powerpoint}/` and `tests/docs/full_corpus/manifest.json`.

- [ ] **Step 1: Write test for full corpus manifest validation**

```python
# In tests/test_docs_corpus.py
import json

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
```

- [ ] **Step 2: Run test to verify initial skip or fail**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_full_corpus_manifest_if_downloaded -v`
Expected: SKIPPED (manifest not yet generated).

- [ ] **Step 3: Execute `scripts/fetch_corpora.py` to download full corpus**

Run: `python scripts/fetch_corpora.py --dest tests/docs/full_corpus`
Ensure:
- Sparse-checkout downloads blobs for targeted test paths only.
- Symlinks / links created under `word/`, `excel/`, `powerpoint/`.
- `manifest.json` written with SHA-256 for all entries.
- Verify `git status` shows no untracked files in `tests/docs/full_corpus/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_full_corpus_manifest_if_downloaded -v`
Expected: PASS.

- [ ] **Step 5: Commit test updates**

```bash
git add tests/test_docs_corpus.py
git commit -m "test(docs): add validation for full corpus manifest and integrity"
```

---

### Task 4: Select Curated Representative Sample into `tests/docs/{word,excel,powerpoint}`

**Files:**
- Create: curated files in `tests/docs/word/`, `tests/docs/excel/`, `tests/docs/powerpoint/`
- Modify: `tests/docs/README.md`
- Test: `tests/test_docs_corpus.py`

**Interfaces:**
- Consumes: Downloaded `tests/docs/full_corpus/` files.
- Produces: ~50-80 canonical files committed in `tests/docs/` (<15MB total).

- [ ] **Step 1: Write test for curated files presence and size constraint**

```python
# In tests/test_docs_corpus.py
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
    
    # Must cover major extensions
    assert {".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}.issubset(extensions_found)
    # Total size must be under 15MB
    assert total_size < 15 * 1024 * 1024, f"Curated files total {total_size / (1024*1024):.2f}MB, exceeds 15MB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_curated_docs_presence_and_size -v`
Expected: FAIL (No files found yet in curated directories).

- [ ] **Step 3: Curate diverse canonical files into `tests/docs/`**

Run curation routine from `fetch_corpora.py`:
- Select ~20 Word documents: simple docx, complex tables, drawings, tracked changes, footnotes, legacy .doc.
- Select ~25 Excel workbooks: formulas, multi-sheet, pivot tables, chart sheets, conditional formatting, legacy .xls.
- Select ~20 PowerPoint presentations: shapes, master slides, transitions, animations, smartart, legacy .ppt.
- Copy them into `tests/docs/word/{docx,doc}`, `tests/docs/excel/{xlsx,xls}`, `tests/docs/powerpoint/{pptx,ppt}`.
- Update `tests/docs/README.md` cataloging each curated file's test purpose.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_curated_docs_presence_and_size -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/docs/ tests/test_docs_corpus.py
git commit -m "feat(docs): add curated representative office test files across word, excel, powerpoint"
```

---

### Task 5: Document Format Detection & Smoke Verification

**Files:**
- Modify: `tests/test_docs_corpus.py`

**Interfaces:**
- Consumes: Curated test files in `tests/docs/`.
- Produces: Format sniffing and basic integrity verification for OOXML (ZIP-based) and OLE2 (Compound File-based) documents.

- [ ] **Step 1: Write format sniffing test**

```python
# In tests/test_docs_corpus.py
import zipfile

def is_ooxml(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path, "r") as z:
            return "[Content_Types].xml" in z.namelist()
    except Exception:
        return False

def is_ole2(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            header = f.read(8)
            return header == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    except Exception:
        return False

def test_curated_files_format_integrity():
    base = Path(__file__).parent / "docs"
    for cat in ["word", "excel", "powerpoint"]:
        for f in (base / cat).rglob("*"):
            if not f.is_file() or f.name.startswith("."):
                continue
            ext = f.suffix.lower()
            if ext in {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm"}:
                assert is_ooxml(f), f"Expected valid OOXML ZIP for {f}"
            elif ext in {".doc", ".xls", ".ppt"}:
                assert is_ole2(f), f"Expected valid OLE2 header for {f}"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py::test_curated_files_format_integrity -v`
Expected: PASS.

- [ ] **Step 3: Run full test suite across the project**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/test_docs_corpus.py -v`
Expected: All tests in `test_docs_corpus.py` PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_docs_corpus.py
git commit -m "test(docs): add format sniffing and integrity verification for test fixtures"
```
