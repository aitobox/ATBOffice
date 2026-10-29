# ATBOffice Phase 2: 1:1 完整全量移植与核心架构补完详细实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ATBOffice 从 JavaScript 原版向 Python 3.12 / PySide6 的 1:1 全量功能等价移植，交付 28 套完整工具栏（300+ 动作项）、纯 Python 驱动的 XLSX 读写器、完整的 Workbook 多工作表与底部 TabBar 交互、跨表公式依赖计算、电子表格浮动图形图层、DOCX 与 PPTX 复杂特性全量解析，以及全量 7 国语言本地化。

**Architecture:**
- **GUI 层**：基于数据驱动的 `ActionRegistry` 与 `OfficeToolBarBuilder` 映射原版 `ribbonSpec` / `ui.toolbar`，提供带有菜单的 `OfficeSplitButton` 与 `OfficeDropDownButton`；
- **电子表格核心**：重构 `SpreadsheetView` 接入 `WorkbookModel` 托管容器，在网格底部实现经典 Office 2003 风格的 `SheetTabBar`，升级公式求值器支持跨工作表引用；
- **I/O 与文件系统**：构建纯 Python 的 `xlsx_reader.py` 与 `xlsx_writer.py`，强化 `vfs/opc.py` 的 Part 级字节流原样透传（Preserve）机制，扩充 `docx_reader.py` 与 `pptx_reader.py` 的复杂 XML 节点解析；
- **浮动对象层**：在表格网格上方构建透明矢量对象层 `SpreadsheetObjectLayer`，支持自由缩放拖拽图片/形状/图表并与 DrawingML 联动。

**Tech Stack:** Python 3.12+, PySide6 (Qt 6.7+), pytest, pytest-qt, ElementTree, zipfile.

**Spec:** `docs/superpowers/specs/2026-10-29-phase2-1to1-reconstruction-design.md`

## Global Constraints
- Python 3.12+ (全类型注解与 strict typing)
- GUI 框架：PySide6 (Qt 6.7+)
- 严禁引入重型第三方 Office 解析库（如 openpyxl, python-docx, python-pptx），必须坚持纯 Python 标准库 + 现有 DOM 模型
- 100% 界面文字必须绑定 `safe_tr()` 动态翻译，严禁硬编码中文字符串
- 未接入底层具体业务的工具栏动作一律注册并绑定状态栏非阻塞提示（`statusBar.showMessage("...", 2000)`），严禁弹出阻塞模态窗

## Review Focus (五大高危盲区与故障模式)
1. **未修改部件破坏 (Lossless Corruption)**：打开包含 VBA 宏（`.xlsm` / `.docm` 的 `vbaProject.bin`）或特殊媒体流的文件再保存后宏丢失。*测试约束：必须对二进制不可识别 Part 进行 100% 原样字节比对校验。*
2. **跨表循环引用 (Cross-sheet Reference Cycles)**：公式形如 `Sheet1!A1 = Sheet2!A1 + 1` 且 `Sheet2!A1 = Sheet1!A1 * 2` 导致 DAG 拓扑排序死锁或递归溢出。*测试约束：DAG 必须支持跨表环路检测并直接返回 `#CYCLE!` / `#REF!` 错误。*
3. **工作表增删后单元格状态错乱**：在含有 3 个 Sheet 的工作簿中删除中间工作表或重命名工作表，活动工作表索引与视口选区脱节。*测试约束：`WorkbookModel` 必须发出规范的原子信号同步刷新视口和 TabBar。*
4. **大文件共享字符串内存耗尽**：打开含有 50 万单元格且大量重复字符串的 XLSX 文件导致内存激增。*测试约束：`xlsx_reader.py` 必须使用 SST 查重索引并按需流式提取。*
5. **多窗口动作同步与快捷键劫持**：同时打开两个 Quire 窗口或不同应用窗口时，全局 Action 快捷键触发串扰。*测试约束：`ActionRegistry` 必须按窗口实例（Window-Scoped）隔离绑定。*

