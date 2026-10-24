"""Unit tests for spreadsheet cell and range reference arithmetic."""


from atboffice.modules.spreadsheet.calc.references import (
    MAXC,
    MAXR,
    abs_range_name,
    adjust,
    adjust_move,
    cell_name,
    col_index,
    col_name,
    parse_cell,
    parse_range,
    quote_sheet,
    range_name,
    rename_sheet,
    shift,
    toggle_abs,
)
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    BinaryOpNode,
    CellRefNode,
    RefErrNode,
)


def test_col_conversion():
    assert col_name(0) == "A"
    assert col_name(25) == "Z"
    assert col_name(26) == "AA"
    assert col_name(MAXC - 1) == "XFD"

    assert col_index("A") == 0
    assert col_index("Z") == 25
    assert col_index("AA") == 26
    assert col_index("XFD") == MAXC - 1
    assert col_index("xfd") == MAXC - 1


def test_cell_name_and_parse():
    assert cell_name(0, 0) == "A1"
    assert cell_name(2, 1, ra=True, ca=True) == "$B$3"
    assert cell_name(2, 1, ra=True, ca=False) == "B$3"
    assert cell_name(2, 1, ra=False, ca=True) == "$B3"

    res = parse_cell("B3")
    assert res == {"r": 2, "c": 1, "ra": False, "ca": False}

    res_abs = parse_cell("$XFD$1048576")
    assert res_abs == {"r": MAXR - 1, "c": MAXC - 1, "ra": True, "ca": True}

    assert parse_cell("INVALID") is None
    assert parse_cell("A0") is None
    assert parse_cell("A1048577") is None


def test_range_name_and_parse():
    rg = parse_range("A1:B5")
    assert rg == {"r1": 0, "c1": 0, "r2": 4, "c2": 1}
    assert range_name(rg) == "A1:B5"

    col_rg = parse_range("A:B")
    assert col_rg == {"r1": 0, "c1": 0, "r2": MAXR - 1, "c2": 1}
    assert range_name(col_rg) == "A:B"

    row_rg = parse_range("3:5")
    assert row_rg == {"r1": 2, "c1": 0, "r2": 4, "c2": MAXC - 1}
    assert range_name(row_rg) == "3:5"

    single_rg = {"r1": 2, "c1": 1, "r2": 2, "c2": 1}
    assert range_name(single_rg) == "B3"
    assert abs_range_name(single_rg) == "$B$3"


def test_quote_sheet():
    assert quote_sheet("Sheet1") == "Sheet1"
    assert quote_sheet("Sheet 1") == "'Sheet 1'"
    assert quote_sheet("It's Sheet") == "'It''s Sheet'"
    assert quote_sheet("A1") == "'A1'"  # cell conflict must be quoted
    assert quote_sheet("TRUE") == "'TRUE'"


def test_shift_and_translate():
    ast = BinaryOpNode(
        op="+",
        left=CellRefNode(r=0, c=0, ra=False, ca=False),  # A1
        right=CellRefNode(r=0, c=1, ra=True, ca=True),  # $B$1
    )
    shifted = shift(ast, dr=2, dc=3)
    assert isinstance(shifted, BinaryOpNode)
    assert isinstance(shifted.left, CellRefNode)
    assert shifted.left.r == 2
    assert shifted.left.c == 3
    # Absolute reference right should not shift
    assert isinstance(shifted.right, CellRefNode)
    assert shifted.right.r == 0
    assert shifted.right.c == 1

    # Out of bounds turns into RefErrNode
    shifted_oob = shift(ast, dr=-1, dc=0)
    assert isinstance(shifted_oob, BinaryOpNode)
    assert isinstance(shifted_oob.left, RefErrNode)

    # Area shifting
    area = AreaRefNode(r1=0, c1=0, r2=2, c2=2, ra1=False, ca1=False, ra2=False, ca2=False)
    shifted_area = shift(area, dr=1, dc=1)
    assert isinstance(shifted_area, AreaRefNode)
    assert shifted_area.r1 == 1 and shifted_area.c1 == 1
    assert shifted_area.r2 == 3 and shifted_area.c2 == 3


def test_adjust_row_col_insert_delete():
    # Insertion of row 1 (op.at=1, op.n=2, op.axis='r')
    node = CellRefNode(r=2, c=1)  # B3
    op_ins = {"sheet": "Sheet1", "axis": "r", "at": 1, "n": 2}
    out, changed = adjust(node, op_ins, home="Sheet1")
    assert changed is True
    assert isinstance(out, CellRefNode)
    assert out.r == 4  # row 3 shifted down by 2 -> row 5 (0-indexed 4)

    # Deletion of row containing the reference
    op_del = {"sheet": "Sheet1", "axis": "r", "at": 2, "n": -1}
    out_del, changed_del = adjust(node, op_del, home="Sheet1")
    assert changed_del is True
    assert isinstance(out_del, RefErrNode)


def test_adjust_move_and_rename_sheet():
    node = CellRefNode(r=1, c=1, sheet="Sheet1")
    src = {"sheet": "Sheet1", "r1": 0, "c1": 0, "r2": 2, "c2": 2}
    out_mv, ch_mv = adjust_move(node, src, dr=5, dc=5, home="Sheet1", to_sheet="Sheet2")
    assert ch_mv is True
    assert isinstance(out_mv, CellRefNode)
    assert out_mv.r == 6 and out_mv.c == 6
    assert out_mv.sheet == "Sheet2"

    # Rename sheet
    out_rn, ch_rn = rename_sheet(out_mv, "Sheet2", "Summary")
    assert ch_rn is True
    assert out_rn.sheet == "Summary"


def test_toggle_abs():
    # Excel cycle: A1 → $A$1 → A$1 → $A1 → A1
    t1 = toggle_abs("A1", 0, 2)
    assert t1 is not None and t1["text"] == "$A$1"

    t2 = toggle_abs("$A$1", 0, 4)
    assert t2 is not None and t2["text"] == "A$1"

    t3 = toggle_abs("A$1", 0, 3)
    assert t3 is not None and t3["text"] == "$A1"

    t4 = toggle_abs("$A1", 0, 3)
    assert t4 is not None and t4["text"] == "A1"
