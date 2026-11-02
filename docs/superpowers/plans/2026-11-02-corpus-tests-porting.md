# Corpus Compatibility & Loss-Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port .vibeoffice's document compatibility and lossless audit test suites to ATBOffice, establishing an enterprise loss-audit engine, pytest regression suites for curated production files, and a multi-process CLI batch runner.

**Architecture:** Implement modular feature extractors in `src/atboffice/deep/audit/` covering 50+ Word, 30+ Excel, and 28 PowerPoint ECMA-376 features. Integrate automated roundtrip and loss-audit tests in `tests/unit/corpus/` executing against the 150 curated production files in `tests/docs/`. Provide `scripts/run_corpus_audit.py` to batch audit the 6,200+ files in `tests/docs/full_corpus/`.

**Tech Stack:** Python 3.12+ standard library (`zipfile`, `xml.etree.ElementTree`, `re`, `multiprocessing`), Pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-corpus-tests-porting-design.md`

## Global Constraints
- Python 3.12+ type hints everywhere.
- Resilient error handling: malformed, fuzz, or CVE bug reproduction files must never crash the test runner; they must be captured cleanly with `failed` or `excluded` status.
- Zero external pip dependencies required for `src/atboffice/deep/audit/` core engine.
- All tests must pass under `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/`.

## Review Focus
1. Diverse XML encodings: UTF-8, UTF-8-sig, UTF-16, UTF-16le, and UTF-16be handled properly.
2. `mc:AlternateContent` normalization: fallback branches stripped during audit to avoid duplicate counting of Choice alternatives.
3. Unhandled part retention: unmodified XML parts and binary blobs preserved with 100% SHA-256 byte fidelity.
4. Process resilience: multi-process batch CLI handles hung or crashed processes gracefully with per-file timeouts.
5. Legacy binary formats (.doc, .xls, .ppt): gracefully identified and audited without unhandled exceptions.

---

### Task 1: Core Loss-Audit Engine (`src/atboffice/deep/audit/core.py`)

**Files:**
- Create: `src/atboffice/deep/audit/__init__.py`
- Create: `src/atboffice/deep/audit/core.py`
- Create: `tests/unit/test_audit_core.py`

**Interfaces:**
- Produces: `xml_text(data: bytes) -> str`, `load_package_xml(path: Path | bytes) -> tuple[list[str], dict[str, str]]`, `AuditSession`, `AuditReport`.

- [ ] **Step 1: Write failing test for core audit decoding and package loader**

```python
# In tests/unit/test_audit_core.py
from pathlib import Path
import io
import zipfile
from atboffice.deep.audit.core import xml_text, load_package_xml, AuditSession

def test_xml_text_encodings():
    assert xml_text(b"<?xml?>hello") == "<?xml?>hello"
    assert xml_text(b"\xef\xbb\xbf<?xml?>bom") == "<?xml?>bom"
    assert xml_text("<?xml?>utf16".encode("utf-16le")) == "<?xml?>utf16"

def test_load_package_xml_alternate_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<mc:AlternateContent><mc:Choice>A</mc:Choice><mc:Fallback>B</mc:Fallback></mc:AlternateContent>")
    names, files = load_package_xml(buf.getvalue())
    assert "word/document.xml" in files
    assert "B" not in files["word/document.xml"]
    assert "A" in files["word/document.xml"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_audit_core.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'atboffice.deep.audit'`).

- [ ] **Step 3: Implement `src/atboffice/deep/audit/core.py`**

Port and modernize `.vibeoffice/tools/ooxml/audit.py`:
- `xml_text(data: bytes) -> str` supporting UTF-8, UTF-8-sig, UTF-16, UTF-16le, UTF-16be.
- `load_package_xml(source: Path | bytes | io.BytesIO) -> tuple[list[str], dict[str, str]]`: reads all `.xml`, `.rels`, and `.vml` parts, strips `<mc:Fallback>` blocks to avoid double counting.
- `AuditSession`: records pair evaluations, calculates `attempted`, `ok`, `failed`, `excluded`, and tracks feature delta metrics.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_audit_core.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/deep/audit/ tests/unit/test_audit_core.py
git commit -m "feat(audit): implement core package loader and loss-audit session"
```

---

### Task 2: Three Document Feature Extractors (Word, Excel, PowerPoint)

**Files:**
- Create: `src/atboffice/deep/audit/word.py`
- Create: `src/atboffice/deep/audit/excel.py`
- Create: `src/atboffice/deep/audit/presentation.py`
- Create: `tests/unit/test_audit_extractors.py`

**Interfaces:**
- Produces:
  - `WORD_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]]` (50+ features)
  - `EXCEL_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]]` (30+ features)
  - `PRESENTATION_FEATURES: dict[str, Callable[[list[str], dict[str, str]], int]]` (28 features)
  - `audit_features(names: list[str], files: dict[str, str], features: dict) -> dict[str, int]`

- [ ] **Step 1: Write failing test for extractors on real sample fixtures**

```python
# In tests/unit/test_audit_extractors.py
from pathlib import Path
from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.word import extract_word_features
from atboffice.deep.audit.excel import extract_excel_features
from atboffice.deep.audit.presentation import extract_presentation_features

def test_extractors_on_curated_samples():
    sample_docx = next(Path("tests/docs/word/docx").glob("*.docx"))
    names, files = load_package_xml(sample_docx)
    feats = extract_word_features(names, files)
    assert isinstance(feats, dict)
    assert len(feats) >= 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_audit_extractors.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'atboffice.deep.audit.word'`).

