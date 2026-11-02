# Specification: Issue #201 - [Phase 5] 执行三模块端到端与稳定性最终验收

## 1. Background & Problem Statement

Phase 5 of the ATBOffice project (`[Epic] #188: 第五期：原版交互与工具栏对齐、稳定性治理`) set out to resolve all post-Phase 4 interaction regressions, toolbar action parity, object lifecycles, and data safety across Quire (Word Processor), Ledger (Spreadsheet), and Lectern (Presentation).

All 12 prior sub-issues have been designed, implemented, and merged into `main`:
1. **#189**: 建立三模块崩溃诊断与子进程重放基线 (`CrashDiagnostics`, `SubprocessReplayRunner`, `faulthandler`, `drain_event_loop`)
2. **#190**: 复现并修复交互崩溃与对象生命周期问题 (修复 4 处 Qt 虚方法遮蔽，100 次子进程重放回归)
3. **#191**: 保护保存失败与关闭取消时的未保存数据 (原子写入与暂存回滚、覆盖确认与只读权限保护)
4. **#192**: 建立三模块工具栏逐控件对照与截图基线 (100% 逐项对照矩阵、9 张原生 GUI 截图索引)
5. **#193**: 接通 Ledger 工具栏下拉及分裂按钮菜单 (边框、填充色、字体颜色、求和、合并居中)
6. **#194**: 实现 Ledger 已注册的空工具栏命令 (格式刷、超链接、汇总行、对象格式)
7. **#195**: 修正 Quire 工具栏控件和上下文状态 (表格、绘图、格式刷及上下文可见性)
8. **#196**: 修正 Lectern 工具栏控件和上下文状态 (幻灯片、播放、放映控制及上下文切换)
9. **#197**: 还原 Ledger 右键选择和上下文菜单 (单元格、行、列、选区保持)
10. **#198**: 建立 Ledger 拖动取消与资源清理机制 (Esc、失焦、捕获丢失、第二按键重置)
11. **#199**: 还原 Ledger 选区边框移动与复制 (边框拖拽移动/复制、覆盖提示与撤销)
12. **#200**: 完善 Ledger 填充、行列拖选与边缘滚动 (智能填充柄、行列吸附选择与边缘滚动)

As the final concluding step (Step 13 of 13), **Issue #201** performs comprehensive end-to-end user journey verification, mixed interaction stress testing (100+ cycles per module), full regression validation, and evidence backfill into `docs/clone/features.csv`, `docs/clone/CLONE_DIFF.md`, and `docs/tasks/05_phase5_parity_stability_plan.md`.

---

## 2. Requirements & Acceptance Criteria

### 2.1 Three-Module End-to-End User Workflows
For each of the three modules (Quire, Ledger, Lectern), verify:
1. **Workflow A (Creation to Reopen)**:
   - New Document / Workbook / Presentation.
   - Input textual and structured content.
   - Apply formatting (fonts, styles, alignments, colors).
   - Perform Undo and Redo, confirming reversible state changes.
   - Save to disk (`.docx`, `.xlsx`, `.pptx`), ensuring file exists and is valid.
   - Reopen saved file in a fresh window, verifying that 100% of the content and formatting match the saved state.
2. **Workflow B (Existing File Roundtrip)**:
   - Open existing file.
   - Edit content, verify `is_modified` state transitions to `True`.
   - Re-save to disk, verify file timestamp and updated content.
3. **Workflow C (Close Cancellation & Dirty State Protection)**:
   - Modify document.
   - Trigger close event.
   - Cancel the save confirmation dialog.
   - Assert window remains open, content is intact, and `is_modified` remains `True`.

### 2.2 Stress & Mixed Interaction Stability Gate
1. Execute at least 100 mixed GUI interactions per module:
   - Quire: Caret navigation, typing, selection, styling toggles, ruler changes, zoom, hover.
   - Ledger: Cell cursor moves, formula editing, selection drag, toolbar actions, sheet navigation.
   - Lectern: Slide navigation, shape selection, transform handles, canvas interaction, toolbar actions.
2. Isolated subprocess execution:
   - Execute `--diagnostics` with `--replay-action=stress_interaction` and `--replay-iterations=100` for each module in separate processes.
   - Confirm exit code 0, 0 unhandled exceptions, 0 segmentation faults, and clean `drain_event_loop`.

### 2.3 Quality Gate & Documentation Synchronization
1. Full test suite: Execute `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/` with 0 failures.
2. AST audit: Run `source_diff.py` verifying 0 orphan controls and 0 stub implementations.
3. Parity calculation: Run `parity.py --markdown` verifying 100.0% must-have score.
4. Backfill evidence into:
   - `docs/clone/CLONE_DIFF.md`: Complete TASK-503, TASK-505, TASK-506, TASK-507 checklist, record test run metrics, and update Phase 5 Shippability verdict.
   - `docs/clone/features.csv`: Verify all audited items reflect true verified state.
   - `docs/tasks/05_phase5_parity_stability_plan.md`: Update Phase 5 status to Complete.

---

## 3. Architecture & Test Design

### 3.1 Test Suite Location
`tests/gui/test_phase5_e2e_acceptance.py`

### 3.2 Fixtures & Components
- Utilizes `qtbot` for asynchronous GUI event pumping and window lifecycle management.
- Uses `tmp_path` for temporary file isolation during save and reopen roundtrips.
- Utilizes `WindowManager.get_instance()` and individual windows (`QuireWindow`, `LedgerWindow`, `LecternWindow`).
- Utilizes `SubprocessReplayRunner` from `tests/gui/test_crash_replay_diagnostics.py` for headless subprocess stress replay.

### 3.3 Visual & Screenshot Evidence
- Automated generation of screenshots verifying active state of all 3 modules during E2E acceptance tests.
