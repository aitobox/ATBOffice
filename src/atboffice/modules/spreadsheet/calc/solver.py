"""Ledger Constrained Solver (规划求解): Simplex LP, MIP B&B, GRG Nonlinear, Evolutionary DE."""

from __future__ import annotations

import heapq
import logging
import math
import random
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.dag import CellAddress, DependencyGraph
from atboffice.modules.spreadsheet.calc.errors import is_error
from atboffice.modules.spreadsheet.calc.evaluator import evaluate_ast
from atboffice.modules.spreadsheet.calc.goal_seek import parse_cell_reference
from atboffice.modules.spreadsheet.calc.grid_spill import apply_spill
from atboffice.modules.spreadsheet.calc.parser import parse
from atboffice.modules.spreadsheet.calc.references import (
    MAXC,
    MAXR,
    cell_name,
    parse_cell,
    quote_sheet,
)
from atboffice.modules.spreadsheet.calc.tokens import ASTNode
from atboffice.modules.spreadsheet.models.sheet_model import CellData

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

logger = logging.getLogger(__name__)

SolverGoal = Literal["max", "min", "value_of"]
SolverMethod = Literal["simplex_lp", "grg_nonlinear", "evolutionary"]
ConstraintOp = Literal["<=", "=", ">=", "int", "bin", "dif"]

_MAX_RANGE_CELLS = 10000
_RE_QUOTED_SHEET_REF = re.compile(r"^'((?:[^']|'')+)'!(.+)$")
_RE_UNQUOTED_SHEET_REF = re.compile(r"^([A-Za-z0-9_.\-]+)!(.+)$")


@dataclass
class SolverConstraint:
    """Single solver constraint specification."""

    lhs_ref: str
    op: ConstraintOp
    rhs: str = ""


@dataclass
class SolverOptions:
    """Algorithmic options controlling solver convergence and limits."""

    max_iterations: int = 200
    max_time_sec: float = 30.0
    precision: float = 1e-6
    integer_optimality: float = 0.01
    population_size: int = 40
    random_seed: int = 42


@dataclass
class SolverParams:
    """Complete solver problem definition."""

    objective_ref: str
    goal: SolverGoal = "max"
    target_value: float = 0.0
    variable_refs: str = ""
    constraints: list[SolverConstraint] = field(default_factory=list)
    make_unconstrained_non_negative: bool = True
    method: SolverMethod = "simplex_lp"
    default_sheet: str = "Sheet1"
    options: SolverOptions = field(default_factory=SolverOptions)


@dataclass
class ConstraintReportItem:
    """Evaluated constraint status row for Answer Report and UI."""

    cell_ref: str
    formula: str
    cell_value: float
    op: ConstraintOp
    rhs_value: str
    binding: bool
    slack: float


@dataclass
class SolverResult:
    """Outcome of a solver execution."""

    success: bool
    status: str
    message: str
    iterations: int
    objective_ref: str
    initial_objective: float
    final_objective: float
    initial_values: dict[str, float]
    solution_values: dict[str, float]
    constraint_reports: list[ConstraintReportItem]
    elapsed_sec: float


def _get_sheet(workbook: Any, name: str) -> Any:
    """Look up sheet by name (case-insensitive) or return None."""
    if hasattr(workbook, "get_sheet_by_name"):
        return workbook.get_sheet_by_name(name)
    target = name.strip().lower()
    for s in getattr(workbook, "sheets", []):
        if getattr(s, "name", "").lower() == target:
            return s
    return None


