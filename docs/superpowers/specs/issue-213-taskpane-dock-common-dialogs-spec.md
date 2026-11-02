# Spec: Issue #213 - 统一任务窗格宿主 TaskPaneDock 与公共对话框

## 1. Overview & Objective
本设计实现跨模块通用的 `TaskPaneDock` 任务窗格宿主容器，并统一接入四大公共 UI 组件/对话框：
1. **统一任务窗格宿主容器 (`TaskPaneDock`)**：
   - 继承 `QDockWidget`，包含经典 Office 2003 顶栏（后退、前进、主页、窗格标题下拉菜单、关闭按钮）。
   - 统一窗格注册体系（通过 ID 注册/切换/注销、维护浏览历史 Stack）。
   - 内置通用窗格：`GettingStartedPane`（开始使用）与 `NewDocumentPane`（新建文档）。
   - 供三大模块（Quire / Ledger / Lectern）统一挂载与快捷键触发（`Ctrl+F1`）。
2. **蜂窝调色板对话框 (`HoneycombColorDialog`)**：
   - 标准标签页（Standard）：基于六角形蜂窝算法精准生成 127 个蜂窝色块 + 底部 16 阶灰度色块条。
   - 自定义标签页（Custom）：RGB 旋钮/滑块、Hex 文本输入与实时预览色块对比（New vs Current）。
   - 统一挂接至 `ColorPickerPopup._open_more_colors_dialog`，替代默认的 `QColorDialog`。
3. **文档属性 5 标签对话框 (`DocumentPropertiesDialog`)**：
   - 覆盖 General（常规）、Summary（摘要）、Statistics（统计）、Contents（内容）、Custom（自定义属性）5 个完整标签页。
   - 支持与文档元数据双向绑定读写，支持自定义属性增删。
4. **内置另存为与加密安全选项对话框 (`InAppSaveAsDialog` & `SecurityOptionsDialog`)**：
   - 支持输入文件名、选择格式过滤器、选择保存路径。
   - 提供“工具(Tools)”下拉菜单，集成“安全选项(Security Options)...”弹窗。
   - 支持设置打开文件密码、修改文件密码、建议只读复选框，并在设置密码时进行二次确认。

---

## 2. Architecture & Design Details

### 2.1 TaskPaneDock (`src/atboffice/ui/components/task_pane.py`)
- **继承体系**：`TaskPaneDock(QDockWidget)`
- **Header 标题栏组件 (`TaskPaneHeader`)**：
  - `btn_back (QToolButton)`: ◄ 回退至上一个浏览的窗格，当 `pos <= 0` 时禁用。
  - `btn_fwd (QToolButton)`: ► 前进至下一个浏览的窗格，当 `pos >= len(stack)-1` 时禁用。
  - `btn_home (QToolButton)`: 🏠 回到默认窗格（如 `getting-started`）。
  - `btn_title (QPushButton)`: 显示当前窗格标题及下拉小箭头 ▼。点击弹出 `QMenu`，列出所有非 hidden 的已注册窗格，当前窗格标记为勾选状态。
  - `btn_close (QToolButton)`: ✕ 关闭窗格（调用 `self.dock.close()` / `hide()`）。
- **Body 内容容器**：
  - `QStackedWidget` 承载各已注册窗格的 Widget。
- **公共 API 接口**：
  - `register_pane(pane_id: str, title: str, widget: QWidget, is_default: bool = False, hidden: bool = False)`
  - `show_pane(pane_id: str)`
  - `go_back()`, `go_forward()`, `go_home()`
  - `current_pane_id() -> str`
  - `get_pane(pane_id: str) -> QWidget | None`
  - `retranslate_ui()`: 动态多语言刷新。

### 2.2 HoneycombColorDialog (`src/atboffice/ui/components/honeycomb_color_dialog.py`)
- **继承体系**：`HoneycombColorDialog(QDialog)`
- **Standard 标签页**：
  - `HoneycombWidget(QWidget)`：
    - 13 行六角形网格分布：行 0~6: `7 + r` 个单元，行 7~12: `19 - r` 个单元，合计正好 127 个蜂窝！
    - 颜色分布算法：中心为白/极浅色，半径向外延伸渐变，角度按 360 度色相环映射，高饱和度分布在中外圈，最外圈深色。
    - 单元格交互：鼠标悬浮加亮描边，单击选中色块并更新预览，双击直接确定并退出。
  - 灰度条 (`GrayscaleStrip` / 按钮网格)：
    - 16 阶从纯黑 `#000000` 到纯白 `#FFFFFF`。
