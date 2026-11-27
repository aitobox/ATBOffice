"""Tests for Ledger object-layer undo, comment undo, event guards, and XLSX round-trip."""

from __future__ import annotations

import zipfile

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QInputDialog

from atboffice.modules.spreadsheet.dialogs.comment_dialog import CommentDialog
from atboffice.ui.shell.ledger_window import LedgerWindow


def test_ledger_insert_shape_textbox_picture_and_comment_are_undoable_and_save(
    qtbot, tmp_path, monkeypatch
) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()

    img = QImage(16, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#2F5597"))
    img_path = tmp_path / "sample.png"
    img.save(str(img_path), "PNG")

    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Audit note")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Tester")

    win.insert_shape("rect")
    win.insert_textbox()
    win.insert_picture(str(img_path))
    win.insert_comment()

    sheet = win.spreadsheet_view.model
    assert len(sheet.drawings) == 3
    assert sheet.get_comment(0, 0) is not None

    # Undo comment, picture, textbox
    win.undo()
    assert sheet.get_comment(0, 0) is None
    win.undo()
    assert len(sheet.drawings) == 2
    win.undo()
    assert len(sheet.drawings) == 1
    win.redo()
    win.redo()
    win.redo()
    assert len(sheet.drawings) == 3
    assert sheet.get_comment(0, 0) is not None

    # Interactive click/delete on object layer does not crash and returns focus cleanly
    layer = win.spreadsheet_view.object_layer
    rect = layer.get_object_rect(sheet.drawings[-1])
    QTest.mouseClick(
        layer, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, rect.center()
    )
    QTest.keyClick(layer, Qt.Key.Key_Delete)
    assert len(sheet.drawings) == 2
    win.undo()
    assert len(sheet.drawings) == 3

    out = tmp_path / "objects.xlsx"
    assert win.save_file(out, confirm_overwrite=False) is True
    assert out.stat().st_size > 0

    reopened = LedgerWindow()
    qtbot.addWidget(reopened)
    assert reopened.open_file(out) is True
    reopened_cm = reopened.spreadsheet_view.model.get_comment(0, 0)
    assert reopened_cm is not None
    assert reopened_cm.text == "Audit note"
    assert reopened_cm.author == "Tester"
    assert len(reopened.spreadsheet_view.model.drawings) == 3

    reopened.delete_comment()
    out2 = tmp_path / "objects_no_comment.xlsx"
    assert reopened.save_file(out2, confirm_overwrite=False) is True
    with zipfile.ZipFile(out2, "r") as zf:
        names = zf.namelist()
        assert not any("comments" in n for n in names)
        assert not any("vmlDrawing" in n for n in names)
        s1_xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "<legacyDrawing" not in s1_xml
        if "xl/worksheets/_rels/sheet1.xml.rels" in names:
            s1_rels = zf.read("xl/worksheets/_rels/sheet1.xml.rels").decode("utf-8")
            assert "relationships/comments" not in s1_rels
            assert "relationships/vmlDrawing" not in s1_rels

    reopened2 = LedgerWindow()
    qtbot.addWidget(reopened2)
    assert reopened2.open_file(out2) is True
    assert reopened2.spreadsheet_view.model.get_comment(0, 0) is None
    assert len(reopened2.spreadsheet_view.model.drawings) == 3

    win.set_modified(False)
    reopened.set_modified(False)
    reopened2.set_modified(False)


def test_ledger_object_drag_paste_zorder_comment_delete_and_event_guards(
    qtbot, monkeypatch
) -> None:
    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()

    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Note")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Author")

    win.insert_shape("rect")
    win.insert_shape("oval")
    sheet = win.spreadsheet_view.model
    layer = win.spreadsheet_view.object_layer
    assert len(sheet.drawings) == 2
    assert sheet.drawings[-1].kind == "oval"

    # Bring first object to front & undo
    layer.select_object(sheet.drawings[0])
    win.bring_to_front()
    assert sheet.drawings[-1].kind == "rect"
    win.undo()
    assert sheet.drawings[-1].kind == "oval"

    # Fill color & undo
    layer.select_object(sheet.drawings[-1])
    win._apply_drawing_fill_color("#FF0000")
    assert sheet.drawings[-1].fill_color == "#FF0000"
    win.undo()
    assert sheet.drawings[-1].fill_color != "#FF0000"

    # Drag move on object layer & undo
    target = sheet.drawings[-1]
    orig_from = (target.from_point.row, target.from_point.col)
    start_pos = layer.get_object_rect(target).center()
    end_pos = start_pos + QPoint(80, 40)
    QTest.mousePress(layer, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start_pos)
    QTest.mouseMove(layer, end_pos)
    QTest.mouseRelease(layer, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, end_pos)
    moved_from = (sheet.drawings[-1].from_point.row, sheet.drawings[-1].from_point.col)
    assert moved_from != orig_from
    win.undo()
    restored_from = (sheet.drawings[-1].from_point.row, sheet.drawings[-1].from_point.col)
    assert restored_from == orig_from

    # Copy/paste via object_layer & undo
    layer.select_object(sheet.drawings[-1])
    layer.copy_selected()
    pasted = layer.paste()
    assert pasted is not None
    assert len(sheet.drawings) == 3
    win.undo()
    assert len(sheet.drawings) == 2

    # Comment insert + delete undo
    win.insert_comment()
    assert sheet.get_comment(0, 0) is not None
    win.delete_comment()
    assert sheet.get_comment(0, 0) is None
    win.undo()
    assert sheet.get_comment(0, 0) is not None

    # Event guard protects against unexpected exceptions inside layer events
    def _boom(_x: int, _y: int) -> tuple[None, None]:
        raise RuntimeError("boom")

    monkeypatch.setattr(layer, "hit_test", _boom)
    QTest.mousePress(layer, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))

    win.set_modified(False)


