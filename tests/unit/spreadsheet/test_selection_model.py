"""Unit tests for spreadsheet selection model and geometry."""


from atboffice.modules.spreadsheet.models.selection_model import (
    SelectionModel,
    SelectionRange,
)
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
    SheetGeometry,
)


class TestSelectionRange:
    def test_normalization(self) -> None:
        rg = SelectionRange(5, 8, 2, 3)
        assert rg.min_r == 2
        assert rg.max_r == 5
        assert rg.min_c == 3
        assert rg.max_c == 8

    def test_contains(self) -> None:
        rg = SelectionRange(2, 2, 5, 5)
        assert rg.contains(2, 2)
        assert rg.contains(4, 3)
        assert rg.contains(5, 5)
        assert not rg.contains(1, 2)
        assert not rg.contains(2, 6)

    def test_overlaps(self) -> None:
        rg1 = SelectionRange(1, 1, 3, 3)
        rg2 = SelectionRange(2, 2, 4, 4)
        rg3 = SelectionRange(5, 5, 6, 6)
        assert rg1.overlaps(rg2)
        assert not rg1.overlaps(rg3)


class TestSelectionModel:
    def test_initial_state(self) -> None:
        sm = SelectionModel()
        assert sm.active_cell == (0, 0)
        assert sm.anchor_cell == (0, 0)
        assert len(sm.ranges) == 1
        assert sm.ranges[0] == SelectionRange(0, 0, 0, 0)

    def test_select_cell(self) -> None:
        sm = SelectionModel()
        sm.select_cell(3, 4)
        assert sm.active_cell == (3, 4)
        assert sm.anchor_cell == (3, 4)
        assert len(sm.ranges) == 1
        assert sm.ranges[0] == SelectionRange(3, 4, 3, 4)
        assert sm.is_selected(3, 4)
        assert not sm.is_selected(3, 5)

    def test_extend_to(self) -> None:
        sm = SelectionModel()
        sm.select_cell(2, 2)
        sm.extend_to(5, 7)
        assert sm.active_cell == (5, 7)
        assert sm.anchor_cell == (2, 2)
        assert len(sm.ranges) == 1
        assert sm.ranges[0] == SelectionRange(2, 2, 5, 7)
        assert sm.is_selected(3, 4)

    def test_ctrl_add_range(self) -> None:
        sm = SelectionModel()
        sm.select_cell(1, 1)
        sm.add_range(SelectionRange(5, 5, 6, 6))
        assert len(sm.ranges) == 2
        assert sm.is_selected(1, 1)
        assert sm.is_selected(5, 5)
        assert not sm.is_selected(3, 3)

    def test_select_rows_and_cols(self) -> None:
        sm = SelectionModel(max_rows=1000, max_cols=100)
        sm.select_rows(2, 4)
        assert sm.ranges[0] == SelectionRange(2, 0, 4, 99)
        assert sm.is_row_selected(3)
        assert not sm.is_row_selected(1)

        sm.select_cols(3, 5)
        assert sm.ranges[0] == SelectionRange(0, 3, 999, 5)
        assert sm.is_col_selected(4)
        assert not sm.is_col_selected(2)

    def test_select_all(self) -> None:
        sm = SelectionModel(max_rows=100, max_cols=20)
        sm.select_all()
        assert sm.ranges[0] == SelectionRange(0, 0, 99, 19)
        assert sm.is_selected(50, 10)


class TestSheetGeometry:
    def test_default_geometry(self) -> None:
        geo = SheetGeometry(default_row_height=20, default_col_width=60)
        assert geo.row_pos(0) == 0
        assert geo.row_pos(1) == 20
        assert geo.row_pos(5) == 100
        assert geo.row_size(3) == 20

        assert geo.col_pos(0) == 0
        assert geo.col_pos(1) == 60
        assert geo.col_pos(3) == 180
        assert geo.col_size(2) == 60

        assert geo.find_row_at(45) == 2  # 0-19: 0, 20-39: 1, 40-59: 2
        assert geo.find_col_at(130) == 2

    def test_custom_sizes(self) -> None:
        geo = SheetGeometry(default_row_height=20, default_col_width=60)
        geo.set_col_width(1, 100)
        assert geo.col_size(0) == 60
        assert geo.col_size(1) == 100
        assert geo.col_pos(0) == 0
        assert geo.col_pos(1) == 60
        assert geo.col_pos(2) == 160


class TestSheetDataModel:
    def test_cell_crud(self) -> None:
        model = SheetDataModel()
        assert model.is_empty(0, 0)
        model.set_cell(0, 0, CellData(value="Hello", format_code="General"))
        assert not model.is_empty(0, 0)
        cell = model.get_cell(0, 0)
        assert cell is not None
        assert cell.value == "Hello"

        # Check neighbor empty
        assert model.is_empty(0, 1)
