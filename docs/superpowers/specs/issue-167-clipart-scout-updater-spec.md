# Specification: Issue #167 — 补全矢量剪贴画库、Scout 桌面助手部件与后台更新检查器

## 1. Overview & Objectives

本项目为 ATBOffice（Python 3.12+ / PySide6 移植工程）补全原版 `.vibeoffice` 的三大经典体验级辅助系统：
1. **矢量剪贴画选择库 (Clipart Gallery)**：内置 24 种经典矢量剪贴画（商务、科技、自然、符号四维分类检索），支持在 Quire/Lectern/Ledger 文档中双击插入，并支持导出 PNG/SVG。
2. **Scout 桌面伴侣助手 (Assistant Scout)**：1:1 复刻 Office 2003 / VibeOffice 经典猎兔犬 Scout 浮动桌面助手，采用无边框透明图层部件，具备呼吸、眨眼、摇尾、气泡对话交互、拖拽吸附及右键功能菜单。
3. **后台版本检查更新器 (Update Checker)**：基于 GitHub Releases API 的异步多线程后台更新检查模块，不阻塞主 UI 线程，支持静默后台检查与“帮助”菜单手动触发，具备优雅降级与网络容错机制。

---

## 2. Requirements & Parity Analysis

### 2.1 矢量剪贴画库 (`src/atboffice/modules/common/clipart_dialog.py`)
- **对齐原版 `.vibeoffice/public/common/clipart.js`**:
  - 完整收录原版 24 种 64×64 精细矢量图元：
    - **商务 (Business)**: Growth chart (增长图表), Calendar (日历), Money (资金/硬币), Team (团队/用户), Target (目标靶心), Trophy (优胜奖杯).
    - **科技 (Technology)**: Computer (计算机/显示器), Gears (齿轮/设置), Telephone (电话/服务), Light bulb (灵感灯泡), Cloud (云计算/存储), Rocket (火箭发射/成长).
    - **自然 (Nature)**: Leaf (生态树叶), Globe (地球仪/国际), House (建筑房产).
    - **符号 (Symbols)**: Star (五角星/评分), Check mark (完成对勾), Clock (时钟/时间), Puzzle (拼图/策略), Flag (里程碑旗帜), Envelope (信封/邮件), Magnifier (放大镜/搜索), Warning (安全警告).
  - **分类过滤与即时检索**：
    - 支持按分类标签（全部、商务、科技、自然、符号与标志）过滤。
    - 搜索输入框实时匹配中英文名称与关键词 tags。
  - **渲染与插入体验**：
    - 使用 `QSvgRenderer` 高质量栅格化渲染矢量缩略图，高清无锯齿。
    - 列表视图与缩略图卡片网格展示，选中显示高亮边框和名称。
    - 双击或点击“插入”按钮，将剪贴画无缝插入到调用窗口（Quire/Lectern/Ledger）的当前文档/画布光标处。

### 2.2 Scout 桌面伴侣助手 (`src/atboffice/modules/common/assistant_scout.py`)
- **对齐原版 `.vibeoffice/public/common/scout/assistant.js` 与 `scout.js`**:
  - **外观与骨骼绘制**：
    - 经典米格鲁猎兔犬（Beagle）：蓝色狗垫、焦糖色身躯、白口鼻与胸腹、深棕色垂耳、黑色圆鼻头、红色项圈与金色吊牌。
    - 基于 PySide6 `QPainter` 与 `QPainterPath` 高清矢量绘制，动态计算呼吸缩放（Breathing Scale）、眼部眨眼开闭（Blinking）、尾巴摇动角度。
  - **窗口属性与交互**：
    - `Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint`，支持透明无边框背景 (`WA_TranslucentBackground`)。
    - 鼠标左键按住拖拽移动位置，松开记忆坐标到 `Settings`。
    - 单击小狗唤起伴侣气泡菜单；右键弹出快捷菜单（动一动!、搜索命令、ATBOffice 帮助、隐藏助手）。
  - **气泡对话框 (Speech Balloon)**：
    - 经典 Office 助手漫画对话气泡（小狗上方浮现白色圆角矩形气泡与指示尾巴），根据时段问候（早上好/下午好/晚上好）。
    - 常用动作快捷导航：搜索命令 (Alt+Q)、打开帮助 (F1)、表演杂技动画、检查更新。
  - **菜单控制**：
    - 在应用顶部菜单“帮助 (&H)”中增加“显示/隐藏 Office 助手 (&O)”，实现全局显隐切换。

### 2.3 后台更新检查器 (`src/atboffice/core/updater.py`)
- **架构设计**：
  - `UpdateCheckWorker(QThread)`：在独立工作线程中通过 `urllib.request` 访问 GitHub Releases API (`https://api.github.com/repos/aitobox/ATBOffice/releases/latest`)。
  - 支持自定义 API URL 或 Mock 回调，便于离线测试。
  - 超时控制（8秒），捕获 `URLError`, `HTTPError`, `TimeoutError`, `json.JSONDecodeError`，严禁崩溃。
  - 版本号解析：兼容 SemVer（如 `v0.4.0` vs `0.4.1`），准确判断是否有更新。
- **UI 交互**：
  - 手动触发（点击菜单“帮助 -> 检查更新...”）：有更新弹窗显示详细 Changelog 并提供下载链接；若已是最新版则弹窗提示；网络故障则提示检查连接。
  - 自动触发（应用启动后静默延迟检测）：仅在有新版本时优雅提醒，无网络或最新时静默不打扰。

---

## 3. Architecture & Module Structure

```
src/atboffice/
├── core/
│   ├── updater.py                    # UpdateCheckWorker, check_for_updates, UpdateDialog
│   └── ...
├── modules/
│   └── common/
│       ├── clipart_dialog.py         # CLIPART_ITEMS, ClipartDialog, prompt_insert_clipart
│       └── assistant_scout.py        # ScoutWidget, ScoutBalloon, ScoutManager, toggle_assistant
├── ui/
│   └── shell/
│       ├── base_window.py            # 集成 open_clipart_dialog, toggle_assistant, check_updates
│       └── mac_menu.py               # 增加 插入->图片->剪贴画 与 帮助->Office 助手/检查更新 动作项
tests/
└── modules/
    └── common/
        └── test_auxiliary.py         # 单元测试：剪贴画加载/搜索、Scout状态动画、更新器线程与版本对比
```

---

## 4. Internationalization (i18n) & Edge Cases

- **i18n 规范**：所有新增控件、提示、菜单项、对话框标题均使用 `safe_tr()` 包装，提供纯正地道中文和英文。
- **边界与异常防护**：
  1. **剪贴画对话框**：搜索为空时显示友好空状态占位符；窗口尺寸过小时自适应流式网格布局。
  2. **Scout 小狗助手**：屏幕边界碰撞吸附保护（防止拖拽到屏幕可视区域之外）；窗口最小化或无父窗口时安全隐藏；动画定时器在销毁时安全停止。
  3. **后台更新器**：无网络连接、代理拦截、GitHub API 速率限制（403）、版本号包含不同前缀（带或不带 `v`）时均能平稳处理。

---

## 5. Verification Plan

1. **自动化测试**：
   - 编写 `tests/modules/common/test_auxiliary.py`，覆盖：
     - Clipart 数据项完整性、搜索算法、SVG 渲染生成 QPixmap；
     - Scout 助手的显隐状态切换、拖拽坐标持久化、动作动画触发；
     - Updater 版本比较算法（升级/同版本/降级）、离线与异常网络捕获。
2. **回归测试**：
   - 运行全量 `pytest tests/` 确保 100% 通过且无回归。
