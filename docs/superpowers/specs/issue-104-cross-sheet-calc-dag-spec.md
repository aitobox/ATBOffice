# Technical Specification - Issue #104: 跨工作表公式求解 (Sheet!Cell) 与 DAG 循环检测

## 1. Overview & Context

- **Issue**: #104 `[Phase 2] 跨工作表公式求解 (Sheet!Cell) 与 DAG 循环检测`
- **Parent Epic**: #96 `[Phase 2] ATBOffice 二期工程：1:1 完整全量移植与核心架构补完`
- **Sequence**: Step 8 of 16
- **Depends On**: #102 (`WorkbookModel` 多工作表容器架构)
- **Blocks**: Step 9 (XLSX Reader), Step 10 (Recalculation engine)
- **Reference**: 原版 `.vibeoffice/public/ledger/js/calc.js` (Lines 340-370, 810-1030)
- **Status**: Design Complete (>=90% Confidence Decision)

### Problem Statement
在电子表格实际使用与 XLSX 文件交换中，大量公式包含跨工作表单元格引用（如 `=Sheet2!A1 + 10`、`=SUM('Q1 Summary'!B5:D10)`、`='O''Reilly'!C3`）。当前 Python 侧的公式求值引擎（`evaluator.py` 与 `dag.py`）只支持当前单张表内部的单元格引用，且在遇到循环引用（如 `Sheet1!A1` 引用 `Sheet2!A1`，`Sheet2!A1` 引用 `Sheet1!A1`）时会导致 `RecursionError` 栈溢出崩溃。

必须打通：
1. 跨工作表引用解析与 AST 节点模型（`SheetReference`、单引号转义 `'Sheet''Name'!A1`）；
2. 公式求值引擎与 `WorkbookModel` / `SheetDataModel` 跨表数据获取打通；
3. 全局多工作表 `DependencyGraph` 拓扑排序与三色 DFS 死锁循环检测；
4. 发生循环引用时稳定输出 `#CYCLE!` / `#REF!` 错误码，彻底杜绝递归死循环或崩溃。

---

## 2. Pre-Implementation Reflection (Edge Case Analysis)

对标原版 `.vibeoffice/public/ledger/js/calc.js` 与 Excel 官方规范，系统必须完备处理以下边界条件：

1. **工作表名称转义与特殊字符**：
   - 标准未加引号名称：`Sheet2!A1`、`Data!B10`、中文字符表名 `销售数据!C5`。
   - 包含空格或连字符名称：`'Q1 Summary'!B5`、`'2026-Report'!A1`。
   - 包含单引号的名称：转义为成对单引号，如 `'O''Reilly'!A1`，解析后工作表名称应准确恢复为 `O'Reilly`。
   - 跨表范围引用：`'Data Sheet'!A1:B10`、`Sheet2!A:B`、`Sheet2!1:5`。
2. **工作表不存在与越界引用**：
   - 若引用的工作表在工作簿中不存在（例如 `=NoSuchSheet!A1`），公式求值应返回 `#REF!` 错误，不得抛出未捕获异常。
3. **循环引用与死锁防范**：
   - 直接环：`Sheet1!A1 = Sheet2!A1`，`Sheet2!A1 = Sheet1!A1`。
   - 间接多跳环：`Sheet1!A1 -> Sheet2!B2 -> Sheet3!C3 -> Sheet1!A1`。
   - 自引用：`Sheet1!A1 = Sheet1!A1 + 1`。
   - 范围包含自环：`Sheet1!A1 = SUM(Sheet1!A1:A5)`。
   - 求值引擎必须维护求值访问标记集合（`visiting` 状态），一旦检测到递归重入，立即熔断死锁并输出 `#CYCLE!`，严禁发生 Python `RecursionError`。
4. **工作簿级别数据桥接**：
   - `EvalContext` 能够直接绑定 `WorkbookModel` 实例，优先从当前绑定的工作簿容器中通过 `get_sheet_by_name(name)` 获取对应工作表模型，并访问其单元格。
5. **依赖图与拓扑排序**：
   - `CellAddress` 结构天然具备 `(sheet, r, c)` 三元组，`extract_precedents` 准确提取所有跨表依赖；
   - `topological_sort` 保证前置依赖单元格先于下游依赖单元格求值。

---

## 3. Architecture & Technical Specifications

### 3.1 跨表引用 AST 节点与解析 (`parser.py` & `tokens.py`)

#### `SheetReference` AST Node
在 `tokens.py` 与 `parser.py` 中定义并导出 `SheetReference(ASTNode)`：
```python
@dataclass
class SheetReference(ASTNode):
    sheet_name: str
    cell_range: str
    t: str = "sheet_ref"
    r: int = 0
    c: int = 0
    r1: int = 0
    c1: int = 0
    r2: int = 0
    c2: int = 0
    is_range: bool = False
    target: ASTNode | None = None
```
- 构造时根据 `cell_range` 自动解析出坐标属性（如果是单个单元格，填充 `r, c`；如果是区域，填充 `r1, c1, r2, c2` 并置 `is_range = True`）。
- 提供便捷工厂方法：
  - `parse_sheet_reference(text: str) -> SheetReference | None`：准确解析形如 `'Q1 Summary'!B5`、`'O''Reilly'!A1:B10`、`Sheet2!C3` 的字符串，反转义 `''` 为 `'`。
  - `CellRefNode` 与 `AreaRefNode` 增加 `.sheet_reference` 属性方便快速获取。

