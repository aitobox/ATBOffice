# [Quire] GitHub Flavored Markdown (含图片 ZIP) 与 RTF 互转 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement comprehensive Markdown (GFM, tables, alerts, tasklists, ZIP with pictures) and RTF 1.5 bidirectional I/O for Quire word processing module in Python 3.12+ / PySide6.

**Architecture:** Create `markdown_io.py` and `rtf_io.py` in `src/atboffice/modules/writer/io/`, integrating tightly with Quire's `Document` DOM tree. Export public interfaces from `src/atboffice/modules/writer/io/__init__.py`. Provide comprehensive unit test suite in `tests/unit/writer/test_markdown_rtf.py`.

**Tech Stack:** Python 3.12+, standard library (`zipfile`, `io`, `re`, `pathlib`, `typing`), PySide6 / Quire DOM (`Document`, `Paragraph`, `Table`, `RunProperties`, `ParagraphProperties`).

**Spec:** `docs/superpowers/specs/issue-34-markdown-rtf-interop-spec.md`

## Global Constraints
- Target branch: `main` via feature branch `agent/issue-34-markdown-rtf-interop`.
- Pure Python 3.12+ with type hints.
- Zero extra external dependencies (rely on standard library and existing PySide6 / Quire architecture).
- Full UTF-8 non-ASCII / Unicode text support.
- All existing tests in `tests/unit/writer/` must continue to pass with zero regressions.

---

### Task 1: Scaffolding and Initial Test Cases
**Files:**
- Create: `tests/unit/writer/test_markdown_rtf.py`

**Interfaces:**
- Consumes: `src/atboffice/modules/writer/io/__init__.py`
- Produces: Failing test cases for markdown read/write, zip read/write, and rtf read/write.

- [ ] **Step 1: Write failing unit tests for Markdown and RTF I/O**
- [ ] **Step 2: Run pytest to verify failure on missing modules**

---

### Task 2: Implement Markdown Reader and Writer (`markdown_io.py`)
**Files:**
- Create: `src/atboffice/modules/writer/io/markdown_io.py`
- Modify: `src/atboffice/modules/writer/io/__init__.py`

**Interfaces:**
- Produces: `read_markdown`, `write_markdown`, `read_markdown_zip`, `write_markdown_zip`, `MarkdownReader`, `MarkdownWriter`

- [ ] **Step 1: Implement GFM block parser (headings, paragraphs, blockquotes, alerts, code blocks, lists, tasklists, pipe tables, footnotes, front matter)**
- [ ] **Step 2: Implement inline parser (bold, italic, strikethrough, code, links, images)**
- [ ] **Step 3: Implement Markdown writer (Document -> Markdown text & extracted images)**
- [ ] **Step 4: Implement Markdown ZIP reader & writer**
- [ ] **Step 5: Run pytest on Markdown tests to confirm pass**

---

### Task 3: Implement RTF 1.5 Reader and Writer (`rtf_io.py`)
**Files:**
- Create: `src/atboffice/modules/writer/io/rtf_io.py`
- Modify: `src/atboffice/modules/writer/io/__init__.py`

**Interfaces:**
- Produces: `read_rtf`, `write_rtf`, `RtfReader`, `RtfWriter`

- [ ] **Step 1: Implement RTF tokenizer and group parser (fonttbl, colortbl, stylesheet, controls, unicode `\\uN?`, hex `\\'xx`)**
- [ ] **Step 2: Implement RTF Document builder (paragraphs, character runs, alignment, indents, spacing, tables `\\intbl`, fields/links, pictures)**
- [ ] **Step 3: Implement RTF writer (Document -> RTF 1.5 bytes)**
- [ ] **Step 4: Run pytest on RTF tests to confirm pass**

---

### Task 4: Full Suite Verification & Final Polish
**Files:**
- Modify: `src/atboffice/modules/writer/io/__init__.py`
- Test: `tests/unit/writer/test_markdown_rtf.py` and full suite `tests/unit/writer/`

- [ ] **Step 1: Run comprehensive tests covering roundtrips and edge cases**
- [ ] **Step 2: Run all writer unit tests to verify zero regressions**
- [ ] **Step 3: Transition state to `reviewing`**
