# Specification: Fix sortconditionref.xlsx Offscreen Event Loop SIGSEGV (Issue #290)

## Problem Summary
When loading `tests/docs/excel/xlsx/libreoffice__sortconditionref.xlsx` in ATBOffice Ledger (particularly during offscreen capture or GUI event processing with `processEvents()`), the application crashed with a Segmentation fault (`SIGSEGV: 11`).

## Root Cause Analysis
1. **Malformed Model Object**: In `src/atboffice/modules/spreadsheet/io/xlsx_reader.py`, worksheet `<autoFilter>` tags were parsed naively as `sheet.auto_filter = dict(af.attrib)`. This set `auto_filter` to a dictionary (e.g. `{'ref': 'B2', ...}`) rather than an instance of `AutoFilter(r1, c1, r2, c2)`.
2. **Unhandled Exception in paintEvent**: In `src/atboffice/modules/spreadsheet/views/grid_viewport.py`, `paintEvent` assumed `self.model.auto_filter` had attributes `.r1, .c1, .c2`. Accessing `af.r1` raised an unhandled `AttributeError: 'dict' object has no attribute 'r1'`.
3. **QPainter Lifecycle & QBackingStore Corruption**: When an exception is raised inside a Qt virtual method (`paintEvent`) between `QPainter(self.viewport())` and method completion, the painter is never ended cleanly (`painter.end()`). Qt's raster paint engine detected an active painter during paint device destruction/flush (`QBackingStore::endPaint() called with active painter`), culminating in an immediate fatal C++ SIGSEGV during `QApplication.processEvents()`.

## Architectural Design & Remediation Plan

### 1. Robust OOXML AutoFilter Parsing (`xlsx_reader.py`)
- Import `AutoFilter` from `atboffice.modules.spreadsheet.models.filter_model`.
- Parse `ref` attribute using `parse_range(ref_str)`.
- If valid, instantiate a proper `AutoFilter(r1=rg["r1"], c1=rg["c1"], r2=rg["r2"], c2=rg["c2"])`.
- Safely handle single cell references (e.g. `ref="B2"` -> `r1=1, c1=1, r2=1, c2=1`).
- Preserve original XML in `sheet.extra["auto_filter_xml"]` for lossless roundtrip.

### 2. Viewport Defensive Safeguards (`grid_viewport.py`)
- Protect all accesses to `self.model.auto_filter` with attribute checks (`hasattr(af, "r1")` and `hasattr(af, "c1")` and `hasattr(af, "c2")`).
- In `paintEvent`, wrap drawing logic with a `try...finally` block that guarantees `painter.end()` is invoked if `painter.isActive()`, preventing any potential paint engine heap corruption or crash if an unexpected exception occurs.

### 3. Verification & Regression Testing
- Implement automated test `tests/test_issue_290_sortconditionref_crash.py` running in an isolated test environment.
- Verify `capture_doc_atboffice.py` succeeds on `libreoffice__sortconditionref.xlsx` without crashing or timing out.

## Implementation Task List
- [x] Task 1: 根因定位与测试复现：重现 sortconditionref.xlsx 离屏/真实事件循环下的段错误，确定 QPainter 异常泄露与 autoFilter dict 属性缺失为触发点
- [ ] Task 2: 数据层与视图层防护修复：
  - 在 xlsx_reader.py 中规范解析 <autoFilter> 为 AutoFilter 领域对象，支持单单元格与多列区域并保留 XML 往返
  - 在 grid_viewport.py 中为 auto_filter 访问添加类型与属性安全防御守卫
  - 在 paintEvent 中增加 try...finally 结构保证 painter.end() 释放，杜绝 QBackingStore 悬挂与 SIGSEGV
- [ ] Task 3: 独立进程与端到端自动化测试验证：
  - 编写 test_sortconditionref_crash.py 专项回归测试，覆盖真实打开、离屏渲染与 processEvents 重复执行
  - 验证 capture_doc_atboffice.py 顺利完成 tests/docs/excel/xlsx/libreoffice__sortconditionref.xlsx 采集且退出码 0
- [ ] Task 4: 全量回归测试与代码审查准备
- [ ] Task 5: grill-me 压力审计与交付验证