#### 单引号转义增强
- `parser.py` 中的 `tokenize` 逻辑完善对单引号包含工作表名、双单引号转义（`''`）的处理，支持含空格、符号和各类字符的表名。
- `references.py` 中的 `walk` 和 `map_ast` 支持遍历 `SheetReference` 节点。

---

### 3.2 错误类型扩充 (`errors.py`)

新增单例错误常量：
```python
CYCLE: Final[ExcelError] = ExcelError("#CYCLE!")
```
- 加入 `ALL_ERRORS` 和 `ERROR_MAP`；
- `parser.py` 的 `ERRORS` 列表加入 `"#CYCLE!"`。

---

### 3.3 计算上下文与工作簿绑定 (`context.py` & `evaluator.py`)

#### `EvalContext` 增强
```python
@dataclass
class EvalContext:
    cell_getter: Callable[[str, int, int], Any] | None = None
    date1904: bool = False
    array_mode: bool = False
    current_sheet: str = "Sheet1"
    current_row: int = 0
    current_col: int = 0
    workbook_data: dict[str, dict[tuple[int, int], Any]] = field(default_factory=dict)
    vars: dict[str, Any] = field(default_factory=dict)
    workbook: Any | None = None  # 支持绑定 WorkbookModel
    visiting: set[tuple[str, int, int]] = field(default_factory=set)  # 递归重入守卫
```
- `get_cell_value(sheet, r, c)` 策略：
  1. 检查 `(sheet.lower(), r, c)` 是否处于 `self.visiting`，若处于则检测到循环，立即返回 `CYCLE`。
  2. 若 `self.cell_getter` 存在，调用之。
  3. 若 `self.workbook` 存在：
     - 调用 `self.workbook.get_sheet_by_name(sheet)`；
     - 若未找到工作表，返回 `REF` 错误（`#REF!`）；
     - 若找到，获取对应单元格值（若包含待求值嵌套公式，在安全守卫下递归求值）。
  4. 检查 `self.workbook_data`（支持不区分大小写匹配）；
  5. 若绑定了 `workbook` 但均未命中，返回 `REF`。

#### `evaluator.py` 增强
- `evaluate_ast` 处理 `SheetReference` 与 `CellRefNode` 时：
  - 进入前将 `(sheet.lower(), r, c)` 登记到 `ctx.visiting`；
  - 若已在 `ctx.visiting` 中，直接短路返回 `CYCLE`；
  - 递归求值后在 `finally` 块中安全移出，杜绝死循环和 `RecursionError`。
- `evaluate(formula: str, ctx: EvalContext | None = None, workbook: Any | None = None) -> Any`：
  - 支持直接传参 `workbook`，自动包装上下文。

---

### 3.4 依赖图与全局循环检测 (`dag.py`)

#### `CellAddress` 与 AST 遍历
- `CellAddress` 为不可变三元组 `(sheet: str, r: int, c: int)`，哈希和相等性判断完整保留大小写规范；
- `extract_precedents` 增强识别 `SheetReference`，将跨表引用准确归档为跨表 `CellAddress` 或 `CellRange`。

#### 全局依赖重算与环路断开
- `DependencyGraph.detect_cycles`：三色标记法返回全部环路路径 `cycles: list[list[CellAddress]]` 与涉及单元格集合 `circular_cells: set[CellAddress]`；
- `DependencyGraph.recalculate(workbook: WorkbookModel, ctx: EvalContext | None = None)`：
  1. 扫描工作簿中所有包含公式的单元格，注册至图；
  2. 执行 `detect_cycles()`；
  3. 将所有位于 `circular_cells` 中的公式单元格赋值为 `CYCLE`；
  4. 对非环路单元格执行拓扑排序并按序计算，并将结果写回 `SheetDataModel`。

---

## 4. Acceptance Criteria & Test Plan

### Acceptance Criteria
- [ ] 准确计算跨表单元格引用（如 `=Sheet2!A1 + 10`）
- [ ] 准确计算带空格或特殊字符表名的公式（如 `='Q1 Summary'!B5 * 2`、`='O''Reilly'!C3 + 1`）
- [ ] 跨表循环引用（`Sheet1!A1` 引用 `Sheet2!A1`，`Sheet2!A1` 引用 `Sheet1!A1`）不发生死循环或栈溢出，稳定输出错误提示（`#CYCLE!`）
- [ ] 跨表范围聚合运算（如 `=SUM(Sheet2!A1:B5)`、`=AVERAGE('Data Sheet'!C1:C10)`）计算正确
- [ ] 引用不存在的工作表稳定输出 `#REF!`
- [ ] 编写并通过独立测试 `tests/modules/spreadsheet/test_cross_sheet_calc.py`
- [ ] 保持全库既有 125+ 个单元测试 100% 通过无回退

### Verification Command
```bash
PYTHONPATH=src conda run -n ATBOffice pytest tests/modules/spreadsheet/test_cross_sheet_calc.py -v
```
