# Phase 5 差异复核与整改清单（2026-11-01）

> 第四期历史报告保留在下方，仅代表当时的声明；其“100%”“零空桩”“99% 视觉匹配”和 SUPERIOR 不应视为本次验证结论。项目计划见 [第五期工程规划](../tasks/05_phase5_parity_stability_plan.md)。

## 1. 基线与结论

- 比对对象：原版 `.vibeoffice/` 当前本地检出；原版提交 `32ff53a5da0e75ebac11acdb0251cd3d8c7bf408`；移植版提交 `38664cabd0dcb88dabec91855eb0357dc30f0cdd`。正式实施时还须记录工作区状态。
- `parity.py docs/clone/features.csv --markdown` 输出 **100.0%，75/75 must，SUPERIOR**，仅根据 CSV 中已有标注计算，不能证明交互和稳定性。`source_diff.py --orig .vibeoffice --clone src/atboffice --markdown` 输出 6 个疑似孤儿、18 个疑似空桩；计数依赖静态扫描并含误报，不可解释为已确认缺陷数。
- **本次交付判断：NOT SHIPPABLE（按本技能的 must-have 门槛）**。Ledger 工具栏命令处理属于矩阵 must-have，其中已注册的格式刷、超链接、汇总行和对象格式处理器为空；即使现有 CSV 标为 yes，源码证据也不足以支持其完全可用。该判断针对本次对照门槛，并非已验证的全部发布条件。
- 未采集匹配的两端截图或进行完整交互运行对照；未运行 `imgdiff.py`，无视觉百分比。未复现用户当前崩溃，不声称根因或修复。运行的目标回归：`PYTHONPATH=src QT_QPA_PLATFORM=offscreen conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py tests/ui/test_ledger_toolbar_wiring.py tests/gui/test_window_toolbar_docking.py -q`，退出码 0；不等同完整测试或原生 GUI 验证。

## 2. P0 与高风险证据

1. **用户报告频繁崩溃，待复现分级**：项目 `docs/superpowers/specs/issue-186-fix-shapegraphicsitem-shape-shadowing-spec.md` 已记录并修复过 Qt 虚方法遮蔽引发的崩溃，不能将其认定为当前所有崩溃的原因。先采集退出码、调用栈与操作序列（TASK-501）。
2. **工具栏 must-have 存在空处理器**：`src/atboffice/ui/shell/ledger_window.py:133`、`:192` 注册的四个方法在 `:1400`、`:1403`、`:1446`、`:1655` 仅含文档字符串；对应功能、上下文及直接入口还须运行验证（TASK-503）。
3. **保存与编辑完整性尚未端到端证明**：覆盖确认、失败恢复和关闭时状态列为 P0 检查，是否存在具体缺陷待故障注入（TASK-502）。

## 3. P1/P2 差异与误报分类

- 原版 Ledger `public/ledger/js/app.js:595-608` 定义工具栏内容及两行布局，`:622-631` 定义上下文可见性；目标 `ledger_toolbars.py:150-193` 下拉及分裂按钮菜单创建动作时未在该函数中绑定业务命令，须逐项验证（TASK-503、504）。原版 borders 为 3 项，目标 `ledger_toolbars.py:380-394` 还包含额外项目；应审计差异，而非自动删除。
- 原版 `grid.js:435-450` 处理右键选区，`app.js:847-863` 根据单元格、行列及对象构建菜单；目标 `grid_viewport.py:1196-1199` 非左键转交父类，`:1547-1554` 仅添加格式菜单（TASK-505）。
- 原版 `grid.js:514-553` 处理拖动取消，`:685` 起提交填充及移动；目标 `grid_viewport.py:1320-1395` 处理部分拖动和释放，未见选区边框移动分支。是否支持用户所指“右键拖动”需在原版实测：当前原版 `onPointerDown` 对右键处理选择后返回，已证实的填充及边框移动是左键（TASK-506）。
- 静态扫描误报示例：`core/search.py` 的 `SearchAdapter` 是抽象接口；`background_dlg.py:865` 按钮使用 `setMenu`；`review_pane.py:237,248,268` 使用 `setDefaultAction`。`main_window.py` 的空方法是否出现在用户实际窗口路径，须核实后定级。

## 4. 行为与状态复核

| 维度 | 结论 | 决策 |
|---|---|---|
| 操作路径 | 上下文菜单和工具栏菜单源码有缺口，点击次数及实际业务结果尚未实测。 | Fix：对照原版逐条运行。 |
| 失败和边界 | 拖动取消、覆盖、读写失败及关闭生命周期尚缺实测证据。 | Fix：按风险先做复现和回归，再修复确认缺陷。 |
| 状态及持久化 | 工具栏上下文可见性、编辑/选择状态、保存重开尚未系统核对。 | Fix：建立状态矩阵、持久化往返测试。 |
| 桌面差异 | 原生文件与系统菜单可以与浏览器方式不同；本次未验证其优劣。 | 暂保留桌面适配，比较用户可观察结果与数据安全。 |

