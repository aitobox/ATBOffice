"""Tests for Phase 9 Excel Paste Special dialog semantics and execution engine.

Covers Issue #339:
1. PasteSpecialDialog UI, radio groups, options dictionary, and retranslate_ui.
2. Full semantic paste engine in GridViewport:
   - Arithmetic operations (add, sub, mul, div) and zero division (#DIV/0!).
   - Multi-cell destination tiling when selection is a multiple of source block dimensions.
   - Transpose dimension swapping (e.g. 2x3 block becomes 3x2 block).
   - Transpose relative formula coordinate translation.
   - Transpose with merged cells and comments.
   - Skip blanks behavior.
   - Paste Link (=Sheet!Cell).
   - Formats and No Borders (preserving target borders).
   - Column widths only.
   - Formulas and Number Formats (formulasNF) / Values and Number Formats (valuesNF).
   - Worksheet protection guard.
   - Undo/Redo fidelity.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.calc.references import transpose_formula
from atboffice.modules.spreadsheet.dialogs.paste_special_dialog import (
    PasteSpecialDialog,
)
from atboffice.modules.spreadsheet.models.selection_model import SelectionRange
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellComment,
    CellData,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


@pytest.fixture
def viewport(qapp: QApplication) -> GridViewport:
    model = SheetDataModel()
    vp = GridViewport(model=model)
    vp.resize(800, 600)
    controller = EditorController(
        viewport=vp,
        model=model,
        selection=vp.selection,
        formula_bar=None,
        parent=vp,
    )
    vp.editor_controller = controller
    return vp


class TestPasteSpecialDialog:
    """Test PasteSpecialDialog widget controls, options extraction, and i18n."""

    def test_dialog_default_options(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        opts = dlg.options
        assert opts["what"] == "all"
        assert opts["op"] == "none"
        assert opts["skip_blanks"] is False
        assert opts["transpose"] is False
        assert opts["link"] is False

    def test_dialog_select_options(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        dlg.rb_formulas.setChecked(True)
        dlg.rb_op_mul.setChecked(True)
        dlg.chk_skip_blanks.setChecked(True)
        dlg.chk_transpose.setChecked(True)

        opts = dlg.options
        assert opts["what"] == "formulas"
        assert opts["op"] == "mul"
        assert opts["skip_blanks"] is True
        assert opts["transpose"] is True

    def test_dialog_paste_link(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        dlg._on_paste_link()
        assert dlg.is_paste_link is True
        assert dlg.options["link"] is True

    def test_dialog_retranslate_ui(self, qapp: QApplication) -> None:
        dlg = PasteSpecialDialog()
        dlg.retranslate_ui()
        assert dlg.windowTitle() == "选择性粘贴"
        assert "全部" in dlg.rb_all.text()
        assert "加" in dlg.rb_op_add.text()
        assert "跳过空单元" in dlg.chk_skip_blanks.text()
        assert "转置" in dlg.chk_transpose.text()


class TestFormulaTransposition:
    """Test relative formula coordinate transposition."""

    def test_transpose_relative_cell_ref(self) -> None:
        # A1 (0,0) has =B1 (0,1). Relative offset is (0, 1).
        # Transposing from (0,0) to (2,2) [C3] swaps offset to (1, 0) -> C4 (3, 2).
        res = transpose_formula("=B1", 0, 0, 2, 2)
        assert res.upper() == "=C4"

    def test_transpose_relative_area_ref(self) -> None:
        # A1 (0,0) has =SUM(A1:A3). Vertical 3 rows -> becomes horizontal 3 cols C3:E3
        res = transpose_formula("=SUM(A1:A3)", 0, 0, 2, 2)
        assert res.upper() == "=SUM(C3:E3)"

    def test_transpose_absolute_ref_stays_fixed(self) -> None:
        res = transpose_formula("=$Z$99", 0, 0, 2, 2)
        assert res.upper() == "=$Z$99"


class TestPasteSpecialSemanticsEngine:
    """Test GridViewport Paste Special business operations and transformations."""

    def test_arithmetic_operations_and_div_zero(self, viewport: GridViewport) -> None:
        # Source cell with 4
        viewport.model.set_cell(0, 0, CellData(value=4))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Target cell with 12
        viewport.model.set_cell(2, 2, CellData(value=12))
        viewport.selection.select_cell(2, 2)

        # Add: 12 + 4 = 16
        viewport.paste_special({"what": "all", "op": "add"})
        assert viewport.model.get_cell_value(2, 2) == 16

        # Subtract: 16 - 4 = 12
        viewport.paste_special({"what": "all", "op": "sub"})
        assert viewport.model.get_cell_value(2, 2) == 12

        # Multiply: 12 * 4 = 48
        viewport.paste_special({"what": "all", "op": "mul"})
        assert viewport.model.get_cell_value(2, 2) == 48

        # Divide: 48 / 4 = 12
        viewport.paste_special({"what": "all", "op": "div"})
        assert viewport.model.get_cell_value(2, 2) in (12, 12.0)

        # Division by zero: Copy 0, divide into 12 -> #DIV/0!
        viewport.model.set_cell(0, 1, CellData(value=0))
        viewport.selection.select_cell(0, 1)
        viewport.copy()

        viewport.selection.select_cell(2, 2)
        viewport.paste_special({"what": "all", "op": "div"})
        assert viewport.model.get_cell_value(2, 2) == "#DIV/0!"

    def test_destination_selection_tiling(self, viewport: GridViewport) -> None:
        # Source factor: 1x1 cell with value 10
        viewport.model.set_cell(0, 0, CellData(value=10))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Target selection: 3x2 range B2:C4 (rows 1..3, cols 1..2)
        for r in range(1, 4):
            for c in range(1, 3):
                viewport.model.set_cell(r, c, CellData(value=r + c))

        viewport.selection.select_cell(1, 1)
        viewport.selection.extend_to(3, 2)

        # Paste Special Multiply tiles 10 across all 6 cells
        viewport.paste_special({"what": "all", "op": "mul"})

        for r in range(1, 4):
            for c in range(1, 3):
                expected = (r + c) * 10
                assert viewport.model.get_cell_value(r, c) == expected

    def test_transpose_dimensions_merges_and_comments(
        self, viewport: GridViewport
    ) -> None:
        # Create 2x3 block:
        # A1: 10, B1: 20, C1: 30
        # A2: 40, B2: 50, C2: 60
        # With merge on A1:B1 (rows 0..0, cols 0..1)
        # With comment on C1 (0, 2)
        for r in range(2):
            for c in range(3):
                viewport.model.set_cell(r, c, CellData(value=(r + 1) * 10 + c))

        viewport.model.merges.append(SelectionRange(0, 0, 0, 1))
        viewport.model.set_comment(0, 2, text="Test Comment", author="Tester")

        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(1, 2)
        viewport.copy()

        # Transpose paste to row 5, col 5 -> becomes 3x2 block
        viewport.selection.select_cell(5, 5)
        viewport.paste_special({"what": "all", "op": "none", "transpose": True})

        # Values should be transposed:
        assert viewport.model.get_cell_value(5, 5) == 10
        assert viewport.model.get_cell_value(6, 5) == 11
        assert viewport.model.get_cell_value(7, 5) == 12
        assert viewport.model.get_cell_value(5, 6) == 20
        assert viewport.model.get_cell_value(6, 6) == 21
        assert viewport.model.get_cell_value(7, 6) == 22

        # Transposed merge: (0, 0, 0, 1) [1x2] transposed becomes [2x1] at (5, 5) to (6, 5)
        found_merge = any(
            (m.min_r == 5 and m.min_c == 5 and m.max_r == 6 and m.max_c == 5)
            for m in viewport.model.merges
        )
        assert found_merge is True

        # Transposed comment: originally at (0, 2), transposed offset (2, 0) -> (7, 5)
        cm = viewport.model.get_comment(7, 5)
        assert cm is not None
        assert cm.text == "Test Comment"

    def test_skip_blanks(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value="KeepMe"))
        viewport.model.set_cell(0, 1, CellData(value=None))

        viewport.selection.select_cell(0, 0)
        viewport.selection.extend_to(0, 1)
        viewport.copy()

        # Destination has existing data in both cells
        viewport.model.set_cell(3, 0, CellData(value="OldA"))
        viewport.model.set_cell(3, 1, CellData(value="OldB"))

        viewport.selection.select_cell(3, 0)
        viewport.paste_special({"what": "all", "skip_blanks": True})

        assert viewport.model.get_cell_value(3, 0) == "KeepMe"
        assert viewport.model.get_cell_value(3, 1) == "OldB"

    def test_no_borders_preserves_target_border(
        self, viewport: GridViewport
    ) -> None:
        # Source has bold text and thick top border
        src = CellData(value="SourceText", bold=True, border_top={"style": "thick"})
        viewport.model.set_cell(0, 0, src)
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Target has thin bottom border
        target = CellData(value="TargetText", border_bottom={"style": "thin"})
        viewport.model.set_cell(4, 4, target)
        viewport.selection.select_cell(4, 4)

        viewport.paste_special({"what": "noBorders"})

        res = viewport.model.get_cell(4, 4)
        assert res.value == "SourceText"
        assert res.bold is True
        # Top border from source should not be copied
        assert res.border_top is None
        # Bottom border from target should be preserved
        assert res.border_bottom == {"style": "thin"}

    def test_column_widths_paste(self, viewport: GridViewport) -> None:
        viewport.geometry_mapper.set_col_width(0, 180)
        viewport.model.set_cell(0, 0, CellData(value="Header"))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        viewport.selection.select_cell(0, 5)
        viewport.paste_special({"what": "colWidths"})

        assert viewport.geometry_mapper.col_width(5) == 180
        # Value should not be copied
        assert viewport.model.get_cell(0, 5) is None

    def test_formulas_and_values_number_formats(
        self, viewport: GridViewport
    ) -> None:
        cell = CellData(value=123.456, formula="=100+23.456", format_code="$#,##0.00")
        viewport.model.set_cell(0, 0, cell)
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Formulas and number formats (formulasNF)
        viewport.selection.select_cell(1, 1)
        viewport.paste_special({"what": "formulasNF"})
        c1 = viewport.model.get_cell(1, 1)
        assert c1.formula == "=100+23.456"
        assert c1.format_code == "$#,##0.00"

        # Values and number formats (valuesNF)
        viewport.selection.select_cell(2, 2)
        viewport.paste_special({"what": "valuesNF"})
        c2 = viewport.model.get_cell(2, 2)
        assert c2.value == 123.456
        assert c2.formula is None
        assert c2.format_code == "$#,##0.00"

    def test_protected_sheet_blocks_paste(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value=100))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        # Lock worksheet
        viewport.model.protected = True

        viewport.selection.select_cell(1, 1)
        viewport.paste_special({"what": "all"})

        # Target cell must NOT have been created or modified
        assert viewport.model.get_cell(1, 1) is None

    def test_undo_redo_paste_special(self, viewport: GridViewport) -> None:
        viewport.model.set_cell(0, 0, CellData(value=50))
        viewport.selection.select_cell(0, 0)
        viewport.copy()

        viewport.model.set_cell(1, 1, CellData(value=20))
        viewport.selection.select_cell(1, 1)

        viewport.paste_special({"what": "all", "op": "add"})
        assert viewport.model.get_cell_value(1, 1) == 70

        # Undo
        viewport.undo()
        assert viewport.model.get_cell_value(1, 1) == 20

        # Redo
        viewport.redo()
        assert viewport.model.get_cell_value(1, 1) == 70

    def test_shortcut_ctrl_alt_v(self, viewport: GridViewport) -> None:
        # Verify Ctrl+Alt+V key event handler invokes paste_special
        called = False

        def mock_paste_special() -> None:
            nonlocal called
            called = True

        viewport.paste_special = mock_paste_special  # type: ignore[assignment]

        event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_V,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier,
        )
        viewport.keyPressEvent(event)
        assert called is True
