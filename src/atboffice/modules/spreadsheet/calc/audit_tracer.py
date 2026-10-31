"""Formula auditing tracer for precedents, dependents, and calculation error trees."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from atboffice.modules.spreadsheet.calc.dag import (
    CellAddress,
    CellRange,
    DependencyGraph,
    extract_precedents,
)
from atboffice.modules.spreadsheet.calc.parser import parse

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


@dataclass
class AuditArrow:
    """Directed connection from a precedent cell/range to a dependent cell."""

    from_sheet: str
    from_r1: int
    from_c1: int
    from_r2: int
    from_c2: int
    to_sheet: str
    to_r: int
    to_c: int
    is_error: bool = False

    @property
    def is_range(self) -> bool:
        """Return True if the source is a multi-cell range."""
        return (self.from_r1 != self.from_r2) or (self.from_c1 != self.from_c2)

    @property
    def is_cross_sheet(self) -> bool:
        """Return True if the connection crosses worksheets."""
        return self.from_sheet != self.to_sheet


class AuditTracer:
    """Service providing formula auditing inspection (precedents, dependents, errors)."""

    @classmethod
    def trace_precedents(
        cls,
        workbook: WorkbookModel | None,
        sheet_name: str,
        r: int,
        c: int,
        is_error: bool = False,
    ) -> list[AuditArrow]:
        """Extract all precedent cell and range references for the formula at (r, c)."""
        sheet = cls._get_sheet(workbook, sheet_name)
        if sheet is None:
            return []

        cell = sheet.get_cell(r, c)
        if cell is None or not cell.formula:
            return []

        formula_text = cell.formula
        if formula_text.startswith("="):
            formula_text = formula_text[1:]

        try:
            ast = parse(formula_text)
        except Exception:
            return []

        prec_res = extract_precedents(ast, default_sheet=sheet_name)
        arrows: list[AuditArrow] = []
        for ref in prec_res.refs:
            if isinstance(ref, CellAddress):
                arrows.append(
                    AuditArrow(
                        from_sheet=ref.sheet,
                        from_r1=ref.r,
                        from_c1=ref.c,
                        from_r2=ref.r,
                        from_c2=ref.c,
                        to_sheet=sheet_name,
                        to_r=r,
                        to_c=c,
                        is_error=is_error,
                    )
                )
            elif isinstance(ref, CellRange):
                arrows.append(
                    AuditArrow(
                        from_sheet=ref.sheet,
                        from_r1=ref.r1,
                        from_c1=ref.c1,
                        from_r2=ref.r2,
                        from_c2=ref.c2,
                        to_sheet=sheet_name,
                        to_r=r,
                        to_c=c,
                        is_error=is_error,
                    )
                )
        return arrows

    @classmethod
    def trace_dependents(
        cls,
        workbook: WorkbookModel | None,
        sheet_name: str,
        r: int,
        c: int,
    ) -> list[AuditArrow]:
        """Query DAG for all formula cells across workbook that depend on (sheet_name, r, c)."""
        if workbook is None:
            return []

        # Build dependency graph from workbook sheets
        graph = DependencyGraph()
        for s in workbook.sheets:
            for (cr, cc), cell in s.cells.items():
                if cell and cell.formula:
                    ftext = cell.formula
                    if ftext.startswith("="):
                        ftext = ftext[1:]
                    try:
                        ast = parse(ftext)
                        graph.set_cell_formula(s.name, cr, cc, ast)
                    except Exception:
                        pass

        deps = graph.get_dependents(sheet_name, r, c)
        arrows: list[AuditArrow] = []
        for dep in deps:
            arrows.append(
                AuditArrow(
                    from_sheet=sheet_name,
                    from_r1=r,
                    from_c1=c,
                    from_r2=r,
                    from_c2=c,
                    to_sheet=dep.sheet,
                    to_r=dep.r,
                    to_c=dep.c,
                    is_error=False,
                )
            )
        return arrows

    @classmethod
    def trace_error(
        cls,
        workbook: WorkbookModel | None,
        sheet_name: str,
        r: int,
        c: int,
    ) -> list[AuditArrow]:
        """Trace precedents for a cell containing a formula calculation error."""
        return cls.trace_precedents(
            workbook=workbook,
            sheet_name=sheet_name,
            r=r,
            c=c,
            is_error=True,
        )

    @staticmethod
    def _get_sheet(
        workbook: WorkbookModel | None, sheet_name: str
    ) -> SheetDataModel | None:
        if workbook is None:
            return None
        for s in workbook.sheets:
            if s.name == sheet_name:
                return s
        return None