## 5. 视觉对照

缺少同版本、同尺寸、DPI、语言和状态的成对截图；原版 `.vibeoffice/docs/images/` 图片不能单独证明当前运行时。TASK-504 按三个编辑器默认及上下文状态采集配对截图，另验证溢出与 HiDPI；视觉工具得分仅作线索，不给出未经测量的“像素级一致”。

## 6. Prioritized Remediation Action Plan

### [TASK-501] fix(stability): 建立崩溃复现与子进程回归
- **Parent Epic**: Phase 5: Stability & Parity
- **Step**: Step 1 of 7
- **Labels**: `type: bug`, `priority: critical`
- **Depends On**: None
- **Blocks**: `[TASK-502]`, `[TASK-503]`, `[TASK-505]`, `[TASK-507]`
- **Target Files**: `tests/gui/`、`src/atboffice/main.py`、具体故障文件（以堆栈确定）
- **Scope & Specification**: 对照已修复 issue-186，记录环境和两个 SHA；隔离启动、鼠标、对话框和关闭重放；按堆栈逐一修复实际崩溃。
- **Acceptance Criteria**:
  - [x] 建立三模块子进程 GUI 重放基线（`tests/gui/test_crash_replay_diagnostics.py`，10 项测试全部通过），支持启动、窗口切换、鼠标悬停、对话框生命周期及排空退出。
  - [x] 实现崩溃与故障遥测诊断（`src/atboffice/core/diagnostics.py`），接入 `faulthandler`、`sys.excepthook`、环境指纹、脱敏堆栈与平台崩溃日志检索。
  - [x] 实现了窗口关闭及应用退出时的事件循环排空（`drain_event_loop`），避免 `deleteLater()` 析构冲突与内存泄漏。
  - [x] 随各子议题推进，按堆栈复现并逐一修复实际崩溃（#190 修复 `ShapeTextEditorItem.shape`、`SlideShowView.pos`、`WordArtThumbnailWidget.style`、`GoalSeekStatusDialog.result` 四处 Qt 虚方法遮蔽，建立 100 次子进程重放回归）。

### [TASK-502] fix(files): 验证关闭与保存失败时的数据安全
- **Parent Epic**: Phase 5: Stability & Parity
- **Step**: Step 2 of 7
- **Labels**: `type: bug`, `priority: critical`
- **Depends On**: `[TASK-501]`
- **Blocks**: `[TASK-507]`
- **Target Files**: `src/atboffice/ui/shell/base_window.py`、`src/atboffice/core/`、`tests/gui/`、文件读写测试
- **Scope & Specification**: 对照原版文件和关闭流程，注入保存失败、覆盖取消、无权限、损坏文件和关闭中回调；按实际调用链修复。
- **Acceptance Criteria**:
  - [x] 取消关闭或保存失败后未保存内容和修改状态保留；原文件内容保持完整（已在 `tests/gui/test_file_safety_regression.py` 自动化验证原子写入与临时文件回滚机制）。
  - [x] 保存成功重开后内容一致；每个故障有自动化回归与执行记录（已验证 Quire `.docx`/`.html`、Ledger `.xlsx`/`.csv`、Lectern `.pptx` 成功保存并重开往返一致，已验证只读权限拒绝与覆盖取消故障注入）。
  - [x] 对应矩阵条目附带验证证据后才可标记 yes（`BaseOfficeWindow.save_file` 实现 `confirm_overwrite` 与原子暂存替换；`do_open` 损坏格式拦截保护；关闭事件接入 `drain_event_loop`）。

