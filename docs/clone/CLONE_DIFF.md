# Phase 7 差异复核与整改任务（2026-11-03）

- **Original Project**：`.vibeoffice/`，提交 `32ff53a5da0e75ebac11acdb0251cd3d8c7bf408`。
- **Clone Project**：`src/atboffice/`，提交 `f423efd2609eefcfb5cb32d5d32f4eaef472a5ee`。
- **Status**：规划已完成，修复未实施；执行 `atb-clone-diff`，结论 **NOT SHIPPABLE**。
- 项目级范围、里程碑、估算和门禁见 [第七期计划](../tasks/07_phase7_fidelity_stability_compatibility_plan.md)。
- [第六期及更早报告快照](archive/CLONE_DIFF_PHASE6_2026-11-02.md) 保留原文；其中 SUPERIOR、零空桩、全量匹配属于历史声明，不是本次结论。
- [本次可追踪审计摘要](PHASE7_AUDIT_SUMMARY.json) 保存环境、扫描候选、截图统计、语料损失候选及探针结果。

## 1. Executive Parity Scorecard

| 指标 | 本次结果 | 解释 |
|---|---|---|
| 历史 features.csv 加权分 | 100%，126 项，must 86/86 | 实际执行 skill parity.py 的输出；来自历史人工 yes，不代表运行时完整性 |
| 本期功能完成率 | 未建立可信分母，不给百分比 | TASK-701 建立独立细粒度矩阵；未知不能当 yes |
| 第六期图像报告 | 平均 80.97%，75/412 达到 85% 阈值 | 报告自身与“全面一致”结论矛盾 |
| 本次历史 Ledger 配对 layout diff | 33.4/100，different | 使用 skill 的 Sobel 结构工具；两图语言、内容、视图状态不一致，只证明该配对无效，不是全产品评分 |
| 定向 pytest | 57 passed，12.54 秒 | 未执行全量测试；不能推导整体稳定 |
| 150 文件现有批处理 | 139 ok / 11 excluded | 其中 66 个 ok 仅是旧格式文件头检查，73 个是 OOXML 读写；无显示断言 |
| 发布判断 | **NOT SHIPPABLE** | 假成功加载、空内容和保存丢失为已确认阻断项 |

### 1.1 三层源码映射

| 原版 | PySide6 对应 | 审计重点 |
|---|---|---|
| `public/common/ui.js`、`common/icons.js`、各 app.js 工具栏配置 | `ui/components/toolbar*.py`、`ui/shell/*_toolbars.py`、`core/action_registry.py` | 控件 ID → 主按钮/箭头/菜单 → 动作结果与状态 |
| `ledger/js/grid.js`、`clipboard.js`、`ops.js`、`app.js:847` | `modules/spreadsheet/views/grid_viewport.py`、`autofill.py`、models | 事件命中 → 编辑提交/保护 → 事务 → 重算/撤销 |
| `quire/js/docx-read.js`、`layout.js`、`render.js`、`preserve.js` | `modules/writer/io/`、`layout/`、`views/canvas_view.py` | 内容解析、排版、渲染及未知节点保留 |
| `ledger/js/xlsx-read.js`、`xlsx-write.js`、`render.js`、`preserve.js` | `modules/spreadsheet/io/`、`views/`、`vfs/opc.py` | 来源包、工作表和对象同步、格式与保存 |
| `lectern/js/pptx-read.js`、`render.js`、`preserve.js` | `modules/presentation/io/`、`views/` | 母版继承、文本、对象及包保留 |

本次 scanner 扫描 `.vibeoffice/public` 与 `src/atboffice`：126 原版组件、549 Python 类、262 原版控件、1197 Python 控件，17 个疑似孤儿、15 个疑似空方法。数量差不能证明一一覆盖；scanner 的 control_gap=0 不是映射完成。

