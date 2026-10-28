# ATBOffice 启动与应用使用指南 (Application Launch Guide)

本文档介绍 **ATBOffice** 桌面办公套件的入口体系、专属 GUI 模块启动命令、文件关联分发规则与核心窗口生命周期机制。

---

## 1. 环境准备 (Environment Setup)

在运行 ATBOffice 之前，请确保已激活专用的 Conda 开发环境：

```bash
# 激活开发环境
conda activate ATBOffice

# 或者从仓库根目录使用 conda run 统一执行
PYTHONPATH=src conda run -n ATBOffice python -m atboffice
```

若已通过 `pip install -e .` 完成了可编辑模式安装，则可以直接使用注册在 `pyproject.toml` 中的控制台命令。

---

## 2. 启动命令参考 (Launch Commands)

ATBOffice 支持 **统一启动中心**、**专属子命令**、**独立别名脚本** 以及 **文件路径自动嗅探** 四种使用方式。

### 2.1 启动统一启动中心 (Start Center)
未传入任何参数时，应用默认展示类似 LibreOffice / VibeOffice 的 **Start Center（启动中心）** 欢迎面板：

```bash
# 方式一：Python 模块调用（推荐开发调试使用）
PYTHONPATH=src conda run -n ATBOffice python -m atboffice

# 方式二：已安装环境直接运行
atboffice
```

---

### 2.2 启动各模块独立专属 GUI

每个模块均拥有专用的主窗口、原汁原味的 Office 2003 Luna 皮肤以及专属的菜单栏与工具栏系统：

| 模块名称 | 功能定位 | 命令行子命令 | 便捷脚本别名 |
|---|---|---|---|
| **Quire** | 文字处理（Word 2003 移植） | `python -m atboffice quire [文件路径]` | `atboffice-quire [文件路径]` |
| **Ledger** | 电子表格（Excel 2003 移植） | `python -m atboffice ledger [文件路径]` | `atboffice-ledger [文件路径]` |
| **Lectern** | 演示文稿（PowerPoint 2003 移植） | `python -m atboffice lectern [文件路径]` | `atboffice-lectern [文件路径]` |

#### 快速启动示例：

```bash
# 启动 Quire 文字处理（新建空白文档）
PYTHONPATH=src conda run -n ATBOffice python -m atboffice quire

# 启动 Quire 并打开现有文档
PYTHONPATH=src conda run -n ATBOffice python -m atboffice quire path/to/document.docx

# 启动 Ledger 电子表格（新建空白工作簿）
PYTHONPATH=src conda run -n ATBOffice python -m atboffice ledger

# 启动 Ledger 并打开现有表格或 CSV
PYTHONPATH=src conda run -n ATBOffice python -m atboffice ledger path/to/data.xlsx

# 启动 Lectern 演示文稿（新建空白幻灯片）
PYTHONPATH=src conda run -n ATBOffice python -m atboffice lectern

# 启动 Lectern 并打开演示文稿
PYTHONPATH=src conda run -n ATBOffice python -m atboffice lectern path/to/slides.pptx
```

---

### 2.3 依据文件扩展名智能分发 (Smart Extension Dispatching)

直接向命令行传入文件路径时，ATBOffice 的路由器会自动分析文件扩展名并拉起对应的专属窗口，无需手动指定子命令：

```bash
# 自动通过 Quire 打开
PYTHONPATH=src conda run -n ATBOffice python -m atboffice report.docx

# 自动通过 Ledger 打开
PYTHONPATH=src conda run -n ATBOffice python -m atboffice budget.xlsx
PYTHONPATH=src conda run -n ATBOffice python -m atboffice metrics.csv

# 自动通过 Lectern 打开
PYTHONPATH=src conda run -n ATBOffice python -m atboffice presentation.pptx
```

#### 扩展名映射规则表：

| 文件扩展名 | 目标专属窗口 |
|---|---|
| `.docx`, `.doc`, `.odt`, `.rtf`, `.txt` | **QuireWindow**（文字处理） |
| `.xlsx`, `.xls`, `.csv`, `.tsv`, `.ods` | **LedgerWindow**（电子表格） |
| `.pptx`, `.ppt`, `.odp` | **LecternWindow**（演示文稿） |
| 其他未知格式 | 默认安全回退或弹窗提示 |

---

### 2.4 CLI 辅助选项 (Flags)

```bash
# 查看帮助信息与用法示例
PYTHONPATH=src conda run -n ATBOffice python -m atboffice --help

# 查看应用版本号
PYTHONPATH=src conda run -n ATBOffice python -m atboffice --version

# 强制打开启动中心
PYTHONPATH=src conda run -n ATBOffice python -m atboffice --start-center
```

---

## 3. 核心界面交互与特性 (Key UI Features)

### 3.1 启动中心 (Start Center) 交互
- **左侧导航栏**：
  - **快速新建**：点击蓝色 Word 图标（Quire）、绿色 Excel 图标（Ledger）或橙色 PPT 图标（Lectern），立即打开对应空白文档，启动中心自动隐藏；
  - **打开现有文件**：点击“打开文件…”调用系统原生文件选择对话框；
  - **视图切换**：在“最近使用的文档”与“模板库”之间切换；
  - **偏好设置与关于**：快速查看版本信息及主题风格配置。
- **右侧工作区**：
  - **最近文档 (Recent Files)**：从 `~/.atboffice/recent_files.json` 读取最近打开过的文档列表，卡片展示应用类型徽标、文件名称、路径、时间戳与文件大小；支持一键清空和单项移除（×）；若点击已丢失的物理文件，会弹窗确认并自动清理失效项；
  - **模板库 (Templates)**：按文字、表格、演示分类展示丰富的内置模板卡片，点击即可基于模板创建新文档。
- **全屏文件拖放 (Drag & Drop)**：
  - 支持将任意办公文档直接从系统资源管理器或 Finder 拖入 Start Center 窗口；松开鼠标后自动识别类型并在专属窗口中打开，同时自动写入最近文档历史。

### 3.2 窗口生命周期与自动唤回机制 (Lifecycle & Resurrection)
- **多窗口共存**：支持同时打开多个 Quire、Ledger、Lectern 独立窗口，实现并排对照编辑。
- **Start Center 自动唤回**：
  - 从 Start Center 打开文档时，Start Center 自动隐藏/后置；
  - 当用户逐一关闭打开的文档窗口时，系统自动跟踪活跃窗口数量；
  - **当最后一个文档窗口被关闭时，Start Center 自动重新显示、置顶并获取焦点 (`show()`, `raise_()`, `activateWindow()`)**，避免无窗口挂起。
- **数据安全与退出拦截**：
  - 单个窗口包含修改时，关闭红叉会触发保存询问对话框（保存 / 不保存 / 取消）；
  - 全局退出（macOS `Cmd+Q` 或 Exit 菜单）时，`WindowManager` 依次询问各个未保存窗口；如果用户在任一窗口点击“取消”，**整个退出操作立即原子性终止**，保护工作现场。

---

## 4. 自动化测试与质量保障 (Verification)

工程内置了全量自动化单元与端到端测试，验证入口与生命周期行为：

```bash
# 运行全部 806+ 项测试套件
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/

# 运行启动器专有 E2E 生命周期回归测试
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_launcher_e2e.py -v

# 运行启动中心 UI 交互与拖拽测试
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_start_center_ui.py -v

# 运行 CLI 路由器解析测试
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/test_cli_router.py -v

# 代码规范与静态检查
PYTHONPATH=src conda run -n ATBOffice ruff check src/ tests/
```