- **Custom 标签页**：
  - 2D 色相-饱和度拾取板或标准 RGB 调整（Red, Green, Blue 0~255）。
  - 包含十六进制 Hex 输入框（带 `#` 容错及大小写自适应格式化）。
- **Preview 侧边对比栏**：
  - 新建颜色（New）vs 原有颜色（Current）对比框。
- **静态方法**：
  - `HoneycombColorDialog.getColor(initial: QColor | str = "#3366FF", parent: QWidget | None = None, title: str | None = None) -> QColor | None`

### 2.3 DocumentPropertiesDialog (`src/atboffice/ui/dialogs/document_properties_dialog.py`)
- **继承体系**：`DocumentPropertiesDialog(QDialog)`
- **5 标签页结构**：
  1. `GeneralTab`: 文件名、文件类型、位置、文件大小、创建时间、修改时间、访问时间。
  2. `SummaryTab`: 标题(Title)、主题(Subject)、作者(Author)、经理(Manager)、公司(Company)、分类(Category)、关键字(Keywords)、备注(Comments)、超链接基址(Hyperlink Base)。
  3. `StatisticsTab`: 创建/修改/最后保存人/修订次数/总编辑时间，以及段落、字数、字符数等统计信息表。
  4. `ContentsTab`: 标题大纲/文档主要内容结构树形列表展示。
  5. `CustomTab`: 自定义属性编辑器，支持名称下拉快捷选择（如 Checked by, Client, Department, Owner 等）、类型选择（文本、日期、数字、是或否）、取值输入、添加/更新/删除操作，以及属性一览表格。
- **模型数据结构**：
  - `DocumentMetadata` dataclass / dict，提供 `to_dict()` 和 `from_dict()`，无缝支持读写。

### 2.4 InAppSaveAsDialog & SecurityOptionsDialog (`src/atboffice/ui/dialogs/in_app_save_as_dialog.py`)
- **InAppSaveAsDialog**：
  - 文件名输入框 (`QLineEdit`)。
  - 保存类型下拉框 (`QComboBox`)。
  - 目录浏览与文件列表视图。
  - 经典“工具(Tools)”下拉菜单，包含“安全选项(Security Options)...”。
  - 保存与取消按钮。
- **SecurityOptionsDialog**：
  - 打开权限密码 (Password to open) 输入框。
  - 修改权限密码 (Password to modify) 输入框。
  - 建议以只读方式打开 (Read-only recommended) 复选框。
  - 确定时若输入了新密码，弹出二次确认密码对话框；一致则保存，不一致则提示错误。

---

## 3. Module & Shell Integration
- 在 `BaseOfficeWindow` 中：
  - 接入 `show_document_properties_dialog()` 方法。
  - 接入 `save_file_as_with_options()`，支持在需要时调起内置另存为与加密对话框。
- 在 `QuireWindow`, `LedgerWindow`, `LecternWindow` 中：
  - 初始化统一挂载 `self.task_pane_dock = TaskPaneDock(self)`。
  - 注册 `getting-started` 和 `new` 通用窗格。
  - 将原有模块特有窗格接入 `TaskPaneDock`（例如 Lectern 的动画窗格）。
  - 在菜单栏 View -> "任务窗格(Task Pane)" (Ctrl+F1) 增加切换动作。
- 在 `ColorPickerPopup` 中：
  - 点击“其他颜色...”时，打开 `HoneycombColorDialog`。

---

## 4. Edge Cases & Robustness
1. **窗格历史回退边界**：当在栈首或栈尾时，后退/前进按钮必须精确禁用；若注销某窗格，栈内对应记录应安全跳过或清理。
2. **多语言与动态刷新**：所有文本均使用 `safe_tr()` 包装，切换语言时触发 `retranslate_ui()` 刷新。
3. **蜂窝调色板坐标与分辨率**：六角形蜂窝渲染使用 `QPainter(Antialiasing)`，支持高 DPI 缩放，点击判断采用欧式距离或多边形包含判断，确保点选命中准确。
4. **加密密码一致性验证**：输入密码后必须弹出确认对话框再次输入验证，防止用户误敲密码导致文件锁死丢失。
5. **元数据读写安全**：若文件未保存（路径为空），常规标签页与统计标签页应安全展示默认信息（如未保存、0 字节），不发生异常崩溃。