def _split_quoted_commas(text: str) -> list[str]:
    """Split a reference list by commas outside single quotes."""
    parts: list[str] = []
    buf: list[str] = []
    in_quotes = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            buf.append(ch)
            if in_quotes and i + 1 < n and text[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            parts.append("".join(buf).strip())
            buf.clear()
        else:
            buf.append(ch)
        i += 1
    if in_quotes:
        raise ValueError(f"Unterminated quote in reference list: '{text}'.")
    tail = "".join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return parts


def _split_sheet_prefix(token: str, default_sheet: str) -> tuple[str, str]:
    """Split optional Sheet! prefix (supporting escaped '' in quoted names)."""
    m_q = _RE_QUOTED_SHEET_REF.match(token)
    if m_q:
        sheet = m_q.group(1).replace("''", "'")
        return sheet, m_q.group(2).strip()
    m_u = _RE_UNQUOTED_SHEET_REF.match(token)
    if m_u:
        return m_u.group(1), m_u.group(2).strip()
    if "!" in token:
        raise ValueError(f"Invalid sheet reference format: '{token}'.")
    return default_sheet, token


def _parse_single_cell(ref: str, default_sheet: str = "Sheet1") -> tuple[str, int, int]:
    """Parse a single cell reference with support for quoted/escaped sheet names."""
    clean = str(ref).strip()
    if not clean:
        raise ValueError("Empty cell reference.")
    sheet, cell_part = _split_sheet_prefix(clean, default_sheet)
    parsed = parse_cell(cell_part)
    if parsed is not None:
        return sheet, int(parsed["r"]), int(parsed["c"])
    return parse_cell_reference(clean, default_sheet=default_sheet)


def parse_cell_list(refs_str: str, default_sheet: str = "Sheet1") -> list[tuple[str, int, int]]:
    """Parse comma-separated cell/range references into deduplicated (sheet, r, c) tuples."""
    clean_all = str(refs_str or "").strip()
    if not clean_all:
        return []

    tokens = _split_quoted_commas(clean_all)
    result: list[tuple[str, int, int]] = []
    seen: set[tuple[str, int, int]] = set()

    for tok in tokens:
        if not tok:
            raise ValueError(f"Empty token in cell list: '{refs_str}'.")
        sheet, body = _split_sheet_prefix(tok, default_sheet)
        if ":" in body:
            parts = body.split(":", 1)
            p1 = parse_cell(parts[0].strip())
            if p1 is None:
                raise ValueError(f"Invalid range start '{tok}'.")
            right_raw = parts[1].strip()
            if "!" in right_raw:
                right_sheet, right_cell = _split_sheet_prefix(right_raw, sheet)
                if right_sheet != sheet:
                    raise ValueError(f"Cross-sheet range not supported: '{tok}'.")
                p2 = parse_cell(right_cell)
            else:
                p2 = parse_cell(right_raw)
            if p2 is None:
                raise ValueError(f"Invalid range end '{tok}'.")

            r1, r2 = min(int(p1["r"]), int(p2["r"])), max(int(p1["r"]), int(p2["r"]))
            c1, c2 = min(int(p1["c"]), int(p2["c"])), max(int(p1["c"]), int(p2["c"]))
            if r2 >= MAXR or c2 >= MAXC:
                raise ValueError(f"Range out of bounds: '{tok}'.")
            if (r2 - r1 + 1) * (c2 - c1 + 1) > _MAX_RANGE_CELLS:
                raise ValueError(f"Range exceeds maximum cell limit: '{tok}'.")
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    coord = (sheet, r, c)
                    if coord not in seen:
                        seen.add(coord)
                        result.append(coord)
        else:
            parsed = parse_cell(body)
            if parsed is None:
                raise ValueError(f"Invalid cell reference: '{tok}'.")
            coord = (sheet, int(parsed["r"]), int(parsed["c"]))
            if coord not in seen:
                seen.add(coord)
                result.append(coord)

    return result


def format_cell_ref(sheet: str, r: int, c: int, default_sheet: str | None = None) -> str:
    """Format (sheet, r, c) as A1 or Sheet!A1 notation."""
    coord = cell_name(r, c)
    if default_sheet is not None and sheet == default_sheet:
        return coord
    return f"{quote_sheet(sheet)}!{coord}"


def _to_numeric(val: Any) -> float | None:
    """Convert cell value to finite float, or None if invalid/error/bool."""
    if val is None or val == "" or isinstance(val, bool):
        return None
    if isinstance(val, str) and is_error(val):
        return None
    if isinstance(val, (int, float)):
        fval = float(val)
        return fval if math.isfinite(fval) else None
    try:
        fval = float(val)
        return fval if math.isfinite(fval) else None
    except (TypeError, ValueError):
        return None


def _parse_numeric_literal(text: str) -> float | None:
    """Parse a numeric RHS string (supports optional trailing %)."""
    s = text.strip()
    if not s:
        return None
    try:
        if s.endswith("%"):
            val = float(s[:-1].strip()) / 100.0
        else:
            val = float(s)
        return val if math.isfinite(val) else None
    except ValueError:
        return None


@dataclass
class _CompiledConstraint:
    """Normalized internal scalar or AllDifferent constraint."""

    kind: Literal["<=", "=", ">=", "int", "bin", "dif"]
    lhs_coords: list[tuple[str, int, int]]
    rhs_coord: tuple[str, int, int] | None = None
    rhs_const: float | None = None
    rhs_display: str = ""
    var_indices: list[int] = field(default_factory=list)


class _WorkbookEvaluator:
    """Fast incremental spreadsheet evaluator with guaranteed state restoration."""

    def __init__(
        self,
        workbook: WorkbookModel,
        var_coords: list[tuple[str, int, int]],
        watch_coords: list[tuple[str, int, int]],
    ) -> None:
        self.workbook = workbook
        self.var_coords = var_coords
        self.watch_coords = watch_coords
        self.ctx = EvalContext(workbook=workbook)
        self.graph = DependencyGraph()

        self._saved_sheets_dirty: dict[str, bool] = {}
        self._saved_cells: list[tuple[Any, int, int, bool, Any, Any]] = []
        self._var_cells: list[CellData] = []
        self._eval_nodes: list[tuple[CellAddress, Any, CellData, ASTNode]] = []
        self._has_volatile = False

    def prepare(self) -> tuple[bool, str | None]:
        """Snapshot initial state, build dependency graph, check cycles, compile ASTs."""
        for sh in getattr(self.workbook, "sheets", []):
            self._saved_sheets_dirty[sh.name] = bool(getattr(sh, "dirty", False))

        for sh_name, r, c in self.var_coords:
            sh = _get_sheet(self.workbook, sh_name)
            if sh is None:
                return False, safe_tr("可变单元格引用无效：{0}", sh_name)
            existing = sh.get_cell(r, c)
            if existing is None:
                self._saved_cells.append((sh, r, c, False, None, None))
                cell = CellData(value=0.0)
                sh.set_cell(r, c, cell)
                self._var_cells.append(cell)
            else:
                self._saved_cells.append((sh, r, c, True, existing.value, existing.spill_origin))
                if existing.value is None or existing.value == "":
                    existing.value = 0.0
                self._var_cells.append(existing)

        cycle_report = self.graph.recalculate(self.workbook, self.ctx)
        if cycle_report.has_cycle:
            return False, safe_tr("模型中存在循环引用，无法进行规划求解。")

        plan = self.graph.get_recalc_plan([CellAddress(sh, r, c) for sh, r, c in self.var_coords])
        if plan.cycle_report.has_cycle:
            return False, safe_tr("模型中存在循环引用，无法进行规划求解。")

        self._has_volatile = bool(self.graph._volatile_cells)
        for addr in plan.eval_order:
            sh = _get_sheet(self.workbook, addr.sheet)
            if sh is None:
                continue
            cell = sh.get_cell(addr.r, addr.c)
            if cell is None or not cell.formula:
                continue
            ast = parse(cell.formula)
            if ast is None:
                continue
            self._eval_nodes.append((addr, sh, cell, ast))

        return True, None

    def restore(self) -> None:
        """Restore every modified cell and recalculate workbook to initial state."""
        try:
            for sh, r, c, existed, orig_val, orig_spill in self._saved_cells:
                if existed:
                    cell = sh.get_cell(r, c)
                    if cell is not None:
                        cell.value = orig_val
                        cell.spill_origin = orig_spill
                else:
                    sh.cells.pop((r, c), None)
            self.graph.recalculate(self.workbook, self.ctx)
        finally:
            for sh in getattr(self.workbook, "sheets", []):
                if sh.name in self._saved_sheets_dirty:
                    sh.dirty = self._saved_sheets_dirty[sh.name]

    def evaluate_vector(self, x: list[float]) -> tuple[bool, dict[tuple[str, int, int], float]]:
        """Write x into variable cells, recalculate dependents, and read watch_coords."""
        for cell, val in zip(self._var_cells, x, strict=True):
            cell.value = float(val)

        if self._has_volatile:
            self.graph.recalculate(self.workbook, self.ctx)
        else:
            spill_moved = False
            for addr, sh, cell, ast in self._eval_nodes:
                self.ctx.current_sheet = addr.sheet
                self.ctx.current_row = addr.r
                self.ctx.current_col = addr.c
                try:
                    res = evaluate_ast(ast, self.ctx)
                    is_err = is_error(res) or (
                        isinstance(res, str)
                        and res.startswith("#")
                        and (res.endswith("!") or res.endswith("?"))
                    )
                    if is_err:
                        cell.value = res
                    else:
                        cell.value, moved = apply_spill(sh, addr.r, addr.c, res)
                        spill_moved = spill_moved or moved
                except Exception as exc:
                    logger.debug("Formula evaluation error at %s: %s", addr, exc)
                    return False, {}
            if spill_moved:
                self.graph.recalculate(self.workbook, self.ctx)

        out: dict[tuple[str, int, int], float] = {}
        for sh_name, r, c in self.watch_coords:
            sh = _get_sheet(self.workbook, sh_name)
            if sh is None:
                return False, {}
            raw = sh.get_cell_value(r, c)
            num = _to_numeric(raw)
            if num is None:
                return False, {}
            out[(sh_name, r, c)] = num
        return True, out


class _CancelledError(Exception):
    """Internal signal for cooperative cancellation."""


class _TimeLimitError(Exception):
    """Internal signal for solver time limit expiration."""


def _canonical_coord(
    workbook: WorkbookModel, coord: tuple[str, int, int]
) -> tuple[str, int, int] | None:
    """Resolve sheet name to its canonical SheetDataModel.name."""
    sh = _get_sheet(workbook, coord[0])
    if sh is None:
        return None
    return (sh.name, coord[1], coord[2])


def _validate_and_compile(
    workbook: WorkbookModel, params: SolverParams
) -> tuple[
    tuple[str, int, int] | None,
    list[tuple[str, int, int]],
    list[float],
    list[_CompiledConstraint],
    str | None,
]:
    """Validate objective, variables, and constraints; return normalized structures or error."""
    # 1. Objective cell
    try:
        raw_obj = _parse_single_cell(params.objective_ref, params.default_sheet)
    except ValueError:
        return None, [], [], [], safe_tr("目标单元格或公式引用无效：{0}", params.objective_ref)

    obj_coord = _canonical_coord(workbook, raw_obj)
    if obj_coord is None:
        return None, [], [], [], safe_tr("目标单元格或公式引用无效：{0}", params.objective_ref)

    obj_sh = _get_sheet(workbook, obj_coord[0])
    obj_cell = obj_sh.get_cell(obj_coord[1], obj_coord[2]) if obj_sh is not None else None
    if obj_cell is None or not obj_cell.formula:
        return (
            None,
            [],
            [],
            [],
            safe_tr("目标单元格 {0} 必须包含公式。", params.objective_ref),
        )

    # 2. Variable cells
    try:
        raw_vars = parse_cell_list(params.variable_refs, params.default_sheet)
    except ValueError:
        return None, [], [], [], safe_tr("可变单元格引用无效：{0}", params.variable_refs)

    if not raw_vars:
        return None, [], [], [], safe_tr("必须至少指定一个可变单元格。")

    var_coords: list[tuple[str, int, int]] = []
    var_index_map: dict[tuple[str, int, int], int] = {}
    initial_vec: list[float] = []

    for raw_v in raw_vars:
        v_coord = _canonical_coord(workbook, raw_v)
        if v_coord is None:
            return None, [], [], [], safe_tr("可变单元格引用无效：{0}", params.variable_refs)
        if v_coord == obj_coord:
            return (
                None,
                [],
                [],
                [],
                safe_tr("可变单元格不能与目标单元格 {0} 重合。", params.objective_ref),
            )
        if v_coord in var_index_map:
            continue
        v_sh = _get_sheet(workbook, v_coord[0])
        v_cell = v_sh.get_cell(v_coord[1], v_coord[2])
        if v_cell is not None and v_cell.formula:
            v_ref = format_cell_ref(*v_coord, params.default_sheet)
            return None, [], [], [], safe_tr("可变单元格 {0} 不能包含公式。", v_ref)
        if v_cell is None or v_cell.value is None or v_cell.value == "":
            init_val = 0.0
        else:
            num = _to_numeric(v_cell.value)
            if num is None:
                v_ref = format_cell_ref(*v_coord, params.default_sheet)
                return None, [], [], [], safe_tr("可变单元格引用无效：{0}", v_ref)
            init_val = num

        var_index_map[v_coord] = len(var_coords)
        var_coords.append(v_coord)
        initial_vec.append(init_val)

    # 3. Constraints
    compiled: list[_CompiledConstraint] = []
    for c in params.constraints:
        try:
            raw_lhs = parse_cell_list(c.lhs_ref, params.default_sheet)
        except ValueError:
            return None, [], [], [], safe_tr("约束条件引用无效：{0}", c.lhs_ref)
        if not raw_lhs:
            return None, [], [], [], safe_tr("约束条件引用无效：{0}", c.lhs_ref)

        lhs_coords: list[tuple[str, int, int]] = []
        for item in raw_lhs:
            canon = _canonical_coord(workbook, item)
            if canon is None:
                return None, [], [], [], safe_tr("约束条件引用无效：{0}", c.lhs_ref)
            lhs_coords.append(canon)

        if c.op in ("int", "bin"):
            indices: list[int] = []
            for coord in lhs_coords:
                if coord not in var_index_map:
                    ref_s = format_cell_ref(*coord, params.default_sheet)
                    if c.op == "int":
                        return None, [], [], [], safe_tr("整数约束只能应用于可变单元格：{0}", ref_s)
                    return None, [], [], [], safe_tr("二元约束只能应用于可变单元格：{0}", ref_s)
                indices.append(var_index_map[coord])
            compiled.append(
                _CompiledConstraint(
                    kind=c.op,
                    lhs_coords=lhs_coords,
                    rhs_display="",
                    var_indices=indices,
                )
            )
            continue

        if c.op == "dif":
            if len(lhs_coords) < 2:
                return None, [], [], [], safe_tr("约束条件引用无效：{0}", c.lhs_ref)
            indices = [var_index_map[coord] for coord in lhs_coords if coord in var_index_map]
            compiled.append(
                _CompiledConstraint(
                    kind="dif",
                    lhs_coords=lhs_coords,
                    rhs_display="",
                    var_indices=indices,
                )
            )
            continue

        # Algebraic constraint: <=, =, >=
        rhs_text = str(c.rhs or "").strip()
        num_rhs = _parse_numeric_literal(rhs_text)
        if num_rhs is not None:
            for coord in lhs_coords:
                compiled.append(
                    _CompiledConstraint(
                        kind=c.op,
                        lhs_coords=[coord],
                        rhs_const=num_rhs,
                        rhs_display=rhs_text,
                    )
                )
            continue

        try:
            raw_rhs = parse_cell_list(rhs_text, params.default_sheet)
        except ValueError:
            return None, [], [], [], safe_tr("约束条件引用无效：{0}", rhs_text)
        if not raw_rhs:
            return None, [], [], [], safe_tr("约束条件引用无效：{0}", rhs_text)

        rhs_coords: list[tuple[str, int, int]] = []
        for item in raw_rhs:
            canon = _canonical_coord(workbook, item)
            if canon is None:
                return None, [], [], [], safe_tr("约束条件引用无效：{0}", rhs_text)
            rhs_coords.append(canon)

        if len(rhs_coords) == 1:
            rc = rhs_coords[0]
            rhs_disp = format_cell_ref(*rc, params.default_sheet)
            for coord in lhs_coords:
                compiled.append(
                    _CompiledConstraint(
                        kind=c.op,
                        lhs_coords=[coord],
                        rhs_coord=rc,
                        rhs_display=rhs_disp,
                    )
                )
        elif len(rhs_coords) == len(lhs_coords):
            for lc, rc in zip(lhs_coords, rhs_coords, strict=True):
                compiled.append(
                    _CompiledConstraint(
                        kind=c.op,
                        lhs_coords=[lc],
                        rhs_coord=rc,
                        rhs_display=format_cell_ref(*rc, params.default_sheet),
                    )
                )
        else:
            return None, [], [], [], safe_tr("约束条件引用无效：{0}", rhs_text)

    return obj_coord, var_coords, initial_vec, compiled, None


# ---------------------------------------------------------------------------
# Simplex LP + Branch-and-Bound MILP
# ---------------------------------------------------------------------------


@dataclass
class _SimplexTableauInfo:
    """Final Simplex tableau metadata used for LP sensitivity analysis."""

    tableau: list[list[float]]
    basis: list[int]
    obj2: list[float]
    total_cols: int
    active_cols: int
    id_cols: list[int]
    row_flips: list[float]
    dropped_rows: set[int]


def _simplex_solve_with_tableau(
    c_vec: list[float],
    rows: list[tuple[list[float], Literal["<=", "=", ">="], float]],
    max_pivots: int = 2000,
    eps_piv: float = 1e-9,
    eps_rc: float = 1e-8,
    eps_feas: float = 1e-6,
) -> tuple[
    Literal["optimal", "infeasible", "unbounded", "max_iterations"],
    list[float],
    float,
    int,
    _SimplexTableauInfo | None,
]:
    """Solve min c^T y subject to A y {<=, =, >=} b, y >= 0 and return final tableau."""
    n_vars = len(c_vec)
    m = len(rows)
    if m == 0:
        # Unconstrained y >= 0
        for cj in c_vec:
            if cj < -eps_rc:
                return "unbounded", [0.0] * n_vars, float("-inf"), 0, None
        obj2_empty = list(c_vec) + [0.0]
        return (
            "optimal",
            [0.0] * n_vars,
            0.0,
            0,
            _SimplexTableauInfo(
                tableau=[],
                basis=[],
                obj2=obj2_empty,
                total_cols=n_vars,
                active_cols=n_vars,
                id_cols=[],
                row_flips=[],
                dropped_rows=set(),
            ),
        )

    # Normalize RHS >= 0 and determine slack/surplus/artificial variables
    norm_rows: list[tuple[list[float], str, float]] = []
    row_flips: list[float] = []
    n_slack = 0
    n_surplus = 0
    n_art = 0
    for coeffs, op, rhs in rows:
        row_c = list(coeffs)
        cur_op = op
        cur_rhs = rhs
        flip = 1.0
        if cur_rhs < 0.0:
            row_c = [-v for v in row_c]
            cur_rhs = -cur_rhs
            flip = -1.0
            if cur_op == "<=":
                cur_op = ">="
            elif cur_op == ">=":
                cur_op = "<="
        row_flips.append(flip)
        if cur_op == "<=":
            n_slack += 1
        elif cur_op == ">=":
            n_surplus += 1
            n_art += 1
        else:
            n_art += 1
        norm_rows.append((row_c, cur_op, cur_rhs))

    total_cols = n_vars + n_slack + n_surplus + n_art
    slack_start = n_vars
    surplus_start = slack_start + n_slack
    art_start = surplus_start + n_surplus

    # Build tableau: rows 0..m-1 are constraints, last col is RHS
    tableau: list[list[float]] = [[0.0] * (total_cols + 1) for _ in range(m)]
    basis: list[int] = [-1] * m
    art_cols: set[int] = set()
    id_cols: list[int] = [-1] * m

    s_idx = 0
    e_idx = 0
    a_idx = 0
    for i, (row_c, cur_op, cur_rhs) in enumerate(norm_rows):
        for j in range(n_vars):
            tableau[i][j] = row_c[j]
        tableau[i][total_cols] = cur_rhs
        if cur_op == "<=":
            col = slack_start + s_idx
            tableau[i][col] = 1.0
            basis[i] = col
            id_cols[i] = col
            s_idx += 1
        elif cur_op == ">=":
            e_col = surplus_start + e_idx
            a_col = art_start + a_idx
            tableau[i][e_col] = -1.0
            tableau[i][a_col] = 1.0
            basis[i] = a_col
            id_cols[i] = a_col
            art_cols.add(a_col)
            e_idx += 1
            a_idx += 1
        else:
            a_col = art_start + a_idx
            tableau[i][a_col] = 1.0
            basis[i] = a_col
            id_cols[i] = a_col
            art_cols.add(a_col)
            a_idx += 1

    pivots = 0

    def do_pivot(piv_row: int, piv_col: int, obj_rows: list[list[float]]) -> None:
        nonlocal pivots
        pivots += 1
        piv_val = tableau[piv_row][piv_col]
        inv = 1.0 / piv_val
        prow = tableau[piv_row]
        for k in range(len(prow)):
            prow[k] *= inv
        prow[piv_col] = 1.0

        for r_i, row in enumerate(tableau):
            if r_i == piv_row:
                continue
            factor = row[piv_col]
            if abs(factor) > 1e-15:
                for k in range(len(row)):
                    row[k] -= factor * prow[k]
                row[piv_col] = 0.0

        for obj in obj_rows:
            factor = obj[piv_col]
            if abs(factor) > 1e-15:
                for k in range(len(obj)):
                    obj[k] -= factor * prow[k]
                obj[piv_col] = 0.0

        basis[piv_row] = piv_col

    def run_simplex_phase(
        obj: list[float], active_cols: int, extra_objs: list[list[float]]
    ) -> Literal["optimal", "unbounded", "max_iterations"]:
        degen_count = 0
        all_objs = [obj] + extra_objs
        while pivots < max_pivots:
            use_bland = degen_count >= 25
            enter_col = -1
            if use_bland:
                for j in range(active_cols):
                    if obj[j] < -eps_rc:
                        enter_col = j
                        break
            else:
                best_rc = -eps_rc
                for j in range(active_cols):
                    if obj[j] < best_rc:
                        best_rc = obj[j]
                        enter_col = j

            if enter_col == -1:
                return "optimal"

            leave_row = -1
            min_ratio = float("inf")
            for i in range(len(tableau)):
                a_ij = tableau[i][enter_col]
                if a_ij > eps_piv:
                    rhs_val = max(0.0, tableau[i][total_cols])
                    ratio = rhs_val / a_ij
                    if ratio < min_ratio - 1e-12:
                        min_ratio = ratio
                        leave_row = i
                    elif abs(ratio - min_ratio) <= 1e-12 and leave_row != -1:
                        if basis[i] < basis[leave_row]:
                            leave_row = i

            if leave_row == -1:
                return "unbounded"

            if min_ratio <= 1e-12:
                degen_count += 1
            else:
                degen_count = 0

            do_pivot(leave_row, enter_col, all_objs)

        return "max_iterations"

    # Maintain Phase II objective row: obj2[0..n_vars-1] = c_vec, obj2[total_cols] = -z
    obj2 = [0.0] * (total_cols + 1)
    for j in range(n_vars):
        obj2[j] = c_vec[j]

    dropped_rows: set[int] = set()
    active_cols = total_cols
    if n_art > 0:
        # Phase I objective: minimize sum of artificial variables
        obj1 = [0.0] * (total_cols + 1)
        for a_col in art_cols:
            obj1[a_col] = 1.0
        for i in range(m):
            if basis[i] in art_cols:
                row = tableau[i]
                for k in range(total_cols + 1):
                    obj1[k] -= row[k]
                obj1[basis[i]] = 0.0

        status1 = run_simplex_phase(obj1, total_cols, [obj2])
        if status1 == "max_iterations":
            return "max_iterations", [0.0] * n_vars, 0.0, pivots, None

        # Phase I value is -obj1[total_cols]
        w_val = -obj1[total_cols]
        if w_val > eps_feas:
            return "infeasible", [0.0] * n_vars, 0.0, pivots, None

        # Drive remaining zero-valued artificial variables out of basis or drop redundant rows
        non_art_cols = art_start
        active_cols = non_art_cols
        rows_to_drop: list[int] = []
        for i in range(m):
            if basis[i] in art_cols:
                piv_c = -1
                best_abs = eps_piv
                for j in range(non_art_cols):
                    if abs(tableau[i][j]) > best_abs:
                        best_abs = abs(tableau[i][j])
                        piv_c = j
                if piv_c != -1:
                    do_pivot(i, piv_c, [obj2])
                else:
                    rows_to_drop.append(i)

        dropped_rows.update(rows_to_drop)
        for r_idx in reversed(rows_to_drop):
            tableau.pop(r_idx)
            basis.pop(r_idx)

        # Eliminate any basic non-artificial variable's cost from obj2 just in case
        for i, b_col in enumerate(basis):
            if b_col < non_art_cols and abs(obj2[b_col]) > 1e-12:
                factor = obj2[b_col]
                row = tableau[i]
                for k in range(total_cols + 1):
                    obj2[k] -= factor * row[k]
                obj2[b_col] = 0.0

        status2 = run_simplex_phase(obj2, non_art_cols, [])
    else:
        status2 = run_simplex_phase(obj2, total_cols, [])

    if status2 == "unbounded":
        return "unbounded", [0.0] * n_vars, float("-inf"), pivots, None
    if status2 == "max_iterations":
        return "max_iterations", [0.0] * n_vars, 0.0, pivots, None

    sol = [0.0] * n_vars
    for i, b_col in enumerate(basis):
        if 0 <= b_col < n_vars:
            val = tableau[i][total_cols]
            sol[b_col] = 0.0 if abs(val) < 1e-12 else val

    obj_val = -obj2[total_cols]
    info = _SimplexTableauInfo(
        tableau=tableau,
        basis=basis,
        obj2=obj2,
        total_cols=total_cols,
        active_cols=active_cols,
        id_cols=id_cols,
        row_flips=row_flips,
        dropped_rows=dropped_rows,
    )
    return "optimal", sol, obj_val, pivots, info


def _simplex_solve(
    c_vec: list[float],
    rows: list[tuple[list[float], Literal["<=", "=", ">="], float]],
    max_pivots: int = 2000,
    eps_piv: float = 1e-9,
    eps_rc: float = 1e-8,
    eps_feas: float = 1e-6,
) -> tuple[
    Literal["optimal", "infeasible", "unbounded", "max_iterations"],
    list[float],
    float,
    int,
]:
    """Solve min c^T y subject to A y {<=, =, >=} b, y >= 0 using Two-Phase Simplex."""
    status, sol, obj_val, pivots, _ = _simplex_solve_with_tableau(
        c_vec,
        rows,
        max_pivots=max_pivots,
        eps_piv=eps_piv,
        eps_rc=eps_rc,
        eps_feas=eps_feas,
    )
    return status, sol, obj_val, pivots


def _solve_bounded_lp_with_info(
    c_obj: list[float],
    c_const: float,
    linear_rows: list[tuple[list[float], Literal["<=", "=", ">="], float]],
    lower_bounds: list[float | None],
    upper_bounds: list[float | None],
    max_pivots: int = 2000,
) -> tuple[
    Literal["optimal", "infeasible", "unbounded", "max_iterations"],
    list[float],
    float,
    int,
    list[tuple[str, float, int, int]],
    _SimplexTableauInfo | None,
]:
    """Solve min c_obj^T x + c_const and also return variable mapping + final tableau."""
    n = len(c_obj)
    for j in range(n):
        lb = lower_bounds[j]
        ub = upper_bounds[j]
        if lb is not None and ub is not None and lb > ub + 1e-7:
            return "infeasible", [0.0] * n, 0.0, 0, [], None

    mapping: list[tuple[str, float, int, int]] = []
    y_costs: list[float] = []
    const_shift = c_const
    extra_rows: list[tuple[list[float], Literal["<=", "=", ">="], float]] = []

    y_count = 0
    for j in range(n):
        lb = lower_bounds[j]
        ub = upper_bounds[j]
        if lb is not None:
            idx = y_count
            y_count += 1
            y_costs.append(c_obj[j])
            const_shift += c_obj[j] * lb
            mapping.append(("lb", lb, idx, -1))
            if ub is not None:
                extra_rows.append(([0.0] * idx + [1.0], "<=", max(0.0, ub - lb)))
        elif ub is not None:
            idx = y_count
            y_count += 1
            y_costs.append(-c_obj[j])
            const_shift += c_obj[j] * ub
            mapping.append(("ub", ub, idx, -1))
        else:
            idx_p = y_count
            idx_n = y_count + 1
            y_count += 2
            y_costs.append(c_obj[j])
            y_costs.append(-c_obj[j])
            mapping.append(("free", 0.0, idx_p, idx_n))

    y_rows: list[tuple[list[float], Literal["<=", "=", ">="], float]] = []
    for row_a, op, rhs in linear_rows:
        y_a = [0.0] * y_count
        rhs_adj = rhs
        for j in range(n):
            a_j = row_a[j]
            if abs(a_j) <= 1e-15:
                continue
            kind, offset, i1, i2 = mapping[j]
            if kind == "lb":
                y_a[i1] += a_j
                rhs_adj -= a_j * offset
            elif kind == "ub":
                y_a[i1] -= a_j
                rhs_adj -= a_j * offset
            else:
                y_a[i1] += a_j
                y_a[i2] -= a_j
        y_rows.append((y_a, op, rhs_adj))

    for partial_a, op, rhs in extra_rows:
        padded = partial_a + [0.0] * (y_count - len(partial_a))
        y_rows.append((padded, op, rhs))

    status, y_sol, y_obj, pivots, tab_info = _simplex_solve_with_tableau(
        y_costs, y_rows, max_pivots=max_pivots
    )
    if status != "optimal":
        return status, [0.0] * n, y_obj, pivots, mapping, None

    x_sol = [0.0] * n
    for j in range(n):
        kind, offset, i1, i2 = mapping[j]
        if kind == "lb":
            x_sol[j] = offset + y_sol[i1]
        elif kind == "ub":
            x_sol[j] = offset - y_sol[i1]
        else:
            x_sol[j] = y_sol[i1] - y_sol[i2]

    return "optimal", x_sol, y_obj + const_shift, pivots, mapping, tab_info


def _solve_bounded_lp(
    c_obj: list[float],
    c_const: float,
    linear_rows: list[tuple[list[float], Literal["<=", "=", ">="], float]],
    lower_bounds: list[float | None],
    upper_bounds: list[float | None],
    max_pivots: int = 2000,
) -> tuple[
    Literal["optimal", "infeasible", "unbounded", "max_iterations"],
    list[float],
    float,
    int,
]:
    """Solve min c_obj^T x + c_const with optional variable lower/upper bounds."""
    status, x_sol, obj_val, pivots, _, _ = _solve_bounded_lp_with_info(
        c_obj, c_const, linear_rows, lower_bounds, upper_bounds, max_pivots=max_pivots
    )
    return status, x_sol, obj_val, pivots


def _extract_linear_model(
    evaluator: _WorkbookEvaluator,
    obj_coord: tuple[str, int, int],
    constraints: list[_CompiledConstraint],
    initial_vec: list[float],
    non_negative: bool,
) -> tuple[
    bool,
    str | None,
    list[float],
    float,
    list[tuple[list[float], Literal["<=", "=", ">="], float]],
]:
    """Verify linearity by numerical probing and extract exact linear coefficients."""
    n = len(initial_vec)
    # Collect scalar output functions: index 0 is objective; 1..k are algebraic constraints
    alg_constraints = [c for c in constraints if c.kind in ("<=", "=", ">=")]

    def eval_outputs(x: list[float]) -> tuple[bool, list[float]]:
        ok, vals = evaluator.evaluate_vector(x)
        if not ok:
            return False, []
        out = [vals[obj_coord]]
        for c in alg_constraints:
            lhs_val = vals[c.lhs_coords[0]]
            rhs_val = vals[c.rhs_coord] if c.rhs_coord is not None else float(c.rhs_const or 0.0)
            out.append(lhs_val - rhs_val)
        return True, out

    # Positive base point avoids division by 0 or log/sqrt domain issues at 0
    base = [1.0 + 0.11 * j for j in range(n)]
    ok0, f_base = eval_outputs(base)
    if not ok0:
        return False, safe_tr("公式计算出现错误，无法继续求解。"), [], 0.0, []

    m_out = len(f_base)
    jac: list[list[float]] = [[0.0] * n for _ in range(m_out)]

    # Forward and backward steps verify zero diagonal curvature (e.g. x^2, 1/x, sqrt)
    for j in range(n):
        p_plus = list(base)
        p_plus[j] += 1.0
        ok_p, f_plus = eval_outputs(p_plus)
        nonlin_msg = safe_tr("线性规划模型不满足线性条件，请改用 GRG 非线性或演化方法。")
        if not ok_p:
            return False, nonlin_msg, [], 0.0, []

        p_minus = list(base)
        p_minus[j] -= 0.5
        ok_m, f_minus = eval_outputs(p_minus)
        if not ok_m:
            return False, nonlin_msg, [], 0.0, []

        for r_i in range(m_out):
            slope_p = f_plus[r_i] - f_base[r_i]
            slope_m = (f_base[r_i] - f_minus[r_i]) / 0.5
            scale = max(1.0, abs(slope_p), abs(slope_m), abs(f_base[r_i]))
            if abs(slope_p - slope_m) > 1e-6 * scale:
                return (
                    False,
                    safe_tr("线性规划模型不满足线性条件，请改用 GRG 非线性或演化方法。"),
                    [],
                    0.0,
                    [],
                )
            jac[r_i][j] = slope_p

    # Multi-variable probes catch bilinear cross-terms (x*y) & piecewise thresholds (IF/MAX/ABS)
    probe_points: list[list[float]] = [
        [0.13 + 0.07 * ((j * 3 + 1) % 7) for j in range(n)],
        [12.7 + 3.1 * ((j * 5 + 2) % 11) for j in range(n)],
        [250.0 + 17.3 * j for j in range(n)],
        list(initial_vec),
    ]
    if not non_negative:
        probe_points.append([-2.3 - 0.41 * j for j in range(n)])

    for q in probe_points:
        ok_q, f_q = eval_outputs(q)
        if not ok_q:
            return (
                False,
                safe_tr("线性规划模型不满足线性条件，请改用 GRG 非线性或演化方法。"),
                [],
                0.0,
                [],
            )
        for r_i in range(m_out):
            pred = f_base[r_i] + sum(jac[r_i][j] * (q[j] - base[j]) for j in range(n))
            scale = max(
                1.0,
                abs(f_q[r_i]),
                abs(pred),
                sum(abs(jac[r_i][j] * q[j]) for j in range(n)),
            )
            if abs(f_q[r_i] - pred) > 1e-6 * scale:
                return (
                    False,
                    safe_tr("线性规划模型不满足线性条件，请改用 GRG 非线性或演化方法。"),
                    [],
                    0.0,
                    [],
                )

    # Extract exact constant offsets (prefer evaluating at 0 if finite)
    ok_zero, f_zero = eval_outputs([0.0] * n)
    consts = [
        (f_zero[r_i] if ok_zero else f_base[r_i] - sum(jac[r_i][j] * base[j] for j in range(n)))
        for r_i in range(m_out)
    ]

    obj_coeffs = jac[0]
    obj_const = consts[0]
    linear_rows: list[tuple[list[float], Literal["<=", "=", ">="], float]] = []
    for idx, c in enumerate(alg_constraints):
        # g(x) = coeffs^T x + const <= / = / >= 0  ==>  coeffs^T x op -const
        op_lit: Literal["<=", "=", ">="] = c.kind  # type: ignore[assignment]
        linear_rows.append((jac[idx + 1], op_lit, -consts[idx + 1]))

    return True, None, obj_coeffs, obj_const, linear_rows


def _run_simplex_lp(
    evaluator: _WorkbookEvaluator,
    params: SolverParams,
    obj_coord: tuple[str, int, int],
    var_coords: list[tuple[str, int, int]],
    initial_vec: list[float],
    constraints: list[_CompiledConstraint],
    cancel_check: Callable[[], bool] | None,
    progress_cb: Callable[[int, float], None] | None,
    start_time: float,
) -> tuple[bool, str, str, list[float], int]:
    """Run Simplex LP (and Branch-and-Bound for int/bin)."""
    if any(c.kind == "dif" for c in constraints):
        return (
            False,
            "non_linear",
            safe_tr("全部不同约束仅支持 GRG 非线性或演化求解方法。"),
            list(initial_vec),
            0,
        )

    ok_lin, err_msg, obj_coeffs, obj_const, linear_rows = _extract_linear_model(
        evaluator, obj_coord, constraints, initial_vec, params.make_unconstrained_non_negative
    )
    if not ok_lin:
        status = "error" if err_msg == safe_tr("公式计算出现错误，无法继续求解。") else "non_linear"
        return False, status, err_msg or "", list(initial_vec), 0

    n = len(var_coords)
    base_lb: list[float | None] = [0.0 if params.make_unconstrained_non_negative else None] * n
    base_ub: list[float | None] = [None] * n
    int_indices: set[int] = set()
    bin_indices: set[int] = set()

    for c in constraints:
        if c.kind == "int":
            int_indices.update(c.var_indices)
        elif c.kind == "bin":
            for idx in c.var_indices:
                bin_indices.add(idx)
                int_indices.add(idx)
                base_lb[idx] = 0.0 if base_lb[idx] is None else max(base_lb[idx], 0.0)
                base_ub[idx] = 1.0 if base_ub[idx] is None else min(base_ub[idx], 1.0)

    # Transform goal to minimization of min_c^T x + min_const
    if params.goal == "max":
        min_c = [-v for v in obj_coeffs]
        min_const = -obj_const
    elif params.goal == "min":
        min_c = list(obj_coeffs)
        min_const = obj_const
    else:
        # value_of: add equality constraint f(x) = target_value and minimize 0
        linear_rows.append((list(obj_coeffs), "=", params.target_value - obj_const))
        min_c = [0.0] * n
        min_const = 0.0

    def to_reported_obj(min_val: float) -> float:
        return -min_val if params.goal == "max" else min_val

    max_pivots = max(500, params.options.max_iterations * 10)
    if not int_indices:
        if cancel_check and cancel_check():
            raise _CancelledError()
        lp_status, sol, obj_val, pivots = _solve_bounded_lp(
            min_c, min_const, linear_rows, base_lb, base_ub, max_pivots=max_pivots
        )
        if progress_cb:
            progress_cb(pivots, to_reported_obj(obj_val) if lp_status == "optimal" else 0.0)
        if lp_status == "optimal":
            return (
                True,
                "optimal",
                safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
                sol,
                pivots,
            )
        if lp_status == "infeasible":
            return (
                False,
                "infeasible",
                safe_tr("规划求解找不到可行解，请检查约束条件。"),
                list(initial_vec),
                pivots,
            )
        if lp_status == "unbounded":
            return (
                False,
                "unbounded",
                safe_tr("目标单元格的值没有收敛（模型无界）。"),
                list(initial_vec),
                pivots,
            )
        return (
            False,
            "max_iterations",
            safe_tr("规划求解在达到最大迭代次数或时间限制前未能收敛。"),
            list(initial_vec),
            pivots,
        )

    # Branch-and-Bound for MILP
    ordered_ints = sorted(int_indices)
    root_status, root_x, root_obj, total_pivots = _solve_bounded_lp(
        min_c, min_const, linear_rows, base_lb, base_ub, max_pivots=max_pivots
    )
    if root_status == "infeasible":
        return (
            False,
            "infeasible",
            safe_tr("规划求解找不到可行解，请检查约束条件。"),
            list(initial_vec),
            total_pivots,
        )
    if root_status == "unbounded":
        return (
            False,
            "unbounded",
            safe_tr("目标单元格的值没有收敛（模型无界）。"),
            list(initial_vec),
            total_pivots,
        )
    if root_status == "max_iterations":
        return (
            False,
            "max_iterations",
            safe_tr("规划求解在达到最大迭代次数或时间限制前未能收敛。"),
            list(initial_vec),
            total_pivots,
        )

    def find_branch_var(x: list[float]) -> int | None:
        best_j: int | None = None
        best_frac = 1e-6
        for j in ordered_ints:
            frac = abs(x[j] - round(x[j]))
            if frac > best_frac:
                best_frac = frac
                best_j = j
        return best_j

    if find_branch_var(root_x) is None:
        snapped = [float(round(root_x[j])) if j in int_indices else root_x[j] for j in range(n)]
        return (
            True,
            "optimal",
            safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
            snapped,
            max(1, total_pivots),
        )

    # Best-first B&B priority queue: (lp_obj, node_id, lb, ub, x_lp)
    node_counter = 0
    heap: list[tuple[float, int, list[float | None], list[float | None], list[float]]] = [
        (root_obj, node_counter, base_lb, base_ub, root_x)
    ]
    incumbent_x: list[float] | None = None
    incumbent_obj = float("inf")
    nodes_explored = 0
    max_nodes = max(1, params.options.max_iterations)
    int_opt = max(0.0, params.options.integer_optimality)

    while heap:
        if cancel_check and cancel_check():
            raise _CancelledError()
        if time.perf_counter() - start_time >= params.options.max_time_sec:
            break
        if nodes_explored >= max_nodes:
            break

        lp_obj, _, cur_lb, cur_ub, cur_x = heapq.heappop(heap)
        if lp_obj >= incumbent_obj - 1e-9:
            continue

        # Check integer optimality gap against current global best lower bound
        if incumbent_x is not None:
            gap = (incumbent_obj - lp_obj) / max(1.0, abs(incumbent_obj))
            if gap <= int_opt:
                break

        nodes_explored += 1
        branch_j = find_branch_var(cur_x)
        if branch_j is None:
            if lp_obj < incumbent_obj:
                incumbent_obj = lp_obj
                incumbent_x = [
                    float(round(cur_x[j])) if j in int_indices else cur_x[j] for j in range(n)
                ]
            continue

        if progress_cb:
            progress_cb(
                nodes_explored,
                to_reported_obj(incumbent_obj if incumbent_x is not None else lp_obj),
            )

        floor_val = math.floor(cur_x[branch_j])
        ceil_val = math.ceil(cur_x[branch_j])

        # Left branch: x_j <= floor_val; Right branch: x_j >= ceil_val
        branches: list[tuple[list[float | None], list[float | None]]] = []
        left_ub = list(cur_ub)
        left_ub[branch_j] = (
            float(floor_val)
            if left_ub[branch_j] is None
            else min(left_ub[branch_j], float(floor_val))
        )
        branches.append((list(cur_lb), left_ub))

        right_lb = list(cur_lb)
        right_lb[branch_j] = (
            float(ceil_val)
            if right_lb[branch_j] is None
            else max(right_lb[branch_j], float(ceil_val))
        )
        branches.append((right_lb, list(cur_ub)))

        for b_lb, b_ub in branches:
            b_status, b_x, b_obj, b_pivs = _solve_bounded_lp(
                min_c, min_const, linear_rows, b_lb, b_ub, max_pivots=max_pivots
            )
            total_pivots += b_pivs
            if b_status != "optimal" or b_obj >= incumbent_obj - 1e-9:
                continue
            if find_branch_var(b_x) is None:
                if b_obj < incumbent_obj:
                    incumbent_obj = b_obj
                    incumbent_x = [
                        float(round(b_x[j])) if j in int_indices else b_x[j] for j in range(n)
                    ]
            else:
                node_counter += 1
                heapq.heappush(heap, (b_obj, node_counter, b_lb, b_ub, b_x))

    if incumbent_x is not None:
        if not heap:
            return (
                True,
                "optimal",
                safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
                incumbent_x,
                max(nodes_explored, 1),
            )
        best_lb = heap[0][0]
        gap = (incumbent_obj - best_lb) / max(1.0, abs(incumbent_obj))
        if gap <= int_opt:
            return (
                True,
                "optimal",
                safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
                incumbent_x,
                max(nodes_explored, 1),
            )
        return (
            True,
            "feasible",
            safe_tr("规划求解找到一个可行解，但未能在限制内证明全局最优。"),
            incumbent_x,
            max(nodes_explored, 1),
        )

    timed_out = time.perf_counter() - start_time >= params.options.max_time_sec
    if nodes_explored >= max_nodes or timed_out:
        return (
            False,
            "max_iterations",
            safe_tr("规划求解在达到最大迭代次数或时间限制前未能收敛。"),
            list(initial_vec),
            nodes_explored,
        )

    return (
        False,
        "infeasible",
        safe_tr("规划求解找不到可行解，请检查约束条件。"),
        list(initial_vec),
        nodes_explored,
    )


# ---------------------------------------------------------------------------
# Constraint Violation / Feasibility Helpers (Shared by GRG & Evolutionary)
# ---------------------------------------------------------------------------


def _compute_bounds(
    n: int,
    constraints: list[_CompiledConstraint],
    non_negative: bool,
    default_upper: float | None = None,
) -> tuple[list[float | None], list[float | None], set[int], set[int]]:
    """Compute variable box bounds and integer/binary index sets."""
    lb: list[float | None] = [0.0 if non_negative else None] * n
    ub: list[float | None] = [default_upper] * n
    int_indices: set[int] = set()
    bin_indices: set[int] = set()

    for c in constraints:
        if c.kind == "int":
            int_indices.update(c.var_indices)
        elif c.kind == "bin":
            for idx in c.var_indices:
                bin_indices.add(idx)
                int_indices.add(idx)
                lb[idx] = 0.0 if lb[idx] is None else max(lb[idx], 0.0)
                ub[idx] = 1.0 if ub[idx] is None else min(ub[idx], 1.0)
    return lb, ub, int_indices, bin_indices


def _project_box(x: list[float], lb: list[float | None], ub: list[float | None]) -> list[float]:
    """Project vector x onto box [lb, ub]."""
    out = list(x)
    for j in range(len(out)):
        if lb[j] is not None and out[j] < lb[j]:
            out[j] = lb[j]  # type: ignore[assignment]
        if ub[j] is not None and out[j] > ub[j]:
            out[j] = ub[j]  # type: ignore[assignment]
    return out


def _constraint_residuals(
    x: list[float],
    vals: dict[tuple[str, int, int], float],
    constraints: list[_CompiledConstraint],
    lb: list[float | None],
    ub: list[float | None],
) -> tuple[list[float], list[float], float]:
    """Return (eq_residuals h(x), ineq_residuals g(x) <= 0, total_violation)."""
    eq_res: list[float] = []
    ineq_res: list[float] = []
    violation = 0.0

    for j, val in enumerate(x):
        if lb[j] is not None and val < lb[j]:  # type: ignore[operator]
            violation += float(lb[j]) - val  # type: ignore[arg-type]
        if ub[j] is not None and val > ub[j]:  # type: ignore[operator]
            violation += val - float(ub[j])  # type: ignore[arg-type]

    for c in constraints:
        if c.kind in ("<=", "=", ">="):
            lhs_val = vals[c.lhs_coords[0]]
            rhs_val = vals[c.rhs_coord] if c.rhs_coord is not None else float(c.rhs_const or 0.0)
            diff = lhs_val - rhs_val
            if c.kind == "=":
                eq_res.append(diff)
                violation += abs(diff)
            elif c.kind == "<=":
                ineq_res.append(diff)
                if diff > 0.0:
                    violation += diff
            else:
                g_val = -diff
                ineq_res.append(g_val)
                if g_val > 0.0:
                    violation += g_val
        elif c.kind == "int":
            for idx in c.var_indices:
                violation += abs(x[idx] - round(x[idx]))
        elif c.kind == "bin":
            for idx in c.var_indices:
                v = x[idx]
                violation += min(abs(v), abs(v - 1.0))
        elif c.kind == "dif":
            rounded: list[int] = []
            for coord in c.lhs_coords:
                v = vals[coord]
                r_v = round(v)
                violation += abs(v - r_v)
                rounded.append(r_v)
            dups = len(rounded) - len(set(rounded))
            if dups > 0:
                violation += float(dups)

    return eq_res, ineq_res, violation


# ---------------------------------------------------------------------------
# GRG Nonlinear (Augmented Lagrangian + Spectral Projected Gradient + Nelder-Mead)
# ---------------------------------------------------------------------------


def _run_grg_nonlinear(
    evaluator: _WorkbookEvaluator,
    params: SolverParams,
    obj_coord: tuple[str, int, int],
    var_coords: list[tuple[str, int, int]],
    initial_vec: list[float],
    constraints: list[_CompiledConstraint],
    cancel_check: Callable[[], bool] | None,
    progress_cb: Callable[[int, float], None] | None,
    start_time: float,
) -> tuple[bool, str, str, list[float], int]:
    """Solve nonlinear constrained problem via Augmented Lagrangian + SPG + Nelder-Mead."""
    n = len(var_coords)
    lb, ub, int_indices, _ = _compute_bounds(n, constraints, params.make_unconstrained_non_negative)
    dif_groups = [c.lhs_coords for c in constraints if c.kind == "dif"]

    # Check if initial_vec has valid evaluation; nudge off 0 if needed
    x_cur = _project_box(initial_vec, lb, ub)
    ok_init, vals_init = evaluator.evaluate_vector(x_cur)
    if not ok_init:
        nudged = _project_box(
            [v if abs(v) > 1e-3 else 0.5 for v in x_cur],
            lb,
            ub,
        )
        ok_nudge, _ = evaluator.evaluate_vector(nudged)
        if not ok_nudge:
            return (
                False,
                "error",
                safe_tr("公式计算出现错误，无法继续求解。"),
                list(initial_vec),
                0,
            )
        x_cur = nudged

    # Build augmented objective helper
    tol = max(params.options.precision, 1e-7)
    max_iters = max(1, params.options.max_iterations)

    def raw_obj(obj_val: float) -> float:
        if params.goal == "max":
            return -obj_val
        if params.goal == "min":
            return obj_val
        diff = obj_val - params.target_value
        return diff * diff

    # Count equality constraints (include value_of target equality)
    eq_count = sum(1 for c in constraints if c.kind == "=") + (
        1 if params.goal == "value_of" else 0
    )
    ineq_count = sum(1 for c in constraints if c.kind in ("<=", ">="))
    lam = [0.0] * eq_count
    mu = [0.0] * ineq_count
    rho = 10.0

    def aug_lagrangian(x: list[float], discrete_weight: float) -> tuple[bool, float, float, float]:
        ok, vals = evaluator.evaluate_vector(x)
        if not ok:
            return False, float("inf"), 0.0, float("inf")
        obj_v = vals[obj_coord]
        eq_res, ineq_res, viol = _constraint_residuals(x, vals, constraints, lb, ub)
        if params.goal == "value_of":
            eq_res.append(obj_v - params.target_value)
            viol += abs(obj_v - params.target_value)

        cost = raw_obj(obj_v)
        for k, h_k in enumerate(eq_res):
            cost += lam[k] * h_k + 0.5 * rho * h_k * h_k
        for i, g_i in enumerate(ineq_res):
            m_i = max(0.0, mu[i] + rho * g_i)
            cost += (m_i * m_i - mu[i] * mu[i]) / (2.0 * rho)

        if discrete_weight > 0.0:
            for idx in int_indices:
                s = math.sin(math.pi * x[idx])
                cost += discrete_weight * (s * s)
            for grp in dif_groups:
                grp_vals = [vals[coord] for coord in grp]
                for a_i in range(len(grp_vals)):
                    for b_i in range(a_i + 1, len(grp_vals)):
                        gap = abs(grp_vals[a_i] - grp_vals[b_i])
                        if gap < 1.0:
                            cost += discrete_weight * (1.0 - gap) ** 2

        return True, cost, obj_v, viol

    def finite_diff_grad(x: list[float], f_x: float, discrete_weight: float) -> list[float]:
        grad = [0.0] * n
        for j in range(n):
            step = 1e-5 * max(1.0, abs(x[j]))
            x_p = list(x)
            x_p[j] += step
            # Respect box bounds in finite difference direction if at boundary
            if ub[j] is not None and x_p[j] > ub[j]:  # type: ignore[operator]
                x_m = list(x)
                x_m[j] -= step
                if lb[j] is not None and x_m[j] < lb[j]:  # type: ignore[operator]
                    continue
                ok_m, f_m, _, _ = aug_lagrangian(x_m, discrete_weight)
                if ok_m:
                    grad[j] = (f_x - f_m) / step
                continue
            ok_p, f_p, _, _ = aug_lagrangian(x_p, discrete_weight)
            x_m = list(x)
            x_m[j] -= step
            if lb[j] is None or x_m[j] >= lb[j]:
                ok_m, f_m, _, _ = aug_lagrangian(x_m, discrete_weight)
            else:
                ok_m, f_m = False, 0.0
            if ok_p and ok_m:
                grad[j] = (f_p - f_m) / (2.0 * step)
            elif ok_p:
                grad[j] = (f_p - f_x) / step
            elif ok_m:
                grad[j] = (f_x - f_m) / step
        return grad

    def nelder_mead_polish(
        x_start: list[float], discrete_weight: float, budget: int
    ) -> list[float]:
        simplex: list[tuple[float, list[float]]] = []
        ok0, f0, _, _ = aug_lagrangian(x_start, discrete_weight)
        if not ok0:
            return x_start
        simplex.append((f0, list(x_start)))
        for j in range(n):
            pt = list(x_start)
            delta = 0.05 * max(1.0, abs(pt[j]))
            if ub[j] is not None and pt[j] + delta > ub[j]:  # type: ignore[operator]
                pt[j] -= delta
            else:
                pt[j] += delta
            pt = _project_box(pt, lb, ub)
            ok_p, f_p, _, _ = aug_lagrangian(pt, discrete_weight)
            simplex.append((f_p if ok_p else 1e30, pt))

        for _ in range(budget):
            if cancel_check and cancel_check():
                raise _CancelledError()
            if time.perf_counter() - start_time >= params.options.max_time_sec:
                break
            simplex.sort(key=lambda item: item[0])
            f_best = simplex[0][0]
            f_worst, x_worst = simplex[-1]
            f_second = simplex[-2][0]
            if max(abs(simplex[i][0] - f_best) for i in range(1, len(simplex))) < tol * 0.1:
                break
            centroid = [sum(simplex[i][1][j] for i in range(n)) / n for j in range(n)]
            # Reflection
            x_ref = _project_box(
                [centroid[j] + (centroid[j] - x_worst[j]) for j in range(n)], lb, ub
            )
            ok_r, f_r, _, _ = aug_lagrangian(x_ref, discrete_weight)
            f_r = f_r if ok_r else 1e30
            if f_best <= f_r < f_second:
                simplex[-1] = (f_r, x_ref)
                continue
            if f_r < f_best:
                x_exp = _project_box(
                    [centroid[j] + 2.0 * (x_ref[j] - centroid[j]) for j in range(n)],
                    lb,
                    ub,
                )
                ok_e, f_e, _, _ = aug_lagrangian(x_exp, discrete_weight)
                f_e = f_e if ok_e else 1e30
                simplex[-1] = (f_e, x_exp) if f_e < f_r else (f_r, x_ref)
                continue
            # Contraction
            if f_r < f_worst:
                x_c = _project_box(
                    [centroid[j] + 0.5 * (x_ref[j] - centroid[j]) for j in range(n)],
                    lb,
                    ub,
                )
                ok_c, f_c, _, _ = aug_lagrangian(x_c, discrete_weight)
                if ok_c and f_c <= f_r:
                    simplex[-1] = (f_c, x_c)
                    continue
            else:
                x_c = _project_box(
                    [centroid[j] + 0.5 * (x_worst[j] - centroid[j]) for j in range(n)],
                    lb,
                    ub,
                )
                ok_c, f_c, _, _ = aug_lagrangian(x_c, discrete_weight)
                if ok_c and f_c < f_worst:
                    simplex[-1] = (f_c, x_c)
                    continue
            # Shrink
            best_pt = simplex[0][1]
            for i in range(1, len(simplex)):
                sh_pt = _project_box(
                    [best_pt[j] + 0.5 * (simplex[i][1][j] - best_pt[j]) for j in range(n)],
                    lb,
                    ub,
                )
                ok_s, f_s, _, _ = aug_lagrangian(sh_pt, discrete_weight)
                simplex[i] = (f_s if ok_s else 1e30, sh_pt)

        simplex.sort(key=lambda item: item[0])
        return simplex[0][1]

    best_feasible_x: list[float] | None = None
    best_feasible_raw = float("inf")
    best_viol_x = list(x_cur)
    best_viol = float("inf")

    total_iters = 0
    outer_rounds = min(20, max(6, max_iters // 10))
    inner_per_outer = max(8, max_iters // outer_rounds)
    prev_viol = float("inf")
    discrete_w = 0.0

    for outer in range(outer_rounds):
        if cancel_check and cancel_check():
            raise _CancelledError()
        if time.perf_counter() - start_time >= params.options.max_time_sec:
            break
        if total_iters >= max_iters:
            break

        if outer >= 3 and (int_indices or dif_groups):
            discrete_w = min(1000.0, 5.0 * (2.0 ** (outer - 3)))

        # Spectral Projected Gradient (SPG) inner minimization
        alpha_bb = 1.0
        ok_c, f_cur, obj_cur, viol_cur = aug_lagrangian(x_cur, discrete_w)
        if not ok_c:
            break
        grad = finite_diff_grad(x_cur, f_cur, discrete_w)

        for _ in range(inner_per_outer):
            if cancel_check and cancel_check():
                raise _CancelledError()
            if time.perf_counter() - start_time >= params.options.max_time_sec:
                break
            if total_iters >= max_iters:
                break
            total_iters += 1

            # Projected gradient norm check
            d_unit = [
                _project_box([x_cur[j] - grad[j] for j in range(n)], lb, ub)[j] - x_cur[j]
                for j in range(n)
            ]
            pg_norm = math.sqrt(sum(v * v for v in d_unit))
            if pg_norm < tol * 0.1:
                break

            # Backtracking line search along projected ray
            step = alpha_bb
            accepted = False
            x_next = x_cur
            f_next = f_cur
            for _ls in range(25):
                cand = _project_box([x_cur[j] - step * grad[j] for j in range(n)], lb, ub)
                d = [cand[j] - x_cur[j] for j in range(n)]
                g_dot_d = sum(grad[j] * d[j] for j in range(n))
                ok_cand, f_cand, _, _ = aug_lagrangian(cand, discrete_w)
                if ok_cand and f_cand <= f_cur + 1e-4 * g_dot_d:
                    x_next = cand
                    f_next = f_cand
                    accepted = True
                    break
                step *= 0.5
                if step < 1e-12:
                    break

            if not accepted:
                break

            grad_next = finite_diff_grad(x_next, f_next, discrete_w)
            s_vec = [x_next[j] - x_cur[j] for j in range(n)]
            y_vec = [grad_next[j] - grad[j] for j in range(n)]
            s_dot_s = sum(v * v for v in s_vec)
            s_dot_y = sum(s_vec[j] * y_vec[j] for j in range(n))
            if s_dot_y > 1e-12:
                alpha_bb = max(1e-6, min(1e4, s_dot_s / s_dot_y))
            else:
                alpha_bb = 1.0

            x_cur = x_next
            f_cur = f_next
            grad = grad_next

            if math.sqrt(s_dot_s) < tol * 1e-2:
                break

        # Nelder-Mead polish if non-smooth or stalling
        x_cur = nelder_mead_polish(x_cur, discrete_w, budget=min(30, max(10, 3 * n)))

        # Evaluate true constraints & update Augmented Lagrangian multipliers
        ok_eval, vals_eval = evaluator.evaluate_vector(x_cur)
        if not ok_eval:
            break
        obj_v = vals_eval[obj_coord]
        eq_res, ineq_res, viol = _constraint_residuals(x_cur, vals_eval, constraints, lb, ub)
        if params.goal == "value_of":
            eq_res.append(obj_v - params.target_value)
            viol += abs(obj_v - params.target_value)

        if progress_cb:
            progress_cb(total_iters, obj_v)

        if viol < best_viol:
            best_viol = viol
            best_viol_x = list(x_cur)

        feas_tol = max(params.options.precision * 10.0, 1e-5)
        if viol <= feas_tol:
            rv = raw_obj(obj_v)
            if rv < best_feasible_raw:
                best_feasible_raw = rv
                best_feasible_x = list(x_cur)

        for k, h_k in enumerate(eq_res):
            lam[k] += rho * h_k
        for i, g_i in enumerate(ineq_res):
            mu[i] = max(0.0, mu[i] + rho * g_i)

        if viol > 0.25 * prev_viol:
            rho = min(1e8, rho * 4.0)
        prev_viol = viol

        if viol <= feas_tol and outer >= 2 and not int_indices and not dif_groups:
            # Check stationarity
            grad_check = finite_diff_grad(x_cur, f_cur, 0.0)
            proj_g = _project_box([x_cur[j] - grad_check[j] for j in range(n)], lb, ub)
            pg = math.sqrt(sum((proj_g[j] - x_cur[j]) ** 2 for j in range(n)))
            if pg <= max(tol, 1e-5):
                break

    # Local integer rounding & coordinate search if int/bin/dif present
    cand_x = best_feasible_x if best_feasible_x is not None else best_viol_x
    if int_indices or dif_groups:
        rounded_x = [float(round(cand_x[j])) if j in int_indices else cand_x[j] for j in range(n)]
        rounded_x = _project_box(rounded_x, lb, ub)
        best_int_x = list(rounded_x)
        best_int_score = (float("inf"), float("inf"))

        def score_int(pt: list[float]) -> tuple[float, float]:
            ok_p, v_p = evaluator.evaluate_vector(pt)
            if not ok_p:
                return (float("inf"), float("inf"))
            _, _, v_viol = _constraint_residuals(pt, v_p, constraints, lb, ub)
            o_v = v_p[obj_coord]
            if params.goal == "value_of":
                v_viol += abs(o_v - params.target_value)
            return (v_viol, raw_obj(o_v))

        best_int_score = score_int(best_int_x)
        for _pass in range(3):
            improved = False
            for j in sorted(int_indices):
                for delta in (-1.0, 1.0):
                    trial = list(best_int_x)
                    trial[j] += delta
                    trial = _project_box(trial, lb, ub)
                    sc = score_int(trial)
                    if sc[0] < best_int_score[0] - 1e-9 or (
                        abs(sc[0] - best_int_score[0]) <= 1e-9 and sc[1] < best_int_score[1] - 1e-9
                    ):
                        best_int_score = sc
                        best_int_x = trial
                        improved = True
            if not improved:
                break
        cand_x = best_int_x

    # Verify final candidate feasibility
    ok_fin, vals_fin = evaluator.evaluate_vector(cand_x)
    if not ok_fin:
        return (
            False,
            "error",
            safe_tr("公式计算出现错误，无法继续求解。"),
            list(initial_vec),
            total_iters,
        )

    _, _, final_viol = _constraint_residuals(cand_x, vals_fin, constraints, lb, ub)
    fin_obj = vals_fin[obj_coord]
    if params.goal == "value_of":
        final_viol += abs(fin_obj - params.target_value)

    feas_tol = max(params.options.precision * 100.0, 1e-4)
    if final_viol <= feas_tol:
        return (
            True,
            "optimal",
            safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
            cand_x,
            max(1, total_iters),
        )

    return (
        False,
        "infeasible",
        safe_tr("规划求解找不到可行解，请检查约束条件。"),
        list(initial_vec),
        max(1, total_iters),
    )


# ---------------------------------------------------------------------------
# Evolutionary (Deterministic Seeded Differential Evolution)
# ---------------------------------------------------------------------------


def _run_evolutionary(
    evaluator: _WorkbookEvaluator,
    params: SolverParams,
    obj_coord: tuple[str, int, int],
    var_coords: list[tuple[str, int, int]],
    initial_vec: list[float],
    constraints: list[_CompiledConstraint],
    cancel_check: Callable[[], bool] | None,
    progress_cb: Callable[[int, float], None] | None,
    start_time: float,
) -> tuple[bool, str, str, list[float], int]:
    """Deterministic seeded Differential Evolution with Deb's feasibility rules."""
    n = len(var_coords)
    rng = random.Random(params.options.random_seed)

    # Determine reasonable search domain bounds
    rhs_mag = 10.0
    for c in constraints:
        if c.rhs_const is not None:
            rhs_mag = max(rhs_mag, abs(c.rhs_const))
    init_mag = max([abs(v) for v in initial_vec] + [1.0])
    scale = max(50.0, rhs_mag * 2.0, init_mag * 4.0)

    lb, ub, int_indices, bin_indices = _compute_bounds(
        n, constraints, params.make_unconstrained_non_negative, default_upper=scale
    )
    for j in range(n):
        if lb[j] is None:
            lb[j] = -scale
        if ub[j] is None:
            ub[j] = scale

    # Identify variable-index dif groups
    var_index_map = {coord: idx for idx, coord in enumerate(var_coords)}
    dif_var_groups: list[list[int]] = []
    for c in constraints:
        if c.kind == "dif":
            grp = [var_index_map[coord] for coord in c.lhs_coords if coord in var_index_map]
            if grp:
                dif_var_groups.append(grp)
                int_indices.update(grp)

    def decode(raw_x: list[float]) -> list[float]:
        out = _project_box(raw_x, lb, ub)
        for j in int_indices:
            out[j] = float(round(out[j]))
        for j in bin_indices:
            out[j] = 1.0 if out[j] >= 0.5 else 0.0
        return _project_box(out, lb, ub)

    def repair_dif(x: list[float]) -> list[float]:
        out = list(x)
        for grp in dif_var_groups:
            k = len(grp)
            lo_vals = [lb[j] if lb[j] is not None else 1.0 for j in grp]
            hi_vals = [ub[j] if ub[j] is not None else float(k) for j in grp]
            lo_g = max(int(math.ceil(max(lo_vals))), 1)
            hi_g = min(int(math.floor(min(hi_vals))), k)
            if hi_g - lo_g + 1 >= k:
                pool = list(range(lo_g, lo_g + k))
            else:
                pool = list(range(1, k + 1))
            used: set[int] = set()
            dups: list[int] = []
            for idx in grp:
                val = int(round(out[idx]))
                if val not in used and val in pool:
                    used.add(val)
                    out[idx] = float(val)
                else:
                    dups.append(idx)
            avail = [p for p in pool if p not in used]
            rng.shuffle(avail)
            for idx, p_val in zip(dups, avail):
                out[idx] = float(p_val)
        return out

    def evaluate_candidate(raw_x: list[float]) -> tuple[list[float], float, float, float]:
        """Return (decoded_x, violation, minimized_obj, raw_spreadsheet_obj)."""
        dec = decode(raw_x)
        ok, vals = evaluator.evaluate_vector(dec)
        if not ok:
            return dec, 1e12, 1e12, 0.0
        obj_v = vals[obj_coord]
        _, _, viol = _constraint_residuals(dec, vals, constraints, lb, ub)
        if params.goal == "max":
            m_obj = -obj_v
        elif params.goal == "min":
            m_obj = obj_v
        else:
            m_obj = abs(obj_v - params.target_value)
        return dec, viol, m_obj, obj_v

    feas_tol = max(params.options.precision, 1e-6)

    def is_better(a: tuple[float, float], b: tuple[float, float]) -> bool:
        """Deb's feasibility rule: (violation, min_obj)."""
        a_feas = a[0] <= feas_tol
        b_feas = b[0] <= feas_tol
        if a_feas and not b_feas:
            return True
        if b_feas and not a_feas:
            return False
        if not a_feas and not b_feas:
            return a[0] < b[0]
        return a[1] < b[1]

    pop_size = max(12, params.options.population_size)
    population: list[list[float]] = []
    # Seed initial vector and randomized individuals
    population.append(list(_project_box(initial_vec, lb, ub)))
    for p_i in range(1, pop_size):
        ind: list[float] = []
        for j in range(n):
            lo = float(lb[j])  # type: ignore[arg-type]
            hi = float(ub[j])  # type: ignore[arg-type]
            if j in bin_indices:
                ind.append(float(rng.randint(0, 1)))
            elif p_i < pop_size // 2:
                span = min(hi - lo, max(10.0, abs(initial_vec[j]) * 2.0 + 5.0))
                center = min(hi, max(lo, initial_vec[j]))
                val = rng.uniform(max(lo, center - span * 0.5), min(hi, center + span * 0.5))
                ind.append(val)
            else:
                ind.append(rng.uniform(lo, hi))
        if dif_var_groups and p_i % 2 == 1:
            ind = repair_dif(ind)
        population.append(ind)

    evals = [evaluate_candidate(ind) for ind in population]
    best_idx = 0
    for i in range(1, pop_size):
        if is_better((evals[i][1], evals[i][2]), (evals[best_idx][1], evals[best_idx][2])):
            best_idx = i

    best_dec, best_viol, best_mobj, best_robj = evals[best_idx]
    max_gens = max(1, params.options.max_iterations)
    stagnant = 0
    gens_run = 0

    for gen in range(1, max_gens + 1):
        if cancel_check and cancel_check():
            raise _CancelledError()
        if time.perf_counter() - start_time >= params.options.max_time_sec:
            break
        gens_run = gen
        improved_this_gen = False

        for i in range(pop_size):
            if cancel_check and cancel_check():
                raise _CancelledError()
            indices = [k for k in range(pop_size) if k != i]
            r1, r2, r3 = rng.sample(indices, 3)
            f_scale = rng.uniform(0.5, 0.9)
            cr = 0.85

            # Mix DE/rand/1 and DE/current-to-best/1
            j_rand = rng.randrange(n)
            trial: list[float] = []
            use_best = i % 2 == 0
            for j in range(n):
                if rng.random() < cr or j == j_rand:
                    if use_best:
                        v_j = (
                            population[i][j]
                            + f_scale * (population[best_idx][j] - population[i][j])
                            + f_scale * (population[r1][j] - population[r2][j])
                        )
                    else:
                        v_j = population[r1][j] + f_scale * (population[r2][j] - population[r3][j])
                    trial.append(v_j)
                else:
                    trial.append(population[i][j])

            trial = _project_box(trial, lb, ub)
            if dif_var_groups and rng.random() < 0.5:
                trial = repair_dif(trial)

            cand_eval = evaluate_candidate(trial)
            if is_better((cand_eval[1], cand_eval[2]), (evals[i][1], evals[i][2])):
                population[i] = trial
                evals[i] = cand_eval
                if is_better((cand_eval[1], cand_eval[2]), (best_viol, best_mobj)):
                    best_idx = i
                    best_dec, best_viol, best_mobj, best_robj = cand_eval
                    improved_this_gen = True

        if progress_cb:
            progress_cb(gen, best_robj)

        if params.goal == "value_of" and best_viol <= feas_tol and best_mobj <= feas_tol:
            break

        if improved_this_gen:
            stagnant = 0
        else:
            stagnant += 1
            if best_viol <= feas_tol and stagnant >= max(40, max_gens // 2):
                break

    # Local coordinate polish on best_dec
    if int_indices and dif_var_groups:
        # Pairwise swap polish for dif groups
        for grp in dif_var_groups:
            for a_i in range(len(grp)):
                for b_i in range(a_i + 1, len(grp)):
                    cand = list(best_dec)
                    cand[grp[a_i]], cand[grp[b_i]] = cand[grp[b_i]], cand[grp[a_i]]
                    ce = evaluate_candidate(cand)
                    if is_better((ce[1], ce[2]), (best_viol, best_mobj)):
                        best_dec, best_viol, best_mobj, best_robj = ce
    elif not int_indices:
        # Brief pattern search polish on continuous variables
        step = 0.05
        for _ in range(10):
            improved = False
            for j in range(n):
                for sign in (-1.0, 1.0):
                    cand = list(best_dec)
                    cand[j] += sign * step * max(1.0, abs(cand[j]))
                    cand = _project_box(cand, lb, ub)
                    ce = evaluate_candidate(cand)
                    if is_better((ce[1], ce[2]), (best_viol, best_mobj)):
                        best_dec, best_viol, best_mobj, best_robj = ce
                        improved = True
            if not improved:
                step *= 0.25

    ok_final = best_viol <= max(feas_tol, 1e-4)
    if params.goal == "value_of":
        ok_final = ok_final and best_mobj <= max(feas_tol * 10.0, 1e-4)

    if ok_final:
        return (
            True,
            "optimal",
            safe_tr("规划求解已完成，找到满足所有约束条件的最优解。"),
            best_dec,
            max(1, gens_run),
        )

    return (
        False,
        "infeasible",
        safe_tr("规划求解找不到可行解，请检查约束条件。"),
        list(initial_vec),
        max(1, gens_run),
    )


# ---------------------------------------------------------------------------
# Report Generation, Solution Application & Public Entry Point
# ---------------------------------------------------------------------------


def _build_constraint_reports(
    workbook: WorkbookModel,
    params: SolverParams,
    compiled: list[_CompiledConstraint],
) -> list[ConstraintReportItem]:
    """Evaluate and build constraint report items at current workbook state."""
    reports: list[ConstraintReportItem] = []
    tol = max(params.options.precision * 10.0, 1e-5)

    for c in compiled:
        if c.kind in ("<=", "=", ">="):
            sh_name, r, c_idx = c.lhs_coords[0]
            sh = _get_sheet(workbook, sh_name)
            cell = sh.get_cell(r, c_idx) if sh is not None else None
            formula = (cell.formula or "") if cell is not None else ""
            lhs_val = _to_numeric(sh.get_cell_value(r, c_idx) if sh is not None else None) or 0.0

            if c.rhs_coord is not None:
                rsh = _get_sheet(workbook, c.rhs_coord[0])
                rhs_val = (
                    _to_numeric(
                        rsh.get_cell_value(c.rhs_coord[1], c.rhs_coord[2])
                        if rsh is not None
                        else None
                    )
                    or 0.0
                )
            else:
                rhs_val = float(c.rhs_const or 0.0)

            if c.kind == "<=":
                slack = rhs_val - lhs_val
            elif c.kind == ">=":
                slack = lhs_val - rhs_val
            else:
                slack = rhs_val - lhs_val

            binding = abs(slack) <= tol
            reports.append(
                ConstraintReportItem(
                    cell_ref=format_cell_ref(sh_name, r, c_idx, params.default_sheet),
                    formula=formula,
                    cell_value=lhs_val,
                    op=c.kind,
                    rhs_value=c.rhs_display,
                    binding=binding,
                    slack=0.0 if abs(slack) <= 1e-12 else slack,
                )
            )
        elif c.kind in ("int", "bin"):
            for sh_name, r, c_idx in c.lhs_coords:
                sh = _get_sheet(workbook, sh_name)
                cell = sh.get_cell(r, c_idx) if sh is not None else None
                formula = (cell.formula or "") if cell is not None else ""
                val = _to_numeric(sh.get_cell_value(r, c_idx) if sh is not None else None) or 0.0
                slack = abs(val - round(val))
                reports.append(
                    ConstraintReportItem(
                        cell_ref=format_cell_ref(sh_name, r, c_idx, params.default_sheet),
                        formula=formula,
                        cell_value=val,
                        op=c.kind,
                        rhs_value="",
                        binding=slack <= tol,
                        slack=0.0 if slack <= 1e-12 else slack,
                    )
                )
        elif c.kind == "dif":
            vals: list[int] = []
            for sh_name, r, c_idx in c.lhs_coords:
                sh = _get_sheet(workbook, sh_name)
                val = _to_numeric(sh.get_cell_value(r, c_idx) if sh is not None else None) or 0.0
                vals.append(round(val))
            dups = len(vals) - len(set(vals))
            first_sh, first_r, first_c = c.lhs_coords[0]
            last_sh, last_r, last_c = c.lhs_coords[-1]
            if len(c.lhs_coords) > 1 and first_sh == last_sh:
                ref_label = (
                    f"{format_cell_ref(first_sh, first_r, first_c, params.default_sheet)}"
                    f":{cell_name(last_r, last_c)}"
                )
            else:
                ref_label = format_cell_ref(first_sh, first_r, first_c, params.default_sheet)
            reports.append(
                ConstraintReportItem(
                    cell_ref=ref_label,
                    formula="",
                    cell_value=float(len(c.lhs_coords)),
                    op="dif",
                    rhs_value="",
                    binding=dups == 0,
                    slack=float(dups),
                )
            )

    return reports


def solve_model(
    workbook: WorkbookModel,
    params: SolverParams,
    cancel_check: Callable[[], bool] | None = None,
    progress_cb: Callable[[int, float], None] | None = None,
) -> SolverResult:
    """Solve the spreadsheet optimization model while always restoring workbook state."""
    start_time = time.perf_counter()

    obj_coord, var_coords, initial_vec, compiled, err_msg = _validate_and_compile(workbook, params)
    if err_msg is not None or obj_coord is None:
        return SolverResult(
            success=False,
            status="invalid_input",
            message=err_msg or "",
            iterations=0,
            objective_ref=params.objective_ref,
            initial_objective=0.0,
            final_objective=0.0,
            initial_values={},
            solution_values={},
            constraint_reports=[],
            elapsed_sec=time.perf_counter() - start_time,
        )

    formatted_obj = format_cell_ref(*obj_coord, params.default_sheet)
    initial_dict = {
        format_cell_ref(*coord, params.default_sheet): val
        for coord, val in zip(var_coords, initial_vec, strict=True)
    }

    # Gather all cells whose values must be read during evaluation
    watch_set: set[tuple[str, int, int]] = {obj_coord}
    for c in compiled:
        watch_set.update(c.lhs_coords)
        if c.rhs_coord is not None:
            watch_set.add(c.rhs_coord)

    evaluator = _WorkbookEvaluator(workbook, var_coords, sorted(watch_set))
    init_obj = 0.0

    try:
        ok_prep, prep_err = evaluator.prepare()
        if not ok_prep:
            return SolverResult(
                success=False,
                status="invalid_input",
                message=prep_err or "",
                iterations=0,
                objective_ref=formatted_obj,
                initial_objective=0.0,
                final_objective=0.0,
                initial_values=initial_dict,
                solution_values=dict(initial_dict),
                constraint_reports=[],
                elapsed_sec=time.perf_counter() - start_time,
            )

        ok_init_eval, init_vals = evaluator.evaluate_vector(initial_vec)
        init_obj = init_vals[obj_coord] if ok_init_eval else 0.0

        if cancel_check and cancel_check():
            raise _CancelledError()

        if params.method == "simplex_lp":
            success, status, msg, sol_vec, iters = _run_simplex_lp(
                evaluator,
                params,
                obj_coord,
                var_coords,
                initial_vec,
                compiled,
                cancel_check,
                progress_cb,
                start_time,
            )
        elif params.method == "grg_nonlinear":
            success, status, msg, sol_vec, iters = _run_grg_nonlinear(
                evaluator,
                params,
                obj_coord,
                var_coords,
                initial_vec,
                compiled,
                cancel_check,
                progress_cb,
                start_time,
            )
        elif params.method == "evolutionary":
            success, status, msg, sol_vec, iters = _run_evolutionary(
                evaluator,
                params,
                obj_coord,
                var_coords,
                initial_vec,
                compiled,
                cancel_check,
                progress_cb,
                start_time,
            )
        else:
            return SolverResult(
                success=False,
                status="invalid_input",
                message=safe_tr("规划求解方法无效：{0}", str(params.method)),
                iterations=0,
                objective_ref=formatted_obj,
                initial_objective=init_obj,
                final_objective=init_obj,
                initial_values=initial_dict,
                solution_values=dict(initial_dict),
                constraint_reports=[],
                elapsed_sec=time.perf_counter() - start_time,
            )

        ok_fin, fin_vals = evaluator.evaluate_vector(sol_vec)
        final_obj = fin_vals[obj_coord] if ok_fin else init_obj
        reports = _build_constraint_reports(workbook, params, compiled)
        sol_dict = {
            format_cell_ref(*coord, params.default_sheet): val
            for coord, val in zip(var_coords, sol_vec, strict=True)
        }
        return SolverResult(
            success=success,
            status=status,
            message=msg,
            iterations=iters,
            objective_ref=formatted_obj,
            initial_objective=init_obj,
            final_objective=final_obj,
            initial_values=initial_dict,
            solution_values=sol_dict,
            constraint_reports=reports,
            elapsed_sec=time.perf_counter() - start_time,
        )

    except _CancelledError:
        return SolverResult(
            success=False,
            status="cancelled",
            message=safe_tr("规划求解已被用户取消。"),
            iterations=0,
            objective_ref=formatted_obj,
            initial_objective=init_obj,
            final_objective=init_obj,
            initial_values=initial_dict,
            solution_values=dict(initial_dict),
            constraint_reports=[],
            elapsed_sec=time.perf_counter() - start_time,
        )
    except Exception as exc:
        logger.exception("Unexpected error during solver execution: %s", exc)
        return SolverResult(
            success=False,
            status="error",
            message=safe_tr("公式计算出现错误，无法继续求解。"),
            iterations=0,
            objective_ref=formatted_obj,
            initial_objective=init_obj,
            final_objective=init_obj,
            initial_values=initial_dict,
            solution_values=dict(initial_dict),
            constraint_reports=[],
            elapsed_sec=time.perf_counter() - start_time,
        )
    finally:
        evaluator.restore()


def apply_solver_solution(workbook: WorkbookModel, solution_values: dict[str, float]) -> None:
    """Write solution_values into workbook cells and recalculate all formulas."""
    default_sheet = workbook.active_sheet.name if getattr(workbook, "sheets", None) else "Sheet1"
    for ref_str, val in solution_values.items():
        sh_name, r, c = _parse_single_cell(ref_str, default_sheet=default_sheet)
        sh = _get_sheet(workbook, sh_name)
        if sh is None:
            raise ValueError(f"Worksheet '{sh_name}' not found.")
        sh.set_cell_value(r, c, float(val))
    workbook.recalculate()


def _create_report_sheet(workbook: WorkbookModel, prefix: str) -> tuple[str, Any]:
    """Create a uniquely named report worksheet like 'Answer Report 1'."""
    idx = 1
    while workbook.get_sheet_by_name(f"{prefix} {idx}") is not None:
        idx += 1
    sheet_name = f"{prefix} {idx}"
    return sheet_name, workbook.add_sheet(name=sheet_name)


def _clean_zero(val: float, tol: float = 1e-10) -> float:
    """Normalize near-zero floats (including -0.0) to 0.0."""
    return 0.0 if abs(val) < tol else float(val)


def _solve_linear_system(mat: list[list[float]], rhs: list[float]) -> list[float] | None:
    """Solve a small dense linear system A x = b via Gaussian elimination with partial pivoting."""
    n = len(rhs)
    if n == 0:
        return []
    aug = [list(mat[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        piv_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[piv_row][col]) < 1e-12:
            return None
        if piv_row != col:
            aug[col], aug[piv_row] = aug[piv_row], aug[col]
        piv = aug[col][col]
        for r in range(col + 1, n):
            factor = aug[r][col] / piv
            if abs(factor) > 1e-15:
                for k in range(col, n + 1):
                    aug[r][k] -= factor * aug[col][k]
    sol = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = aug[i][n] - sum(aug[i][j] * sol[j] for j in range(i + 1, n))
        sol[i] = s / aug[i][i]
    return sol


def _solution_vector_from_result(
    var_coords: list[tuple[str, int, int]],
    initial_vec: list[float],
    params: SolverParams,
    result: SolverResult,
) -> list[float]:
    """Extract ordered solution vector matching var_coords from SolverResult."""
    vec: list[float] = []
    for coord, init_v in zip(var_coords, initial_vec, strict=True):
        ref_rel = format_cell_ref(*coord, params.default_sheet)
        ref_abs = format_cell_ref(*coord, None)
        if ref_rel in result.solution_values:
            vec.append(float(result.solution_values[ref_rel]))
        elif ref_abs in result.solution_values:
            vec.append(float(result.solution_values[ref_abs]))
        else:
            vec.append(float(init_v))
    return vec


def _compute_lp_sensitivity(
    evaluator: _WorkbookEvaluator,
    params: SolverParams,
    obj_coord: tuple[str, int, int],
    var_coords: list[tuple[str, int, int]],
    initial_vec: list[float],
    compiled: list[_CompiledConstraint],
) -> (
    tuple[
        list[tuple[float, float, float, float]],
        list[tuple[float, float, float, float]],
    ]
    | None
):
    """Compute exact Simplex LP sensitivity rows for variables and algebraic constraints.

    Returns ``(var_rows, con_rows)`` where:
    - ``var_rows[j] = (reduced_cost, obj_coeff, allow_inc, allow_dec)``
    - ``con_rows[i] = (shadow_price, rhs_val, allow_inc, allow_dec)``
    or ``None`` if the problem is not a clean continuous LP.
    """
    if params.method != "simplex_lp" or params.goal == "value_of":
        return None
    if any(c.kind in ("int", "bin", "dif") for c in compiled):
        return None

    ok_lin, _err, obj_coeffs, obj_const, linear_rows = _extract_linear_model(
        evaluator, obj_coord, compiled, initial_vec, params.make_unconstrained_non_negative
    )
    if not ok_lin:
        return None

    n = len(var_coords)
    base_lb: list[float | None] = [0.0 if params.make_unconstrained_non_negative else None] * n
    base_ub: list[float | None] = [None] * n
    is_max = params.goal == "max"
    min_c = [-v for v in obj_coeffs] if is_max else list(obj_coeffs)
    min_const = -obj_const if is_max else obj_const

    max_pivots = max(500, params.options.max_iterations * 10)
    lp_status, sol_x, _obj_v, _pivs, mapping, tab_info = _solve_bounded_lp_with_info(
        min_c, min_const, linear_rows, base_lb, base_ub, max_pivots=max_pivots
    )
    if lp_status != "optimal" or tab_info is None:
        return None

    ok_sol, sol_vals = evaluator.evaluate_vector(sol_x)
    if not ok_sol:
        return None

    _INF = 1e30
    tableau = tab_info.tableau
    basis = tab_info.basis
    obj2 = tab_info.obj2
    total_cols = tab_info.total_cols
    active_cols = tab_info.active_cols
    basis_row_by_col = {b_col: r_idx for r_idx, b_col in enumerate(basis)}
    basis_set = set(basis)

    def _range_from_basic_row(
        row_idx: int, sign_mult: float, exclude_cols: set[int]
    ) -> tuple[float, float]:
        """Compute [d_lo, d_hi] for delta_min keeping reduced costs non-negative."""
        d_lo = float("-inf")
        d_hi = float("inf")
        row = tableau[row_idx]
        for k in range(active_cols):
            if k in basis_set or k in exclude_cols:
                continue
            a_rk = sign_mult * row[k]
            rc_k = max(0.0, obj2[k])
            if a_rk > 1e-12:
                d_hi = min(d_hi, rc_k / a_rk)
            elif a_rk < -1e-12:
                d_lo = max(d_lo, rc_k / a_rk)
        return d_lo, d_hi

    var_rows: list[tuple[float, float, float, float]] = []
    for j in range(n):
        c_j = float(obj_coeffs[j])
        kind, _offset, i1, i2 = mapping[j]
        if kind == "lb":
            if i1 in basis_row_by_col:
                reduced_cost = 0.0
                d_lo, d_hi = _range_from_basic_row(basis_row_by_col[i1], 1.0, set())
                if is_max:
                    allow_inc = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
                    allow_dec = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                else:
                    allow_inc = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                    allow_dec = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
            else:
                rc_min = max(0.0, obj2[i1])
                reduced_cost = _clean_zero(-rc_min if is_max else rc_min)
                if is_max:
                    allow_inc = _clean_zero(rc_min)
                    allow_dec = _INF
                else:
                    allow_inc = _INF
                    allow_dec = _clean_zero(rc_min)
        else:
            # Free variable: x_j = y_p - y_n
            excl = {i1, i2}
            if i1 in basis_row_by_col:
                reduced_cost = 0.0
                d_lo, d_hi = _range_from_basic_row(basis_row_by_col[i1], 1.0, excl)
                if is_max:
                    allow_inc = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
                    allow_dec = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                else:
                    allow_inc = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                    allow_dec = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
            elif i2 in basis_row_by_col:
                reduced_cost = 0.0
                d_lo, d_hi = _range_from_basic_row(basis_row_by_col[i2], -1.0, excl)
                if is_max:
                    allow_inc = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
                    allow_dec = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                else:
                    allow_inc = _INF if math.isinf(d_hi) else max(0.0, d_hi)
                    allow_dec = _INF if math.isinf(d_lo) else max(0.0, -d_lo)
            else:
                reduced_cost = 0.0
                allow_inc = 0.0
                allow_dec = 0.0

        var_rows.append(
            (
                _clean_zero(reduced_cost),
                _clean_zero(c_j),
                allow_inc if allow_inc < _INF else _INF,
                allow_dec if allow_dec < _INF else _INF,
            )
        )

    alg_constraints = [c for c in compiled if c.kind in ("<=", "=", ">=")]
    con_rows: list[tuple[float, float, float, float]] = []
    for i, c in enumerate(alg_constraints):
        rhs_val = sol_vals[c.rhs_coord] if c.rhs_coord is not None else float(c.rhs_const or 0.0)
        if i in tab_info.dropped_rows or i >= len(tab_info.id_cols):
            con_rows.append((0.0, _clean_zero(rhs_val), 0.0, 0.0))
            continue

        id_col = tab_info.id_cols[i]
        flip = tab_info.row_flips[i]
        sp_min = -flip * obj2[id_col]
        shadow_price = _clean_zero(-sp_min if is_max else sp_min)

        delta_lo = float("-inf")
        delta_hi = float("inf")
        for r_idx, row in enumerate(tableau):
            d_r = row[id_col]
            rhs_bar = max(0.0, row[total_cols])
            if d_r > 1e-12:
                delta_lo = max(delta_lo, -rhs_bar / d_r)
            elif d_r < -1e-12:
                delta_hi = min(delta_hi, -rhs_bar / d_r)

        if flip > 0.0:
            allow_inc = _INF if math.isinf(delta_hi) else max(0.0, delta_hi)
            allow_dec = _INF if math.isinf(delta_lo) else max(0.0, -delta_lo)
        else:
            allow_inc = _INF if math.isinf(delta_lo) else max(0.0, -delta_lo)
            allow_dec = _INF if math.isinf(delta_hi) else max(0.0, delta_hi)

        con_rows.append(
            (
                shadow_price,
                _clean_zero(rhs_val),
                allow_inc if allow_inc < _INF else _INF,
                allow_dec if allow_dec < _INF else _INF,
            )
        )

    return var_rows, con_rows


def _compute_nonlinear_sensitivity(
    evaluator: _WorkbookEvaluator,
    params: SolverParams,
    obj_coord: tuple[str, int, int],
    var_coords: list[tuple[str, int, int]],
    sol_vec: list[float],
    compiled: list[_CompiledConstraint],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Estimate variable reduced gradients / objective partials and constraint shadow prices."""
    n = len(var_coords)
    lb, ub, _, _ = _compute_bounds(n, compiled, params.make_unconstrained_non_negative)
    alg_constraints = [c for c in compiled if c.kind in ("<=", "=", ">=")]

    ok0, vals0 = evaluator.evaluate_vector(sol_vec)
    if not ok0:
        return [(0.0, 0.0)] * n, [(0.0, float(c.rhs_const or 0.0)) for c in alg_constraints]

    # Finite-difference Jacobian for objective and algebraic constraints
    obj_grad = [0.0] * n
    con_grads: list[list[float]] = [[0.0] * n for _ in alg_constraints]

    def _con_val(vals: dict[tuple[str, int, int], float], c: _CompiledConstraint) -> float:
        lhs_v = vals[c.lhs_coords[0]]
        rhs_v = vals[c.rhs_coord] if c.rhs_coord is not None else float(c.rhs_const or 0.0)
        return lhs_v - rhs_v

    f0 = vals0[obj_coord]
    g0 = [_con_val(vals0, c) for c in alg_constraints]

    for j in range(n):
        step = 1e-5 * max(1.0, abs(sol_vec[j]))
        x_p = list(sol_vec)
        x_p[j] += step
        can_p = ub[j] is None or x_p[j] <= float(ub[j]) + 1e-12
        ok_p, vals_p = evaluator.evaluate_vector(x_p) if can_p else (False, {})

        x_m = list(sol_vec)
        x_m[j] -= step
        can_m = lb[j] is None or x_m[j] >= float(lb[j]) - 1e-12
        ok_m, vals_m = evaluator.evaluate_vector(x_m) if can_m else (False, {})

        if ok_p and ok_m:
            obj_grad[j] = (vals_p[obj_coord] - vals_m[obj_coord]) / (2.0 * step)
            for k, c in enumerate(alg_constraints):
                con_grads[k][j] = (_con_val(vals_p, c) - _con_val(vals_m, c)) / (2.0 * step)
        elif ok_p:
            obj_grad[j] = (vals_p[obj_coord] - f0) / step
            for k, c in enumerate(alg_constraints):
                con_grads[k][j] = (_con_val(vals_p, c) - g0[k]) / step
        elif ok_m:
            obj_grad[j] = (f0 - vals_m[obj_coord]) / step
            for k, c in enumerate(alg_constraints):
                con_grads[k][j] = (g0[k] - _con_val(vals_m, c)) / step

    # Identify active algebraic constraints and free (non-bound-pinned) variables
    tol = max(params.options.precision * 100.0, 1e-4)
    active_idx = [k for k, g_val in enumerate(g0) if abs(g_val) <= tol]
    free_vars = [
        j
        for j in range(n)
        if not (
            (lb[j] is not None and abs(sol_vec[j] - float(lb[j])) <= 1e-6)
            or (ub[j] is not None and abs(sol_vec[j] - float(ub[j])) <= 1e-6)
        )
    ]
    if not free_vars:
        free_vars = list(range(n))

    shadow_prices = [0.0] * len(alg_constraints)
    if active_idx:
        m_act = len(active_idx)
        normal_mat = [[0.0] * m_act for _ in range(m_act)]
        normal_rhs = [0.0] * m_act
        for a in range(m_act):
            ka = active_idx[a]
            normal_rhs[a] = sum(con_grads[ka][j] * obj_grad[j] for j in free_vars)
            for b in range(m_act):
                kb = active_idx[b]
                normal_mat[a][b] = sum(con_grads[ka][j] * con_grads[kb][j] for j in free_vars)
            normal_mat[a][a] += 1e-10
        lam = _solve_linear_system(normal_mat, normal_rhs)
        if lam is not None:
            for a, ka in enumerate(active_idx):
                shadow_prices[ka] = _clean_zero(lam[a])

    var_rows: list[tuple[float, float]] = []
    for j in range(n):
        red_grad = obj_grad[j] - sum(shadow_prices[k] * con_grads[k][j] for k in active_idx)
        var_rows.append((_clean_zero(red_grad), _clean_zero(obj_grad[j])))

    con_rows: list[tuple[float, float]] = []
    for k, c in enumerate(alg_constraints):
        rhs_v = vals0[c.rhs_coord] if c.rhs_coord is not None else float(c.rhs_const or 0.0)
        con_rows.append((shadow_prices[k], _clean_zero(rhs_v)))

    return var_rows, con_rows


def generate_answer_report(
    workbook: WorkbookModel, params: SolverParams, result: SolverResult
) -> str:
    """Create a unique Answer Report worksheet summarizing objective, variables, and constraints."""
    sheet_name, report_sh = _create_report_sheet(workbook, "Answer Report")

    def write_cell(r: int, c: int, val: Any, bold: bool = False) -> None:
        report_sh.set_cell(r, c, CellData(value=val, bold=bold))

    row = 0
    write_cell(row, 0, safe_tr("规划求解运算结果报告"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("状态"), bold=True)
    write_cell(row, 1, result.message)
    row += 2

    # Objective Cell section
    write_cell(row, 0, safe_tr("目标单元格"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("单元格"), bold=True)
    write_cell(row, 1, safe_tr("公式"), bold=True)
    write_cell(row, 2, safe_tr("初值"), bold=True)
    write_cell(row, 3, safe_tr("终值"), bold=True)
    row += 1

    obj_formula = ""
    try:
        o_sh_name, o_r, o_c = _parse_single_cell(params.objective_ref, params.default_sheet)
        o_sh = _get_sheet(workbook, o_sh_name)
        o_cell = o_sh.get_cell(o_r, o_c) if o_sh is not None else None
        if o_cell is not None and o_cell.formula:
            obj_formula = o_cell.formula
    except ValueError:
        obj_formula = ""

    write_cell(row, 0, result.objective_ref)
    write_cell(row, 1, obj_formula)
    write_cell(row, 2, result.initial_objective)
    write_cell(row, 3, result.final_objective)
    row += 2

    # Variable Cells section
    write_cell(row, 0, safe_tr("可变单元格"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("单元格"), bold=True)
    write_cell(row, 1, safe_tr("初值"), bold=True)
    write_cell(row, 2, safe_tr("终值"), bold=True)
    row += 1

    for ref_key, init_v in result.initial_values.items():
        fin_v = result.solution_values.get(ref_key, init_v)
        write_cell(row, 0, ref_key)
        write_cell(row, 1, init_v)
        write_cell(row, 2, fin_v)
        row += 1
    row += 1

    # Constraints section
    write_cell(row, 0, safe_tr("约束"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("单元格"), bold=True)
    write_cell(row, 1, safe_tr("公式"), bold=True)
    write_cell(row, 2, safe_tr("单元格值"), bold=True)
    write_cell(row, 3, safe_tr("状态"), bold=True)
    write_cell(row, 4, safe_tr("松弛量"), bold=True)
    row += 1

    for item in result.constraint_reports:
        expr = f"{item.cell_ref} {item.op} {item.rhs_value}".strip()
        status_txt = safe_tr("绑定") if item.binding else safe_tr("非绑定")
        write_cell(row, 0, item.cell_ref)
        write_cell(row, 1, item.formula or expr)
        write_cell(row, 2, item.cell_value)
        write_cell(row, 3, status_txt)
        write_cell(row, 4, item.slack)
        row += 1

    return sheet_name


def generate_sensitivity_report(
    workbook: WorkbookModel, params: SolverParams, result: SolverResult
) -> str:
    """Create a unique Sensitivity Report worksheet with LP tableau or gradient sensitivity."""
    sheet_name, report_sh = _create_report_sheet(workbook, "Sensitivity Report")

    def write_cell(r: int, c: int, val: Any, bold: bool = False) -> None:
        report_sh.set_cell(r, c, CellData(value=val, bold=bold))

    row = 0
    write_cell(row, 0, safe_tr("规划求解灵敏度报告"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("状态"), bold=True)
    write_cell(row, 1, result.message)
    row += 2

    obj_coord, var_coords, initial_vec, compiled, err_msg = _validate_and_compile(workbook, params)
    var_sens: list[tuple[float, float, Any, Any]] = []
    con_sens: list[tuple[float, float, Any, Any]] = []

    if err_msg is None and obj_coord is not None and var_coords:
        sol_vec = _solution_vector_from_result(var_coords, initial_vec, params, result)
        watch_set: set[tuple[str, int, int]] = {obj_coord}
        for c in compiled:
            watch_set.update(c.lhs_coords)
            if c.rhs_coord is not None:
                watch_set.add(c.rhs_coord)

        evaluator = _WorkbookEvaluator(workbook, var_coords, sorted(watch_set))
        try:
            ok_prep, _ = evaluator.prepare()
            if ok_prep:
                lp_sens = None
                if result.success:
                    lp_sens = _compute_lp_sensitivity(
                        evaluator, params, obj_coord, var_coords, initial_vec, compiled
                    )
                if lp_sens is not None:
                    var_rows, con_rows = lp_sens
                    var_sens = list(var_rows)
                    con_sens = list(con_rows)
                else:
                    nl_vars, nl_cons = _compute_nonlinear_sensitivity(
                        evaluator, params, obj_coord, var_coords, sol_vec, compiled
                    )
                    na_lbl = safe_tr("不适用")
                    var_sens = [(rc, oc, na_lbl, na_lbl) for rc, oc in nl_vars]
                    con_sens = [(sp, rhs_v, na_lbl, na_lbl) for sp, rhs_v in nl_cons]
        finally:
            evaluator.restore()

    # Variable Cells section
    write_cell(row, 0, safe_tr("可变单元格"), bold=True)
    row += 1
    for col, title in enumerate(
        (
            safe_tr("单元格"),
            safe_tr("终值"),
            safe_tr("递减成本"),
            safe_tr("目标系数"),
            safe_tr("允许的增量"),
            safe_tr("允许的减量"),
        )
    ):
        write_cell(row, col, title, bold=True)
    row += 1

    na_lbl = safe_tr("不适用")
    if var_coords:
        sol_vec = _solution_vector_from_result(var_coords, initial_vec, params, result)
        for j, coord in enumerate(var_coords):
            ref_key = format_cell_ref(*coord, params.default_sheet)
            fin_v = sol_vec[j]
            rc, oc, a_inc, a_dec = var_sens[j] if j < len(var_sens) else (0.0, 0.0, na_lbl, na_lbl)
            write_cell(row, 0, ref_key)
            write_cell(row, 1, fin_v)
            write_cell(row, 2, rc)
            write_cell(row, 3, oc)
            write_cell(row, 4, a_inc)
            write_cell(row, 5, a_dec)
            row += 1
    else:
        for ref_key, init_v in result.initial_values.items():
            fin_v = result.solution_values.get(ref_key, init_v)
            write_cell(row, 0, ref_key)
            write_cell(row, 1, fin_v)
            write_cell(row, 2, 0.0)
            write_cell(row, 3, 0.0)
            write_cell(row, 4, na_lbl)
            write_cell(row, 5, na_lbl)
            row += 1
    row += 1

    # Constraints section
    write_cell(row, 0, safe_tr("约束"), bold=True)
    row += 1
    for col, title in enumerate(
        (
            safe_tr("单元格"),
            safe_tr("终值"),
            safe_tr("阴影价格"),
            safe_tr("约束右侧值"),
            safe_tr("允许的增量"),
            safe_tr("允许的减量"),
        )
    ):
        write_cell(row, col, title, bold=True)
    row += 1

    alg_idx = 0
    for item in result.constraint_reports:
        write_cell(row, 0, item.cell_ref)
        write_cell(row, 1, item.cell_value)
        if item.op in ("<=", "=", ">="):
            if alg_idx < len(con_sens):
                sp, rhs_v, a_inc, a_dec = con_sens[alg_idx]
            else:
                sp, rhs_v, a_inc, a_dec = (0.0, item.rhs_value, na_lbl, na_lbl)
            alg_idx += 1
            write_cell(row, 2, sp)
            write_cell(row, 3, rhs_v)
            write_cell(row, 4, a_inc)
            write_cell(row, 5, a_dec)
        else:
            write_cell(row, 2, 0.0)
            write_cell(row, 3, item.op)
            write_cell(row, 4, na_lbl)
            write_cell(row, 5, na_lbl)
        row += 1

    return sheet_name


def _find_1d_feasible_limits(
    evaluator: _WorkbookEvaluator,
    obj_coord: tuple[str, int, int],
    var_idx: int,
    sol_vec: list[float],
    compiled: list[_CompiledConstraint],
    lb: float | None,
    ub: float | None,
    is_int: bool,
    is_bin: bool,
    params: SolverParams,
) -> tuple[float | None, float | None, float | None, float | None]:
    """Find feasible (lower_val, lower_obj, upper_val, upper_obj) for variable var_idx."""
    feas_tol = max(params.options.precision * 100.0, 1e-4)
    n = len(sol_vec)
    all_lb, all_ub, _, _ = _compute_bounds(n, compiled, params.make_unconstrained_non_negative)

    def eval_point(t: float) -> tuple[bool, float | None]:
        trial = list(sol_vec)
        trial[var_idx] = t
        ok, vals = evaluator.evaluate_vector(trial)
        if not ok:
            return False, None
        _, _, viol = _constraint_residuals(trial, vals, compiled, all_lb, all_ub)
        obj_v = vals[obj_coord]
        if params.goal == "value_of":
            viol += abs(obj_v - params.target_value)
        return viol <= feas_tol, obj_v

    x_star = sol_vec[var_idx]
    ok_star, obj_star = eval_point(x_star)
    if not ok_star or obj_star is None:
        return x_star, result_obj_fallback(obj_star), x_star, result_obj_fallback(obj_star)

    if is_bin:
        candidates = [v for v in (0.0, 1.0) if eval_point(v)[0]]
        lo_v = min(candidates) if candidates else x_star
        hi_v = max(candidates) if candidates else x_star
        _, lo_obj = eval_point(lo_v)
        _, hi_obj = eval_point(hi_v)
        return lo_v, lo_obj, hi_v, hi_obj

    if is_int:

        def search_int(direction: int) -> tuple[float | None, float | None]:
            bound = lb if direction < 0 else ub
            cur = float(round(x_star))
            best = cur
            best_obj = obj_star
            step = 1
            for _ in range(40):
                nxt = cur + direction * step
                if bound is not None:
                    if (direction < 0 and nxt < bound - 1e-9) or (
                        direction > 0 and nxt > bound + 1e-9
                    ):
                        nxt = float(math.ceil(bound) if direction < 0 else math.floor(bound))
                if abs(nxt - cur) < 0.5:
                    break
                ok_n, obj_n = eval_point(nxt)
                if ok_n and obj_n is not None:
                    cur = nxt
                    best = nxt
                    best_obj = obj_n
                    if bound is not None and abs(nxt - bound) < 1.0:
                        break
                    step = min(step * 2, 10000)
                else:
                    # Binary search between cur (feasible) and nxt (infeasible)
                    lo_i = int(round(min(cur, nxt)))
                    hi_i = int(round(max(cur, nxt)))
                    while lo_i + 1 < hi_i:
                        mid = (lo_i + hi_i) // 2
                        ok_m, _ = eval_point(float(mid))
                        if direction < 0:
                            if ok_m:
                                hi_i = mid
                            else:
                                lo_i = mid
                        else:
                            if ok_m:
                                lo_i = mid
                            else:
                                hi_i = mid
                    fin_i = float(hi_i if direction < 0 else lo_i)
                    ok_f, obj_f = eval_point(fin_i)
                    return (fin_i, obj_f) if ok_f else (best, best_obj)
                if abs(cur - x_star) >= 1e6:
                    return None, None
            if bound is None and abs(best - x_star) >= 1e6:
                return None, None
            return best, best_obj

        lo_v, lo_obj = search_int(-1)
        hi_v, hi_obj = search_int(1)
        return lo_v, lo_obj, hi_v, hi_obj

    # Continuous search via exponential expansion + bisection
    def search_cont(direction: int) -> tuple[float | None, float | None]:
        bound = lb if direction < 0 else ub
        if bound is not None and abs(x_star - bound) <= 1e-9:
            return _clean_zero(float(bound)), obj_star

        last_feas = x_star
        last_obj = obj_star
        infeas_pt: float | None = None
        for step in (1e-3, 1e-2, 1e-1, 1.0, 2.0, 5.0, 10.0, 50.0, 200.0, 1e3, 1e4, 1e5, 1e6):
            cand = x_star + direction * step
            hit_bound = False
            if bound is not None:
                if (direction < 0 and cand <= bound) or (direction > 0 and cand >= bound):
                    cand = float(bound)
                    hit_bound = True
            ok_c, obj_c = eval_point(cand)
            if ok_c and obj_c is not None:
                last_feas = cand
                last_obj = obj_c
                if hit_bound:
                    return _clean_zero(last_feas), last_obj
            else:
                infeas_pt = cand
                break

        if infeas_pt is None:
            if bound is not None:
                return _clean_zero(float(bound)), last_obj
            return None, None

        f_pt = last_feas
        i_pt = infeas_pt
        for _ in range(40):
            mid = 0.5 * (f_pt + i_pt)
            ok_m, obj_m = eval_point(mid)
            if ok_m and obj_m is not None:
                f_pt = mid
                last_obj = obj_m
            else:
                i_pt = mid
            if abs(i_pt - f_pt) <= 1e-9 * max(1.0, abs(f_pt)):
                break
        return _clean_zero(f_pt), last_obj

    lo_v, lo_obj = search_cont(-1)
    hi_v, hi_obj = search_cont(1)
    return lo_v, lo_obj, hi_v, hi_obj


def result_obj_fallback(val: float | None) -> float | None:
    """Pass through optional objective value."""
    return val


def generate_limits_report(
    workbook: WorkbookModel, params: SolverParams, result: SolverResult
) -> str:
    """Create a unique Limits Report worksheet showing feasible variable bounds and objectives."""
    sheet_name, report_sh = _create_report_sheet(workbook, "Limits Report")

    def write_cell(r: int, c: int, val: Any, bold: bool = False) -> None:
        report_sh.set_cell(r, c, CellData(value=val, bold=bold))

    row = 0
    write_cell(row, 0, safe_tr("规划求解极限值报告"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("状态"), bold=True)
    write_cell(row, 1, result.message)
    row += 2

    # Objective Cell section
    write_cell(row, 0, safe_tr("目标单元格"), bold=True)
    row += 1
    write_cell(row, 0, safe_tr("单元格"), bold=True)
    write_cell(row, 1, safe_tr("终值"), bold=True)
    row += 1
    write_cell(row, 0, result.objective_ref)
    write_cell(row, 1, result.final_objective)
    row += 2

    # Variable Cells section
    write_cell(row, 0, safe_tr("可变单元格"), bold=True)
    row += 1
    for col, title in enumerate(
        (
            safe_tr("单元格"),
            safe_tr("终值"),
            safe_tr("下限"),
            safe_tr("目标结果"),
            safe_tr("上限"),
            safe_tr("目标结果"),
        )
    ):
        write_cell(row, col, title, bold=True)
    row += 1

    unlim_lbl = safe_tr("无限制")
    obj_coord, var_coords, initial_vec, compiled, err_msg = _validate_and_compile(workbook, params)
    if err_msg is None and obj_coord is not None and var_coords:
        sol_vec = _solution_vector_from_result(var_coords, initial_vec, params, result)
        n = len(var_coords)
        lb, ub, int_indices, bin_indices = _compute_bounds(
            n, compiled, params.make_unconstrained_non_negative
        )
        watch_set: set[tuple[str, int, int]] = {obj_coord}
        for c in compiled:
            watch_set.update(c.lhs_coords)
            if c.rhs_coord is not None:
                watch_set.add(c.rhs_coord)

        # Try exact analytical bounds when pure continuous LP
        exact_lp_bounds: list[tuple[float | None, float | None]] | None = None
        evaluator = _WorkbookEvaluator(workbook, var_coords, sorted(watch_set))
        try:
            ok_prep, _ = evaluator.prepare()
            if ok_prep:
                if (
                    params.method == "simplex_lp"
                    and params.goal != "value_of"
                    and not int_indices
                    and not any(c.kind == "dif" for c in compiled)
                ):
                    ok_lin, _, _oc, _oconst, linear_rows = _extract_linear_model(
                        evaluator,
                        obj_coord,
                        compiled,
                        initial_vec,
                        params.make_unconstrained_non_negative,
                    )
                    if ok_lin:
                        exact_lp_bounds = []
                        for j in range(n):
                            lo_j = lb[j]
                            hi_j = ub[j]
                            for row_a, op, rhs in linear_rows:
                                a = row_a[j]
                                if abs(a) <= 1e-12:
                                    continue
                                other = sum(row_a[k] * sol_vec[k] for k in range(n) if k != j)
                                bound_t = (rhs - other) / a
                                if op == "=":
                                    lo_j = sol_vec[j] if lo_j is None else max(lo_j, sol_vec[j])
                                    hi_j = sol_vec[j] if hi_j is None else min(hi_j, sol_vec[j])
                                elif (op == "<=" and a > 0) or (op == ">=" and a < 0):
                                    hi_j = bound_t if hi_j is None else min(hi_j, bound_t)
                                else:
                                    lo_j = bound_t if lo_j is None else max(lo_j, bound_t)
                            if lo_j is not None and lo_j > sol_vec[j]:
                                lo_j = sol_vec[j]
                            if hi_j is not None and hi_j < sol_vec[j]:
                                hi_j = sol_vec[j]
                            exact_lp_bounds.append((lo_j, hi_j))

                for j, coord in enumerate(var_coords):
                    ref_key = format_cell_ref(*coord, params.default_sheet)
                    if exact_lp_bounds is not None:
                        lo_v, hi_v = exact_lp_bounds[j]
                        lo_obj: float | None = None
                        hi_obj: float | None = None
                        if lo_v is not None:
                            lo_v = _clean_zero(lo_v)
                            t_lo = list(sol_vec)
                            t_lo[j] = lo_v
                            ok_l, vals_l = evaluator.evaluate_vector(t_lo)
                            if ok_l:
                                lo_obj = _clean_zero(vals_l[obj_coord])
                        if hi_v is not None:
                            hi_v = _clean_zero(hi_v)
                            t_hi = list(sol_vec)
                            t_hi[j] = hi_v
                            ok_h, vals_h = evaluator.evaluate_vector(t_hi)
                            if ok_h:
                                hi_obj = _clean_zero(vals_h[obj_coord])
                    else:
                        lo_v, lo_obj, hi_v, hi_obj = _find_1d_feasible_limits(
                            evaluator,
                            obj_coord,
                            j,
                            sol_vec,
                            compiled,
                            lb[j],
                            ub[j],
                            j in int_indices,
                            j in bin_indices,
                            params,
                        )
                    write_cell(row, 0, ref_key)
                    write_cell(row, 1, _clean_zero(sol_vec[j]))
                    write_cell(row, 2, lo_v if lo_v is not None else unlim_lbl)
                    write_cell(row, 3, lo_obj if lo_obj is not None else "")
                    write_cell(row, 4, hi_v if hi_v is not None else unlim_lbl)
                    write_cell(row, 5, hi_obj if hi_obj is not None else "")
                    row += 1
        finally:
            evaluator.restore()
    else:
        for ref_key, init_v in result.initial_values.items():
            fin_v = result.solution_values.get(ref_key, init_v)
            write_cell(row, 0, ref_key)
            write_cell(row, 1, fin_v)
            write_cell(row, 2, unlim_lbl)
            write_cell(row, 3, "")
            write_cell(row, 4, unlim_lbl)
            write_cell(row, 5, "")
            row += 1

    return sheet_name


_GOAL_TO_TYP: dict[SolverGoal, str] = {"max": "1", "min": "2", "value_of": "3"}
_TYP_TO_GOAL: dict[str, SolverGoal] = {"1": "max", "2": "min", "3": "value_of"}

_METHOD_TO_ENG: dict[SolverMethod, str] = {
    "grg_nonlinear": "1",
    "simplex_lp": "2",
    "evolutionary": "3",
}
_ENG_TO_METHOD: dict[str, SolverMethod] = {
    "1": "grg_nonlinear",
    "2": "simplex_lp",
    "3": "evolutionary",
}

_OP_TO_REL: dict[ConstraintOp, str] = {
    "<=": "1",
    "=": "2",
    ">=": "3",
    "int": "4",
    "bin": "5",
    "dif": "6",
}
_REL_TO_OP: dict[str, ConstraintOp] = {v: k for k, v in _OP_TO_REL.items()}


def _qualify_defined_name_refs(refs_str: str, default_sheet: str) -> str:
    """Ensure cell/range tokens in a Solver reference list carry a sheet prefix for Excel."""
    clean = str(refs_str or "").strip()
    if not clean or not default_sheet:
        return clean
    if _parse_numeric_literal(clean) is not None:
        return clean
    try:
        tokens = _split_quoted_commas(clean)
    except ValueError:
        return clean
    qualified: list[str] = []
    prefix = quote_sheet(default_sheet)
    for tok in tokens:
        if not tok:
            continue
        if "!" in tok:
            qualified.append(tok)
        else:
            qualified.append(f"{prefix}!{tok}")
    return ",".join(qualified)


def _strip_matching_sheet_prefix(refs_str: str, sheet_name: str) -> str:
    """Strip matching ``sheet_name!`` prefix from comma-separated definedName tokens."""
    clean = str(refs_str or "").strip()
    if clean.startswith("="):
        clean = clean[1:].strip()
    if not clean:
        return ""
    if _parse_numeric_literal(clean) is not None:
        return clean
    try:
        tokens = _split_quoted_commas(clean)
    except ValueError:
        return clean
    target_lower = sheet_name.strip().lower()
    out: list[str] = []
    for tok in tokens:
        if not tok:
            continue
        try:
            tok_sheet, body = _split_sheet_prefix(tok, sheet_name)
        except ValueError:
            out.append(tok)
            continue
        if "!" in tok and tok_sheet.strip().lower() == target_lower:
            out.append(body)
        else:
            out.append(tok)
    return ", ".join(out) if len(out) > 1 else (out[0] if out else "")


def solver_params_to_defined_names(
    params: SolverParams, sheet_idx: int
) -> list[tuple[str, int, str]]:
    """Serialize ``SolverParams`` to Excel hidden sheet-scoped ``solver_*`` defined names."""
    sheet_name = params.default_sheet or "Sheet1"
    entries: list[tuple[str, int, str]] = []

    if params.objective_ref.strip():
        entries.append(
            ("solver_opt", sheet_idx, _qualify_defined_name_refs(params.objective_ref, sheet_name))
        )
    entries.append(("solver_typ", sheet_idx, _GOAL_TO_TYP.get(params.goal, "1")))
    entries.append(("solver_val", sheet_idx, str(params.target_value)))
    entries.append(
        ("solver_adj", sheet_idx, _qualify_defined_name_refs(params.variable_refs, sheet_name))
    )
    entries.append(("solver_num", sheet_idx, str(len(params.constraints))))

    for i, con in enumerate(params.constraints, start=1):
        entries.append(
            (f"solver_lhs{i}", sheet_idx, _qualify_defined_name_refs(con.lhs_ref, sheet_name))
        )
        entries.append((f"solver_rel{i}", sheet_idx, _OP_TO_REL.get(con.op, "1")))
        rhs_val = (
            ""
            if con.op in ("int", "bin", "dif")
            else _qualify_defined_name_refs(con.rhs, sheet_name)
        )
        entries.append((f"solver_rhs{i}", sheet_idx, rhs_val))

    neg_flag = "1" if params.make_unconstrained_non_negative else "2"
    entries.append(("solver_neg", sheet_idx, neg_flag))
    entries.append(("solver_eng", sheet_idx, _METHOD_TO_ENG.get(params.method, "2")))
    entries.append(("solver_itr", sheet_idx, str(params.options.max_iterations)))
    entries.append(("solver_tim", sheet_idx, str(params.options.max_time_sec)))
    entries.append(("solver_pre", sheet_idx, str(params.options.precision)))
    entries.append(("solver_tol", sheet_idx, str(params.options.integer_optimality)))
    entries.append(("solver_pop", sheet_idx, str(params.options.population_size)))
    entries.append(("solver_sed", sheet_idx, str(params.options.random_seed)))
    return entries


def solver_params_from_defined_names(
    entries: Sequence[tuple[str, int | None, str]],
    sheet_idx: int,
    sheet_name: str,
) -> SolverParams | None:
    """Reconstruct ``SolverParams`` for ``sheet_idx`` from Excel ``solver_*`` defined names."""
    scoped: dict[str, str] = {}
    for raw_name, local_id, raw_val in entries:
        if local_id != sheet_idx:
            continue
        key = str(raw_name or "").strip().lower()
        if key.startswith("solver_"):
            scoped[key] = str(raw_val or "").strip()

    if not scoped:
        return None
    if not scoped.get("solver_opt") and not scoped.get("solver_adj"):
        return None

    def _clean_num(val: str | None) -> str:
        s = (val or "").strip()
        if s.startswith("="):
            s = s[1:].strip()
        return s

    def _safe_int(val: str | None, default: int) -> int:
        try:
            return int(round(float(_clean_num(val))))
        except (TypeError, ValueError):
            return default

    def _safe_float(val: str | None, default: float) -> float:
        try:
            return float(_clean_num(val))
        except (TypeError, ValueError):
            return default

    goal = _TYP_TO_GOAL.get(_clean_num(scoped.get("solver_typ")), "max")
    target_value = _safe_float(scoped.get("solver_val"), 0.0)
    objective_ref = _strip_matching_sheet_prefix(scoped.get("solver_opt", ""), sheet_name)
    variable_refs = _strip_matching_sheet_prefix(scoped.get("solver_adj", ""), sheet_name)

    max_idx = _safe_int(scoped.get("solver_num"), 0)
    for k in scoped:
        if k.startswith("solver_lhs"):
            suffix = k[len("solver_lhs") :]
            if suffix.isdigit():
                max_idx = max(max_idx, int(suffix))

    constraints: list[SolverConstraint] = []
    for idx in range(1, max_idx + 1):
        lhs_raw = scoped.get(f"solver_lhs{idx}", "")
        rel_raw = _clean_num(scoped.get(f"solver_rel{idx}"))
        rhs_raw = scoped.get(f"solver_rhs{idx}", "")
        op = _REL_TO_OP.get(rel_raw)
        if op is None or not lhs_raw:
            continue
        lhs_ref = _strip_matching_sheet_prefix(lhs_raw, sheet_name)
        rhs = (
            "" if op in ("int", "bin", "dif") else _strip_matching_sheet_prefix(rhs_raw, sheet_name)
        )
        constraints.append(SolverConstraint(lhs_ref=lhs_ref, op=op, rhs=rhs))

    neg_raw = _clean_num(scoped.get("solver_neg")).lower()
    non_negative = False if neg_raw in ("0", "2", "false") else True

    method = _ENG_TO_METHOD.get(_clean_num(scoped.get("solver_eng")), "simplex_lp")
    defaults = SolverOptions()
    options = SolverOptions(
        max_iterations=_safe_int(scoped.get("solver_itr"), defaults.max_iterations),
        max_time_sec=_safe_float(scoped.get("solver_tim"), defaults.max_time_sec),
        precision=_safe_float(scoped.get("solver_pre"), defaults.precision),
        integer_optimality=_safe_float(scoped.get("solver_tol"), defaults.integer_optimality),
        population_size=_safe_int(scoped.get("solver_pop"), defaults.population_size),
        random_seed=_safe_int(scoped.get("solver_sed"), defaults.random_seed),
    )

    return SolverParams(
        objective_ref=objective_ref,
        goal=goal,
        target_value=target_value,
        variable_refs=variable_refs,
        constraints=constraints,
        make_unconstrained_non_negative=non_negative,
        method=method,
        default_sheet=sheet_name,
        options=options,
    )


def save_solver_model(sheet: Any, params: SolverParams) -> None:
    """Persist SolverParams into sheet.extra['solver_model'] as a JSON-serializable dict."""
    if not hasattr(sheet, "extra") or sheet.extra is None:
        sheet.extra = {}
    payload = asdict(params)
    sheet.extra["solver_model"] = payload


def load_solver_model(sheet: Any) -> SolverParams | None:
    """Restore SolverParams from sheet.extra['solver_model'], or return None if absent/invalid."""
    extra = getattr(sheet, "extra", None)
    if not isinstance(extra, dict):
        return None
    raw = extra.get("solver_model")
    if not isinstance(raw, dict):
        return None
    try:
        opts_raw = raw.get("options") or {}
        opts = SolverOptions(
            max_iterations=int(opts_raw.get("max_iterations", 200)),
            max_time_sec=float(opts_raw.get("max_time_sec", 30.0)),
            precision=float(opts_raw.get("precision", 1e-6)),
            integer_optimality=float(opts_raw.get("integer_optimality", 0.01)),
            population_size=int(opts_raw.get("population_size", 40)),
            random_seed=int(opts_raw.get("random_seed", 42)),
        )
        constraints: list[SolverConstraint] = []
        for c_raw in raw.get("constraints") or []:
            if isinstance(c_raw, dict) and "lhs_ref" in c_raw and "op" in c_raw:
                op = str(c_raw["op"])
                if op not in ("<=", "=", ">=", "int", "bin", "dif"):
                    continue
                constraints.append(
                    SolverConstraint(
                        lhs_ref=str(c_raw["lhs_ref"]),
                        op=op,  # type: ignore[arg-type]
                        rhs=str(c_raw.get("rhs", "")),
                    )
                )

        goal = str(raw.get("goal", "max"))
        if goal not in ("max", "min", "value_of"):
            goal = "max"
        method = str(raw.get("method", "simplex_lp"))
        if method not in ("simplex_lp", "grg_nonlinear", "evolutionary"):
            method = "simplex_lp"

        return SolverParams(
            objective_ref=str(raw.get("objective_ref", "")),
            goal=goal,  # type: ignore[arg-type]
            target_value=float(raw.get("target_value", 0.0)),
            variable_refs=str(raw.get("variable_refs", "")),
            constraints=constraints,
            make_unconstrained_non_negative=bool(raw.get("make_unconstrained_non_negative", True)),
            method=method,  # type: ignore[arg-type]
            default_sheet=str(raw.get("default_sheet", getattr(sheet, "name", "Sheet1"))),
            options=opts,
        )
    except (TypeError, ValueError, KeyError) as exc:
        logger.warning("Failed to load solver_model from sheet.extra: %s", exc)
        return None