---

## 任务拆解与执行阶段 (Task Breakdown)

### 阶段 2.1：GUI 基础微件与 1:1 声明式工具栏系统 (Tasks 1-5)

#### Task 1: 复杂工具栏微件开发 (SplitButton 与 DropDownButton)
**Files:**
- Create: `src/atboffice/ui/components/toolbar_buttons.py`
- Modify: `src/atboffice/ui/components/toolbar.py`
- Test: `tests/ui/test_toolbar_buttons.py`

**Interfaces:**
- Produces: `class OfficeSplitButton(QToolButton)`: 支持左侧主按钮点击与右侧小三角弹出菜单；
- Produces: `class OfficeDropDownButton(QToolButton)`: 整体点击弹出菜单，右侧带向下箭头；
- Produces: `OfficeToolBar.add_split_action(action: QAction, menu: QMenu) -> OfficeSplitButton`
- Produces: `OfficeToolBar.add_drop_button(text: str, icon: QIcon, menu: QMenu) -> OfficeDropDownButton`

- [ ] **Step 1: Write the failing test**
```python
def test_office_split_button_behavior(qtbot):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu
    from atboffice.ui.components.toolbar_buttons import OfficeSplitButton
    act = QAction("Save")
    menu = QMenu()
    btn = OfficeSplitButton(act, menu)
    assert btn.defaultAction() == act
    assert btn.menu() == menu
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/ui/test_toolbar_buttons.py -v`
Expected: FAIL (module not found)
- [ ] **Step 3: Implement `OfficeSplitButton` & `OfficeDropDownButton` in `toolbar_buttons.py`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/ui/test_toolbar_buttons.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/ui/components/toolbar_buttons.py src/atboffice/ui/components/toolbar.py tests/ui/test_toolbar_buttons.py && git commit -m "feat(ui): add OfficeSplitButton and OfficeDropDownButton components"`

---

#### Task 2: ActionRegistry 统一命令驱动总线
**Files:**
- Create: `src/atboffice/core/action_registry.py`
- Test: `tests/core/test_action_registry.py`

**Interfaces:**
- Produces: `class ActionSpec`: 包含 id, label, icon, tip, shortcut, checkable, is_split, is_drop, handler
- Produces: `class ActionRegistry`: 统一注册并返回 `QAction`，支持 fallback 提示与双向状态同步；

- [ ] **Step 1: Write the failing test**
```python
def test_action_registry_registration_and_fallback(qtbot):
    from atboffice.core.action_registry import ActionRegistry, ActionSpec
    reg = ActionRegistry()
    spec = ActionSpec(id="spelling", label="&Spelling...", tip="Check spelling")
    act = reg.register_action(spec)
    assert act.text() == "&Spelling..."
    assert act.toolTip() == "Check spelling"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/core/test_action_registry.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `ActionRegistry` in `src/atboffice/core/action_registry.py`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/core/test_action_registry.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/core/action_registry.py tests/core/test_action_registry.py && git commit -m "feat(core): implement ActionRegistry command bus"`

---

#### Task 3: Quire 10 套工具栏声明式构建与装配
**Files:**
- Create: `src/atboffice/ui/shell/quire_toolbars.py`
- Modify: `src/atboffice/ui/shell/quire_window.py`
- Test: `tests/ui/test_quire_toolbars.py`

**Interfaces:**
- Consumes: `ActionRegistry`, `OfficeToolBar`, `OfficeSplitButton`, `OfficeDropDownButton`
- Produces: `build_quire_toolbars(window: QuireWindow) -> dict[str, OfficeToolBar]`
包含：standard, formatting, tables, reviewing, outlining, headerFooter, drawing, mailMerge, picture, wordart 全部 10 套工具栏。

- [ ] **Step 1: Write the failing test**
```python
def test_quire_all_10_toolbars_exist(qtbot):
    from atboffice.ui.shell.quire_window import QuireWindow
    win = QuireWindow()
    qtbot.addWidget(win)
    expected = {"standard", "formatting", "tables", "reviewing", "outlining", "headerFooter", "drawing", "mailMerge", "picture", "wordart"}
    assert expected.issubset(set(win.toolbars.keys()))
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `quire_toolbars.py` and hook into `QuireWindow`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/ui/test_quire_toolbars.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/ui/shell/quire_toolbars.py src/atboffice/ui/shell/quire_window.py tests/ui/test_quire_toolbars.py && git commit -m "feat(quire): build complete 10-toolbar cluster matching vibeoffice spec"`

---

#### Task 4: Ledger 8 套工具栏声明式构建与装配
**Files:**
- Create: `src/atboffice/ui/shell/ledger_toolbars.py`
- Modify: `src/atboffice/ui/shell/ledger_window.py`
- Test: `tests/ui/test_ledger_toolbars.py`

**Interfaces:**
- Produces: `build_ledger_toolbars(window: LedgerWindow) -> dict[str, OfficeToolBar]`
包含：standard, formatting, borders, auditing, reviewing, list, chart, drawing 全部 8 套工具栏。

- [ ] **Step 1: Write the failing test**
```python
def test_ledger_all_8_toolbars_exist(qtbot):
    from atboffice.ui.shell/ledger_window import LedgerWindow
    win = LedgerWindow()
    qtbot.addWidget(win)
    expected = {"standard", "formatting", "borders", "auditing", "reviewing", "list", "chart", "drawing"}
    assert expected.issubset(set(win.toolbars.keys()))
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `ledger_toolbars.py` and integrate with `LedgerWindow`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/ui/test_ledger_toolbars.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/ui/shell/ledger_toolbars.py src/atboffice/ui/shell/ledger_window.py tests/ui/test_ledger_toolbars.py && git commit -m "feat(ledger): build complete 8-toolbar cluster matching vibeoffice spec"`

---

#### Task 5: Lectern 10 套工具栏声明式构建与装配
**Files:**
- Create: `src/atboffice/ui/shell/lectern_toolbars.py`
- Modify: `src/atboffice/ui/shell/lectern_window.py`
- Test: `tests/ui/test_lectern_toolbars.py`

**Interfaces:**
- Produces: `build_lectern_toolbars(window: LecternWindow) -> dict[str, OfficeToolBar]`
包含：standard, formatting, sorter, master, outlining, diagram, tables, picture, wordart, drawing 全部 10 套工具栏。

- [ ] **Step 1: Write the failing test**
```python
def test_lectern_all_10_toolbars_exist(qtbot):
    from atboffice.ui.shell.lectern_window import LecternWindow
    win = LecternWindow()
    qtbot.addWidget(win)
    expected = {"standard", "formatting", "sorter", "master", "outlining", "diagram", "tables", "picture", "wordart", "drawing"}
    assert expected.issubset(set(win.toolbars.keys()))
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `lectern_toolbars.py` and connect with `LecternWindow`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/ui/test_lectern_toolbars.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/ui/shell/lectern_toolbars.py src/atboffice/ui/shell/lectern_window.py tests/ui/test_lectern_toolbars.py && git commit -m "feat(lectern): build complete 10-toolbar cluster matching vibeoffice spec"`

---

### 阶段 2.2：电子表格 Workbook 多工作表与纯 Python XLSX 引擎 (Tasks 6-10)

#### Task 6: WorkbookModel 多工作表容器架构
**Files:**
- Create: `src/atboffice/modules/spreadsheet/models/workbook_model.py`
- Modify: `src/atboffice/modules/spreadsheet/view.py`
- Test: `tests/modules/spreadsheet/test_workbook_model.py`

**Interfaces:**
- Produces: `class WorkbookModel(QObject)`:
  - `add_sheet(name: str | None = None) -> SheetDataModel`
  - `remove_sheet(index: int) -> None`
  - `rename_sheet(index: int, new_name: str) -> None`
  - `move_sheet(from_index: int, to_index: int) -> None`
  - `active_sheet_index: int`
  - Signals: `sheet_added`, `sheet_removed`, `sheet_renamed`, `active_sheet_changed`

- [ ] **Step 1: Write the failing test**
```python
def test_workbook_model_sheet_lifecycle():
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    wb = WorkbookModel()
    assert len(wb.sheets) == 1
    s2 = wb.add_sheet("Sheet2")
    assert len(wb.sheets) == 2
    wb.rename_sheet(1, "Data")
    assert wb.sheets[1].name == "Data"
    wb.remove_sheet(0)
    assert len(wb.sheets) == 1
    assert wb.sheets[0].name == "Data"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_workbook_model.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `WorkbookModel` in `workbook_model.py`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_workbook_model.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/models/workbook_model.py tests/modules/spreadsheet/test_workbook_model.py && git commit -m "feat(spreadsheet): implement WorkbookModel container for multi-sheet support"`

---

#### Task 7: 经典 SheetTabBar 底部标签栏组件
**Files:**
- Create: `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`
- Modify: `src/atboffice/modules/spreadsheet/view.py`
- Test: `tests/modules/spreadsheet/test_sheet_tab_bar.py`

**Interfaces:**
- Consumes: `WorkbookModel`
- Produces: `class SheetTabBar(QWidget)`: 支持导航箭头、标签切换、右键菜单（插入/删除/重命名/复制）。

- [ ] **Step 1: Write the failing test**
```python
def test_sheet_tab_bar_sync(qtbot):
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    from atboffice.modules.spreadsheet.views.sheet_tab_bar import SheetTabBar
    wb = WorkbookModel()
    bar = SheetTabBar(wb)
    qtbot.addWidget(bar)
    assert bar.count() == 1
    wb.add_sheet("Summary")
    assert bar.count() == 2
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_sheet_tab_bar.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `SheetTabBar` and embed below `SpreadsheetView` grid**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_sheet_tab_bar.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py src/atboffice/modules/spreadsheet/view.py tests/modules/spreadsheet/test_sheet_tab_bar.py && git commit -m "feat(spreadsheet): add SheetTabBar widget with sheet switching and management"`

---

#### Task 8: 跨工作表公式求解与跨表 DAG 依赖
**Files:**
- Modify: `src/atboffice/modules/spreadsheet/calc/parser.py`
- Modify: `src/atboffice/modules/spreadsheet/calc/evaluator.py`
- Modify: `src/atboffice/modules/spreadsheet/calc/dag.py`
- Test: `tests/modules/spreadsheet/test_cross_sheet_calc.py`

**Interfaces:**
- Consumes: `WorkbookModel`
- Produces: 支持形如 `=Sheet2!A1 + 10` 或 `='Sales 2026'!B5 * 2` 的跨表语法及循环检测。

- [ ] **Step 1: Write the failing test**
```python
def test_cross_sheet_formula_evaluation():
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    wb = WorkbookModel()
    s1 = wb.sheets[0]
    s2 = wb.add_sheet("Sheet2")
    s2.set_cell_value(0, 0, 42)
    s1.set_cell_formula(0, 0, "=Sheet2!A1 + 8")
    wb.recalculate()
    assert s1.get_cell_value(0, 0) == 50
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_cross_sheet_calc.py -v`
Expected: FAIL
- [ ] **Step 3: Update parser & evaluator with Sheet qualified references**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_cross_sheet_calc.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/calc/ tests/modules/spreadsheet/test_cross_sheet_calc.py && git commit -m "feat(calc): support cross-sheet formula evaluation and DAG cycle detection"`

