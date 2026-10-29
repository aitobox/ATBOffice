# Specification: Issue #108 - [Phase 2] DOCX 读取器全量扩充 (编号列表、复杂表格跨行跨列与图形环绕)

## Overview & Background
ATBOffice 的 WordprocessingML (DOCX) 读取器 `src/atboffice/modules/writer/io/docx_reader.py` 目前仅支持基础段落、基础表格单元格和简单文本 Run，缺少与原版 `.vibeoffice/public/quire/js/docx-read.js`（1,876 行）对齐的关键核心功能：
1. **多级编号列表 (`word/numbering.xml`)**：解析抽象编号定义 (`abstractNum`)、实例编号 (`num`)、9 个层级的编号格式 (`numFmt`)、编号文本模式 (`lvlText`)、起始值 (`start`)、级别重写 (`lvlOverride`)，并在文档模型中建立 `doc.numbering` 索引树。
2. **复杂表格跨行跨列与样式布局**：完整解析水平合并 (`w:gridSpan`)、垂直合并 (`w:vMerge` restart/continue)、行高规则 (`w:trHeight` exact/atLeast/auto)、单元格边距 (`w:tcMar`) 与表格级边距 (`w:tblCellMar`)、表格与单元格边框 (`tblBorders`, `tcBorders`)。
3. **DrawingML 矢量绘图与图片环绕 (Inline / Anchor)**：全面解析 `w:drawing` 下的 `wp:inline` 和 `wp:anchor`，转换 EMU 尺寸单位，解析浮动位置 (`PositionH`, `PositionV`)、文字环绕模式 (`WrapMode`: square, tight, through, topBottom, behind, inFront)、Z-Index、裁剪 (`srcRect`) 与旋转度数，并支持旧版 VML (`w:pict`) 图片嵌入。
4. **结构元素与批注/脚注/尾注支持**：解析书签 (`bookmarkStart`/`bookmarkEnd`) 索引树、节属性 (`w:sectPr`) 纸张方向/边距/分栏 (`cols`)、页眉页脚与脚注 (`word/footnotes.xml`)、尾注 (`word/endnotes.xml`)。

---

## Architecture & Data Contracts

### 1. Document Model Enhancements (`src/atboffice/modules/writer/models/`)
- `NoteRefItem(RunItem)`: 结构化存储脚注与尾注引用标记 (`kind: "fn" | "en"`, `note_id: str`).
- `CellProperties`: 扩展 `tc_mar: dict[str, float]` (top, bottom, left, right in points).
- `TableProperties`: 扩展 `tbl_cell_mar: dict[str, float]`, `borders: dict[str, BorderProperties]`.
- `Document`: 完善 `numbering: dict[str, Any] = {"abs": {}, "nums": {}}`, `fn: dict[str, Story]`, `en: dict[str, Story]`.

### 2. Numbering Resolution Engine (`DocxReader._parse_numbering`)
- 加载 `word/numbering.xml` 及其 relationships。
- 解析每个 `<w:abstractNum>`：
  - `id`: abstractNumId
  - `multi`: multiLevelType ("singleLevel", "multilevel", "hybridMultilevel")
  - `levels`: list of 9 level definitions (`lvl`), 每个级别包含：
    - `ilvl`: 层级索引 (0-8)
    - `start`: 初始编号 (int, 默认 1)
    - `fmt`: 格式化类型 (`decimal`, `bullet`, `lowerLetter`, `upperLetter`, `lowerRoman`, `upperRoman`, `chineseCountingThousand` 等)
    - `text`: 模板字符串 (如 `%1.`, `%1.%2`, ``, `(%1)`)
    - `jc`: 对齐方式 (`left`, `center`, `right`)
    - `suff`: 后缀符 (`tab`, `space`, `nothing`)
    - `ind`: 缩进 (`left`, `hanging`, `first_line`)
    - `r_pr`: 字体、字号、颜色等
    - `is_lgl`: 是否使用法律编号
    - `restart`: 重置编号层级
- 解析每个 `<w:num>`：
  - `id`: numId
  - `abs`: 绑定的 abstractNumId
  - `ov`: 级别重载字典 (`lvlOverride`), 包含 `startOverride` 或完整 `lvl`
- 挂载至 `self.doc.numbering = {"abs": abs_map, "nums": num_map}`。
- 提供辅助方法 `resolve_numbering_level(num_id: str, ilvl: int) -> dict[str, Any] | None`。

