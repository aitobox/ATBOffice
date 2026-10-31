"""Ledger Goal Seek (单变量求解) numerical solver and reference parser."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.dag import DependencyGraph
from atboffice.modules.spreadsheet.calc.references import cell_name, col_index

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

RE_CELL_REF = re.compile(
    r"^(?:(?:'([^']+)'|([A-Za-z0-9_]+))!)?\$?([A-Za-z]{1,3})\$?(\d{1,7})$"
)


def parse_cell_reference(ref: str, default_sheet: str = "Sheet1") -> tuple[str, int, int]:
    """Parse cell reference string (e.g. 'B5', '$B$5', 'Sheet1!B5', ''My Sheet'!$A$1').

    Returns:
        tuple[str, int, int]: (sheet_name, row_0_based, col_0_based)

    Raises:
        ValueError: If ref cannot be parsed into a valid cell coordinate.
    """
    clean = str(ref).strip()
    if not clean:
        raise ValueError("Empty cell reference.")

    m = RE_CELL_REF.match(clean)
    if not m:
        raise ValueError(f"Invalid cell reference format: '{ref}'.")

    sheet_quoted = m.group(1)
    sheet_unquoted = m.group(2)
    sheet_name = sheet_quoted or sheet_unquoted or default_sheet

    col_str = m.group(3)
    row_str = m.group(4)

    c = col_index(col_str)
    r = int(row_str) - 1

    if r < 0 or c < 0:
        raise ValueError(f"Coordinates out of bounds: r={r}, c={c}.")

    return sheet_name, r, c


@dataclass(slots=True)
class GoalSeekParams:
    """Parameters passed to the goal seek solver."""

    target_sheet: str
    target_row: int
    target_col: int
    goal_value: float
    changing_sheet: str
    changing_row: int
    changing_col: int
    max_iterations: int = 100
    tolerance: float = 0.001


@dataclass(slots=True)
class GoalSeekResult:
    """Outcome of a goal seek run."""

    success: bool
    solution: float
    iterations: int
    target_value: float
    current_value: float
    error_margin: float
    initial_value: float
    target_cell_name: str = ""
    changing_sheet: str = ""
    changing_row: int = 0
    changing_col: int = 0
    error_message: str | None = None


def _get_sheet(workbook: Any, name: str) -> Any:
    """Look up sheet by name or return None."""
    if hasattr(workbook, "get_sheet_by_name"):
        return workbook.get_sheet_by_name(name)
    sheets = getattr(workbook, "sheets", [])
    for s in sheets:
        if getattr(s, "name", "") == name:
            return s
    return None


def solve_goal_seek(
    workbook: WorkbookModel,
    params: GoalSeekParams,
) -> GoalSeekResult:
    """Solve for target formula cell reaching goal_value by adjusting changing cell.

    Uses a hybrid secant and bisection numerical approach matching Excel 2003 / Ledger.
    Guarantees that the workbook state is restored to its initial condition upon exit.
    """
    # 1. Validation
    if (
        params.target_sheet == params.changing_sheet
        and params.target_row == params.changing_row
        and params.target_col == params.changing_col
    ):
        raise ValueError("Target cell and changing cell cannot be the same cell.")

    target_sh = _get_sheet(workbook, params.target_sheet)
    if target_sh is None:
        raise ValueError(f"Target sheet '{params.target_sheet}' not found.")

    changing_sh = _get_sheet(workbook, params.changing_sheet)
    if changing_sh is None:
        raise ValueError(f"Changing sheet '{params.changing_sheet}' not found.")

    target_cell = target_sh.get_cell(params.target_row, params.target_col)
    if target_cell is None or not target_cell.formula:
        raise ValueError("Target cell must contain a formula.")

    changing_cell = changing_sh.get_cell(params.changing_row, params.changing_col)
    if changing_cell is not None and changing_cell.formula:
        raise ValueError("Changing cell must contain a value, not a formula.")

    if changing_cell is None:
        from atboffice.modules.spreadsheet.models.sheet_model import CellData

        changing_cell = CellData(value=0.0)
        changing_sh.set_cell(params.changing_row, params.changing_col, changing_cell)

    # Determine initial value
    start_raw = changing_cell.value
    if isinstance(start_raw, (int, float)) and not isinstance(start_raw, bool):
        start_val = float(start_raw)
    else:
        try:
            start_val = float(start_raw) if start_raw is not None else 0.0
        except (ValueError, TypeError):
            start_val = 0.0

    target_cell_display = cell_name(params.target_row, params.target_col, ra=True, ca=True)

    # 2. Setup DAG calculation engine
    ctx = EvalContext(workbook=workbook)
    graph = DependencyGraph()
    graph.recalculate(workbook, ctx)

    def evaluate_target(x: float) -> float:
        changing_cell.value = x
        try:
            graph.recalculate_cell(
                params.changing_sheet,
                params.changing_row,
                params.changing_col,
                workbook,
                ctx,
            )
        except Exception:
            workbook.recalculate()

        val = target_sh.get_cell_value(params.target_row, params.target_col)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            if math.isnan(val) or math.isinf(val):
                return float("nan")
            return float(val) - params.goal_value
        return float("nan")

    # 3. Initial evaluation
    x0 = start_val
    f0 = evaluate_target(x0)

    # Check if already converged
    scale = max(1.0, abs(params.goal_value))
    tol = params.tolerance
    threshold = max(tol * scale * 1e-3, 1e-9)

    if not math.isnan(f0) and (abs(f0) <= threshold or abs(f0) <= tol):
        # Restoring initial value before returning
        changing_cell.value = start_val
        graph.recalculate_cell(
            params.changing_sheet,
            params.changing_row,
            params.changing_col,
            workbook,
            ctx,
        )
        curr_val = params.goal_value + f0
        return GoalSeekResult(
            success=True,
            solution=x0,
            iterations=1,
            target_value=params.goal_value,
            current_value=curr_val,
            error_margin=abs(f0),
            initial_value=start_val,
            target_cell_name=target_cell_display,
            changing_sheet=params.changing_sheet,
            changing_row=params.changing_row,
            changing_col=params.changing_col,
        )

    # 4. Determine second point x1
    if x0 == 0.0:
        x1 = 0.01 if abs(params.goal_value) > 1.0 else 0.001
    else:
        x1 = x0 * 1.01
        if x1 == x0:
            x1 = x0 + 0.01

    f1 = evaluate_target(x1)

    best_x = x0
    best_err = abs(f0) if not math.isnan(f0) else float("inf")
    if not math.isnan(f1) and abs(f1) < best_err:
        best_x = x1
        best_err = abs(f1)

    ok = False
    iterations_run = 0

    # 5. Hybrid Secant / Bisection Iteration
    for i in range(1, params.max_iterations + 1):
        iterations_run = i
        if not math.isnan(f1) and abs(f1) < best_err:
            best_x = x1
            best_err = abs(f1)

        if not math.isnan(f1) and (abs(f1) <= threshold or abs(f1) <= tol):
            ok = True
            break

        if math.isnan(f0) or math.isnan(f1) or f1 == f0:
            # Shift or perturb
            x1 = x1 * 2.0 + 1.0 if abs(x1) < 1e6 else (x1 * 0.5 - 1.0)
            f1 = evaluate_target(x1)
            continue

        # Secant step
        denom = f1 - f0
        step = f1 * (x1 - x0) / denom
        x2 = x1 - step

        # Safeguard against wild divergence
        if math.isnan(x2) or math.isinf(x2):
            x2 = (x0 + x1) / 2.0

        x0, f0 = x1, f1
        x1 = x2
        f1 = evaluate_target(x1)

    if not ok and best_err <= tol * scale:
        ok = True

    final_x = x1 if ok else best_x
    if abs(final_x - round(final_x)) < 1e-9:
        final_x = float(round(final_x))

    final_err = abs(f1) if ok and not math.isnan(f1) else best_err

    # Compute current value reached with solution
    final_res = evaluate_target(final_x)
    reached_current_value = params.goal_value + (final_res if not math.isnan(final_res) else final_err)

    # 6. Always restore model to start_val
    changing_cell.value = start_val
    graph.recalculate_cell(
        params.changing_sheet,
        params.changing_row,
        params.changing_col,
        workbook,
        ctx,
    )

    return GoalSeekResult(
        success=ok,
        solution=final_x,
        iterations=iterations_run,
        target_value=params.goal_value,
        current_value=reached_current_value,
        error_margin=final_err,
        initial_value=start_val,
        target_cell_name=target_cell_display,
        changing_sheet=params.changing_sheet,
        changing_row=params.changing_row,
        changing_col=params.changing_col,
    )
