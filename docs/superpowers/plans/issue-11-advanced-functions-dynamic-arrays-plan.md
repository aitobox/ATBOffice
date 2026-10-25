# Implementation Plan: Issue #11 - Advanced Worksheet Functions and Dynamic Arrays (519 Full Coverage)

- **Target Issue**: aitobox/ATBOffice#11
- **Branch**: `agent/issue-11-advanced-functions-dynamic-arrays`
- **Spec**: `docs/superpowers/specs/issue-11-advanced-functions-dynamic-arrays-spec.md`

---

## Task Breakdown

### Task 1: Complete Modern Dynamic Array, Higher-Order, and Text Functions
- Update `src/atboffice/modules/spreadsheet/calc/fn_dynamic.py`:
  - Add `TEXTJOIN(delimiter, ignore_empty, *args)`
  - Add `LAMBDA` constructor and callable wrapper
  - Add `LET` support in evaluation
  - Add `MAP`, `REDUCE`, `BYROW`, `BYCOL`
  - Ensure all dynamic functions are registered in `DYNAMIC_FUNCTIONS`
- Update `src/atboffice/modules/spreadsheet/calc/evaluator.py`:
  - Handle `NameNode` (variable lookup in `ctx.vars`)
  - Handle `InvokeNode` (calling lambdas/functions)
  - Handle `LET` and `LAMBDA` AST nodes in `evaluate_ast`

### Task 2: Implement Dynamic Array Spill Manager & Collision Engine
- Create `src/atboffice/modules/spreadsheet/calc/spill.py`:
  - `SpillManager`: tracks active spills per sheet
  - `evaluate_and_spill(sheet, r, c, ast, ctx)`: evaluates formula, checks for obstruction in spill rectangle, assigns `#SPILL!` on collision or updates spilled area
  - Clear prior spills when origin cell formula changes

### Task 3: Implement Financial Functions Module (`fn_fin.py`)
- Create `src/atboffice/modules/spreadsheet/calc/fn_fin.py`:
  - Annuities: `PMT`, `IPMT`, `PPMT`, `PV`, `FV`, `NPER`, `RATE`
  - Cash flows: `NPV`, `IRR`, `MIRR`, `XNPV`, `XIRR`, `FVSCHEDULE`
  - Cumulative: `CUMIPMT`, `CUMPRINC`, `ISPMT`
  - Rates: `EFFECT`, `NOMINAL`, `PDURATION`, `RRI`
  - Pricing: `DOLLARDE`, `DOLLARFR`
  - Depreciation: `SLN`, `SYD`, `DB`, `DDB`, `VDB`, `AMORLINC`, `AMORDEGRC`
  - Bonds/Securities: `PRICE`, `YIELD`, `DURATION`, `MDURATION`, `ACCRINT`, `ACCRINTM`, `PRICEMAT`, `YIELDMAT`, `TBILLPRICE`, `TBILLYIELD`, `TBILLEQ`
  - Stubs for remaining financial functions

### Task 4: Implement Engineering & Bitwise Functions Module (`fn_eng.py`)
- Create `src/atboffice/modules/spreadsheet/calc/fn_eng.py`:
  - Base conversions: `BIN2DEC`, `BIN2HEX`, `BIN2OCT`, `DEC2BIN`, `DEC2HEX`, `DEC2OCT`, `HEX2BIN`, `HEX2DEC`, `HEX2OCT`, `OCT2BIN`, `OCT2DEC`, `OCT2HEX`
  - Bitwise operations: `BITAND`, `BITOR`, `BITXOR`, `BITLSHIFT`, `BITRSHIFT`
  - Threshold / Error tests: `DELTA`, `GESTEP`, `ERF`, `ERF.PRECISE`, `ERFC`, `ERFC.PRECISE`
  - Complex numbers: `COMPLEX`, `IMREAL`, `IMAGINARY`, `IMABS`, `IMCONJUGATE`, `IMARGUMENT`, `IMSUM`, `IMSUB`, `IMPRODUCT`, `IMDIV`, `IMPOWER`, `IMSQRT`, `IMEXP`, `IMLN`, `IMLOG10`, `IMLOG2`, `IMSIN`, `IMCOS`, `IMTAN`, `IMSEC`, `IMCSC`, `IMCOT`, `IMSINH`, `IMCOSH`, `IMSECH`, `IMCSCH`
  - Bessel functions: `BESSELI`, `BESSELJ`, `BESSELK`, `BESSELY`
  - Physical unit conversion: `CONVERT(number, from_unit, to_unit)`

