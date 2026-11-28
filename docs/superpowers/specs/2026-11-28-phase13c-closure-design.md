# ATBOffice 第十三期 C 阶段（Phase 13C）全套件收口设计规格

> **基线**：`phase13b/ledger-solver`（完成 Phase 13A 与 Phase 13B）  
> **状态**：实施与验收中（Track 1 / Track 2 / Track 3 并行交付）  
> **范围**：补齐 Solver 灵敏度/极限值报告及 `.xlsx` 隐藏定义名称往返、Quire 浮动对象工具栏/格式对话框及撤销/DOCX 往返、以及跨应用共享信息检索/同义词库任务窗格（Ledger 与 Lectern）。

---

## 一、总体目标与三大并行轨道

Phase 13C 围绕三项独立且互补的功能收口，使 ATBOffice 在电子表格规划求解持久化、文字处理图文对象排版与全套件离线信息检索方面达到 Office 2003 完整体验：

1. **Track 1 — Ledger 规划求解高级报告与 XLSX 模型持久化（`@solver-xlsx`）**：
   - 新增灵敏度报告（`generate_sensitivity_report`）与极限值报告（`generate_limits_report`），并在 `SolverResultsDialog` 支持任意组合生成运算结果/灵敏度/极限值三类报告；
   - 实现符合 Excel 标准的隐藏工作表作用域定义名称（`solver_*`）序列化与反序列化，并在 `xlsx_reader.py` / `xlsx_writer.py` 中基于 `lxml` 原地保留机制完成 `.xlsx` 无损往返。
2. **Track 2 — Quire 浮动对象命令与设置对象格式对话框（`@quire-objects`）**：
   - 实现文字环绕（`wrap_inline` / `wrap_square` / `wrap_tight` / `wrap_behind` / `wrap_front`）、图片调整（旋转、重置、亮度/对比度、颜色模式）及自选图形样式（线宽、虚线、箭头、阴影）的可撤销命令；
   - 新增 Luna 2003 风格 `FormatObjectDialog`（`设置对象格式`），将已实现命令从 `OBJECT_COMMANDS` 禁用白名单移除，并与画布浮动对象选中态实时联动。
3. **Track 3 — 全套件共享信息检索与同义词库任务窗格（`@suite-research`）**：
   - 将原 Quire 专属信息检索能力抽象为可参数化公共组件 `SuiteResearchPane`（`atboffice/modules/common/research_pane.py`），依托 `ThesaurusEngine` 与 `ResearchHostAdapter` 回调契约复用至 Ledger 与 Lectern；
   - 统一 `MacMenuBar` 跨应用菜单门控（`信息检索(&R)...`、`同义词库(&T)...` / `Shift+F7`）与 Paper 2016 Ribbon「审阅 -> 校对」面板。

---

## 二、Track 1：Ledger Solver 高级报告与 XLSX 模型持久化

### 2.1 灵敏度报告与极限值报告（`src/atboffice/modules/spreadsheet/calc/solver.py`）
- **`generate_sensitivity_report(workbook, params, result) -> str`**：
  - 创建唯一命名工作表 `Sensitivity Report N`（本地化表头与列标题经 `safe_tr()`）。
  - **可变单元格区**：输出单元格引用、名称/公式、终值、递减成本（`Reduced Cost`）、目标系数（`Objective Coefficient`）及可行增减量（`Allowable Increase` / `Allowable Decrease`）。Simplex LP 求解时提取单纯形表灵敏度范围；GRG 非线性 / 演化求解时通过有限差分梯度近似并优雅降级不可用字段（`不适用`）。
  - **约束区**：输出约束终值、公式/运算符、阴影价格（`Shadow Price`）、约束右侧值（`Constraint R.H. Side`）及允许增量/减量。
- **`generate_limits_report(workbook, params, result) -> str`**：
  - 创建唯一命名工作表 `Limits Report N`。
  - 固定其余决策变量于当前最优解，针对每个决策变量沿可行域边界分别探测下限（`Lower Limit`）与上限（`Upper Limit`）及其对应目标值（`Objective Result`）。

### 2.2 Excel 隐藏定义名称契约与 `.xlsx` 无损往返
- **定义名称编码（`solver_params_to_defined_names` / `solver_params_from_defined_names`）**：
  - 导出/解析标准 Excel 隐藏表级定义名称（`localSheetId=sheet_idx`、`hidden="1"`）：
    - `solver_opt`、`solver_typ`、`solver_val`、`solver_adj`、`solver_num`；
    - `solver_lhsN`、`solver_relN`（`1=<=`, `2==`, `3=>=`, `4=int`, `5=bin`, `6=dif`）、`solver_rhsN`；
    - `solver_neg`、`solver_eng`、`solver_itr`、`solver_tim`、`solver_pre`、`solver_tol`、`solver_pop`、`solver_sed`。
  - 保持 `save_solver_model` / `load_solver_model`（`sheet.extra["solver_model"]`）向后兼容。
