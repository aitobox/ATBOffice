# Technical Specification: Issue #293 - 基准测试并优化稀疏 XLS 导入性能

## 1. Problem Statement & Background
In `src/atboffice/modules/spreadsheet/io/xls_reader.py`, the `read_xls` function imports binary Excel 97-2003 (`.xls`) workbooks using the `xlrd` library.
For large dimensioned workbooks, `xls_reader.py` performs a naive nested Cartesian loop over all rows and columns:
```python
nrows = sheet.nrows
ncols = sheet.ncols
for r in range(nrows):
    for c in range(ncols):
        cell = sheet.cell(r, c)
```
When loading files like `tests/docs/excel/xls/poi__51535.xls`, which has dimensions 65536 rows × 256 columns, this loop triggers 16,777,216 iterations. Each iteration invokes Python methods `sheet.cell(r, c)` and `sheet.cell_xf_index(r, c)` and instantiates a Python `Cell` object, only to immediately discard it because the cell is `XL_CELL_EMPTY`.
As measured on the test machine, this took ~17.2 seconds for a workbook that only contained 4 non-empty cells.

Furthermore, long synchronous loading on the main GUI thread causes UI freezes with no user cancellation capability.

## 2. Requirements & Acceptance Criteria
1. **Accurate Baseline & Profiling**:
   - Accurately measure baseline CPU time and peak memory on real sample (`poi__51535.xls`) and synthetic sparse/dense workbooks before optimization.
2. **High-Performance Sparse Traversal**:
   - Leverage direct underlying buffers in `xlrd.sheet.Sheet` (`_cell_types`, `_cell_values`, `_cell_xf_indexes`).
   - Implement zero-overhead row-level emptiness detection via memoryview/bytes comparison (`rt.tobytes() == zero_bytes`), reducing empty row checks from hundreds of milliseconds to under 10ms for 65536 rows.
   - For non-empty rows, traverse only non-empty/styled columns.
   - Retain 100% of values, data types (numbers, strings, dates, booleans, error codes), styles (fonts, alignments, colors, borders, format codes), merged cells, column widths, row heights, and visibility flags.
3. **Responsive UI & Cancellation Support**:
   - Add `cancel_check: Callable[[], bool] | None = None` and `progress_callback: Callable[[int, int], None] | None = None` parameters to `read_xls`.
   - Update `ledger_window.py` open path to support cooperative cancellation if user cancels.
4. **Performance Budgets & Regression Testing**:
   - Establish strict performance budgets:
     - Real sample `poi__51535.xls` parse time must be < 1.0s (target: < 0.3s, down from 17s).
     - Synthetic sparse 65536×256 workbook parse time must be < 0.5s.
   - Add automated regression tests validating correctness, style preservation, merged cells, cancellation, and reproducible performance budgets.

## 3. Architecture & Detailed Design

### 3.1 Fast Row-Level and Cell-Level Sparse Traversal
In `read_xls`:
```python
zero_bytes = b"\x00" * ncols if ncols > 0 else b""
for r in range(nrows):
    if cancel_check and r % 1024 == 0 and cancel_check():
        raise InterruptedError("XLS read cancelled by caller")
    
    rt = getattr(sheet, "_cell_types", None)
    if rt is not None and r < len(rt):
        row_types = rt[r]
        if isinstance(row_types, array.array) and len(row_types) == ncols:
            if row_types.tobytes() == zero_bytes:
                continue
        elif not any(row_types):
            continue
```
For non-empty rows, iterate over columns:
- Extract `ctype = row_types[c]`.
- If `ctype == xlrd.XL_CELL_EMPTY`: skip immediately.
- If `ctype == xlrd.XL_CELL_BLANK`: check if cell has non-default styling (borders, background color, etc.). If no custom formatting, skip.
- If `ctype` is value-bearing: retrieve value directly from `_cell_values[r][c]`, convert datatype, apply styles, and store in `sheet_model`.

### 3.2 Cancellation Contract
`read_xls` accepts:
- `cancel_check: Callable[[], bool] | None = None`
- `progress_callback: Callable[[int, int], None] | None = None`
If `cancel_check()` returns True during worksheet processing or row processing, `InterruptedError` is raised cleanly, allowing transactional rollback.

## 4. Implementation Task List
- [ ] Task 1: 独立测量真实样例 (poi__51535.xls) 与构造样例的基准耗时与内存开销
- [ ] Task 2: 优化 xls_reader.py 稀疏遍历算法，集成高效空行/空单元格跳过并保留样式/合并/几何属性
- [ ] Task 3: 在 read_xls 中增加取消机制 (cancel_check) 与进度回调 (progress_callback) 支持
- [ ] Task 4: 完善 LedgerWindow 打开 XLS 流程，增强取消与大文件加载稳定性
- [ ] Task 5: 编写数据保真度、稀疏性能预算与取消机制的单元测试及回归测试
- [ ] Task 6: 重新测量优化后的耗时、内存对比并记录前后结果
- [ ] Task 7: 执行 grill-me 压力审计与全量测试套件验证
