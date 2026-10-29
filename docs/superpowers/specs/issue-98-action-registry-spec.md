# Specification: Issue #98 - ActionRegistry 统一命令驱动总线与动作双向同步

## 1. Overview & Context

- **Issue**: [#98 [Phase 2] ActionRegistry 统一命令驱动总线与动作双向同步](https://github.com/aitobox/ATBOffice/issues/98)
- **Parent Epic**: [#96 [Epic] ATBOffice 二期工程：1:1 完整全量移植与核心架构补完 (Phase 2)](https://github.com/aitobox/ATBOffice/issues/96)
- **Prerequisites**: Issue #97 (OfficeSplitButton 与 OfficeDropDownButton - Merged in PR #113)

### Objective
在 ATBOffice 中，各独立窗口的菜单栏（MacMenuBar）与工具栏（OfficeToolBar）过去各自独立创建 QAction，代码冗余且无法实现快捷键和勾选/禁用状态的双向同步。
原版（`.vibeoffice/public/common/ui.js` 及各模块 `commands.js`）统一通过 `ui.cmd` 与 `ui.cmds` 维护动作规范。本项目需构建数据驱动的 `ActionRegistry`，作为菜单和工具栏动作的单一事实源（Single Source of Truth）。

---

## 2. Architecture & Design

### 2.1 ActionSpec (数据模型)
`ActionSpec` 是不可变或结构化的命令动作声明类（dataclass）：
```python
@dataclass
class ActionSpec:
    id: str                                  # 唯一命令标识符，如 "file_save", "spelling"
    label: str                               # 规范文本，带助记键如 "&Save" 或 "保存(&S)"
    icon: QIcon | str | None = None          # 图标或图标资源名
    tip: str = ""                            # 提示文本（ToolTip 与 StatusTip）
    shortcut: str | QKeySequence | QKeySequence.StandardKey | None = None
    checkable: bool = False                  # 是否为开关型动作
    checked: bool = False                    # 默认开关状态
    enabled: bool = True                     # 默认启用状态
    is_split: bool = False                   # 是否适合拆分按钮（OfficeSplitButton）
    is_drop: bool = False                    # 是否适合下拉按钮（OfficeDropDownButton）
    handler: Callable[[], Any] | None = None # 点击触发的回调业务逻辑
```

### 2.2 ActionRegistry (命令总线与注册表)
`ActionRegistry` 继承自 `QObject`，提供以下核心功能：
1. **统一动作实例化与缓存**:
   - `register_action(spec: ActionSpec, parent: QWidget | None = None) -> QAction`:
     声明式注册动作并构建标准 `QAction`。若已注册同名 ID，则更新现有属性并返回已有 `QAction`，保证单例性。
   - `get_action(action_id: str) -> QAction | None`:
     按 ID 获取对应的全局唯一 `QAction` 实例。
   - `has_action(action_id: str) -> bool`:
     检查动作是否存在。
2. **状态双向同步**:
   - `set_enabled(action_id: str, enabled: bool)`: 切换启用状态，所有绑定该 QAction 的菜单和工具栏自动同步。
   - `set_checked(action_id: str, checked: bool)`: 切换勾选状态，菜单复选与工具栏按压状态天然同步。
   - `set_handler(action_id: str, handler: Callable[[], Any])`: 动态绑定或更换业务回调。
   - `trigger_action(action_id: str) -> bool`: 代码级触发指定动作。
3. **规范降级机制 (Non-blocking Fallback)**:
   - 当触发一个尚未接入业务逻辑（`handler is None`）的 Action 时，自动寻找主窗口或父微件的 `statusBar()` 发送非阻塞状态提示：
     `statusBar.showMessage("功能正在联调中", 2000)`
   - 严禁弹窗（QMessageBox）阻塞界面或阻断自动化测试。
4. **i18n 多语言联动**:
   - `retranslate_ui(tr_func: Callable[[str], str] | None = None)`:
     当语言切换时遍历所有已注册的 Actions，更新其 Text, ToolTip, StatusTip。

---

## 3. Edge Cases & Robustness Analysis

1. **重复注册同一 action_id**:
   - 处理：不抛异常，更新 `ActionSpec` 对应属性并复用原有 `QAction` 实例，保证已添加到菜单/工具栏上的引用依然有效。
2. **父窗口没有 statusBar**:
   - 处理：安全检查 `getattr(win, "statusBar", None)`，若不存在或返回 None，则发出 `action_fallback_triggered` 信号或记录 debug 日志，绝不抛出 AttributeError。
3. **Handler 抛出异常**:
   - 处理：执行 `handler` 时增加安全包装，捕获异常并记录，防止单点故障崩溃整个 UI 循环。
4. **内存管理与 QObject 生命周期**:
   - `ActionRegistry` 作为 parent 或挂载在 `QMainWindow` 上，随窗口销毁而正常清理。
5. **快捷键冲突与类型支持**:
   - 支持字符串（如 "Ctrl+S"）、`QKeySequence` 或 `QKeySequence.StandardKey`，统一通过 `QKeySequence` 解析。

---

## 4. Verification & Acceptance Criteria

- [ ] `ActionSpec` 声明完整，类型注解完备。
- [ ] `ActionRegistry` 支持注册、查询、批量注册、状态同步。
- [ ] 菜单栏与工具栏共享相同 QAction 实例，验证状态同步。
- [ ] 未接线动作安全触发状态栏 Toast，不抛异常也不弹阻塞框。
- [ ] 编写并通过独立单元测试 `tests/core/test_action_registry.py`，全量覆盖率 >= 95%。
- [ ] `ruff check .` 零告警通过。
