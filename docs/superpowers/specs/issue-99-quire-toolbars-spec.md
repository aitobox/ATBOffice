# Specification: Issue #99 - Quire 10 套工具栏声明式构建与命令接入

## 1. Overview & Problem Statement
当前 `QuireWindow` 仅硬编码了标准和格式工具栏的几个按钮，缺失了表格、审阅、大纲、页眉页脚、绘图、邮件合并、图片、艺术字等工具栏。
原版 `quire/js/app.js` 拥有 10 套完备的 Office 2003 Luna 工具栏体系。本项目对照原版规格，1:1 全量落地 Quire 10 套工具栏，并接入 `ActionRegistry` 统一命令驱动总线，实现上下文感知的动态显隐控制。

## 2. Architecture & Design

### 2.1 模块结构与职责划分
- **`src/atboffice/ui/shell/quire_toolbars.py`**:
  - 声明式定义 Quire 10 套工具栏构建器类 `QuireToolBarCluster`。
  - 提供 `build_quire_toolbars(window, action_registry) -> dict[str, OfficeToolBar]` 工厂函数。
  - 构建各专用工具栏及其特有控件（组合框 `QComboBox`、颜色下拉器 `ColorPickerButton`、分裂按钮 `OfficeSplitButton`、下拉按钮 `OfficeDropDownButton`）。
  - 封装多语言更新函数 `retranslate_quire_toolbars(toolbars, tr_func)`。

- **`src/atboffice/ui/shell/quire_window.py`**:
  - 持有 `self.action_registry: ActionRegistry`。
  - 持有 `self.toolbars: dict[str, OfficeToolBar]`，按 ID 索引：
    1. `standard` (常用)
    2. `formatting` (格式)
    3. `tables` (表格与边框)
    4. `reviewing` (审阅)
    5. `outlining` (大纲)
    6. `headerFooter` (页眉页脚)
    7. `drawing` (绘图，停靠于底部)
    8. `mailMerge` (邮件合并)
    9. `picture` (图片)
    10. `wordart` (艺术字)
  - 维护 `self.toolbar_modes: dict[str, bool | str]`（`True`, `False`, 或 `'auto'`）。
  - 实现上下文感知显隐管理：`update_context_toolbars()`，响应光标选区对象（表格内、图片、艺术字、大纲视图、页眉页脚编辑状态等）。
  - 完善 `retranslate_ui()`。

### 2.2 10 套工具栏 1:1 对齐清单

1. **常用工具栏 (`standard`)**：
   - 按钮项：`new`, `open`, `save`, `permission`, `sendMail`, `print`, `printPreview`, `spelling`, `research`
   - 分隔符 `|`
   - 按钮项：`cut`, `copy`, `paste`, `painter`
   - 分隔符 `|`
   - 分裂按钮：`undo` (撤销历史下拉), `redo` (重做历史下拉)
   - 分隔符 `|`
   - 按钮项：`hyperlink`, `tb_tables` (切换表格工具栏)
   - 下拉项：`insertTable` (表格插入网格/菜单), `insertExcel`
   - 下拉项：`columns` (分栏菜单)
   - 按钮项：`tb_drawing` (切换绘图工具栏), `docMap`, `showMarks`
   - 组合框：`zoomCombo` (25% ~ 500%、页宽、整页等)
   - 按钮项：`help`, `viewReading` (阅读版式)

2. **格式工具栏 (`formatting`)**：
   - 按钮项：`stylesPane`
   - 组合框：`styleCombo` (样式), `fontCombo` (字体), `sizeCombo` (字号)
   - 切换按钮：`bold`, `italic`, `underline`
   - 分隔符 `|`
   - 互斥/切换按钮：`alignLeft`, `alignCenter`, `alignRight`, `justify`
   - 分隔符 `|`
   - 下拉菜单：`lineSpacing` (1.0, 1.5, 2.0, 2.5, 3.0 等)
   - 分隔符 `|`
   - 按钮项：`numbering`, `bullets`, `decIndent`, `incIndent`
   - 分隔符 `|`
   - 控件项：`borderBtn` (边框分裂按钮), `highlightBtn` (高亮颜色拾取), `fontColorBtn` (字体颜色拾取)

3. **表格与边框工具栏 (`tables`)**：
   - 按钮项：`drawTable` (绘制表格), `eraser` (擦除)
   - 分隔符 `|`
   - 下拉项：`dashStyle` (线型), `lineStyle` (线宽), `lineColor` (边框颜色)
   - 分裂项：`borderBtn` (应用边框), `fillColor` (底纹颜色)
   - 分隔符 `|`
   - 下拉项：`insertTable` (插入表/列/行), 按钮项：`mergeCells`, `splitCells`
   - 分隔符 `|`
   - 下拉项：`alignTop` (对齐方式), 按钮项：`distRows`, `distCols`
   - 分隔符 `|`
   - 按钮项：`tableAutoFormat`, `textDirection`
   - 分隔符 `|`
   - 按钮项：`sortAsc`, `sortDesc`, `autoSum`

4. **审阅工具栏 (`reviewing`)**：
   - 下拉项：`displayForReview` (显示标记的最终状态等)
   - 下拉项：`showMarkup` (显示批注/墨迹/插入删除等)
   - 分隔符 `|`
   - 按钮项：`prevChange`, `nextChange`
   - 分隔符 `|`
   - 分裂项：`acceptChange`, `rejectChange`
   - 分隔符 `|`
   - 按钮项：`insertComment`, `trackChanges`, `reviewingPane`