---

#### Task 9: 纯 Python XLSX 读取器 (xlsx_reader.py)
**Files:**
- Create: `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
- Modify: `src/atboffice/modules/spreadsheet/io/__init__.py`
- Test: `tests/modules/spreadsheet/test_xlsx_reader.py`

**Interfaces:**
- Consumes: `zipfile`, `vfs/opc.py`, `WorkbookModel`
- Produces: `read_xlsx(file_path_or_bytes: str | Path | bytes, workbook: WorkbookModel) -> None`
解析 SST (`sharedStrings.xml`), styles (`styles.xml`), sheets (`worksheets/sheetN.xml`), 单元格数值/公式/跨列合并。

- [ ] **Step 1: Write the failing test**
```python
def test_read_minimal_xlsx(tmp_path):
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    # Test reading valid sample or synthetic xlsx
    wb = WorkbookModel()
    read_xlsx("tests/fixtures/sample.xlsx", wb)
    assert len(wb.sheets) >= 1
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_reader.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `xlsx_reader.py` based on `ledger/js/xlsx-read.js`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_reader.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/io/xlsx_reader.py tests/modules/spreadsheet/test_xlsx_reader.py && git commit -m "feat(io): implement pure Python xlsx reader for multi-sheet workbooks"`

---

#### Task 10: 纯 Python XLSX 写入器 (xlsx_writer.py) 与无损回写
**Files:**
- Create: `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
- Test: `tests/modules/spreadsheet/test_xlsx_writer.py`

