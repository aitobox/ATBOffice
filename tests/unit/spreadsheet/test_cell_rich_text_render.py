"""Unit tests for in-cell rich text runs layout, multi-style mixing, sub/superscript, and OOXML roundtrip."""

from __future__ import annotations

import io
import sys
import zipfile
import xml.etree.ElementTree as ET
import pytest
from PySide6.QtCore import QPointF, QRect
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QFontMetricsF,
    QImage,
    QPainter,
)

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx, _parse_rich_runs
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    RichTextRun,
    SheetDataModel,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.editor_controller import EditorController
from atboffice.modules.spreadsheet.views.grid_viewport import GridViewport


class TestRichTextModel:
    """Tests for RichTextRun dataclass and CellData integration."""

    def test_rich_text_run_defaults_and_clone(self):
        run = RichTextRun(
            text="CO2",
            font_family="Calibri",
            font_size=11.0,
            bold=True,
            italic=False,
            underline=True,
            underline_style="single",
            strike=False,
            fg_color="#FF0000",
            vert_align="subscript",
        )
        assert run.text == "CO2"
        assert run.font_family == "Calibri"
        assert run.font_size == 11.0
        assert run.bold is True
        assert run.italic is False
        assert run.underline is True
        assert run.underline_style == "single"
        assert run.fg_color == "#FF0000"
        assert run.vert_align == "subscript"

        cloned = run.clone()
        assert cloned is not run
        assert cloned.text == run.text
        assert cloned.vert_align == run.vert_align
        assert cloned.fg_color == run.fg_color

    def test_cell_data_clone_deep_copies_rich_runs(self):
        runs = [
            RichTextRun(text="H", bold=True),
            RichTextRun(text="2", vert_align="subscript"),
            RichTextRun(text="O", bold=True),
        ]
        cell = CellData(value="H2O", rich_runs=runs)
        assert cell.rich_runs is not None
        assert len(cell.rich_runs) == 3

        cloned_cell = cell.clone()
        assert cloned_cell is not cell
        assert cloned_cell.rich_runs is not None
        assert len(cloned_cell.rich_runs) == 3
        assert cloned_cell.rich_runs is not cell.rich_runs
        assert cloned_cell.rich_runs[1] is not cell.rich_runs[1]
        assert cloned_cell.rich_runs[1].vert_align == "subscript"


