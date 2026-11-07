# Implementation Plan: 修复 Word 连续分节错误分页 (Issue #289)

## Overview
本计划针对 Quire 排版分页引擎中的连续分节强制物理分页缺陷，通过实现单页区域复用、纸张几何校验、多栏分节自适应以及跨页溢出流转，恢复与 Word 及 .vibeoffice 一致的连续分节排版效果。

## Chunks & Milestones

### Chunk 1: TDD 单元测试集构建
- 文件: `tests/unit/writer/test_pagination.py`
- 内容:
  1. `test_section_breaks_continuous_same_page`: 两个相同纸张几何的分节，后一节为 continuous，验证排在同一页面的两个独立 Region 中，总页数为 1。
  2. `test_section_breaks_continuous_diff_geometry`: 后一节为 continuous 但纸张宽高不同，验证强制物理分页，总页数为 2 且各自纸张尺寸独立。
  3. `test_section_breaks_continuous_space_exhausted`: 前一节已占满页面高度，剩余空间不足 12pt，验证后一 continuous 分节自动触发新物理页。
  4. `test_section_breaks_continuous_multi_column`: 单栏分节紧接两栏连续分节，验证同一页内正确创建 2 个 ColumnFrame，各列宽度与起始位置符合预期。
  5. `test_fdo52208_document_regression`: 读取真实测试文档 `tests/docs/word/docx/libreoffice__fdo52208.docx`，断言分页总数为 1，且正文包含 `"second para, still on the first page"`。

### Chunk 2: 核心排版引擎分节推进逻辑重构
- 文件: `src/atboffice/modules/writer/layout/pagination.py`
- 内容:
  1. 在 `_PaginationContext` 中增加 `get_current_region_bottom() -> float` 方法，精确计算当前区域中最深一列的内容底部坐标（`region.top + max(used_height)`）。
  2. 重构 `_execute_single_pagination_pass` 分节初始化与流转逻辑：
     - 首节（`si == 0`）：调用 `ctx.start_page(0, sect, first_of_section=True)`。
     - 后续分节（`si > 0`）：
       - 若 `sect_type == "continuous"`：判断纸张几何尺寸 `sameGeom` 与剩余可用高度 `avail_h >= 12.0`。若满足条件，调用 `ctx.start_region(si, sect, top=bottom_y, height=avail_h)`；否则调用 `ctx.start_page`。
       - 若 `sect_type == "nextColumn"`：若当前区域仍有富余列则切列，否则切页。
       - 若 `sect_type == "oddPage" / "evenPage"`：根据目标奇偶性补空白页后切页。
       - 默认（`nextPage`）：调用 `ctx.start_page`。
     - 清理原循环末尾残留的未完工连续分节空 stub 代码。

### Chunk 3: 验证、回归测试与 Grill-Me 自审
- 执行 `pytest tests/unit/writer/test_pagination.py` 验证新用例与既有用例全部通过。
- 执行 `pytest tests/` 保证全量测试无回归。
- 实施 edge-case 压力审查（空分节、多连续分节嵌套、表格跨分节等）。
