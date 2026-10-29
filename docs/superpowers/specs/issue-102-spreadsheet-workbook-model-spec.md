# Technical Specification - Issue #102: 电子表格 WorkbookModel 多工作表容器架构重构

## 1. Overview & Context

- **Issue**: #102 `[Phase 2] 电子表格 WorkbookModel 多工作表容器架构重构`
- **Parent Epic**: #96 `[Phase 2] ATBOffice 二期工程：1:1 完整全量移植与核心架构补完`
- **Reference**: 原版 `.vibeoffice/public/ledger/js/model.js` (Workbook & Sheet architecture)
- **Status**: Design / Brainstorming Complete (>=90% Confidence Decision)

### Problem Statement
当前 Python 侧的 Ledger 仅支持孤立的单表 `SheetDataModel`，缺少工作簿容器层级。在打开实际的多工作表 XLSX 文件、实现底部工作表标签栏（SheetTabBar，Issue #103）交互以及跨表公式求解（`Sheet!Cell`，Issue #104）时，需要核心具备管理多个工作表生命周期、名称验证、工作表重排与当前活动表（active sheet）切换的能力。

---

## 2. Architecture & Design

### 2.1 WorkbookModel (`src/atboffice/modules/spreadsheet/models/workbook_model.py`)

`WorkbookModel` 继承自 `PySide6.QtCore.QObject`，充当工作簿顶层数据模型容器。

```
+-------------------------------------------------------------+
|                       WorkbookModel                         |
+-------------------------------------------------------------+
| - _sheets: list[SheetDataModel]                             |
| - _active_sheet_index: int                                  |
+-------------------------------------------------------------+
| + sheets -> list[SheetDataModel]                            |
| + active_sheet_index -> int                                 |
| + active_sheet -> SheetDataModel                            |
| + add_sheet(name=None, index=None) -> SheetDataModel        |
| + remove_sheet(index: int) -> SheetDataModel                |
| + rename_sheet(index: int, new_name: str) -> None           |
| + move_sheet(from_index: int, to_index: int) -> None        |
| + get_sheet_by_name(name: str) -> SheetDataModel | None     |
| + sheet_index(sheet: SheetDataModel) -> int                 |
| + set_active_sheet_index(index: int) -> None                |
| + set_active_sheet(sheet: SheetDataModel) -> None           |
+-------------------------------------------------------------+
| Signals:                                                    |
| * sheet_added(int, str)                                     |
| * sheet_removed(int, str)                                   |
| * sheet_renamed(int, str, str)                              |
| * sheet_moved(int, int)                                     |
| * active_sheet_changed(int)                                 |
+-------------------------------------------------------------+
```

