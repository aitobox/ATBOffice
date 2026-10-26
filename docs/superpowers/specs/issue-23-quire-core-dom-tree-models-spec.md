# Specification: Issue #23 [Quire] 核心文档对象模型 (DOM Tree: Document, Section, Paragraph, Run)

## 1. 概述 (Overview)

本规范为 ATBOffice 的文字处理模块（Quire，对应 Word 2003）构建纯 Python 3.12+ 的核心文档对象模型（Document Object Model, DOM Tree）。
DOM 树与 GUI（PySide6）完全解耦，提供类型安全（Type Hints）、结构清晰、可无损往返（Lossless Roundtrip）的数据底座，负责承载排版计算（Portions/Pagination）、样式继承解析（Style Chain）、节点遍历定位与 WordprocessingML / DOCX 格式持久化。

参考实现与架构渊源：
- 本地原始参考代码：`.vibeoffice/public/quire/js/dmodel.js` (59KB)
- 遵循 Open Packaging Conventions (OPC) 与 ECMA-376 WordprocessingML 标准。

---

## 2. 核心架构与模块规划 (Architecture & Module Layout)

模块路径：`src/atboffice/modules/writer/models/`
- `src/atboffice/modules/writer/models/__init__.py`
- `src/atboffice/modules/writer/models/properties.py` (样式、段落属性、字符属性、节属性、边框与底纹)
- `src/atboffice/modules/writer/models/document.py` (Document, Section, Paragraph, Run, Item, Table, Row, Cell, Story)
- `src/atboffice/modules/writer/models/styles.py` (Word 2003 内置样式表、样式继承链解析与属性级联求解)

### 2.1 长度单位与坐标系统规范
所有内部几何与排版尺寸均统一以 **点 (pt, 1/72 inch)** 为基准：
- 1 inch = 72 pt = 1440 dxa (twips)
- 1 cm = 28.3465 pt
- 1 mm = 2.83465 pt
- 1 px (96 DPI) = 0.75 pt (即 96/72 px per pt)

---

## 3. 数据模型设计 (Data Models)

### 3.1 节模型属性 (SectionProperties)
节（Section）定义了页面布局与分节行为：
- `pg_w`: 页面宽度 (pt)，默认 Letter 612 pt (A4 为 595.3 pt)
- `pg_h`: 页面高度 (pt)，默认 Letter 792 pt (A4 为 841.9 pt)
- `orient`: 纸张方向，`'portrait'` 或 `'landscape'`
- `mt`, `mb`, `ml`, `mr`: 上、下、左、右页边距 (pt)，默认 mt=72, mb=72, ml=90, mr=90
- `gutter`: 装订线距离 (pt)，默认 0
- `hdr`, `ftr`: 页眉、页脚距离顶端/底端的边距 (pt)，默认 36
- `cols`: 分栏配置，`num` 栏数 (默认 1), `space` 栏间距 (默认 36), `sep` 分隔线 (bool), `equal_width` (bool), `widths` (list[float])
- `doc_grid`: 东亚行网格配置，`type`: `'lines'` | `'linesAndChars'` | `'none'`, `line_pitch`: pt (默认 15.6 或 18 pt), `char_space`: pt
- `title_pg`: 是否区分首页页眉页脚 (bool, 默认 False)
- `v_align`: 垂直对齐，`'top'` | `'center'` | `'both'` | `'bottom'`
- `pg_num`: 页码格式与起始值，`fmt`: `'decimal'` | `'upperRoman'` 等, `start`: int | None
- `refs`: 页眉页脚引用标识映射，如 `{"hdr": {"default": id, "first": id, "even": id}, "ftr": {...}}`
- `type`: 分节符类型，`'nextPage'` | `'continuous'` | `'oddPage'` | `'evenPage'` | `'nextColumn'`

### 3.2 段落属性 (ParagraphProperties)
段落（Paragraph）外观与排版控制：
- `style`: 样式 ID，默认 `'Normal'`
- `jc`: 对齐方式，`'left'` | `'center'` | `'right'` | `'both'` (两端对齐) | `'distribute'`
- `ind`: 缩进配置，`left`: float, `right`: float, `first_line`: float (正值为首行缩进，负值为悬挂缩进)
- `sp`: 行距与段间距，`before`: float, `after`: float, `line`: float, `line_rule`: `'auto'` | `'exact'` | `'atLeast'`, `before_auto`: bool, `after_auto`: bool
- `keep_next`: 与下段同页 (bool)
- `keep_lines`: 段中不分页 (bool)
- `page_break_before`: 段前分页 (bool)
- `widow_control`: 孤行控制 (bool, 默认 True)
- `outline_level`: 大纲级别 (0..8 为 1~9 级，None 为正文)
- `tabs`: 制表位列表，每项包含 `pos` (pt), `align` (`'left'`|`'center'`|`'right'`|`'decimal'`), `leader` (`'none'`|`'dot'`|`'hyphen'`)
- `num`: 列表编号关联，`id`: str, `lvl`: int (0..8)
- `sect`: 若该段落末尾包含分节符，则附带该节的 `SectionProperties`