分类例子：`BackgroundDialog.btn_fill_picker`、SlideShowHud 菜单按钮、ReviewToolbar 的 defaultAction 按钮需按 setMenu/setDefaultAction 排除误报；SearchAdapter 五个方法为抽象合同。`MainWindow` 的九个空方法需核查启动可达性。`OutlineToolbar._on_outline_level_changed()` 的 pass、ChartWizardDialog 的添加/删除系列、ScenarioManagerDialog 合并、LedgerOptionsDialog 自定义列表、HyperlinkDialog 屏幕提示均应核查完整业务链。候选不直接等于已证实缺陷。

## 2. P0 Blockers

| ID | 证据与影响 | 证据级别 | 任务 |
|---|---|---|---|
| F01 | 三窗口 `do_open` 未匹配扩展名仍返回 True；`BaseOfficeWindow.open_file:170` 更新路径、清 dirty。`.doc/.xls/.ppt` 出现在文件筛选器但未实现读取 | 源码确认＋无绑定方法探针；尚未完成带 dirty 的原生 GUI 复现 | 702 |
| F02 | `docx_reader.py:509` 只查 Transitional body。`libreoffice__strict.docx` 含 7 个文本节点，读取后仅空段落、0 文本 run，返回成功 | 实测解析；短程 GUI 可显示空窗口且退出 0 | 705 |
| F03 | `read_xlsx` → `write_xlsx(wb)` 默认往返使 XLSM 的 `xl/vbaProject.bin` 消失；writer 有显式 source_opc 参数，但默认链未保留该部件 | 实测 ZIP 部件缺失；必须补 GUI 保存回归 | 706 |
| F04 | 填充释放分支缺少保护拦截；保护模型直接释放探针从 A1=7 写成 A1:A3=[7,7,7] | 处理器级实测，非完整鼠标路径 | 710 |
| F05 | 用户报告持续崩溃；已有短测没有复现 | 用户报告，原因未知；不能推断均为 Qt 虚方法遮蔽 | 703 |
| F06 | 捕获失败/未匹配回退主窗口；文件损失仍 ok、异常自动 excluded；超时写在 as_completed 后的 future.result，不能中止未完成文件 | 源码确认，验收可信性阻断 | 701、704 |

原版对旧格式有明确拒绝/转换提示：Lectern `app.js:407` 拒绝二进制 PPT，Ledger `app.js:183` 检查可选 XLS reader，否则提示转 XLSX，Quire `app.js` 捕获 `ole` 错误。第七期首先恢复这种准确反馈，不承诺原版也未提供的二进制编辑。

## 3. P1/P2 Gaps

1. **右键菜单语义**：`grid_viewport.py:3171` 的选择性粘贴等价普通粘贴；原版 `app.js:847` 中的表格 List/Create List 条件分支没有在当前单元格菜单中还原。行列复制按整个选择逐格遍历（`copy:3052`），整列大范围存在 UI 阻塞风险，尚未计时实测。
2. **拖动填充**：引擎和拖动处理器已存在；用户实际使用不可用，优先验证完整 LedgerWindow/覆盖层/焦点/坐标，而不是重写算法。原版 `grid.js:435` 右键只调整选区后返回；填充为左键，用户已确认这一范围。原版使用 Ctrl 或 Meta，本地释放填充只显式检查 Control，需要补 macOS Cmd 对照。
3. **工具栏细节**：历史 Ledger 全工具栏截图的箭头区域有黑色竖块、工具栏分行及文本宽度不同；目标同时处于空白分页预览，原版为含数据普通视图，不能把所有差异归因字体。`OfficeSplitButton.paintEvent` 在原生绘制后再画箭头/分隔线，是排查重复绘制的候选，尚非确定根因。
4. **文档显示与往返**：现有 75 个 OOXML 中 73 个返回 ok，但 Word 15 个、Excel 15 个有特性计数减少候选；PPTX 25 个无计数减少也不能证明视觉一致。命名范围、图表、批注、修订、图片等必须增加语义断言。完整清单见 JSON 摘要。
5. **i18n**：`test_i18n_phase6.py` 检查注册语言、非空 JSON 和 Cancel 翻译，不能证明所有文案正确、动态刷新完整或没有中英混杂。