#### Naming & Validation Rules
对标 Excel / 原版规范：
1. 默认命名生成算法：`Sheet1`, `Sheet2`, ..., 寻找第一个不冲突的正整数序号（不区分大小写比较）。
2. 工作表名称校验规则：
   - 不能为空或纯空白字符；
   - 长度不超过 31 个字符；
   - 不得包含非法字符：`\`, `/`, `?`, `*`, `:`, `[`, `]`;
   - 不能与工作簿中其他现有工作表重名（大小写不敏感匹配）。若与现有同名工作表冲突，抛出 `ValueError`。

#### Sheet Mutation & Active Index Invariant
- **添加工作表 (`add_sheet`)**:
  - 若 `index` 为 `None`，追加至末尾。
  - 若 `index <= _active_sheet_index`，更新 `_active_sheet_index += 1` 以保证指向同一个活跃表。
  - 发出 `sheet_added(index, sheet.name)`。
- **删除工作表 (`remove_sheet`)**:
  - 若 `len(_sheets) <= 1`，抛出 `ValueError("Cannot remove the only remaining worksheet.")`，保证至少保留一张工作表。
  - 若 `index < _active_sheet_index`：`_active_sheet_index -= 1`。
  - 若 `index == _active_sheet_index`：活跃表被移除，新活跃表索引为 `min(index, len(_sheets) - 1)`，并发出 `active_sheet_changed(_active_sheet_index)`。
  - 发出 `sheet_removed(index, old_name)`。
- **重命名工作表 (`rename_sheet`)**:
  - 校验合法性及是否重复。若新旧名称相同则安全无操作返回。
  - 更新表名并发出 `sheet_renamed(index, old_name, new_name)`。
- **重排工作表 (`move_sheet`)**:
  - 将工作表从 `from_index` 移动到 `to_index`。
  - 动态校正 `_active_sheet_index`，确保活跃表依然指向原活动对象。
  - 发出 `sheet_moved(from_index, to_index)`。

### 2.2 SheetDataModel Enhancement (`src/atboffice/modules/spreadsheet/models/sheet_model.py`)
- 为 `SheetDataModel` 增加 `name: str = "Sheet1"` 属性；
- 构造器接受 `name: str = "Sheet1"`，保持 100% 向后兼容。

### 2.3 SpreadsheetView Refactoring (`src/atboffice/modules/spreadsheet/view.py`)
- 构造函数签名升级为：
  `def __init__(self, workbook: WorkbookModel | None = None, model: SheetDataModel | None = None, selection: SelectionModel | None = None, parent: QWidget | None = None)`
- 兼容性保障：
  - 若传入 `workbook`，直接绑定；
  - 若仅传入 `model`，自动构造包含该 `model` 的 `WorkbookModel`；
  - 若均未传入，默认新建含单一 "Sheet1" 的 `WorkbookModel`。
- 对外暴露属性：
  - `view.workbook -> WorkbookModel`
  - `view.model -> SheetDataModel` (返回当前 `workbook.active_sheet`，保证原有所有调用者无缝运行)
- 多工作表选区隔离：
  - 内部维护 `self._sheet_selections: dict[SheetDataModel, SelectionModel] = {}`。
  - 切换工作表时，获取或创建目标 Sheet 的 `SelectionModel`，同步更新 `self.grid.selection` 和 `self.editor_controller.selection`，确保各工作表的活动单元格与选区互不干扰。
- 视图切换联动：
  - 监听 `workbook.active_sheet_changed`，更新 `grid.model`、`editor_controller.model`，并调用 `grid.viewport().update()`。

---

## 3. Edge Cases & Reliability Checklist

1. **零表状态防御**: 构造空列表或尝试删除最后一张表均被拦截。
2. **重排活动表**: 移动当前活动表时，`active_sheet_index` 紧密随动更新，指针不漂移。
3. **命名冲突及符号清洗**: 对标 Excel 31 字符及非法字符规范，抛出详尽异常。
4. **内存与引用泄漏**: 移除 Sheet 时，清理该 Sheet 在 View 中的选区缓存。
5. **i18n 本地化**: 异常提示使用规范的中文与英文支持。

---

## 4. Verification & Testing Strategy

1. **测试文件**: `tests/modules/spreadsheet/test_workbook_model.py`
   - `test_default_workbook`: 验证默认初始化带有一张 Sheet1，active_sheet 正常。
   - `test_add_sheet`: 自动命名、指定命名、插入位置校验与信号发射。
   - `test_sheet_name_validation`: 31 字符超长、非法字符、重名、大小写重名防御。
   - `test_remove_sheet`: 中间删除、前置删除、删除当前活动表后的指针修正、防止删除最后一张表。
   - `test_rename_sheet`: 成功重命名与信号、重复名异常。
   - `test_move_sheet`: 前后移动、移动活跃表、越界校验。
2. **视图集成测试**: `tests/gui/test_spreadsheet_view_workbook.py`
   - 验证 `SpreadsheetView` 绑定 `WorkbookModel`。
   - 验证切换工作表时 `grid.model` 切换及各工作表独立的选区隔离。
3. **回归验证**:
   - 运行全量 `tests/unit/spreadsheet/` 和 `tests/gui/` 确保 141+ 用例 100% 通过。