5. **大纲工具栏 (`outlining`)**：
   - 按钮项：`promoteH1`, `promote`
   - 组合框：`outlineLevel` (正文文本、1 级 ~ 9 级)
   - 按钮项：`demote`, `demoteBody`
   - 分隔符 `|`
   - 按钮项：`moveUp`, `moveDown`, `expand`, `collapse`
   - 组合框：`showLevel` (显示所有级别、1 级 ~ 9 级)
   - 按钮项：`olFirstLine`, `olFormatting`
   - 分隔符 `|`
   - 按钮项：`updateTOC`, `gotoTOC`

6. **页眉页脚工具栏 (`headerFooter`)**：
   - 下拉项：`insertAutoText` (自动图文集)
   - 分隔符 `|`
   - 按钮项：`hfPageNum`, `hfNumPages`, `hfFormatPageNum`, `hfDate`, `hfTime`
   - 分隔符 `|`
   - 按钮项：`pageSetup`, `hfShowText`, `hfLinkPrev`
   - 分隔符 `|`
   - 按钮项：`hfSwitch`, `hfPrev`, `hfNext`
   - 分隔符 `|`
   - 按钮项：`hfClose` (关闭页眉和页脚)

7. **绘图工具栏 (`drawing`)**：
   - 下拉项：`drawMenu` (绘图菜单)
   - 按钮项：`selectObjects`
   - 分隔符 `|`
   - 下拉项：`autoShapes` (自选图形)
   - 按钮项：`drawLine`, `drawArrow`, `drawRect`, `drawOval`, `textBox`, `insertWordArt`, `insertDiagram`, `insertClipArt`, `insertPicture`
   - 分隔符 `|`
   - 颜色控件：`fillColor`, `lineColor`, `fontColorBtn`
   - 分隔符 `|`
   - 下拉项：`lineStyle`, `dashStyle`, `arrowStyle`, `shadowStyle`

8. **邮件合并工具栏 (`mailMerge`)**：
   - 按钮项：`mmMainDoc`, `mmOpenSource`, `mmRecipients`
   - 分隔符 `|`
   - 按钮项：`mmAddress`, `mmGreeting`, `mmInsertField`
   - 分隔符 `|`
   - 按钮项：`mmViewData`, `mmFirst`, `mmPrev`
   - 控件项：`mmRecord` (记录号微调框/文本框)
   - 按钮项：`mmNext`, `mmLast`
   - 分隔符 `|`
   - 按钮项：`mmMergeNew`, `mmMergePrint`

9. **图片工具栏 (`picture`)**：
   - 按钮项：`insertPicture`
   - 下拉项：`colorPic` (自动、灰度、黑白、冲蚀)
   - 按钮项：`moreContrast`, `lessContrast`, `moreBright`, `lessBright`, `crop`
   - 下拉项：`rotatePic`, `lineStyle`
   - 按钮项：`formatObject`, `setTransparent`, `resetPicture`

10. **艺术字工具栏 (`wordart`)**：
    - 按钮项：`insertWordArt`, `wordartEdit`, `wordartGallery`, `formatObject`
    - 下拉项：`wordartShape` (40 种文字环绕与形状变换), `textWrap` (文字环绕)

### 2.3 上下文感知机制 (Contextual Toolbar Visibility)
- 原版 `app.js` 规则：
  - `standard`: 始终可见（阅读/预览视图除外）
  - `formatting`: 始终可见（阅读/预览视图除外）
  - `drawing`: 默认停靠底部（或用户开关）
  - `tables`: `'auto'`，当光标位于表格内（`in_table`）时自动展示
  - `reviewing`: `'auto'`，当存在修订、批注或开启修订模式时自动展示
  - `picture`: `'auto'`，当选中文档中的图像对象时自动展示
  - `outlining`: `'auto'`，当处于大纲视图时展示
  - `headerFooter`: `'auto'`，当正在编辑页眉页脚时展示
  - `wordart`: `'auto'`，当选中艺术字或图形对象时展示
  - `mailMerge`: `False`，默认关闭，可通过菜单/视图开启
- 当用户手动切换某一工具栏状态（通过菜单项勾选）时，该工具栏锁定为用户指定状态（`True` 或 `False`）。

### 2.4 命令接入与 ActionRegistry 双向联动
- 每个工具栏按钮通过 `ActionRegistry.register_action(spec)` 注册或复用已注册的 Action。
- 按钮触发时统一发射 `ActionRegistry.action_triggered` 信号。若对应操作在窗口中有真实绑定（如保存、撤销、加粗），由特定 handler 响应；未完全联调的功能由 ActionRegistry 统一在状态栏输出友好提示 `safe_tr("功能正在联调中")`。
- 所有按钮具备原生 ToolTip 与快捷键提示。

## 3. Edge Cases & Robustness
1. **频繁选区变更性能**：`update_context_toolbars` 仅在目标状态与当前 `isVisible()` 不一致时执行 `setVisible`，避免引起不必要的重绘布局振荡。
2. **多语言即时刷新**：`retranslate_ui` 递归更新所有 10 套工具栏的标题、Tooltip、下拉框条目。
3. **父子对象生命周期安全**：所有新建控件均指定对应工具栏为父对象，杜绝 Qt 析构时悬垂指针与内存泄漏。
4. **测试覆盖**：编写专用测试套件 `tests/ui/test_quire_toolbars.py`，完整覆盖 10 套工具栏的实例化、按钮数量对齐、ActionRegistry 命令触发、上下文显隐切换与多语言更新。
