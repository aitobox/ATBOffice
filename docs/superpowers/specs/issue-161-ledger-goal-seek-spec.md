# Spec: Issue #161 - Ledger 单变量求解 (Goal Seek) 数值逼近迭代器与交互对话框

## 1. 概述与背景 (Overview & Background)

在电子表格应用（Excel 2003 / Ledger）中，**单变量求解 (Goal Seek)** 是一项核心的高级财务推算与公式逆向求解工具。当用户知道某个公式计算结果的目标值（Target Value），但不知道需要输入什么数值（Changing Cell）才能获得该结果时，单变量求解可通过数值逼近算法自动反推可变单元格的最优解。

原 JavaScript 项目在 `.vibeoffice/public/ledger/js/dialogs2.js`（`D.goalSeek`, `D.solveGoal`）中提供了单变量求解支持。本项目在 Python 3.12 / PySide6 技术栈下进行 1:1 原版对齐与企业级增强，提供高精度数值逼近迭代引擎、完整的错误处理机制、经典 Excel 2003 风格输入/状态对话框以及多语言国际化支持。

---

## 2. 算法与核心设计 (Architecture & Algorithm Design)

### 2.1 模块职责分工

1. **核心计算引擎** (`src/atboffice/modules/spreadsheet/calc/goal_seek.py`)
   - 包含数值迭代求解器核心逻辑，脱离 Qt GUI 强依赖，保证可测试性与高性能。
   - `GoalSeekSolver`:
     - 结合**割线法 (Secant Method)** 与**二分法 (Bisection Method)** 的混合数值逼近算法（类 Brent 思想），具备极强的非线性适应能力和发散回退保护。
     - 状态隔离：单变量求解在探测期间维护现场保护，求解结束后可还原初始状态，或根据用户确认写入解。
   - 数据类：
     - `GoalSeekParams`: 封装目标单元格地址、目标值、可变单元格地址、最大迭代次数 (`max_iterations`, 默认 100)、容差 (`tolerance`, 默认 0.001)。
     - `GoalSeekResult`: 封装求解结果（`success: bool`, `solution: float`, `iterations: int`, `target_value: float`, `current_value: float`, `error_margin: float`, `initial_value: float`, `error_message: str | None`）。

2. **UI 交互对话框** (`src/atboffice/modules/spreadsheet/dialogs/goal_seek_dlg.py`)
   - `GoalSeekDialog`:
     - 经典 Excel 2003 单变量求解参数输入弹窗。
     - 包含“目标单元格(Set cell)”、“目标值(To value)”、“可变单元格(By changing cell)”三个输入控件及“确定”、“取消”按钮。
     - 自动化引用解析与前置校验（必须包含公式、必须包含数值、禁止自引用、数字格式校验）。
   - `GoalSeekStatusDialog`:
     - 求解状态结果面板。
     - 展示求解状态信息（已找到解 / 可能尚未找到解）、目标值、当前计算结果对比。
     - 点击“确定”保留求解值并支持 Undo 事务；点击“取消”撤销回填、恢复可变单元格初始值。

3. **宿主接入与菜单联动**
   - `src/atboffice/ui/shell/ledger_window.py`:
     - 注册 `goalSeek` action 处理函数 `open_goal_seek()`。
   - `src/atboffice/ui/shell/mac_menu.py`:
     - 在“工具(&Tools)”菜单中增加“单变量求解(&G)...” (`tools_goal_seek`) 菜单项并与快捷键/槽函数联动。

---

## 3. 数值迭代算法细节 (Numerical Method)

1. **目标函数构造**：
   定义残差函数 $R(x) = f(x) - \text{goal}$，其中 $f(x)$ 为在可变单元格赋值 $x$ 后，经拓扑图局部重算得到的目标单元格数值。
2. **初始探测与步长选择**：
   - 设可变单元格初始值为 $x_0$。
   - 若 $x_0 = 0$，选择初始摄动步长 $\Delta = 0.01$（或基于目标值尺度的量纲）；若 $x_0 \neq 0$，取 $x_1 = x_0 \times 1.01$（若 $x_1 == x_0$ 则取 $x_0 + 0.01$）。
