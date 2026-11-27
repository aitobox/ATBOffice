# Phase 13A — `.vibeoffice` 100% 收口实施计划

> **For agentic workers:** Follow TDD task-by-task (`Phase 13A` spec on `main`). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the final three `.vibeoffice` parity gaps in `ATBOffice`: (1) WordNet `en.thes` offline thesaurus engine (`modules/common/thesaurus.py`) + Quire `ResearchTaskPane` (`Shift+F7`), (2) Quire interactive Draw Table pen & Eraser canvas tool modes (`canvas_table_tool.py` + `models/table.py`), and (3) Ledger `ENCODEURL` + offline `FILTERXML` & `EUROCONVERT` + 520-function parity contract.

**Architecture:** Isolate each subsystem behind narrow interfaces — a thread-safe lazy `ThesaurusEngine` consumed by `ResearchTaskPane`, a self-contained `canvas_table_tool` controller backed by pure `split_cell_at_x` / `split_cell_rows` / `merge_cells` table operations, and pure evaluator functions registered cleanly into `FUNCTION_REGISTRY`, `parser._XLFN_FUNCTIONS`, and `ALL_FUNCTIONS_CATALOG`.

**Tech Stack:** Python 3.12+, PySide6 (Qt 6), `lxml.etree` (XXE-hardened offline XML/XPath), `urllib.parse`, `pytest` + `pytest-qt`.

**Spec:** [2026-11-27-phase13a-vibeoffice-closure-design.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/superpowers/specs/2026-11-27-phase13a-vibeoffice-closure-design.md)

## Global Constraints

- Execute all Python/pytest/lint commands inside conda env `ATBOffice` with `QT_QPA_PLATFORM=offscreen PYTHONPATH="$WT/src:$WT"`.
- Every visible UI string uses `safe_tr()` with Chinese source text and matching English entry in `src/atboffice/resources/locale/source/zh-CN_to_en.json` (preserving 0-space-indent JSON formatting); every widget/pane implements `retranslate_ui()`.
- Colors come from `theme_tokens()` / `luna_2003.py`; fonts from `ui_font()`.
- Commands go through `ActionRegistry`; document edits go through `UndoService` (`canvas.run_undoable(...)`).
- Never check `PYTEST_CURRENT_TEST` in product code; never silently swallow exceptions (log via `logger.exception` / `logger.debug(..., exc_info=True)`).
- Never merge into `main` or push without explicit user confirmation.

---

### Task 1: WordNet Offline Thesaurus (`en.thes`) & Quire Research Task Pane

**Files:**
- Copy: `src/atboffice/resources/dict/en.thes`, `src/atboffice/resources/dict/LICENSES.txt`
- Create: `src/atboffice/modules/common/thesaurus.py`, `src/atboffice/modules/writer/panes/research_pane.py`, `tests/modules/common/test_thesaurus.py`, `tests/gui/test_phase13_quire_research_and_table_tools.py`
- Modify: `src/atboffice/modules/writer/panes/__init__.py`, `src/atboffice/ui/shell/quire_commands.py`, `src/atboffice/ui/shell/quire_window.py`, `src/atboffice/ui/shell/mac_menu.py`, `src/atboffice/ui/shell/quire_ribbon.py`, `src/atboffice/resources/locale/source/zh-CN_to_en.json`

**Interfaces:**
- Produces `ThesaurusSense`, `ThesaurusEntry`, `ThesaurusEngine`, `get_thesaurus_engine()` in `atboffice.modules.common.thesaurus`.
- Produces `ResearchTaskPane` in `atboffice.modules.writer.panes.research_pane` with `.search(query: str, service: str | None = None)`, `.insert_word(word: str) -> bool`, `.retranslate_ui()`.
- Produces `QuireWindow.open_research(service: str | None = None)` bound to `"research"` and `"thesaurus"` (`Shift+F7`).

- [ ] **Step 1: Write failing unit tests in `tests/modules/common/test_thesaurus.py`** covering lazy loading, exact lookup, inflection/stemming (`children`/`running`/`happily`/`walked`/`boxes`/`bigger`), antonyms, `near()`, and missing-file `FileNotFoundError`.
- [ ] **Step 2: Run `pytest tests/modules/common/test_thesaurus.py -v` and confirm FAIL (`ModuleNotFoundError`).**
- [ ] **Step 3: Implement `src/atboffice/modules/common/thesaurus.py`** with thread-safe lazy loading and `.vibeoffice` stem-reduction ladder.
- [ ] **Step 4: Run `pytest tests/modules/common/test_thesaurus.py -v` and confirm PASS.**
- [ ] **Step 5: Implement `src/atboffice/modules/writer/panes/research_pane.py`**, export in `panes/__init__.py`, wire `"research"` / `"thesaurus"` (`Shift+F7`) in `quire_commands.py`, `quire_window.py`, `mac_menu.py`, `quire_ribbon.py`, and add translations to `zh-CN_to_en.json`.
- [ ] **Step 6: Add GUI tests in `tests/gui/test_phase13_quire_research_and_table_tools.py`** verifying `Shift+F7`, `open_research()`, thesaurus stem lookup & undoable replace (`insert_word`), document search & navigation, back history, and `en` / `zh-CN` retranslation; run targeted pytest and confirm PASS.
- [ ] **Step 7: Commit Task 1** (`feat(quire): add offline WordNet thesaurus engine and Research task pane`).

---

### Task 2: Quire Interactive Draw Table Pen & Eraser Canvas Tools

