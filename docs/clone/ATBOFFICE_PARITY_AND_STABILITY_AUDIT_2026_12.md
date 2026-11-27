# ATBOffice vs. `.vibeoffice` 第十二期全面对比、视觉渲染回归与稳定性审计报告

> **审计基准日期**: 2026-11-26  
> **对照基线**: `.vibeoffice/`（原版 JS/HTML 黄金实现） vs. `ATBOffice` 第十二期 Wave 1 + Wave 2 工作区  
> **双端视觉比对报告**: [OFFICE_DOCS_DIFF.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/clone/OFFICE_DOCS_DIFF.md)  
> **工具栏逐控件对照矩阵**: [TOOLBAR_BASELINE_MATRIX.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/clone/TOOLBAR_BASELINE_MATRIX.md)  
> **阶段门禁状态**: **✅ Wave 1 + Wave 2 全部门禁通过**（73 份 `--strict` 视觉门禁 `95.37%`、`0` 低于单文档阈值；154 份语料审计 `0` 失败/`0` 崩溃/`0` 丢数；全量自动化测试通过）

---

## 一、 执行摘要（Executive Summary）

第十二期对齐针对用户在实机运行 `python -m atboffice` 打开真实文档并插入/编辑新元素时偶发崩溃退出的问题，以及 `v0.2.0` 引入 `Fusion` 浅色主题后在 Excel 视觉比对中出现的 Chrome 回归，分两波次完成根治与全量核验：

| 审计维度 | Wave 2 前基线 | 本期实测结果 | 门禁要求 | 状态 |
|---|---:|---:|---|---|
| **73 份核心文档 `--strict` 视觉均值** | `92.71%` | **`95.37%`**（MAE `96.75%`） | `>= 94.0%` | **PASS** |
| **低于 85% 单文档数（不含豁免）** | 2（`poi__45540` `81.8%`、`poi__49156` `84.5%`） | **`0`**（44 份 `>=95%`，29 份 `85%-95%`） | `0` | **PASS** |
| **154 份语料严格审计 (`run_corpus_audit.py --strict`)** | 154/154 | **`154/154`**（0 failure / 0 crash / 0 loss） | 0 失败/崩溃/丢数 | **PASS** |
| **源码 AST 健康度 (`source_diff.py --check`)** | 0 Orphan / 0 Stub | **`CLEAN`（0 Orphans, 0 Stubs）** | `CLEAN` | **PASS** |
| **工具栏逐控件接线 (`audit_toolbars_parity.py`)** | 存在跨端文案漂移 | **Quire 150 / Ledger 65 / Lectern 117（100% WIRED）** | 100% 接线 | **PASS** |
| **77 份旧格式/加密/损坏文档 GUI 保护** | 子进程打开审计 | **已打开脏文档、路径与内容 100% 保留** | 无破坏/明确提示 | **PASS** |

---

## 二、 Wave 1 健壮性加固总结（已在 `main` 合入）

