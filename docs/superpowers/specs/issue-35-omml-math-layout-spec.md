# Specification: Issue #35 - [Quire] Office Math ML (m:oMath) 数学公式解析与排版

## 1. Overview & Problem Statement
实现 Quire 模块对 Office Math ML (`m:oMath` 与 `m:oMathPara`) 规范数学公式的端到端支持：
1. **数据模型与解析**：将 OOXML 格式的 Office Math XML (`m:oMath` / `m:oMathPara`) 解析为结构化内部公式抽象语法树 (AST)，涵盖分式、上下标、根号、大括号定界符、求和/积分 n-ary 算子、函数名、重音符、上划线下划线、矩阵与方程组。
2. **矢量排版引擎**：实现 `math_layout.py` 计算数学公式各节点包围盒的宽度、高度、上升高度 (`ascent`)、下降高度 (`descent`) 与基线对齐，并支持在 PySide6 画布上矢量绘制分数线、根号折线与顶线、定界符大括号等。
3. **无损存取 (Round-trip)**：与 `docx_reader.py` 与 `docx_writer.py` 深度集成，打开 DOCX 时解析公式，保存时 100% 字节/结构级无损写回标准 OOXML `<m:oMath>` 片段，无数据降级。
4. **排版流水线集成**：在 `portions.py` 中将公式无缝作为行内或块级图元排版，准确参与行高撑开、断行与基线对齐。

---

## 2. Architecture & Data Structures

### 2.1 File Organization
- `src/atboffice/modules/writer/models/omml.py`:
  - Math AST 数据模型：`MathNode`, `MathRun`, `MathFraction`, `MathSup`, `MathSub`, `MathSubSup`, `MathPre`, `MathRadical`, `MathDelimiter`, `MathNary`, `MathFunction`, `MathAccent`, `MathBar`, `MathGroupChar`, `MathLimitLower`, `MathLimitUpper`, `MathMatrix`, `MathEqArray`, `MathBoxNode`, `MathBorderBoxNode`, `MathPhantomNode`.
  - 行内图元模型：`OfficeMathItem(RunItem)`，挂载在 `Paragraph.runs` 中。
  - XML 解析与序列化：`parse_omml(element_or_xml)` 与 `serialize_omml(item)`。
- `src/atboffice/modules/writer/layout/math_layout.py`:
  - 布局盒模型：`MathLayoutBox`（坐标、尺寸、ascent、descent、子盒结构、绘制指令）。
  - 排版度量算法：`layout_math_item(item, base_font_size, font_family)`。
  - 矢量绘制：`paint_math(painter, item, origin_x, baseline_y, zoom)`。
- 集成点：
  - `src/atboffice/modules/writer/io/docx_reader.py`: 在 `_parse_paragraph` 识别 `<m:oMath>` 与 `<m:oMathPara>`。
  - `src/atboffice/modules/writer/io/docx_writer.py`: 在 `_serialize_run_item` 序列化 `OfficeMathItem`。
  - `src/atboffice/modules/writer/layout/portions.py`: 在 `decompose_paragraph_to_portions` 识别 `OfficeMathItem` 并度量宽度/高度。
  - `src/atboffice/modules/writer/views/canvas_view.py`: 在 `_paint_page_content` 绘制公式矢量图元。

### 2.2 Math AST 节点设计
- `MathNode`: 抽象基类。
- `MathRun`: 对应 `m:r`，文本、字符集分类（数字、标识符、运算符）、样式（粗体、斜体、手写体、双线、黑体等）。
- `MathFraction`: 对应 `m:f`，分子 `num`，分母 `den`，类型 `type` (`bar`, `skw`, `lin`, `noBar`)。
- `MathSup` / `MathSub` / `MathSubSup`: 对应 `m:sSup`, `m:sSub`, `m:sSubSup`。
- `MathRadical`: 对应 `m:rad`，底数 `base`，方次 `deg`，隐藏方次 `deg_hide`。
- `MathDelimiter`: 对应 `m:d`，包裹项 `items`，起始符 `beg_chr`，结束符 `end_chr`，分隔符 `sep_chr`，垂直拉伸标志 `grow`。
- `MathNary`: 对应 `m:nary`，算子 `op` (`∫`, `∑` 等)，下限 `sub`，上限 `sup`，被积/求和式 `base`，限位置 `lim_loc` (`undOvr` / `subSup`)。
- `MathFunction`: 对应 `m:func`，函数名 `name`，自变量 `base`。
- `MathAccent` / `MathBar`: 对应 `m:acc`, `m:bar`。
- `MathMatrix`: 对应 `m:m`，包含行列表，每行为单元格公式节点列表。
- `OfficeMathItem(RunItem)`:
  - `t = "omath"`
  - `nodes: list[MathNode]`
  - `raw_xml: str | None`: 原始 XML 字符串缓存，修改时清空，未修改时保障 100% 原始字节保留。
  - `display: bool`: 是否为独立段落公式 (`m:oMathPara`)。
  - `jc: str | None`: 对齐方式。
  - `layout_box: MathLayoutBox | None`: 缓存排版度量结果。

---

## 3. Mathematical Layout & Typography Engine

### 3.1 度量与基线对齐
- **文本与数字**：使用 `compute_font_metrics` 与 `measure_text_width`。
- **分式 (Fraction)**：
  - 分子与分母缩放至 `0.85 * font_size`。
  - 宽度取分子与分母宽度的较大值加上两端边距。
  - 分数线置于基线上方数学轴线（约为 `0.25 * font_size`），分子基线在分数线上方，分母顶在分数线下方。
  - 整体 `ascent` 与 `descent` 围绕分数线垂直对称展开。
- **上下标 (Sub/Sup)**：
  - 上标升高 `0.45 * base.ascent`，缩放至 `0.7 * font_size`。
  - 下标降低 `0.35 * base.descent`，缩放至 `0.7 * font_size`。
  - 总宽度为底数宽度加上标/下标宽度。
- **根式 (Radical)**：
  - 预留根号符号宽度（约 `8-12 pt`），上方绘制水平横线 (`vinculum`)。
  - 若有次数 `deg`，置于根号左上折角内。
- **定界符 (Delimiter)**：
  - 若 `grow=True` 且内部内容高度超过普通单行，大括号/小括号拉伸覆盖整个内部高度。

### 3.2 矢量绘制 (Vector Drawing)
- 使用 `QPainter` 矢量路径：
  - 分数线：`painter.drawLine(x1, y, x2, y)`。
  - 根号：`QPainterPath` 依次 `moveTo` -> `lineTo`（起点、下折尖角、上折顶点、平引横线）。
  - 括号定界符：根据高度采用绘制或拉伸弧线。
  - 文本与符号：`painter.drawText(...)`。

---

## 4. Verification Plan
1. 单元测试 `tests/unit/writer/test_omml.py`：
   - 测试 XML 字符串到 AST 的解析（分式、根式、上下标、积分、矩阵、定界符）。
   - 测试 AST 到 OOXML `<m:oMath>` / `<m:oMathPara>` 的序列化。
   - 测试排版算法：分式高度、根号宽度、基线计算与上下标偏移。
   - 测试 DOCX 读写 round-trip：包含公式的文档写入并重新读取，内容与公式结构保持一致。
2. 现有 Quire 整体回归：
   - 运行全部 93 个现有单元测试，确保 0 regression。
