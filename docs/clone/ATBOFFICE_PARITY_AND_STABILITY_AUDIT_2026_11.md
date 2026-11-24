# ATBOffice vs. `.vibeoffice` 全量对比、稳定性及主干功能深度审计报告

> **审计基准日期**: 2026-11-21  
> **对照基线**: `.vibeoffice/`（原版 JS/HTML 黄金实现） vs. `src/atboffice/`（PySide6/Qt6 移植版，Commit `96a61d3`）  
> **真机崩溃日志证据**: [crash.log](file:///Users/brainzhang/.atboffice/logs/crash.log)（1,890 行，含 `2026-11-21` 最新实测崩溃栈）  
> **双端视觉比对报告**: [OFFICE_DOCS_DIFF.md](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/clone/OFFICE_DOCS_DIFF.md)  
> **GitHub 整改跟踪（第 11 期）**: [Epic #436](https://github.com/aitobox/ATBOffice/issues/436)（[#437](https://github.com/aitobox/ATBOffice/issues/437) – [#448](https://github.com/aitobox/ATBOffice/issues/448)，实施计划见 [11_phase11_stability_print_ui_parity_plan.md](file:///Users/brainzhang/work/aitobox/ATBOffice/docs/tasks/11_phase11_stability_print_ui_parity_plan.md)）  
> **发布评估结论**: **⚠️ NOT SHIPPABLE（存在 P0 级崩溃、数据丢失、按钮空桩及打印预览严重失真）**

---

## 一、 执行摘要（Executive Summary）

本次结合 `atb-office-diff`（73 份核心 OOXML 文档双端截图像素与前景加权比对）、`atb-clone-diff` 源码三层映射扫描、真实运行期崩溃日志（[crash.log](file:///Users/brainzhang/.atboffice/logs/crash.log)）以及逐模块源码审计，全面定位了当前实现中观察到的四大核心问题：

| 审计维度 | 核心问题摘要 | 影响范围 | 严重程度 |
|---|---|---|---|
| **视觉比对 (`atb-office-diff`)** | 73 份核心文档像素 MAE 均值 `96.91%`，但**前景加权相似度仅 `65.31%`**（`22 PARITY_MATCH`、`2 COSMETIC_MINOR`、`19 LAYOUT_DRIFT`、`30 CRITICAL_MISMATCH`）。存在画布顶部边距偏移（+20px）、Excel 行号列偏宽（+14px）、3D 图表退化为 2D 等系统性漂移。 | Word / Excel / PPT | **High (P1)** |
| **1. UI 按键与交互响应缺失** | `MacMenuBar` 与 `ActionRegistry` 双重/三重信号连接；`alias` 未写入 `_specs` 导致 18 个 Lectern 动作绑定失效；110+ 工具栏/菜单动作落入 `"正在联调中"`；Quire **29 个弹窗丢弃返回值**；Lectern **27 个处理函数为空桩或未重绘**；**Save As 覆盖原文件**。 | 全局三模块 + 启动中心 | **Critical (P0)** |
| **2. 打印预览效果不理想** | 点击打印预览连续弹出**两个**原生 `QPrintPreviewDialog`（且实测触发 C++ `Segmentation fault`）；未调用 `setPageSize`/`setPageOrientation`/`setFullPage(True)` 导致内容裁切与双倍页边距；Quire 独立打印绘制定制版丢弃列表编号、高亮与表格自定义边框；Ledger 丢弃页面设置与全部图表图片；Lectern 写死 `960×540` 纵向。 | 全局打印与预览 | **High (P1)** |
| **3. 操作一段时间后 Crash 崩溃** | `crash.log` 记录到 **7 次 C++ `Segmentation fault`** 与 **45+ 次未捕获 Python 异常**：`MacMenuBar` 重入弹窗崩溃、`closeEvent` 内同步强排 `drain_event_loop` 触发 C++ Use-After-Free、Ledger `SpreadsheetObjectLayer` 抢焦点并用错 `QKeyEvent.StandardKey`、13 处单元格格式化未判 `None`、Quire 每次改格式即调用 `set_document` 清空撤销栈、Lectern 编辑器与 `SlideScene` 生命周期冲突。 | 全局 `.docx`/`.xlsx`/`.pptx` | **Blocker (P0)** |
| **4. `.vibeoffice` 主干功能遗漏** | 缺少 Paper 2016 Ribbon 模式与上下文自动跟随面板；`RecoveryService.start()` 从未调用导致自动恢复未启用；`.rtf`/`.md`/`.zip`/`.html`/`.png` 另存为会写出 **0 字节空文件**；加密文件保存丢失密码；Clipart/WordArt 插入空转；Excel 动态数组溢出/`Table1[Col]`/Solver/大纲分组缺失；Word 页眉页脚画布内编辑与浮动图拖拽缺失；PPT 动效预览断链与真机音视频播放缺失。 | 全套件主干能力 | **High (P1–P2)** |

---

## 二、 `atb-office-diff` 73 份核心文档双端视觉渲染对比结果

### 2.1 总体量化指标（2026-11-21 最新实测）

通过运行 `scripts/run_office_diff.py --all --capture` 对 73 份核心 OOXML 文档（Word 24、Excel 24、PowerPoint 25）与 `.vibeoffice` 基准图进行画布级比对：

| 指标 | 最新实测值 | 门禁要求 | 说明 |
|---|---:|---|---|
| **可比对文档数** | `73 / 73` | 73 | 无尺寸不匹配或缺失截图 |
| **平均前景加权相似度（Foreground）** | **`65.31%`** | `>= 90.0%` | 前景文字与图形对齐度，因全局偏移被严重拉低 |
| **平均像素相似度（Pixel MAE）** | `96.91%` | 参考指标 | 大面积白底掩盖了文字/网格线整体位移 |
| **`PARITY_MATCH` (>= 95%)** | `22` | - | PowerPoint 占 22 份，Word 0 份，Excel 0 份 |
| **`COSMETIC_MINOR` (85% - 95%)** | `2` | - | Word 1 份，PowerPoint 1 份 |
| **`LAYOUT_DRIFT` (70% - 85%)** | `19` | `0` | Excel 14 份、Word 3 份、PPT 2 份 |
| **`CRITICAL_MISMATCH` (< 70%)** | `30` | `0` | Word 20 份、Excel 10 份、PPT 0 份 |

### 2.2 视觉 Diff 热力图揭示的 4 大根因

1. **Word（Quire）画布顶部边距系统性下移约 20px（导致大量 `0.0%` 前景错位）**
   - **定位**: [canvas_view.py:L437](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/writer/views/canvas_view.py#L437) `WriterCanvasView.page_rect_canvas()` 写死初始 `cur_y = 33.0`，而 `.vibeoffice` 画布顶部空白显著更小。
   - **现象**: 在 [libreoffice__A019_min.docx_diff.png](file:///Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/word/libreoffice__A019_min.docx_diff.png) 中，仅一行 `"Hello"` 的最简文档像素 MAE 高达 `99.0%`，但因纸张与文本整体下移约 20px 导致前景重叠率为 `0.0%`，其余 19 份 DOCX 均受此全局偏移连带扣分。
2. **Excel（Ledger）左侧行号列宽度偏大（导致全表向右偏移约 14px）**
   - **定位**: [grid_viewport.py:L202](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/views/grid_viewport.py#L202) 定义 `self.row_header_width: int = 46`，比 `.vibeoffice` 的行号表头宽约 14px。
   - **现象**: 在 [libreoffice__Pivot2_Row.xlsx_diff.png](file:///Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/libreoffice__Pivot2_Row.xlsx_diff.png) 和 [poi__SimpleWithComments.xlsx_diff.png](file:///Users/brainzhang/work/aitobox/ATBOffice/screenshots/docs_diff/excel/poi__SimpleWithComments.xlsx_diff.png) 中，A 列及所有网格线、单元格文字、批注气泡均整体右移，导致前景重合度跌至 `30%~75%`。
3. **PowerPoint（Lectern）3D 图表退化为 2D 渲染 & SmartArt 主题填充与圆角偏移**
   - **定位**: [painter.py:L119-L158](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/presentation/chart/painter.py#L119-L158) 中的 `ChartPainter.paint_chart` 仅处理 2D 类型（`"col"`, `"colStacked"`, `"colPct"` 等），未实现 3D 透视柱面/墙面绘制，导致 `openxml-sdk__Chart_3D (Column).pptx`（86.1%）退化为平面柱状图。
   - `libreoffice__smartart-text.pptx`（70.8%）在主题色调映射、圆角矩形半径及顶部文本内边距上与 `.vibeoffice` 存在明显偏差。
4. **Word 特定版式元素未完全对齐**
   - `libreoffice__strict.docx`（47.2%）：嵌入式图表 Y 轴刻度步长（0.5 vs 1.0）及 SmartArt 纵坐标未对齐。
   - `openxml-sdk__Comment066.docx`（82.5%）：阿拉伯语 RTL 段落断行宽度与右侧批注气泡样式有偏移。
   - `libreoffice__tdf105035_framePrB.docx`（79.4%）与 `libreoffice__tdf113182.docx`（73.7%）：`w:framePr` 文本框/表格边距与避让排版尚有差距。

---

## 三、 问题 1：部分功能缺失与 UI 按键/菜单/弹窗无响应或异常

经过对 [action_registry.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/action_registry.py)、[mac_menu.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py)、三模块窗口与工具栏代码的全面排查，共发现 **6 类系统性接线缺陷**，涉及 **180+ 处控件/命令**：

### 3.1 六大系统性接线缺陷

1. **双重/三重信号触发 (`DUPLICATE_SIGNAL_DOUBLE_FIRE`)**
   - **根因**: `ActionRegistry.register_action`（[action_registry.py:L95-L97](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/action_registry.py#L95-L97)）已将 `action.triggered` 连接到 `_on_action_triggered`；随后 `MacMenuBar._bind_window_slots`（[mac_menu.py:L448-L531](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L448-L531)）在**同一个 `QAction`** 上再次调用 `connect_if` 绑定第二个槽函数。
   - **后果**:
     - 在 Quire 与 Ledger 中点击或按快捷键触发 `undo`/`redo`/`cut`/`copy`/`paste`/`new`/`open`/`save`/`printPreview`/`find`/`replace`/`view_fullscreen`/`zoom_in`/`zoom_out`/`tools_options` 等会**连续执行 2 次**（例如按一次 `Cmd+Z` 撤销两步，点击全屏立即打开又关闭，打开选项弹窗关闭后立刻再弹出第二个通用选项弹窗）。
     - 在 Ledger 中，`file_print` 被同时绑定了 `print_document`（[mac_menu.py:L466](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L466)）、`print_workbook`（[mac_menu.py:L467](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L467)）以及 `ActionRegistry` 的 `"print"`，点一次打印连续弹出 **3 个打印对话框**。
     - 仅通过 `connect_if` 绑定而未调用 `action_registry.set_handler` 的动作（如 `close`、`save_as`、主题切换、窗口菜单、关于/检查更新等），因 `spec.handler is None`，每次触发都会在状态栏错误闪烁 `"xxx 正在联调中"`，且全局命令搜索框 `CommandSearchBox` 无法调用它们。
2. **`MacMenuBar._reg_act` 别名未注册进 `_specs` (`ACTION_ID_MISMATCH_AND_ALIAS_BUG`)**
   - **根因**: [mac_menu.py:L85-L88](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L85-L88) 仅把 `alias` 写入 `action_registry._actions[alias]` 而未写入 `_specs[alias]`；而 [action_registry.py:L185-L187](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/action_registry.py#L185-L187) 的 `set_handler` 检查 `self._specs.get(action_id)`。
   - **后果**: `LecternWindow` 中 **18 处使用别名的 `set_handler` 调用全部静默失效**（如 `file_new`、`file_open`、`file_save`、`file_save_as`、`file_print`、`edit_undo`、`edit_select_all`、`view_task_pane`、`insert_hyperlink`、`format_bullets`、`tools_spelling` 等）。同时，菜单与工具栏大量混用 `snake_case` 与 `camelCase`（见下表）。
3. **跨模块菜单项错配与重复注册**
   - `MacMenuBar`（[mac_menu.py:L330-L341](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L330-L341)）把 `insert_clipart`、`insert_picture`、`insert_wordart`、`insert_shape` 同时加进 `图片` 子菜单和顶层 `插入` 菜单。
   - Word 专属的 `view_web`/`view_print`/`view_reading`/`view_outline`/`view_doc_map`/`view_thumbnails`/`wordCount`、Excel 专属的 `view_page_break`/`insert_function`、PPT 专属的 `background` 均无条件显示在全套件菜单中，在非所属模块点击即提示 `"正在联调中"`。
4. **110+ 工具栏/菜单动作无绑定处理器 (`UNHANDLED_FALLBACK_TOAST`)**
   - 触发后落入 [action_registry.py:L226](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/action_registry.py#L226) 弹出状态栏提示 `"{label} 正在联调中"`。
5. **弹窗返回值丢弃 (`DIALOG_DISCARDS_RESULT`) 与伪造空桩 (`TOAST_ONLY_STUB`)**
   - Quire 中 **29 个模态弹窗方法**只执行 `dlg.exec()` 却不读取也不应用设置；Lectern 中 **27 个操作方法**只显示状态栏提示或改写字典字段而不刷新画布。
6. **组件级交互缺陷与孤立控件 (`ORPHAN_NO_SIGNAL`)**
   - 三模块的撤销/重做分裂按钮（`OfficeSplitButton`）下拉菜单均为写死的单条禁用项（`"无操作可撤销"` / `"无操作可重做"`），从未从 Undo/Redo 栈动态填充。
   - `Quire_ShowLevelCombo`（大纲级别下拉）、`Quire_MMRecordCombo`（邮件合并记录下拉）、绘图工具栏 3 个 `ColorPickerButton`、阅读版式工具栏的 `single_page_requested`/`multi_page_requested` 信号、新建文档窗格的 `"new_web"` 按钮均未连接信号。
   - Quire 文本突出显示按钮使用 `"fill"` 模式的 40 色盘，选择“无颜色”时传递字符串 `"none"` 给 `set_highlight_color`（非 `None`），导致渲染器构造无效颜色绘出黑底。
   - `BaseOfficeWindow._show_getting_started_pane` 调用不存在的 `self.task_pane.switch_pane("getting_started")`，触发时直接抛出 `AttributeError`。

### 3.2 各模块失效按钮与空桩明细

#### A. 公共菜单栏命名不匹配 / 无处理器清单（[mac_menu.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py)）

| 菜单项 / Action ID | 影响模块 | 根因说明 |
|---|---|---|
| `insert_page_break` | 全部 3 模块 | Quire 绑 `"break"`、Ledger 绑 `"pageBreak"`，均未绑 `"insert_page_break"` |
| `insert_page_number` / `insert_date_time` / `insert_symbol` / `insert_shape` | 全部 3 模块 | 各窗口绑 `"pageNumbers"` / `"dateTime"` / `"symbol"` / `"insertShape"`，蛇形命名不匹配 |
| `format_font` / `format_paragraph` / `format_borders` / `format_tabs` / `tools_language` | 全部 3 模块 | 对应弹窗类已在 `writer/dialogs/` 实现，但从未绑定到菜单 ID |
| `table_insert` / `table_delete` / `table_select` / `table_properties` / `drawTable` | Quire | 菜单注册蛇形 ID，Quire 绑驼峰或未实现，点击全部 `"正在联调中"` |
| `headerFooter` / `data_filter` / `data_validation` | Ledger | Ledger 绑 `"header_footer_dlg"` / `"autoFilter"` / `"validation"`，命名不匹配 |
| `view_normal` / `view_outline` / `view_ruler` / `slideshow_rehearse` / `slideshow_transition` | Lectern | Lectern 绑 `"viewNormal"` / `"viewOutline"` / `"ruler"` / `"rehearse"` / `"transitionPane"` |
| `find` / `replace` | Lectern | Lectern 未实现查找/替换处理器及对话框 |

#### B. Quire（Word）失效按钮与空桩（[quire_toolbars.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_toolbars.py) & [quire_window.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py)）

- **工具栏完全未绑定（落入 `"正在联调中"`）**:
  - **页眉和页脚工具栏（16/16 按钮 100% 未绑定）**: `hf_at_page`、`hfPageNum`、`hfNumPages`、`hfFormatPageNum`、`hfDate`、`hfTime`、`pageSetup`、`hfShowText`、`hfLinkPrev`、`hfSwitch`、`hfPrev`、`hfNext`、`hfClose` 等全部无处理器。
  - **图片工具栏（18/18 按钮 100% 未绑定）**: `pic_insert`、颜色模式、对比度、亮度、裁剪、旋转、文字环绕（`wrap_inline`..`wrap_front`）、`formatObject`、`picReset` 全部无处理器。
  - **常用/审阅/大纲/表格与边框/绘图/邮件合并/艺术字**: `painter`（格式刷）、`showMarks`（显示/隐藏编辑标记）、`permission`、`sendMail`、`research`、`insertExcel`、`col_left`/`col_right`、`docMap`（ID 错配 `view_doc_map`）、`viewReading`（ID 错配 `view_reading`）、`drawTable`、`eraser`、表格线型/粗细/颜色/底纹、`rev_*` 审阅显示模式、`prevChange`/`nextChange`、`olFirstLine`/`olFormatting`/`updateTOC`/`gotoTOC`、`mmMergeNew`/`mmMergePrint`、`wa_*` 全部无处理器。
- **29 个模态弹窗丢弃结果（[quire_window.py:L474-L618](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py#L474-L618)）**:
  `open_break_dialog`、`open_drop_cap_dialog`、`open_text_direction_dialog`、`open_watermark_dialog`、`open_page_numbers_dialog`、`open_change_case_dialog`、`open_document_theme_dialog`、`open_footnote_dialog`、`open_caption_dialog`、`open_cross_ref_dialog`、`open_index_tables_dialog`、`open_bookmark_dialog`、`open_hyperlink_dialog`、`open_date_time_dialog`、`open_field_dialog`、`open_symbol_dialog`、`open_autocorrect_dialog`、`open_customize_dialog`、`open_quire_options_dialog`、`open_envelopes_labels_dialog`、`open_letter_wizard_dialog`、`open_autosummarize_dialog`、`open_hyphenation_dialog`、`open_insert_cells_dialog`、`open_delete_cells_dialog`、`open_split_cells_dialog`、`open_table_autoformat_dialog`、`open_table_sort_dialog`、`open_table_formula_dialog` 全部只调用 `dlg.exec(); return dlg`，未读写任何结果。
- **其他假实现与覆盖错误**:
  - `reorder_selected_object`、`nudge_selected_object`、`align_selected_objects`、`rotate_selected_object`、`insert_shape`（[quire_window.py:L1178-L1211](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py#L1178-L1211)）检查 `WriterCanvasView` 上不存在的同名方法后仅弹窗提示，插入自选图形完全无效。
  - `apply_border_preset` / `apply_table_border`（[L1213-L1240](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py#L1213-L1240)）将普通 `dict` 赋给 `borders` 而非数据类，导致边框无法渲染。
  - `promoteH1`..`moveDown` 在 `L211-L225` 绑定给 `outline_widget` 后，在 `L281-L286` 被 `canvas` 处理器覆盖。
  - `col_1`/`col_2`/`col_3` 调用不存在的 `canvas.set_columns`；`line_spacing_more` 写死 `1.5` 倍行距；缩放下拉框忽略 `"页宽"` 与 `"整页"`。

#### C. Ledger（Excel）失效按钮与空桩（[ledger_toolbars.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_toolbars.py) & [ledger_window.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py)）

- **工具栏未绑定**: `drawBorder`（绘制边框线）、`draw_group`、`draw_ungroup`。
- **菜单遗漏导致 15 个已实现处理器无法从菜单或搜索框触达**: `clearAll`..`clearComments`、`comment`、`defineName`、`condFormat`、`autoFormat`、`sortDlg`、`pageBreak`、`removePageBreaks`、`textToColumns`、`consolidate`、`scenarios`、`dataTable`、`protectSheet`、`protectWorkbook`、`advancedFilter` 等未加入 `MacMenuBar`。
- **假实现 / 缺陷**:
  - `check_spelling`（[ledger_window.py:L2553-L2559](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L2553-L2559)）直接弹出“已完成对整个工作表的拼写检查”假消息框。
  - `insert_picture`（[L2218-L2238](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L2218-L2238)）选完图片路径后丢弃路径与字节数据，只插入空白框。
  - `chart_wizard`（工具栏按钮）跳过 `ChartWizardDialog` 直接插入示例柱状图；而 `ChartWizardDialog._on_finish`（[chart_wizard.py:L724-L760](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/dialogs/chart_wizard.py#L724-L760)）未写入 `chart_data`，导致画布永远渲染写死的 Q1–Q4 假数据，且选“作为新工作表”时直接丢弃图表。
  - `SubtotalDialog`、`ConsolidateDialog`、`AdvancedFilterDialog`、`DataTableDialog`（竟用 `r_val * c_val` 替代公式求值）、`ScenarioManagerDialog`（摘要按钮仅弹假提示）均为断链或假逻辑。
  - `_apply_zoom`（[L807-L816](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L807-L816)）忽略 `"选定区域"`。

#### D. Lectern（PowerPoint）失效按钮与空桩（[lectern_toolbars.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_toolbars.py) & [lectern_window.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_window.py)）

- **Action ID 碰撞**: 绘图工具栏的“对齐或分布 -> 左对齐/居中/右对齐”复用 `"alignLeft"`/`"alignCenter"`/`"alignRight"`（[lectern_toolbars.py:L1011-L1013](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_toolbars.py#L1011-L1013)），点击时错误切换段落文本对齐而非图形对齐。
- **工具栏未绑定**: 图示工具栏的版式/颜色/样式子菜单（15 项）、表格线型/粗细/颜色/底纹（21 项）、图片线条样式（5 项）、艺术字 4 种形状及 5 种字符间距、绘图线型/虚线/箭头/阴影（18 项）。
- **27 个核心处理器为空桩或严重缺陷（[lectern_window.py:L979-L1628](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_window.py#L979-L1628)）**:
  - `insert_chart`（L979-1006）插入的是普通矩形 `Shape(type="shape", geom="rect")` 而非图表对象。
  - `insert_picture_from_file`（L1177-1203）完全不打开文件选择框，直接插入空图片占位框；`insertClipArt` 错误指向它而非 `open_clipart_dialog`。
  - `save_as_dialog`（L1626-1628）错误调用 `self.save_file()` 而非 `self.save_file_as()`，已有路径时直接静默覆盖当前文件！
  - `table_merge_cells` / `table_split_cell` 只设置无意义的 `merged`/`split` 标记；`table_insert_*` / `table_delete_*` / `table_distribute_*` / `apply_table_border` 改写 `shape.tbl` 后均未重绘场景。
  - `open_action_settings_dialog`（L1527）访问不存在的 `item.shape` 而非 `item.model`，确认后配置未保存。
  - 仅弹状态栏提示的纯空桩：`toggle_format_painter`、`open_hyperlink_dialog`、`expand_all_outline`、`toggle_show_formatting`、`run_spelling`、`show_help`（覆盖了基类帮助弹窗）、`table_select`、`table_borders_and_shading`、`toggle_picture_transparent`、`format_object_dialog`、`open_wordart_format`、`edit_speaker_notes`、`open_transition_pane`、`_on_play_slide_animation`、5 个母版工具栏按钮（L1592-1605）、`move_para_up`/`move_para_down`。

---

## 四、 问题 2：打印预览（Print Preview）效果不理想的根本原因

对比 `.vibeoffice` 原生内置打印预览视图（Quire [panes.js:L630-L690](file:///Users/brainzhang/work/aitobox/ATBOffice/.vibeoffice/public/quire/js/panes.js#L630-L690)、Ledger [print.js:L179-L404](file:///Users/brainzhang/work/aitobox/ATBOffice/.vibeoffice/public/ledger/js/print.js#L179-L404)、Lectern [panes.js:L405-L470](file:///Users/brainzhang/work/aitobox/ATBOffice/.vibeoffice/public/lectern/js/panes.js#L405-L470)）与当前实现（[base_window.py:L671-L700](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/base_window.py#L671-L700)、[quire_window.py:L1430-L1449](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py#L1430-L1449)、[ledger_window.py:L2362-L2550](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L2362-L2550)、[lectern_window.py:L2414-L2555](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_window.py#L2414-L2555)），效果差的核心技术原因如下：

1. **交互壳层缺失且重复弹窗触发崩溃**
   - `BaseOfficeWindow.print_preview` 仅弹出通用 `QPrintPreviewDialog(printer, self)`，完全缺失 `.vibeoffice` 的 Office 2003 窗口内预览体验（放大镜切换、单页/多页网格 `1x1..2x3`、缩放至一页、边距虚线拖动、Excel“页面设置”联动、“打印内容：幻灯片/讲义 1-9 张/备注页/大纲”切换、颜色/灰度/纯黑白切换、幻灯片加框开关）。
   - 受 `MacMenuBar` 双重连接影响，点击预览会连续构造两个模态 `QPrintPreviewDialog`，并在实测中直接导致 C++ `Segmentation fault`（[crash.log:L1054-L1063](file:///Users/brainzhang/.atboffice/logs/crash.log#L1054-L1063)）。
2. **`QPrinter` 硬件可打印边距双倍叠加与纸张尺寸/方向未同步**
   - **全代码库实测验证**：除邮件合并外，Quire/Ledger/Lectern 三大 `render_to_printer` **从未调用 `printer.setFullPage(True)`、`printer.setPageSize(...)` 或 `printer.setPageOrientation(...)`**。
   - **视觉后果**: `QPrinter` 默认存在硬件不可打印边距（Painter 原点非纸张左上角），而文档布局（尤其是 Quire 与 Ledger 的 `margin_left`/`margin_top`）本身已包含完整页边距坐标。叠加后造成**全页向右下偏移、右侧与底部内容被硬件矩形硬生生裁切**；横向文档/演示文稿也被强行塞入纵向纸张导致严重缩放或溢出。
3. **Quire 维护了“第二套缩水版”打印绘制器 (`render_page_to_painter`)**
   - [canvas_view.py:L1855-L2178](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/writer/views/canvas_view.py#L1855-L2178) 单独重写了一套 `render_page_to_painter`，与屏幕主渲染 `_paint_page_content` 严重分叉，导致打印预览丢失大量文档样式：
     - **表格边框写死**: 第 1899–1900 行直接 `painter.setPen(QPen(QColor(120, 120, 120), 0.75)); painter.drawRect(cell_rect)`，完全忽略 `w:tcBorders` / `w:tblBorders` 的无边框、粗细、虚线与颜色。
     - **项目符号与自动编号全丢**: 从未绘制段落前的 `p.label`（编号/圆点列表在预览中全部空白）。
     - **文本与段落样式残缺**: 未处理两端对齐间距拉伸（`extra_space_per_blank`）、表格内与页眉页脚内的居中/右对齐、文字突出显示背景（`highlight`）、段落边框与底纹、页边框、水印，以及内联图表/自选图形。
4. **Ledger 简化循环完全忽略页面设置与浮动对象**
   - [ledger_window.py:L2362-L2550](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L2362-L2550) 使用写死的 `margin_left=36pt`、`margin_top=45pt` 和 `"第 X 页，共 Y 页"`，**完全忽略 `PageSetupDialog` 的页面设置**（纸张方向、缩放比例、适应 N×M 页、打印区域、打印标题行/列、行列标题显示、网格线开关、黑白打印、先列后行顺序、自定义页眉页脚代码 `&L&C&R&P&N`）。
   - **严重缺漏**: 遍历单元格时忽略了**合并单元格（`sheet.merges`）**、**条件格式（色阶/数据条/图标集）**、自动换行与文本旋转，且**完全没有绘制工作表上的任何图表、图片和自选图形（`sheet.drawings`）**。
5. **Lectern 写死 960×540 纵向画布且忽略灰度与多种打印版式**
   - [lectern_window.py:L2414-L2555](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_window.py#L2414-L2555) 在标准模式下强制按纵向纸张居中绘制写死的 `960.0 × 540.0` 比例，4:3、A4 或 B4 演示文稿边缘被裁切；声明了 `grayscale` 参数却在函数体内完全未使用；讲义模式写死 3 张/页；缺失备注页、大纲视图、1/2/4/6/9 张讲义、隐藏幻灯片过滤及母版背景继承。

---

## 五、 问题 3：打开文件操作一段时间后必定 Crash 崩溃

通过解析用户本机 [crash.log](file:///Users/brainzhang/.atboffice/logs/crash.log)（含 `2026-11-21` 实测崩溃）并审计生命周期与事件链，确认了 **7 个导致长时间操作必现崩溃或异常退出的直接根因**：

### 5.1 实测崩溃日志证据汇总（[crash.log](file:///Users/brainzhang/.atboffice/logs/crash.log)）

- **7 次 C++ 级 `Fatal Python error: Segmentation fault`**:
  1. `GridViewport.mouseMoveEvent`（`grid_viewport.py:2086`）— 拖拽/悬停期间段错误（[crash.log:L1-L9](file:///Users/brainzhang/.atboffice/logs/crash.log#L1-L9)）。
  2. `BaseOfficeWindow.print_preview`（`base_window.py:689`）由 `MacMenuBar._bind_window_slots.<lambda>`（`mac_menu.py:457`）触发重入弹窗段错误（[crash.log:L1054-L1063](file:///Users/brainzhang/.atboffice/logs/crash.log#L1054-L1063)）。
  3. **5 次**发生在 Qt 主事件循环 `app.exec()`（`__main__.py:372`）内的延迟对象销毁 / 悬空 C++ 指针段错误（[L57-64](file:///Users/brainzhang/.atboffice/logs/crash.log#L57-L64), [L87-94](file:///Users/brainzhang/.atboffice/logs/crash.log#L87-L94), [L96-103](file:///Users/brainzhang/.atboffice/logs/crash.log#L96-L103), [L1036-1043](file:///Users/brainzhang/.atboffice/logs/crash.log#L1036-L1043), [L1045-1052](file:///Users/brainzhang/.atboffice/logs/crash.log#L1045-L1052)），紧随多次关闭窗口操作之后。
- **45+ 次未捕获 Python 异常（`2026-11-21 09:39` 实测高频触发）**:
  - **40+ 次**: `SpreadsheetObjectLayer.keyPressEvent` 抛出 `AttributeError: type object 'PySide6.QtGui.QKeyEvent' has no attribute 'StandardKey'`（[crash.log:L1848-L1852](file:///Users/brainzhang/.atboffice/logs/crash.log#L1848-L1852)）。
  - **5 次**: `LedgerWindow.apply_format_painter_to_range` 抛出 `AttributeError: 'NoneType' object has no attribute 'bold'`（[crash.log:L1097-L1102](file:///Users/brainzhang/.atboffice/logs/crash.log#L1097-L1102)）。

### 5.2 各模块与公共层崩溃根因精确定位

1. **[全局 P0] `BaseOfficeWindow.closeEvent` 内强排事件循环与过早 GC 导致 C++ Use-After-Free**
   - **定位**: [base_window.py:L824-L831](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/base_window.py#L824-L831) & [window_manager.py:L190-L209](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/window_manager.py#L190-L209)。
   - **机制**: 顶层窗口的唯一长生命周期 Python 引用保存在 `WindowManager._active_windows` 中。`closeEvent` 先触发 `self.window_closed.emit(self)` 将自身从 `_active_windows` 移除（释放最后引用），紧接着**在 C++ `QWidgetPrivate::close_helper` 栈帧尚未退出时**调用 `drain_event_loop(2)`（内部执行 `app.processEvents()` 和 `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)`）。这会在窗口关闭过程中同步重入事件循环并销毁挂起的 C++ `QWidget`/`QMenu`/Mac 原生窗口对象，直接引发 `app.exec()` 中的段错误。
2. **[全局 P0] `MacMenuBar` 双重/三重连接引发重入模态对话框 Segfault**
   - **定位**: [mac_menu.py:L453-L531](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py#L453-L531) & [action_registry.py:L95-L97](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/core/action_registry.py#L95-L97)。
   - **机制**: macOS 原生菜单回调栈中同时弹出两层/三层模态对话框（如 `QPrintPreviewDialog`、`QPrintDialog`、选项窗），关闭或销毁其中一个时另一个处于同一原生回调栈的半初始化状态，触发 Qt macOS Cocoa 桥接层 `SIGSEGV`。
3. **[Excel P0] `SpreadsheetObjectLayer` 拦截网格点击焦点并在每次按键崩溃**
   - **定位**: [object_layer.py:L391-L393, L874-L888](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/views/object_layer.py#L874-L888) & [view.py:L104-L106](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/view.py#L104-L106)。
   - **机制**: 覆盖整个视口的 `SpreadsheetObjectLayer` 设置了 `StrongFocus`，点击空白单元格时虽在 `mousePressEvent` 中 `ignore()`，但 Qt 已先将键盘焦点切换给 `object_layer`。用户随后按任意方向键、字母键或复制粘贴键即进入 `object_layer.keyPressEvent`，其第 879/883 行误写了 PySide6 中不存在的 `QKeyEvent.StandardKey.Copy` / `Paste`（正确应为 `QKeySequence.StandardKey`），导致每次键盘操作均抛未捕获异常。
4. **[Excel P0] 13 处格式化与格式刷未判空 `get_cell(r, c)` 导致 `NoneType` 崩溃**
   - **定位**: [sheet_model.py:L701-L702](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/models/sheet_model.py#L701-L702)；[ledger_window.py:L774-L971, L1357-L1372, L2610-L2650](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L774-L971)；[main_window.py:L441-L497](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/main_window.py#L441-L497)。
   - **机制**: 稀疏网格模型中空白单元格的 `model.get_cell(r, c)` 返回 `None`。只要选区包含空白格，点击字体、字号、加粗、斜体、下划线、对齐、缩进、合并居中、数字格式、小数位、字体颜色、填充颜色或格式刷（`crash.log` 实测 5 次）都会立刻抛出 `AttributeError`。
5. **[Excel P1] 打开工作簿或切换工作表后 `LedgerWindow` 选区信号断链**
   - **定位**: [ledger_window.py:L106-L107](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L106-L107) & [view.py:L166, L193-L196, L265-L269](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/view.py#L265-L269)。
   - **机制**: 窗口初始化时仅连接了最初空白表的 `SelectionModel`。加载 `.xlsx` 或切换 Sheet 时会新建 `SelectionModel`，原信号监听完全失效，状态栏与工具栏不再同步当前单元格状态，极端情况下对旧选区回调造成状态错乱。
6. **[PPT P0] `SlideScene.clear()` 与在位文本编辑器 `focusOutEvent` 生命周期撕裂**
   - **定位**: [slide_canvas.py:L553-L556, L1051-L1060](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/presentation/views/slide_canvas.py#L553-L556)；[shape_item.py:L1196-L1220](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/presentation/views/shape_item.py#L1196-L1220)；[text_editor.py:L1471-L1483](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/presentation/views/text_editor.py#L1471-L1483)。
   - **机制**: 在 `ShapeTextEditorItem` 编辑文本时点击工具栏下拉框或按钮，由于 `focusOutEvent` 未豁免工具栏焦点切换，编辑器立即自毁提交；而在 `SlideScene.mousePressEvent` 中直接调用 `it.finish_text_editing()`（跳过了 `commit_text_to_shape()`，同时移除带焦点的 `QGraphicsTextItem`）；在 `SlideCanvasView.keyPressEvent`（Delete/Group/Ungroup）及 `OutlineEditorWidget._on_cursor_changed` 中同步调用 `scene.load_slide()` -> `self.clear()`，在 Qt 事件分发栈上直接销毁全部 `QGraphicsItem` 极易触发 C++ 场景树悬空指针。此外，每次场景变更都同步重绘所有缩略图并重建大纲 `QTextDocument`，长时间编辑会导致内存与主线程卡顿叠加。
7. **[Word P0/P1] 每次排版格式变更即调用 `set_document` 清空撤销栈与缓存，每敲一键全量重排**
   - **定位**: [canvas_view.py:L217-L229, L2466, L2817-L2820](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/writer/views/canvas_view.py#L2817-L2820)。
   - **机制**: 35+ 个格式化方法和表格拖拽释放都会调用 `_on_formatting_applied()` -> `self.set_document(self.doc)`，**每次操作都直接清空 `_undo_stack`、`_redo_stack`、`_pixmap_cache` 并重置光标到文首**！同时每次按键都执行全文档 `deepcopy` 备份、`reindex`、全文档分页并触发 `review_pane.refresh_items()` 与缩略图同步全量重绘，长文档编辑极易内存飙升和界面假死。

---

## 六、 问题 4：`.vibeoffice` 主干功能对比与其余不完善之处

对照 `.vibeoffice/docs/{suite,quire,ledger,lectern,LOSSLESS_SAVE,smartart}.md` 与源码，整理出尚未落地或仅停留在“界面外壳”的主干功能清单：

### 6.1 公共套件基础设施
- **[MISSING] Paper 2016 Ribbon 界面模式**: `ThemeDialog` 中虽有 `"Paper 2016 Ribbon"` 卡片，但 [luna_2003.py](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/styles/luna_2003.py) 将其映射到与 `"paper"` 完全相同的经典工具栏样式，全套件尚无标签页 Ribbon、上下文工具选项卡、快速访问工具栏及 `Alt` KeyTips。
- **[MISSING] 上下文任务窗格自动跟随 (`RB.follow`)**: 选中图片/表格/图表/艺术字时右侧窗格不会自动切换为对应工具面板（仅 Lectern 手动切换了 SmartArt 面板）。
- **[BROKEN] 自动恢复服务从未启动 & 缺失启动中心文档恢复面板**: [base_window.py:L55](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/base_window.py#L55) 创建了 `RecoveryService`，但全代码库**从未调用 `self.recovery_service.start()`**，定时草稿保存根本没有运行，启动中心也无崩溃草稿恢复面板。
- **[MISSING] 启动中心缩略图与缺失模板**: 最近文件仅显示 emoji 图标（缺首屏缩略图渲染）；[start_center.py:L538-L587](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/start_center.py#L538-L587) 仅硬编码展示 4 个模板，遗漏了 `TemplateRegistry` 中已存在的另外 14 个模板；卡片预览均为静态 emoji。
- **[BROKEN] 剪贴画（Clipart）与艺术字（WordArt）通用插入断链**: [clipart_dialog.py:L600-L632](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/common/clipart_dialog.py#L600-L632) 与 [wordart_gallery.py:L725-L784](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/modules/common/wordart_gallery.py#L725-L784) 检查的窗口方法（如 `add_shape`、`insert_image`、`insert_drawing_object`）在三窗口均不存在，导致从通用面板插入在三模块全部静默失败。
- **[BROKEN] 多重剪贴板不支持图片粘贴 & Quire 仅复制纯文本**: [clipboard_pane.py:L347-L362](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/panes/clipboard_pane.py#L347-L362) 未将图片字节写回系统剪贴板；Quire 复制仅写入纯文本，丢失富文本与图片；Edit 菜单和工具栏缺少多重剪贴板入口。
- **[DATA LOSS] 加密文档保存丢失密码 & 多格式导出生成 0 字节空文件**: `try_decrypt_if_encrypted` 打开解密后丢弃了密码，保存时覆写为明文；`QuireWindow.do_save`（[L722](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/quire_window.py#L722)）、`LedgerWindow.do_save`（[L455](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/ledger_window.py#L455)）、`LecternWindow.do_save`（[L2183](file:///Users/brainzhang/work/aitobox/ATBOffice/src/atboffice/ui/shell/lectern_window.py#L2183)）对 `.rtf`、`.md`、`.zip`、`.txt`、`.html`、`.png` 均落入 `path.touch(exist_ok=True)`，生成 0 字节空文件！
- **[PARTIAL] 无损兼容性检查器与 Scout 助手**: Ledger/Lectern 保存时不展示 `losses` 兼容性检查弹窗；`ScoutWidget` 常驻 40ms 定时器（违背 `.vibeoffice` 静止 0% CPU 原则），缺失 67 个分层 SVG 动画、命令联动反应与气泡内操作按钮；命令搜索框缺少空聚焦最近命令列表、菜单路径面包屑与容错模糊匹配。

### 6.2 Quire（Word）主干遗漏
- **视图模式未真正分化**: `Normal`、`Web`、`Reading` 视图在 `WriterCanvasView.paintEvent` 中全部沿用固定页宽的打印版式分页框（未实现 Web 流式重排、Reading 双页适应窗口、Normal 折叠页边距与虚线分页符）。
- **缺失画布内核心交互**: 无法双击/进入画布内直接编辑页眉和页脚；浮动图片/自选图形无法在画布上选中、拖动、缩放、旋转；缺失**绘制表格（画笔）**与**擦除器**交互；水平标尺缺少表格列分隔滑块与多栏栏距滑块。
- **修订（Track Changes）正文绘制缺失**: 虽有右侧批注/修订气球，但正文中的插入下划线、删除线作者色标及左侧修订竖线未绘制，且“最终状态/原始状态”视图切换无法在正文中隐藏删除/插入内容。
- **同义词库与信息检索**: 缺失基于 WordNet `en.thes` 的信息检索任务窗格，且 Ledger/Lectern 无拼写检查。

### 6.3 Ledger（Excel）主干遗漏
- **公式与动态数组**: 注册约 220 个函数（`.vibeoffice` 为 519 个）；`SEQUENCE`/`FILTER`/`SORT`/`UNIQUE` 返回的 `Arr` 对象在 `dag.py` 中未实现网格自动溢出（`#SPILL!` 碰撞检查与蓝框）；`Table1[Col]` 结构化引用与 `@` 隐式交集在 `evaluator.py` 中求值报错 `#VALUE!`；不支持 `Ctrl+Shift+Enter` 数组公式。
- **高级分析与视图**: 缺失 **数据透视图（PivotChart）**、**拆分窗口（Window Split）**、**行列大纲分组折叠槽（`1,2,3` 级别与 `+/-` 按钮）**、**规划求解（Solver）**；分页预览中的蓝色分页虚线仅静态显示，无法鼠标拖拽调整分页符；`ConditionalFormatDialog` 只能新建两种基础规则和改背景色，无法创建色阶/数据条/图标集；`TextToColumnsWizardDialog` 固定宽度模式未实现。

### 6.4 Lectern（PowerPoint）主干遗漏
- **双右侧任务窗格冲突与母版视图跳错**: 窗口右侧同时存在内置 `LecternTaskPane` 与外部 `QDockWidget` 两套重复面板；`set_view_mode("master")` 错误切换到 `center_normal_widget` 而非 `self.master_view`；缺失讲义母版（Handout Master）与备注母版（Notes Master）。
- **大纲编辑丢失正文数据**: `OutlineEditorWidget._on_text_changed` 仅解析 `[N]` 标题行，用户在“大纲”标签页输入/修改的所有项目符号正文全部被静默丢弃。
- **动画与切换预览断链**: `AnimationPane.playRequested` 与 `SlideTransitionPane.previewRequested` 均未连接到画布预览；12 种遮罩擦除类动画（`wipe`/`blinds`/`wheel`/`split` 等）设置 `reveal_type` 后被渲染器完全忽略；画布缺少动作路径矢量虚线编辑。
- **幻灯片表格/媒体/排练功能缺失**: 双击幻灯片表格编辑的是外层矩形文本而非点击的单元格；导入的音视频点击播放仅画一个写死在 `35% ("00:15")` 的假进度条（无 `QMediaPlayer` 播放）；`rehearse` 排练计时无计时 HUD 也未保存每页停留时间；`create_summary_slide` 仅插入空白页。

---

## 七、 分阶段优先级整改路线图（Remediation Action Plan）

建议严格按 **P0（止血崩溃与数据安全） → P1（打印预览与核心按钮接线） → P2（渲染对齐与主干补全）** 三阶段推进修复，每个子项建议补齐独立回归测试：

### Phase A — P0 阻断项：消除 Crash 与数据丢失（最高优先级）
1. **统一信号调度并消除 `MacMenuBar` 重复连接与别名断链**:
   - 删除 `MacMenuBar._bind_window_slots` 中的 `connect_if` 重复绑定，统一由 `ActionRegistry` 注册与分发；修复 `_reg_act` 将别名同步映射到 `_specs`，并清理 `insert_*` 重复菜单项和跨模块错配项。
2. **修复 `BaseOfficeWindow.closeEvent` 析构重入**:
   - 移除 `closeEvent` 内的 `drain_event_loop(2)` 同步强排与 `processEvents()`，确保清理定时器/信号后由主事件循环安全回收。
3. **修复 Ledger 焦点抢占与空单元格 `NoneType` 崩溃**:
   - 修正 `SpreadsheetObjectLayer.keyPressEvent` 的 `QKeySequence.StandardKey` 并将非对象按键转发至 `grid`；取消空白区点击对焦点的抢占。
   - 全面替换 `LedgerWindow` 与 `MainWindow` 中 18 处直接访问 `model.get_cell(r, c)` 的格式化方法与格式刷，改用安全取/建单元辅助方法。
   - 修复 `SpreadsheetView` 切换工作表或重绑工作簿后 `LedgerWindow._update_spreadsheet_status` 信号断链。
4. **修复 Quire 撤销栈清零与 Lectern 编辑器生命周期撕裂**:
   - 将 `WriterCanvasView._on_formatting_applied` 与表格拖拽释放从 `self.set_document(self.doc)` 改为局部增量重排与刷新，恢复完整撤销/重做栈与光标位置。
   - 统一 `SlideScene` 在 `mousePressEvent` / `keyPressEvent` 中先通过 `commit_and_finish()` 提交编辑器，豁免工具栏焦点切换触发的误提交。
5. **修复“另存为”覆写、0 字节文件导出、加密丢密码与大纲数据丢失**:
   - 修正 `LecternWindow.save_as_dialog` 调用 `save_file_as()`；接入 `RtfWriter`/`MarkdownWriter`/HTML/PNG 导出并禁止未知格式 `path.touch` 假成功；保留加密源密码；修复 Lectern 大纲正文双向同步；启用 `RecoveryService.start()`。

### Phase B — P1 核心体验：重构打印预览与打通断开的 UI 按钮/弹窗
1. **重构统一高质量打印与内置预览引擎**:
   - 根据文档/纸张物理尺寸与方向显式配置 `QPrinter`（`setPageSize`、`setPageOrientation`、`setFullPage(True)`），消除偏移裁切。
   - 废弃 Quire 缩水版 `render_page_to_painter`，使屏幕绘制与矢量打印共享统一路径（保留编号、高亮、表格边框、水印）。
   - 让 Ledger `render_to_printer` 完整读取 `PageSetupDialog`（缩放、适应页数、打印区域、重复标题、自定义页眉页脚 `&L&C&R`）并渲染合并单元格、条件格式及 `sheet.drawings` 图表图片。
   - 为 Lectern `render_to_printer` 补全讲义（1/2/3/4/6/9 张）、备注页、大纲、灰度/纯黑白及幻灯片加框选项，提供仿 `.vibeoffice` 的窗口内预览工具栏。
2. **打通 180+ 失效按钮与 29 个 Quire 空壳弹窗**:
   - 统一 `MacMenuBar` 与三模块 `toolbars.py` 的 Action ID（消除蛇形/驼峰分歧）。
   - 为 Quire 29 个弹窗补齐 `Accepted` 后的模型写回逻辑；修复 Quire 页眉页脚/图片/审阅工具栏、Highlight 颜色与 `"none"` 字符串 bug、Undo/Redo 动态下拉历史菜单。
   - 修复 Ledger `insert_picture`、`ChartWizardDialog` 真实数据源绑定、`AdvancedFilter`/`Subtotal`/`Consolidate`/`DataTable` 与真实拼写检查。
   - 修复 Lectern `insert_chart`、`insert_picture_from_file`、`save_as_dialog`、表单元格双击编辑、形状对齐 ID 碰撞及通用 Clipart/WordArt 插入路由。

### Phase C — P2 视觉保真度与主干补齐
1. **消除 `atb-office-diff` 渲染系统性偏移**:
   - 对齐 `WriterCanvasView.page_rect_canvas` 顶部空白（`cur_y`）与 `.vibeoffice` 基准，对齐 `GridViewport.row_header_width` 宽度；在 `ChartPainter` 中补充 3D 柱状/条形/折线/饼图透视渲染，目标推动 73 份文档平均前景相似度跨过 `>= 90%` 门禁。
2. **补全 `.vibeoffice` 主干差异能力**:
   - 实现 Paper 2016 Ribbon 模式与上下文任务窗格自动跟随、Start Center 实景缩略图与全量 22 模板展示、Quire 正文修订标记绘制与浮动图形画布拖拽、Ledger 动态数组溢出/`Table1[Col]`/大纲分组/可拖拽分页虚线、Lectern 动画与切换预览连线及音视频媒体播放。

---

## 八、 第十一期验收签核（Phase 11 Sign-off，#448，2026-11-22 实测，基线提交 `b205424`）

| 门禁 | 结果 | 结论 |
|---|---|---|
| `pytest tests/` 全量回归 | GUI 与非 GUI 两部分全部通过（已知 `test_phase9_six_docx_render_and_visual_parity` 除外，主干既有失败） | ✅ |
| 长程操作压力测试 `tests/gui/test_phase11_acceptance.py` | 3 轮 × 每应用 2 份真实语料：打开、编辑、格式刷（含空单元格）、复制/粘贴、切换视图/工作表/幻灯片、撤销/重做、打印预览、保存、重新打开、关闭；0 崩溃、0 未处理异常，`crash.log` 为空 | ✅ |
| 语料审计 `run_corpus_audit.py --strict` | 154 份：77 有效 OOXML、23 旧版导入、1 加密、3 损坏、50 不支持格式；**0 崩溃 / 0 超时 / 0 失败 / 0 数据丢失** | ✅ |
| 视觉 Diff `run_office_diff.py --all --capture --strict` | 73/73 可比，前景加权平均相似度 **93.79%**（基线 65.31%），**0 个 CRITICAL_MISMATCH**；29 PARITY_MATCH、41 COSMETIC_MINOR、3 LAYOUT_DRIFT | ✅ 平均值与零严重门禁达标 |
| 源码级控件审计 `source_diff.py --check` | 0 ORPHAN_NO_SIGNAL、0 STUB_IMPLEMENTATION | ✅ |
| ActionRegistry 运行时探针 | 三个应用所有可见菜单/工具栏命令均有处理器或明确的禁用原因，无"正在联调中"兜底提示；已启用菜单项均恰好触发一次命令（无重复触发） | ✅ |

### 8.1 验收中修复的问题
- 别名 ID 下注册的独立 QAction（如 Quire 的 `docMap`、`viewReading`）点击后只显示"正在联调中"，现改为执行规范命令。
- Quire「视图 ▸ 页眉和页脚」此前无处理器，现切换到页面视图并进入页眉编辑。

### 8.2 遗留项（非阻断）
- 3 份 LAYOUT_DRIFT（单份前景相似度低于 85%）：`libreoffice__totalsRowFunction.xlsx`（76.8%）、`openxml-sdk__00d63cdd-….xlsx`（81.9%）、`openxml-sdk__sldsz-Slide Size-type-b4iso.pptx`（83.0%）。前两者源于缺失字体（如 Century Gothic）回退后列宽不同，后者为 B4 幻灯片尺寸的缩放差异；内容与格式（含 `[$£-809]` 货币格式、表格样式）渲染正确。因此 `--strict` 的单份 85% 阈值尚未全部满足。
