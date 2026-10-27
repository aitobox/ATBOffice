# Specification: Issue #53 [Lectern] 自动化幻灯片渲染比对回归与真实 PPTX 语料库无损验证

## 1. 概述与目标

### 1.1 背景与目标
在 Epic #38（ATBOffice Lectern PowerPoint 2003 演示文稿与放映动效引擎移植）中，前序子任务（#39 ~ #52）已分别实现了 Lectern 的核心演示文稿对象模型、自由交互画布与几何手柄、原位文本编辑与自适应字号（AutoFit）、PPTX 核心读写、三栏经典工作台视口、全屏放映与 58 种切页转场、IntelliArt 26 种智能图示、DrawingML 矢量图表与数据表、50+ 对象自定义动画、双屏演讲者控制台、经典属性对话框集、幻灯片浏览与母版视图、多媒体音视频占位海报以及批注作者图谱管理。

作为 Epic #38 的终审与收官任务（Step 15 of 15），本任务建立 Lectern 演示文稿模块的**三层金字塔自动化回归测试矩阵**（Three-Tier Regression Pyramid Matrix），涵盖：
1. **Tier 1 (底层 - 纯逻辑模型与算法单元测试)**：整合母版占位符继承（Master Placeholders）、26 种 IntelliArt 拓扑几何计算、文本自适应缩放（AutoFit）、58 种切页转场算法、DrawingML 图表渲染以及 PresentationML ECMA-376 模式排序（Schema Ordering）等无 GUI 算法回归。
2. **Tier 2 (中层 - PySide6 `pytest-qt` 画布交互与视口测试)**：基于 `pytest-qt` 测试画布图形变换手柄移动缩放、原位文本框编辑与双向同步、幻灯片缩略图大纲导航与按键切换、全屏放映转场触发、视口缩放平移以及 i18n 无障碍重翻译。
3. **Tier 3 (顶层 - 真实 PPTX 语料库与无损 Roundtrip 矩阵)**：参考 `.vibeoffice/tests/lectern/corpus.js` 与 `.vibeoffice/tests/lectern/loss-audit.py`，构建真实与高保真复杂 PPTX 语料库，执行“打开 ➔ 修改单一幻灯片 ➔ 保存 ➔ 重新读取”测试，断言未修改部件（未编辑幻灯片、母版、版式、主题、媒体文件、VBA宏等）SHA-256 二进制哈希 100% 保持一致，并对 `.vibeoffice` 定义的 28 种关键特性执行零降级（Zero Feature Loss）审计。

---

## 2. 三层金字塔架构设计

```
                    ▲
                   / \
                  /   \
                 /     \
                / Tier 3 \   真实 PPTX 语料库与无损 Roundtrip 矩阵
               /───────────\  (Corpus Loss-Audit, SHA-256 Byte-for-Byte Lossless)
              /   Tier 2    \  PySide6 pytest-qt 画布与视口交互矩阵
             /───────────────\ (Transform Handles, Inplace Text, Slideshow, Zoom)
            /     Tier 1      \ 纯逻辑模型树与排版渲染单测矩阵
           /───────────────────\ (Master Placeholders, 26 IntelliArt, AutoFit, Schema Order)
```

### 2.1 Tier 1: 纯逻辑模型树与排版渲染单测矩阵 (`tests/unit/presentation/`)
- **模型树与占位符继承** (`test_pmodel.py`):
  - 幻灯片（Slide）继承自母版（Master）与版式（Layout）的占位符（Title、Body、Date/Time、Footer、SlideNumber）。
  - 15 套经典主题色彩（Design Themes）与 21 种版式结构映射。
- **IntelliArt 26 种拓扑排版** (`test_smartart.py`):
  - 涵盖 Process、Hierarchy、Cycle、Relationship、Matrix、Pyramid 6 大家族全部 26 种拓扑结构。
  - 节点增删、层级升降与几何图元计算。
- **文本自适应与字号阶梯** (`test_text_autofit.py`):
  - Text AutoFit: None、shrink（字号自适应压缩）与 resize（形状自适应扩展）。
- **切页转场与动画时序** (`test_transitions.py`, `tests/gui/test_animations.py`):
  - 58 种切页转场（Fade, Push, Wipe, Split, Box, Diamond 等）参数与时序。
- **DrawingML 矢量图表** (`test_chart_draw.py`):
  - 柱状图、折线图、饼图、面积图、散点图及内置数据表双向联动。
- **批注与作者图谱** (`test_comments.py`):
  - 批注卡片、作者颜色、回复链与 ECMA-376 `comments.xml` 往返。