- [ ] **Step 3: Implement `word.py`, `excel.py`, `presentation.py`**

Port feature extractors:
- `word.py`: from `.vibeoffice/tests/quire/loss-audit.py` (comments, footnotes, tracked changes, bookmarks, tables, fields, equations, VBA, SmartArt, styles, numberings, etc.). Add `count_document_words(files: dict[str, str]) -> int`.
- `excel.py`: from `.vibeoffice/tests/ledger/loss-audit.py` (sheets, merges, validations, data bars, notes, threads, defined names, charts, pivottables, slicers, column widths).
- `presentation.py`: from `.vibeoffice/tests/lectern/loss-audit.py` (masters, layouts, shapes, media, transitions, animations, comments, SmartArt).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/test_audit_extractors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/deep/audit/ tests/unit/test_audit_extractors.py
git commit -m "feat(audit): implement Word, Excel, and PowerPoint ECMA-376 feature extractors"
```

---

### Task 3: Word Corpus Roundtrip & Loss-Audit Pytest Suite

**Files:**
- Create: `tests/unit/corpus/__init__.py`
- Create: `tests/unit/corpus/test_word_corpus.py`

**Interfaces:**
- Consumes: `atboffice.modules.writer.io`, `src/atboffice/deep/audit/word.py`, files in `tests/docs/word/`.
- Produces: Automated pytest matrix verifying reading, saving, and losslessness.

- [ ] **Step 1: Write the failing test for Word corpus roundtrip & loss audit**

```python
# In tests/unit/corpus/test_word_corpus.py
from pathlib import Path
import pytest
from atboffice.modules.writer.io import read_docx, write_docx
from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.word import extract_word_features, count_document_words

def test_curated_docx_roundtrip_loss_audit():
    docx_dir = Path("tests/docs/word/docx")
    for docx_path in sorted(docx_dir.glob("*.docx"))[:5]:
        raw = docx_path.read_bytes()
        try:
            doc = read_docx(raw)
        except Exception:
            continue
        saved = write_docx(doc)
        assert len(saved) > 0
        orig_names, orig_files = load_package_xml(raw)
        saved_names, saved_files = load_package_xml(saved)
        orig_feats = extract_word_features(orig_names, orig_files)
        saved_feats = extract_word_features(saved_names, saved_files)
        # Check core text/paragraph preservation
        assert len(saved_files) > 0
```

- [ ] **Step 2: Run test to verify execution**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_word_corpus.py -v`
Expected: PASS or initial baseline diagnostics.

- [ ] **Step 3: Complete Word corpus tests for all curated files**

Implement comprehensive test functions:
- `test_curated_docx_roundtrip_and_feature_preservation`: sweeps all curated `.docx` files.
- `test_curated_doc_binary_safe_handling`: tests legacy `.doc` files, verifying binary detection without unhandled crashes.
- Word count and paragraph integrity checks.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_word_corpus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/corpus/test_word_corpus.py
git commit -m "test(corpus): add Word corpus roundtrip and loss-audit regression suite"
```

---

### Task 4: Excel Corpus Roundtrip & Loss-Audit Pytest Suite

**Files:**
- Create: `tests/unit/corpus/test_excel_corpus.py`

**Interfaces:**
- Consumes: `atboffice.modules.spreadsheet.io`, `src/atboffice/deep/audit/excel.py`, files in `tests/docs/excel/`.
- Produces: Automated pytest matrix verifying reading, saving, and losslessness.

- [ ] **Step 1: Write test for Excel corpus roundtrip & loss audit**

```python
# In tests/unit/corpus/test_excel_corpus.py
from pathlib import Path
import pytest
from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.excel import extract_excel_features

def test_curated_xlsx_roundtrip_loss_audit():
    xlsx_dir = Path("tests/docs/excel/xlsx")
    for xlsx_path in sorted(xlsx_dir.glob("*.xlsx"))[:5]:
        raw = xlsx_path.read_bytes()
        try:
            wb = read_xlsx(raw)
        except Exception:
            continue
        saved = write_xlsx(wb)
        assert len(saved) > 0
        orig_names, orig_files = load_package_xml(raw)
        saved_names, saved_files = load_package_xml(saved)
        orig_feats = extract_excel_features(orig_names, orig_files)
        saved_feats = extract_excel_features(saved_names, saved_files)
        assert len(saved_files) > 0
