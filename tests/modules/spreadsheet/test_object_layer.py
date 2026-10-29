"""Unit tests for spreadsheet grid floating object layer and DrawingML sync."""

from __future__ import annotations

import io
import zipfile

import pytest
from PySide6.QtWidgets import QApplication

from atboffice.modules.spreadsheet.io.xlsx_reader import read_xlsx
from atboffice.modules.spreadsheet.io.xlsx_writer import write_xlsx
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    SheetDataModel,
    SheetGeometry,
)
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
    HandleType,
    SpreadsheetObjectLayer,
    object_to_rect,
    rect_to_anchor,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_floating_object_model_and_anchors():
    """Verify FloatingObject creation, cloning, and dictionary serialization."""
    p1 = CellAnchorPoint(col=1, col_off=10, row=2, row_off=5)
    p2 = CellAnchorPoint(col=4, col_off=20, row=6, row_off=15)

    obj = FloatingObject(
        id=10,
        name="Test Box",
        kind="textbox",
        anchor_type=AnchorType.TWO_CELL,
        from_point=p1,
        to_point=p2,
        fill_color="#FFCC00",
        fill_alpha=0.8,
        line_color="#003366",
        line_width=2.0,
        text="Quarterly Sales",
        z_index=1,
    )

    # 1. Clone test
    clone_obj = obj.clone()
    assert clone_obj.id == 10
    assert clone_obj.text == "Quarterly Sales"
    assert clone_obj.from_point.col == 1
    # Modify clone, ensure original is unchanged
    clone_obj.from_point.col = 9
    assert obj.from_point.col == 1

    # 2. Serialization test
    d = obj.to_dict()
    restored = FloatingObject.from_dict(d)
    assert restored.id == 10
    assert restored.name == "Test Box"
    assert restored.kind == "textbox"
    assert restored.anchor_type == AnchorType.TWO_CELL
    assert restored.from_point.col == 1
    assert restored.from_point.col_off == 10
    assert restored.from_point.row == 2
    assert restored.from_point.row_off == 5
    assert restored.to_point.col == 4
    assert restored.to_point.row == 6
    assert restored.fill_color == "#FFCC00"
    assert restored.fill_alpha == 0.8
    assert restored.text == "Quarterly Sales"


def test_object_to_rect_and_rect_to_anchor():
    """Verify conversion between cell anchors and viewport pixel coordinates."""
    geom = SheetGeometry(default_col_width=60, default_row_height=20)

    # Col 1 starts at 60px, Row 2 starts at 40px
    # Col 4 starts at 240px, Row 6 starts at 120px
    obj = FloatingObject(
        from_point=CellAnchorPoint(col=1, col_off=5, row=2, row_off=4),
        to_point=CellAnchorPoint(col=4, col_off=15, row=6, row_off=10),
    )

    rect = object_to_rect(
        obj=obj,
        geometry=geom,
        scroll_x=0,
        scroll_y=0,
        row_header_width=40,
        col_header_height=20,
    )

    expected_x = 40 + (1 * 60 + 5)  # 40 + 65 = 105
    expected_y = 20 + (2 * 20 + 4)  # 20 + 44 = 64
    expected_r = 40 + (4 * 60 + 15)  # 40 + 255 = 295
    expected_b = 20 + (6 * 20 + 10)  # 20 + 130 = 150
    expected_w = expected_r - expected_x  # 190
    expected_h = expected_b - expected_y  # 86

    assert rect.x() == expected_x
    assert rect.y() == expected_y
    assert rect.width() == expected_w
    assert rect.height() == expected_h

    # Convert back via rect_to_anchor
    new_from, new_to = rect_to_anchor(
        rect=rect,
        geometry=geom,
        scroll_x=0,
        scroll_y=0,
        row_header_width=40,
        col_header_height=20,
    )

    assert new_from.col == 1
    assert new_from.col_off == 5
    assert new_from.row == 2
    assert new_from.row_off == 4
    assert new_to.col == 4
    assert new_to.col_off == 15
    assert new_to.row == 6
    assert new_to.row_off == 10


def test_spreadsheet_object_layer_hit_testing_and_handles(qapp):
    """Verify hit-testing on object bodies and selection resize handles."""
    model = SheetDataModel(name="TestSheet")
    layer = SpreadsheetObjectLayer(model=model)
    layer.resize(800, 600)

    # Place an object
    obj = FloatingObject(
        id=1,
        name="Rect 1",
        kind="rect",
        from_point=CellAnchorPoint(col=1, col_off=0, row=1, row_off=0),
        to_point=CellAnchorPoint(col=3, col_off=0, row=4, row_off=0),
    )
    layer.add_object(obj)

    # Compute object rect
    rect = layer.get_object_rect(obj)
    center = rect.center()

    # 1. Hit test on body
    hit_obj, handle = layer.hit_test(center.x(), center.y())
    assert hit_obj is obj
    assert handle == HandleType.BODY

    # 2. Select object
    layer.select_object(obj)
    assert layer.selected_object is obj

    # 3. Hit test on Top-Left handle (NW)
    nw_pos = rect.topLeft()
    hit_nw, handle_nw = layer.hit_test(nw_pos.x(), nw_pos.y())
    assert hit_nw is obj
    assert handle_nw == HandleType.NW

    # 4. Hit test on Bottom-Right handle (SE)
    se_pos = rect.bottomRight()
    hit_se, handle_se = layer.hit_test(se_pos.x(), se_pos.y())
    assert hit_se is obj
    assert handle_se == HandleType.SE

    # 5. Hit test on outside space
    hit_none, handle_none = layer.hit_test(5, 5)
    assert hit_none is None
    assert handle_none == HandleType.NONE


