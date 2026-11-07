# Specification: 修复 Word 连续分节错误分页 (Issue #289)

## 1. 背景与问题分析
在 ATBOffice 的 Quire (Word) 排版分页引擎 (`src/atboffice/modules/writer/layout/pagination.py`) 中，当前的分页循环逻辑实现存在缺陷：
- 在 `_execute_single_pagination_pass` 中，对文档的每一个分节（Section）在循环开始处无条件调用 `ctx.start_page(si, sect, first_of_section=first_of_section)`。
- 对于包含连续分节符（`sect_type == "continuous"`）的文档（如 `tests/docs/word/docx/libreoffice__fdo52208.docx`），即使前置分节仅占用少量垂直高度且后续分节使用相同纸张规格，排版引擎依然会强制新建物理页面。
- 导致样例 `libreoffice__fdo52208.docx` 产生两页，第一页仅有空白行，第二页才显示正文 `"second para, still on the first page"`；而在原版 Word 及 `.vibeoffice` 基准中，该样例正文在第一页正常显示，总页数为 1。

## 2. 行为目标与规范 (Specification)
1. **连续分节单页多区域复用 (Same-Page Region Reuse)**:
   - 当遇到后续分节 `sect_type == "continuous"` 且与前一分节页面宽高一致（`abs(sect.pg_w - prev_sect.pg_w) < 1.0 and abs(sect.pg_h - prev_sect.pg_h) < 1.0`）：
   - 计算当前页面已使用区域底端位置 `bottom_y = current_region.top + max(c.used_height for c in current_region.columns)`。
   - 剩余可用高度 `avail_h = current_page.body_height - bottom_y`。
   - 若 `avail_h >= 12.0`（有足够空间容纳内容）：在当前页面创建新区域 `current_page.start_region(si, sect, top=bottom_y, height=avail_h)`，保持在同一物理页面上连续排版。
2. **纸张几何不匹配或空间不足时强制物理分页**:
   - 若 `sect.pg_w` 或 `sect.pg_h` 与前一节不一致（例如纵向转横向、A4 转 Letter），物理纸张无法合并，必须调用 `ctx.start_page` 开启新页。
   - 若当前页剩余垂直空间不足（`avail_h < 12.0`），调用 `ctx.start_page` 开启新页。
3. **连续分节内容溢出流转 (Overflow Across Pages)**:
   - 若连续分节内容超出当前页剩余高度，通过 `advance_column_or_page` 流转至下一页；在下一页上以 `top=0.0, height=body_height` 继续该分节排版。
4. **分栏切换支持 (Multi-Column in Continuous Sections)**:
   - 连续分节常用于单栏与多栏混排（例如前一节 1 栏，后一节 2 栏）。新区域应按照目标分节的 `sect.cols` 配置创建列，各列垂直起始位置对齐在 `top`，列宽计算基于当前页的 `body_width`。
5. **保持其他分节符行为完全不受影响**:
   - `nextPage`: 始终另起新页。
   - `oddPage` / `evenPage`: 根据当前页码奇偶性，必要时插入空白页以对齐目标奇/偶页。
   - 分节起始页码重置（`pg_num.start`）：连续分节若定义在同一页，页码重置遵循 Word/OOXML 规范。

## 3. 验收标准
- [x] 单元测试覆盖连续分节同一页布局、纸张尺寸变化强制分页、连续分节内容跨页溢出、多栏切换等场景。
- [x] 真实样本文档 `tests/docs/word/docx/libreoffice__fdo52208.docx` 分页结果为 1 页，正文 `"second para, still on the first page"` 在首页第一区域/列中正确排版。
- [x] 既有分页单元测试与全量测试套件持续通过，无回归。
