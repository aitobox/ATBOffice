# Specification: [Phase 2] Ledger 8 套工具栏声明式构建与命令接入

- **Issue**: #100
- **Branch**: `agent/issue-100-ledger-toolbars`
- **Related Spec**: `docs/superpowers/specs/2026-10-29-phase2-1to1-reconstruction-design.md`

## 1. Overview & Problem Statement
当前 `LedgerWindow` 仅硬编码了基础常用与格式工具栏的少量按钮，缺失了边框 (borders)、公式审核 (auditing)、审阅 (reviewing)、列表 (list)、图表 (chart) 和绘图 (drawing) 等 6 套工具栏，并且没有接入统一的 `ActionRegistry` 命令总线。

原版 `.vibeoffice/public/ledger/js/app.js` 拥有完备的 8 套 Excel 2003 Luna 工具栏体系（standard, formatting, borders, auditing, reviewing, list, chart, drawing），支持 SplitButton（自动求和、边框、撤销/重做）、DropDownButton（列表操作、图表类型、绘图菜单）、颜色拾取器以及上下文感知显隐控制（如选中图表时动态呈现 Chart 工具栏，在 Table 区域呈现 List 工具栏）。

本项目将对照原版规格，在 Python / PySide6 中实现 1:1 声明式构建 8 套工具栏，接入 `ActionRegistry`，并无缝集成到 `LedgerWindow` 中。

## 2. Architecture & Design

### 2.1 模块结构
1. **`src/atboffice/ui/shell/ledger_toolbars.py`**:
   - `LedgerToolBarCluster`: 工具栏构建器类，接收 `QMainWindow` 和 `ActionRegistry`。
   - `build_ledger_toolbars(window, action_registry)`: 工厂函数，返回 `dict[str, OfficeToolBar]` 包含 8 套工具栏。
   - `retranslate_ledger_toolbars(toolbars)`: 多语言动态重译函数。
   - `safe_tr(text)`: 上下文安全的 Qt 国际化函数。

2. **`src/atboffice/ui/shell/ledger_window.py`**:
   - 实例化 `ActionRegistry(self)` 并注册核心动作处理函数。
   - 调用 `build_ledger_toolbars` 创建 8 套工具栏。
   - `drawing` 工具栏停靠在底部 `Qt.ToolBarArea.BottomToolBarArea`。
   - 其他 7 套工具栏停靠在顶部 `Qt.ToolBarArea.TopToolBarArea`。
   - 保留向后兼容别名：`toolbar_standard`, `toolbar_formatting`, `act_bold`, `act_italic`, `act_underline`, `btn_font_color`, `btn_fill_color`。
   - 实现 `set_toolbar_mode(name, mode)` 与 `update_context_toolbars(context)`。
   - 实现 `retranslate_ui()`。

### 2.2 8 套工具栏清单与控件规范

1. **常用 (standard)**:
   - 新建 (`newBook`), 打开 (`open`), 保存 (`save`)
   - 分隔符
   - 打印 (`print`), 打印预览 (`printPreview`), 拼写检查 (`spelling`)
   - 分隔符
   - 剪切 (`cut`), 复制 (`copy`), 粘贴 (`paste`), 格式刷 (`formatPainter`)
   - 分隔符
   - 撤销 (Split: `undo`), 重做 (Split: `redo`)
   - 分隔符
   - 超链接 (`hyperlink`), 自动求和 (Split: `autoSum`, 下拉菜单含 求和, 平均值, 计数, 最大值, 最小值, 其他函数...), 升序 (`sortAsc`), 降序 (`sortDesc`)
   - 分隔符
   - 图表向导 (`chartWizard`), 绘图 (`tb_drawing`), 缩放比例 (`zoomCombo`), 帮助 (`help`)