**Files:**
- Create: `src/atboffice/modules/writer/views/canvas_table_tool.py`
- Modify: `src/atboffice/modules/writer/models/table.py`, `src/atboffice/modules/writer/views/canvas_view.py`, `src/atboffice/modules/writer/views/canvas_input.py`, `src/atboffice/modules/writer/views/canvas_paint.py`, `src/atboffice/ui/shell/quire_commands.py`, `src/atboffice/ui/shell/quire_window.py`
- Test: `tests/gui/test_phase13_quire_research_and_table_tools.py`

**Interfaces:**
- Produces `split_cell_rows(table, cell, num_rows=2)` and `split_cell_at_x(table, row_idx, col_idx, cut_pt)` in `atboffice.modules.writer.models.table`.
- Produces `WriterCanvasView.table_tool` (`None | "draw" | "erase"`), `WriterCanvasView.set_table_tool(kind)`, `WriterCanvasView.table_tool_changed = Signal(object)`.
- Produces `hit_test_table_cell`, `hit_test_internal_border`, `paint_table_tool_overlay`, `handle_table_tool_*` in `atboffice.modules.writer.views.canvas_table_tool`.

- [ ] **Step 1: Write failing model + canvas tool tests in `tests/gui/test_phase13_quire_research_and_table_tools.py`** covering `split_cell_at_x`, `split_cell_rows`, pen outside table (`1x1` custom width/height), pen inside cell horizontal/vertical split, eraser click merging adjacent cells across internal border, `Escape` exit, toolbar/Ribbon checked state sync, undo/redo, and `DocxWriter`/`DocxReader` round-trip.
- [ ] **Step 2: Run `pytest tests/gui/test_phase13_quire_research_and_table_tools.py -v` and confirm new tests FAIL.**
- [ ] **Step 3: Implement `split_cell_rows` and `split_cell_at_x` in `src/atboffice/modules/writer/models/table.py`** preserving full-table `grid_span` matrix invariants across rows.
- [ ] **Step 4: Implement `src/atboffice/modules/writer/views/canvas_table_tool.py`** and integrate with `canvas_view.py`, `canvas_input.py`, `canvas_paint.py`, `quire_commands.py`, and `quire_window.py`.
- [ ] **Step 5: Run `pytest tests/gui/test_phase13_quire_research_and_table_tools.py tests/gui/test_writer_canvas.py tests/gui/test_phase11_quire_ui_wiring.py -v` and confirm PASS.**
- [ ] **Step 6: Commit Task 2** (`feat(quire): add interactive Draw Table pencil and Eraser canvas tools`).

---

### Task 3: Ledger `ENCODEURL`, Offline `FILTERXML` & `EUROCONVERT`, and 520-Function Parity Gate

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/calc/fn_dynamic.py`, `src/atboffice/modules/spreadsheet/calc/parser.py`, `src/atboffice/modules/spreadsheet/calc/fn_info.py`
- Create: `tests/modules/spreadsheet/test_phase13_formula_parity.py`

**Interfaces:**
- Produces registered functions `ENCODEURL`, `FILTERXML`, `EUROCONVERT` in `DYNAMIC_FUNCTIONS` / `FUNCTION_REGISTRY` (520 total), `ENCODEURL` in `parser._XLFN_FUNCTIONS` and `fn_info.ALL_FUNCTIONS_CATALOG`.

- [ ] **Step 1: Write failing parity & formula tests in `tests/modules/spreadsheet/test_phase13_formula_parity.py`** testing `ENCODEURL`, `FILTERXML` (XPath scalar/array, XXE entity rejection, `#VALUE!`/`#N/A`), `EUROCONVERT` (EU rates, triangulation, `full_precision`, error cases), 520-function registry/catalog equality, `.vibeoffice` 498-function 100% coverage, and smoke calls across all 520 functions.
- [ ] **Step 2: Run `pytest tests/modules/spreadsheet/test_phase13_formula_parity.py -v` and confirm FAIL (`ENCODEURL` missing, `FILTERXML`/`EUROCONVERT` return `#N/A`).**
- [ ] **Step 3: Implement `ENCODEURL`, `FILTERXML`, and `EUROCONVERT` in `fn_dynamic.py`**, remove `"FILTERXML"`/`"EUROCONVERT"` from `PLACEHOLDER_STUBS`, update `parser.py` `_XLFN_FUNCTIONS`, and register `ENCODEURL` in `fn_info.py`.
- [ ] **Step 4: Run `pytest tests/modules/spreadsheet/test_phase13_formula_parity.py tests/modules/spreadsheet/test_function_wizard.py -v` and confirm PASS.**
- [ ] **Step 5: Commit Task 3** (`feat(ledger): add ENCODEURL, offline FILTERXML/EUROCONVERT, and 520-function parity gate`).

---

### Task 4: Full Phase 13A Verification Gate

- [ ] **Step 1:** Run `conda run --no-capture-output -n ATBOffice ruff check . && conda run --no-capture-output -n ATBOffice ruff format --check .`
- [ ] **Step 2:** Run `/opt/anaconda3/bin/mypy --python-executable /opt/anaconda3/envs/ATBOffice/bin/python src/atboffice/core`
- [ ] **Step 3:** Run `QT_QPA_PLATFORM=offscreen PYTHONPATH="$WT/src:$WT" conda run --no-capture-output -n ATBOffice python scripts/source_diff.py --check` and `scripts/audit_toolbars_parity.py`
- [ ] **Step 4:** Run `QT_QPA_PLATFORM=offscreen PYTHONPATH="$WT/src:$WT" conda run --no-capture-output -n ATBOffice pytest -n auto` (`0 failed`)
- [ ] **Step 5:** Confirm clean `git status` and present finishing options without auto-merging.
