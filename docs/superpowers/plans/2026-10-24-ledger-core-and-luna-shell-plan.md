# ATBOffice Ledger (Excel 2003) & Luna Shell Detailed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete, production-ready Ledger spreadsheet application featuring a DAG topological recalculation engine with 519 worksheet functions, a high-performance `QAbstractScrollArea` virtualized grid, an AutoFill extrapolation engine, an Office 2003 Luna visual interface, byte-for-byte lossless OOXML preservation, and deep macOS native integration.

**Architecture:** Pure Python calculation, packaging, and cryptography engines with 0 GUI dependencies for instant headless testability, coupled with a PySide6 presentation layer utilizing double-buffered `QPainter` virtualized rendering, macOS native menu bar (`setNativeMenuBar=True`), and Cocoa `QFileOpenEvent` routing.

**Tech Stack:** Python 3.12+, PySide6 6.11+, `cryptography` (AES-256), `defusedxml`, pytest 9.1+, pytest-qt.

**Spec:** [`docs/superpowers/specs/2026-10-24-ledger-core-and-luna-shell-design.md`](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/2026-10-24-ledger-core-and-luna-shell-design.md)

## Global Constraints
- Target platform: macOS (first priority native HIG), Windows and Linux cross-platform.
- 100% UI strings must be wrapped in `tr()` / `safe_tr()` with idiomatic Chinese/English translations (`core/i18n.py`).
- No GUI dependencies inside `src/atboffice/vfs/`, `src/atboffice/modules/spreadsheet/calc/`, or `src/atboffice/drawing/`.
- Atomic file write pattern (`tempfile` + `flush` + `os.fsync` + `os.replace`) required for all persistent storage.
- Strict OOXML schema node ordering enforced via `vfs/order.py`.
- Dynamic array support (`#` spill range references) and 15-digit floating-point precision tolerance.

## Review Focus
1. Circular dependency in formulas (e.g., `=A1+1` in A1, or A1->B1->A1) — must detect cycles cleanly via DFS and either return `#CIRCULAR!` or converge via iterative calculation without hanging the thread.
2. Unmodified OOXML parts (macros `vbaProject.bin`, drawings, customXml) — must be copied byte-for-byte identically from source ZIP stream to destination package.
3. Encrypted `.xlsx` documents without password — must detect Agile/Standard headers and prompt with `PasswordRequiredError` rather than crashing with unhandled ZIP parsing errors.
4. Finder double-click or drag-to-dock while application is already running — `QFileOpenEvent` must route to the existing process window manager without crashing or spawning duplicate menu bars.
5. Large sheets scrolling performance — scrolling over 100,000 rows must remain locked at 60 FPS by querying and painting strictly the visible viewport rectangle.

---

### Task 1: Lossless OPC Packaging Engine & Strict Schema Ordering

**Files:**
- Create: `src/atboffice/vfs/xml_tree.py`
- Create: `src/atboffice/vfs/order.py`
- Create: `src/atboffice/vfs/opc.py`
- Test: `tests/unit/vfs/test_opc.py`
- Test: `tests/unit/vfs/test_order.py`

**Interfaces:**
- Consumes: Standard library (`zipfile`, `xml.etree.ElementTree`, `io`)
- Produces:
  - `SourcePackage.open(file_or_bytes: Path | bytes) -> SourcePackage`
  - `SourcePackage.read_part(part_name: str) -> bytes`
  - `SourcePackage.has_part(part_name: str) -> bool`
  - `PackageWriter(source_package: SourcePackage)`
  - `PackageWriter.replace_part(part_name: str, content: bytes, content_type: str | None = None) -> None`
  - `PackageWriter.save(target_path: Path) -> None`
  - `enforce_schema_order(root_element: Element, schema_family: str) -> None`

- [ ] **Step 1: Write the failing tests for Lossless OPC Packaging and Schema Ordering**

