# Implementation Plan: [Ledger] 基于 QAbstractScrollArea 的虚拟化自绘网格视口 (Issue #9)

## 任务目标
按照 `docs/superpowers/specs/issue-9-virtualized-grid-viewport-spec.md` 规范，实现：
1. `src/atboffice/drawing/numfmt.py`：Excel 格式串数字格式化引擎，含中英/东亚本地化周几（`aaa` / `aaaa`）支持。
2. `src/atboffice/modules/spreadsheet/models/`：表格轻量数据模型与选区状态机（单选、框选、多区域选区、全选）。
3. `src/atboffice/modules/spreadsheet/views/grid_viewport.py`：基于 `QAbstractScrollArea` 的纯自绘虚拟化网格视口。支持十万级行列平滑滚动、自绘表头（可拖拽缩放与双击 AutoFit）、相邻空单元格平滑文字右溢出排版、2px 活动光标边框。
4. `src/atboffice/modules/spreadsheet/view.py`：挂载网格视口并支持双向绑定。
5. 完备的单元测试与 GUI 自动化验证套件。

---

## Task 1: Excel 数字格式化引擎 (`numfmt.py`)

### 1.1 编写单元测试 `tests/unit/drawing/test_numfmt.py`
- 测试内置格式与通用（General）格式化。
- 测试正负数、百分比、千分位、科学计数法。
- 测试日期时间与序列号换算。
- 测试中文周几 `aaa`（"一"、"日"等）与 `aaaa`（"星期一"、"星期日"等）。
- 测试文本节 `@` 与颜色标签提取 `[Red]`。

### 1.2 实现 `src/atboffice/drawing/numfmt.py`
- 实现标准日期序列号与日历换算（支持 1900 与 1904 历法）。
- 实现多节格式串解析器（分号分节、方括号提取颜色与比较条件）。
- 实现数字/百分比/千分位/日期格式化。
- 实现 `aaa` 与 `aaaa` 本地化星期转换。
- 运行测试并验证通过：`conda run -n ATBOffice pytest tests/unit/drawing/test_numfmt.py -v`。

---

## Task 2: 表格轻量数据模型与选区状态机

### 2.1 编写单元测试 `tests/unit/spreadsheet/test_selection_model.py`
- 测试 `SelectionRange` 标准化（`min_r`, `min_c`, `max_r`, `max_c`）。
- 测试单选、扩展（Shift+Click/Arrow）、多选区追加（Ctrl/Cmd+Click）。
- 测试整行选区、整列选区与全选。

### 2.2 实现模型
- `src/atboffice/modules/spreadsheet/models/sheet_model.py`：定义单元格数据对象 `CellData`、表格数据模型 `SheetDataModel` 及行列几何计算类 `SheetGeometry`。
- `src/atboffice/modules/spreadsheet/models/selection_model.py`：定义选区矩形 `SelectionRange` 与选区状态机 `SelectionModel`。
- 运行测试并验证通过。

---

## Task 3: 虚拟化自绘网格视口 (`grid_viewport.py`)

### 3.1 编写 GUI 测试 `tests/gui/test_grid_viewport.py`
- 测试无头环境下 `GridViewport` 初始化。
- 测试可视行列计算（虚拟化视口剪裁）。
- 测试行列头点击、拖拽调整大小、双击 AutoFit 宽度。
- 测试多模式选区与鼠标点击/拖拽状态转换。
- 测试平滑文字向右溢出排版逻辑。

### 3.2 实现 `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
- 继承 `QAbstractScrollArea`，重写 `paintEvent`、`resizeEvent`、`mousePressEvent`、`mouseMoveEvent`、`mouseReleaseEvent`、`mouseDoubleClickEvent`、`wheelEvent`、`keyPressEvent`。
- 实现双缓冲自绘：背景、网格线、单元格文本（含平滑右溢出）、半透明选区、2px 活动光标、行列头与全选角块。
- 实现拖拽调宽调高与 AutoFit。
- 实现国际化 `tr()` 与 `retranslate_ui()`。

---

## Task 4: 整合视口与模块视图 (`view.py`)

- 更新 `src/atboffice/modules/spreadsheet/view.py`，将占位符替换为包含 `GridViewport` 的电子表格视图。
- 运行全量测试套件保证 100% 通过。