**Interfaces:**
- Consumes: `WorkbookModel`, `vfs/opc.py`
- Produces: `write_xlsx(workbook: WorkbookModel, output_path: str | Path, source_opc: OpcPackage | None = None) -> None`

- [ ] **Step 1: Write the failing test**
```python
def test_write_and_reopen_xlsx(tmp_path):
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
    from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
    from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
    wb = WorkbookModel()
    s = wb.sheets[0]
    s.set_cell_value(0, 0, "Test Value")
    out_file = tmp_path / "saved.xlsx"
    write_xlsx(wb, out_file)
    wb2 = WorkbookModel()
    read_xlsx(out_file, wb2)
    assert wb2.sheets[0].get_cell_value(0, 0) == "Test Value"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_writer.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `xlsx_writer.py` based on `ledger/js/xlsx-write.js`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_xlsx_writer.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/io/xlsx_writer.py tests/modules/spreadsheet/test_xlsx_writer.py && git commit -m "feat(io): implement pure Python xlsx writer with OPC roundtrip support"`

---

### 阶段 2.3：文档 I/O 深水区与无损保真加固 (Tasks 11-13)

#### Task 11: OPC 容器规范强化与未修改 Part 字节流保真 (Preserve Engine)
**Files:**
- Modify: `src/atboffice/vfs/opc.py`
- Test: `tests/vfs/test_opc_preserve.py`