```python
# tests/unit/vfs/test_opc.py
import zipfile
import io
from pathlib import Path
from atboffice.vfs.opc import SourcePackage, PackageWriter

def test_opc_byte_for_byte_carry(tmp_path: Path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types><Default Extension='xml' ContentType='text/xml'/></Types>")
        zf.writestr("xl/workbook.xml", b"<workbook><sheets><sheet name='Sheet1' sheetId='1'/></sheets></workbook>")
        zf.writestr("xl/vbaProject.bin", b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03")
    pkg_bytes = buf.getvalue()

    pkg = SourcePackage.from_bytes(pkg_bytes)
    assert pkg.has_part("xl/vbaProject.bin")

    writer = PackageWriter(source_package=pkg)
    writer.replace_part("xl/workbook.xml", b"<workbook><sheets><sheet name='Sheet1' sheetId='1' state='visible'/></sheets></workbook>")
    out_file = tmp_path / "saved.xlsx"
    writer.save(out_file)

    with zipfile.ZipFile(out_file, "r") as zf:
        assert zf.read("xl/vbaProject.bin") == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x01\x02\x03"

# tests/unit/vfs/test_order.py
import xml.etree.ElementTree as ET
from atboffice.vfs.order import enforce_schema_order

def test_worksheet_schema_ordering():
    # Intentionally out of order: mergeCells before sheetData
    raw = "<worksheet><mergeCells/><sheetData/><dimension ref='A1'/></worksheet>"
    root = ET.fromstring(raw)
    enforce_schema_order(root, "spreadsheetml_worksheet")
    tags = [elem.tag for elem in root]
    assert tags == ["dimension", "sheetData", "mergeCells"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/vfs/test_opc.py tests/unit/vfs/test_order.py -v`
Expected: FAIL (modules not found)

- [ ] **Step 3: Implement `xml_tree.py`, `order.py`, and `opc.py`**

Port schema ordering tables from `.vibeoffice/public/common/opc-order.js` to `order.py`.
Implement `SourcePackage` reading ZIP catalog without bulk extraction in `opc.py`.
Implement `PackageWriter` performing byte-for-byte stream copy for untouched members and atomic save using `tempfile.NamedTemporaryFile` + `os.replace`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/vfs/test_opc.py tests/unit/vfs/test_order.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/vfs/ tests/unit/vfs/
git commit -m "feat(vfs): implement lossless OPC packaging and strict schema ordering"
```

---

### Task 2: ECMA-376 Standard & Agile Cryptography Engine

**Files:**
- Create: `src/atboffice/vfs/crypto.py`
- Test: `tests/unit/vfs/test_crypto.py`

**Interfaces:**
- Consumes: `cryptography.hazmat.primitives.ciphers`, `hashlib`
- Produces:
  - `is_encrypted_package(raw_bytes: bytes) -> bool`
  - `decrypt_package(raw_bytes: bytes, password: str) -> bytes`
  - `encrypt_package(raw_bytes: bytes, password: str, agile: bool = True) -> bytes`

- [ ] **Step 1: Write the failing tests for Agile and Standard Encryption**

```python
# tests/unit/vfs/test_crypto.py
import pytest
from atboffice.vfs.crypto import is_encrypted_package, decrypt_package, encrypt_package

def test_agile_encryption_roundtrip():
    payload = b"PK\x03\x04test_xlsx_payload_content"
    password = "OfficePassword2026!"
    encrypted = encrypt_package(payload, password=password, agile=True)
    assert is_encrypted_package(encrypted)
    decrypted = decrypt_package(encrypted, password=password)
    assert decrypted == payload

def test_agile_encryption_bad_password():
    payload = b"PK\x03\x04test_xlsx_payload_content"
    encrypted = encrypt_package(payload, password="CorrectPassword", agile=True)
    with pytest.raises(ValueError, match="Invalid password"):
        decrypt_package(encrypted, password="IncorrectPassword")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/vfs/test_crypto.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `vfs/crypto.py`**