## 4. Behavioral & UX Divergences

| 维度 | 决策 | 依据与验收方向 |
|---|---|---|
| 流程与点击路径 | Fix | 选择性粘贴必须呈现原版选项并改变相应属性；工具栏主区域/箭头分别触发正确行为 |
| 错误与边界 | Fix | 无效文件不能假成功；保护、取消、全列/大范围不得破坏数据或阻塞界面 |
| 状态与持久化 | Fix | 旧文档、撤销栈、dirty、选区、工作表、后台任务在失败/切换/关闭时一致；保存重开验证 |
| 视觉与响应 | Fix | 按控件和上下文逐项配对；原生截图、DPR、语言、字体与文档内容有记录 |
| macOS 原生菜单/文件对话框 | Keep Modernized | 保留原生适配，以结果、快捷键和可访问性为准；截图差异单列 |
| 原版不支持的旧格式 | Keep Modernized | 本期先明确拒绝并给本地化转换建议；以后可单独评估转换服务，不假装已支持 |

## 5. Visual Layout Discrepancies

| 模块 | 第六期 PNG 数 | 唯一 SHA-256 数 | 最大完全重复组 |
|---|---:|---:|---:|
| Start Center | 10 | 10 | 1 |
| Quire | 175 | 18 | 65 |
| Ledger | 131 | 10 | 84 |
| Lectern | 96 | 14 | 32 |

重复图本身不必然错误，但结合未匹配分支直接 win.grab、菜单/窗格未触发和异常 fallback，可确认不能以文件数量证明 412 状态覆盖。原版本身也有少量重复图，仍需核对 records 的状态断言。

本次实际查看 Ledger `038_toolbar_All_Visible__Full_Toolbars_Dock.png` 两版图片，并执行 skill imgdiff。原版 2880×1800，目标 1440×900；缩放后虽同纵横比，却语言/数据/视图不同，因此不纳入真实视觉验收。全图缩至 320×200 的平均像素距离并非 SSIM，易掩盖小按钮缺陷；须按工具栏/菜单/对话框 ROI、几何与真实状态分开检查。

## 6. Prioritized Remediation Action Plan

以下任务均未开始，TASK 编号保留为规划标识；现已登记至 [Epic #234](https://github.com/aitobox/ATBOffice/issues/234) 及子任务 #235–#247，2026-11-04 已回读核验，见 [任务映射](PHASE7_GITHUB_ISSUES.md)。新增测试文件在目标中以“新增”标识。所有任务共用步骤：先写能失败的回归并确认原因，再实现最小修复、运行指定测试、更新矩阵与证据后独立提交。各卡验收第 1 项就是该任务要先固化的失败场景；不得用断言控件存在替代结果断言。

### [TASK-701] test(evidence): 重建可信截图与功能验收基线

- **Parent Epic**: Phase 7: 可信基线
- **Step**: Step 1 of 13
- **Labels**: `type: enhancement`, `priority: high`
- **Depends On**: None
- **Blocks**: `[TASK-702]`, `[TASK-703]`, `[TASK-704]`, `[TASK-709]`, `[TASK-711]`
- **Target Files**:
  - `scripts/capture_atboffice_screens.py`
  - `scripts/imgdiff.py`
  - `scripts/phase7_capture_scenarios.py（新增）`
  - `docs/clone/phase7_control_matrix.csv（新增）`
  - `docs/clone/phase7_features.csv（新增）`
  - `tests/test_phase7_capture_contract.py（新增）`
- **Scope & Specification**: 对照 records.json、common/ui.js 和三模块 app.js。替换含混文件名分派；每场景准备独立文档、语言、主题和视图，验证实际 popup/dialog/tab/pane 后抓图。失败输出 failed，不 fallback；检测重复截图并核查状态。保留原报告，矩阵区分已验证/部分/缺失/未验证。
- **Acceptance Criteria**:
- [ ] 未注册场景、异常构造器、错误标签页、PNG 保存失败均使该场景及整次验收失败；菜单场景必须证明菜单可见。
- [ ] 412 条记录有映射、状态合同和处置；同内容状态才允许配对。几何/ROI 与全图分数分别保存，不宣称 MAE 为 SSIM。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_capture_contract.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-702] fix(files): 修复假成功并事务化文件打开

