# Technical Design Specification: Issue #11 - Advanced Worksheet Functions and Modern Dynamic Arrays (519 Full Coverage)

- **Author**: Antigravity Autonomous Agent
- **Date**: 2026-10-25
- **Status**: Approved (Autonomous >= 90% Confidence)
- **Target Issue**: aitobox/ATBOffice#11
- **Branch**: `agent/issue-11-advanced-functions-dynamic-arrays`

---

## 1. Overview & Objectives

This specification covers the implementation of advanced worksheet calculation functions and modern dynamic array handling for Ledger in ATBOffice (Python 3.12 / PySide6 port).

Building on top of the foundation core functions (#8) and DAG dependency graph (#7), this implementation achieves:
1. **Modern Dynamic Array Functions**: `XLOOKUP`, `XMATCH`, `FILTER`, `UNIQUE`, `SORT`, `SORTBY`, `SEQUENCE`, `TEXTSPLIT`, `TEXTJOIN`, `LET`, `LAMBDA`, `MAP`, `REDUCE`, `BYROW`, `BYCOL`.
2. **Dynamic Array Spilling & Collision Handling**: Automatic array spill computation, origin cell binding, and `#SPILL!` collision detection when target spill cells are obstructed.
3. **56 Financial Functions**: Full port of `.vibeoffice/public/ledger/js/fn-fin.js` including `PMT`, `IPMT`, `PPMT`, `PV`, `FV`, `NPV`, `IRR`, `XIRR`, `XNPV`, `RATE`, `NPER`, `CUMIPMT`, `CUMPRINC`, `DURATION`, `PRICE`, `YIELD`, depreciation methods (`SLN`, `SYD`, `DB`, `DDB`), and Treasury bills.
4. **45 Engineering & Bitwise Functions**: Full port of `.vibeoffice/public/ledger/js/fn-eng.js` including two's-complement base conversions (`BIN2DEC`, `DEC2HEX`, `HEX2BIN`, etc.), bitwise logic (`BITAND`, `BITOR`, `BITXOR`, `BITLSHIFT`, `BITRSHIFT`), complex numbers (`COMPLEX`, `IMREAL`, `IMAGINARY`, `IMDIV`, `IMSUB`, etc.), error functions (`ERF`, `ERFC`), delta/step tests (`DELTA`, `GESTEP`), and physical unit conversions (`CONVERT`).
5. **Statistical, Database & Extended Functions**: Full statistical distributions, regressions, rankings, and database functions (`DAVERAGE`, `DSUM`, `DCOUNT`, etc.).
6. **Strict 519 Function Registry Coverage**: 100% parity with `.vibeoffice/public/ledger/js/fninfo.js`, where all 519 functions in `ALL_FUNCTIONS_CATALOG` are registered in `FUNCTION_REGISTRY`, asserting `len(FUNCTION_REGISTRY) == 519`.

---

## 2. Architecture & Module Structure

```
src/atboffice/modules/spreadsheet/calc/
├── __init__.py          # Exported symbols, function registry, and spill handlers
├── coercion.py          # Value conversions, date serials, criteria matchers
├── context.py           # Arr, Ref, and EvalContext (with local vars & spill state)
├── dag.py               # Dependency tracking, cycle detection
├── errors.py            # Excel error singletons (#SPILL!, #CALC!, etc.)
├── evaluator.py         # AST evaluation (with LET, LAMBDA, InvokeNode, NameNode)
├── fn_dynamic.py        # Dynamic arrays, lambda higher-order, lookup & text
├── fn_eng.py            # Engineering, bitwise, complex numbers, CONVERT
├── fn_fin.py            # Financial, cash flow, bonds, depreciation
├── fn_info.py           # 519 function metadata catalog
├── fn_stat.py           # Statistical, distributions, regressions, database functions
├── functions.py         # Central aggregation ensuring all 519 functions registered
├── spill.py             # SpillManager and spill collision resolution
├── parser.py            # Formula grammar parser
├── references.py        # Cell reference arithmetic
└── tokens.py            # AST node definitions
```

---

## 3. Detailed Component Designs

### 3.1 Modern Dynamic Array Functions (`fn_dynamic.py`)
- **`SEQUENCE(rows, [cols], [start], [step])`**: Generates 2D numeric grid.
- **`FILTER(array, include, [if_empty])`**: Evaluates row/column boolean masks, returning matching sub-array or default.
- **`UNIQUE(array, [by_col], [exactly_once])`**: De-duplicates rows or columns based on Excel comparison rules.
- **`SORT(array, [sort_index], [sort_order], [by_col])`**: Orders matrix rows/cols ascending or descending.
- **`SORTBY(array, by_array1, [order1], ...)`**: Multi-key array sorting.
- **`XLOOKUP(lookup_val, lookup_arr, return_arr, [if_not_found], [match_mode], [search_mode])`**: Next-generation bidirectional lookup with exact/fuzzy/wildcard match and binary search.
- **`XMATCH(lookup_val, lookup_arr, [match_mode], [search_mode])`**: Returns 1-based index with enhanced matching.
- **`TEXTSPLIT(text, col_delimiter, [row_delimiter], [ignore_empty], [match_mode], [pad_with])`**: Splits text into 2D array.
- **`TEXTJOIN(delimiter, ignore_empty, text1, ...)`**: Joins text scalars/arrays with delimiter.
- **`LET(name1, val1, ..., expr)`**: Sequentially evaluates variable bindings into local scope.
- **`LAMBDA(param1, ..., expr)`**: Encapsulates dynamic user formulas into first-class callable functions.
- **`MAP(arr, lambda)`**, **`REDUCE(init, arr, lambda)`**, **`BYROW(arr, lambda)`**, **`BYCOL(arr, lambda)`**: Matrix higher-order operations.

### 3.2 Dynamic Array Spill Engine (`spill.py`)
- When evaluating a formula in cell `(sheet, r, c)`:
  - If result is a scalar, result writes to `(r, c)`.
  - If result is an `Arr(rows=R, cols=C)`:
    - Target spill range is `(r, c)` to `(r + R - 1, c + C - 1)`.
    - Collision check: Inspect all cells in the rectangle except origin `(r, c)`. If any cell contains non-blank value or formula, or belongs to another spill:
      - Origin cell receives `#SPILL!`.
      - Spill area is cleared.
    - If no collision:
      - Mark origin cell with spill metadata `af = (r, c, r + R - 1, c + C - 1)`.
      - Populate or mirror spill values across the rectangle.
- `#` Spill Reference operator: e.g. `A1#` resolves via `ANCHORARRAY` to the full spilled range.

### 3.3 Financial Calculation Engine (`fn_fin.py`)
- Strict numerical parity with Excel and `.vibeoffice/public/ledger/js/fn-fin.js`:
  - Annuities: `PMT`, `IPMT`, `PPMT`, `PV`, `FV`, `NPER`, `RATE` using Newton-Raphson approximation.
  - Cash flows: `NPV`, `IRR`, `MIRR`, `XNPV`, `XIRR` using date-weighted discounted cash flows.
  - Depreciation: `SLN` (straight-line), `SYD` (sum of years), `DB` (fixed declining), `DDB` (double declining), `VDB` (variable declining).
  - Bonds & Securities: Day count conventions (basis 0: 30/360 US, 1: Actual/actual, 2: Actual/360, 3: Actual/365, 4: 30/360 European) for `PRICE`, `YIELD`, `DURATION`, `MDURATION`, `ACCRINT`.

### 3.4 Engineering & Bitwise Functions (`fn_eng.py`)
- Base conversions with two's complement 10-character limits: `BIN2DEC`, `BIN2HEX`, `BIN2OCT`, `DEC2BIN`, `DEC2HEX`, `DEC2OCT`, `HEX2BIN`, `HEX2DEC`, `HEX2OCT`, `OCT2BIN`, `OCT2DEC`, `OCT2HEX`.
- Bitwise 48-bit unsigned operations: `BITAND`, `BITOR`, `BITXOR`, `BITLSHIFT`, `BITRSHIFT`.
- Complex numbers: String parsing `"a+bi"` and operations `COMPLEX`, `IMREAL`, `IMAGINARY`, `IMABS`, `IMCONJUGATE`, `IMSUM`, `IMSUB`, `IMPRODUCT`, `IMDIV`, `IMPOWER`, `IMSQRT`, `IMEXP`, `IMLN`.
- Error functions & thresholds: `ERF`, `ERFC`, `DELTA`, `GESTEP`.
- Unit conversions: `CONVERT(val, from_unit, to_unit)` supporting length, mass, time, pressure, energy, power, temperature (C, F, K, Rankine).

### 3.5 Central Function Registration & 519 Parity (`functions.py`)
- Aggregates core, dynamic, financial, engineering, statistical, database, and text functions.
- Stubs placeholder functions (`CUBE*`, `WEBSERVICE`, `RTD`, `SQL.REQUEST`, etc.) that require external data connectors by returning `#N/A` or keeping saved values.
- Validates that `len(FUNCTION_REGISTRY) == 519` with zero missing functions from `ALL_FUNCTIONS_CATALOG`.

---

## 4. Verification Plan

Comprehensive pytest suite in `tests/unit/spreadsheet/test_functions_advanced.py`:
1. `test_registry_size_519`: Assert `len(FUNCTION_REGISTRY) == 519` and every catalog function exists.
2. `test_dynamic_arrays`: Test `SEQUENCE`, `FILTER`, `UNIQUE`, `SORT`, `XLOOKUP`, `TEXTSPLIT`, `TEXTJOIN`.
3. `test_lambda_let`: Test `LET`, `LAMBDA`, `MAP`, `REDUCE`, `BYROW`, `BYCOL`.
4. `test_spill_collision`: Test spill success and `#SPILL!` collision when blocked.
5. `test_financial_functions`: Test `PMT`, `PV`, `FV`, `NPV`, `IRR`, `XIRR`, `RATE`.
6. `test_engineering_functions`: Test `BIN2DEC`, `DEC2HEX`, `BITAND`, `COMPLEX`, `IMDIV`, `CONVERT`.
7. `test_zero_regressions`: All pre-existing 131 tests continue to pass.
