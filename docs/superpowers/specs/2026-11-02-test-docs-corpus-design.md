# Test Documents & Compatibility Corpus Design

## Intent & The Why
To ensure enterprise-grade robustness and compatibility for ATBOffice (Python / PySide6 port), the project requires real-world production documents (DOC/DOCX, XLS/XLSX, PPT/PPTX) to thoroughly verify:
1. Low-level document format parsing, formula calculation, and lossless save/round-trip fidelity (headless batch & loss audit).
2. High-level layout, font rendering, canvas painting, and pagination parity against reference outputs.

## Goals, Non-Goals, and Anti-Goals
* **Goals:**
  * Establish a clean, standardized directory structure under `tests/docs/` categorized by document type (`word/`, `excel/`, `powerpoint/`) and extension (`docx`, `doc`, `xlsx`, `xls`, `pptx`, `ppt`).
  * Integrate a curated set (~50-80 high-value, small footprint files, total < 15MB) into `tests/docs/` committed to git for instant local pytest and offline CI regression.
  * Provide a robust Python script `scripts/fetch_corpora.py` (ported from `.vibeoffice/tools/ooxml/corpora.py`) that uses git sparse-checkout (`--filter=blob:none --depth=1`) to pull the full 4,600+ real-world file corpus from LibreOffice QA, Apache POI, and Microsoft Open-XML-SDK.
  * Organize the full 4,600+ files into `tests/docs/full_corpus/` with a verifiable `manifest.json`.
  * Ensure `tests/docs/full_corpus/` is strictly ignored in `.gitignore` to prevent git repository bloat.
* **Non-Goals:**
  * Committing the full 4,600+ files or gigabytes of binary fixtures into git history.
  * Implementing the full rendering engine changes in this task (this task establishes the test file infrastructure).
* **Anti-Goals:**
  * Generating synthetic/fake empty office files that do not reflect real-world user bug reports or edge cases.

## Constraints
* Full corpus must reside locally in `tests/docs/full_corpus/` and be ignored by `.gitignore`.
* Fetch script must be resilient: support resumption, handle sparse checkout failures gracefully, verify SHA-256 hashes, and avoid cloning full repo histories.
* Curated subset must be strictly bounded in size (<15MB total) and contain zero copyright-encumbered proprietary private leaks (relying strictly on public open-source QA corpora).

## Approaches Considered
* **Approach 1: Dual-tier Strategy (Curated committed subset + local full corpus via automated tool, gitignored) [Chosen]**
  * *Tradeoffs:* Combines zero-network out-of-the-box CI testing with immediate access to 4,600+ real production edge-case files for deep loss audits. Protects git repo size while fulfilling user requirement.
* **Approach 2: Monolithic Local Download without Curation**
  * *Tradeoffs:* Every CI runner or fresh clone would require downloading hundreds of megabytes before basic tests can run.
* **Approach 3: Pure External Corpora (No files in repo, exact .vibeoffice mirror)**
  * *Tradeoffs:* Tests fail or are skipped on any clean environment without manual external setup.

## Technical Architecture & Implementation Steps
1. **Repository Configuration:**
   * Update `.gitignore` to ignore `/tests/docs/full_corpus/` and `/tests/docs/**/full/`.
2. **Directory Layout:**
   ```
   tests/docs/
   ├── word/
   │   ├── docx/
   │   └── doc/
   ├── excel/
   │   ├── xlsx/
   │   └── xls/
   ├── powerpoint/
   │   ├── pptx/
   │   └── ppt/
   ├── full_corpus/            # [gitignored] Full 4600+ files
   │   ├── manifest.json
   │   ├── word/
   │   ├── excel/
   │   └── powerpoint/
   └── README.md
   ```
3. **Corpora Fetch Tool (`scripts/fetch_corpora.py`):**
   * Port logic from `.vibeoffice/tools/ooxml/corpora.py` to idiomatic Python 3.12.
   * Target upstream pinned commits:
     * `libreoffice`: `https://github.com/LibreOffice/core` (`sw/qa`, `sc/qa`, `sd/qa`, `oox/qa`)
     * `poi`: `https://github.com/apache/poi` (`test-data`)
     * `openxml-sdk`: `https://github.com/dotnet/Open-XML-SDK` (`test`)
     * `ledger-features`: pinned supplemental workbooks for slicers/timelines
   * Sparse-checkout with blob filter: `git fetch --depth=1 --filter=blob:none origin <commit>`.
   * Export/link files to `tests/docs/full_corpus/` with SHA-256 manifest.
   * Curate representative samples into `tests/docs/{word,excel,powerpoint}/`.
4. **Verification & Smoke Test:**
   * Add `tests/test_docs_corpus.py` to verify curated files and full corpus integrity (manifest validation, non-empty, loadable).

## Left to Builder
* Precise selection of the ~50-80 curated samples from the corpus (choosing key representative cases: complex tables, charts, comments, drawingML, password-protected, legacy binary OLE2).