- **Parent Epic**: Phase 7: P0 数据安全
- **Step**: Step 2 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-701]`
- **Blocks**: `[TASK-705]`, `[TASK-706]`, `[TASK-708]`
- **Target Files**:
  - `src/atboffice/ui/shell/base_window.py`
  - `src/atboffice/ui/shell/quire_window.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/lectern_window.py`
  - `src/atboffice/modules/spreadsheet/view.py`
  - `tests/gui/test_phase7_open_contract.py（新增）`
- **Scope & Specification**: 对照原版三 app.js 的 openFile/readDocx/read 流程。收敛打开筛选器、启动中心、Finder/drop 和实际解析能力；恢复已存在的 RTF/Markdown 等入口前先验证 reader。未知格式、伪装、OLE/加密分开报告；解析到候选模型并完成验证后才提交，绑定失败回滚。
- **Acceptance Criteria**:
- [ ] 有效但不支持的 DOC/XLS/PPT、损坏 ZIP、取消密码、绑定异常均返回失败/取消且保留旧内容、路径、dirty、撤销与最近文件。
- [ ] 每个承诺支持的扩展名至少一个真实成功样本；从 open_file 而非仅 do_open 验证标题/模型/显示一致；读写失败仍通过既有 file safety 回归。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_open_contract.py tests/gui/test_file_safety_regression.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-703] fix(stability): 基于操作序列治理崩溃与对象生命周期

- **Parent Epic**: Phase 7: P0 稳定性
- **Step**: Step 3 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-701]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/__main__.py`
  - `src/atboffice/core/diagnostics.py`
  - `src/atboffice/core/window_manager.py`
  - `src/atboffice/modules/spreadsheet/view.py`
  - `tests/gui/test_phase7_native_replay.py（新增）`
  - `tests/gui/test_crash_replay_diagnostics.py`
- **Scope & Specification**: 以原版 common/ui.js 拖动和 app.js 文档关闭行为为参考。复用已有 diagnostics，不把强制 processEvents 排空当作通用修复；审计 QObject/scene/item 所有权、deleteLater、模态重入、定时器、旧模型信号和后台任务。普通启动也应能本地记录异常；测试中 Qt slot 异常即失败，脱敏记录文档 SHA 和命令序列。
- **Acceptance Criteria**:
- [ ] 编辑中打开另一文件、关闭窗口、切换视图、弹出/取消菜单和对话框各有可重放记录；出现异常后独立子进程保存退出码、堆栈、最后动作与环境。
- [ ] 每个复现崩溃都有最小回归；无堆栈的用户问题保留为未定位。完成每模块 100 轮混合操作及 30 分钟原生会话，检查旧信号/定时器和内存趋势。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_native_replay.py tests/gui/test_crash_replay_diagnostics.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-704] test(corpus): 建立逐文件内容与显示合同

- **Parent Epic**: Phase 7: P0 验收可信性
- **Step**: Step 4 of 13
- **Labels**: `type: enhancement`, `priority: high`
- **Depends On**: `[TASK-701]`
- **Blocks**: `[TASK-705]`, `[TASK-706]`, `[TASK-707]`, `[TASK-708]`
- **Target Files**:
  - `scripts/run_corpus_audit.py`
  - `src/atboffice/deep/audit/core.py`
  - `tests/docs/expectations.json（新增）`
  - `tests/unit/corpus/`
  - `tests/test_phase7_corpus_runner.py（新增）`
