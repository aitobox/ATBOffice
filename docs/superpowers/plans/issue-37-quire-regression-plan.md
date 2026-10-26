# Implementation Plan: Issue #37 [Quire] 自动化排版断行回归与真实 DOCX 语料库无损验证

## 任务目标
构建 Quire 模块三层金字塔自动化回归测试矩阵，覆盖纯算法单测、PySide6 `pytest-qt` 画布交互，以及真实 DOCX 语料库与无损 Roundtrip 验证，确保零排版退化并达成 100% 测试通过。

---

## 阶段划分与步骤

### Task 1: 实现 Tier 1 纯算法回归测试矩阵 (`tests/unit/writer/test_layout_regression.py`)
- **文件**: `tests/unit/writer/test_layout_regression.py`
- **内容**:
  1. 行分段（Portions）算法测试：混合样式文本、Tabs、换行符、分页符、符号与行内图形。
  2. 行高测算回归：Exact、Auto 模式、多倍行距（1.0, 1.15, 1.5, 2.0）、段前段后间距折叠。
  3. 东亚行网格（Line Grid）测算：15.6pt / 18pt 网格对齐、中英文混排网格阶梯与吸附。
  4. 分页控制测试：`pageBreakBefore`、`keepWithNext`、`keepLines` 孤行寡行控制。
  5. 分节符测试：`nextPage`、`oddPage`、`evenPage`、`continuous` 与空白页填充。
  6. 编号与字段格式化：`format_number` 多种进制格式化覆盖。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_layout_regression.py -v`

### Task 2: 实现 Tier 2 PySide6 `pytest-qt` 画布与视口交互测试 (`tests/gui/test_writer_pyramid_interactions.py`)
- **文件**: `tests/gui/test_writer_pyramid_interactions.py`
- **内容**:
  1. 视口与光标导航：光标移动（ArrowLeft/Right/Up/Down 带 `preferred_x` 记忆、Home/End、DocStart/DocEnd）。
  2. 选区与拖拽：Shift+方向键扩展选区、鼠标拖拽划选、双击选词、三击选段、Ctrl+A 全选。
  3. 实时交互编辑：字符连续键入、回车分段与段落属性继承、Backspace/Delete 跨段合并删除。
  4. 标尺控件交互：水平标尺首行/左/右缩进滑块拖拽与模型联动、制表位增删改、垂直标尺页边距拖拽调整。
  5. 画布缩放与重绘：50% ~ 400% 缩放边界与缩放后坐标转换映射。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_writer_pyramid_interactions.py -v`

### Task 3: 实现 Tier 3 真实语料库与无损 Roundtrip 验证 (`tests/unit/writer/test_quire_corpus_roundtrip.py`)
- **文件**: `tests/unit/writer/test_quire_corpus_roundtrip.py`
- **内容**:
  1. 真实语料库加载：`.vibeoffice/tests/quire/lines/linecases.docx`（验证 31 个段落加载，分页总数 = 1）。
  2. 真实语料库加载：`.vibeoffice/tests/from-issues/11/linegrid.docx`（验证 91 个段落加载，分页总数 = 19，且各页起始段与 `word.json` 一致）。
  3. Word 记录页数无差异验证：加载带 `docProps/app.xml` `<Pages>` 计数的真实或仿真 Word 文档，断言计算页数与 Word 记录页数差异为 0。
  4. 无损保存 (Lossless Roundtrip)：加载包含未识别部件、VBA 宏工程（`vbaProject.bin`）、主题（`theme1.xml`）、图片等的包，修改文字后执行保存，验证未修改部件的 SHA-256 哈希值 100% 保持一致。
  5. 重载正确性：重新读取保存后的文档，验证文本修改生效且原有复杂样式及分节完全无损。
- **验证**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/test_quire_corpus_roundtrip.py -v`

### Task 4: 运行全量回归验证与代码风格检查
- **命令**:
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v -k "writer or quire" --durations=10`
  - `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/writer/ tests/gui/test_writer* tests/gui/test_ruler.py -v`
- **指标**: 0 failures, 0 errors, 100% 通过。

### Task 5: 状态流转与交付
- 更新状态到 `reviewing`，进入 `atb-github-code-reviewer`，随后 `atb-github-pr-monitor` 创建 PR，最终 `atb-github-pr-merge` 合并到 main。
