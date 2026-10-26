# Specification: Issue #37 [Quire] 自动化排版断行回归与真实 DOCX 语料库无损验证

## 1. 概述与目标

### 1.1 背景与目标
在 Epic #22（ATBOffice Quire 文字处理与排版引擎移植）中，前序子任务（#23 ~ #36）已分别实现了 Quire 的 DOM 树模型、行分段断行（Portions）、分页流排版（Pagination）、DOCX 核心读写、画布光标与编辑、表格与跨行跨列排版、交互式标尺、字段与目录、图文环绕、格式对话框、审阅修订与批注、Markdown/RTF 互转、OMML 公式排版以及邮件合并。

作为 Epic #22 的终审与收官任务（Step 15 of 15），本任务建立 Quire 模块的**三层金字塔自动化回归测试矩阵**（Three-Tier Regression Pyramid Matrix），涵盖：
1. **Tier 1 (底层 - 纯算法单元测试)**：整合行分段排版（Portions）、行高测算、间距折叠、东亚行网格（East Asian Line Grid）与标号格式化等无 GUI 算法回归。
2. **Tier 2 (中层 - PySide6 `pytest-qt` 画布交互测试)**：页面视口滚动、光标移动（Arrow/Home/End/DocStart/DocEnd）、鼠标选区与划选拖拽、键盘输入退格与段落拆分合并、水平/垂直标尺滑块拖拽及制表位操作。
3. **Tier 3 (顶层 - 真实 DOCX 语料库与无损 Roundtrip 验证)**：加载本地 `.vibeoffice` 真实测试语料库（`linecases.docx`、`linegrid.docx` 及典型多页 Word 文档），验证复杂排版文件打开后分页总数与 Word 记录的页数差异为 0，比对各行间距与基准，验证保存重载机制下未修改部件字节级一致性（SHA-256 100% 匹配）。

---

## 2. 三层金字塔架构设计

```
                    ▲
                   / \
                  /   \
                 /     \
                / Tier 3 \   真实 DOCX 语料库与无损验证
               /───────────\  (Corpus Page Count diff=0, SHA-256 Byte-for-Byte Lossless)
              /   Tier 2    \  PySide6 pytest-qt 画布与视口交互
             /───────────────\ (Caret, Mouse Select, Typing, Rulers Drag)
            /     Tier 1      \ 纯算法单测矩阵
           /───────────────────\ (Portions, Line Grid, Spacing Collapse, Section Breaks)
```

### 2.1 Tier 1: 算法回归矩阵 (`tests/unit/writer/test_layout_regression.py`)
- **Portions 算法**：
  - 测试混合文本、制表符（Tabs）、分页/换行符（Breaks）、Wingdings 符号（Symbols）及嵌入式图片的准确分段。
  - 测算行高（Line Heights）：Exact 模式、Auto 倍数模式（1.0, 1.15, 1.5, 2.0）、大号字首字、行内图形行高撑开。
- **东亚行网格 (East Asian Line Grid)**：
  - 测试 15.6pt / 18pt 行网格跨距对齐与字符居中对齐。
  - 测试中英文混排、不同字号（10.5pt, 12pt, 14pt, 16pt, 22pt, 28pt）在网格上的行距阶梯与吸附（与 `.vibeoffice/tests/from-issues/11/word.json` 基准严格对齐）。
- **间距折叠与排版控制**：
  - 段前（before）、段后（after）间距与行距折叠。
  - `pageBreakBefore`、`keepWithNext` 与 `keepLines` 孤行/寡行控制。
  - 分节符（`nextPage`、`oddPage`、`evenPage`、`continuous`）与奇偶空白页填充。
- **动态字段与标号格式化**：
  - `format_number`: decimal, upperRoman, lowerRoman, upperLetter, lowerLetter, decimalZero, ordinal。

### 2.2 Tier 2: GUI 视口与交互测试 (`tests/gui/test_writer_pyramid_interactions.py`)
- **视口与光标导航**：
  - 光标移动：`move_left`, `move_right`, `move_up`, `move_down`（保持 `preferred_x`）、`move_line_start`, `move_line_end`, `move_doc_start`, `move_doc_end`。
  - 选区扩展：Shift+方向键、鼠标点击、双击选词、三击选段、全选（Ctrl+A / Cmd+A）。
- **实时文本编辑与段落演进**：
  - 字符输入（`insert_text`）、删除（Backspace / Delete / 选区清除）。
  - 回车分段（`insert_paragraph_break`）以及跨段回退合并。
- **标尺与视口控件交互**：
  - 水平标尺拖拽：首行缩进（First Line Indent）、左缩进（Left Indent）、右缩进（Right Indent）。
  - 制表位管理：点击标尺添加制表位、拖拽移动制表位、向下拖拽移除制表位。
  - 垂直标尺拖拽：页顶边距与页底边距拖拽调整并触发布局重算。
  - 视口缩放与坐标转换：50% ~ 400% 缩放比例限制与画布/文档点精确映射。

### 2.3 Tier 3: 真实语料库与无损 Roundtrip (`tests/unit/writer/test_quire_corpus_roundtrip.py`)
- **真实语料库测试**：
  - 语料库 1：`.vibeoffice/tests/quire/lines/linecases.docx`（31 个段落，覆盖全部行高与图形案例，分页验证 = 1 页）。
  - 语料库 2：`.vibeoffice/tests/from-issues/11/linegrid.docx`（91 个段落，覆盖 15.6pt/18pt 网格与中英混排，分页验证 = 19 页，各页起始段与 `word.json` 一致）。
  - 语料库 3：带 `docProps/app.xml` `<Pages>` 计数的综合 Word 文档，断言 Quire 计算的总页数与 Word 记录的 `<Pages>` 差异为 0（`abs(quire_pages - word_pages) == 0`）。
- **无损保存与重载 (Lossless Preservation)**：
  - 读取包含宏（VBA）、自定义 XML、图片资源、主题（Theme）、编号（Numbering）及复杂样式的 DOCX/DOCM 包。
  - 修改文档部分文字并执行保存。
  - 验证未修改部件（`word/vbaProject.bin`, `word/theme/theme1.xml`, `word/media/*`, `customXml/*` 等）的 SHA-256 哈希值 100% 保持不变。
  - 重新加载保存后的文件，断言文档 DOM 树结构、段落与格式完全正确。

---

## 3. 验收标准与验证方案
1. 单元测试全部通过：`pytest tests/unit/writer/ tests/gui/test_writer* tests/gui/test_ruler.py -v`。
2. 运行总测试套件：`pytest tests/ -v -k "writer or quire"` 达成 100% 通过。
3. 语料库页数与 Word 差异为 0，无损保留哈希 100% 匹配。