- **Scope & Specification**: 对照原版 tests/quire、ledger、lectern 的 loss-audit 和当前 corpus 设计。将150样本分类为有效/加密/损坏/格式未支持，记录来源许可/SHA/预期；逐阶段输出 parse/model/render/roundtrip。每文件独立进程30秒硬超时，可终止和回收进程；不能在 as_completed 后设置无效超时。
- **Acceptance Criteria**:
- [ ] 注入挂起、崩溃、普通解析异常和有损输出，均得到独立 timeout/crash/fail/loss；只有 manifest 预先声明的拒绝才可算预期结果，不能异常后自动 excluded。
- [ ] 150/150均记账；旧格式头检查不计兼容成功；有效支持文件逐个语义断言、原生显示检查和另存重开，退出码反映失败。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_corpus_runner.py tests/unit/corpus/ -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-705] fix(quire): 修复 Strict DOCX 空白及真实排版差异

- **Parent Epic**: Phase 7: 文档兼容
- **Step**: Step 5 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-702]`, `[TASK-704]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/modules/writer/io/docx_reader.py`
  - `src/atboffice/modules/writer/io/docx_writer.py`
  - `src/atboffice/modules/writer/layout/`
  - `src/atboffice/modules/writer/views/canvas_view.py`
  - `tests/gui/test_phase7_docx_render.py（新增）`
- **Scope & Specification**: 对照 quire/js/docx-read.js、portions.js、layout.js、render.js、preserve.js。先支持 Strict/Transitional 的元素、属性和关系解析；不能仅改根 namespace。然后按表格/分节页眉页脚/浮动图形/修订/字体失败簇修复，保留未知内容，不为清零指标删除特性。
- **Acceptance Criteria**:
- [ ] libreoffice__strict.docx 的7个源文本节点进入模型并绘制，图片/公式可见或明确标注受限；不再以默认空段落算成功。
- [ ] nested-runs、sdt-ignored-footer、headerPic、tdf125881 等样本分别验证文本框、页脚、页眉图片与修订；保存重开后文本/对象和未修改部件保持。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_docx_render.py tests/unit/corpus/test_word_corpus.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-706] fix(ledger-io): 修复 XLSX/XLSM 默认保存丢失

- **Parent Epic**: Phase 7: P0 数据安全
- **Step**: Step 6 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-702]`, `[TASK-704]`
- **Blocks**: `[TASK-707]`
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
  - `src/atboffice/modules/spreadsheet/io/xlsx_writer.py`
  - `src/atboffice/modules/spreadsheet/models/workbook_model.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/vfs/opc.py`
  - `tests/gui/test_phase7_xlsx_preserve.py（新增）`
- **Scope & Specification**: 对照 ledger/js/xlsx-read.js、xlsx-write.js、preserve.js。梳理 SourcePackage 从 reader 到 workbook 到 GUI writer 的传递；明确源格式与另存转换。修复覆盖关系、内容类型与未知部件；宏只保留不执行。计数差异需按具体部件确认，不能全部当作同一根因。
- **Acceptance Criteria**:
- [ ] macro-button-form-control.xlsm 不编辑及改单格两条 GUI 保存链均保留 vbaProject.bin 的 SHA、内容类型和关系，保存结果仍为合法 XLSM。
- [ ] SimpleWithComments、60509、enhanced-protection、tdf113621 等分别验证批注、图表、保护、custom XML；重开无修复警告，故障写入不损坏原件。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_preserve.py tests/unit/corpus/test_excel_corpus.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-707] fix(ledger-render): 修复真实工作簿载入后的显示与同步

- **Parent Epic**: Phase 7: 文档显示
- **Step**: Step 7 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-704]`, `[TASK-706]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/view.py`
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/object_layer.py`
  - `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`
  - `tests/gui/test_phase7_xlsx_render.py（新增）`