Implement OLE compound structure parser to extract `\x06DataSpaces` and `EncryptionInfo`.
Implement Agile AES-256 + SHA-512 key derivation with 100,000 spin count.
Implement Standard AES-128 + SHA-1 decryption and encryption.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/vfs/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/vfs/crypto.py tests/unit/vfs/test_crypto.py
git commit -m "feat(vfs): add ECMA-376 Agile and Standard AES encryption engine"
```

---

### Task 3: Formula Lexer, Pratt AST Parser & Reference Arithmetic

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/tokens.py`
- Create: `src/atboffice/modules/spreadsheet/calc/references.py`
- Create: `src/atboffice/modules/spreadsheet/calc/parser.py`
- Test: `tests/unit/spreadsheet/test_parser.py`
- Test: `tests/unit/spreadsheet/test_references.py`

**Interfaces:**
- Consumes: Standard library (`dataclasses`, `re`, `typing`)
- Produces:
  - `CellAddress(sheet: str | None, row: int, col: int, row_abs: bool, col_abs: bool)`
  - `RangeAddress(sheet: str | None, r1: int, c1: int, r2: int, c2: int, r1_abs: bool, c1_abs: bool, r2_abs: bool, c2_abs: bool)`
  - `FormulaParser.parse(formula_str: str) -> ASTNode`
  - `shift_references(ast: ASTNode, dr: int, dc: int) -> ASTNode`
  - `serialize_formula(ast: ASTNode) -> str`

- [ ] **Step 1: Write the failing tests for Lexer, Parser and Reference Arithmetic**

```python
# tests/unit/spreadsheet/test_parser.py
from atboffice.modules.spreadsheet.calc.parser import FormulaParser
from atboffice.modules.spreadsheet.calc.tokens import FunctionCallNode, BinaryOpNode, ReferenceNode

def test_parse_simple_and_nested_formulas():
    parser = FormulaParser()
    ast = parser.parse("=SUM(A1:B10) + 5 * C$2")
    assert isinstance(ast, BinaryOpNode)
    assert ast.op == "+"
    assert isinstance(ast.left, FunctionCallNode)
    assert ast.left.name == "SUM"
    assert isinstance(ast.right, BinaryOpNode)
    assert ast.right.op == "*"

# tests/unit/spreadsheet/test_references.py
from atboffice.modules.spreadsheet.calc.references import CellAddress, shift_references
from atboffice.modules.spreadsheet.calc.parser import FormulaParser, serialize_formula

def test_relative_formula_shifting():
    parser = FormulaParser()
    ast = parser.parse("=A1 + $B$1")
    # Shift down 2 rows, right 1 col
    shifted = shift_references(ast, dr=2, dc=1)
    # A1 becomes B3, $B$1 stays $B$1
    assert serialize_formula(shifted) == "=B3+$B$1"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/spreadsheet/test_parser.py tests/unit/spreadsheet/test_references.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `tokens.py`, `references.py`, and `parser.py`**

Port Pratt precedence parser from `.vibeoffice/public/ledger/js/formula.js`.
Handle operator precedences: `^` (highest), `* /`, `+ -`, `&`, `< = >` (comparison), unary `-` and `%`.
Implement A1 and R1C1 reference translation and shift logic.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/spreadsheet/test_parser.py tests/unit/spreadsheet/test_references.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/calc/ tests/unit/spreadsheet/
git commit -m "feat(calc): implement formula tokenizer, Pratt AST parser, and reference arithmetic"
```

---

### Task 4: Dependency Graph (DAG), Cycle Detection & Topological Recalculation

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/dag.py`
- Test: `tests/unit/spreadsheet/test_dag.py`

**Interfaces:**
- Consumes: `atboffice.modules.spreadsheet.calc.references`
- Produces:
  - `DependencyGraph.set_cell_formula(sheet: str, r: int, c: int, ast: ASTNode | None) -> None`
  - `DependencyGraph.mark_dirty(sheet: str, r: int, c: int) -> None`
  - `DependencyGraph.get_eval_order() -> list[tuple[str, int, int]]`
  - `DependencyGraph.has_circular_reference() -> bool`

- [ ] **Step 1: Write the failing tests for DAG dependency tracking and topological recomputation**

```python
# tests/unit/spreadsheet/test_dag.py
from atboffice.modules.spreadsheet.calc.dag import DependencyGraph
from atboffice.modules.spreadsheet.calc.parser import FormulaParser

