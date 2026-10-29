# Implementation Plan: Issue #103 经典 SheetTabBar 底部工作表标签栏交互组件

## 1. Overview
本计划根据规范 `docs/superpowers/specs/issue-103-sheet-tab-bar-spec.md`，以测试驱动开发（TDD）的方式实现 Excel 2003 经典外观与行为的 `SheetTabBar` 交互组件，并嵌入到 `SpreadsheetView` 中。

---

## 2. Tasks & Detailed Steps

### Task 1: 编写 SheetTabBar 自动化测试用例
- **File**: `tests/modules/spreadsheet/test_sheet_tab_bar.py`
- **Steps**:
  1. 测试 `SheetTabBar` 的构造与模型绑定（默认工作簿、带多工作表的工作簿）。
  2. 测试导航按钮（`first`, `prev`, `next`, `last`）的滚动与行为。
  3. 测试标签单击切换活动工作表，验证 `WorkbookModel.active_sheet_index` 及信号触发。
  4. 测试双击原位重命名交互：合法名称成功更新、非法字符拦截、重复名称拦截、ESC 取消。
  5. 测试右键上下文菜单（插入新工作表、删除工作表与单表保护、标签颜色设置）。
  6. 测试模型外部变动同步（`sheet_added`, `sheet_removed`, `sheet_renamed`, `sheet_moved`）。
  7. 测试 `retranslate_ui()` 国际化多语言刷新。
- **Expected Result**: 初始运行时由于类未实现报错 (ImportError/AssertionError)。

### Task 2: 开发 `SheetTabBar` 核心组件
- **File**: `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`
- **Steps**:
  1. 引入 Qt 微件与样式绘制 (`QPainter`, `QStyle`, `QLineEdit`, `QMenu`, `QToolButton`, `QScrollArea`)。
  2. 实现导航按钮区与 4 个紧凑按钮（`|<`, `<`, `>`, `>|`）及其图标与右键工作表菜单。
  3. 实现工作表标签绘制，匹配 Excel 2003 经典外观（梯形/圆角、白底活动态、灰底非活动态、自定义标签颜色线）。
  4. 实现平滑滚轮横向滚动与自动 `ensure_visible(index)`。
  5. 实现原位 `QLineEdit` 编辑器，具备输入验证（`is_valid_sheet_name` 及唯一性重名校验）与友好的拦截提示。
  6. 实现完整的右键快捷菜单（插入、删除、重命名、复制、颜色、查看代码）。
  7. 实现 `safe_tr()` 与 `retranslate_ui()`。
- **Expected Result**: `test_sheet_tab_bar.py` 所有用例全部通过。

### Task 3: 将 `SheetTabBar` 嵌入 `SpreadsheetView`
- **File**: `src/atboffice/modules/spreadsheet/view.py`
- **Steps**:
  1. 在 `SpreadsheetView.__init__` 中实例化 `self.sheet_tab_bar = SheetTabBar(workbook=self._workbook, parent=self)`。
  2. 通过 `self.grid.addScrollBarWidget(self.sheet_tab_bar, Qt.AlignmentFlag.AlignLeft)` 嵌入网格滚动区左下角。
  3. 在 `retranslate_ui()` 中联动调用 `self.sheet_tab_bar.retranslate_ui()`。
- **Expected Result**: `SpreadsheetView` 初始化包含 `sheet_tab_bar`，多工作表切换顺畅联动。

### Task 4: 全量测试验证与回归测试
- **Commands**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_sheet_tab_bar.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/ -v`
- **Expected Result**: 100% 测试通过，无任何回归问题。
