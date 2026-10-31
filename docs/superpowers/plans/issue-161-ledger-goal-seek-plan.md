# Plan: Issue #161 - Ledger 单变量求解 (Goal Seek)

## Overview
按照 TDD 流程实现 Ledger 单变量求解功能：
1. 编写单变量求解引擎核心算法与边界用例测试。
2. 实现 `src/atboffice/modules/spreadsheet/calc/goal_seek.py`。
3. 实现 `src/atboffice/modules/spreadsheet/dialogs/goal_seek_dlg.py`。
4. 暴露对话框至 `src/atboffice/modules/spreadsheet/dialogs/__init__.py`。
5. 接入 `src/atboffice/ui/shell/ledger_window.py` 与 `src/atboffice/ui/shell/mac_menu.py`。
6. 运行全量测试验证无回归。

---

## Tasks

### Task 1: 编写单元与集成测试套件 (TDD Tests First)
- **File**: `tests/modules/spreadsheet/test_goal_seek.py`
- **Details**:
  - 测试线性公式求解：如 `=B1*2 + 10`，目标值 50，反推 B1 为 20。
  - 测试多项式/非线性公式求解：如 `=B1^2 - 16`，目标值 0，反推 B1 为 4。
  - 测试初值已等于目标值立即返回。
  - 测试无依赖导数为 0 时的收敛探测与容错。
  - 测试目标单元格缺少公式、可变单元格包含公式、无效目标值等边界异常。
  - 测试跨表单元格引用解析。
  - 测试 `GoalSeekDialog` 与 `GoalSeekStatusDialog` 的 UI 交互行为（包含确定回填与取消还原）。
- **Verification**: 初始运行失败（ImportError / ModuleNotFound）。

### Task 2: 实现单变量求解核心算法与解析引擎
- **File**: `src/atboffice/modules/spreadsheet/calc/goal_seek.py`
- **Details**:
  - `GoalSeekParams` 与 `GoalSeekResult` 数据模型。
  - 引用解析辅助函数 `parse_cell_ref(ref_str, default_sheet)`，支持单表 A1 及跨表 `Sheet1!A1` / `'My Sheet'!$B$2`。
  - `solve_goal_seek(...)` 核心算法：
    - 验证目标单元格是否包含公式、可变单元格是否为纯数值。
    - 记录可变单元格初始数值与现场状态。
    - 割线法与二分逼近混合迭代，容差判断与奇异点防护。
    - 在求解探测结束时恢复现场，返回包含迭代步数、求解值、实际误差的 `GoalSeekResult`。
- **Verification**: `test_goal_seek.py` 中的算法核心测试通过。

### Task 3: 实现经典 2003 单变量求解对话框
- **File**: `src/atboffice/modules/spreadsheet/dialogs/goal_seek_dlg.py`
- **Details**:
  - `GoalSeekDialog`:
    - 包含“目标单元格”、“目标值”、“可变单元格”三个文本输入框。
    - 自动根据当前活动单元格填入“目标单元格”。
    - 校验输入有效性并弹窗提示错误（无公式、非数值、格式错误等）。
    - 调用 `solve_goal_seek` 并呼出 `GoalSeekStatusDialog`。
  - `GoalSeekStatusDialog`:
    - 显示求解状态文本、目标值、当前计算结果表格。
    - 确定：保留更改，并记录撤销栈。
    - 取消：将可变单元格恢复至初始状态。
  - 100% 具备 `safe_tr()` 与 `retranslate_ui()` 国际化支持。
- **Verification**: `test_goal_seek.py` 中的对话框测试通过。

### Task 4: 导出对话框接口
- **File**: `src/atboffice/modules/spreadsheet/dialogs/__init__.py`
- **Details**:
  - 导出 `GoalSeekDialog`, `GoalSeekStatusDialog`。

### Task 5: 接入 Ledger 主窗口与 macOS 原生菜单
- **Files**:
  - `src/atboffice/ui/shell/ledger_window.py`
  - `src/atboffice/ui/shell/mac_menu.py`
- **Details**:
  - 在 `ledger_window.py` 中实现 `open_goal_seek()`，并在 `action_registry` 中绑定 `"goalSeek"`。
  - 在 `mac_menu.py` 的 Tools 菜单中注册 `tools_goal_seek` 动作，并与 `open_goal_seek` 槽函数绑定。
- **Verification**: 验证动作绑定及菜单创建逻辑。

### Task 6: 全量测试验证与质量门禁
- **Verification**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_goal_seek.py -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -k "spreadsheet or auditing or formula"`
