# Implementation Plan: Issue #6 — [Ledger] 公式词法分析器、Pratt 优先级 AST 解析与引用计算

## Task List

- [ ] **Task 1: Define AST Nodes, TokenType and ParseError in tokens.py**
  - Create `src/atboffice/modules/spreadsheet/calc/__init__.py`
  - Create `src/atboffice/modules/spreadsheet/calc/tokens.py`
  - Add AST dataclasses: `LiteralNode`, `CellRefNode`, `AreaRefNode`, `RefErrNode`, `NameNode`, `StructuredRefNode`, `UnaryOpNode`, `BinaryOpNode`, `PercentNode`, `FunctionCallNode`, `InvokeNode`, `ParenNode`, `UnionNode`, `ArrayNode`.
  - Add `ParseError` with error message and character position.
  - Create `tests/unit/spreadsheet/test_tokens.py` and verify AST creation and string representations.

- [ ] **Task 2: Implement Reference Parsing and Shift/Adjust Arithmetic in references.py**
  - Implement `col_name`, `col_index`, `cell_name`, `parse_cell`, `parse_range`, `range_name`, `abs_range_name`, `quote_sheet`.
  - Implement AST tree walking utilities `walk(ast, fn)` and `map_ast(ast, fn)`.
  - Implement reference operations:
    - `shift(ast, dr, dc, wrap=False)`: offset relative cell/area references, out-of-bounds become `#REF!`.
    - `translate(text, dr, dc)`: formula text translation across cells.
    - `adjust(ast, op, home=None)`: insert/delete rows/columns.
    - `adjust_move(ast, src, dr, dc, home, to_sheet)`: cut-and-paste range movement.
    - `rename_sheet(ast, from_name, to_name)`: sheet renaming/deletion.
    - `toggle_abs(text, sel_start, sel_end)`: F4 key cycle between absolute and relative.
  - Create `tests/unit/spreadsheet/test_references.py` testing A1/R1C1 conversion, offsets, insert/delete shifts, and F4 cycle.

- [ ] **Task 3: Implement Tokenizer, Pratt Precedence Parser and Serializer in parser.py**
  - Implement `tokenize(src: str) -> list[Token]`:
    - Handles whitespace, quoted strings, numbers (int, float, scientific), booleans, error codes, cell references (A1, $A$1, 1:1, A:A), ranges (`A1:B10`), sheet qualifiers (`'Sheet 1'!A1`, `Sheet1:Sheet3!A1`), spill `#`, structured references `[@Col]`, function names, operators.
  - Implement Pratt parsing algorithm `parse(text: str) -> ASTNode`:
    - Binary operators with proper precedence: Range `:` (9), Intersection ` ` (8), `^` (5, left-associative), `*`, `/` (4), `+`, `-` (3), `&` (2), comparisons `=`, `<>`, `<`, `<=`, `>`, `>=` (1).
    - Unary operators `-`, `+`, `@` (7).
    - Postfix `%` (6).
    - Array constants `{1, 2; 3, 4}`.
    - Function calls and missing arguments (`IF(A1,,B1)`).
    - Lambda immediate invocation (`LAMBDA(x, x+1)(2)`).
  - Implement serializer `to_text(ast, store=False) -> str`, `display(text) -> str`, `to_store(text) -> str`.
  - Create `tests/unit/spreadsheet/test_parser.py` with comprehensive parser and serializer test cases.

- [ ] **Task 4: Export Calc APIs & Run Full Verification Suite**
  - Expose `parse`, `try_parse`, `to_text`, `translate`, `shift`, `adjust`, `toggle_abs`, `col_name`, `col_index`, `parse_cell`, `parse_range` in `calc/__init__.py`.
  - Run `pytest tests/unit/spreadsheet/ -v`
  - Run full repository test suite to guarantee zero regressions.