### 3. DrawingML & VML Parsing Engine (`DocxReader._parse_drawing`, `_parse_vml_pict`)
- 解析 `<w:drawing>`：
  - 支持直接作为 `<w:p>` 的子节点，或作为 `<w:r>` 内的子节点。
  - 读取 `<wp:inline>` 或 `<wp:anchor>`：
    - `extent`: `cx`, `cy` (EMU / 12700.0 转 pt)
    - `docPr`: `id`, `name`, `descr` (alt text), `title`
    - 若为 `<wp:anchor>`：
      - `simplePos`: `x`, `y`
      - `positionH`: `relativeFrom`, `align`, `posOffset` (EMU / 12700.0)
      - `positionV`: `relativeFrom`, `align`, `posOffset` (EMU / 12700.0)
      - `dist`: `t`, `b`, `l`, `r` (EMU / 12700.0)
      - `z_index`: `relativeHeight`
      - `behind`: `behindDoc == "1"`
      - `wrap`: `wrapSquare`, `wrapTight`, `wrapThrough`, `wrapTopAndBottom`, `wrapNone`
    - `<a:graphicData>`:
      - `<pic:pic>`:
        - `<a:blip>`: 解析 `r:embed` 或 `r:link`，根据 relationships 映射为 package 内的媒体路径 (如 `word/media/image1.png`)
        - `<a:srcRect>`: 裁剪比例 `l`, `t`, `r`, `b`
        - `<a:xfrm>`: 旋转角 `rot / 60000.0`
        - 实例化 `PictureItem`
- 解析 `<w:pict>` (VML):
  - 读取 `<v:shape>`, `<v:rect>`, `<v:imagedata>`
  - 解析 `style` 属性中的 width, height, position, z-index, margin 等
  - 提取 `r:id` 或 `r:href` 对应媒体资源，生成对应 `PictureItem`

### 4. Advanced Table Parsing
- 解析单元格水平合并 `<w:gridSpan w:val="N">` -> `cell.tc_pr.grid_span = N`
- 解析单元格垂直合并 `<w:vMerge w:val="restart|continue">` -> `cell.tc_pr.v_merge = val` (缺失 val 时默认为 `continue`)
- 解析单元格边距 `<w:tcMar>`：`<w:top>`, `<w:bottom>`, `<w:left>`, `<w:right>` (twips / 20.0 -> pt)
- 解析行高 `<w:trHeight w:val="X" w:hRule="exact|atLeast|auto">`
- 解析表级默认边距 `<w:tblCellMar>` 与表边框 `<w:tblBorders>`

### 5. Footnotes, Endnotes & Structural Elements
- 解析 `word/footnotes.xml` -> `self.doc.fn[id] = Story(kind="footnote", blocks=...)`
- 解析 `word/endnotes.xml` -> `self.doc.en[id] = Story(kind="endnote", blocks=...)`
- 在段落 inline 遍历时，遇到 `<w:footnoteReference>` / `<w:endnoteReference>` 生成 `NoteRefItem`
- 书签全局索引：收集 `<w:bookmarkStart>` 中的 `name` 与 `id`，存入 `self.doc.props["bookmarks"][name] = b_id`
- 分节符 (`<w:sectPr>`): 准确提取纸张方向 (`orient`), 纸张宽高 (`pg_w`, `pg_h`), 页边距 (`mt`, `mb`, `ml`, `mr`, `hdr`, `ftr`, `gutter`), 分栏 (`cols`: num, space), 节类型 (`sect_type`), 首页不同 (`title_pg`).

---

## Verification & Test Plan
编写并通过全面测试集 `tests/modules/writer/test_docx_reader_advanced.py`，覆盖：
1. **测试多级编号列表**：
   - 含有 `abstractNum`（多级混合编号、法律编号、前缀格式）与 `num` 实例及 `lvlOverride` 的 DOCX 解析。
   - 验证 `doc.numbering["abs"]` 与 `doc.numbering["nums"]` 的结构与属性。
   - 验证段落 `p_pr.num` 引用与层级解析。
2. **测试复杂表格跨行跨列与布局**：
   - 含有 `gridSpan` 水平跨列与 `vMerge` 垂直跨行合并的表格。
   - 验证 `tr_pr.h`, `tr_pr.h_rule`, `tc_pr.tc_mar`, `tbl_pr.cell_mar` 的尺寸精度。
3. **测试 DrawingML 与浮动图片**：
   - 含有 `<wp:inline>` 内联图片和 `<wp:anchor>` 浮动图片的段落。
   - 验证 `PictureItem` 的尺寸、图片文件路径、裁剪参数、旋转角度以及 `float_pr.wrap`（square, tight, behind 等）。
   - 含有 `<w:pict>` VML 图片的向后兼容解析。
4. **测试脚注、尾注与书签**：
   - 含有脚注与尾注引用的正文及对应 `word/footnotes.xml` 内容解析。
   - 验证 `doc.fn`、`doc.en` 与书签字典 `doc.props["bookmarks"]`。
5. **完整自动化测试运行**：
   `PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/writer/test_docx_reader_advanced.py -v`