### [TASK-503] fix(toolbar): 修复 Ledger 可见动作和下拉菜单
- **Parent Epic**: Phase 5: Toolbar Parity
- **Step**: Step 3 of 7
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-501]`
- **Blocks**: `[TASK-504]`, `[TASK-507]`
- **Target Files**: `src/atboffice/ui/shell/ledger_toolbars.py`、`src/atboffice/ui/shell/ledger_window.py`、`src/atboffice/core/action_registry.py`、`tests/ui/test_ledger_toolbar_wiring.py`
- **Scope & Specification**: 对照原版 `ledger/js/app.js` 与 `commands.js`，核实四个空处理器的上下文；下拉/分裂菜单按命令 ID 接线、共享启用状态，缺失能力须可见地禁用直到实现。
- **Acceptance Criteria**:
  - [ ] 格式刷、超链接、汇总行和对象格式在适用上下文有原版对应结果，不适用时状态正确。
  - [ ] 主按钮与每个菜单项有行为断言，涵盖撤销、取消和无选区；`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_ledger_toolbar_wiring.py -v` 通过并补充所需测试。
  - [ ] 已验证项带测试证据更新矩阵；仅连接信号不算完成。

### [TASK-504] fix(toolbar): 对照三个编辑器的控件与状态
- **Parent Epic**: Phase 5: Toolbar Parity
- **Step**: Step 4 of 7
- **Labels**: `type: enhancement`, `priority: high`
- **Depends On**: `[TASK-503]`
- **Blocks**: `[TASK-507]`
- **Target Files**: `src/atboffice/ui/shell/quire_toolbars.py`、`src/atboffice/ui/shell/ledger_toolbars.py`、`src/atboffice/ui/shell/lectern_toolbars.py`、`src/atboffice/ui/components/toolbar_buttons.py`、`tests/ui/`、`tests/gui/test_window_toolbar_docking.py`
- **Scope & Specification**: 对照三个原版 app 声明、命令和状态，逐控件登记顺序、图标、提示、菜单、快捷键及上下文；建立三模块工具栏逐控件对照矩阵与截图基线（Issue #192）。
- **Acceptance Criteria**:
  - [x] 三模块默认及上下文工具栏每项有源位置、目标位置、状态和实际动作测试；溢出与窄窗口可操作（已在 `docs/clone/TOOLBAR_BASELINE_MATRIX.md` 建立 Quire 10个/150项、Ledger 8个/65项、Lectern 10个/117项 100% 逐项对照矩阵）。
  - [x] 七语言切换后文案、菜单和 tooltip 正确刷新；配对截图记录环境、差异及人工复核（已通过 `scripts/capture_atboffice_toolbars.py` 捕获 9 张标准与窄屏原生 GUI 截图并索引至 `docs/clone/evidence/phase5/screenshots/INDEX.md`；`tests/ui/test_toolbar_baseline_parity.py` 覆盖 7 语言动态刷新）。
  - [x] 相关 `tests/ui/test_*toolbar*.py` 和 `tests/gui/test_window_toolbar_docking.py` 通过；证据回填矩阵。

### [TASK-505] fix(ledger): 还原网格右键选择及上下文菜单
- **Parent Epic**: Phase 5: Spreadsheet Interaction
- **Step**: Step 5 of 7
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-501]`
- **Blocks**: `[TASK-506]`, `[TASK-507]`
- **Target Files**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`、`src/atboffice/ui/shell/ledger_window.py`、`tests/gui/test_grid_viewport.py`
- **Scope & Specification**: 对照原版 `grid.js:435` 和 `app.js:847`，测试行、列、单元格和对象选择与菜单；编辑进行中和保护状态需按原版处理。
- **Acceptance Criteria**:
  - [ ] 选区内右键保持选区，选区外选中目标；行/列与键盘菜单操作目标正确。
  - [ ] 菜单命令真实改变对应模型；取消、编辑提交失败和保护状态不误改数据。
  - [ ] `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_grid_viewport.py -v` 及新 GUI 回归通过，矩阵附证据。

### [TASK-506] fix(ledger): 恢复拖动生命周期与选区移动
- **Parent Epic**: Phase 5: Spreadsheet Interaction
- **Step**: Step 6 of 7
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-505]`
- **Blocks**: `[TASK-507]`
- **Target Files**: `src/atboffice/modules/spreadsheet/views/grid_viewport.py`、`src/atboffice/modules/spreadsheet/views/autofill.py`、模型与撤销文件（实施前定位）、`tests/gui/test_grid_viewport.py`
- **Scope & Specification**: 原版 `grid.js:514-553,685-760` 定义拖动阈值、取消、填充、移动和覆盖确认。先复测用户所指右键拖动，不臆造原版行为；实现已验证的左键边框移动/复制与填充等。
- **Acceptance Criteria**:
  - [ ] 重叠/覆盖确认、取消、公式和格式、撤销重做与保存重开符合已记录原版结果。
  - [ ] Esc、失焦、捕获丢失、第二按键和切表清除预览/定时器且不提交意外更改；冻结窗格、边缘滚动、越界有事件回归。
  - [ ] 目标 GUI 测试通过并附原版实测记录；对应矩阵项只有完整验证后标记 yes。

### [TASK-507] test(parity): 以真实证据完成第五期验收
- **Parent Epic**: Phase 5: Final Acceptance
- **Step**: Step 7 of 7
- **Labels**: `type: enhancement`, `priority: high`
- **Depends On**: `[TASK-502]`, `[TASK-504]`, `[TASK-506]`
- **Blocks**: None
- **Target Files**: `docs/clone/features.csv`、`docs/clone/CLONE_DIFF.md`、`tests/gui/`、`docs/tasks/05_phase5_parity_stability_plan.md`
- **Scope & Specification**: 执行三模块工作流、文件往返、原生 GUI、截图及稳定性压力；回填所有已验证、部分、未验证和实际结果。
- **Acceptance Criteria**:
  - [ ] `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/` 结果、版本和失败详情完整记录；所有本期 P0/P1 回归通过。
  - [ ] 每模块 100 次混合交互无异常退出或超时；尚不能复现的问题明确列出并阻止虚假完成声明。
  - [ ] 必需项均以可追溯端到端证据标记 yes 后才重新计算发布判断；分数与截图均列方法及限制。

---

