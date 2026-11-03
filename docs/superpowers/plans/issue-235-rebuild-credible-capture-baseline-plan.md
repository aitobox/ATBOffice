# Implementation Plan: TASK-701 重建可信截图与功能验收基线 (Issue #235)

## Overview
重构 ATBOffice 截图抓取与图像对比套件，建立 412 项完整控制矩阵与显式场景注册器，彻底消除静默降级（fallback），严谨区分 MAE 与 SSIM/ROI 指标，并提供全套自动化合约测试。

---

## Tasks

### Task 1: 编写失败的回归测试套件 `tests/test_phase7_capture_contract.py`
- **目标**: 落实 TDD，先写合约测试，确认红灯。
- **涉及文件**: `tests/test_phase7_capture_contract.py` (新增)
- **测试内容**:
  1. `test_control_matrix_schema_and_completeness`: 412 条记录与 `records.json` 严格一一对应，表头与合法枚举校验。
  2. `test_scenario_registry_no_silent_fallback`: 场景注册器拒绝静默 fallback，错误场景抛出异常并置为 FAILED。
  3. `test_duplicate_hash_tracker`: 检测相同 SHA-256 截图哈希碰撞。
  4. `test_imgdiff_metric_separation`: 区分 `pixel_mae_similarity` 与 `roi_similarity`，杜绝“MAE as SSIM”。
- **运行命令**: `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_capture_contract.py -ra` (预期失败)

### Task 2: 实现场景注册器 `scripts/phase7_capture_scenarios.py`
- **目标**: 提供显式场景配置、目标控件验证与防降级执行器。
- **涉及文件**: `scripts/phase7_capture_scenarios.py` (新增)
- **核心组件**:
  - `ScenarioStatus`, `CaptureScenario`, `ScenarioCaptureError`
  - `CaptureScenarioRegistry`: 加载 `records.json`、注册显式触发器、执行与验证、哈希去重与碰撞检测。

### Task 3: 构建 412 条记录控制矩阵 `docs/clone/phase7_control_matrix.csv`
- **目标**: 覆盖原版 `records.json` 中全部 412 条记录，区分 `verified/partial/missing/unverified`。
- **涉及文件**: `docs/clone/phase7_control_matrix.csv` (新增)
- **数据源**: `.vibeoffice/screenshots/records.json`。

### Task 4: 重构截图抓取脚本 `scripts/capture_atboffice_screens.py`
- **目标**: 移除所有静默 `window.grab()` 降级，接入 `CaptureScenarioRegistry`，支持严格模式与失败汇报。
- **涉及文件**: `scripts/capture_atboffice_screens.py` (修改)

### Task 5: 重构图像对比脚本 `scripts/imgdiff.py`
- **目标**: 区分全图 MAE 像素相似度与 ROI 局部几何相似度，严谨修正报告文本与数学定义。
- **涉及文件**: `scripts/imgdiff.py` (修改)

### Task 6: 更新特性状态与影响范围 `docs/clone/phase7_features.csv`
- **目标**: 更新 `Automated Screenshot Capture and imgdiff Analysis Suite` 为 `verified` 并补充测试证据。
- **涉及文件**: `docs/clone/phase7_features.csv` (修改)

### Task 7: 全量运行测试与验收门禁验证
- **目标**: 验证定向测试与现有测试全部通过，无 Qt 未处理异常。
- **运行命令**:
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_capture_contract.py -ra`
  - `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_i18n_phase6.py -ra`
