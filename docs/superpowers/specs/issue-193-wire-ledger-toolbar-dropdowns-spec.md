# Specification: [Issue #193] 接通 Ledger 工具栏下拉及分裂按钮菜单

## 1. Overview & Problem Statement
原版 `ledger/js/app.js:595-608` 使用命令及菜单构建工具栏，而在 Python 移植版中，`ledger_toolbars.py` 的 `_add_drop` 和 `_add_split` 创建菜单项时，仅仅将文本转化为 `QAction` 加入 `QMenu`，未在 `ActionRegistry` 中注册业务命令，导致：
1. 菜单项与业务命令（如 AutoSum 各子函数、边框预设、公式审核有效性圈释、列表操作、图表类型、绘图叠放层次）处于断开状态；
2. 菜单项无法通过 `ActionRegistry` 统一进行 `trigger_action`、`set_enabled`、`set_checked` 管理；
3. 多语言动态切换（`retranslate_ui`）无法更新菜单项文案，导致中英混杂或翻译失效；
4. 不适用的能力（如空历史撤销/重做、组合/取消组合）未明确禁用。

本设计基于原版 `ledger/js/app.js`、`ledger/js/commands.js`、`ledger/js/ops.js` 规范，对 `_add_drop`、`_add_split`、`ActionRegistry`、`toolbar_buttons` 及 `LedgerWindow` 进行系统级接通与重构。

---

## 2. Requirements & Parity Matrix

### 2.1 Standard Toolbar (常用)
- `undo` (Split):
  - 主命令: `undo` (撤销, Ctrl+Z), 绑定 `win.undo`
  - 下拉项: `undo_empty` ("无操作可撤销" / "&Can't Undo"), 明确禁用 (`enabled=False`)
- `redo` (Split):
  - 主命令: `redo` (重做, Ctrl+Y), 绑定 `win.redo`
  - 下拉项: `redo_empty` ("无操作可重做" / "&Can't Redo"), 明确禁用 (`enabled=False`)
- `autoSum` (Split):
  - 主命令: `autoSum` (自动求和, Alt+=), 绑定 `win.auto_sum("SUM")`
  - 下拉项:
    - `autoSum_sum` -> `win.auto_sum("SUM")`
    - `autoSum_average` -> `win.auto_sum("AVERAGE")`
    - `autoSum_count` -> `win.auto_sum("COUNT")`
    - `autoSum_max` -> `win.auto_sum("MAX")`
    - `autoSum_min` -> `win.auto_sum("MIN")`
    - 分隔线 `-`
    - `autoSum_more` -> `win.open_function_wizard`

### 2.2 Formatting Toolbar (格式)
- `bordersApply` (Split):
  - 主命令: `bordersApply` (边框), 绑定 `win.apply_border_preset("all")`
  - 下拉项:
    - `border_bottom`: 下框线
    - `border_top`: 上框线
    - `border_left`: 左框线
    - `border_right`: 右框线
    - `border_none`: 无边框
    - `border_all`: 所有框线
    - `border_thick_box`: 粗外侧框线
    - `border_bottom_double`: 双下框线

### 2.3 Borders Toolbar (边框)
- `bordersPalette` (Split):
  - 主命令: `bordersPalette` (边框), 绑定 `win.apply_border_preset("outline")`
  - 下拉项:
    - `border_pal_none`: 无框线
    - `border_pal_bottom`: 下框线
    - `border_pal_top`: 上框线
    - `border_pal_all`: 所有框线
    - `border_pal_outside`: 外侧框线
    - `border_pal_thick`: 粗外侧框线
- `border_line_color` (Drop):
  - 主按钮: `border_line_color` (线条颜色)
  - 下拉项:
    - `border_color_auto`: 自动 (默认黑色/None)
    - `border_color_black`: 黑色 (`#000000`)
    - `border_color_red`: 红色 (`#FF0000`)
    - `border_color_blue`: 蓝色 (`#0000FF`)
    - `border_color_gray`: 灰色 (`#808080`)

### 2.4 Formula Auditing Toolbar (公式审核)
- `validation` (Split):
  - 主命令: `validation` (数据有效性), 绑定 `win.data_validation`
  - 下拉项:
    - `validation_dlg`: 数据有效性对话框
    - `circleInvalid`: 圈释无效数据 (`win.circle_invalid`)
    - `clearCircles`: 清除无效数据圈 (`win.clear_circles`)