- **Scope & Specification**: 对照 ledger/js/render.js、layout.js、styles.js、objects.js。验证 workbook替换后 grid/editor/tabs/object_layer/geometry 引用同一活动表，解除旧信号。按数值格式、合并、隐藏、冻结、条件样式、图片图表逐类建立参考截图与模型断言。
- **Acceptance Criteria**:
- [x] cell-value、SimpleWithComments、GroupTest、conditional_fmt_origin、Pivot2_Row 等样本加载后非空内容/表签/列宽/对象与参考一致；透视表缓存展示与编辑能力分开记录。
- [x] 连续打开两个不同工作簿再切表、撤销、缩放不会显示旧数据；编辑公式后缓存值与重算结果有明确合同，未支持特性不得伪装为空白。
- [x] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_xlsx_render.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [x] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-708] fix(lectern): 按真实样本修复幻灯片显示及往返

- **Parent Epic**: Phase 7: 文档显示
- **Step**: Step 8 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-702]`, `[TASK-704]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/modules/presentation/io/pptx_reader.py`
  - `src/atboffice/modules/presentation/io/pptx_writer.py`
  - `src/atboffice/modules/presentation/view.py`
  - `src/atboffice/modules/presentation/views/`
  - `tests/gui/test_phase7_pptx_render.py（新增）`
- **Scope & Specification**: 对照 lectern/js/pptx-read.js、render.js、textedit.js、preserve.js。从母版/布局占位符继承、主题字体、组合变换、文本自适应、裁剪与图表逐簇比较。使用参考渲染核对位置/内容，不以形状数不减少代替正确显示。
- **Acceptance Criteria**:
- [ ] master-slides、TextFittingComparisonWithMSO_3、smartart-text、table-with-different-font-colors 等样本覆盖母版、文本、SmartArt及表格；正常视图/缩略图/放映内容一致。
- [ ] 普通对象编辑保存重开不丢失母版、媒体、动画及未知关系；不支持外部媒体时有可恢复提示，不等待网络导致挂起。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_pptx_render.py tests/unit/corpus/test_presentation_corpus.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-709] fix(ledger-menu): 补齐右键菜单的真实业务行为

- **Parent Epic**: Phase 7: Ledger 交互
- **Step**: Step 9 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-701]`
- **Blocks**: `[TASK-710]`
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py`
  - `src/atboffice/modules/spreadsheet/views/object_layer.py`
  - `src/atboffice/ui/shell/ledger_window.py`
  - `tests/gui/test_phase7_context_actions.py（新增）`
- **Scope & Specification**: 对照 app.js:847、commands.js、clipboard.js 及截图049–053。逐项登记单元格/行/列/表签/对象/状态栏菜单、enabled和目标选区；实现真正选择性粘贴及表格条件分支，操作共享事务/保护/撤销。整列复制使用稀疏边界和可取消大范围处理。
- **Acceptance Criteria**:
- [ ] 完整 LedgerWindow 中右键打开菜单并点击：选区内外、Shift+F10、编辑提交失败都作用于正确目标。选择性粘贴分别验证值/公式/格式/转置及取消；List/Create List有正确条件。
- [ ] 插入删除/清除/隐藏/批注/超链接/工作表移动复制/统计切换均验证模型、dirty、一次撤销与保存重开；保护与多选边界不误改，整列操作不枚举百万空单元格。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_context_actions.py tests/gui/test_ledger_context_menu.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-710] fix(ledger-fill): 恢复填充柄完整事件链与保护事务

- **Parent Epic**: Phase 7: Ledger 交互
- **Step**: Step 10 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-709]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/modules/spreadsheet/views/grid_viewport.py`
  - `src/atboffice/modules/spreadsheet/views/autofill.py`
  - `src/atboffice/modules/spreadsheet/views/editor_controller.py`
  - `src/atboffice/modules/spreadsheet/views/object_layer.py`
  - `tests/gui/test_phase7_fill_integration.py（新增）`