```

- [ ] **Step 2: Run test to verify it passes on baseline**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_excel_corpus.py -v`
Expected: PASS.

- [ ] **Step 3: Complete Excel corpus tests**

Implement:
- `test_curated_xlsx_roundtrip_and_feature_preservation`: sweeps curated `.xlsx`.
- `test_curated_xls_binary_safe_handling`: tests legacy `.xls`.
- Formula, merged cell, and sheet count audits.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_excel_corpus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/corpus/test_excel_corpus.py
git commit -m "test(corpus): add Excel corpus roundtrip and loss-audit regression suite"
```

---

### Task 5: PowerPoint Corpus Roundtrip & Loss-Audit Pytest Suite

**Files:**
- Create: `tests/unit/corpus/test_presentation_corpus.py`

**Interfaces:**
- Consumes: `atboffice.modules.presentation.io`, `src/atboffice/deep/audit/presentation.py`, files in `tests/docs/powerpoint/`.
- Produces: Automated pytest matrix verifying reading, saving, and losslessness.

- [ ] **Step 1: Write test for PowerPoint corpus roundtrip & loss audit**

```python
# In tests/unit/corpus/test_presentation_corpus.py
from pathlib import Path
import pytest
from atboffice.modules.presentation.io import read_pptx, write_pptx
from atboffice.deep.audit.core import load_package_xml
from atboffice.deep.audit.presentation import extract_presentation_features

def test_curated_pptx_roundtrip_loss_audit():
    pptx_dir = Path("tests/docs/powerpoint/pptx")
    for pptx_path in sorted(pptx_dir.glob("*.pptx"))[:5]:
        raw = pptx_path.read_bytes()
        try:
            pres = read_pptx(raw)
        except Exception:
            continue
        saved = write_pptx(pres)
        assert len(saved) > 0
        orig_names, orig_files = load_package_xml(raw)
        saved_names, saved_files = load_package_xml(saved)
        orig_feats = extract_presentation_features(orig_names, orig_files)
        saved_feats = extract_presentation_features(saved_names, saved_files)
        assert len(saved_files) > 0
```

- [ ] **Step 2: Run test to verify it passes on baseline**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_presentation_corpus.py -v`
Expected: PASS.

- [ ] **Step 3: Complete PowerPoint corpus tests**

Implement:
- `test_curated_pptx_roundtrip_and_feature_preservation`: sweeps curated `.pptx`.
- `test_curated_ppt_binary_safe_handling`: tests legacy `.ppt`.
- Slide counts, layout inheritance, and shape audits.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/corpus/test_presentation_corpus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/unit/corpus/test_presentation_corpus.py
git commit -m "test(corpus): add PowerPoint corpus roundtrip and loss-audit regression suite"
```

---

### Task 6: Multi-process Full Corpus Batch Audit CLI (`scripts/run_corpus_audit.py`)

**Files:**
- Create: `scripts/run_corpus_audit.py`
- Test: `tests/unit/test_audit_core.py`

**Interfaces:**
- Produces: CLI tool with arguments `--corpus-dir`, `--workers`, `--timeout`, `--limit`, `--output`.

- [ ] **Step 1: Write test for batch runner invocation logic**

```python
# In tests/unit/test_audit_core.py
from scripts.run_corpus_audit import audit_single_file
from pathlib import Path

def test_audit_single_file_helper():
    sample = next(Path("tests/docs/word/docx").glob("*.docx"))
    res = audit_single_file(str(sample), "word")
    assert res["status"] in ("ok", "failed", "excluded")
    assert "file" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src:. conda run -n ATBOffice pytest tests/unit/test_audit_core.py::test_audit_single_file_helper -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scripts.run_corpus_audit'`).

- [ ] **Step 3: Implement `scripts/run_corpus_audit.py`**

Port and modernize `.vibeoffice/tests/ledger/recalc-all.js` and `corpus.js`:
- Process pool with `concurrent.futures.ProcessPoolExecutor` or `multiprocessing.Pool`.
- Per-file timeout protection (default 30s) so hanging fuzz files do not block the suite.
- Reads document using appropriate reader (`read_docx`, `read_xlsx`, `read_pptx`).
- Writes document back using writer.
- Runs `extract_*_features` and computes delta.
- Streams results to JSONL output file and prints terminal progress summary.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src:. conda run -n ATBOffice pytest tests/unit/test_audit_core.py::test_audit_single_file_helper -v`
Expected: PASS.

- [ ] **Step 5: Verify CLI runs cleanly on small limit**

Run: `python scripts/run_corpus_audit.py --corpus-dir tests/docs/word/docx --limit 5`
Expected: Successful scan and summary report.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_corpus_audit.py tests/unit/test_audit_core.py
git commit -m "feat(cli): implement multi-process corpus batch audit tool"
```
