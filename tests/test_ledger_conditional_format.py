"""Tests for Issue #380 (TASK-DOC-L07): icon-set conditional formatting and
formula-based rules evaluated relative to the range origin."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.conditional_format import (
    CFVO,
    CFRule,
    ConditionalFormat,
    IconSetRule,
    evaluate_cf_for_cell,
)
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

XLSX_CORPUS = Path("tests/docs/excel/xlsx")


def _sheet(values: dict[tuple[int, int], object]) -> SheetDataModel:
    sh = SheetDataModel("Sheet1")
    for (r, c), v in values.items():
        sh.set_cell_value(r, c, v)
    return sh


def _cf(sqref_ranges: list[tuple[int, int, int, int]], rule: CFRule) -> ConditionalFormat:
    return ConditionalFormat(sqref="", ranges=sqref_ranges, rules=[rule])


# ------------------------------------------------------------- origin fixes


def test_origin_fixture_no_cell_matches() -> None:
    wb = read_xlsx(XLSX_CORPUS / "libreoffice__conditional_fmt_origin.xlsx")
    sh = wb.sheets[0]
    assert sh.conditional_formats, "fixture rule must be read"
    for r1, c1, r2, c2 in [(2, 1, 5, 2), (0, 5, 1, 6)]:  # B3:C6, F1:G2
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                res = evaluate_cf_for_cell(sh, r, c)
                assert res is None or res.bg_color is None, (r, c)


def test_contains_text_formula_shifts_from_anchor() -> None:
    # Rule on B3:B4 written for B3, referring to B1 -> B3 checks B1, B4 checks B2.
    sh = _sheet({(0, 1): "xBACx", (2, 1): "nothing", (3, 1): "BAC"})
    rule = CFRule(
        type="containsText",
        operator="containsText",
        text="BAC",
        formula=['NOT(ISERROR(SEARCH("BAC",B1)))'],
        bg_color="#00FF00",
    )
    sh.add_conditional_format(_cf([(2, 1, 3, 1)], rule))
    assert evaluate_cf_for_cell(sh, 2, 1).bg_color == "#00FF00"
    assert evaluate_cf_for_cell(sh, 3, 1) is None


def test_reference_shifted_off_sheet_never_matches() -> None:
    # Anchor A3, formula refers to A1: cell A1 would refer to row -1 -> #REF!.
    sh = _sheet({(0, 0): "BAC", (1, 0): "BAC", (2, 0): "BAC"})
    rule = CFRule(
        type="containsText",
        text="BAC",
        formula=['NOT(ISERROR(SEARCH("BAC",A1)))'],
        bg_color="#00FF00",
    )
    sh.add_conditional_format(_cf([(2, 0, 2, 0), (0, 0, 1, 0)], rule))
    assert evaluate_cf_for_cell(sh, 2, 0).bg_color == "#00FF00"
    assert evaluate_cf_for_cell(sh, 0, 0) is None


def test_expression_rule_mixed_references() -> None:
    sh = _sheet({(0, 0): 10, (1, 0): 1, (0, 1): "a", (1, 1): "b"})
    rule = CFRule(type="expression", formula=["$A1>5"], bg_color="#FFFF00")
    sh.add_conditional_format(_cf([(0, 0, 1, 1)], rule))
    assert evaluate_cf_for_cell(sh, 0, 1).bg_color == "#FFFF00"  # row 1: A1=10
    assert evaluate_cf_for_cell(sh, 1, 1) is None  # row 2: A2=1


def test_text_rule_without_formula_uses_text() -> None:
    sh = _sheet({(0, 0): "Hello World", (1, 0): "bye"})
    rule = CFRule(type="beginsWith", text="hello", bg_color="#123456")
    sh.add_conditional_format(_cf([(0, 0, 1, 0)], rule))
    assert evaluate_cf_for_cell(sh, 0, 0).bg_color == "#123456"
    assert evaluate_cf_for_cell(sh, 1, 0) is None


def test_text_rule_unparsable_formula_falls_back_to_text() -> None:
    sh = _sheet({(0, 0): "abc"})
    rule = CFRule(type="containsText", text="b", formula=["((("], bg_color="#111111")
    sh.add_conditional_format(_cf([(0, 0, 0, 0)], rule))
    assert evaluate_cf_for_cell(sh, 0, 0).bg_color == "#111111"


def test_cell_is_string_literal_and_absolute_reference() -> None:
    sh = _sheet({(0, 0): "abc", (1, 0): 7, (0, 3): 5})
    eq = CFRule(type="cellIs", operator="equal", formula=['"ABC"'], bg_color="#AA0000")
    gt = CFRule(type="cellIs", operator="greaterThan", formula=["$D$1"], bg_color="#00AA00")
    sh.add_conditional_format(_cf([(0, 0, 0, 0)], eq))
    sh.add_conditional_format(_cf([(1, 0, 1, 0)], gt))
    assert evaluate_cf_for_cell(sh, 0, 0).bg_color == "#AA0000"
    assert evaluate_cf_for_cell(sh, 1, 0).bg_color == "#00AA00"


def test_blank_and_error_rules() -> None:
    sh = _sheet({(0, 0): "x", (2, 0): "#DIV/0!"})
    blanks = CFRule(type="containsBlanks", bg_color="#EEEEEE")
    errs = CFRule(type="containsErrors", bg_color="#FF0000")
    sh.add_conditional_format(_cf([(0, 0, 2, 0)], blanks))
    sh.add_conditional_format(_cf([(0, 0, 2, 0)], errs))
    assert evaluate_cf_for_cell(sh, 1, 0).bg_color == "#EEEEEE"
    assert evaluate_cf_for_cell(sh, 2, 0).bg_color == "#FF0000"
    assert evaluate_cf_for_cell(sh, 0, 0) is None


# ---------------------------------------------------------------- icon sets


def _icon_rule(**kw: object) -> CFRule:
    ic = IconSetRule(
        set_name=str(kw.pop("set_name", "3TrafficLights1")),
        cfvos=[CFVO("percent", "0"), CFVO("percent", "33"), CFVO("percent", "67")],
        **kw,  # type: ignore[arg-type]
    )
    return CFRule(type="iconSet", icon_set=ic)


def _icon_sheet(rule: CFRule) -> SheetDataModel:
    sh = _sheet({(r, 0): float(r * 10) for r in range(11)})  # 0..100
    sh.add_conditional_format(_cf([(0, 0, 10, 0)], rule))
    return sh


def test_icon_set_bands() -> None:
    sh = _icon_sheet(_icon_rule())
    assert evaluate_cf_for_cell(sh, 0, 0).icon == {
        "set": "3TrafficLights1",
        "i": 0,
        "n": 3,
        "show_value": True,
    }
    assert evaluate_cf_for_cell(sh, 5, 0).icon["i"] == 1  # 50
    assert evaluate_cf_for_cell(sh, 10, 0).icon["i"] == 2  # 100


def test_icon_set_gte_false_is_strict() -> None:
    rule = _icon_rule()
    rule.icon_set.cfvos[2] = CFVO("num", "70", gte=False)
    sh = _icon_sheet(rule)
    assert evaluate_cf_for_cell(sh, 7, 0).icon["i"] == 1  # 70 is not > 70
    assert evaluate_cf_for_cell(sh, 8, 0).icon["i"] == 2


def test_icon_set_reverse_and_show_value() -> None:
    sh = _icon_sheet(_icon_rule(reverse=True, show_value=False))
    icon = evaluate_cf_for_cell(sh, 0, 0).icon
    assert icon["i"] == 2
    assert icon["show_value"] is False


def test_icon_set_custom_icons_and_no_icons() -> None:
    sh = _icon_sheet(_icon_rule(custom=[("NoIcons", 0), ("3Flags", 1), ("3Stars", 2)]))
    assert evaluate_cf_for_cell(sh, 0, 0) is None
    assert evaluate_cf_for_cell(sh, 5, 0).icon["set"] == "3Flags"
    assert evaluate_cf_for_cell(sh, 10, 0).icon == {
        "set": "3Stars",
        "i": 2,
        "n": 3,
        "show_value": True,
    }


def test_icon_set_formula_threshold() -> None:
    rule = _icon_rule()
    rule.icon_set.cfvos[2] = CFVO("formula", "$C$1")
    sh = _icon_sheet(rule)
    sh.set_cell_value(0, 2, 95.0)
    assert evaluate_cf_for_cell(sh, 9, 0).icon["i"] == 1  # 90 < 95
    assert evaluate_cf_for_cell(sh, 10, 0).icon["i"] == 2


def test_icon_set_ignores_text_cells() -> None:
    sh = _icon_sheet(_icon_rule())
    sh.set_cell_value(3, 0, "n/a")
    assert evaluate_cf_for_cell(sh, 3, 0) is None


def test_no_ext_data_fixture_d2_reports_icon() -> None:
    wb = read_xlsx(XLSX_CORPUS / "openxml-sdk__NoExtDataB1.xlsx")
    sh = wb.sheets[0]
    res = evaluate_cf_for_cell(sh, 1, 3)  # D2 = 4.9, smallest value in D
    assert res is not None and res.icon is not None
    assert res.icon["set"] == "3TrafficLights1"
    assert res.icon["i"] == 0  # red circle


# ----------------------------------------------------------- round trip


def _sheet_xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        return z.read("xl/worksheets/sheet1.xml").decode("utf-8")


def test_icon_set_round_trip_main_namespace() -> None:
    wb = read_xlsx(XLSX_CORPUS / "openxml-sdk__NoExtDataB1.xlsx")
    data = write_xlsx(wb)
    assert '<cfRule type="iconSet"' in _sheet_xml(data)
    wb2 = read_xlsx(data)
    icon_rules = [
        rule for cf in wb2.sheets[0].conditional_formats for rule in cf.rules if rule.icon_set
    ]
    assert icon_rules
    assert len(icon_rules[0].icon_set.cfvos) == 3
    assert icon_rules[0].icon_set.cfvos[1].type == "percentile"
    assert str(icon_rules[0].icon_set.cfvos[1].val) == "33"


def test_icon_set_round_trip_x14_extension() -> None:
    wb = WorkbookModel()
    sh = wb.sheets[0]
    for r in range(5):
        sh.set_cell_value(r, 0, float(r))
    rule = _icon_rule(set_name="3Stars", reverse=True, custom=[("NoIcons", 0), ("3Flags", 1)])
    rule.priority = 3
    sh.add_conditional_format(ConditionalFormat(sqref="A1:A5", ranges=[(0, 0, 4, 0)], rules=[rule]))
    data = write_xlsx(wb)
    xml = _sheet_xml(data)
    assert "<conditionalFormatting " not in xml  # x14-only rule kept out of the main namespace
    assert '<x14:cfRule type="iconSet"' in xml
    assert xml.index("<extLst>") > xml.index("<pageMargins")

    wb2 = read_xlsx(data)
    rules = [rule for cf in wb2.sheets[0].conditional_formats for rule in cf.rules]
    assert len(rules) == 1
    ic = rules[0].icon_set
    assert ic.set_name == "3Stars" and ic.reverse and ic.x14
    assert ic.custom == [("NoIcons", 0), ("3Flags", 1)]
    assert [str(v.val) for v in ic.cfvos] == ["0", "33", "67"]
    assert rules[0].priority == 3


# ------------------------------------------------------------- painting


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_draw_icon_paints_left_edge(qapp) -> None:
    from PySide6.QtGui import QColor, QImage, QPainter

    from atboffice.modules.spreadsheet.views.cf_icons import ICON_SETS, draw_icon

    for set_name, icons in ICON_SETS.items():
        for i in range(len(icons)):
            img = QImage(20, 20, QImage.Format.Format_ARGB32)
            img.fill(QColor("white"))
            p = QPainter(img)
            draw_icon(p, set_name, i, 2, 2, 16)
            p.end()
            painted = any(
                img.pixelColor(x, y) != QColor("white") for x in range(20) for y in range(20)
            )
            assert painted, (set_name, i)

    img = QImage(20, 20, QImage.Format.Format_ARGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    draw_icon(p, "3TrafficLights1", 0, 2, 2, 16)
    p.end()
    assert img.pixelColor(10, 10) == QColor("#C00000")
    assert img.pixelColor(19, 10) == QColor("white")


def test_grid_viewport_paints_icon_at_cell_left_edge(qtbot) -> None:

    from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport

    sh = _icon_sheet(_icon_rule(show_value=False))
    viewport = GridViewport(model=sh)
    qtbot.addWidget(viewport)
    viewport.resize(300, 300)
    img = viewport.grab().toImage()
    x0 = viewport.row_header_width
    y0 = viewport.col_header_height
    row_h = sh.geometry.row_size(0)
    reds = [
        (x, y)
        for x in range(x0, x0 + 20)
        for y in range(y0, y0 + row_h)
        if img.pixelColor(x, y).red() > 150
        and img.pixelColor(x, y).green() < 60
        and img.pixelColor(x, y).blue() < 60
    ]
    assert reds, "red traffic light expected at the left edge of A1"


def test_cell_is_unquoted_text_from_dialog_still_matches() -> None:
    sh = _sheet({(0, 0): "Done"})
    rule = CFRule(type="cellIs", operator="equal", formula=["done"], bg_color="#00AA00")
    sh.add_conditional_format(_cf([(0, 0, 0, 0)], rule))
    assert evaluate_cf_for_cell(sh, 0, 0).bg_color == "#00AA00"