- **Scope & Specification**: 对照 grid.js:435–770、ops.js 和 issue-12/200。复用现有引擎，从完整窗口命中填充柄，验证覆盖层转发、坐标/缩放、鼠标捕获和焦点。先关闭保护绕过；以一次事务提交、一次undo恢复，并接通dirty/重算/状态。避免每次拖动复制整张表造成内存峰值。
- **Acceptance Criteria**:
- [ ] A1=1/A2=2真实拖到A10得到1..10；单值默认复制、Ctrl/Cmd变序列；公式相对/绝对引用、日期/文本、四向与原版一致。受保护目标不可改且无undo脏记录。
- [ ] Esc/失焦/切表/关闭/第二按键/丢失释放取消，预览和定时器清理；冻结/合并/隐藏/缩放/边缘滚动有事件测试；undo/redo/保存重开恢复正确，不能仅设置私有字段或直接调用引擎算验收。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_fill_integration.py tests/gui/test_autofill.py tests/gui/test_gestures_drag.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-711] fix(toolbar): 逐控件校准图标箭头状态与命中区域

- **Parent Epic**: Phase 7: 视觉对齐
- **Step**: Step 11 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-701]`
- **Blocks**: `[TASK-712]`
- **Target Files**:
  - `src/atboffice/ui/components/toolbar_buttons.py`
  - `src/atboffice/ui/components/toolbar.py`
  - `src/atboffice/ui/styles/luna_2003.py`
  - `src/atboffice/ui/shell/quire_toolbars.py`
  - `src/atboffice/ui/shell/ledger_toolbars.py`
  - `src/atboffice/ui/shell/lectern_toolbars.py`
  - `tests/ui/test_phase7_toolbar_geometry.py（新增）`
- **Scope & Specification**: 对照 common/ui.js、icons.js 和三 app.js 配置及 screenshots/*toolbar*。按ID匹配顺序、类型、图标、分隔、宽高、色条、箭头、hover/pressed/checked/disabled和上下文可见性。核查原生绘制与自绘叠加；同语言同DPR同数据先配对，再修复。
- **Acceptance Criteria**:
- [ ] 主按钮与箭头命中分离、各触发一次；颜色主按钮使用最近颜色；hover/pressed/disabled图无黑块、重影或裁切，动态enabled同步。
- [ ] 1440×900、DPR1/2及1024×768溢出场景均可操作；按钮几何偏差≤2逻辑像素或逐项记录原生豁免；九locale无截断，原生菜单适配单列。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/ui/test_phase7_toolbar_geometry.py tests/gui/test_window_toolbar_docking.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-712] fix(commands): 清理可见空行为并完善动态本地化

- **Parent Epic**: Phase 7: 命令完整性
- **Step**: Step 12 of 13
- **Labels**: `type: bug`, `priority: high`
- **Depends On**: `[TASK-711]`
- **Blocks**: `[TASK-713]`
- **Target Files**:
  - `src/atboffice/core/action_registry.py`
  - `src/atboffice/modules/writer/views/outline_view.py`
  - `src/atboffice/modules/spreadsheet/dialogs/chart_wizard.py`
  - `src/atboffice/modules/spreadsheet/dialogs/scenario_manager_dialog.py`
  - `src/atboffice/modules/spreadsheet/dialogs/options_dialog.py`
  - `src/atboffice/modules/writer/dialogs/reference_dialogs.py`
  - `src/atboffice/resources/locale/`
  - `tests/gui/test_phase7_visible_commands.py（新增）`
- **Scope & Specification**: 对照原版 dialogs/commands 与三层扫描逐项核实17/15候选，记录误报证据而不是删除抽象接口。修复可达的图表系列、自定义列表、方案合并、屏幕提示、大纲级别等；对话框确认要修改当前文档，取消不写入，切文档不引用旧模型。
- **Acceptance Criteria**:
- [ ] 每个可见候选有真实调用链及业务断言；死按钮修复或按已记录能力明确禁用解释，不能以统一占位提示代替P1实现。
- [ ] 九locale切换后菜单/tooltip/动态子菜单/对话框刷新正确，往返切换不重复connect；检查典型文案人工译文，abstract/setMenu/defaultAction误报有明确白名单依据。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_visible_commands.py tests/test_i18n_phase6.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

### [TASK-713] test(acceptance): 以真实用户路径完成第七期验收

- **Parent Epic**: Phase 7: 最终验收
- **Step**: Step 13 of 13
- **Labels**: `type: enhancement`, `priority: high`
- **Depends On**: `[TASK-703]`, `[TASK-705]`, `[TASK-707]`, `[TASK-708]`, `[TASK-710]`, `[TASK-712]`
- **Blocks**: None
- **Target Files**:
  - `tests/gui/test_phase7_acceptance.py（新增）`
  - `docs/clone/phase7_features.csv（新增）`
  - `docs/clone/CLONE_DIFF.md`
  - `docs/tasks/07_phase7_fidelity_stability_compatibility_plan.md`
- **Scope & Specification**: 按主计划全部门禁整合。三编辑器从打开真实语料到编辑、菜单/工具栏、撤销重做、另存重开、取消/关闭重放；保留文件SHA、环境、原生截图、堆栈和命令日志。新证据只能对应本次SHA，不自动继承旧yes。
- **Acceptance Criteria**:
- [ ] 全量pytest记录实际通过/失败/skip/xfail；150文件分层、412状态处置、九locale、原生窗口/Retina以及每模块100轮和30分钟会话全部完成；存在缺口列明任务，不标SHIPPABLE。
- [ ] P0/P1全部关闭，所有本期must=有证据的yes；原始数据、审计摘要与报告相互一致，已知不支持格式透明记录；发布结论不由平均分单独产生。
- [ ] 定向命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/gui/test_phase7_acceptance.py -ra`；退出码0，无未处理Qt异常。原生与offscreen分别注明，不相互替代。
- [ ] 对应 `phase7_features.csv` 条目附测试/截图/版本证据后才改为 `clone: yes`；更新状态与影响范围。

