# Implementation Plan: [Issue #195] 修正 Quire 工具栏控件和上下文状态

## Task Overview
根据原版 Word 2003 / Quire 对照规范，完善 Quire 模块中 10 个 Luna 工具栏的下拉和分裂按钮命令注册，接通业务动作，实现光标及选区上下文状态（表格、修订、对象）联动，并确保 7 语言动态刷新与测试回归。

---

## Task 1: 升级 `quire_toolbars.py` 下拉与分裂按钮及命令注册
- **Files**: `src/atboffice/ui/shell/quire_toolbars.py`
- **Details**:
  1. 建立 `_QUIRE_DROP_AIDS` 和 `_QUIRE_KNOWN_ITEM_AIDS` 映射字典，统筹所有下拉按钮和分裂按钮的 Action ID、国际化文案、默认可用状态与图标。
  2. 实现 `_add_menu_item(menu, item, parent_aid)`，支持注册 ActionSpec 或从已知字典创建 `QAction` 并注册至 `ActionRegistry`。
  3. 改进 `_add_drop`：设置 `drop_label` 与 `drop_aid` 属性，通过 `_add_menu_item` 接入菜单项，返回 `OfficeDropDownButton`。
  4. 改进 `_add_split`：主 Action 注册 `is_split=True`，菜单项通过 `_add_menu_item` 统一注册，返回 `OfficeSplitButton`。
  5. 改进 `retranslate_quire_toolbars`：递归遍历 10 个工具栏中的 `OfficeDropDownButton` 调用其 `retranslate_ui()`。
- **Verification**: `python -c "from atboffice.ui.shell.quire_toolbars import build_quire_toolbars"`

---

## Task 2: 在 `quire_window.py` 中接通业务动作与上下文状态机
- **Files**: `src/atboffice/ui/shell/quire_window.py`
- **Details**:
  1. 新增业务回调方法：
     - `apply_border_preset(preset: str)`
     - `apply_table_border(border_type: str)`
     - `set_table_cell_valign(align: str)`
     - `reorder_selected_object(direction: str)`
     - `nudge_selected_object(dx: int, dy: int)`
     - `align_selected_objects(alignment: str)`
     - `rotate_selected_object(angle: float)`
     - `insert_shape(shape_type: str)`
  2. 在 `_bind_action_handlers` 中注册所有下拉及分裂菜单动作处理器：
     - 撤销/重做空项
     - 常用工具栏表格与分栏下拉动作
     - 格式工具栏行距与边框下拉动作
     - 表格和边框工具栏插入、对齐、线型、粗细、底纹动作
     - 审阅工具栏接受/拒绝所有修订、删除所有批注动作
     - 绘图工具栏叠放次序、微移、对齐、自选图形各分类动作
  3. 强化上下文状态机 (`_sync_toolbar_states` 与 `update_context_toolbars`)：
     - 当光标离开表格时，禁用表格专属 Action (`mergeCells`, `splitCells`, `distRows`, `distCols`, `sortAsc`, `sortDesc`, `autoSum` 等)。
     - 当光标进入表格时，启用上述 Action，并显示 `tables` 工具栏。
     - 根据修订与批注状态动态更新 `acceptChange`、`rejectChange` 可用性。
- **Verification**: `python -m pytest tests/ui/test_quire_toolbar_wiring.py -v`

---

## Task 3: 编写并扩充测试集 `tests/ui/test_quire_toolbar_wiring.py`
- **Files**: `tests/ui/test_quire_toolbar_wiring.py`
- **Details**:
  1. `test_quire_toolbar_dropdown_and_split_wiring`: 验证常用、格式、表格、绘图、审阅工具栏的所有下拉与分裂按钮均已实例绑定且 Action 注册到 `ActionRegistry`。
  2. `test_quire_toolbar_actions_trigger_and_state`: 测试通过 `ActionRegistry.trigger_action` 触发各个菜单命令（如行距、边框预设、表格插入、自选图形等），验证文档或视图状态正确更新。
  3. `test_quire_toolbar_context_state_switching`: 验证光标在表格内和表格外切换时光标同步信号触发的 Action 启用/禁用与上下文工具栏显隐切换。
  4. `test_quire_toolbars_7_language_retranslate`: 验证 7 种语言切换下 `retranslate_ui` 稳定运行且无异常。
- **Verification**: `python -m pytest tests/ui/test_quire_toolbar_wiring.py tests/ui/test_toolbar_baseline_parity.py -v`

---

## Task 4: 全局回归测试与质量验证
- **Details**:
  - 运行 `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`
  - 确保除已知的 pre-existing 失败项外所有测试全部通过。