def test_ledger_zorder_text_edit_show_hide_comment_and_chart_wizard_undo(
    qtbot, monkeypatch
) -> None:
    from atboffice.modules.spreadsheet.dialogs.chart_wizard import ChartWizardDialog
    from atboffice.modules.spreadsheet.dialogs.format_object_dialog import FormatObjectDialog
    from atboffice.modules.spreadsheet.views.object_layer import AnchorType, FloatingObject

    win = LedgerWindow()
    qtbot.addWidget(win)
    win.resize(1100, 800)
    win.show()

    win.insert_shape("rect")
    win.insert_shape("oval")
    sheet = win.spreadsheet_view.model
    layer = win.spreadsheet_view.object_layer

    # Direct SpreadsheetObjectLayer Z-order ops are undoable
    layer.send_backward(sheet.drawings[1])
    assert [d.kind for d in sheet.drawings] == ["oval", "rect"]
    win.undo()
    assert [d.kind for d in sheet.drawings] == ["rect", "oval"]
    layer.bring_forward(sheet.drawings[0])
    assert [d.kind for d in sheet.drawings] == ["oval", "rect"]
    win.undo()
    assert [d.kind for d in sheet.drawings] == ["rect", "oval"]

    # Text editing via object_layer is undoable
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a, **k: ("Edited Label", True))
    layer.start_text_editing(sheet.drawings[0])
    assert sheet.drawings[0].text == "Edited Label"
    win.undo()
    assert sheet.drawings[0].text != "Edited Label"

    # FormatObjectDialog is undoable
    def _fake_format_exec(dlg):
        dlg.obj.fill_color = "#112233"
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(FormatObjectDialog, "exec", _fake_format_exec)
    layer.select_object(sheet.drawings[0])
    win.format_selected_object()
    assert sheet.drawings[0].fill_color == "#112233"
    win.undo()
    assert sheet.drawings[0].fill_color != "#112233"

    # show_hide_comment is undoable
    monkeypatch.setattr(CommentDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(CommentDialog, "get_text", lambda self: "Visibility test")
    monkeypatch.setattr(CommentDialog, "get_author", lambda self: "Tester")
    win.insert_comment()
    assert sheet.get_comment(0, 0).visible is False
    win.show_hide_comment()
    assert sheet.get_comment(0, 0).visible is True
    win.undo()
    assert sheet.get_comment(0, 0).visible is False

    # open_chart_wizard (embedded chart) is undoable/redoable
    def _fake_embedded_exec(dlg):
        chart_obj = FloatingObject(id=99, kind="chart", anchor_type=AnchorType.TWO_CELL)
        sheet.drawings.append(chart_obj)
        dlg.chart_created.emit(chart_obj, "embedded")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ChartWizardDialog, "exec", _fake_embedded_exec)
    before_count = len(sheet.drawings)
    win.open_chart_wizard()
    assert len(sheet.drawings) == before_count + 1
    win.undo()
    assert len(sheet.drawings) == before_count
    win.redo()
    assert len(sheet.drawings) == before_count + 1

    # open_chart_wizard (new chart sheet) is undoable/redoable
    wb = win.spreadsheet_view.workbook
    initial_sheets = len(wb)

    def _fake_sheet_exec(dlg):
        new_sheet = wb.add_sheet(name="Chart1")
        chart_obj = FloatingObject(id=100, kind="chart", anchor_type=AnchorType.TWO_CELL)
        new_sheet.drawings.append(chart_obj)
        dlg.created_sheet = new_sheet
        dlg.chart_created.emit(chart_obj, "sheet")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ChartWizardDialog, "exec", _fake_sheet_exec)
    win.open_chart_wizard()
    assert len(wb) == initial_sheets + 1
    assert win.spreadsheet_view.model.name == "Chart1"
    win.undo()
    assert len(wb) == initial_sheets
    assert win.spreadsheet_view.model is sheet
    win.redo()
    assert len(wb) == initial_sheets + 1
    assert win.spreadsheet_view.model.name == "Chart1"

    win.set_modified(False)