### Task 5: Implement Statistical & Database Functions Module (`fn_stat.py`)
- Create `src/atboffice/modules/spreadsheet/calc/fn_stat.py`:
  - Distributions & Inverses: `NORMDIST`, `NORMSDIST`, `NORMINV`, `NORMSINV`, `CONFIDENCE`, `POISSON`, `BINOMDIST`, `EXPONDIST`, `GAMMADIST`, `GAMMAINV`, `GAMMALN`, `CHIDIST`, `CHIINV`, `CHITEST`, `TDIST`, `TINV`, `TTEST`, `FDIST`, `FINV`, `FTEST`, `WEIBULL`, `BETADIST`, `BETAINV`, `HYPGEOMDIST`, `LOGNORMDIST`, `LOGINV`, `STANDARDIZE`, `ZTEST`
  - Rankings & Statistics: `LARGE`, `SMALL`, `RANK`, `RANK.EQ`, `RANK.AVG`, `PERCENTILE`, `PERCENTILE.INC`, `PERCENTILE.EXC`, `QUARTILE`, `QUARTILE.INC`, `QUARTILE.EXC`, `PERCENTRANK`, `PERCENTRANK.INC`, `PERCENTRANK.EXC`, `MEDIAN`, `MODE`, `MODE.SNGL`, `MODE.MULT`, `GEOMEAN`, `HARMEAN`, `TRIMMEAN`, `AVEDEV`, `DEVSQ`, `VAR`, `VARP`, `VARA`, `VARPA`, `VAR.S`, `VAR.P`, `STDEV`, `STDEVP`, `STDEVA`, `STDEVPA`, `STDEV.S`, `STDEV.P`, `KURT`, `SKEW`, `SKEW.P`
  - Regressions & Correlation: `CORREL`, `PEARSON`, `RSQ`, `COVAR`, `COVARIANCE.P`, `COVARIANCE.S`, `SLOPE`, `INTERCEPT`, `STEYX`, `FORECAST`, `TREND`, `GROWTH`, `LINEST`, `LOGEST`, `FREQUENCY`, `PROB`
  - Database functions: `DSUM`, `DAVERAGE`, `DCOUNT`, `DCOUNTA`, `DMAX`, `DMIN`, `DPRODUCT`, `DSTDEV`, `DSTDEVP`, `DVAR`, `DVARP`, `DGET`

### Task 6: Unify Function Registry & Guarantee 519 Coverage in `functions.py`
- Update `src/atboffice/modules/spreadsheet/calc/functions.py`:
  - Import and aggregate all function modules (`fn_core`, `fn_dynamic`, `fn_fin`, `fn_eng`, `fn_stat`)
  - Register any remaining catalog functions with appropriate stubs
  - Validate `len(FUNCTION_REGISTRY) == 519`
  - Update `src/atboffice/modules/spreadsheet/calc/__init__.py` exports

### Task 7: Comprehensive Unit Testing (`test_functions_advanced.py`)
- Create `tests/unit/spreadsheet/test_functions_advanced.py`
- Test cases:
  - 519 Registry validation
  - Dynamic array execution: `SEQUENCE`, `FILTER`, `UNIQUE`, `SORT`, `SORTBY`, `XLOOKUP`, `XMATCH`, `TEXTSPLIT`, `TEXTJOIN`
  - `LET`, `LAMBDA`, `MAP`, `REDUCE`, `BYROW`, `BYCOL`
  - Dynamic array spill and `#SPILL!` collision
  - Financial calculations (`PMT`, `PV`, `FV`, `NPV`, `IRR`, `XIRR`, `RATE`, etc.)
  - Engineering calculations (`BIN2DEC`, `DEC2HEX`, `BITAND`, `COMPLEX`, `CONVERT`, etc.)
  - Statistical & database calculations (`MEDIAN`, `STDEV`, `NORM.DIST`, `DSUM`, etc.)
- Run full pytest test suite and ensure 100% pass rate.