3. **收敛判据**：
   - 绝对误差判据：$|R(x_k)| \le \epsilon$（默认 $\epsilon = 0.001$，且考虑尺度缩放 $\le 0.001 \times \max(1, |\text{goal}|) \times 10^{-3}$ 或 $10^{-9}$）。
4. **混合步进机制**：
   - 割线迭代式：$x_{k+1} = x_k - R(x_k) \cdot \frac{x_k - x_{k-1}}{R(x_k) - R(x_{k-1})}$。
   - 若出现 $R(x_k) = R(x_{k-1})$（导数近似 0）或产生非数值异常（`NaN`, `#DIV/0!`, `#VALUE!`）：
     - 采用倍增摄动或符号交替步进 $x_{k+1} = x_k \cdot 2 + 1.0$ 或向相反方向探查。
   - 若两点残差异号 ($R(a) \cdot R(b) < 0$)，激活区间二分截断，防止割线法跨越奇异点发散。
5. **最大迭代保护**：
   - 最大迭代次数达到 100 时停止，若未满足收敛容差，返回历史最优解（残差最小点）并标记 `success = False`。

---

## 4. 边界用例与异常防御 (Edge Cases & Robustness)

1. **初始值即为目标解**：
   - $f(x_0) == \text{goal}$ 时，迭代步数 0，立刻返回成功。
2. **目标单元格不含公式**：
   - 弹窗提示“目标单元格必须包含公式。”，阻断求解。
3. **可变单元格包含公式**：
   - 弹窗提示“可变单元格必须包含数值，不能包含公式。”，阻断求解。
4. **可变单元格与目标单元格相同**：
   - 弹窗提示“目标单元格与可变单元格不能为同一单元格。”，阻断求解。
5. **目标值非数值输入**：
   - 用户输入空字符串或字母（如 "abc"），提示“请输入有效的数字目标值。”。
6. **公式计算出现除以零或错误值**：
   - 捕获 `DIV0`, `VALUE`, `NUM` 等 Excel 错误类型，视为无有效导数，平滑调整试探点而不使程序崩溃。
7. **多工作表跨表引用**：
   - 支持跨表引用格式，如 `Sheet2!B3`、`'Data Summary'!$C$10`。
8. **UI 取消与模型一致性**：
   - 无论求解成功与否，在 Status 弹窗点击“取消”时，必须保证可变单元格恢复至求解前初始数值，且相关公式链重新评估回初始状态。

---

## 5. 国际化 (i18n)

严格遵循项目规则，所有 UI 文本均使用 `safe_tr()` 包装，并提供地道中文与英文对照：
- "单变量求解" / "Goal Seek"
- "目标单元格(&E):" / "S&et cell:"
- "目标值(&V):" / "To &value:"
- "可变单元格(&C):" / "By &changing cell:"
- "单变量求解状态" / "Goal Seek Status"
- "目标单元格 {0} 的单变量求解已找到一个解。" / "Goal Seeking with Cell {0} found a solution."
- "目标单元格 {0} 的单变量求解可能尚未找到解。" / "Goal Seeking with Cell {0} may not have found a solution."
- "目标值:" / "Target value:"
- "当前值:" / "Current value:"
- "确定" / "OK"
- "取消" / "Cancel"

---

## 6. 验证计划 (Verification Plan)

- 单元测试与数值算法测试：`tests/modules/spreadsheet/test_goal_seek.py`
  - 线性方程求解（如 $y = 2x + 10 = 50 \Rightarrow x = 20$）
  - 非线性/复合公式求解（如 $y = x^2 - 16 = 0 \Rightarrow x = 4$）
  - 财务公式求解（如 PMT 年金月供反推贷款本金）
  - 多工作表跨表公式反推
  - 错误单元格与边界校验（无公式、无效目标值、常数导数发散）
  - 对话框交互行为（确定回填、取消恢复现场）
- 整体测试套件回归验证：
  `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_goal_seek.py -v`