- **XLSX 读写（`xlsx_reader.py`、`xlsx_writer.py`）**：
  - 读取时使用 `lxml.etree` 解析 `<definedNames>` 中的表级 `solver_*` 条目恢复至 `sheet.extra["solver_model"]`，同时将所有非 Solver 用户定义名称原样保留在 `wb.extra["defined_names"]`。
  - 写入时使用 `lxml` 原地编辑 `<definedNames>`（含 `wb.extra["defined_names"]` 初始为空的场景），仅替换已写入工作表的 `solver_*` 条目，绝不丢弃用户自定义名称或未建模部件。

### 2.3 多报告结果对话框（`src/atboffice/modules/spreadsheet/dialogs/solver_dialog.py`）
- `SolverResultsDialog` 支持任意组合勾选 `生成运算结果报告(&A)`、`生成灵敏度报告(&S)` 与 `生成极限值报告(&L)`。
- 保留 `self.report_checkbox` 与 `dlg.created_report_sheet` 向后兼容，新增 `dlg.created_report_sheets: list[str]` 记录所有已创建报告表名；全面支持 `safe_tr()`、`retranslate_ui()`、`theme_tokens()` 与 `ui_font()`。

---

## 三、Track 2：Quire 浮动对象命令与格式设置对话框

### 3.1 撤销可逆的对象操作（`src/atboffice/modules/writer/views/canvas_object_commands.py`）
所有操作通过 `canvas.selected_float()` 获取当前选中的浮动图片、自选图形或文本框，并经 `canvas.run_undoable(..., label=safe_tr(...))` 执行单步可撤销变更；未选中对象时安全返回 `False` 并展示简短本地化提示：
- **文字环绕模式**：`wrap_inline`、`wrap_square`、`wrap_tight`、`wrap_behind`、`wrap_front`，同步更新内联/浮动状态、`FloatProperties` 环绕类型及 `behindDoc`。
- **图片工具命令**：`picRotate`（+90° 模 360°）、`picReset`（重置旋转/亮度/对比度/色彩模式/裁剪）、`picMoreBright` / `picLessBright`、`picMoreContrast` / `picLessContrast`、`pic_color_auto` / `pic_color_gray` / `pic_color_bw` / `pic_color_wash`。
- **图形描边/阴影命令**：`draw_weight_075`、`draw_dash_dash`、`draw_arrow_1`、`draw_shadow_1`。
- **`formatObject`**：打开 `FormatObjectDialog` 并将尺寸、旋转角度、环绕模式、线条颜色/粗细、填充颜色与阴影配置一次性提交为可撤销历史步骤，所有属性同步经 `DocxWriter` / `DocxReader` 无损往返。

### 3.2 `FormatObjectDialog`（`src/atboffice/modules/writer/dialogs/format_object_dialog.py`）
- 提供尺寸（宽/高 pt）、旋转角度（deg）、文字环绕下拉框、线条颜色与粗细、填充颜色与阴影复选框。
- 严格遵循 `theme_tokens()`、`ui_font()`、`safe_tr()`、`retranslate_ui()`，不含 `PYTEST_CURRENT_TEST`。

### 3.3 命令接线与选中态同步（`quire_commands.py`、`quire_window.py`）
- 将上述 20 个已实现命令 ID 从 `OBJECT_COMMANDS` 白名单移除，保留尚未实现的占位命令（如 `sendMail`、`permission`、`insertClipArt`）。
- 绑定全部命令处理器，并在画布浮动对象选区变化时同步更新对应 `QAction.setEnabled(has_float)` 状态。

---

## 四、Track 3：全套件共享信息检索与同义词库任务窗格

### 4.1 公共适配器组件：`SuiteResearchPane`（`src/atboffice/modules/common/research_pane.py`）
- **核心抽象**：
  - `ResearchSearchHit(label: str, navigate: Callable[[], None], tooltip: str = "")`
  - `ResearchHostAdapter(get_selection_text, insert_text, search_items, scope_label, scope_heading, no_matches_label)`
