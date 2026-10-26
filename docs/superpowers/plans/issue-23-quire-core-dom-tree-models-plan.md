# Implementation Plan: Issue #23 [Quire] 核心文档对象模型 (DOM Tree: Document, Section, Paragraph, Run)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建纯 Python 3.12+ 的文字处理核心文档对象模型（DOM Tree）。涵盖节（Section）、段落（Paragraph）、行内文本（Run）、书签（Bookmark）、动态域（Field）及样式继承关系，与 GUI 彻底解耦，为排版计算和格式读写提供坚实的数据结构底座。

**Tech Stack:** Python 3.12+ (dataclasses, typing, type hints), pytest.

**Spec:** [`docs/superpowers/specs/issue-23-quire-core-dom-tree-models-spec.md`](file:///Volumes/My%20Shared%20Files/brainzhang/work/aitobox/ATBOffice/docs/superpowers/specs/issue-23-quire-core-dom-tree-models-spec.md)

---

### Task 1: 长度单位与排版属性数据结构 (`properties.py`)

**Files:**
- Create: `src/atboffice/modules/writer/models/properties.py`
- Test: `tests/unit/writer/test_dmodel.py`

**Key Components:**
- 长度转换与解析：`parse_length(s, default_unit="in") -> float (pt)`, `format_length(pt, unit="in") -> str`, `pt_to_dxa(pt)`, `dxa_to_pt(dxa)`.
- 纸张预设常量：`PAPER_SIZES: dict[str, tuple[float, float]]` (Letter, Legal, A4, A5, A3, B5, etc.)。
- 排版属性模型：
  - `DocGridProperties`: type ('lines' | 'linesAndChars' | 'none'), line_pitch, char_space.
  - `SectionProperties`: pg_w, pg_h, orient, mt, mb, ml, mr, gutter, hdr, ftr, cols, doc_grid, title_pg, v_align, pg_num, refs, sect_type.
  - `SpacingProperties`: before, after, line, line_rule, before_auto, after_auto.
  - `IndentProperties`: left, right, first_line.
  - `TabStop`: pos, align, leader.
  - `ParagraphProperties`: style, jc, ind, sp, keep_next, keep_lines, page_break_before, widow_control, outline_level, tabs, num, sect.
  - `RunProperties`: style, font, font_ea, font_cs, sz, sz_ea, b, i, u, color, vert, highlight, strike, dstrike, caps, small_caps, kern, spacing.
  - `BorderProperties`, `ShadingProperties`, `TableProperties`, `RowProperties`, `CellProperties`.

- [ ] **Step 1: Write failing unit test for units & properties**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `src/atboffice/modules/writer/models/properties.py`**
- [ ] **Step 4: Verify pass**

---

### Task 2: 核心文档树节点与图元操作 (`document.py`)

**Files:**
- Create: `src/atboffice/modules/writer/models/document.py`
- Test: `tests/unit/writer/test_dmodel.py`

**Key Components:**
- 图元项 (Items):
  - `RunItem` (base)
  - `TextItem`: text, r_pr
  - `TabItem`: r_pr
  - `BreakItem`: break_type ('line' | 'page' | 'column'), r_pr
  - `SymbolItem`: font, char, r_pr
  - `BookmarkStartItem`, `BookmarkEndItem`: name, bookmark_id
  - `FieldBeginItem`, `FieldSeparateItem`, `FieldEndItem`: field_type, instr, locked
  - `CommentRangeStart`, `CommentRangeEnd`: comment_id
- 块节点 (Blocks):
  - `Paragraph`: id, runs, p_pr, r_pr, sect
  - `Table`: id, tbl_pr, grid, rows
  - `Row`: id, tr_pr, cells
  - `Cell`: id, tc_pr, blocks
  - `Story`: kind, blocks, paras
- 根容器 (Document):
  - `Document`: main, sect, styles, defaults, numbering, hf, fn, en, comments, settings, props
- 高性能字符串与度量计算：
  - `ilen(item) -> int`: 文本返回长度，marker (如书签、域标示) 返回 0，图元返回 1
  - `plen(para) -> int`: 段落总字符数
  - `ptext(para, from_idx=None, to_idx=None) -> str`: 包含占位符的段落文本
  - `plain_text(para, skip_deleted=True) -> str`: 纯文本
- 高性能图元编辑与切分：
  - `locate(para, offset, side="after") -> (item_index, internal_offset, start_offset)`
  - `split_at(para, offset) -> int`
  - `insert_index(para, offset) -> int`
  - `normalize(para)`: 相邻相同格式 TextItem 合并，清除空串
  - `slice_runs(para, start, end) -> list[RunItem]`
- 树索引与导航：
  - `reindex(doc)`: 构建段落读取顺序索引与快速查找字典
  - `walk(container, callback, story=None, parents=None) -> bool`
  - `all_paragraphs(doc, all_stories=False) -> list[Paragraph]`
  - `paras_between(doc, p1, p2) -> list[Paragraph]`
  - `sections(doc) -> list[dict]`: 提取所有分节区间

- [ ] **Step 1: Write failing unit test for DOM nodes, text extraction, split/slice/normalize, and traversal**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `src/atboffice/modules/writer/models/document.py`**
- [ ] **Step 4: Verify pass**

---

### Task 3: Word 2003 内置样式与属性级联求解 (`styles.py`)

**Files:**
- Create: `src/atboffice/modules/writer/models/styles.py`
- Test: `tests/unit/writer/test_dmodel.py`

**Key Components:**
- 样式定义：`Style`: id, name, style_type ('paragraph' | 'character' | 'table' | 'numbering'), based_on, next_style, p_pr, r_pr, tbl_pr, tc_pr, builtin, is_default.
- 内置样式字典：`builtin_styles() -> dict[str, Style]` (Normal, Heading 1~9, Title, Subtitle, ListBullet, ListNumber, TableNormal, TableGrid, Hyperlink 等).
- 级联与继承计算：
  - `style_chain(doc, style_id) -> list[Style]`
  - `merge_p_props(base, over) -> ParagraphProperties`
  - `merge_r_props(base, over) -> RunProperties`
  - `resolve_p_props(doc, para, context=None) -> ParagraphProperties`
  - `resolve_r_props(doc, para, item=None, context=None) -> RunProperties`

- [ ] **Step 1: Write failing unit test for style inheritance and property cascade resolution**
- [ ] **Step 2: Run pytest to verify failure**
- [ ] **Step 3: Implement `src/atboffice/modules/writer/models/styles.py`**
- [ ] **Step 4: Verify pass**

---

### Task 4: 模块导出与全量回归验证 (`__init__.py` & Full Test Suite)

**Files:**
- Modify: `src/atboffice/modules/writer/models/__init__.py`
- Verify: `tests/unit/writer/test_dmodel.py`
- Verify: Full pytest test suite (`tests/`)

- [ ] **Step 1: Export models from `src/atboffice/modules/writer/models/__init__.py`**
- [ ] **Step 2: Run `pytest tests/unit/writer/test_dmodel.py -v`**
- [ ] **Step 3: Run full regression test suite `PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/`**
- [ ] **Step 4: Transition state to `reviewing`**