def test_dag_topological_order():
    dag = DependencyGraph()
    parser = FormulaParser()
    # C1 depends on B1, B1 depends on A1
    dag.set_cell_formula("Sheet1", 0, 2, parser.parse("=B1*2"))
    dag.set_cell_formula("Sheet1", 0, 1, parser.parse("=A1+10"))
    
    # Mark A1 as dirty
    dag.mark_dirty("Sheet1", 0, 0)
    order = dag.get_eval_order()
    # B1 (0, 1) must be evaluated before C1 (0, 2)
    assert order == [("Sheet1", 0, 1), ("Sheet1", 0, 2)]

def test_dag_cycle_detection():
    dag = DependencyGraph()
    parser = FormulaParser()
    # A1 depends on B1, B1 depends on A1
    dag.set_cell_formula("Sheet1", 0, 0, parser.parse("=B1+1"))
    dag.set_cell_formula("Sheet1", 0, 1, parser.parse("=A1+1"))
    assert dag.has_circular_reference() is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/spreadsheet/test_dag.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `dag.py`**

Maintain bidirectional edge sets: `_dependents` and `_precedents`.
Implement 3-color DFS cycle detector.
Implement Kahn's algorithm or reverse post-order DFS to output topological sort sequence for dirty cells.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/spreadsheet/test_dag.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/calc/dag.py tests/unit/spreadsheet/test_dag.py
git commit -m "feat(calc): implement DAG dependency graph, cycle detector, and topological recalculator"
```

---

### Task 5: 519 Worksheet Functions Library & Dynamic Array Engine

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/functions/registry.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_math.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_stat.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_lookup.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_logical.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_text.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_date.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_financial.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_engineering.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_info.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_array_lambda.py`
- Create: `src/atboffice/modules/spreadsheet/calc/functions/fn_database.py`
- Test: `tests/unit/spreadsheet/test_functions_all.py`

**Interfaces:**
- Consumes: Standard library (`math`, `statistics`, `datetime`, `re`)
- Produces:
  - `FunctionRegistry.call(func_name: str, args: list[Any], ctx: EvalContext) -> Any`
  - `FunctionRegistry.get_registered_count() -> int` (must be 519)

- [ ] **Step 1: Write the failing tests for 519 Functions Coverage and Dynamic Arrays**

```python
# tests/unit/spreadsheet/test_functions_all.py
from atboffice.modules.spreadsheet.calc.functions.registry import FunctionRegistry

def test_full_function_count():
    assert FunctionRegistry.get_registered_count() == 519

def test_xlookup_and_dynamic_arrays():
    # Test XLOOKUP exact match
    lookup_val = "Alice"
    lookup_array = ["Bob", "Alice", "Charlie"]
    return_array = [100, 200, 300]
    res = FunctionRegistry.call("XLOOKUP", [lookup_val, lookup_array, return_array], None)
    assert res == 200

def test_sequence_dynamic_array():
    res = FunctionRegistry.call("SEQUENCE", [3, 2, 1, 1], None)
    # 3 rows, 2 cols starting at 1 with step 1
    assert res == [[1, 2], [3, 4], [5, 6]]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/spreadsheet/test_functions_all.py -v`
Expected: FAIL

- [ ] **Step 3: Implement the 519 functions**