### 3.3 字符属性 (RunProperties)
Run / 行内文本与图元的富文本格式：
- `style`: 字符样式 ID (如 `'Hyperlink'`, `'DefaultParagraphFont'`)
- `font`: 西文字体名称 (如 `'Times New Roman'`, `'Arial'`)
- `font_ea`: 东亚中日韩字体名称 (如 `'SimSun'`, `'MS Gothic'`, `'PingFang SC'`)
- `font_cs`: 复杂文本字体 (Complex Script)
- `sz`: 字号 (pt)，默认 12 pt
- `sz_ea`, `sz_cs`: 东亚与复杂脚本字号 (pt)
- `b`: 粗体 (bool)
- `i`: 斜体 (bool)
- `u`: 下划线类型 (`'none'`, `'single'`, `'double'`, `'dotted'`, `'dashed'`, `'wave'`)
- `color`: 字体颜色，十六进制 `'RRGGBB'` 或 `'auto'`
- `vert`: 上下标，`'superscript'` | `'subscript'` | `'baseline'`
- `highlight`: 背景高亮色 (如 `'yellow'`, `'cyan'`, `'green'`, 或十六进制)
- `strike`: 单删除线 (bool), `dstrike`: 双删除线 (bool)
- `caps`: 全部大写 (bool), `small_caps`: 小型大写 (bool)
- `kern`: 字距调整字号阈值 (pt)
- `spacing`: 字符间距微调 (pt)

### 3.4 行内图元项 (Run / Item)
一个段落包含一系列 `RunItem`：
- `TextItem`: 纯文本，`text`: str, `r_pr`: RunProperties
- `TabItem`: 制表符
- `BreakItem`: 换行/分页/分栏符，`break_type`: `'line'` | `'page'` | `'column'`
- `SymbolItem`: 特殊符号，`font`: str, `char`: str
- `BookmarkStartItem` / `BookmarkEndItem`: 书签起止标示，`name`: str, `id`: int
- `FieldBeginItem` / `FieldSeparateItem` / `FieldEndItem`: 动态域结构（如 PAGE, NUMPAGES, DATE, TOC）
- `CommentRangeStart` / `CommentRangeEnd`: 批注范围标示

### 3.5 表格模型 (Table, Row, Cell)
- `Table`: `rows`: list[Row], `grid`: list[float] (各列宽度), `tbl_pr`: TableProperties
- `Row`: `cells`: list[Cell], `tr_pr`: RowProperties (高度、行重复 `tblHeader`, 禁止跨页断行 `cantSplit`)
- `Cell`: `blocks`: list[Paragraph | Table], `tc_pr`: CellProperties (宽度 `w`, 跨列 `grid_span`, 跨行 `v_merge`, 边框、底纹、内边距)

### 3.6 文档根容器 (Document)
- `main`: 主体故事 Story (`blocks`: list[Paragraph | Table])
- `sect`: 最终节属性 (文档全局或最后一节)
- `styles`: 样式字典 (`id` -> `Style`)
- `defaults`: 文档全局默认字符/段落属性 (`r_pr`, `p_pr`)
- `numbering`: 列表编号体系（抽象编号 `abs` 与编号实例 `nums`）
- `hf`: 页眉/页脚故事字典 (`id` -> Story)
- `fn`, `en`: 脚注/尾注故事字典
- `comments`: 批注故事字典
- `settings`: 文档设置（默认制表位 `def_tab` 等）
- `props`: 元数据（标题、作者、创建修改时间等）

---

## 4. 样式继承链与属性级联解析 (Style Resolution)

级联优先级严格符合 Word 2003 / ECMA-376 规范：
`Document Defaults < Table Style < Paragraph Style Chain < Numbering Indents < Direct Paragraph Formatting`
`Document Defaults < Table Style < Paragraph Style Chain < Character Style Chain < Direct Run Formatting`

提供核心解析方法：
- `style_chain(doc, style_id)`: 递归追溯 `based_on` 获取样式继承链
- `resolve_p_props(doc, para, context)`: 计算段落的最终有效排版属性
- `resolve_r_props(doc, para, item, context)`: 计算字符/项的最终有效富文本属性
- `merge_p_props(base, override)` / `merge_r_props(base, override)`: 级联深度合并

---

## 5. 高效文档树遍历与定位操作 (Document Tree Operations)

- `reindex()`: 为所有段落建立全局读取顺序索引（`_o` 序号、`_idx` ID 映射表，支持跨表格单元格扁平化遍历）
- `walk(container, callback)`: 深度优先递归遍历容器内所有图元
- `all_paragraphs(doc)`: 按阅读顺序快速获取全部段落
- `paras_between(doc, p1, p2)`: 获取两个段落间（含端点）的所有段落
- `locate(para, offset)`: 快速定位段落内部字符偏移对应的 Run 项与内部索引
- `split_at(para, offset)`: 在指定字符偏移处精确切分 Run
- `normalize(para)`: 自动合并具有相同字符属性的相邻文本 Run，清除空 Run
- `slice_runs(para, start, end)`: 截取指定字符区间并深拷贝 Run 项
- `sections(doc)`: 计算主体故事中全部节范围（`[{sect, from, to, end_para}]`）

---

## 6. 测试与验证策略 (Testing & Verification)

测试文件：`tests/unit/writer/test_dmodel.py`
验证覆盖：
1. **基础节点实例化与类型校验**：创建 Section, Paragraph, Run, Table, Cell，验证默认属性与单位换算。
2. **文本提取与长度计算**：验证 `plen()`、`ptext()`、`plain_text()` 对纯文本、制表符、分节符、特殊符号的处理。
3. **Word 2003 内置样式与级联解析**：验证 Normal, Heading 1~3 等继承链以及段落/字符属性合并结果。
4. **节与东亚行网格属性**：验证纸张预设（A4, Letter）与 15.6pt / 18pt linePitch 行网格参数。
5. **Run 切分、合并与标准化**：验证 `split_at()` 切分文本、`normalize()` 合并相同样式 Run、`slice_runs()` 区域拷贝。
6. **全文档树索引与遍历**：验证表格嵌套段落时的 `walk()`、`reindex()` 顺序一致性与 `paras_between()`。
