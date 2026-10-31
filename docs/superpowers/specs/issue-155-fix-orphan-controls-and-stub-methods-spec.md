# Design Specification: Issue #155 (TASK-401)
## 修复孤儿无信号控件并规范基类窗口虚方法接口

### 1. Context & Motivation
经静态 AST 与运行期控件扫描分析，ATBOffice 处于第四阶段（Phase 4）终态收敛过程。当前代码库中存在若干孤儿控件（未绑定任何槽函数或未接通业务逻辑的按钮/菜单）以及基类窗口中的空桩方法。本任务旨在：
1. 联动接通常用排版对话框中的孤儿按钮（段落制表位、编号自定义定制向导）；
2. 汉化审阅工具栏并将标记筛选、接受/拒绝修订及删除批注动作完整接通至文档与审阅面板；
3. 规范动画窗格添加效果菜单交互并绑定动作；
4. 规范 `BaseOfficeWindow` 与 `SearchAdapter` 中的虚基类方法；
5. 提供全面的自动化单元与集成测试 `tests/test_orphan_stubs.py`。

---

### 2. Detailed Technical Design

#### 2.1 ParagraphDialog.btn_tabs 联动 TabsDialog
- **文件**: `src/atboffice/modules/writer/dialogs/paragraph_dialog.py`
- **槽函数**: `_on_tabs_clicked(self) -> None`
- **逻辑**:
  - 实例化 `TabsDialog(parent=self, tabs=self.props.tabs)`。
  - 若对话框被接受 (`QDialog.DialogCode.Accepted`)，读取 `dlg.get_tabs()` 回填至 `self.props.tabs`。
  - 调用 `self._trigger_preview()` 刷新段落预览。
  - 在 `get_properties()` 中确保返回的 `ParagraphProperties.tabs` 携带最新的制表位列表。

#### 2.2 BulletsNumberingDialog.btn_customize 弹出列表层级自定义定制向导
- **文件**:
  - `src/atboffice/modules/writer/dialogs/customize_list_dialog.py` (新增)
  - `src/atboffice/modules/writer/dialogs/bullets_numbering.py` (接线)
- **对话框设计 (`CustomizeListDialog`)**:
  - 继承 `QDialog`，支持 Word 2003 经典“自定义项目符号/编号/多级符号列表”界面。
  - 包含控件：
    - 级别选择列表（1~9 级，用于多级符号）；
    - 编号格式文本框（如 `%1.`）；
    - 编号样式下拉框（1, 2, 3... / I, II, III... / A, B, C... / 项目符号 / 无）；
    - 起始编号设置 (`QSpinBox`)；
    - 对齐方式（左对齐、居中、右对齐）及对齐位置 (`QDoubleSpinBox`)；
    - 文本缩进位置及制表位设置；
    - 实时预览区域 (`ParagraphPreviewWidget` 或自定义列表预览部件)；
    - 完整 `retranslate_ui()` 与 `safe_tr()` 支持。
- **BulletsNumberingDialog 接线**:
  - `self.btn_customize.clicked.connect(self._on_customize_clicked)`。
  - 打开 `CustomizeListDialog` 并将定制结果合并到返回模型中。

#### 2.3 ReviewToolbar 汉化与标记显隐、接受/拒绝动作接线
- **文件**:
  - `src/atboffice/modules/writer/views/review_pane.py`
  - `src/atboffice/modules/writer/view.py`
