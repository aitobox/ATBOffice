# Specification: Issue #103 经典 SheetTabBar 底部工作表标签栏交互组件

## 1. Overview
在 ATBOffice Ledger（电子表格）中，原版 Excel 2003 与 VibeOffice 在工作表网格左下方提供一套标志性的标签栏组件：包含首表/上一个/下一个/尾表四联导航按钮区、横向排列的圆角/梯形工作表标签列表（Sheet1、Sheet2...）、活动工作表突出高亮态、双击原位编辑重命名、右键经典快捷菜单（插入、删除、重命名、移动或复制、工作表标签颜色等），以及与 `WorkbookModel` 的双向信号槽联动。

本规范定义 `SheetTabBar` 的完整技术架构、UI 视觉设计、交互行为及与 `SpreadsheetView` 的集成方式。

---

## 2. Architecture & Class Design

### 2.1 File Location
- **Component File**: `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`
- **View Integration**: `src/atboffice/modules/spreadsheet/view.py`
- **Test File**: `tests/modules/spreadsheet/test_sheet_tab_bar.py`

### 2.2 Class Hierarchy & Responsibilities

```
+---------------------------------------------------------------------------------------------------+
| SheetTabBar (QWidget)                                                                             |
| +------------------------------------+ +--------------------------------------------------------+ |
| | NavButtonsArea (QWidget)           | | TabScrollArea (QScrollArea)                            | |
| | [ |< ] [ < ] [ > ] [ >| ]          | |   TabsContainerWidget (custom paint / layout)          | |
| | - First / Prev / Next / Last       | |   - SheetTabItem / Tab buttons                         | |
| | - ContextMenu: Full sheets list    | |   - Inline QLineEdit editor for renaming               | |
| +------------------------------------+ +--------------------------------------------------------+ |
+---------------------------------------------------------------------------------------------------+
```

- **`SheetTabBar(QWidget)`**:
  - 主容器，包含左侧四联导航按钮区和右侧横向滚动的工作表标签条区。
  - 绑定 `WorkbookModel`，监听其所有生命周期信号：
    - `sheet_added(int, str)` -> 刷新标签列表，自动滚动至新标签。
    - `sheet_removed(int, str)` -> 刷新标签列表，重新计算选中高亮。
    - `sheet_renamed(int, str, str)` -> 更新对应标签名称与宽度。
    - `sheet_moved(int, int)` -> 重构标签次序。
    - `active_sheet_changed(int)` -> 切换活动标签视觉态并确保可见 (`ensure_tab_visible(index)`)。
  - 对外信号：
    - `tab_clicked(int)` -> 请求切换活动工作表。
    - `tab_rename_requested(int, str)` -> 请求重命名工作表。
    - `sheet_insert_requested()` -> 请求插入新工作表。
    - `sheet_delete_requested(int)` -> 请求删除工作表。
    - `sheet_color_requested(int, QColor)` -> 请求修改标签颜色。

- **`TabNavButton(QToolButton / QPushButton)`**:
  - 四个紧凑导航按钮：`|<`（首表）、`<`（上一个）、`>`（下一个）、`>|`（尾表）。
  - 支持左键点击平滑滚动标签条，支持右键弹出所有工作表选择菜单（带单选对勾）。

- **Inline Renaming Overlay (`QLineEdit`)**:
  - 双击标签或右键选择“重命名”时，在标签上方浮动显示与标签文字位置对齐的 `QLineEdit`。
  - 回车（Enter）或失焦（blur）提交校验；ESC 取消修改。
  - 调用 `WorkbookModel.rename_sheet(index, new_name)`。若校验失败（空名、重名、包含特殊字符），弹出友好提示并阻止非法修改。

---

## 3. Visual Styling (Excel 2003 Classic / Office Luna)

- **配色与几何特征**:
  - 背景色：经典的 Windows 2003 灰色/工具栏表面底色 `#ECE9D8`。
  - 活动标签（Active Tab）：
    - 纯白背景 `#FFFFFF`，顶部边框 `#7F9DB9` 或 `#9E9A91`，左右侧略带圆角斜边，底部边框与网格背景打通无缝融合。
    - 粗体或突出字色 `#000000`。
    - 若有自定义 `tab_color`，在标签下沿绘制 3px 鲜艳彩色底条或彩色渐变。
  - 非活动标签（Inactive Tabs）：
    - 背景色 `#D4D0C8` / `#E0DFE3`，与活动标签形成清晰反差。
    - 悬停（Hover）：轻微高亮态 `#F5F4EE`。
  - 分隔线与尺寸：
    - 标签高度 20-22px，字体 9pt/11px Arial / Segoe UI / 微软雅黑。
    - 紧凑导航按钮尺寸 16x18px，扁平无边框风格，悬停微凸。

---

## 4. User Interaction & Context Menu

### 4.1 Click & Navigation
- 单击标签：激活对应工作表（调用 `workbook.set_active_sheet_index(idx)`）。
- 鼠标滚轮：在标签条区域滚动横向移动标签列表。
- 导航按钮：
  - `|<`：滚动到最左侧标签。
  - `<`：左移滚动 60px。
  - `>`：右移滚动 60px。
  - `>|`：滚动到最右侧标签。
  - 右键任意导航按钮：弹出菜单列出全部工作表，单选标记当前活动工作表，点击直达。

### 4.2 Tab Context Menu
右键点击标签弹出经典快捷菜单：
1. `&Insert...` / `插入工作表(&I)...` -> 在当前位置插入新工作表，命名如 `Sheet2`，并进入重命名态。
2. `&Delete` / `删除工作表(&D)` -> 校验 `len(workbook.sheets) > 1`。若只有 1 张工作表，禁用或拦截并提示不可删除；多张工作表时执行删除并询问确认。
3. `&Rename` / `重命名(&R)` -> 进入原位编辑。
4. `&Move or Copy...` / `移动或复制(&M)...` -> 支持复制当前工作表（如 `Sheet1 (2)`）或移动位置。
5. `&Tab Color...` / `工作表标签颜色(&T)...` -> 弹出 `QColorDialog` 设置个性化标签颜色。
6. `-` 分隔线。
7. `&View Code` / `查看代码(&V)` -> 经典灰显占位。

---

## 5. Edge Cases & Robustness Analysis
1. **工作簿无缝切换**: `set_workbook(model)` 安全解绑旧模型信号、绑定新模型信号，避免悬空回调与内存泄漏。
2. **唯一工作表删除保护**: 当仅剩 1 个工作表时，删除操作严格拦截并给出中文友好提示，防止工作簿进入非法空状态。
3. **重命名冲突与非法字符拦截**:
   - 验证字符集：禁止包含 `:\/?*[]`。
   - 验证长度：1 ~ 31 字符。
   - 禁止首尾含单引号 `'`。
   - 区分大小写不敏感的重名冲突检测。
4. **大量工作表溢出滚动**: 即使存在 50+ 个工作表，标签条平滑滚动，且在切换活动表时自动调用 `ensure_visible` 将当前标签卷入视口。
5. **i18n 本地化覆盖**: 所有菜单项、Tooltip、弹窗文字 100% 接入 `safe_tr()` / `tr()`，并实现 `retranslate_ui()`。
