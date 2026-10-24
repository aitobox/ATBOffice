# Specification: Issue #6 — [Ledger] 公式词法分析器、Pratt 优先级 AST 解析与引用计算

## 1. Overview & Objective
移植 Excel 2003 / Modern Excel 公式词法与语法分析引擎至 Python 3.12+ / PySide6 环境。
将公式文本（如 `=SUM(A1:B10) + 5 * $C$2`）精准解析为强类型的抽象语法树（AST），并提供完整的单元格/区域地址运算、相对与绝对引用偏移调整（shift / translate）、结构变更调整（row/column insert/delete）、剪切移动调整（adjust_move）以及 F4 循环绝对引用切换（toggle_abs）。

严格对齐 `.vibeoffice/public/ledger/js/formula.js` 的行为语义与边界处理。

---

## 2. Architecture & Modules

### 2.1 `src/atboffice/modules/spreadsheet/calc/tokens.py`
- 定义 Token 类型（`TokenType` 枚举）与 `Token` 数据类。
  - 支持类型：`ws`（空白）, `num`（数字）, `str`（字符串）, `bool`（布尔）, `err`（错误码如 `#REF!`, `#VALUE!`）, `ref`（单元格/区域引用）, `name`（定义名称）, `fn`（函数名+开括号）, `struct`（结构化表引用）, `spill`（动态数组溢出 `#`）, `op`（运算符）, 标点 `(`, `)`, `{`, `}`, `,`, `;`。
- 定义 `ParseError`（继承自 `Exception`），记录解析错误信息与字符位置 `pos`。
- 定义强类型 AST 节点（dataclasses）：
  - `LiteralNode` (num, str, bool, err, missing)
  - `CellRefNode` (`r`, `c`, `ra`, `ca`, `sheet`, `sheet2`, `book`)
  - `AreaRefNode` (`r1`, `c1`, `r2`, `c2`, `ra1`, `ca1`, `ra2`, `ca2`, `sheet`, `sheet2`, `book`, `kind`)
  - `RefErrNode` (`sheet`, `sheet2`, `book`)
  - `NameNode` (`name`, `sheet`, `book`, `param`)
  - `StructuredRefNode` (`table`, `spec`, `sheet`)
  - `UnaryOpNode` (`op`, `operand`)
  - `BinaryOpNode` (`op`, `left`, `right`)
  - `PercentNode` (`operand`)
  - `FunctionCallNode` (`name`, `args`, `raw`, `udf`)
  - `InvokeNode` (`fn`, `args`)
  - `ParenNode` (`child`)
  - `UnionNode` (`items`)
  - `ArrayNode` (`rows`)

### 2.2 `src/atboffice/modules/spreadsheet/calc/references.py`
- 常量定义：`MAXR = 1048576`, `MAXC = 16384`。
- 列名与数字索引互相转换：`col_name(c: int) -> str`, `col_index(s: str) -> int`。
- 单元格坐标格式化与解析：`cell_name(r, c, ra, ca) -> str`, `parse_cell(s: str) -> dict | None`。
- 区域格式化与解析：`parse_range(s: str) -> dict | None`, `range_name(rg) -> str`, `abs_range_name(rg) -> str`。
- 工作表名称引用转义：`quote_sheet(name: str) -> str`。
- AST 遍历与变换：`walk(ast, fn)`, `map_ast(ast, fn)`。
- 引用计算：
  - `shift(ast, dr, dc, wrap=False) -> ASTNode`
  - `translate(text: str, dr: int, dc: int) -> str`
  - `adjust(ast, op: dict, home: str | None = None) -> tuple[ASTNode, bool]`
  - `adjust_move(ast, src: dict, dr: int, dc: int, home: str | None, to_sheet: str | None) -> tuple[ASTNode, bool]`
  - `rename_sheet(ast, from_name: str, to_name: str | None) -> tuple[ASTNode, bool]`
  - `toggle_abs(text: str, sel_start: int, sel_end: int) -> dict | None` (F4 键循环切换)

### 2.3 `src/atboffice/modules/spreadsheet/calc/parser.py`
- 词法分析器 `tokenize(src: str) -> list[Token]`：
  - 处理空白、转义引号字符串、Excel 错误常量、Spill `#`、单元格与区域引用匹配（A1, $A$1, A:A, 1:1, A1:B10）、结构化引用 `[@Col]`、带工作表前缀 `'Sheet 1'!A1` 与跨簿引用 `[Book.xlsx]Sheet1!A1`、3D 跨表引用 `Sheet1:Sheet3!A1:B10`。
- Pratt 优先级语法分析器：
  - 优先级表：
    - `:` 范围（9）
    - ` ` 交集（8）
    - 一元 `-`, `+`, `@`（7）
    - `%` 百分比（6）
    - `^` 乘方（5，左结合）
    - `*`, `/` 乘除（4）
    - `+`, `-` 加减（3）
    - `&` 字符串连接（2）
    - `=`, `<`, `>`, `<=`, `>=`, `<>` 比较（1）
- 序列化与格式转换：
  - `to_text(ast, store: bool = False) -> str`
  - `display(text: str) -> str`
  - `to_store(text: str) -> str`
  - `parse(text: str, opts: dict | None = None) -> ASTNode`
  - `try_parse(text: str, opts: dict | None = None) -> tuple[ASTNode | None, Exception | None]`

---

## 3. Edge Cases & Reliability Guarantees
1. **边界范围检查**：任何偏移导致行列小于 0 或超出 MAXR/MAXC 范围的单元格或区域，自动转为 `#REF!` 错误节点。
2. **整行整列支持**：支持 `A:A`, `2:2`, `$A:$C`, `$1:$10`，整行偏移只调整行，整列偏移只调整列。
3. **空参数支持**：如 `=IF(A1,,B1)` 中间遗漏的参数生成 `MissingNode`，转换为文本时保持 `=IF(A1,,B1)`。
4. **数组常量校验**：`{1, 2; 3, 4}` 必须保证每一行元素个数严格一致，且只允许常量，非法输入抛出 `ParseError`。
5. **单元格跨工作表引用单引号转义**：工作表名包含单引号时按 `''` 转义（如 `'O''Reilly'!A1`）。
