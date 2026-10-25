# [Ledger] 基础与高频核心工作表函数库实现 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 Ledger 电子表格高频核心工作表函数库（覆盖 90% 以上日常表格使用场景），包含标量强制类型转换、通配符匹配（`*`, `?`）、多条件判定、范围聚合与标准错误类型体系。

**Architecture:** 按照领域职责分拆为错误模型 (`errors.py`)、运行时容器与求值上下文 (`context.py`)、强制类型转换与条件判定器 (`coercion.py`)、函数注册与实现库 (`functions.py`)、以及 AST 表达式求值器 (`evaluator.py`)。

**Tech Stack:** Python 3.12+, pytest, type hints

**Spec:** `docs/superpowers/specs/issue-8-core-worksheet-functions-spec.md`

## Global Constraints
- Python 3.12+ (type hints everywhere)
- Zero third-party runtime dependencies (纯 Python 标准库实现)
- 严格对照本地 `.vibeoffice/public/ledger/js/` 逻辑行为与 Excel 官方计算精度
- 完整单元测试覆盖，全套测试运行命令：`PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/spreadsheet/test_functions_core.py -v`

---

### Task 1: Standard Excel Errors and Runtime Types (`errors.py`, `context.py`)

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/errors.py`
- Create: `src/atboffice/modules/spreadsheet/calc/context.py`
- Test: `tests/unit/spreadsheet/test_functions_core.py`

- [ ] **Step 1: Write tests for ExcelError, Ref, Arr, EvalContext**
- [ ] **Step 2: Implement `errors.py` with singleton ExcelError constants (`#NULL!`, `#DIV/0!`, `#VALUE!`, `#REF!`, `#NAME?`, `#NUM!`, `#N/A`) and `is_error`**
- [ ] **Step 3: Implement `context.py` with `Arr`, `Ref`, and `EvalContext`**
- [ ] **Step 4: Run unit tests to verify passes**

---

### Task 2: Coercion, Wildcard Regex, Criteria Matcher & Date Utilities (`coercion.py`)

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/coercion.py`
- Test: `tests/unit/spreadsheet/test_functions_core.py`

- [ ] **Step 1: Write tests for `to_num`, `to_bool`, `to_str`, wildcard regex, criteria comparison (`>10`, `<>text`, `cat*`), and Excel 1900 date serial conversions**
- [ ] **Step 2: Implement scalar conversions with 15-digit precision rounding**
- [ ] **Step 3: Implement `wildcard_to_regex` supporting `*`, `?`, and escape `~*`, `~?`, `~~`**
- [ ] **Step 4: Implement `build_criteria_matcher` supporting `>`, `<`, `>=`, `<=`, `<>`, `=`**
- [ ] **Step 5: Implement `date_to_serial`, `serial_to_parts`, and `js_date_to_serial` matching `.vibeoffice/public/common/numfmt.js`**
- [ ] **Step 6: Run unit tests to verify passes**

---

### Task 3: Math & Trig, Statistical Functions (`functions.py` Part 1)

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/functions.py`
- Test: `tests/unit/spreadsheet/test_functions_core.py`

- [ ] **Step 1: Write tests for Math & Trig functions: `SUM`, `SUMIF`, `SUMIFS`, `ROUND`, `ROUNDUP`, `ROUNDDOWN`, `ABS`, `INT`, `MOD`, `PRODUCT`, `POWER`, `SQRT`, `SUBTOTAL`**
- [ ] **Step 2: Write tests for Statistical functions: `AVERAGE`, `AVERAGEIF`, `AVERAGEIFS`, `COUNT`, `COUNTA`, `COUNTBLANK`, `COUNTIF`, `COUNTIFS`, `MAX`, `MIN`**
- [ ] **Step 3: Implement function registry decorator and dispatching**
- [ ] **Step 4: Implement Math & Trig functions**
- [ ] **Step 5: Implement Statistical functions**
- [ ] **Step 6: Run unit tests to verify passes**

---

### Task 4: Lookup, Logical, Text, Date & Time Functions (`functions.py` Part 2)

**Files:**
- Modify: `src/atboffice/modules/spreadsheet/calc/functions.py`
- Test: `tests/unit/spreadsheet/test_functions_core.py`

- [ ] **Step 1: Write tests for Lookup & Reference (`VLOOKUP`, `HLOOKUP`, `INDEX`, `MATCH`, `LOOKUP`, `CHOOSE`)**
- [ ] **Step 2: Write tests for Logical & Error (`IF`, `IFS`, `AND`, `OR`, `NOT`, `SWITCH`, `IFERROR`, `IFNA`)**
- [ ] **Step 3: Write tests for Text (`CONCAT`, `CONCATENATE`, `LEFT`, `RIGHT`, `MID`, `LEN`, `TRIM`, `UPPER`, `LOWER`, `SUBSTITUTE`)**
- [ ] **Step 4: Write tests for Date & Time (`DATE`, `YEAR`, `MONTH`, `DAY`, `TODAY`, `NOW`, `DATEDIF`, `WEEKDAY`)**
- [ ] **Step 5: Implement all functions in `functions.py`**
- [ ] **Step 6: Run unit tests to verify passes**

---

### Task 5: Formula AST Evaluator & Calc Package Integration (`evaluator.py`, `__init__.py`)

**Files:**
- Create: `src/atboffice/modules/spreadsheet/calc/evaluator.py`
- Modify: `src/atboffice/modules/spreadsheet/calc/__init__.py`
- Test: `tests/unit/spreadsheet/test_functions_core.py`

- [ ] **Step 1: Write tests for end-to-end formula evaluation from parsed AST (e.g. `evaluate("=SUM(1, 2, 3)")`, `evaluate("=VLOOKUP(...)")`, etc.)**
- [ ] **Step 2: Implement AST visitor/evaluator in `evaluator.py` supporting binary operators, unary operators, literal values, cell references, area references, and function calls**
- [ ] **Step 3: Expose new public APIs in `calc/__init__.py`**
- [ ] **Step 4: Run unit tests to verify passes**

---

### Task 6: Full Test Suite Verification and Regression Guard

**Files:**
- Test: `tests/unit/spreadsheet/test_functions_core.py`
- Test: `tests/` (entire project suite)

- [ ] **Step 1: Run comprehensive tests in `test_functions_core.py`**
- [ ] **Step 2: Run entire project test suite (`pytest tests/`) ensuring zero regressions**
