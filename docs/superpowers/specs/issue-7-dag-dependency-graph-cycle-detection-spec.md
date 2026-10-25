# Specification: Issue #7 — [Ledger] DAG 依赖拓扑重算图、三色环路检测与迭代计算

## 1. Overview & Objective
实现电子表格引擎的核心——DAG（有向无环图）依赖追踪与拓扑重算调度引擎。
当单元格数据或公式变动时，仅重新计算依赖于它的下游脏单元格（dirty cells）；精确检测循环引用，支持返回 `#CIRCULAR!` 错误标记或在启用迭代计算时支持按步长（最大 100 步）收敛重算；通过 Kahn 算法及三色标记 DFS，确保在百万级单元格规模下依然能瞬间完成增量拓扑重算序列生成。

严格对齐 `.vibeoffice/public/ledger/js/calc.js` 中的依赖图设计、列分桶索引优化（column bucketing）、易失性函数处理（volatile functions）与循环处理规范。

---

## 2. Core Concepts & Architecture

### 2.1 依赖关系定义
- **Precedent（前置/被依赖者）**：公式计算所需的数据来源。如 `=A1+B1` 的前置为 `A1` 和 `B1`。
- **Dependent（后置/依赖者）**：依赖于某单元格的公式单元格。若 `C1 = A1 + B1`，则 `C1` 是 `A1` 和 `B1` 的 Dependent。
- **求值顺序（Evaluation Order）**：拓扑排序保证所有 Precedents 在其 Dependents 之前完成求值。

### 2.2 数据模型与分桶索引优化
在真实电子表格中，大量公式引用连续区域（例如 `SUM(A1:A10000)`），若对数万个单元格逐一建立点对点边，图规模将急剧膨胀。因此参照 `calc.js` 实现混合索引架构：
1. **点对点依赖（Direct Cell Dependencies）**：
   - `_cell_dependents: dict[CellAddress, set[CellAddress]]`：记录由单单元格引用（如 `A1`）产生的下游依赖。
   - `_precedents: dict[CellAddress, set[CellAddress | CellRange]]`：记录单元格的所有前置引用（包括单单元格与矩形区域）。
2. **列分桶区域依赖（Column Bucket Range Dependencies）**：
   - 对范围引用（如 `A1:B10`），按工作表列进行分桶存储：
     `_col_buckets[sheet][col] -> list[RangeEntry]`（其中 `RangeEntry` 包含 `(r1, r2, c1, c2, dependent_node)`）。
   - 对跨度超宽（如宽度 > 24 列或整行引用 `1:1`）的区域，存入 `_wide_buckets[sheet] -> list[RangeEntry]`。
   - 当单点 `(sheet, r, c)` 发生变动时：
     - 检索 `_cell_dependents[sheet, r, c]`
     - 检索 `_col_buckets[sheet][c]` 中满足 `r1 <= r <= r2` 的项
     - 检索 `_wide_buckets[sheet]` 中满足 `r1 <= r <= r2 and c1 <= c <= c2` 的项
     - 高效聚合并去重，时间复杂度对列内查找保持最优。
3. **易失性函数追踪（Volatile Functions）**：
   - `VOLATILE_FUNCTIONS = {"NOW", "TODAY", "RAND", "RANDBETWEEN", "RANDARRAY", "OFFSET", "INDIRECT", "CELL", "INFO"}`
   - 包含易失性函数的公式单元格登记至 `_volatile_cells: set[CellAddress]`。
   - 触发脏传递时，所有易失性单元格及其下游依赖均自动纳入重算集合。

### 2.3 脏子图传播（Dirty Invalidation）
- 当传入修改事件 `changes: list[Change]`（包含单单元格或区域变动）：
  - 收集直接受影响的单元格；
  - 若修改单元格本身包含公式，其自身首先标记为脏；
  - 将所有易失性单元格加入初始队列；
  - 使用 BFS 遍历沿下游依赖链递归传递脏标记（`dirty = True`），生成需要重算的最小诱导子图（Dirty Subgraph）。

### 2.4 三色标记 DFS 环路检测（Three-Color Cycle Detection）
- 节点状态定义：
  - `WHITE (0)`：未访问
  - `GRAY (1)`：当前 DFS 递归调用栈中正在访问的节点
  - `BLACK (2)`：已完全遍历且所有下游分支均已访问完成的节点
- 环路检测逻辑：
  - 在脏子图内进行 DFS 遍历；
  - 若在访问某节点的邻接下游节点时遇到 `GRAY` 节点，证明检测到回边（Back-edge），存在有向环路；
  - 提取环路路径并收集所有涉及循环引用的单元格集合 `circular_cells`。

