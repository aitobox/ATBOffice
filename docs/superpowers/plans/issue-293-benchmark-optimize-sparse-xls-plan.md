# Implementation Plan: Issue #293 - 基准测试并优化稀疏 XLS 导入性能

## Overview
Optimize `xls_reader.py` to accelerate sparse Excel 97-2003 `.xls` loading by replacing the naive $O(nrows \times ncols)$ Python object creation loop with low-level array buffer checks and fast row skipping, while preserving complete data fidelity, styling, merged cells, geometries, adding cancellation/progress hooks, and enforcing strict performance budgets with automated regression tests.

---

## Proposed Changes

### Chunk 1: Benchmark and Baseline Profiling
- Write an isolated benchmark script in `scripts/benchmark_xls_sparse.py` that measures:
  - Parse time (min, max, median over 5 iterations)
  - Peak memory usage (via `tracemalloc`)
  - Real sample `poi__51535.xls`
  - Synthetic sparse workbook (65536 rows × 256 cols, only corner cells filled)
  - Synthetic dense workbook (1000 rows × 50 cols)
- Run baseline and log results before code changes.

### Chunk 2: Core Optimization in `xls_reader.py`
- Modify `src/atboffice/modules/spreadsheet/io/xls_reader.py`:
  - Add `cancel_check: Callable[[], bool] | None = None` and `progress_callback: Callable[[int, int], None] | None = None` to `read_xls`.
  - Use fast row-level memory comparison (`rt.tobytes() == zero_bytes`) when `_cell_types` is available.
  - Skip empty rows in 1 byte-level check.
  - Traverse only non-empty cells in sparse rows.
  - Extract cell values directly from `_cell_values[r][c]` to avoid instantiating intermediate `Cell` objects.
  - Check `cancel_check` periodically (every 1024 rows) and trigger `progress_callback`.
  - Keep fallback path if `_cell_types` is absent (using `sheet.cell(r, c)`).
  - Preserve all styles, formatting, merged cells, row heights, col widths.

### Chunk 3: Integration with UI & Error Handling
- Update `src/atboffice/ui/shell/ledger_window.py`:
  - Handle potential `InterruptedError` if cancelled, displaying user feedback and rolling back safely.
  - Ensure status bar and error dialogs provide clear feedback.

### Chunk 4: Tests & Performance Regression Guard
- Update `tests/test_xls.py`:
  - `test_read_xls_poi_51535_sparse_correctness_and_budget()`: Verifies the 4 corners of `poi__51535.xls` are correctly read, sheet name is preserved, and total parse time is under 1.0 second (target < 0.3s).
  - `test_read_xls_sparse_synthetic_perf_budget()`: Generates a sparse 65536×256 workbook in memory, tests correctness and verifies execution is under 0.5s.
  - `test_read_xls_cancellation()`: Verifies `cancel_check` raises `InterruptedError` cleanly.
  - `test_read_xls_progress_callback()`: Verifies progress callback reports progress.
  - Run full test suite to guarantee zero regressions.

### Chunk 5: Audit & Stress-Testing
- Re-run benchmark script to record after-metrics.
- Execute `grill-me` stress test.
- Advance state machine to `reviewing` and trigger `atb-github-code-reviewer`.

---

## Verification Plan

### Automated Tests
- Run `pytest tests/test_xls.py -v`
- Run full spreadsheet test suite: `pytest tests/ -k "xls or ledger or spreadsheet" -v`
- Run all project tests: `pytest tests/`

### Manual / Benchmark Verification
- Run `python3 scripts/benchmark_xls_sparse.py` before and after to verify > 100x speedup and memory efficiency.