### 2.5 List Toolbar (列表)
- `list_menu` (Drop):
  - 主按钮: `list_menu` (列表)
  - 下拉项:
    - `insertRows`: 插入行 (`win.insert_rows`)
    - `insertCols`: 插入列 (`win.insert_columns`)
    - 分隔线 `-`
    - `sortDlg`: 排序对话框 (`win.quick_sort`)
    - `autoFilter`: 自动筛选 (`win.toggle_auto_filter`, checkable)
    - 分隔线 `-`
    - `totalRow`: 汇总行 (`win.toggle_total_row`, checkable)
    - `convertToRange`: 转换为区域 (`win.convert_table_to_range`)

### 2.6 Chart Toolbar (图表)
- `chart_type_menu` (Drop):
  - 主按钮: `chart_type_menu` (图表类型)
  - 下拉项:
    - `chart_type_column`: 柱形图
    - `chart_type_line`: 折线图
    - `chart_type_pie`: 饼图
    - `chart_type_bar`: 条形图
    - `chart_type_area`: 面积图
    - `chart_type_scatter`: 散点图
    - `chart_type_radar`: 雷达图

### 2.7 Drawing Toolbar (绘图)
- `draw_menu` (Drop):
  - 主按钮: `draw_menu` (绘图)
  - 下拉项:
    - `bringToFront`: 置于顶层 (`win.bring_to_front`)
    - `sendToBack`: 置于底层 (`win.send_to_back`)
    - 分隔线 `-`
    - `draw_group`: 组合 (不适用，明确禁用 `enabled=False`)
    - `draw_ungroup`: 取消组合 (不适用，明确禁用 `enabled=False`)

---

## 3. Architecture & Interface Design

### 3.1 `ledger_toolbars.py`
重构 `_add_split` 与 `_add_drop`：
- 支持传入富元组 `(aid, label)`、`(aid, label, enabled)`、`(aid, label, enabled, checkable)`、`ActionSpec` 或 `str`。
- 每个菜单项通过 `self._reg_act(aid, ...)` 统一在 `action_registry` 注册，确保拥有独立的命令标识符、快捷键与状态。
- 使用规范的 English i18n key 或本地化文本，建立全局 `_LEDGER_I18N_MAP` 字典，确保 7 国语言（zh-CN, en, ja, ko, fr, de, zh-Hant）均能 100% 匹配。

### 3.2 `toolbar_buttons.py`
- 为 `OfficeDropDownButton` 增加 `_raw_text` 属性与 `retranslate_ui(tr_func)` 支持。
- 增强 `OfficeSplitButton` 和 `OfficeDropDownButton` 的 `menu` 行为与事件派发。

### 3.3 `action_registry.py`
- 支持 `has_action`、`get_action`、`trigger_action`、`set_enabled`、`set_checked`、`is_enabled`、`is_checked`。
- `retranslate_ui` 遍历所有 specs（包含 split 及 drop 下拉注册项）并更新文案与提示。

### 3.4 `ledger_window.py`
- 在 `_bind_action_handlers` 中将所有新增命令（如 `autoSum_average`, `insertRows`, `insertCols`, `autoFilter`, `convertToRange`, `chart_type_*`, `border_color_*`, `bringToFront`, `sendToBack` 等）与窗口业务逻辑完成单点绑定。
- 实现 `insert_rows`、`insert_columns`、`toggle_auto_filter`、`convert_table_to_range`、`set_chart_type`、`apply_border_color` 等核心逻辑。

---

## 4. Verification Plan
1. 执行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_ledger_toolbar_wiring.py -v`。
2. 扩充 `test_ledger_toolbar_wiring.py`，全面覆盖：
   - 所有下拉与分裂菜单项在 `action_registry` 的存在性；
   - 触发每个子命令的业务效果验证（求和、平均值、计数、最大值、最小值、插入行、插入列、边框预设、颜色应用、图表类型、层级调整等）；
   - 禁用项状态验证（`undo_empty`, `redo_empty`, `draw_group`, `draw_ungroup` 的 `isEnabled() == False`）；
   - 动态语言切换（`retranslate_ui`）下，所有下拉与分裂项的本地化文案验证。
