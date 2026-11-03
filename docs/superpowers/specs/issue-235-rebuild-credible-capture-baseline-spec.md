# Spec: TASK-701 重建可信截图与功能验收基线 (Issue #235)

## 1. Overview & Problem Analysis

在先前的第六期（Phase 6）图像与功能验收中，存在以下严重的可信度缺陷：
1. **静默降级（Fallback Grabs）**：`scripts/capture_atboffice_screens.py` 在遇到未映射场景、对话框异常或未实现菜单时，捕获了异常并静默回退为 `window.grab()`。这导致在 Quire 175 张截图中出现多达 65 张完全相同的全屏图，Ledger 131 张截图中出现多达 84 张完全相同的全屏图，产生“全量 412 张截图均已完成”的假象。
2. **指标混淆（MAE vs. SSIM）**：`scripts/imgdiff.py` 将经过尺寸缩放（320×200）后的平均绝对误差归一化值（`1.0 - MAE/255`）误称或宣传为“结构相似度（SSIM）”，掩盖了局部控件、工具栏箭头、对话框排版的几何偏差。
3. **缺乏状态合同与细粒度矩阵**：未对原版 `records.json` 412 条记录建立逐一对应、明确状态合同与处置的控制矩阵（Control Matrix），无法区分已验证（verified）、部分实现（partial）、缺失（missing）与未验证（unverified）。

TASK-701 旨在确立第七期的**可信基线**：
- 替换含混文件名分派，通过显式场景注册器验证真实状态；
- 失败输出 failed，彻底禁止 fallback；
- 412 条记录建立完整控制矩阵与处置分类；
- 严格区分 MAE 与 SSIM/ROI 分数，几何与全图分别保存；
- 提供完整的定向 pytest 自动化合约测试。

---

## 2. Architecture & Design Specifications

### 2.1 模块与文件职责

```
scripts/
├── phase7_capture_scenarios.py     # [新增] 显式场景注册器、状态合约验证与无降级抓取
├── capture_atboffice_screens.py    # [重构] 接入场景注册器，去除静默 fallback，支持严格模式
└── imgdiff.py                      # [重构] 区分 MAE 与 SSIM/ROI，多尺度与局部几何独立打分

docs/clone/
├── phase7_control_matrix.csv       # [新增] 412 条记录逐条状态合同与处置矩阵
└── phase7_features.csv             # [更新] 更新 tooling 截图套件条目证据与验证状态

tests/
└── test_phase7_capture_contract.py # [新增] 定向合约测试：矩阵完整性、无降级验证、指标区分
```

### 2.2 显式场景注册器设计 (`scripts/phase7_capture_scenarios.py`)

- **数据模型**：
  ```python
  class ScenarioStatus(str, Enum):
      VERIFIED = "verified"
      PARTIAL = "partial"
      MISSING = "missing"
      FAILED = "failed"

  @dataclass
  class CaptureScenario:
      id: int
      module: str
      filename: str
      category: str
      gui_target: str
      action: str
      status: ScenarioStatus = ScenarioStatus.UNVERIFIED
      handler: Callable[[Any], QPixmap] | None = None
      tab_index: int | None = None
      target_widget_class: str | None = None
  ```
- **核心原则**：
  1. **禁止 Fallback**：如果场景未注册、控件无法实例化、目标 Tab 不存在或可见性断言失败，直接抛出 `ScenarioExecutionError`，结果标为 `FAILED`，禁止使用 `win.grab()` 或纯色 Pixmap 替代。
  2. **状态验证契约**：
     - 对话框（dialog）：必须验证 dialog 实例有效、尺寸合法，若包含 TabWidget 必须验证 Tab 索引匹配。
     - 菜单（menu）：必须证明菜单已展开或处于可激活状态（offscreen 模式下可提取/验证 QMenu action 列表与其几何位置）。
     - 窗格（pane）：验证对应 DockWidget/Sidebar 处于可见并已布局状态。
  3. **重复截图检测**：对捕获的 Pixmap 计算 SHA-256 哈希，若不同语义状态产生意外哈希碰撞，记录警告或阻止伪装通过。

### 2.3 差异分析引擎重构 (`scripts/imgdiff.py`)

- **指标数学规范**：
  - **Pixel Similarity (MAE)**:
    $$S_{MAE} = 1.0 - \frac{\sum |A_{i} - B_{i}|}{N \times 255.0}$$
    明确标为 `pixel_mae_similarity`，绝不宣称为 SSIM。
  - **Structural / Geometry Metric**:
    计算局部 ROI（例如中心对话框区域、工具栏条带）的边缘/梯度差异或真实结构相似度，输出 `roi_similarity` 与 `geometry_delta`。
  - **综合报告**：输出包含 `pixel_similarity`、`roi_similarity`、`geometry_match` 的结构化报告，原生与 offscreen 分别标明。

### 2.4 412 控制矩阵设计 (`docs/clone/phase7_control_matrix.csv`)

- **表头规范**：
  `id,module,original_ref,target_ref,context,command_id,visual_status,behavior_status,test,evidence`
- **行数与对齐**：
  精确包含 412 行，一一对应 `.vibeoffice/screenshots/records.json`。
- **状态处置值**：
  - `visual_status`: `verified` | `partial` | `missing` | `unverified`
  - `behavior_status`: `verified` | `partial` | `missing` | `unverified`
  - 明确标注每个条目的关联测试（如 `tests/test_phase7_capture_contract.py`）及证据文件路径。

### 2.5 定向测试设计 (`tests/test_phase7_capture_contract.py`)

1. **测试 412 控制矩阵完整性**：
   - 读取 `.vibeoffice/screenshots/records.json` 与 `docs/clone/phase7_control_matrix.csv`；
   - 断言记录数严格为 412，无遗漏、无多余；
   - 断言所有必填字段（id, module, original_ref, target_ref, visual_status, behavior_status）非空；
   - 断言状态值处于合法枚举内。
2. **测试场景注册器与严格无降级机制**：
   - 未注册场景在严格模式下抛出 `ScenarioExecutionError`；
   - 构造异常或错误 Tab 时拒绝 fallback；
   - 捕获结果明确标注 failed。
3. **测试重复图与哈希检测**：
   - 验证能够检测相同哈希截图并输出告警/异常。
4. **测试 imgdiff 指标独立性**：
   - 验证 `compare_images` 返回对象包含独立的 `pixel_mae_similarity` 与 `roi_similarity`；
   - 验证报告输出不包含“MAE as SSIM”的虚假描述。

---

## 3. Implementation Steps & Verification

1. 创建失败回归测试 `tests/test_phase7_capture_contract.py`（TDD 红灯）。
2. 实现 `scripts/phase7_capture_scenarios.py` 场景注册与状态验证逻辑。
3. 生成并完善 `docs/clone/phase7_control_matrix.csv` 412 项完整矩阵。
4. 重构 `scripts/capture_atboffice_screens.py` 与 `scripts/imgdiff.py`。
5. 运行定向测试直至绿灯：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_phase7_capture_contract.py -ra`。
6. 更新 `docs/clone/phase7_features.csv`。
