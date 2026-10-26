# Implementation Plan: [Ledger] 三层金字塔自动化回归测试套件与真实 Office 样本验证

- **Issue**: #18
- **Branch**: `agent/issue-18-three-tier-regression-pyramid`
- **Specification**: `docs/superpowers/specs/issue-18-three-tier-pyramid-regression-suite-spec.md`

---

## Task Breakdown

### Task 1: Fix Core Engine Bug in `evaluator.py`
- **Files**: `src/atboffice/modules/spreadsheet/calc/evaluator.py`
- **Action**: Fix `UnaryOpNode` operand resolution from `node.node` to `node.operand`.
- **Verification**: Run unit test with unary minus expression (e.g. `=-5`, `VDB(2400,300,10,-1,1)`).

---

### Task 2: Tier 1 - Pure Logic Unit Regression Suite
- **Files**:
  - `tests/unit/spreadsheet/test_calc_regression.py`
  - `tests/unit/spreadsheet/test_clean_functions_baseline.py`
  - `tests/unit/spreadsheet/test_dag_regression.py`
- **Actions**:
  1. Port all test scenarios from `.vibeoffice/tests/ledger/calc.test.js` to `test_calc_regression.py`.
  2. Implement precision baseline runner in `test_clean_functions_baseline.py` checking `clean-functions.baseline.json` against strict tolerances.
  3. Implement deep chain recalculation and cycle reporting in `test_dag_regression.py`.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/spreadsheet/test_calc_regression.py tests/unit/spreadsheet/test_clean_functions_baseline.py tests/unit/spreadsheet/test_dag_regression.py -v`

---

### Task 3: Tier 2 - GUI Interaction Suite (`pytest-qt`)
- **Files**:
  - `tests/gui/test_pyramid_interactions.py`
- **Actions**:
  1. Test mouse drag selection (press, move, release across cells, multi-cell rectangle).
  2. Test in-place cell editing (double-click activation, typing in line edit, Enter commit, Escape cancel).
  3. Test AutoFill smart handle drag (drag handle down 3 rows, verify sequence interpolation).
  4. Test keyboard shortcuts & navigation (Arrow keys, Tab/Shift+Tab, Ctrl+C / Ctrl+V, Delete).
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/gui/test_pyramid_interactions.py -v`

---

### Task 4: Tier 3 - Real Office XLSX Corpus & Roundtrip Suite
- **Files**:
  - `tests/unit/vfs/test_office_roundtrip.py`
- **Actions**:
  1. Build realistic multi-part XLSX package with worksheets, formulas, styles, drawings, custom XML, and VBA binary.
  2. Perform single-cell mutation on Sheet1!A1.
  3. Save package using `PackageWriter`.
  4. Re-open and assert:
     - 100% SHA-256 match on all untouched parts (`vbaProject.bin`, `styles.xml`, `sheet2.xml`, `_rels/.rels`, etc.).
     - Modified sheet has correct updated cell value and ECMA-376 schema order.
     - Dependent formula recalculations are completely accurate.
- **Verification**: `PYTHONPATH=src conda run -n ATBOffice pytest tests/unit/vfs/test_office_roundtrip.py -v`

---

### Task 5: Project-Wide Verification & Quality Check
- **Action**: Run `PYTHONPATH=src conda run -n ATBOffice pytest tests/ -v --durations=10`.
- **Expected Result**: All tests pass, 0 failures, 0 errors.
