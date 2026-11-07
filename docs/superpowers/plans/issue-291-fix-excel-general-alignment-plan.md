# Implementation Plan: 修复 Excel General 格式数值默认对齐 (Issue #291)

## Chunk 1: 核心模型对齐解析引擎与单元测试 (TDD)
- **Files**:
  - `src/atboffice/modules/spreadsheet/models/sheet_model.py`
  - `tests/unit/spreadsheet/test_cell_alignment.py`
- **Actions**:
  1. 编写单元测试 `tests/unit/spreadsheet/test_cell_alignment.py`，覆盖：
     - General 格式下整数、浮点数、负数默认为右对齐
     - General 格式下布尔值 (`True`, `False`) 默认为居中对齐
     - General 格式下错误值 (`#N/A`, `#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#NULL!`) 默认为居中对齐
     - General 格式下日期/时间 (`datetime.date`, `datetime.datetime`) 默认为右对齐
     - General 格式下普通字符串默认为左对齐
     - 显式 `align_h` 为 `left`, `center`, `right`, `justify` 时优先遵循显式设置
     - 文字走向 `text_direction == "rtl"` 时普通文本在 General 格式下为右对齐
     - 垂直对齐 `align_v` 的解析映射
  2. 在 `CellData` 与 `SheetDataModel` 中实现 `get_effective_align_h()` 与 `get_effective_align_v()`
  3. 运行测试验证全部通过

## Chunk 2: 视口渲染与内联编辑器对齐重构
- **Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/editor_controller.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `tests/gui/test_ledger_alignment_rendering.py`
- **Actions**:
  1. 更新 `grid_viewport.py`：
     - 在 `paintEvent` 绘制单元格文本时，根据 `cell.get_effective_align_h()` 生成 Qt 对齐标志；
     - 限制跨列溢出：对于右对齐（含默认右对齐的数字）或居中对齐单元格，禁用跨列向右溢出计算（`calculate_overflow_span` 仅限左对齐文本使用）；
     - 支持垂直对齐标志映射。
  2. 更新 `editor_controller.py`：在 `_style_in_cell_editor` 中使用 `get_effective_align_h()`。
  3. 更新 `ledger_window.py`：在状态栏/工具栏与打印绘制中同步使用统一逻辑。
  4. 编写 GUI 测试 `tests/gui/test_ledger_alignment_rendering.py` 验证视口绘制与渲染对齐。

## Chunk 3: OOXML Reader / Writer RTL 与 readingOrder 序列化无损支持
- **Files**:
  - `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
  - `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
  - `tests/modules/spreadsheet/test_xlsx_alignment_roundtrip.py`
- **Actions**:
  1. 完善 `xlsx_reader.py`：解析 `<alignment readingOrder="1|2"/>` 并保存到 `CellData.text_direction`。
  2. 完善 `xlsx_writer.py`：在生成 `<alignment>` 样式时包含 `readingOrder`，并在 `has_align` 中考虑 `text_direction`。
  3. 编写往返测试 `tests/modules/spreadsheet/test_xlsx_alignment_roundtrip.py` 验证保存后重开保持 RTL 及对齐属性。

## Chunk 4: 样本文档 `libreoffice__cell-value.xlsx` 回归验证与全套测试
- **Files**:
  - `tests/docs/excel/xlsx/libreoffice__cell-value.xlsx`
  - `tests/unit/spreadsheet/test_cell_value_corpus.py`
- **Actions**:
  1. 编写真实样本解析核验测试 `test_cell_value_corpus.py`，验证 `tests/docs/excel/xlsx/libreoffice__cell-value.xlsx` 中所有数值、文本、日期单元格的对齐行为完全符合预期。
  2. 运行完整测试套件，保证 0 回归。