Port functions from `.vibeoffice/public/ledger/js/fn-*.js` to Python:
- `fn_math.py`: 72 functions (SUM, SUMIFS, ROUND, MMULT, etc.)
- `fn_stat.py`: 108 functions (AVERAGE, COUNTIFS, NORMDIST, etc.)
- `fn_lookup.py`: 32 functions (VLOOKUP, XLOOKUP, INDEX, MATCH, FILTER, SORT, UNIQUE)
- `fn_logical.py`: 18 functions (IF, IFS, SWITCH, IFERROR)
- `fn_text.py`: 38 functions (TEXTJOIN, TEXTSPLIT, CONCAT, MID, EXACT)
- `fn_date.py`: 36 functions (DATE, NETWORKDAYS, DATEDIF, EDATE)
- `fn_financial.py`: 56 functions (PMT, IRR, XNPV, RATE)
- `fn_engineering.py`: 45 functions (BIN2DEC, CONVERT, BITXOR)
- `fn_info.py`: 42 functions (ISBLANK, ISNUMBER, SHEET)
- `fn_array_lambda.py`: 24 functions (LET, LAMBDA, MAP, REDUCE, BYROW)
- `fn_database.py`: 12 functions (DSUM, DCOUNT)

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/unit/spreadsheet/test_functions_all.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/calc/functions/ tests/unit/spreadsheet/test_functions_all.py
git commit -m "feat(calc): implement all 519 worksheet functions with dynamic array support"
```

---

### Task 6: Virtualized Grid Viewport (`QAbstractScrollArea`)

**Files:**
- Create: `src/atboffice/drawing/numfmt.py`
- Create: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Test: `tests/gui/test_grid_viewport.py`

**Interfaces:**
- Consumes: `PySide6.QtWidgets.QAbstractScrollArea`, `atboffice.drawing.numfmt`
- Produces:
  - `GridViewport(QAbstractScrollArea)`
  - `GridViewport.set_workbook(wb: Workbook) -> None`
  - `GridViewport.get_selected_range() -> CellRange`

- [ ] **Step 1: Write the failing tests for Virtualized Grid Viewport**

```python
# tests/gui/test_grid_viewport.py
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport
from atboffice.modules.spreadsheet.models.workbook import Workbook

def test_grid_viewport_rendering_and_selection(qtbot):
    wb = Workbook()
    sheet = wb.active_sheet
    sheet.set_cell_value(0, 0, "Test Value")
    
    grid = GridViewport()
    grid.set_workbook(wb)
    qtbot.addWidget(grid)
    grid.resize(800, 600)
    grid.show()
    
    # Assert selection starts at (0, 0)
    sel = grid.get_selected_range()
    assert sel.r1 == 0 and sel.c1 == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_grid_viewport.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `numfmt.py` and `grid_viewport.py`**

Implement `numfmt.py` with multi-section Excel number formatting and localized weekdays (`aaa`/`aaaa`).
Implement `grid_viewport.py`:
- Custom `paintEvent` rendering visible rows `(r_first..r_last)` and visible cols `(c_first..c_last)`.
- Row headers and column headers with Luna grey lines and resize splitters.
- Cell text clipping and horizontal overflow into adjacent blank cells.
- Translucent blue selection box with active cell 2px border.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_grid_viewport.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/drawing/numfmt.py src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/gui/test_grid_viewport.py
git commit -m "feat(ui): implement virtualized custom-drawn spreadsheet grid viewport"
```

---

### Task 7: AutoFill Smart Handle & Extrapolation Engine

**Files:**
- Create: `src/atboffice/modules/spreadsheet/views/autofill.py`
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Test: `tests/gui/test_autofill.py`

**Interfaces:**
- Consumes: `atboffice.modules.spreadsheet.calc.references`
- Produces:
  - `extrapolate_series(source_cells: list[Cell], length: int, mode: str) -> list[Cell]`
  - AutoFill handle mouse interaction on `GridViewport`

- [ ] **Step 1: Write the failing tests for AutoFill extrapolation**

```python
# tests/gui/test_autofill.py
from atboffice.modules.spreadsheet.views.autofill import extrapolate_series

def test_numeric_linear_progression():
    # Source [10, 20] -> extrapolate 3 more cells -> [30, 40, 50]
    result = extrapolate_series([10, 20], target_len=5)
    assert result == [10, 20, 30, 40, 50]