2. **格式 (formatting)**:
   - 字体 ComboBox (`fontCombo`), 字号 ComboBox (`sizeCombo`)
   - 分隔符
   - 加粗 (`bold`), 倾斜 (`italic`), 下划线 (`underline`)
   - 分隔符
   - 左对齐 (`alignLeft`), 居中 (`alignCenter`), 右对齐 (`alignRight`), 合并及居中 (`mergeCenter`)
   - 分隔符
   - 货币样式 (`currencyStyle`), 百分比样式 (`percentStyle`), 千位分隔样式 (`commaStyle`), 增加小数位数 (`incDecimal`), 减少小数位数 (`decDecimal`)
   - 分隔符
   - 减少缩进 (`decIndent`), 增加缩进 (`incIndent`)
   - 分隔符
   - 边框 (Split: `borderSplit`), 填充颜色 (ColorPickerButton `fill`), 字体颜色 (ColorPickerButton `font`)

3. **边框 (borders)**:
   - 边框应用 (Split: `bordersApply`), 无框线 (`borderNone`), 外侧框线 (`borderOutline`), 粗外框线 (`borderThickOutline`), 绘制边框线 (`drawBorder`), 擦除边框 (`eraseBorder`), 边框颜色 (Drop: `borderLineColor`)

4. **公式审核 (auditing)**:
   - 错误检查 (`traceError`)
   - 分隔符
   - 追踪引用单元格 (`tracePrecedents`), 追踪从属单元格 (`traceDependents`), 移去所有箭头 (`removeArrows`)
   - 分隔符
   - 新建批注 (`insertComment`), 数据有效性 (Split: `validation`), 圈释无效数据 (`circleInvalid`), 清除无效数据圈 (`clearCircles`)
   - 分隔符
   - 监视窗口 (`watchWindow`), 公式求值 (`evaluateFormula`)

5. **审阅 (reviewing)**:
   - 新建批注 (`insertComment`), 显示/隐藏批注 (`showHideComment`), 删除批注 (`deleteComment`)
   - 分隔符
   - 显示所有批注 (`showComments`)

6. **列表/表格 (list)**:
   - 列表操作 (Drop: `listDrop`: 插入行, 插入列, 排序, 自动筛选, 汇总行, 转换为区域), 汇总行切换 (`totalRow`)

7. **图表 (chart)**:
   - 图表类型 (Drop: `chartTypeDrop`: 柱形图, 折线图, 饼图, 条形图, 面积图, 散点图, 雷达图), 设置所选对象格式 (`formatObject`)

8. **绘图 (drawing)**:
   - 绘图菜单 (Drop: `drawDrop`: 置于顶层, 置于底层, 组合, 取消组合)
   - 分隔符
   - 自选图形/矩形 (`insertShape`), 文本框 (`insertTextBox`), 插入图片 (`insertPicture`)
   - 分隔符
   - 填充颜色 (ColorPickerButton `drawingFillColor`)

### 2.3 默认显隐与上下文感知规则
- `standard`: `True` (常驻)
- `formatting`: `True` (常驻)
- `drawing`: `False` (默认隐藏，可通过工具栏按钮或菜单开启，停靠在底部)
- `borders`: `False` (默认隐藏)
- `auditing`: `False` (默认隐藏)
- `reviewing`: `False` (默认隐藏)
- `chart`: `'auto'` (当 `ctx.get("is_chart")` 或 `selected_object.kind == "chart"` 为真时显示，否则隐藏)
- `list`: `'auto'` (当 `ctx.get("in_table")` 或在列表数据区域时显示，否则隐藏)

## 3. Testing Strategy
- 创建 `tests/ui/test_ledger_toolbars.py`:
  1. 验证 8 套工具栏实例存在于 `LedgerWindow.toolbars`，键名完整对齐；
  2. 验证 `drawing` 工具栏位于 `BottomToolBarArea`；
  3. 验证 `ActionRegistry` 动作注册与信号触发；
  4. 验证 特殊控件（QComboBox、ColorPickerButton、OfficeSplitButton、OfficeDropDownButton）；
  5. 验证 上下文感知显隐逻辑（`is_chart`, `in_table` 及覆盖配置）；
  6. 验证 `retranslate_ui` 动态重译；
  7. 保证已有的 `tests/test_dedicated_windows.py` 全部通过。