class TestRichTextRenderingAndLayout:
    """Tests for GridViewport rich text layout, QFontMetricsF measurement, sub/superscript, and auto-fit."""

    def test_measure_rich_runs_width(self, qapp):
        viewport = GridViewport()
        cell = CellData(
            value="H2O",
            font_family="Arial",
            font_size=10,
            rich_runs=[
                RichTextRun(text="H", font_size=10),
                RichTextRun(text="2", font_size=10, vert_align="subscript"),
                RichTextRun(text="O", font_size=10),
            ],
        )

        width = viewport._measure_rich_runs_width(cell)
        assert width > 0.0

        # Subscript '2' is rendered at 70% font size (7pt instead of 10pt)
        fm_normal = QFontMetricsF(QFont("Arial", 10))
        fm_sub = QFontMetricsF(QFont("Arial", 7))
        expected_w = (
            fm_normal.horizontalAdvance("H")
            + fm_sub.horizontalAdvance("2")
            + fm_normal.horizontalAdvance("O")
        )
        assert abs(width - expected_w) < 1.0

    def test_subscript_and_superscript_scaling_and_offsets(self, qapp):
        viewport = GridViewport()
        img = QImage(300, 100, QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        painter = QPainter(img)

        # Chemical formula with subscript: H2O
        cell_chem = CellData(
            value="H2O",
            rich_runs=[
                RichTextRun(text="H"),
                RichTextRun(text="2", vert_align="subscript"),
                RichTextRun(text="O"),
            ],
        )
        viewport._paint_rich_cell(
            painter,
            cell_chem,
            col_x=10,
            row_y=10,
            span_w=100,
            row_h=30,
            eff_h="left",
            eff_v="center",
        )

        # Math formula with superscript: E=mc2
        cell_math = CellData(
            value="E=mc2",
            rich_runs=[
                RichTextRun(text="E=mc"),
                RichTextRun(text="2", vert_align="superscript"),
            ],
        )
        viewport._paint_rich_cell(
            painter,
            cell_math,
            col_x=120,
            row_y=10,
            span_w=100,
            row_h=30,
            eff_h="left",
            eff_v="center",
        )
        painter.end()

        # Image was successfully painted without crashing
        assert not img.isNull()

    def test_multistyle_runs_mixing_colors_and_fonts(self, qapp):
        viewport = GridViewport()
        img = QImage(400, 100, QImage.Format.Format_ARGB32)
        painter = QPainter(img)

        cell = CellData(
            value="RedBold GreenItalic BlueUnder",
            rich_runs=[
                RichTextRun(text="RedBold ", bold=True, fg_color="#FF0000"),
                RichTextRun(text="GreenItalic ", italic=True, fg_color="#008000"),
                RichTextRun(text="BlueUnder", underline=True, fg_color="#0000FF"),
            ],
        )

        # Test horizontal alignments
        for align_h in ("left", "center", "right"):
            viewport._paint_rich_cell(
                painter,
                cell,
                col_x=10,
                row_y=10,
                span_w=350,
                row_h=40,
                eff_h=align_h,
                eff_v="center",
            )

        # Test vertical alignments
        for align_v in ("top", "center", "bottom"):
            viewport._paint_rich_cell(
                painter,
                cell,
                col_x=10,
                row_y=10,
                span_w=350,
                row_h=50,
                eff_h="left",
                eff_v=align_v,
            )

        painter.end()
        assert not img.isNull()

    def test_word_wrapping_and_explicit_newlines(self, qapp):
        viewport = GridViewport()
        img = QImage(200, 200, QImage.Format.Format_ARGB32)
        painter = QPainter(img)

        # Explicit newline
        cell_nl = CellData(
            value="Line1\nLine2",
            rich_runs=[
                RichTextRun(text="Line1\n", bold=True),
                RichTextRun(text="Line2", italic=True),
            ],
        )
        viewport._paint_rich_cell(
            painter,
            cell_nl,
            col_x=0,
            row_y=0,
            span_w=150,
            row_h=60,
            eff_h="left",
            eff_v="top",
        )

        # Word wrap
        cell_wrap = CellData(
            value="This is a very long text that must wrap to next lines",
            wrap_text=True,
            rich_runs=[
                RichTextRun(text="This is a very ", bold=True),
                RichTextRun(text="long text that ", fg_color="#0000FF"),
                RichTextRun(text="must wrap to next lines", italic=True),
            ],
        )
        viewport._paint_rich_cell(
            painter,
            cell_wrap,
            col_x=0,
            row_y=70,
            span_w=80,
            row_h=80,
            eff_h="left",
            eff_v="top",
        )

        painter.end()
        assert not img.isNull()

    def test_auto_fit_column_with_rich_text(self, qapp):
        model = SheetDataModel()
        viewport = GridViewport(model=model)

        runs = [
            RichTextRun(text="Very Long Header ", bold=True, font_size=14),
            RichTextRun(text="Subtext", italic=True, font_size=10),
        ]
        model.set_cell(0, 2, CellData(value="Very Long Header Subtext", rich_runs=runs))

        # Initial col width is standard 64px
        assert viewport.geometry_mapper.col_size(2) == 64

        viewport.auto_fit_column(2)
        fitted_w = viewport.geometry_mapper.col_size(2)
        assert fitted_w > 100


class TestInplaceEditingPreservation:
    """Tests that in-place editing preserves rich runs on commit when text is unchanged."""

    def test_inplace_editing_preserves_rich_runs_when_unchanged(self, qapp):
        from atboffice.modules.spreadsheet.models.selection_model import SelectionModel

        model = SheetDataModel()
        selection = SelectionModel()
        viewport = GridViewport(model=model, selection=selection)
        controller = EditorController(
            viewport=viewport,
            model=model,
            selection=selection,
        )
        viewport.editor_controller = controller

        runs = [
            RichTextRun(text="H"),
            RichTextRun(text="2", vert_align="subscript"),
            RichTextRun(text="O"),
        ]
        cell = CellData(value="H2O", rich_runs=runs)
        model.set_cell(0, 0, cell)

        controller.begin_edit(0, 0)
        assert controller.in_cell_editor.text() == "H2O"

        # Commit unchanged
        ok = controller.commit()
        assert ok is True

        committed_cell = model.get_cell(0, 0)
        assert committed_cell is not None
        assert committed_cell.value == "H2O"
        assert committed_cell.rich_runs is not None
        assert len(committed_cell.rich_runs) == 3
        assert committed_cell.rich_runs[1].vert_align == "subscript"

    def test_inplace_editing_resets_rich_runs_when_text_changed(self, qapp):
        from atboffice.modules.spreadsheet.models.selection_model import SelectionModel

        model = SheetDataModel()
        selection = SelectionModel()
        viewport = GridViewport(model=model, selection=selection)
        controller = EditorController(
            viewport=viewport,
            model=model,
            selection=selection,
        )
        viewport.editor_controller = controller

        runs = [
            RichTextRun(text="H"),
            RichTextRun(text="2", vert_align="subscript"),
            RichTextRun(text="O"),
        ]
        cell = CellData(value="H2O", rich_runs=runs)
        model.set_cell(0, 0, cell)

        controller.begin_edit(0, 0)
        controller.in_cell_editor.setText("Different Text")
        ok = controller.commit()
        assert ok is True

        committed_cell = model.get_cell(0, 0)
        assert committed_cell is not None
        assert committed_cell.value == "Different Text"
        assert committed_cell.rich_runs is None


class TestOOXMLRoundtripRichText:
    """Tests saving and reading rich text runs to/from XLSX."""

    def test_roundtrip_xlsx_rich_text_runs(self):
        wb = WorkbookModel()
        sheet = wb.active_sheet
        sheet.name = "RichData"

        # Cell A1: Chemical formula with subscript H2O
        r_chem = [
            RichTextRun(text="H", font_family="Calibri", font_size=11),
            RichTextRun(text="2", font_family="Calibri", font_size=11, vert_align="subscript"),
            RichTextRun(text="O", font_family="Calibri", font_size=11),
        ]
        sheet.set_cell(0, 0, CellData(value="H2O", rich_runs=r_chem))

        # Cell A2: Math formula with superscript E = mc2
        r_math = [
            RichTextRun(text="E = mc", font_family="Calibri", font_size=12, italic=True),
            RichTextRun(text="2", font_family="Calibri", font_size=12, vert_align="superscript"),
        ]
        sheet.set_cell(1, 0, CellData(value="E = mc2", rich_runs=r_math))

        # Cell A3: Multi-color and multi-style runs
        r_styles = [
            RichTextRun(text="Red Bold ", bold=True, fg_color="#FF0000"),
            RichTextRun(text="Blue Underline", underline=True, underline_style="single", fg_color="#0000FF"),
        ]
        sheet.set_cell(2, 0, CellData(value="Red Bold Blue Underline", rich_runs=r_styles))

        # Write to XLSX bytes
        raw_bytes = write_xlsx(wb)
        assert len(raw_bytes) > 0

        # Inspect sharedStrings.xml
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
            assert "xl/sharedStrings.xml" in z.namelist()
            sst_xml = z.read("xl/sharedStrings.xml").decode("utf-8")
            assert '<vertAlign val="subscript"/>' in sst_xml
            assert '<vertAlign val="superscript"/>' in sst_xml
            assert '<color rgb="FFFF0000"/>' in sst_xml
            assert '<color rgb="FF0000FF"/>' in sst_xml
            assert "<b/>" in sst_xml
            assert "<u/>" in sst_xml

        # Read back with read_xlsx
        loaded_wb = read_xlsx(raw_bytes)
        assert len(loaded_wb) == 1
        loaded_sheet = loaded_wb[0]

        # Verify A1 (H2O)
        c00 = loaded_sheet.get_cell(0, 0)
        assert c00 is not None
        assert c00.value == "H2O"
        assert c00.rich_runs is not None
        assert len(c00.rich_runs) == 3
        assert c00.rich_runs[0].text == "H"
        assert c00.rich_runs[1].text == "2"
        assert c00.rich_runs[1].vert_align == "subscript"
        assert c00.rich_runs[2].text == "O"

        # Verify A2 (E = mc2)
        c10 = loaded_sheet.get_cell(1, 0)
        assert c10 is not None
        assert c10.value == "E = mc2"
        assert c10.rich_runs is not None
        assert len(c10.rich_runs) == 2
        assert c10.rich_runs[0].text == "E = mc"
        assert c10.rich_runs[0].italic is True
        assert c10.rich_runs[1].text == "2"
        assert c10.rich_runs[1].vert_align == "superscript"

        # Verify A3 (Colors & styles)
        c20 = loaded_sheet.get_cell(2, 0)
        assert c20 is not None
        assert c20.value == "Red Bold Blue Underline"
        assert c20.rich_runs is not None
        assert len(c20.rich_runs) == 2
        assert c20.rich_runs[0].text == "Red Bold "
        assert c20.rich_runs[0].bold is True
        assert c20.rich_runs[0].fg_color == "#FF0000"
        assert c20.rich_runs[1].text == "Blue Underline"
        assert c20.rich_runs[1].underline is True
        assert c20.rich_runs[1].fg_color == "#0000FF"

    def test_parse_rich_runs_helper_with_inline_xml(self):
        xml_content = """<is xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
            <r>
                <rPr><b/><sz val="12"/></rPr>
                <t>Hello </t>
            </r>
            <r>
                <rPr><i/><color rgb="FF00FF00"/></rPr>
                <t>World</t>
            </r>
        </is>"""
        el = ET.fromstring(xml_content)
        full_text, runs = _parse_rich_runs(el)
        assert full_text == "Hello World"
        assert runs is not None
        assert len(runs) == 2
        assert runs[0].text == "Hello "
        assert runs[0].bold is True
        assert runs[0].font_size == 12.0
        assert runs[1].text == "World"
        assert runs[1].italic is True
        assert runs[1].fg_color == "#00FF00"