def test_spreadsheet_object_layer_z_order_and_clipboard(qapp):
    """Verify Z-order adjustment and clipboard copy/paste/delete."""
    model = SheetDataModel(name="OrderTest")
    layer = SpreadsheetObjectLayer(model=model)

    o1 = FloatingObject(id=1, name="O1", z_index=0)
    o2 = FloatingObject(id=2, name="O2", z_index=1)
    o3 = FloatingObject(id=3, name="O3", z_index=2)

    layer.add_object(o1)
    layer.add_object(o2)
    layer.add_object(o3)

    # Initial order: [o1, o2, o3]
    assert [o.id for o in layer.objects] == [1, 2, 3]

    # Bring o1 to front
    layer.bring_to_front(o1)
    assert [o.id for o in layer.objects] == [2, 3, 1]

    # Send o1 to back
    layer.send_to_back(o1)
    assert [o.id for o in layer.objects] == [1, 2, 3]

    # Bring o1 forward one step
    layer.bring_forward(o1)
    assert [o.id for o in layer.objects] == [2, 1, 3]

    # Send o1 backward one step
    layer.send_backward(o1)
    assert [o.id for o in layer.objects] == [1, 2, 3]

    # Copy and paste o2
    layer.select_object(o2)
    layer.copy_selected()
    pasted = layer.paste()
    assert pasted is not None
    assert pasted.id != o2.id
    assert pasted.name.startswith("O2")
    assert pasted in layer.objects
    assert pasted in model.drawings

    # Delete selected
    layer.select_object(pasted)
    deleted = layer.delete_selected()
    assert deleted is True
    assert pasted not in layer.objects
    assert pasted not in model.drawings


def test_drawingml_xlsx_writer_and_reader_roundtrip():
    """Verify roundtrip DrawingML serialization and deserialization in XLSX."""
    wb = WorkbookModel()
    sheet = wb.active_sheet
    sheet.name = "GraphicsSheet"

    # Add sample cell
    sheet.set_cell(0, 0, CellData(value="Sales Overview"))

    # 1. Rectangle Shape
    shape = FloatingObject(
        id=2,
        name="Revenue Box",
        kind="rect",
        anchor_type=AnchorType.TWO_CELL,
        from_point=CellAnchorPoint(col=1, col_off=10, row=1, row_off=5),
        to_point=CellAnchorPoint(col=3, col_off=20, row=4, row_off=15),
        fill_color="#4F81BD",
        line_color="#385D8A",
        line_width=1.5,
    )

    # 2. Textbox
    textbox = FloatingObject(
        id=3,
        name="Notice Text",
        kind="textbox",
        anchor_type=AnchorType.TWO_CELL,
        from_point=CellAnchorPoint(col=4, col_off=0, row=1, row_off=0),
        to_point=CellAnchorPoint(col=6, col_off=0, row=3, row_off=0),
        fill_color="#FFFFFF",
        line_color="#000000",
        text="Confidential Report\nFor Internal Use Only",
    )

    # 3. Picture
    # 1x1 transparent PNG payload
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
        b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pic = FloatingObject(
        id=4,
        name="Company Logo",
        kind="image",
        anchor_type=AnchorType.TWO_CELL,
        from_point=CellAnchorPoint(col=7, col_off=0, row=1, row_off=0),
        to_point=CellAnchorPoint(col=9, col_off=0, row=4, row_off=0),
        image_data=png_bytes,
        image_mime="image/png",
    )

    sheet.drawings.extend([shape, textbox, pic])

    # Write to XLSX bytes
    raw_bytes = write_xlsx(wb)
    assert isinstance(raw_bytes, bytes)
    assert len(raw_bytes) > 0

    # Inspect zip contents
    with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
        names = z.namelist()
        assert "xl/drawings/drawing1.xml" in names
        assert "xl/worksheets/_rels/sheet1.xml.rels" in names
        assert any(n.startswith("xl/media/") for n in names)

        # Inspect drawing1.xml content
        drawing_xml = z.read("xl/drawings/drawing1.xml").decode("utf-8")
        assert "Revenue Box" in drawing_xml
        assert "Notice Text" in drawing_xml
        assert "Confidential Report" in drawing_xml

    # Read back with read_xlsx
    loaded_wb = read_xlsx(raw_bytes)
    assert len(loaded_wb) == 1
    loaded_sheet = loaded_wb[0]

    # Verify drawings were restored
    assert hasattr(loaded_sheet, "drawings")
    assert len(loaded_sheet.drawings) == 3

    # Check restored shape
    restored_shape = next(d for d in loaded_sheet.drawings if d.name == "Revenue Box")
    assert restored_shape.kind == "rect"
    assert restored_shape.from_point.col == 1
    assert restored_shape.from_point.row == 1
    assert restored_shape.to_point.col == 3
    assert restored_shape.to_point.row == 4
    assert restored_shape.fill_color.upper() == "#4F81BD"

    # Check restored textbox
    restored_tb = next(d for d in loaded_sheet.drawings if d.name == "Notice Text")
    assert restored_tb.kind == "textbox"
    assert "Confidential Report" in restored_tb.text

    # Check restored picture
    restored_pic = next(d for d in loaded_sheet.drawings if d.name == "Company Logo")
    assert restored_pic.kind == "image"
    assert restored_pic.image_data == png_bytes