### 2.5 拓扑排序与迭代计算收敛（Kahn's Algorithm & Iterative Calculation）
- **Kahn 算法拓扑排序**：
  - 计算脏子图内各节点的入度（In-degree，即脏子图内部前置节点数量）；
  - 入度为 0 的节点放入队列；
  - 依次出队并将其下游节点的入度减 1，入度归 0 则入队；
  - 正常情况下生成完全线性的拓扑求值顺序列表 `eval_order`。
- **循环引用与迭代计算控制**：
  - 若拓扑排序结束后 `len(eval_order) < len(dirty_nodes)`，说明存在无法解构的循环环路；
  - **非迭代模式（默认）**：
    - 环路中的节点被标记为 `#CIRCULAR!`（或在求值时赋予循环引用状态）；
    - 剩余无法排序的环内节点按自然物理顺序（工作表、行优先、列优先）排入序列末尾，避免流程卡死；
  - **迭代计算模式（Iterative Calculation Mode）**：
    - 配置参数：`iterative_enabled = True`，`max_iterations = 100`，`tolerance = 0.001`；
    - 在重算计划中输出 `is_iterative = True` 与迭代配置，供后续计算引擎执行定步长迭代直至收敛或达上限。

---

## 3. Public API Specification (`src/atboffice/modules/spreadsheet/calc/dag.py`)

### 3.1 核心数据结构
```python
from dataclasses import dataclass, field
from enum import IntEnum
from typing import NamedTuple

class Color(IntEnum):
    WHITE = 0
    GRAY = 1
    BLACK = 2

@dataclass(frozen=True, slots=True)
class CellAddress:
    sheet: str
    r: int
    c: int

@dataclass(frozen=True, slots=True)
class CellRange:
    sheet: str
    r1: int
    c1: int
    r2: int
    c2: int

@dataclass
class Change:
    sheet: str
    r: int | None = None
    c: int | None = None
    range: CellRange | None = None

@dataclass
class CycleReport:
    has_cycle: bool
    cycles: list[list[CellAddress]] = field(default_factory=list)
    circular_cells: set[CellAddress] = field(default_factory=set)

@dataclass
class RecalcPlan:
    dirty_nodes: list[CellAddress]
    eval_order: list[CellAddress]
    cycle_report: CycleReport
    is_iterative: bool = False
    max_iterations: int = 100
    tolerance: float = 0.001
```

### 3.2 `DependencyGraph` 类接口
```python
class DependencyGraph:
    def __init__(self, iterative_enabled: bool = False, max_iterations: int = 100, tolerance: float = 0.001): ...
    
    def set_cell_formula(self, sheet: str, r: int, c: int, formula: str | ASTNode) -> None: ...
    def remove_cell(self, sheet: str, r: int, c: int) -> None: ...
    def clear(self) -> None: ...
    
    def get_dependents(self, sheet: str, r: int, c: int) -> set[CellAddress]: ...
    def get_precedents(self, sheet: str, r: int, c: int) -> set[CellAddress | CellRange]: ...
    def get_direct_cell_precedents(self, sheet: str, r: int, c: int) -> set[CellAddress]: ...
    
    def invalidate(self, changes: list[Change | CellAddress | tuple]) -> list[CellAddress]: ...
    def detect_cycles(self, nodes: list[CellAddress] | None = None) -> CycleReport: ...
    def topological_sort(self, dirty_nodes: list[CellAddress]) -> list[CellAddress]: ...
    def get_recalc_plan(self, changes: list[Change | CellAddress | tuple]) -> RecalcPlan: ...
```

---

## 4. Verification Plan
通过 pytest 运行全面单元测试：
1. **测试直接与区域依赖建立**：
   - 单单元格依赖 `B1 = A1 * 2`，验证 `get_dependents("Sheet1", 0, 0)` 返回 `B1`。
   - 区域依赖 `C1 = SUM(A1:A5)`，验证修改 A1..A5 任意单元格均触发 C1。
2. **测试脏标记多层级传递**：
   - 链式传递 `A1 -> B1 -> C1 -> D1`，修改 A1 触发 B1, C1, D1。
3. **测试易失性函数**：
   - 包含 `NOW()` 的单元格在任意变动时均加入脏重算集合。
4. **测试三色标记环路检测**：
   - 自引用 `A1 = A1 + 1`；
   - 双单元格相互引用 `A1 = B1`, `B1 = A1`；
   - 多单元格环路 `A1 -> B1 -> C1 -> A1`；
   - 验证均能准确识别 `has_cycle = True` 并返回涉及的所有循环单元格。
5. **测试 Kahn 算法拓扑排序**：
   - 菱形依赖（Diamond Dependency）`A1 -> (B1, C1) -> D1`，验证求值顺序满足 `A1` 在前，`B1/C1` 在中，`D1` 在后。
6. **测试迭代计算配置**：
   - 当 `iterative_enabled = True` 时，循环引用生成迭代重算计划（max_iterations=100）。