**Interfaces:**
- Produces: `OpcPackage.preserve_unmodified_parts(target_zip: zipfile.ZipFile, modified_parts: set[str]) -> None`
自动将未被用户修改的 Part（包括 `vbaProject.bin`, 图片, 样式, 主题）原样复制。

- [ ] **Step 1: Write the failing test**
```python
def test_opc_preserve_macro_and_custom_parts(tmp_path):
    from atboffice.vfs.opc import OpcPackage
    pkg = OpcPackage.create_empty()
    pkg.add_part("xl/vbaProject.bin", b"DUMMY_VBA_BYTECODE", "application/vnd.ms-office.vbaProject")
    out = tmp_path / "test.xlsm"
    pkg.save_to(out)
    pkg2 = OpcPackage.open(out)
    assert pkg2.get_part("xl/vbaProject.bin") == b"DUMMY_VBA_BYTECODE"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/vfs/test_opc_preserve.py -v`
Expected: FAIL
- [ ] **Step 3: Enhance `vfs/opc.py` to support full byte-for-byte carry**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/vfs/test_opc_preserve.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/vfs/opc.py tests/vfs/test_opc_preserve.py && git commit -m "feat(vfs): harden OPC package engine with lossless byte carry for unmodified parts"`

---

#### Task 12: DOCX 读取器全量扩充 (编号列表、复杂表格合并与图形环绕)
**Files:**
- Modify: `src/atboffice/modules/writer/io/docx_reader.py`
- Test: `tests/modules/writer/test_docx_reader_advanced.py`

**Interfaces:**
- Produces: 完整支持 `w:numPr` 列表级联、`w:gridSpan` / `w:vMerge` 表格跨行跨列、`w:drawing` 嵌入与浮动图片。

- [ ] **Step 1: Write the failing test**
```python
def test_docx_complex_table_gridspan_and_numbering(tmp_path):
    from atboffice.modules.writer.io.docx_reader import DocxReader
    reader = DocxReader()
    # verify parse table with gridSpan and numbering definitions
    assert hasattr(reader, "parse_numbering")
    assert hasattr(reader, "parse_drawing_ml")
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/writer/test_docx_reader_advanced.py -v`
Expected: FAIL
- [ ] **Step 3: Expand `docx_reader.py` aligned with `quire/js/docx-read.js` (1,876 lines)**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/writer/test_docx_reader_advanced.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/writer/io/docx_reader.py tests/modules/writer/test_docx_reader_advanced.py && git commit -m "feat(writer): expand docx_reader to full parity with numbering, complex tables, and drawings"`