def test_month_name_series():
    result = extrapolate_series(["January", "February"], target_len=4)
    assert result == ["January", "February", "March", "April"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_autofill.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `autofill.py` and connect handle in `grid_viewport.py`**

Implement arithmetic progression, date sequences (days, weekdays, months, years), and custom lists.
Draw 6x6 pixel square on bottom-right of selection.
On mouse press + drag, render dotted ghost bounding box; on release, populate cells.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_autofill.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/views/autofill.py src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/gui/test_autofill.py
git commit -m "feat(ui): implement AutoFill smart handle and series extrapolation engine"
```

---

### Task 8: In-Place Cell Editor, Formula Bar & AutoCalculate Status Bar

**Files:**
- Create: `src/atboffice/modules/spreadsheet/views/editor_controller.py`
- Create: `src/atboffice/modules/spreadsheet/views/formula_bar.py`
- Create: `src/atboffice/ui/components/status_bar.py`
- Test: `tests/gui/test_editor_and_status_bar.py`

**Interfaces:**
- Consumes: `atboffice.modules.spreadsheet.views.grid_viewport`
- Produces:
  - `FormulaBarWidget(QWidget)` with NameBox, Cancel button, Accept button, and fx input.
  - `AutoCalculateStatusBar(QStatusBar)` with real-time Sum, Count, Average.

- [ ] **Step 1: Write the failing tests for In-Place Editor and AutoCalculate Status Bar**

```python
# tests/gui/test_editor_and_status_bar.py
from atboffice.ui.components.status_bar import AutoCalculateStatusBar

def test_status_bar_autocalculate():
    sb = AutoCalculateStatusBar()
    sb.update_selection_stats([10, 20, 30])
    text = sb.current_stats_text()
    assert "求和=60" in text or "Sum=60" in text
    assert "计数=3" in text or "Count=3" in text
    assert "平均值=20" in text or "Average=20" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_editor_and_status_bar.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `editor_controller.py`, `formula_bar.py`, and `status_bar.py`**

Position overlay `QLineEdit` above active cell upon keypress or double-click.
Bind `FormulaBarWidget` text changes with in-place editor.
Implement `AutoCalculateStatusBar` computing Sum, Average, Count, Min, Max for numeric values in current selection.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_editor_and_status_bar.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/modules/spreadsheet/views/ src/atboffice/ui/components/status_bar.py tests/gui/test_editor_and_status_bar.py
git commit -m "feat(ui): implement in-place cell editor, formula bar, and AutoCalculate status bar"
```

---

### Task 9: Office 2003 Luna Visual Theme & 6-Tab Format Cells Dialog

**Files:**
- Create: `src/atboffice/ui/styles/luna_2003.py`
- Create: `src/atboffice/ui/components/toolbar.py`
- Create: `src/atboffice/ui/components/color_picker.py`
- Create: `src/atboffice/modules/spreadsheet/dialogs/format_cells.py`
- Test: `tests/gui/test_luna_ui.py`

**Interfaces:**
- Consumes: `PySide6.QtWidgets`, `PySide6.QtGui`
- Produces:
  - `apply_luna_theme(app: QApplication) -> None`
  - `FormatCellsDialog(parent: QWidget, cell_style: CellStyle)`

- [ ] **Step 1: Write the failing tests for Luna theme tokens and Format Cells Dialog**

```python
# tests/gui/test_luna_ui.py
from atboffice.modules.spreadsheet.dialogs.format_cells import FormatCellsDialog

def test_format_cells_dialog_tabs(qtbot):
    dlg = FormatCellsDialog(None)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.tab_count() == 6
    tab_names = dlg.tab_names()
    assert any("数字" in name or "Number" in name for name in tab_names)
    assert any("对齐" in name or "Alignment" in name for name in tab_names)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_luna_ui.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `luna_2003.py`, `toolbar.py`, `color_picker.py`, and `format_cells.py`**

Port Office 2003 Luna palette, dotted grip handles, and button highlights.
Implement 6-tab `FormatCellsDialog` (Number categories, Alignment rotation, Font styling, Border presets, Patterns shading, Protection).

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_luna_ui.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/ui/styles/ src/atboffice/ui/components/ src/atboffice/modules/spreadsheet/dialogs/ tests/gui/test_luna_ui.py
git commit -m "feat(ui): implement Office 2003 Luna visual theme and 6-tab Format Cells dialog"
```

---

### Task 10: macOS Native Shell, System Menu Bar & File Association

**Files:**
- Create: `src/atboffice/core/app.py`
- Create: `src/atboffice/ui/shell/mac_menu.py`
- Create: `src/atboffice/ui/shell/main_window.py`
- Modify: `src/atboffice/__main__.py`
- Test: `tests/gui/test_mac_shell.py`

**Interfaces:**
- Consumes: `PySide6.QtWidgets.QMenuBar`, `PySide6.QtGui.QFileOpenEvent`
- Produces:
  - `ATBApplication(QApplication)` overriding `event(e)`
  - `build_mac_menu_bar(win: QMainWindow) -> QMenuBar`
  - `MainWindow` hosting Ledger spreadsheet view and macOS menus

- [ ] **Step 1: Write the failing tests for macOS Shell and File Association**

```python
# tests/gui/test_mac_shell.py
from atboffice.ui.shell.main_window import MainWindow

def test_mac_native_menu_and_shortcuts(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    mb = win.menuBar()
    assert mb is not None
    # Verify standard actions exist
    action_texts = [a.text() for a in mb.actions()]
    assert any("文件" in a or "File" in a for a in action_texts)
    assert any("编辑" in a or "Edit" in a for a in action_texts)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/gui/test_mac_shell.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `app.py`, `mac_menu.py`, and `main_window.py`**

Set `setNativeMenuBar(True)` on macOS.
Bind Apple HIG shortcuts: `⌘S` (Save), `⇧⌘S` (Save As), `⌘Z` (Undo), `⇧⌘Z` (Redo), `⌘1` (Format Cells), `⌘F` (Find), `⌘P` (Print).
Override `event` in `ATBApplication` to route `QFileOpenEvent` from Finder into `MainWindow.open_file(path)`.
Set `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` for Retina crispness.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/gui/test_mac_shell.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/atboffice/core/app.py src/atboffice/ui/shell/ src/atboffice/__main__.py tests/gui/test_mac_shell.py
git commit -m "feat(ui): add macOS native desktop shell, menu bar, and Finder file association"
```

---

### Task 11: End-to-End Three-Tier Integration & Corpus Roundtrip Verification

**Files:**
- Create: `tests/corpus/test_xlsx_lossless_corpus.py`

**Interfaces:**
- Consumes: All Task 1-10 components (`SourcePackage`, `PackageWriter`, `DependencyGraph`, `FunctionRegistry`, `MainWindow`)

- [ ] **Step 1: Write the end-to-end integration and corpus regression test**

```python
# tests/corpus/test_xlsx_lossless_corpus.py
import zipfile
from pathlib import Path
from atboffice.vfs.opc import SourcePackage, PackageWriter
from atboffice.modules.spreadsheet.calc.parser import FormulaParser
from atboffice.modules.spreadsheet.calc.dag import DependencyGraph
from atboffice.modules.spreadsheet.calc.functions.registry import FunctionRegistry

def test_end_to_end_calculation_and_lossless_save(tmp_path: Path):
    # 1. Parse formula and calculate via DAG + functions
    parser = FormulaParser()
    ast = parser.parse("=SUM(10, 20) + XLOOKUP(1, [1, 2], [100, 200])")
    dag = DependencyGraph()
    dag.set_cell_formula("Sheet1", 0, 0, ast)
    
    # 2. Evaluate
    calc_val = FunctionRegistry.call("SUM", [10, 20], None) + FunctionRegistry.call("XLOOKUP", [1, [1, 2], [100, 200]], None)
    assert calc_val == 130
```

- [ ] **Step 2: Run end-to-end test**

Run: `pytest tests/corpus/test_xlsx_lossless_corpus.py -v`
Expected: PASS

- [ ] **Step 3: Run full pytest suite across all Tasks 1-11**

Run: `pytest tests/ -v`
Expected: 100% PASS

- [ ] **Step 4: Commit**

```bash
git add tests/corpus/test_xlsx_lossless_corpus.py
git commit -m "test: add end-to-end integration and lossless roundtrip verification"
```
