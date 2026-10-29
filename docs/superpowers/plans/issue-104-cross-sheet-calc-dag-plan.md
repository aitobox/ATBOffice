# Implementation Plan - Issue #104: 跨工作表公式求解 (Sheet!Cell) 与 DAG 循环检测

## Overview
本计划指导完成 Issue #104 的全量实现与单元测试。
核心任务：打通跨表解析（`SheetReference`、单引号及转义）、打通公式求值引擎与 `WorkbookModel` 跨表数据获取、实现全局循环检测与死锁熔断（返回 `#CYCLE!` / `#REF!`）、升级 `DependencyGraph` 多表拓扑排序与重算。

---

## Task Breakdown

### Task 1: 错误类型扩展与单例注册
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/errors.py`
  - `src/atboffice/modules/spreadsheet/calc/parser.py`
  - `src/atboffice/modules/spreadsheet/calc/__init__.py`
- **Actions**:
  - 在 `errors.py` 中增加 `CYCLE: Final[ExcelError] = ExcelError("#CYCLE!")`
  - 将 `CYCLE` 加入 `ALL_ERRORS` 和 `ERROR_MAP`
  - 在 `parser.py` 的 `ERRORS` 列表中追加 `"#CYCLE!"`
  - 在 `calc/__init__.py` 中导出 `CYCLE`

### Task 2: 跨表引用 AST 节点与解析增强
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/tokens.py`
  - `src/atboffice/modules/spreadsheet/calc/parser.py`
  - `src/atboffice/modules/spreadsheet/calc/references.py`
  - `src/atboffice/modules/spreadsheet/calc/__init__.py`
- **Actions**:
  - 在 `tokens.py` 中定义 `SheetReference(ASTNode)`，支持 `sheet_name`, `cell_range`, `r, c`, `r1, c1, r2, c2`, `is_range`
  - 在 `parser.py` 中实现 `parse_sheet_reference(text: str) -> SheetReference | None`，支持转义单引号 `'O''Reilly'!A1` 和特殊字符表名
  - 在 `references.py` 中的 `walk` 和 `map_ast` 中增加对 `SheetReference` 的遍历与映射支持
  - 在 `CellRefNode` 与 `AreaRefNode` 中添加 `.sheet_reference` 便捷属性

### Task 3: 计算上下文与工作簿绑定及重入死锁守卫
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/context.py`
- **Actions**:
  - 在 `EvalContext` 中新增 `workbook: Any | None = None` 与 `visiting: set[tuple[str, int, int]]` 属性
  - 在 `with_vars` 中透传 `workbook` 与 `visiting`
  - 增强 `get_cell_value(sheet, r, c)`：
    - 若 `(sheet.lower(), r, c)` 已在 `visiting` 中，直接返回 `CYCLE`
    - 若存在 `self.workbook`，通过 `workbook.get_sheet_by_name(sheet)` 获取工作表模型；若表不存在返回 `REF`；若存在获取单元格值
    - 兼容 `self.workbook_data` 的不区分大小写匹配

### Task 4: 求值引擎跨表支持与递归死锁熔断
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/evaluator.py`
- **Actions**:
  - 在 `evaluate_ast` 中处理 `SheetReference` 节点
  - 在 `evaluate_ast` 中对 `CellRefNode` 和 `SheetReference` 添加 `ctx.visiting` 登记与 `finally: ctx.visiting.discard`，避免栈溢出
  - 增强 `evaluate(formula, ctx=None, workbook=None)`，支持直接传入 `workbook`
  - 跨表范围引用（`AreaRefNode` / `SheetReference` 区域）正确绑定指定工作表，传递给 `SUM`、`AVERAGE` 等聚合函数

### Task 5: 依赖图跨表依赖抽取与拓扑重算
- **Files**:
  - `src/atboffice/modules/spreadsheet/calc/dag.py`
  - `src/atboffice/modules/spreadsheet/calc/__init__.py`
- **Actions**:
  - 在 `extract_precedents` 中识别 `SheetReference` 节点，提取 `CellAddress` 或 `CellRange`
  - 在 `DependencyGraph` 中增加 `recalculate(workbook, ctx=None)` 方法，支持跨工作表扫描公式单元格、拓扑排序、循环检测与批量重算
  - 遇到死锁环路时将环路单元格精准标记为 `CYCLE`

### Task 6: 编写独立全量测试套件
- **Files**:
  - `tests/modules/spreadsheet/test_cross_sheet_calc.py`
- **Test Scenarios**:
  1. 准确计算跨表单元格引用（如 `=Sheet2!A1 + 10`）
  2. 准确计算带空格或特殊字符表名的公式（如 `='Q1 Summary'!B5 * 2`、`='O''Reilly'!C3 + 1`）
  3. 跨表循环引用（`Sheet1!A1` 引用 `Sheet2!A1`，`Sheet2!A1` 引用 `Sheet1!A1`）不发生死循环或栈溢出，稳定输出错误提示（`#CYCLE!`）
  4. 跨表范围聚合运算（`SUM(Sheet2!A1:B5)`、`AVERAGE('Data Sheet'!C1:C10)`）
  5. 跨表不存在报错（`=NoSuchSheet!A1` -> `#REF!`）
  6. `SheetReference` AST 节点解析、属性计算与反向序列化
  7. 多工作表三级级联更新拓扑重算（Sheet3 引用 Sheet2，Sheet2 引用 Sheet1）

### Task 7: 全库回归验证与代码审查准备
- **Actions**:
  - 运行 `pytest tests/modules/spreadsheet/test_cross_sheet_calc.py -v`
  - 运行 `pytest tests/ -v` 验证无任何既有测试破坏
  - 将状态机流转至 `reviewing`