- **`SuiteResearchPane(QWidget)` 契约**：
  - 支持美式英语同义词库（`thesaurus`）、英式英语同义词库（`thesaurusUK`）、当前宿主范围检索（`document`，文本随宿主本地化为「搜索此工作簿」/「搜索此演示文稿」）以及全部参考书籍（`all`）。
  - 复用 `ThesaurusEngine`（`en.thes`）实现精确/词干检索、邻近词推荐、反义词分组、历史栈 `◄ 返回`、`插入` / `复制` / `查阅` 单击菜单及双击连续查阅。
  - 全组件使用 `theme_tokens()`、`ui_font()`、`safe_tr()` 与 `retranslate_ui()`，无硬编码颜色与字体。

### 4.2 Ledger 集成（`ledger_auditing.py`、`ledger_window.py`、`ledger_ribbon.py`）
- 在 `_setup_ledger_task_panes()` 注册 `"research"` 任务窗格（`SuiteResearchPane`），绑定 `"research"` 与 `"thesaurus"`（`Shift+F7`）至 `LedgerWindow.open_research(service=None)`。
- **取词与插入**：优先读取活动内联编辑器选区/文本，否则读取活动单元格文本；插入同义词通过 `LedgerWindow.run_cell_edit()` 写入工作表并记录至 `LedgerWindow.undo_service()`（`grid.history`），同步刷新公式栏、重算依赖公式并更新状态栏。
- **工作簿跨表检索**：遍历工作簿全部工作表非空单元格（值与公式，最多 50 条），点击命中项自动切换目标工作表并选中对应单元格。

### 4.3 Lectern 集成（`lectern_window.py`、`lectern_commands.py`、`lectern_ribbon.py`）
- 在 `_setup_lectern_task_panes()` 注册 `"research"` 任务窗格（`SuiteResearchPane`），绑定 `"research"` / `"tools_research"` / `"thesaurus"`（`Shift+F7`）至 `LecternWindow.open_research(service=None)`。
- **取词与插入**：优先读取在位 `ShapeTextEditorItem` 选区或光标单词，否则提取当前选中文本框的首个词条；插入时在在位编辑器替换选区/当前词，或在选中形状 / 当前幻灯片首个文本形状中保留首段 Run 格式替换目标词或文本，随后刷新画布并通过 `PresentationHistory.note_edit()` + `flush()` 记录单步可撤销历史。
- **演示文稿检索**：复用 `iter_paragraphs(pres, include_notes=True)` 遍历全部幻灯片形状、表格单元格与演讲者备注，点击命中项通过 `LecternCommands._focus_text()` 跳转目标幻灯片并选中对应对象。

### 4.4 跨应用菜单与 Ribbon 同步（`mac_menu.py`、`ledger_ribbon.py`、`lectern_ribbon.py`）
- `MacMenuBar` 在「工具」菜单注册 `"research"`（别名 `"tools_research"`，`信息检索(&R)...`）与 `"thesaurus"`（`同义词库(&T)...`，`Shift+F7`），`_APP_SPECIFIC_ACTIONS` 将二者均对 `{"quire", "ledger", "lectern"}` 可见而对通用窗口/启动中心隐藏。
- `ledger_ribbon.py` 与 `lectern_ribbon.py` 在「审阅 -> 校对」分组暴露 `"research"` 与 `"thesaurus"`，并映射有效 Luna 图标 `"research"` / `"thesaurus"`，保障 `test_ribbon_spec_parity.py` 与 `test_toolbars_icons.py` 全通过。
- `zh-CN_to_en.json` 以 0 空格缩进 JSON 格式合入全三轨新增中英文词条，确保 `test_i18n.py` 占位符与目录校验通过。

---

## 五、全量验收门禁

1. **静态与一致性检查**：
   - `conda run -n ATBOffice ruff check .`
   - `conda run -n ATBOffice ruff format --check .`
   - `/opt/anaconda3/bin/mypy --python-executable /opt/anaconda3/envs/ATBOffice/bin/python src/atboffice/core`
   - `conda run -n ATBOffice python scripts/source_diff.py --check`（输出 `CLEAN`）
   - `conda run -n ATBOffice python scripts/audit_toolbars_parity.py`
2. **自动化测试**：
   - Track 1：`test_solver_engine.py`、`test_phase13c_solver_reports_and_xlsx.py`、`test_phase13b_solver_ui.py`、`test_xlsx_reader.py`、`test_xlsx_writer.py`
   - Track 2：`test_phase13c_quire_object_commands.py`、`test_phase11_quire_ui_wiring.py`、`test_writer_canvas.py`
   - Track 3 & 套件回归：`test_phase13c_suite_research_panes.py`、`test_phase13_quire_research_and_table_tools.py`、`test_i18n.py`、`test_ribbon_spec_parity.py`、`test_toolbars_icons.py`、`test_phase11_ledger_ui_wiring.py`、`test_phase11_lectern_ui_wiring.py`、`test_mac_menu.py`
