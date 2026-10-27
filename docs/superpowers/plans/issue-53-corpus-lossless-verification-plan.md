# Implementation Plan: Issue #53 [Lectern] 自动化幻灯片渲染比对回归与真实 PPTX 语料库无损验证

## 任务目标
构建 Lectern 演示文稿模块三层金字塔自动化回归测试矩阵，覆盖纯逻辑模型树与排版单测、PySide6 `pytest-qt` 画布交互，以及真实 PPTX 语料库与无损 Roundtrip 验证，实现零排版与零特性退化，达成 100% 测试通过。

---

## 阶段划分与步骤

### Task 1: 审查与整合 Tier 1 纯逻辑模型树与排版渲染单测矩阵 (`tests/unit/presentation/`)
- **文件**: `tests/unit/presentation/` 既有单测文件与验证
- **内容**:
  1. 母版占位符继承与版式：`test_pmodel.py`。
  2. 26 种 IntelliArt 拓扑几何布局：`test_smartart.py`。
  3. 文本自适应字号缩放：`test_text_autofit.py`。
  4. 58 种切页转场与放映动效：`test_transitions.py`。
  5. DrawingML 图表与数据表：`test_chart_draw.py`。
  6. 批注与作者图谱：`test_comments.py`。
  7. 多媒体音视频无损占位：`test_media_preserve.py`。
  8. ECMA-376 PresentationML 模式排序（`SCHEMA_ORDERS`）：`test_pptx_io.py`。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/ -v`

### Task 2: 实现 Tier 2 PySide6 `pytest-qt` 画布与视口交互测试 (`tests/gui/test_lectern_pyramid_interactions.py`)
- **文件**: `tests/gui/test_lectern_pyramid_interactions.py`
- **内容**:
  1. **图形变换手柄交互 (Transform Handles)**: 鼠标拖拽 8 个方向控制手柄（TopLeft, TopRight, BottomRight 等）缩放、拖拽中心位移、Shift 约束等比例缩放。
  2. **原位文本框富文本编辑 (In-Place Text Editing)**: 双击激活原位编辑器、实时输入文本、退格删除、Enter 换行、提交并同步到 Slide 模型。
  3. **三栏工作台视口导航 (Three-Pane Navigation)**: 缩略图列表与大纲编辑器的键盘方向键/PageUp/PageDown 切换当前幻灯片、状态栏幻灯片索引更新。
  4. **全屏放映与转场触发 (Slideshow & Transitions)**: 从工作台启动全屏放映、触发前后页切页转场动效、退出放映返回编辑状态。
  5. **视口缩放与平移 (Zoom & Panning)**: 25% ~ 400% 钳位缩放比例测试、画布与视口坐标转换映射。
  6. **无障碍与国际化重翻译 (Accessibility & i18n)**: 验证 `LecternWorkspace` 及子视图的 `retranslate_ui()`。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_lectern_pyramid_interactions.py -v`

### Task 3: 实现 Tier 3 真实 PPTX 语料库与无损 Roundtrip 矩阵 (`tests/unit/presentation/test_lectern_corpus_roundtrip.py`)
- **文件**: `tests/unit/presentation/test_lectern_corpus_roundtrip.py`
- **内容**:
  1. **复杂演示文稿语料库加载**: 构建包含母版、版式、主题、多幻灯片、图片媒体、SmartArt 图示、矢量图表、批注、VBA 宏与自定义 XML 的高保真真实结构演示文稿。
  2. **无损保存与 SHA-256 二进制一致性 (Byte-for-Byte Lossless Roundtrip)**:
     - 修改指定幻灯片（如幻灯片 2 标题与形状）。
     - 保存为新 PPTX 并用 `SourcePackage` 逐部件校验：未修改幻灯片（slide1.xml, slide3.xml）、母版（slideMaster1.xml）、版式（slideLayout*.xml）、主题（theme1.xml）、媒体文件（image1.png）与 VBA 宏（vbaProject.bin）的 SHA-256 哈希值 100% 相同。
  3. **特性零丢失审计 (Loss-Audit Regression Benchmark)**:
     - 移植 `.vibeoffice/tests/lectern/loss-audit.py` 的 28 种 ECMA-376 特征检测器（comments, embedded OLE, media, VBA, animations, transitions, hyperlinks, 3D, SmartArt, layouts, masters 等）。
     - 验证保存前后特征数量不减少，`decks_lost_all == 0`。
  4. **重载与拓扑完整性**:
     - 重新加载保存后的 PPTX，断言形状数量、文本词汇数（Words / Characters）与幻灯片树结构完全正确无缺失。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/test_lectern_corpus_roundtrip.py -v`

### Task 4: 运行全量 Lectern 回归与质量门禁验证
- **命令**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/presentation/ tests/gui/test_lectern* -v`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v -k "presentation or lectern" --durations=10`
- **指标**: 100% 测试通过，无破坏性改动。

### Task 5: 自动流水线流转 (Review -> PR -> Merge)
- 转换状态为 `reviewing`，触发 `atb-github-code-reviewer`。
- 自动完成代码审查并通过后推进至 `pr_ready`。
- 触发 `atb-github-pr-monitor` 创建并推送 PR。
- 触发 `atb-github-pr-merge` 监控 CI 并完成 Squash Merge 至 main。
