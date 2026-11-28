"""Tests for Phase 13C Quire floating object commands and FormatObjectDialog."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QDialog

from atboffice.core.i18n import load_locale, safe_tr
from atboffice.modules.writer.dialogs.format_object_dialog import FormatObjectDialog
from atboffice.modules.writer.models.document import all_stories
from atboffice.modules.writer.models.drawing import (
    Crop,
    FloatProperties,
    PictureItem,
    PositionH,
    PositionV,
    ShapeItem,
    WrapMode,
)
from atboffice.modules.writer.views import canvas_object_commands as obj_cmds
from atboffice.ui.shell.quire_commands import FLOAT_SCOPED_COMMANDS, OBJECT_COMMANDS
from atboffice.ui.shell.quire_window import QuireWindow


@pytest.fixture
def quire(qtbot) -> QuireWindow:
    load_locale("zh-CN")
    win = QuireWindow()
    qtbot.addWidget(win)
    yield win
    load_locale("zh-CN")
    win.set_modified(False)


def _insert_floating_picture(win: QuireWindow, tmp_path: Path) -> PictureItem:
    img = QImage(24, 16, QImage.Format.Format_RGBA8888)
    img.fill(QColor("#336699"))
    img_path = tmp_path / "sample.png"
    img.save(str(img_path), "PNG")
    assert win.insert_image_bytes(img_path.read_bytes(), "png", "sample") is True

    canvas = win.writer_view.canvas_view
    pic = next(
        r
        for st in all_stories(canvas.doc)
        for p in st.paras
        for r in p.runs
        if isinstance(r, PictureItem) and not isinstance(r, ShapeItem)
    )
    pic.float_pr = FloatProperties(
        wrap=WrapMode.SQUARE,
        pos_h=PositionH(rel="margin", offset=48.0),
        pos_v=PositionV(rel="paragraph", offset=12.0),
    )
    canvas.refresh_layout()
    canvas.select_float(0, pic)
    return pic


def _all_pictures(doc) -> list[PictureItem]:
    return [
        r
        for st in all_stories(doc)
        for p in st.paras
        for r in p.runs
        if isinstance(r, PictureItem) and not isinstance(r, ShapeItem)
    ]


def _all_shapes(doc) -> list[ShapeItem]:
    return [
        r for st in all_stories(doc) for p in st.paras for r in p.runs if isinstance(r, ShapeItem)
    ]


def test_object_action_enable_sync_and_no_selection_hint(quire) -> None:
    reg = quire.action_registry
    canvas = quire.writer_view.canvas_view

    # None of the implemented commands remain in unimplemented OBJECT_COMMANDS
    for aid in FLOAT_SCOPED_COMMANDS:
        assert aid not in OBJECT_COMMANDS
        assert reg.has_action(aid), aid
        assert reg.has_command(aid), aid
        assert not reg.is_enabled(aid), f"{aid} should start disabled without float selection"

    # Calling commands directly with no selection returns False and sets a localized status hint
    hints: list[str] = []
    assert obj_cmds.pic_rotate(canvas, status_cb=hints.append) is False
    assert obj_cmds.wrap_square(canvas, status_cb=hints.append) is False
    assert obj_cmds.draw_weight_075(canvas, status_cb=hints.append) is False
    assert obj_cmds.format_object(canvas, parent=quire, status_cb=hints.append) is False
    assert hints and all(h == safe_tr(obj_cmds.OBJECT_HINT) for h in hints)

    # Selecting a floating shape enables all float-scoped actions
    quire.insert_shape("rect")
    assert canvas.selected_float() is not None
    for aid in FLOAT_SCOPED_COMMANDS:
        assert reg.is_enabled(aid), f"{aid} should be enabled when float is selected"

    # Deselecting disables them again
    canvas.select_float(None, None)
    for aid in FLOAT_SCOPED_COMMANDS:
        assert not reg.is_enabled(aid), f"{aid} should be disabled after deselecting"


def test_wrap_modes_and_undo_redo(quire) -> None:
    reg = quire.action_registry
    canvas = quire.writer_view.canvas_view

    quire.insert_shape("rect")
    shape = canvas.selected_float()
    assert isinstance(shape, ShapeItem)
    assert shape.float_pr is not None and shape.float_pr.wrap == WrapMode.IN_FRONT

    assert reg.trigger_action("wrap_square") is True
    assert shape.float_pr.wrap == WrapMode.SQUARE
    assert shape.float_pr.behind is False

    assert reg.trigger_action("wrap_tight") is True
    assert shape.float_pr.wrap == WrapMode.TIGHT
    assert shape.float_pr.behind is False

    assert reg.trigger_action("wrap_behind") is True
    assert shape.float_pr.wrap == WrapMode.BEHIND
    assert shape.float_pr.behind is True

    assert reg.trigger_action("wrap_front") is True
    assert shape.float_pr.wrap == WrapMode.IN_FRONT
    assert shape.float_pr.behind is False

    # Converting to inline clears float_pr and clears float selection
    assert reg.trigger_action("wrap_inline") is True
    assert _all_shapes(canvas.doc)[0].float_pr is None
    assert canvas.selected_float() is None

    # Undo restores floating state; redo reapplies inline
    assert canvas.undo() is True
    restored = _all_shapes(canvas.doc)[0]
    assert restored.float_pr is not None
    assert restored.float_pr.wrap == WrapMode.IN_FRONT

    assert canvas.redo() is True
    assert _all_shapes(canvas.doc)[0].float_pr is None


def test_picture_commands_and_reset_undo_redo(quire, tmp_path) -> None:
    reg = quire.action_registry
    canvas = quire.writer_view.canvas_view
    pic = _insert_floating_picture(quire, tmp_path)
    orig_w, orig_h = pic.natural_width, pic.natural_height

    # Rotate +90 mod 360
    assert reg.trigger_action("picRotate") is True
    assert pic.rotation == 90.0
    assert reg.trigger_action("picRotate") is True
    assert reg.trigger_action("picRotate") is True
    assert reg.trigger_action("picRotate") is True
    assert pic.rotation == 0.0
    assert reg.trigger_action("picRotate") is True
    assert pic.rotation == 90.0

    # Brightness & Contrast
    assert reg.trigger_action("picMoreBright") is True
    assert pic.brightness == pytest.approx(0.1)
    assert reg.trigger_action("picLessBright") is True
    assert pic.brightness == pytest.approx(0.0)
    assert reg.trigger_action("picLessBright") is True
    assert pic.brightness == pytest.approx(-0.1)

    assert reg.trigger_action("picMoreContrast") is True
    assert pic.contrast == pytest.approx(0.1)
    assert reg.trigger_action("picLessContrast") is True
    assert reg.trigger_action("picLessContrast") is True
    assert pic.contrast == pytest.approx(-0.1)

    # Color modes
    assert reg.trigger_action("pic_color_gray") is True
    assert pic.grayscale is True
    assert pic.washout is False
    assert getattr(pic, "color_mode", None) == "gray"

    assert reg.trigger_action("pic_color_bw") is True
    assert pic.grayscale is False
    assert getattr(pic, "color_mode", None) == "bw"

    assert reg.trigger_action("pic_color_wash") is True
    assert pic.washout is True
    assert getattr(pic, "color_mode", None) == "washout"

    assert reg.trigger_action("pic_color_auto") is True
    assert pic.grayscale is False
    assert pic.washout is False
    assert getattr(pic, "color_mode", None) == "auto"

    # Mutate size & crop then reset
    pic.width = orig_w * 1.5
    pic.height = orig_h * 1.5
    pic.crop = Crop(left=0.1, top=0.1, right=0.1, bottom=0.1)
    assert reg.trigger_action("pic_color_gray") is True
    assert reg.trigger_action("picReset") is True

    reset_pic = _all_pictures(canvas.doc)[0]
    assert reset_pic.rotation == 0.0
    assert reset_pic.brightness == 0.0
    assert reset_pic.contrast == 0.0
    assert reset_pic.grayscale is False
    assert reset_pic.washout is False
    assert reset_pic.crop == Crop(0.0, 0.0, 0.0, 0.0)
    assert reset_pic.width == pytest.approx(orig_w)
    assert reset_pic.height == pytest.approx(orig_h)

    # Undo picReset restores pre-reset state
    assert canvas.undo() is True
    pre_reset = _all_pictures(canvas.doc)[0]
    assert pre_reset.rotation == 90.0
    assert pre_reset.grayscale is True


def test_drawing_style_commands_and_undo_redo(quire) -> None:
    reg = quire.action_registry
    canvas = quire.writer_view.canvas_view

    quire.insert_shape("line")
    shape = canvas.selected_float()
    assert isinstance(shape, ShapeItem)

    assert reg.trigger_action("draw_weight_075") is True
    assert shape.line.visible is True
    assert shape.line.width == pytest.approx(0.75)

    assert reg.trigger_action("draw_dash_dash") is True
    assert shape.line.dash == "dash"

    assert reg.trigger_action("draw_arrow_1") is True
    assert getattr(shape.line, "tail", None) == {"type": "triangle", "w": "med", "len": "med"}
    assert getattr(shape, "arrow", None) == "style1"

    assert reg.trigger_action("draw_shadow_1") is True
    assert getattr(shape, "shadow", False) is True
    assert "shadow" in shape.raw_data

    # Undo shadow & arrow
    assert canvas.undo() is True
    assert not getattr(_all_shapes(canvas.doc)[0], "shadow", False)
    assert canvas.undo() is True
    assert getattr(_all_shapes(canvas.doc)[0].line, "tail", None) is None


def test_format_object_dialog_edit_retranslate_and_undo(quire, qtbot, monkeypatch) -> None:
    canvas = quire.writer_view.canvas_view
    quire.insert_shape("rect")
    shape = canvas.selected_float()
    assert isinstance(shape, ShapeItem)

    dlg = FormatObjectDialog(shape, parent=quire)
    qtbot.addWidget(dlg)
    assert dlg.windowTitle() == "设置对象格式"
    assert dlg.chk_shadow.isChecked() is False

    # Dynamic retranslation
    load_locale("en")
    dlg.retranslate_ui()
    assert dlg.windowTitle() == "Format Object"
    assert dlg.grp_size.title() == "Size and rotate"
    load_locale("zh-CN")
    dlg.retranslate_ui()
    assert dlg.windowTitle() == "设置对象格式"

    # Drive dialog edits via mocked exec() and trigger formatObject action
    def _mock_exec(self_dlg: FormatObjectDialog) -> int:
        self_dlg.spin_width.setValue(180.0)
        self_dlg.spin_height.setValue(96.0)
        self_dlg.spin_rotation.setValue(45.0)
        idx = self_dlg.combo_wrap.findData(WrapMode.TIGHT.value)
        assert idx >= 0
        self_dlg.combo_wrap.setCurrentIndex(idx)
        self_dlg.set_line_color("#FF0000")
        self_dlg.spin_line_width.setValue(2.5)
        self_dlg.set_fill_color("#00AAFF")
        self_dlg.chk_shadow.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(FormatObjectDialog, "exec", _mock_exec)
    assert quire.action_registry.trigger_action("formatObject") is True

    edited = _all_shapes(canvas.doc)[0]
    assert edited.width == pytest.approx(180.0)
    assert edited.height == pytest.approx(96.0)
    assert edited.rotation == pytest.approx(45.0)
    assert edited.float_pr is not None
    assert edited.float_pr.wrap == WrapMode.TIGHT
    assert edited.line.visible is True
    assert edited.line.color == "#FF0000"
    assert edited.line.width == pytest.approx(2.5)
    assert edited.fill.kind == "solid"
    assert edited.fill.color == "#00AAFF"
    assert getattr(edited, "shadow", False) is True

    # Undo / Redo
    assert canvas.undo() is True
    reverted = _all_shapes(canvas.doc)[0]
    assert reverted.width == pytest.approx(144.0)
    assert reverted.rotation == pytest.approx(0.0)
    assert reverted.float_pr.wrap == WrapMode.IN_FRONT
    assert not getattr(reverted, "shadow", False)

    assert canvas.redo() is True
    redone = _all_shapes(canvas.doc)[0]
    assert redone.width == pytest.approx(180.0)
    assert redone.rotation == pytest.approx(45.0)
    assert redone.float_pr.wrap == WrapMode.TIGHT


def test_object_commands_docx_roundtrip(quire, qtbot, tmp_path, monkeypatch) -> None:
    # 1. Floating picture rotated 90° and wrapped behind text
    _insert_floating_picture(quire, tmp_path)
    assert quire.action_registry.trigger_action("picRotate") is True
    assert quire.action_registry.trigger_action("wrap_behind") is True

    # 2. Floating shape formatted via FormatObjectDialog (square wrap, size, rot, line, fill)
    quire.insert_shape("rect")

    def _mock_exec(self_dlg: FormatObjectDialog) -> int:
        self_dlg.spin_width.setValue(200.0)
        self_dlg.spin_height.setValue(100.0)
        self_dlg.spin_rotation.setValue(30.0)
        self_dlg.combo_wrap.setCurrentIndex(self_dlg.combo_wrap.findData(WrapMode.SQUARE.value))
        self_dlg.set_line_color("#112233")
        self_dlg.spin_line_width.setValue(2.0)
        self_dlg.set_fill_color("#AABBCC")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(FormatObjectDialog, "exec", _mock_exec)
    assert quire.action_registry.trigger_action("formatObject") is True

    # 3. Inline textbox converted via wrap_inline
    quire.insert_shape("textbox")
    assert quire.action_registry.trigger_action("wrap_inline") is True

    out = tmp_path / "objects_roundtrip.docx"
    assert quire.save_file(out, confirm_overwrite=False) is True

    reopened = QuireWindow()
    qtbot.addWidget(reopened)
    assert reopened.open_file(out) is True
    rdoc = reopened.writer_view.canvas_view.doc

    rpics = _all_pictures(rdoc)
    assert len(rpics) == 1
    assert rpics[0].rotation == pytest.approx(90.0, abs=0.5)
    assert rpics[0].float_pr is not None
    assert rpics[0].float_pr.wrap == WrapMode.BEHIND
    assert rpics[0].float_pr.behind is True

    rshapes = _all_shapes(rdoc)
    assert len(rshapes) == 2
    rect = next(s for s in rshapes if s.story is None)
    tb = next(s for s in rshapes if s.story is not None)

    assert rect.width == pytest.approx(200.0, abs=0.5)
    assert rect.height == pytest.approx(100.0, abs=0.5)
    assert rect.rotation == pytest.approx(30.0, abs=0.5)
    assert rect.float_pr is not None
    assert rect.float_pr.wrap == WrapMode.SQUARE
    assert rect.float_pr.behind is False
    assert rect.line is not None and rect.line.visible is True
    assert rect.line.color.upper() == "#112233"
    assert rect.line.width == pytest.approx(2.0, abs=0.1)
    assert rect.fill is not None and rect.fill.kind == "solid"
    assert rect.fill.color.upper() == "#AABBCC"

    assert tb.float_pr is None

    # Edit reopened shape again and save a second time to verify raw_xml invalidation works
    rcanvas = reopened.writer_view.canvas_view
    rcanvas.select_float(0, rect)
    assert reopened.action_registry.trigger_action("wrap_tight") is True
    out2 = tmp_path / "objects_roundtrip_2.docx"
    assert reopened.save_file(out2, confirm_overwrite=False) is True

    reopened2 = QuireWindow()
    qtbot.addWidget(reopened2)
    assert reopened2.open_file(out2) is True
    rect2 = next(s for s in _all_shapes(reopened2.writer_view.canvas_view.doc) if s.story is None)
    assert rect2.float_pr is not None
    assert rect2.float_pr.wrap == WrapMode.TIGHT

    reopened.set_modified(False)
    reopened2.set_modified(False)