1. **懒加载 `ImportError` 清零与静态 AST 门禁**：
   - 修复 `ledger_auditing.py`（`to_a1` -> `cell_name`）、`modules/writer/view.py`（`add_comment` -> `canvas_view.insert_comment`）及 `fn_dynamic.py`（`parse_cell_reference` -> `parse_range`）4 处运行期断链；新增 [test_lazy_imports_integrity.py](file:///Users/aitobox/work/aitobox/ATBOffice/tests/test_lazy_imports_integrity.py)。
2. **统一 Qt 故障隔离与 `shiboken6.isValid()` 生命周期守卫**：
   - 新增 [fault_guard.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/core/fault_guard.py) 与 `BaseOfficeWindow.register_owned_timer()` / `stop_owned_timers()`，在三端画布/场景事件与异步定时器上收敛空指针与 C++ 已销毁对象防护。
3. **三端“打开→插元素→编辑→撤销→保存→重开”闭环补齐**：
   - **Quire**：实现 `WriterCanvasView.insert_shape` 与全文档级可撤销浮动对象操作；解决 `openxml-sdk__bullet-complex.docx` 键入阻塞卡顿（20.28s 降至约 1s 内）；补齐 `DocxWriter` 对新建 `ShapeItem`、`PictureItem`（含 `word/media/*` 关系）和 `word/comments.xml` 的无损写出与重开恢复。
   - **Ledger**：将对象拖拽、粘贴、Z 序、文本编辑、对象格式、图表向导（含独立图表工作表）及批注显隐/增删纳入 `UndoService`，补齐 `.xlsx` 批注 XML 与 VML 往返清理。
   - **Lectern**：为 `PresentationHistory` 增加延迟刷新取消与关窗清理，修复 `SlideScene` 悬浮拖拽与键盘事件防护。
   - 门禁见 [test_phase12_element_edit_robustness.py](file:///Users/aitobox/work/aitobox/ATBOffice/tests/gui/test_phase12_element_edit_robustness.py)。

---

## 三、 `atb-office-diff` 73 份核心文档双端渲染回归清零

### 3.1 Excel 24 份回归定位与修复

Commit `9eb12b7` 在全应用启用 Qt `Fusion` 样式与 Luna 调色板后，导致 `GridViewport` 滚动条渲染为带按钮的米色 `Fusion` 轨道、底栏 `SheetTabBar` 保持 `22px` 且占满底部宽度、且竖向滚动条按 `1000` 行计算使滑块过短，造成 24 份 Excel 截图出现 5%–10% 前景像素偏移：

- **样式与几何对齐**：在 [luna_2003.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/styles/luna_2003.py) 新增 `grid_scrollbar_stylesheet()` 并在 [grid_viewport.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/views/grid_viewport.py) 应用；将 [sheet_tab_bar.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/views/sheet_tab_bar.py) 调整为 `18px` 高与顶部贴合的倒梯形页签；在 [view.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/modules/spreadsheet/view.py) 动态按 `65%` 比例收敛 `SheetTabBar` 宽度；并在 `GridViewport._update_scrollbars()` 对齐 `.vibeoffice` 的 `lcl_GetScrollRange`（已用区域 + 1 视口）范围逻辑。
- **典型修复效果**：`libreoffice__empty.xlsx` 由 `89.7%` 恢复至 **`98.9%`**；`poi__45540_form_Header.xlsx` 由 `81.8%` 提升至 **`97.9%`**；`poi__49156.xlsx` 由 `84.5%` 提升至 **`95.1%`**；`libreoffice__totalsRowFunction.xlsx` 达到 **`87.0%`**。

### 3.2 最新 73 份分应用视觉指标（`--region workspace`）

| 应用模块 | 文档数 | 前景相似度均值 | 像素 MAE 均值 | 最低单文档 | 分档统计 (`PARITY_MATCH` / `COSMETIC_MINOR` / `LAYOUT_DRIFT` / `CRITICAL`) |
|---|---:|---:|---:|---|---|
| **Word (Quire)** | 24 | **91.13%** | 95.22% | `85.4%` (`openxml-sdk__Comment066.docx`) | `0 / 24 / 0 / 0` |
| **Excel (Ledger)** | 24 | **96.86%** | 96.24% | `85.5%` (`openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx`) | `20 / 4 / 0 / 0` |
| **PowerPoint (Lectern)** | 25 | **98.02%** | 98.70% | `93.2%` (`libreoffice__tdf112089.pptx`) | `24 / 1 / 0 / 0` |
| **全套件总计** | **73** | **`95.37%`** | **`96.75%`** | **`85.4%`** | **`44 / 29 / 0 / 0`** |

- **门禁口径统一**：[run_office_diff.py](file:///Users/aitobox/work/aitobox/ATBOffice/scripts/run_office_diff.py) 已抽取 `evaluate_strict_gate()`，与 [reporter.py](file:///Users/aitobox/work/aitobox/ATBOffice/scripts/office_diff/reporter.py) 一致地将 `expectations.json` 中的 `reference_limitation` 文档计入全量均值、并在 `--strict` 单文档失败判定中予以豁免（当前 `openxml-sdk__00d63cdd-ee44-4e6a-99af-a7966ffbdda0.xlsx` 本期实测 `85.5%`，已超过 `85.0%` 线）。
- **纯画布区域 (`--region canvas`) 探针备注**：由于现存基线库 `screenshots/office_audit_20261112/vibeoffice` 均按 `--region workspace`（`1178×798`）采集，对 Excel 单独运行 `--region canvas` 采集尺寸为 `1425×740`，触发尺寸/区域护栏返回 `INCOMPARABLE_SIZE`（24/24 未强行拉伸打分），验证了跨区域误判隔离机制有效。

---

## 四、 工具栏、文案、AST 与 77 份异常语料 GUI 核验

1. **工具栏与命令文案对齐**：
   - 修复 [mac_menu.py](file:///Users/aitobox/work/aitobox/ATBOffice/src/atboffice/ui/shell/mac_menu.py) 中 `insertComment` 在 Quire 环境下沿用 Ledger 提示 `"为活动单元格添加批注"` 的问题（现区分 Quire 使用 `"插入新批注"`）。
   - 重新运行 `scripts/audit_toolbars_parity.py` 刷新 [TOOLBAR_BASELINE_MATRIX.md](file:///Users/aitobox/work/aitobox/ATBOffice/docs/clone/TOOLBAR_BASELINE_MATRIX.md)：Quire 150/150、Ledger 65/65、Lectern 117/117，全量 `WIRED`（0 STUB、0 UI_ONLY、0 MISSING）。
   - 运行 `scripts/source_diff.py --check` 返回 `CLEAN (0 Orphans, 0 Stubs)`。
2. **77 份旧格式与异常语料真实窗口 GUI 保护**：
   - 新增 [test_phase12_corpus_gui_resilience.py](file:///Users/aitobox/work/aitobox/ATBOffice/tests/gui/test_phase12_corpus_gui_resilience.py)，验证在 Quire / Ledger / Lectern 已存在未保存修改时尝试打开 `.doc`/`.ppt`、加密 `.docx`（取消与错误密码）及损坏 `.xls`/`.xlsx`/`.docx`/`.pptx`，均会弹出清晰本地化提示（或取消时静默中止），并完整保留原窗口文件路径、脏状态和未保存文本/单元格/幻灯片。
   - 验证 `tests/docs/expectations.json` 稳定划分 `73` 份核心 OOXML 与 `77` 份旧格式/异常文件（`.doc`/`.xls`/`.ppt`/加密/损坏），全部磁盘文件就绪，且 `scripts/run_corpus_audit.py --strict` `154/154` 零崩溃通过。

---

## 五、 后续规划（Wave 3 与 Phase 13 Backlog）

- **Wave 3（`.vibeoffice` 重点高价值能力模块化补齐）**：
  1. 上下文任务窗格自动跟随（`RB.follow` / `context_tools_pane.py` + `view/pane_follows_selection`）；
  2. Paper 2016 Ribbon 模式（`ribbon_bar.py` + 三端声明式 `*_ribbon.py`，仅在 `paper2016` 主题懒构建）；
  3. Lectern 讲义母版与备注母版（`master_view.py` + 打印与 PPTX 往返）；
  4. Ledger 条件格式（色阶/数据条/图标集）端到端闭环测试 + 固定宽度分列标尺控件 + 数据透视图（PivotChart）。
- **Phase 13 Backlog（显式延后长尾项）**：Excel Solver 与 519 函数长尾、WordNet `en.thes` 同义词窗格、Quire 交互式手绘表格画笔与擦除器。
