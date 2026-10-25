# Specification: [Ledger] 基础与高频核心工作表函数库实现 (Issue #8)

## 1. 概述与背景 (Overview)
本规范对应 GitHub Issue #8: `[Ledger] 基础与高频核心工作表函数库实现`。
在已完成的词法/AST语法解析器 (#6) 与 DAG 依赖拓扑重算图 (#7) 基础之上，实现日常办公高频核心工作表函数集合（覆盖 90% 以上日常表格使用场景）。

严格对照本地 `.vibeoffice/public/ledger/js/` 原始代码：
- `fn-core.js` (数学、逻辑、文本、日期基础函数与标量隐式转换)
- `fn-stat.js` (统计函数与多条件汇总)
- `fn-lookup.js` (经典查找与引用函数)
- `calc.js` (Criteria 判别器、Wildcard 正则转换、Arr/Ref 内存表达)
- `numfmt.js` (Excel 1900/1904 历法序数换算与 15 位有效浮点精度)

---

## 2. 架构设计与模块分层 (Architecture)

```
src/atboffice/modules/spreadsheet/calc/
├── tokens.py        # 已存在：AST 节点定义
├── references.py    # 已存在：单元格/区域坐标换算
├── parser.py        # 已存在：公式解析与反序列化
├── dag.py           # 已存在：DAG 与重算拓扑
├── errors.py        # 新增：标准 Excel 错误类型与判断 (XErr / ERR)
├── context.py       # 新增：Ref, Arr, EvalContext 运行时内存数据结构
├── coercion.py      # 新增：类型强制转换、通配符正则、Criteria 判别器、日期序列号转换
├── functions.py     # 新增：函数注册表、参数适配器与全部 50+ 核心工作表函数实现
└── evaluator.py     # 新增：AST 公式求值引擎与函数分发调度器
```

### 2.1 错误类型设计 (`errors.py`)
定义不可变单例错误类型 `ExcelError`：
- `#NULL!`
- `#DIV/0!`
- `#VALUE!`
- `#REF!`
- `#NAME?`
- `#NUM!`
- `#N/A`
提供辅助函数 `is_error(val) -> bool`。

### 2.2 运行时计算上下文与数据结构 (`context.py`)
- `Arr`: 2D 二维矩阵容器 `Arr(data: list[list[Any]])`，包含 `rows`, `cols`, `get(r, c)`。
- `Ref`: 单表矩形区域引用 `Ref(sheet, r1, c1, r2, c2, getter=...)`，支持 `rows`, `cols`, `cell_value(r, c)`。
- `EvalContext`: 求值上下文，挂载 `cell_getter(sheet, r, c)`、`date1904: bool`、`array_mode: bool`。

### 2.3 强制类型转换与条件匹配引擎 (`coercion.py`)
1. **隐式标量转换**：
   - `to_num(val, default=None)`: 遵循 Excel 规则，布尔值 `TRUE -> 1`, `FALSE -> 0`；数值直接返回；字符串根据浮点/百分比/千分位解析，不符合规范返回 `#VALUE!`。
   - `to_bool(val)`: 遵循 Excel 规则，`0 -> False`, 非 0 数字 -> `True`；`"TRUE" -> True`, `"FALSE" -> False`；其余字符串返回 `#VALUE!`。
   - `to_str(val)`: 遵循 Excel 规则，浮点数保留至多 15 位有效数字，布尔值转为 `"TRUE"` / `"FALSE"`。
2. **通配符转正则表达式** (`wildcard_to_regex`):
   - 支持 `*` 匹配任意多个字符。
   - 支持 `?` 匹配单个字符。
   - 支持 `~*`, `~?`, `~~` 转义自身。
3. **Criteria 条件判别器** (`build_criteria_matcher`):
   - 解析比较运算符前缀: `=`, `<>`, `<`, `>`, `<=`, `>=`。
   - 缺省前缀为 `=`。
   - 支持数值比对、文本大小写不敏感匹配、通配符正则匹配、布尔值比对、空单元格比对。
4. **Excel 日期序列号换算** (`date_to_serial`, `serial_to_parts`):
   - 完整还原 Excel 1900 闰年缺陷（1900-02-29 为序列号 60，1900-01-01 为序列号 1）。
   - 支持 1904 历法系统切换。

---

## 3. 核心函数清单与行为规范 (`functions.py`)

### 3.1 数学与三角函数 (Math & Trig)
1. `SUM(*args)`: 对数字求和。区域中的文本/空值忽略；直接传入的非数值字面量报错 `#VALUE!`。
2. `SUMIF(range, criteria, [sum_range])`: 按 criteria 匹配筛选并累加对应 sum_range 区域数值。
3. `SUMIFS(sum_range, criteria_range1, criteria1, ...)`: 多条件与逻辑求和。
4. `ROUND(number, num_digits)`: 四舍五入到指定小数位（15位浮点稳定性）。
5. `ROUNDUP(number, num_digits)`: 绝对值向上舍入。
6. `ROUNDDOWN(number, num_digits)`: 绝对值向下舍入。
7. `ABS(number)`: 绝对值。
8. `INT(number)`: 向下取整到最接近的整数 (`INT(-1.5) == -2`)。
9. `MOD(number, divisor)`: 求余，除数为 0 返回 `#DIV/0!`。符号与除数一致。
10. `PRODUCT(*args)`: 所有数字的乘积。
11. `POWER(number, power)`: 幂运算。
12. `SQRT(number)`: 平方根，负数返回 `#NUM!`。
13. `SUBTOTAL(function_num, ref1, ...)`: 嵌套汇总计算，忽略区域内的嵌套 SUBTOTAL。

### 3.2 统计函数 (Statistical)
1. `AVERAGE(*args)`: 算术平均值，若无数字返回 `#DIV/0!`。
2. `AVERAGEIF(range, criteria, [average_range])`: 单条件平均值。
3. `AVERAGEIFS(average_range, criteria_range1, criteria1, ...)`: 多条件平均值。
4. `COUNT(*args)`: 统计数字个数。
5. `COUNTA(*args)`: 统计非空单元格个数。
6. `COUNTBLANK(range)`: 统计空白单元格个数。
7. `COUNTIF(range, criteria)`: 单条件计数。
8. `COUNTIFS(criteria_range1, criteria1, ...)`: 多条件计数。
9. `MAX(*args)`: 最大值。
10. `MIN(*args)`: 最小值。

### 3.3 查找与引用函数 (Lookup & Reference)
1. `VLOOKUP(lookup_value, table_array, col_index, [range_lookup])`: 垂直查表。精确匹配 (0/FALSE) 与近视二分匹配 (1/TRUE)，支持通配符。
2. `HLOOKUP(lookup_value, table_array, row_index, [range_lookup])`: 水平查表。
3. `INDEX(array, row_num, [column_num], [area_num])`: 区域索引。
4. `MATCH(lookup_value, lookup_array, [match_type])`: 查找项在一维向量中的相对位置（1-based）。
5. `LOOKUP(lookup_value, lookup_vector, [result_vector])`: 经典单行/单列或两向量近似查找。
6. `CHOOSE(index_num, value1, [value2], ...)`: 索引选择分支。

### 3.4 逻辑与错误处理 (Logical & Error)
1. `IF(logical_test, [value_if_true], [value_if_false])`: 惰性分支求值。
2. `IFS(logical_test1, value_if_true1, ...)`: 多条件顺序判断，无匹配返回 `#N/A`。
3. `AND(*args)`: 逻辑与，遇错返回错误。
4. `OR(*args)`: 逻辑或。
5. `NOT(logical)`: 逻辑非。
6. `SWITCH(expression, val1, result1, ..., [default])`: 多重条件匹配。
7. `IFERROR(value, value_if_error)`: 异常捕获保护。
8. `IFNA(value, value_if_na)`: 仅针对 `#N/A` 的异常捕获保护。

### 3.5 文本函数 (Text)
1. `CONCAT(*args)`: 区域与字符串拼接。
2. `CONCATENATE(*args)`: 标量拼接。
3. `LEFT(text, [num_chars])`: 从左侧截取字符。
4. `RIGHT(text, [num_chars])`: 从右侧截取字符。
5. `MID(text, start_num, num_chars)`: 从指定位置截取字符（1-based）。
6. `LEN(text)`: 字符串长度。
7. `TRIM(text)`: 清除前后空格并将多空格压缩为单个空格。
8. `UPPER(text)`: 转大写。
9. `LOWER(text)`: 转小写。
10. `SUBSTITUTE(text, old_text, new_text, [instance_num])`: 替换文本，支持指定出现序号。

### 3.6 日期与时间函数 (Date & Time)
1. `DATE(year, month, day)`: 组合为 Excel 序列号，支持月份/日期溢出自动结转。
2. `YEAR(serial_number)`: 提取年份。
3. `MONTH(serial_number)`: 提取月份 (1-12)。
4. `DAY(serial_number)`: 提取日期 (1-31)。
5. `TODAY()`: 当前系统日期的整天序列号。
6. `NOW()`: 当前系统日期加时间的浮点序列号。
7. `DATEDIF(start_date, end_date, unit)`: 日期差值计算，支持 "Y", "M", "D", "MD", "YM", "YD"。
8. `WEEKDAY(serial_number, [return_type])`: 星期几计算，支持 return_type 1, 2, 3 等常用参数。

---

## 4. 边界处理与容错分析 (Think One Step Ahead)
1. **除以零与无效数值**：
   - `MOD(x, 0)`、`SQRT(-1)` 等必须抛出对应的 `ExcelError("#DIV/0!")` 或 `ExcelError("#NUM!")`，严禁 Python 原始 ZeroDivisionError / ValueError 泄露。
2. **文本与数值混合聚合**：
   - 在 `SUM(A1:B10)` 等区域引用中，纯文本单元格被忽略；但在 `SUM("12", 3)` 中直接传入的数字文本被转换为数值计算，非数字字符串直接报错 `#VALUE!`。
3. **通配符转义**：
   - 如 `COUNTIF(A1:A5, "apple~*")` 必须正确匹配字面量 `"apple*"`，而不是匹配 `"apple"` 开头的所有字符串。
4. **跨表与未赋值单元格**：
   - 引用未初始化的空白单元格视为空值（在数值聚合中按 0 计算，在文本查找中视为空字符串）。
5. **查找越界**：
   - `VLOOKUP` 列索引超过数据范围返回 `#REF!`，找不到返回 `#N/A`。

---

## 5. 验收标准与测试计划 (Verification)
运行命令：
```bash
PYTHONPATH=src conda run -n ATBOffice python -m pytest tests/unit/spreadsheet/test_functions_core.py -v
```
测试用例覆盖全部 6 大类、50 多个函数的核心行为与所有边界情况。
全工程回归测试用例全部通过，零 regression。
