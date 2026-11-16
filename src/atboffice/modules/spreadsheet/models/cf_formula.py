"""Origin-relative formula evaluation for conditional formatting rules.

Excel stores a conditional-format formula as if it were written in the anchor
cell (the top-left cell of the first range in ``sqref``). For any other cell
in the range, relative references move by that cell's offset from the anchor
(see ``ledger/js/cf.js`` ``evalAt``).
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import ExcelError
from atboffice.modules.spreadsheet.calc.evaluator import evaluate_ast
from atboffice.modules.spreadsheet.calc.parser import parse
from atboffice.modules.spreadsheet.calc.references import shift

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.calc.tokens import ASTNode
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel

_PARSE_FAILED = object()


@lru_cache(maxsize=1024)
def _parse_cached(text: str) -> Any:
    """Parse formula text once; return ``_PARSE_FAILED`` on syntax errors."""
    body = text.strip()
    if body.startswith("="):
        body = body[1:]
    try:
        return parse(body)
    except Exception:  # noqa: BLE001 - any parser failure means "unusable formula"
        return _PARSE_FAILED


def can_parse(text: str) -> bool:
    """True if the formula text parses with the Ledger formula engine."""
    return _parse_cached(text) is not _PARSE_FAILED


def cell_display_value(sheet: SheetDataModel, r: int, c: int) -> Any:
    """Value of a cell for CF purposes: stored value, falling back to the cached result."""
    cell = sheet.get_cell(r, c)
    if cell is None:
        return None
    v = cell.value
    if (
        v is None or v == "" or (isinstance(v, str) and v.startswith("#"))
    ) and getattr(cell, "cached_value", None) is not None:
        v = cell.cached_value
    if isinstance(v, str) and v.startswith("="):
        # Unevaluated formula text: never feed it back into the evaluator.
        cached = getattr(cell, "cached_value", None)
        return cached
    return v


def eval_at(
    sheet: SheetDataModel,
    formula: str,
    anchor: tuple[int, int],
    r: int,
    c: int,
) -> Any:
    """Evaluate ``formula`` (written for ``anchor``) at cell (r, c).

    Returns the scalar result. Unparsable formulas yield ``#NAME?`` and
    evaluation failures yield ``#VALUE!``, matching the original engine.
    """
    ast = _parse_cached(formula)
    if ast is _PARSE_FAILED:
        return ExcelError("#NAME?")
    shifted: ASTNode = shift(ast, r - anchor[0], c - anchor[1])
    sheet_name = getattr(sheet, "name", "Sheet1") or "Sheet1"

    def getter(sh_name: str, rr: int, cc: int) -> Any:
        if sh_name and sh_name.lower() != sheet_name.lower():
            return None  # cross-sheet references are not resolvable from a sheet model
        return cell_display_value(sheet, rr, cc)

    ctx = EvalContext(
        cell_getter=getter,
        current_sheet=sheet_name,
        current_row=r,
        current_col=c,
    )
    try:
        v = evaluate_ast(shifted, ctx)
    except Exception:  # noqa: BLE001 - mirror the original: any failure is #VALUE!
        return ExcelError("#VALUE!")
    if isinstance(v, Ref):
        if v.single:
            v = v.cell_value(v.r1, v.c1)
        elif v.r1 <= r <= v.r2 and v.c1 == v.c2:
            v = v.cell_value(r, v.c1)  # implicit intersection on the row
        elif v.c1 <= c <= v.c2 and v.r1 == v.r2:
            v = v.cell_value(v.r1, c)  # implicit intersection on the column
        else:
            v = ExcelError("#VALUE!")
    elif isinstance(v, Arr):
        v = v.data[0][0] if v.data and v.data[0] else None
    return v


def truthy(v: Any) -> bool:
    """Excel truthiness of a rule formula result (errors are never true)."""
    if isinstance(v, ExcelError):
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.upper() == "TRUE"
    return False