- **媒体与海报保护** (`test_media_preserve.py`):
  - 音频、视频占位图、媒体控制参数与原生媒体流无损存储。
- **ECMA-376 PresentationML 严格模式排序** (`test_pptx_io.py`):
  - 保证生成的 `p:sld`、`p:sp`、`p:pic` 等元素标签严格遵循 `SCHEMA_ORDERS` 规范。

### 2.2 Tier 2: PySide6 `pytest-qt` 画布交互与视口测试 (`tests/gui/test_lectern_pyramid_interactions.py`)
- **图形变换手柄交互 (Transform Handles)**:
  - 鼠标拖拽 8 个方向控制手柄（TopLeft, TopRight, BottomRight 等）进行缩放。
  - 拖拽旋转手柄执行几何旋转。
  - Shift 按键锁定等比例缩放（Aspect Ratio Constraint）。
- **原位文本框富文本编辑 (In-Place Text Editing)**:
  - 双击形状或文本框激活原位编辑器。
  - 实时键入字符、Backspace 消除、Enter 换行。
  - 失焦或按 Escape 提交编辑并更新底层模型文本树。
- **三栏经典工作台视口导航 (Three-Pane Navigation)**:
  - 缩略图列表点击与键盘上下方向键、PageUp/PageDown 切换当前幻灯片。
  - 大纲编辑器（Outline Editor）与画布当前选中图元双向联动。
- **全屏放映与转场触发 (Slideshow & Transitions)**:
  - F5 / 放映按钮触发 `SlideShowView`。
  - 切换上一页/下一页幻灯片并触发切页转场渲染。
- **视口缩放与平移 (Zoom & Panning)**:
  - 缩放比例限制（25% ~ 400% 钳位）。
  - 画布坐标与视口像素点映射。
- **无障碍与国际化重翻译 (Accessibility & i18n)**:
  - 100% 控件文字通过 `tr()`/`safe_tr()` 国际化，调用 `retranslate_ui()` 验证工具提示与标签更新。

### 2.3 Tier 3: 真实 PPTX 语料库与无损 Roundtrip 矩阵 (`tests/unit/presentation/test_lectern_corpus_roundtrip.py`)
- **真实语料库 / 复杂多媒体演示文稿加载**:
  - 构建真实复杂多页演示文稿（多张幻灯片、不同版式、IntelliArt、Chart、图片、表格、批注、音频视频、VBA 宏）。
  - 验证打开读取速度、对象模型完整解析（Shapes、Runs、Tables、Comments、Transitions）。
- **无损增量保存与哈希一致性 (Byte-for-Byte Lossless Roundtrip)**:
  - 修改 1 张幻灯片上的文本或形状。
  - 执行 `write_pptx` 并重新读取。
  - 验证未编辑幻灯片（如 `ppt/slides/slide1.xml`, `ppt/slides/slide3.xml`）、母版（`ppt/slideMasters/*`）、版式（`ppt/slideLayouts/*`）、主题（`ppt/theme/theme1.xml`）、媒体二进制流（`ppt/media/*`）及 VBA 项目（`ppt/vbaProject.bin`）的 SHA-256 二进制哈希 100% 严格一致。
- **语料库特性零丢失审计 (Loss-Audit Regression Benchmark)**:
  - 移植 `.vibeoffice/tests/lectern/loss-audit.py` 中的 `FEATURES` 特征提取字典（28 种 ECMA-376 特性：comments, embedded OLE, media, VBA, animations, transitions, hyperlinks, 3D, SmartArt, layouts, masters 等）。
  - 对比原文件与保存后文件的特性统计，断言 `decks_lost_all == 0` 且 `decks_lost_some == 0`。
- **文本词汇与图元拓扑完整性**:
  - 对比重载前后各幻灯片的图元总数、文本内容（Words / Characters），确保零缺失。

---

## 3. 验收标准与验证方案

1. **单元测试矩阵达成**:
   - `tests/unit/presentation/test_lectern_corpus_roundtrip.py` 包含多页复杂 PPTX 无损 roundtrip 测试与 loss-audit 审计。
   - `tests/gui/test_lectern_pyramid_interactions.py` 包含基于 `pytest-qt` 的画布交互、文本原位编辑、按键导航与缩放。
2. **测试执行指令**:
   ```bash
   PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/ tests/gui/test_lectern* -v
   ```
   达成 100% 测试通过。
3. **全模块综合测试**:
   ```bash
   PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v -k "presentation or lectern" --durations=10
   ```
   全部测试零回归、零警告、毫秒级响应。
