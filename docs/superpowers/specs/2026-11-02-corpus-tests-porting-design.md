# Corpus Compatibility & Loss-Audit Test Suite Design

## Intent & The Why
To ensure that ATBOffice (Python 3.12+ / PySide6) matches or exceeds the real-world document compatibility and preservation fidelity of the original `.vibeoffice` project, we port `.vibeoffice`'s test suites and feature loss audit engines. This guarantees that loading, modifying, and saving real-world office files (`docx`, `xlsx`, `pptx`, and legacy `doc`, `xls`, `ppt`) retains XML structure, unknown ECMA-376 elements, formulas, cell styles, slide masters, and binary payloads without regression.

## Goals, Non-Goals, and Anti-Goals
* **Goals:**
  * Port the three loss-audit feature extractors from `.vibeoffice`:
    * Word (`tests/quire/loss-audit.py`): 50+ ECMA-376 features (comments, footnotes, tracked changes, bookmarks, tables, fields, equations, VBA, SmartArt).
    * Excel (`tests/ledger/loss-audit.py`): 30+ features (sheets, pivots, cell merges, validations, data bars, formulas, values, notes, threads).
    * PowerPoint (`tests/lectern/loss-audit.py`): 28 features (masters, layouts, shapes, media, transitions, animations, comments).
  * Build a robust audit module in `src/atboffice/deep/audit/` that parses UTF-8/UTF-16 XML, normalizes `mc:AlternateContent`, and reports structural differences.
  * Implement automated Pytest suites in `tests/unit/corpus/` running against the 150 curated production files in `tests/docs/`.
  * Implement an enterprise multi-process CLI tool `scripts/run_corpus_audit.py` capable of scanning the full 6,200+ files in `tests/docs/full_corpus/`.
* **Non-Goals:**
  * Re-architecting the existing PySide6 UI views in this task (this task focuses on format compatibility, headless roundtrip, and loss auditing).
  * Enforcing 100% losslessness on intentionally corrupted fuzz/CVE test documents (which must instead be handled gracefully with clear failure/exclusion status without process crashes).
* **Anti-Goals:**
  * Discarding unhandled parts silently without accounting for them in the audit ledger.

## Constraints
* Pure Python 3.12+ implementation; standard library only for the core audit extraction, with optional `openpyxl` / internal readers for cell comparisons.
* Tests must run cleanly in pytest (`PYTHONPATH=src pytest tests/unit/corpus/`).
* Must not crash when encountering fuzz or malformed files from the corpora.

## Approaches Considered
* **Approach 1: Layered Full Port (Audit Engine + Pytest Matrix + Multi-process CLI) [Chosen]**
  * *Tradeoffs:* Delivers both fast CI regression on 150 curated files and deep headless batch testing on 6,200+ files. Clean architectural separation in `src/atboffice/deep/audit/`.
* **Approach 2: Pytest-Only Scripting**
  * *Tradeoffs:* Fast to implement, but lacks CLI batch diagnostics for large corpora.
* **Approach 3: 1:1 Transliterated Ad-hoc Scripts**
  * *Tradeoffs:* Poor integration with pytest and Python module ecosystem.

## Technical Architecture
```text
src/atboffice/deep/audit/
├── __init__.py
├── core.py                 # XML text decoding, AuditSession, report aggregation
├── word.py                 # 50+ Word ECMA-376 feature extractors
├── excel.py                # 30+ Excel ECMA-376 feature extractors & cell comparator
└── presentation.py         # 28 PowerPoint ECMA-376 feature extractors

tests/unit/corpus/
├── __init__.py
├── test_word_corpus.py     # Roundtrip & loss audit on tests/docs/word/
├── test_excel_corpus.py    # Roundtrip & loss audit on tests/docs/excel/
└── test_presentation_corpus.py # Roundtrip & loss audit on tests/docs/powerpoint/

scripts/
└── run_corpus_audit.py     # Multi-process CLI runner for full 6,200+ files
```