- **设计**:
  - 汉化 `ReviewToolbar` 所有文字（通过 `safe_tr()` 映射地道中文）。
  - 新增信号 `markup_filter_changed = Signal(bool, bool, bool)`，分别对应（批注 comments、插入/删除 ins_del、格式 formatting）。
  - 连接 `act_show_comments.toggled`、`act_show_ins_del.toggled`、`act_show_formatting.toggled` 发送该信号。
  - `ReviewPane` 增加 `set_markup_filter(self, show_comments: bool, show_ins_del: bool, show_formatting: bool) -> None`，根据过滤条件筛选列表项及批注气泡。
  - 在 `WriterView` 中完成信号槽接线：
    - `review_toolbar.markup_filter_changed` -> `review_pane.set_markup_filter`
    - `review_toolbar.accept_change_requested` -> 接受当前选区或光标处修订
    - `review_toolbar.accept_all_requested` -> `accept_all_revisions`
    - `review_toolbar.reject_change_requested` -> 拒绝当前选区或光标处修订
    - `review_toolbar.reject_all_requested` -> `reject_all_revisions`
    - `review_toolbar.delete_comment_requested` -> 删除当前选区或激活的批注
    - `review_toolbar.delete_all_comments_requested` -> 删除全部批注
    - `review_toolbar.new_comment_requested` -> 在光标处新建批注对话框

#### 2.4 AnimationPane.btn_add_effect 弹出菜单与动作绑定
- **文件**: `src/atboffice/modules/presentation/views/animation_pane.py`
- **设计**:
  - `self.btn_add_effect.clicked.connect(self.btn_add_effect.showMenu)`。
  - 确保 4 大类菜单（进入 Entrance、强调 Emphasis、退出 Exit、动作路径 Motion Paths）及其子动作均使用地道中文翻译并关联图标。
  - 选中任何动作即调用 `_on_add_effect_chosen(cls, eff)` 为幻灯片中选中的图形或首个图形添加动画。

#### 2.5 LecternTaskPane.title_button 接线
- **文件**: `src/atboffice/modules/presentation/views/workspace.py`
- **设计**:
  - `self.title_button.clicked.connect(self.title_button.showMenu)`，确保点击标题直接触发任务窗格切换菜单。

#### 2.6 BaseOfficeWindow 与 SearchAdapter 虚基类方法规范化
- **文件**:
  - `src/atboffice/ui/shell/base_window.py`
  - `src/atboffice/core/search.py`
- **BaseOfficeWindow 规范化**:
  - 对于 `undo`, `redo`, `cut`, `copy`, `paste`:
    - 消除无意义空 pass，实现通用分发逻辑：优先尝试向当前拥有焦点的子控件（如 `focusWidget()`）派发标准 Qt 动作或方法，若不支持则静默安全返回，并提供规范 docstring。
  - 对于 `zoom_in`, `zoom_out`, `zoom_reset`:
    - 优先检查并调用当前活动视图的缩放接口（如 `self.centralWidget().zoom_in()` 等），保持优雅默认实现。
  - 对于 `render_to_printer(printer: QPrinter)`:
    - 规范虚方法声明，说明由派生模块窗口（Quire/Ledger/Lectern）负责具体的页面排版光栅化绘制。
- **SearchAdapter 规范化**:
  - 严格保持标准 ABC 模式，使用 `@abstractmethod` 装饰器、规范类型注解与清晰抽象接口定义。

---

### 3. Verification Plan
- 编写 `tests/test_orphan_stubs.py`，全覆盖测试：
  - 测试 `ParagraphDialog` 点击制表位按钮能够呼出 `TabsDialog` 并同步数据。
  - 测试 `BulletsNumberingDialog` 点击自定义按钮能够弹出 `CustomizeListDialog` 并返回定制属性。
  - 测试 `ReviewToolbar` 所有中文字符串、标记过滤器信号联动、接受/拒绝修订及删除批注槽函数接线。
  - 测试 `AnimationPane` 添加效果菜单弹出与动作触发。
  - 测试 `LecternTaskPane` 标题菜单与关闭交互。
  - 测试 `BaseOfficeWindow` 默认虚方法的安全性（派发至焦点部件或安全无副作用）。
  - 测试 `SearchAdapter` 派生类的契约完整性。
- 运行完整测试套件：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_orphan_stubs.py tests/gui/test_writer_dialogs.py -v`。