## 7. 本次执行记录与复验方法

Skill 使用本机源码：`/Users/brainzhang/work/aitobox/ATBPromptsHub/agents/skills/atb-clone-diff/SKILL.md`。原始审计阶段只运行审计和只读诊断；后续依用户明确请求，使用 `atb-github-issue-creator` 发布 Epic 与 13 个子任务，尚未启动实施。

```bash
python3 /Users/brainzhang/work/aitobox/ATBPromptsHub/agents/skills/atb-clone-diff/scripts/parity.py docs/clone/features.csv --markdown
python3 /Users/brainzhang/work/aitobox/ATBPromptsHub/agents/skills/atb-clone-diff/scripts/source_diff.py --orig .vibeoffice/public --clone src/atboffice --json
QT_QPA_PLATFORM=offscreen PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/corpus tests/gui/test_gestures_drag.py tests/gui/test_ledger_context_menu.py tests/gui/test_crash_replay_diagnostics.py tests/gui/test_file_safety_regression.py tests/test_imgdiff.py tests/test_i18n_phase6.py -ra
# 分别替换 word / excel / powerpoint；这是原有宽松审计，结果不是发布通过率
PYTHONPATH=src conda run -n ATBOffice python scripts/run_corpus_audit.py --corpus-dir tests/docs/word --workers 2
```

本次调用现有语料 runner 的外层设60秒总超时，不能据此宣称 runner 已实现逐文件超时。诊断未写回任何样本。短程 GUI 探针加载 Strict DOCX、nested-runs、SimpleWithComments XLSX、master-slides PPTX 并抓图/关闭，4/4退出0；这只证明短程路径未崩溃，不是视觉正确。宏丢失是默认 reader/writer 直接往返实测；保护填充为直接释放处理器探针，两者都须补真实UI回归。

原始日志在本地 `docs/clone/evidence/phase7/`；该目录受现有 `.gitignore` 排除，因此仓库可传播证据以本报告及 `PHASE7_AUDIT_SUMMARY.json` 为准，正式实施需通过CI artifact或明确纳管路径保存原始日志/截图。未运行全量测试、全量原生截图、全部文档参考渲染或长程原生压力，不宣称完成这些验证。