---

#### Task 13: PPTX 读取器补全 (母版占位符继承与时序树)
**Files:**
- Modify: `src/atboffice/modules/presentation/io/pptx_reader.py`
- Test: `tests/modules/presentation/test_pptx_reader_advanced.py`

**Interfaces:**
- Produces: 完整支持 `SlideMaster` -> `SlideLayout` -> `Slide` 占位符继承解析与 `p:timing` 进出场动画时序树。

- [ ] **Step 1: Write the failing test**
```python
def test_pptx_master_layout_placeholder_inheritance():
    from atboffice.modules.presentation.io.pptx_reader import PptxReader
    reader = PptxReader()
    assert hasattr(reader, "resolve_master_placeholders")
    assert hasattr(reader, "parse_timing_tree")
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/presentation/test_pptx_reader_advanced.py -v`
Expected: FAIL
- [ ] **Step 3: Enhance `pptx_reader.py` to match `lectern/js/pptx-read.js`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/presentation/test_pptx_reader_advanced.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/presentation/io/pptx_reader.py tests/modules/presentation/test_pptx_reader_advanced.py && git commit -m "feat(presentation): complete pptx_reader master layout inheritance and timing parse"`

---

### 阶段 2.4：表格浮动图形、查找替换与全量多语言 (Tasks 14-16)

#### Task 14: 电子表格网格浮动对象层 (SpreadsheetObjectLayer)
**Files:**
- Create: `src/atboffice/modules/spreadsheet/views/object_layer.py`
- Modify: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- Test: `tests/modules/spreadsheet/test_object_layer.py`

**Interfaces:**
- Produces: `class SpreadsheetObjectLayer(QWidget)`: 在单元格上方自由定位、拖拽、缩放矩形、圆形、箭头、图片与图表，并提供 8 点手柄交互。

- [ ] **Step 1: Write the failing test**
```python
def test_spreadsheet_object_layer_add_and_hit_test(qtbot):
    from atboffice.modules.spreadsheet.views.object_layer import SpreadsheetObjectLayer, FloatingObject
    layer = SpreadsheetObjectLayer()
    qtbot.addWidget(layer)
    obj = FloatingObject(kind="rect", x=50, y=50, width=100, height=80)
    layer.add_object(obj)
    assert layer.hit_test(60, 60) == obj
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_object_layer.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `object_layer.py` and attach to `GridViewport`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/modules/spreadsheet/test_object_layer.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/modules/spreadsheet/views/object_layer.py src/atboffice/modules/spreadsheet/views/grid_viewport.py tests/modules/spreadsheet/test_object_layer.py && git commit -m "feat(spreadsheet): add floating object layer over grid viewport for shapes and images"`

---

#### Task 15: 跨模块通用查找与替换系统 (Find & Replace)
**Files:**
- Create: `src/atboffice/core/search.py`
- Create: `src/atboffice/ui/dialogs/find_replace_dialog.py`
- Test: `tests/core/test_search.py`

**Interfaces:**
- Produces: `class SearchController`: 提供 `find_next`, `find_prev`, `replace_current`, `replace_all`；
- Produces: `class FindReplaceDialog(QDialog)`: 经典 Office 2003 查找替换浮动对话框。

- [ ] **Step 1: Write the failing test**
```python
def test_search_controller_text_match():
    from atboffice.core.search import SearchController, SearchOptions
    sc = SearchController()
    text = "Hello ATBOffice, welcome to ATBOffice"
    matches = sc.find_all(text, "ATBOffice", SearchOptions(case_sensitive=True))
    assert len(matches) == 2
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/core/test_search.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `search.py` and `find_replace_dialog.py`**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/core/test_search.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/core/search.py src/atboffice/ui/dialogs/find_replace_dialog.py tests/core/test_search.py && git commit -m "feat(core): implement universal find and replace engine and classic dialog"`

---

#### Task 16: 全量 7 国语言多语言翻译系统与资源加载
**Files:**
- Create: `src/atboffice/core/i18n.py`
- Create: `src/atboffice/resources/locale/` (导入 7 语言词典)
- Modify: `src/atboffice/main.py`
- Test: `tests/core/test_i18n.py`

**Interfaces:**
- Consumes: `.vibeoffice/public/common/i18n/*.json` (zh-CN, zh-Hant, en, ja, ko, fr, de)
- Produces: `load_locale(locale_name: str) -> None`
- Produces: 动态切换 `safe_tr(key: str) -> str`，覆盖所有 300+ 个 Action 与对话框。

- [ ] **Step 1: Write the failing test**
```python
def test_i18n_dynamic_locale_switching():
    from atboffice.core.i18n import load_locale, safe_tr
    load_locale("en")
    assert safe_tr("&Save") == "&Save"
    load_locale("zh-CN")
    assert safe_tr("&Save") == "保存(&S)"
```
- [ ] **Step 2: Run test to verify it fails**
Run: `conda run -n ATBOffice pytest tests/core/test_i18n.py -v`
Expected: FAIL
- [ ] **Step 3: Implement `i18n.py` and import locale JSON catalogs into Python package resources**
- [ ] **Step 4: Run test to verify it passes**
Run: `conda run -n ATBOffice pytest tests/core/test_i18n.py -v`
Expected: PASS
- [ ] **Step 5: Commit**
`git add src/atboffice/core/i18n.py src/atboffice/resources/locale/ tests/core/test_i18n.py && git commit -m "feat(core): introduce full 7-language i18n dictionary system and dynamic safe_tr"`

---

## 阶段验收与集成验证标准 (Integration Verification)

每个阶段完成后，均必须运行全套自动化测试套件：
1. **单元测试与组件测试**：
   `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v`
2. **文档往返无损比对 (Roundtrip Parity)**：
   打开原始测试目录中的 `.docx`, `.xlsx`, `.pptx` 文件，执行无修改重写保存，比对关键 XML 语义树与未修改二进制 Parts 保持 100% 一致。
3. **工具栏数量与功能审计**：
   自动化脚本遍历检查 3 个窗口的全部 28 套工具栏，断言按钮总数达到 300+ 且每一个 Action 均具备有效的 ToolTip、Shortcut 与事件响应。
