"""Unit tests for AutoFilter and multi-column Sort logic."""

import pytest

from atboffice.modules.spreadsheet.models.filter_model import (
    AutoFilter,
    ColumnFilter,
    apply_auto_filter,
    clear_auto_filter,
    excel_sort_key,
    sort_sheet_range,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


class TestExcelSortLogic:
    """Test Excel-compliant sort key and comparator."""

    def test_sort_type_hierarchy(self) -> None:
        """Numbers < Strings < Booleans < Errors < Blanks."""
        items = ["apple", 100, None, True, 25, "#VALUE!", False, "", "banana"]
        sorted_asc = sorted(items, key=lambda x: excel_sort_key(x, desc=False))
        # Expected types order:
        # Numbers: 25, 100
        # Strings: 'apple', 'banana'
        # Booleans: False, True
        # Errors: '#VALUE!'
        # Blanks: None, '' (at the very end)
        assert sorted_asc[0] == 25
        assert sorted_asc[1] == 100
        assert sorted_asc[2] == "apple"
        assert sorted_asc[3] == "banana"
        assert sorted_asc[4] is False
        assert sorted_asc[5] is True
        assert sorted_asc[6] == "#VALUE!"
        assert sorted_asc[7] is None or sorted_asc[7] == ""
        assert sorted_asc[8] is None or sorted_asc[8] == ""

    def test_blanks_always_last_in_descending(self) -> None:
        """Blanks must remain at the bottom even in descending sort."""
        items = [10, None, 30, "", 20]
        sorted_desc = sorted(items, key=lambda x: excel_sort_key(x, desc=True))
        assert sorted_desc[:3] == [30, 20, 10]
        assert sorted_desc[3] is None or sorted_desc[3] == ""
        assert sorted_desc[4] is None or sorted_desc[4] == ""


class TestSheetRangeSort:
    """Test multi-column sorting on SheetDataModel."""

    @pytest.fixture
    def sample_model(self) -> SheetDataModel:
        model = SheetDataModel()
        # Row 0: Header: Name, Department, Salary
        model.set_cell_value(0, 0, "Name")
        model.set_cell_value(0, 1, "Department")
        model.set_cell_value(0, 2, "Salary")

        # Row 1: Alice, HR, 5000
        model.set_cell_value(1, 0, "Alice")
        model.set_cell_value(1, 1, "HR")
        model.set_cell_value(1, 2, 5000)

        # Row 2: Bob, IT, 8000
        model.set_cell_value(2, 0, "Bob")
        model.set_cell_value(2, 1, "IT")
        model.set_cell_value(2, 2, 8000)

        # Row 3: Charlie, IT, 6000
        model.set_cell_value(3, 0, "Charlie")
        model.set_cell_value(3, 1, "IT")
        model.set_cell_value(3, 2, 6000)

        # Row 4: David, HR, 7000
        model.set_cell_value(4, 0, "David")
        model.set_cell_value(4, 1, "HR")
        model.set_cell_value(4, 2, 7000)

        return model

    def test_sort_single_key_with_header(self, sample_model: SheetDataModel) -> None:
        # Sort by Salary descending (col 2, desc=True)
        sort_sheet_range(
            sample_model,
            r1=0,
            c1=0,
            r2=4,
            c2=2,
            keys=[(2, True)],
            has_header=True,
        )

        # Header remains intact
        assert sample_model.get_cell_value(0, 0) == "Name"
        # Salaries should be 8000, 7000, 6000, 5000
        assert sample_model.get_cell_value(1, 2) == 8000
        assert sample_model.get_cell_value(1, 0) == "Bob"
        assert sample_model.get_cell_value(2, 2) == 7000
        assert sample_model.get_cell_value(2, 0) == "David"
        assert sample_model.get_cell_value(3, 2) == 6000
        assert sample_model.get_cell_value(3, 0) == "Charlie"
        assert sample_model.get_cell_value(4, 2) == 5000
        assert sample_model.get_cell_value(4, 0) == "Alice"

    def test_multi_key_sort(self, sample_model: SheetDataModel) -> None:
        # Sort by Department ascending (col 1), then Salary descending (col 2)
        sort_sheet_range(
            sample_model,
            r1=0,
            c1=0,
            r2=4,
            c2=2,
            keys=[(1, False), (2, True)],
            has_header=True,
        )

        # Department HR (David: 7000, Alice: 5000), then IT (Bob: 8000, Charlie: 6000)
        assert sample_model.get_cell_value(1, 0) == "David"
        assert sample_model.get_cell_value(2, 0) == "Alice"
        assert sample_model.get_cell_value(3, 0) == "Bob"
        assert sample_model.get_cell_value(4, 0) == "Charlie"


class TestAutoFilterLogic:
    """Test AutoFilter criteria and row hiding."""

    @pytest.fixture
    def filter_model(self) -> SheetDataModel:
        model = SheetDataModel()
        # Row 0: Fruit, Quantity, Price
        model.set_cell_value(0, 0, "Fruit")
        model.set_cell_value(0, 1, "Quantity")
        model.set_cell_value(0, 2, "Price")

        # Row 1: Apple, 10, 2.5
        model.set_cell_value(1, 0, "Apple")
        model.set_cell_value(1, 1, 10)
        model.set_cell_value(1, 2, 2.5)

        # Row 2: Banana, 20, 1.2
        model.set_cell_value(2, 0, "Banana")
        model.set_cell_value(2, 1, 20)
        model.set_cell_value(2, 2, 1.2)

        # Row 3: Orange, 5, 3.0
        model.set_cell_value(3, 0, "Orange")
        model.set_cell_value(3, 1, 5)
        model.set_cell_value(3, 2, 3.0)

        # Row 4: Apple, 15, 2.8
        model.set_cell_value(4, 0, "Apple")
        model.set_cell_value(4, 1, 15)
        model.set_cell_value(4, 2, 2.8)

        # Row 5: Empty fruit, 0, 0
        model.set_cell_value(5, 0, None)
        model.set_cell_value(5, 1, 0)
        model.set_cell_value(5, 2, 0.0)

        return model

    def test_filter_values(self, filter_model: SheetDataModel) -> None:
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        # Filter Fruit == Apple
        af.cols[0] = ColumnFilter(values={"Apple"})
        apply_auto_filter(filter_model, af)

        # Visible: Row 1, Row 4 (and header Row 0)
        # Hidden: Row 2, Row 3, Row 5
        assert 1 not in filter_model.geometry.hidden_rows
        assert 4 not in filter_model.geometry.hidden_rows
        assert 2 in filter_model.geometry.hidden_rows
        assert 3 in filter_model.geometry.hidden_rows
        assert 5 in filter_model.geometry.hidden_rows

    def test_filter_blanks(self, filter_model: SheetDataModel) -> None:
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        # Filter blanks on col 0
        af.cols[0] = ColumnFilter(blank=True)
        apply_auto_filter(filter_model, af)

        # Only Row 5 is blank
        assert 5 not in filter_model.geometry.hidden_rows
        assert 1 in filter_model.geometry.hidden_rows
        assert 2 in filter_model.geometry.hidden_rows

    def test_filter_top10(self, filter_model: SheetDataModel) -> None:
        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        # Top 2 by Quantity (col 1)
        af.cols[1] = ColumnFilter(top10_top=True, top10_val=2, top10_percent=False)
        apply_auto_filter(filter_model, af)

        # Quantities: 10 (r1), 20 (r2), 5 (r3), 15 (r4), 0 (r5)
        # Top 2 are 20 (r2) and 15 (r4)
        assert 2 not in filter_model.geometry.hidden_rows
        assert 4 not in filter_model.geometry.hidden_rows
        assert 1 in filter_model.geometry.hidden_rows
        assert 3 in filter_model.geometry.hidden_rows
        assert 5 in filter_model.geometry.hidden_rows

    def test_clear_filter_preserves_manual_hidden_rows(self, filter_model: SheetDataModel) -> None:
        # User manually hides row 3
        filter_model.geometry.hidden_rows.add(3)

        af = AutoFilter(r1=0, c1=0, r2=5, c2=2)
        af.cols[0] = ColumnFilter(values={"Apple"})
        apply_auto_filter(filter_model, af)

        # Clear filter
        clear_auto_filter(filter_model, af)

        # Row 3 should still be hidden because it was manually hidden!
        assert 3 in filter_model.geometry.hidden_rows
        # Rows 2 and 5 should now be unhidden
        assert 2 not in filter_model.geometry.hidden_rows
        assert 5 not in filter_model.geometry.hidden_rows
