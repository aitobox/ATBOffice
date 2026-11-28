"""Real handlers for Lectern commands that used to be toast-only stubs or unbound IDs."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from atboffice.core.i18n import safe_tr
from atboffice.modules.presentation.tools import shape_styles, table_ops

if TYPE_CHECKING:
    from atboffice.ui.shell.lectern_window import LecternWindow


CONTAINER_COMMANDS = (
    "autoshapes_menu",
    "draw_menu",
    "table_menu",
    "lineStyle",
    "draw_dash_style",
    "draw_arrow_style",
    "draw_shadow_style",
    "tbl_line_weight",
    "tbl_line_color",
    "tbl_dash_style",
    "tbl_shading_color",
    "pic_color_mode",
    "pic_line_style",
    "wa_shape_menu",
    "wa_align_menu",
    "wa_char_spacing_menu",
    "diagram_layout_menu",
    "diagram_colors_menu",
    "diagram_style_menu",
)
PLACEHOLDER_COMMANDS = ("undo_empty", "redo_empty")
RECORD_REASON = "录制旁白需要麦克风录音支持，将在后续版本提供"

TABLE_DASHES = {"single": "solid", "dash": "dash", "dot": "sysDot", "double": "solid"}
TABLE_WEIGHTS = {
    "05": 0.5,
    "10": 1.0,
    "15": 1.5,
    "225": 2.25,
    "30": 3.0,
    "45": 4.5,
    "60": 6.0,
}
TABLE_COLORS = {
    "auto": "#000000",
    "black": "#000000",
    "red": "#FF0000",
    "blue": "#0000FF",
    "gray": "#808080",
}
TABLE_SHADES = {
    "none": None,
    "gray": "#D9D9D9",
    "yellow": "#FFFF99",
    "blue": "#CCECFF",
    "green": "#CCFFCC",
}
PICTURE_WEIGHTS = {"075": 0.75, "15": 1.5, "30": 3.0, "45": 4.5, "60": 6.0}
WORDART_SHAPES = {
    "plain": "textPlain",
    "wave": "textWave1",
    "arch_up": "textArchUp",
    "arch_down": "textArchDown",
    "circle": "textCircle",
    "triangle_down": "textTriangle",
}
WORDART_SPACING = {
    "very_tight": -0.2,
    "tight": -0.1,
    "normal": 0.0,
    "loose": 0.2,
    "very_loose": 0.4,
}
DIAGRAM_LAYOUTS = {
    "org": "orgChart",
    "hierarchy": "hierarchy",
    "cycle": "cycle",
    "radial": "radial",
    "pyramid": "pyramid",
    "venn": "venn",
    "target": "target",
}
DIAGRAM_COLORS = {"primary": "ocean", "colorful": "vivid", "dark": "midnight", "light": "pastel"}
DIAGRAM_STYLES = {"flat": "flat", "3d": "lifted", "metal": "gloss", "gradient": "soft"}
LANGUAGES = [
    ("中文(中国)", "zh-CN"),
    ("English (United States)", "en-US"),
    ("English (United Kingdom)", "en-GB"),
    ("中文(台湾)", "zh-TW"),
    ("日本語", "ja-JP"),
    ("한국어", "ko-KR"),
    ("Deutsch", "de-DE"),
    ("Français", "fr-FR"),
    ("Español", "es-ES"),
    ("Русский", "ru-RU"),
]


class _PickFilter(QObject):
    """One-shot viewport click filter (Set Transparent Color / Format Painter)."""

    def __init__(self, view: Any, callback: Callable[[QPointF], bool]) -> None:
        super().__init__(view)
        self.view = view
        self.callback = callback
        view.viewport().installEventFilter(self)
        view.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                consumed = self.callback(self.view.mapToScene(event.position().toPoint()))
                self.dispose()
                return consumed
            self.dispose()
        elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.dispose()
        return False

    def dispose(self) -> None:
        vp = self.view.viewport()
        vp.removeEventFilter(self)
        vp.unsetCursor()
        self.deleteLater()


class LecternCommands:
    """Owns command state (table pen, format painter) and binds handlers to action IDs."""

    def __init__(self, window: LecternWindow) -> None:
        self.w = window
        self.table_pen: dict[str, Any] = {"w": 1.0, "c": "#000000", "dash": "solid"}
        self._find_dialog: Any = None
        self._painter_source: Any = None
        self._pick_filter: _PickFilter | None = None

    # ------------------------------------------------------------------ helpers
    @property
    def ws(self) -> Any:
        return getattr(self.w.presentation_view, "workspace", None)

    @property
    def pres(self) -> Any:
        return getattr(self.w.presentation_view, "presentation", None)

    @property
    def scene(self) -> Any:
        ws = self.ws
        return getattr(ws, "scene", None) if ws is not None else None

    def selected_items(self) -> list[Any]:
        sc = self.scene
        if sc is None:
            return []
        return [it for it in sc.selectedItems() if getattr(it, "model", None) is not None]

    def selected_shapes(self) -> list[Any]:
        return [it.model for it in self.selected_items()]

    def active_editor(self) -> Any | None:
        for it in self.selected_items():
            if getattr(it, "is_editing_text", False) and getattr(it, "_text_editor", None):
                return it._text_editor
        sc = self.scene
        focus = sc.focusItem() if sc is not None else None
        if focus is not None and hasattr(focus, "commit_and_finish"):
            return focus
        return None

    def refresh(self, select_ids: list[str] | None = None, message: str = "") -> None:
        """Reload the slide into the scene, keep the selection and mark modified."""
        ws, sc = self.ws, self.scene
        if ws is not None and sc is not None:
            keep = select_ids if select_ids is not None else [s.id for s in self.selected_shapes()]
            slide = getattr(ws, "master_slide", None) if ws.view_mode == "master" else None
            sc.load_slide(slide or ws.current_slide)
            for sid in keep:
                item = sc.get_shape_item(sid)
                if item is not None:
                    item.setSelected(True)
            if hasattr(ws, "_refresh_current_thumbnail") and ws.view_mode != "master":
                ws._refresh_current_thumbnail()
        self.w.set_modified(True)
        if message:
            self.w.show_status_message(message)

    def _update_items(self, items: list[Any], message: str = "") -> None:
        for it in items:
            it.update()
        self.w.set_modified(True)
        if message:
            self.w.show_status_message(message)

    def _require(self, ok: bool, message: str) -> bool:
        if not ok:
            self.w.show_status_message(message, 3000)
        return ok

    # ------------------------------------------------------------------ tables
    def _table_target(self) -> tuple[Any, Any, tuple[int, int, int, int]] | None:
        """(item, shape, range) for the selected table; range defaults to the whole table."""
        for it in self.selected_items():
            shape = it.model
            if shape.tbl:
                table_ops.normalize(shape.tbl)
                n_rows, n_cols = table_ops.dims(shape.tbl)
                if not n_rows or not n_cols:
                    return None
                rect = it.table_sel or (0, 0, n_rows - 1, n_cols - 1)
                r1, c1, r2, c2 = rect
                rect = (
                    min(r1, n_rows - 1),
                    min(c1, n_cols - 1),
                    min(r2, n_rows - 1),
                    min(c2, n_cols - 1),
                )
                return it, shape, rect
        self.w.show_status_message(safe_tr("请先选择一个表格"), 3000)
        return None

    def _commit_cell_editor(self, item: Any) -> None:
        ed = getattr(item, "_text_editor", None)
        if ed is not None and hasattr(ed, "commit_and_finish"):
            ed.commit_and_finish()

    def _after_table_change(self, item: Any, shape: Any, message: str) -> None:
        new_h = table_ops.table_height(shape.tbl)
        if abs(new_h - shape.h) > 0.5:
            item.prepareGeometryChange()
            shape.h = new_h
        item.update()
        if hasattr(item, "_position_handles"):
            item._position_handles()
        self.w.set_modified(True)
        self.w.show_status_message(message)

    def table_merge(self) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        if not self._require(
            rect[0] != rect[2] or rect[1] != rect[3], safe_tr("请按住 Shift 选择要合并的多个单元格")
        ):
            return
        self._commit_cell_editor(item)
        item.table_sel = table_ops.merge(shape.tbl, rect)
        self._after_table_change(item, shape, safe_tr("已合并单元格"))

    def table_split(self) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        if not self._require(
            table_ops.split(shape.tbl, rect[0], rect[1]), safe_tr("所选单元格未合并，无需拆分")
        ):
            return
        item.table_sel = (rect[0], rect[1], rect[0], rect[1])
        self._after_table_change(item, shape, safe_tr("已拆分单元格"))

    def table_insert_row(self, above: bool) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        at = rect[0] if above else rect[2] + 1
        table_ops.insert_row(shape.tbl, at)
        item.table_sel = (at, rect[1], at, rect[3])
        self._after_table_change(item, shape, safe_tr("已插入行"))

    def table_insert_col(self, left: bool) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        at = rect[1] if left else rect[3] + 1
        old_total = sum(shape.tbl["cols"])
        table_ops.insert_col(shape.tbl, at)
        # The table keeps its width, like PowerPoint shrinking the other columns
        scale = old_total / sum(shape.tbl["cols"])
        shape.tbl["cols"] = [c * scale for c in shape.tbl["cols"]]
        item.table_sel = (rect[0], at, rect[2], at)
        self._after_table_change(item, shape, safe_tr("已插入列"))

    def table_delete_rows(self) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        if not table_ops.delete_rows(shape.tbl, rect[0], rect[2]):
            self._delete_whole_table(item, shape)
            return
        r = min(rect[0], table_ops.dims(shape.tbl)[0] - 1)
        item.table_sel = table_ops.span_of(shape.tbl, r, rect[1])
        self._after_table_change(item, shape, safe_tr("已删除行"))

    def table_delete_cols(self) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        old_total = sum(shape.tbl["cols"])
        if not table_ops.delete_cols(shape.tbl, rect[1], rect[3]):
            self._delete_whole_table(item, shape)
            return
        scale = old_total / sum(shape.tbl["cols"])
        shape.tbl["cols"] = [c * scale for c in shape.tbl["cols"]]
        c = min(rect[1], table_ops.dims(shape.tbl)[1] - 1)
        item.table_sel = table_ops.span_of(shape.tbl, rect[0], c)
        self._after_table_change(item, shape, safe_tr("已删除列"))

    def _delete_whole_table(self, item: Any, shape: Any) -> None:
        """Deleting every row/column removes the table (PowerPoint behaviour, confirmed)."""
        res = QMessageBox.question(
            self.w,
            safe_tr("删除"),
            safe_tr("这将删除整个表格。是否继续？"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if res != QMessageBox.StandardButton.Yes:
            return
        slide = self.ws.current_slide
        if shape in slide.shapes:
            slide.shapes.remove(shape)
        self.refresh([], safe_tr("已删除表格"))

    def table_distribute(self, rows: bool) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        if rows:
            table_ops.distribute_rows(shape.tbl, rect[0], rect[2])
            msg = safe_tr("已平均分布各行")
        else:
            table_ops.distribute_cols(shape.tbl, rect[1], rect[3])
            msg = safe_tr("已平均分布各列")
        self._after_table_change(item, shape, msg)

    def table_border(self, mode: str) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        table_ops.apply_borders(shape.tbl, rect, mode, None if mode == "none" else self.table_pen)
        self._after_table_change(item, shape, safe_tr("已应用边框"))

    def table_shading(self, color: str | None) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        table_ops.apply_shading(shape.tbl, rect, color)
        self._after_table_change(item, shape, safe_tr("已设置填充颜色"))

    def table_valign(self, valign: str) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        self._commit_cell_editor(item)
        table_ops.apply_valign(shape.tbl, rect, valign)
        self._after_table_change(item, shape, safe_tr("已设置单元格对齐方式"))

    def table_select(self) -> None:
        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, _rect = tgt
        n_rows, n_cols = table_ops.dims(shape.tbl)
        item.table_sel = (0, 0, n_rows - 1, n_cols - 1)
        item.update()
        self.w.show_status_message(safe_tr("已选择整个表格"))

    def set_table_pen(self, **changes: Any) -> None:
        self.table_pen.update(changes)
        self.w.show_status_message(safe_tr("已设置边框笔样式，单击边框按钮应用"))

    def table_borders_and_shading(self) -> None:
        """Format Table: outside border colour/weight and fill for the selected cells."""
        from PySide6.QtWidgets import QColorDialog

        tgt = self._table_target()
        if tgt is None:
            return
        item, shape, rect = tgt
        color = QColorDialog.getColor(QColor(self.table_pen["c"]), self.w, safe_tr("边框颜色"))
        if not color.isValid():
            return
        weight, ok = QInputDialog.getDouble(
            self.w,
            safe_tr("边框和填充"),
            safe_tr("边框粗细(磅):"),
            float(self.table_pen["w"]),
            0.25,
            6.0,
            2,
        )
        if not ok:
            return
        self.table_pen.update({"c": color.name().upper(), "w": weight})
        table_ops.apply_borders(shape.tbl, rect, "all", self.table_pen)
        self._after_table_change(item, shape, safe_tr("已应用边框和填充"))

    # ------------------------------------------------------------------ drawing styles
    def _styled(self, fn: Callable[[list[Any], str], int], key: str, done: str) -> None:
        items = self.selected_items()
        if not self._require(bool(items), safe_tr("请先选择图形对象")):
            return
        n = fn([it.model for it in items], key)
        if not self._require(n > 0, safe_tr("箭头样式仅适用于线条和连接符")):
            return
        self._update_items(items, done)

    def apply_dash(self, key: str) -> None:
        self._styled(shape_styles.apply_dash, key, safe_tr("已应用虚线线型"))

    def apply_arrows(self, key: str) -> None:
        self._styled(shape_styles.apply_arrows, key, safe_tr("已应用箭头样式"))

    def apply_shadow(self, key: str) -> None:
        self._styled(shape_styles.apply_shadow, key, safe_tr("已应用阴影样式"))

    def picture_weight(self, points: float) -> None:
        items = [it for it in self.selected_items() if it.model.type == "image"]
        if not self._require(bool(items), safe_tr("请先选择一张图片")):
            return
        shape_styles.apply_line_weight([it.model for it in items], points)
        self._update_items(items, safe_tr("已设置图片线型"))

    # ------------------------------------------------------------------ pictures
    def set_transparent_color(self) -> None:
        """Picture toolbar > Set Transparent Color: click the colour to make transparent."""
        items = [it for it in self.selected_items() if it.model.type == "image"]
        if not self._require(bool(items), safe_tr("请先选择一张图片")):
            return
        view = getattr(self.ws, "canvas_view", None)
        if view is None:
            return
        if self._pick_filter is not None:
            self._pick_filter.dispose()
        self.w.show_status_message(safe_tr("单击图片中要设为透明的颜色"), 5000)
        self._pick_filter = _PickFilter(view, lambda pos: self._pick_color(items[0], pos))

    def _pick_color(self, item: Any, scene_pos: QPointF) -> bool:
        self._pick_filter = None
        from atboffice.modules.presentation.views.picture_painter import (
            decode_picture_bytes,
            picture_bytes,
            picture_target_rect,
        )

        local = item.mapFromScene(scene_pos)
        shape = item.model
        if not item.boundingRect().contains(local):
            return False
        data = picture_bytes(shape, self.pres)
        img = decode_picture_bytes(data) if data else None
        if img is None:
            return True
        target = picture_target_rect(shape.crop, max(1.0, shape.w), max(1.0, shape.h))
        px = int((local.x() - target.x()) / target.width() * img.width())
        py = int((local.y() - target.y()) / target.height() * img.height())
        if shape.flip_h:
            px = img.width() - 1 - px
        if shape.flip_v:
            py = img.height() - 1 - py
        if not (0 <= px < img.width() and 0 <= py < img.height()):
            return True
        shape.clr_change = QColor(img.pixel(px, py)).name().upper()
        self._update_items([item], safe_tr("已设置透明色"))
        return True

    def format_object(self) -> None:
        from atboffice.modules.presentation.dialogs.format_shape import FormatShapeDialog

        shapes = self.selected_shapes()
        if not self._require(bool(shapes), safe_tr("请先选择要设置格式的对象")):
            return
        dlg = FormatShapeDialog(shapes, parent=self.w)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh([s.id for s in shapes], safe_tr("已设置对象格式"))

    # ------------------------------------------------------------------ WordArt
    def _wordart_items(self) -> list[Any]:
        items = [
            it
            for it in self.selected_items()
            if it.model.type == "wordart" or str(it.model.name).startswith("WordArt")
        ]
        self._require(bool(items), safe_tr("请先选择艺术字"))
        return items

    def _rerender_wordart(self, item: Any) -> None:
        """Re-render a WordArt picture from its stored spec (warp / spacing changes)."""
        from atboffice.modules.common.wordart_gallery import render_wordart_png

        shape = item.model
        spec = getattr(shape, "wordart", None)
        if not spec or not shape.media:
            return
        self.pres.props.setdefault("_media_map", {})[shape.media] = render_wordart_png(spec)
        item._cached_media_key = None

    def wordart_spacing(self, key: str) -> None:
        items = self._wordart_items()
        for it in items:
            it.model.wa_spacing = WORDART_SPACING[key]
            if getattr(it.model, "wordart", None):
                it.model.wordart["spacing"] = WORDART_SPACING[key]
                self._rerender_wordart(it)
        if items:
            self._update_items(items, safe_tr("已设置艺术字字符间距"))

    def wordart_shape(self, key: str) -> None:
        items = self._wordart_items()
        for it in items:
            it.model.wa_shape = WORDART_SHAPES[key]
            if getattr(it.model, "wordart", None):
                it.model.wordart["style"]["warp"] = WORDART_SHAPES[key]
                self._rerender_wordart(it)
        if items:
            self._update_items(items, safe_tr("已设置艺术字形状"))

    def wordart_align(self, align: str) -> None:
        items = self._wordart_items()
        for it in items:
            it.model.wa_align = align
            if it.model.text:
                code = {"left": "l", "center": "ctr", "right": "r", "justify": "just"}[align]
                for p in it.model.text.paragraphs:
                    p.props["algn"] = code
        if items:
            self._update_items(items, safe_tr("已设置艺术字对齐方式"))

    # ------------------------------------------------------------------ diagrams
    def _diagram(self) -> Any | None:
        diag = self.w._get_active_diagram_shape()
        if not self._require(
            diag is not None and bool(getattr(diag, "sa", None)), safe_tr("请先选择一个图示")
        ):
            return None
        return diag

    def _relayout(self, diag: Any, message: str) -> None:
        from atboffice.modules.presentation.smartart.engine import relayout

        relayout(diag, self.pres.get_design_for_slide(self.ws.current_slide))
        self.refresh([diag.id], message)

    def diagram_layout(self, key: str) -> None:
        diag = self._diagram()
        if diag is not None:
            diag.sa["layout"] = DIAGRAM_LAYOUTS[key]
            self._relayout(diag, safe_tr("已更改图示类型"))

    def diagram_colors(self, key: str) -> None:
        diag = self._diagram()
        if diag is not None:
            diag.sa["colors"] = DIAGRAM_COLORS[key]
            self._relayout(diag, safe_tr("已更改图示颜色"))

    def diagram_style(self, key: str) -> None:
        diag = self._diagram()
        if diag is not None:
            diag.sa["style"] = DIAGRAM_STYLES[key]
            self._relayout(diag, safe_tr("已更改图示样式"))

    def insert_diagram(self) -> None:
        import uuid

        from atboffice.modules.presentation.dialogs.diagram_gallery_dialog import (
            DiagramGalleryDialog,
        )
        from atboffice.modules.presentation.models.shape import Shape
        from atboffice.modules.presentation.smartart.engine import SmartArtEngine
        from atboffice.modules.presentation.smartart.palettes import (
            DEFAULT_COLORS,
            DEFAULT_STYLE,
        )

        ws = self.ws
        if ws is None or not ws.presentation.slides:
            return
        dlg = DiagramGalleryDialog(parent=self.w)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        layout_id = dlg.selected_layout()
        items = SmartArtEngine().blank(layout_id)
        pres = self.pres
        w, h = pres.w * 0.6, pres.h * 0.6
        diag = Shape(
            id=f"s_sa_{uuid.uuid4().hex[:8]}",
            type="group",
            name=f"Diagram {len(ws.current_slide.shapes) + 1}",
            x=(pres.w - w) / 2.0,
            y=(pres.h - h) / 2.0,
            w=w,
            h=h,
            sa={
                "layout": layout_id,
                "colors": DEFAULT_COLORS,
                "style": DEFAULT_STYLE,
                "items": [it.to_dict() for it in items],
            },
        )
        ws.current_slide.shapes.append(diag)
        self._relayout(diag, safe_tr("已插入图示"))
        self.w.show_smartart_pane(diag)

    # ------------------------------------------------------------------ text commands
    def open_find(self, replace: bool = False) -> None:
        from atboffice.modules.presentation.tools.text_search import PresentationSearchAdapter
        from atboffice.ui.dialogs.find_replace_dialog import FindReplaceDialog

        ws = self.ws
        if ws is None:
            return
        editor = self.active_editor()
        if editor is not None:
            editor.commit_and_finish()
        if self._find_dialog is None:
            self._find_dialog = FindReplaceDialog(parent=self.w)
        adapter = PresentationSearchAdapter(
            ws.presentation,
            on_focus=self._focus_text,
            on_changed=lambda: self.refresh(message=""),
            start_slide=ws.current_slide_index,
        )
        self._find_dialog.controller.set_adapter(adapter)
        if replace:
            self._find_dialog.show_replace()
        else:
            self._find_dialog.show_find()

    def _focus_text(self, ref: Any, start: int, end: int) -> None:
        ws = self.ws
        if ws is None:
            return
        if ws.view_mode != "normal":
            self.w.set_view_mode("normal")
        if ws.current_slide_index != ref.slide_idx:
            ws.set_current_slide_index(ref.slide_idx)
        sc = self.scene
        sc.clearSelection()
        if ref.owner[0] == "notes":
            self.w.show_status_message(
                safe_tr("在幻灯片 {0} 的备注中找到").format(ref.slide_idx + 1), 3000
            )
            return
        target = ref.shape.id if ref.shape is not None else ref.owner[1]
        item = sc.get_shape_item(target)
        if item is None and ref.owner[0] == "shape":
            item = sc.get_shape_item(ref.owner[1])
        if item is not None:
            item.setSelected(True)
            if ref.owner[0] == "cell":
                item.table_sel = (ref.owner[2], ref.owner[3], ref.owner[2], ref.owner[3])
                item.update()

    def check_spelling(self) -> None:
        from atboffice.modules.presentation.tools.spelling import PresentationSpellChecker
        from atboffice.modules.spreadsheet.dialogs.sheet_spelling_dialog import (
            SheetSpellingDialog,
        )
        from atboffice.modules.writer.spell import SpellEngine

        ws = self.ws
        if ws is None:
            return
        editor = self.active_editor()
        if editor is not None:
            editor.commit_and_finish()
        checker = PresentationSpellChecker(
            ws.presentation, SpellEngine.get_instance(), ws.current_slide_index
        )
        dlg = SheetSpellingDialog(checker, parent=self.w)
        dlg.finished_message = safe_tr("拼写检查已完成。")
        if not dlg.start():
            QMessageBox.information(self.w, safe_tr("拼写检查"), dlg.finished_message)
            return
        dlg.exec()
        if checker.changed:
            self.refresh(message=safe_tr("拼写检查已完成"))

    def insert_symbol(self) -> None:
        from atboffice.modules.writer.dialogs.reference_dialogs import SymbolDialog

        editor = self.active_editor()
        if not self._require(editor is not None, safe_tr("请先在文本框中定位插入点")):
            return
        dlg = SymbolDialog(parent=self.w)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        char = dlg.get_selected_character()
        if char:
            editor.textCursor().insertText(char)
            editor.setFocus()
            self.w.set_modified(True)

    def open_hyperlink(self) -> None:
        from atboffice.modules.writer.dialogs.reference_dialogs import HyperlinkDialog

        items = self.selected_items()
        if not self._require(bool(items), safe_tr("请先选择要添加超链接的对象")):
            return
        shape = items[0].model
        link = dict(shape.link or {})
        editor = self.active_editor()
        text = editor.textCursor().selectedText() if editor is not None else ""
        dlg = HyperlinkDialog(
            initial_text=text, initial_address=str(link.get("url", "")), parent=self.w
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_hyperlink_data()
        target = str(data.get("target") or data.get("address") or "").strip()
        if not target:
            shape.link = {k: v for k, v in link.items() if k not in ("url", "tooltip", "kind")}
            shape.link = shape.link or None
            self._update_items([items[0]], safe_tr("已删除超链接"))
            return
        link.update(
            {
                "url": target,
                "kind": data.get("kind", "external"),
                "tooltip": data.get("screentip") or dlg.screentip,
            }
        )
        shape.link = link
        self._update_items([items[0]], safe_tr("已插入超链接"))

    def apply_action_settings(self, settings: dict[str, Any]) -> int:
        n = 0
        for it in self.selected_items():
            link = dict(it.model.link or {})
            link["actions"] = copy.deepcopy(settings)
            it.model.link = link
            n += 1
        return n

    def _text_shapes(self) -> list[Any]:
        """Selected shapes with text, committing an active in-place editor first."""
        editor = self.active_editor()
        if editor is not None:
            editor.commit_and_finish()
        return [it for it in self.selected_items() if it.model.text is not None]

    def format_font(self) -> None:
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QFontDialog

        editor = self.active_editor()
        items = [] if editor is not None else self._text_shapes()
        if not self._require(editor is not None or bool(items), safe_tr("请先选择文字")):
            return
        current = QFont("Arial", 18)
        if editor is not None:
            current = editor.textCursor().charFormat().font()
        else:
            run = self._first_run_format(items[0].model) or {}
            current = QFont(run.get("font") or "Arial", int(run.get("size") or 18))
            current.setBold(bool(run.get("bold")))
            current.setItalic(bool(run.get("italic")))
            current.setUnderline(bool(run.get("underline")))
        font, ok = QFontDialog.getFont(current, self.w, safe_tr("字体"))
        if not ok:
            return
        if editor is not None:
            editor.set_font_family(font.family())
            editor.set_font_size(float(font.pointSizeF() if font.pointSizeF() > 0 else 18))
            editor.set_bold(font.bold())
            editor.set_italic(font.italic())
            editor.set_underline(font.underline())
            self.w.set_modified(True)
            return
        for it in items:
            for para in it.model.text.paragraphs:
                for run in para.runs:
                    run.font = font.family()
                    run.size = float(font.pointSizeF() if font.pointSizeF() > 0 else 18)
                    run.bold, run.italic = font.bold(), font.italic()
                    run.underline = font.underline()
        self._update_items(items, safe_tr("已设置字体"))

    def line_spacing(self) -> None:
        """Format > Line Spacing (lines) for the selected text boxes."""
        items = self._text_shapes()
        if not self._require(bool(items), safe_tr("请先选择文本框")):
            return
        first = items[0].model.text.paragraphs[:1]
        ln = (first[0].props.get("lnSpc") or {}) if first else {}
        current = float(ln.get("pct", 100.0)) / 100.0 if isinstance(ln, dict) else 1.0
        value, ok = QInputDialog.getDouble(
            self.w, safe_tr("行距"), safe_tr("行距(行):"), current, 0.5, 9.99, 2
        )
        if not ok:
            return
        for it in items:
            for para in it.model.text.paragraphs:
                para.props["lnSpc"] = {"pct": round(value * 100.0, 2)}
        self._update_items(items, safe_tr("已设置行距"))

    def set_language(self) -> None:
        labels = [safe_tr(name) for name, _ in LANGUAGES]
        choice, ok = QInputDialog.getItem(
            self.w, safe_tr("语言"), safe_tr("将所选文字标记为(&M):"), labels, 0, False
        )
        if not ok:
            return
        code = LANGUAGES[labels.index(choice)][1]
        self.pres.props["proofing_lang"] = code
        self.w.set_modified(True)
        self.w.show_status_message(safe_tr("校对语言已设置为 {0}").format(choice))

    def move_paragraph(self, direction: int) -> None:
        from atboffice.modules.presentation.tools.outline_ops import move_paragraph

        editor = self.active_editor()
        if not self._require(editor is not None, safe_tr("请先将光标置于要移动的段落中")):
            return
        block = editor.textCursor().blockNumber()
        body = editor.to_text_body()
        new_idx = move_paragraph(body, block, direction)
        if new_idx is None:
            return
        editor.load_from_text_body(body)
        cursor = editor.textCursor()
        cursor.setPosition(editor.document().findBlockByNumber(new_idx).position())
        editor.setTextCursor(cursor)
        self.w.set_modified(True)

    # ------------------------------------------------------------------ slides / outline
    def create_summary_slide(self) -> None:
        from atboffice.modules.presentation.tools.outline_ops import build_summary_slide

        ws = self.ws
        if ws is None or not ws.presentation.slides:
            return
        indices: list[int] = []
        sorter = getattr(ws, "sorter_view", None)
        if ws.view_mode == "sorter" and sorter is not None:
            indices = sorted(sorter.get_selected_indices())
        if not indices:
            indices = list(range(len(ws.presentation.slides)))
        result = build_summary_slide(ws.presentation, indices, safe_tr("摘要幻灯片"))
        if not self._require(result is not None, safe_tr("所选幻灯片均没有标题，无法生成摘要")):
            return
        _slide, idx = result
        ws._refresh_thumbnails()
        if hasattr(ws, "outline_editor"):
            ws.outline_editor.reload(ws.presentation)
        ws.set_current_slide_index(idx)
        self.w.set_modified(True)
        self.w.show_status_message(safe_tr("已生成摘要幻灯片"))

    def edit_speaker_notes(self) -> None:
        ws = self.ws
        if ws is None or not ws.presentation.slides:
            return
        slide = ws.current_slide
        text, ok = QInputDialog.getMultiLineText(
            self.w,
            safe_tr("演讲者备注"),
            safe_tr("幻灯片 {0} 的备注:").format(ws.current_slide_index + 1),
            slide.notes or "",
        )
        if ok and text != (slide.notes or ""):
            slide.notes = text
            ws.notes_pane.set_plain_text(text, emit_signal=False)
            self.w.set_modified(True)

    def expand_all_outline(self) -> None:
        ws = self.ws
        if ws is None:
            return
        tabs = getattr(ws, "left_pane", None)
        editor = getattr(ws, "outline_editor", None)
        if tabs is not None and editor is not None:
            widget = editor
            while widget is not None and tabs.indexOf(widget) < 0:
                widget = widget.parentWidget()
            if widget is not None:
                tabs.setCurrentWidget(widget)
        if editor is not None:
            editor.reload(ws.presentation)
        self.w.show_status_message(safe_tr("已全部展开大纲"))

    def toggle_show_formatting(self) -> None:
        from PySide6.QtGui import QFont

        ws = self.ws
        editor = getattr(ws, "outline_editor", None) if ws is not None else None
        if editor is None:
            return
        editor.show_formatting = not getattr(editor, "show_formatting", True)
        font = QFont(editor.font())
        if editor.show_formatting:
            font.setFamily(self.pres.get_design_for_slide(None).fonts.get("major", "Arial"))
            font.setPointSize(11)
        else:
            font.setFamily("Courier New")
            font.setPointSize(10)
        editor.setFont(font)
        act = self.w.action_registry.get_action("showFormatting")
        if act is not None and act.isCheckable():
            act.setChecked(editor.show_formatting)

    def toggle_ruler(self) -> None:
        view = getattr(self.ws, "canvas_view", None)
        if view is None:
            return
        view.set_rulers_visible(not view.show_rulers)
        act = self.w.action_registry.get_action("view_ruler")
        if act is not None:
            act.setCheckable(True)
            act.setChecked(view.show_rulers)

    def header_footer(self) -> None:
        from atboffice.modules.presentation.dialogs.header_footer import HeaderFooterDialog

        ws = self.ws
        if ws is None:
            return
        dlg = HeaderFooterDialog(ws.presentation, ws.current_slide_index, parent=self.w)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh(message=safe_tr("已更新页眉和页脚"))

    def open_transition_pane(self) -> None:
        dock = self.w.task_pane_dock
        ws = self.ws
        if dock is None or ws is None:
            return
        if dock.get_pane("transition") is None:
            dock.register_pane("transition", safe_tr("幻灯片切换"), ws.transition_pane)
        if ws.presentation.slides:
            ws.transition_pane.set_slide(ws.current_slide)
        dock.show()
        dock.show_pane("transition")

    def open_custom_animation_pane(self) -> None:
        dock = self.w.task_pane_dock
        ws = self.ws
        if dock is None or ws is None:
            return
        if dock.get_pane("customAnim") is None:
            dock.register_pane("customAnim", safe_tr("自定义动画"), ws.animation_pane)
        if ws.presentation.slides:
            ws.animation_pane.set_slide(ws.current_slide, [s.id for s in self.selected_shapes()])
        dock.show()
        dock.show_pane("customAnim")

    def play_slide_animation(self) -> None:
        """Animation Schemes > Play: preview the current slide's animations on the canvas."""
        ws = self.ws
        if ws is None or not ws.presentation.slides:
            return
        if not ws.preview_animations():
            ws.preview_transition()  # schemes without builds still show their transition

    # ------------------------------------------------------------------ masters
    def _master_view(self) -> Any | None:
        ws = self.ws
        if ws is None:
            return None
        if ws.view_mode != "master":
            self.w.set_view_mode("master")
        return ws.master_view

    def insert_slide_master(self) -> None:
        from atboffice.modules.presentation.models.designs import build_design

        mv = self._master_view()
        if mv is None:
            return
        pres = self.pres
        base = pres.get_design_for_slide(self.ws.current_slide if pres.slides else None)
        new = build_design(getattr(base, "key", "default") or "default", pres.w, pres.h)
        n = len(pres.designs) + 1
        while f"design_{n}" in pres.designs:
            n += 1
        new.id = f"design_{n}"
        new.name = safe_tr("自定义设计 {0}").format(n)
        pres.designs[new.id] = new
        self.w.set_modified(True)
        mv.refresh_master_list()
        self.w.show_status_message(safe_tr("已插入新幻灯片母版"))

    def insert_title_master(self) -> None:
        mv = self._master_view()
        if mv is not None:
            mv.insert_title_master()
            self.w.set_modified(True)
            self.w.show_status_message(safe_tr("已插入标题母版"))

    def delete_title_master(self) -> None:
        mv = self._master_view()
        if mv is None:
            return
        design = self.pres.get_design_for_slide(None)
        if not self._require(
            design.title_decorations is not None or design.title_bg is not None,
            safe_tr("当前设计没有独立的标题母版"),
        ):
            return
        mv.delete_title_master()
        self.w.set_modified(True)
        self.w.show_status_message(safe_tr("已删除标题母版"))

    def preserve_master(self) -> None:
        design = self.pres.get_design_for_slide(None)
        kept = set(self.pres.props.get("preserved_masters", []))
        if design.id in kept:
            kept.discard(design.id)
            msg = safe_tr("已取消保留母版")
        else:
            kept.add(design.id)
            msg = safe_tr("已保留母版（未使用时也不会被删除）")
        self.pres.props["preserved_masters"] = sorted(kept)
        act = self.w.action_registry.get_action("preserveMaster")
        if act is not None:
            act.setCheckable(True)
            act.setChecked(design.id in kept)
        self.w.set_modified(True)
        self.w.show_status_message(msg)

    def rename_master(self) -> None:
        design = self.pres.get_design_for_slide(None)
        name, ok = QInputDialog.getText(
            self.w, safe_tr("重命名母版"), safe_tr("母版名称(&M):"), text=design.name
        )
        name = name.strip()
        if ok and name and name != design.name:
            design.name = name
            self.w.set_modified(True)
            self.w.show_status_message(safe_tr("母版已重命名为 {0}").format(name))

    # ------------------------------------------------------------------ format painter
    def toggle_format_painter(self) -> None:
        items = self.selected_items()
        act = self.w.action_registry.get_action("formatPainter")
        if self._painter_source is not None or not items:
            self._painter_source = None
            if act is not None:
                act.setChecked(False)
            if not items:
                self.w.show_status_message(safe_tr("请先选择要复制格式的对象"), 3000)
            return
        src = items[0].model
        self._painter_source = {
            "fill": copy.deepcopy(src.fill),
            "line": copy.deepcopy(src.line),
            "shadow": copy.deepcopy(src.shadow),
            "run": self._first_run_format(src),
        }
        if act is not None:
            act.setCheckable(True)
            act.setChecked(True)
        view = getattr(self.ws, "canvas_view", None)
        if view is not None:
            if self._pick_filter is not None:
                self._pick_filter.dispose()
            self._pick_filter = _PickFilter(view, self._paint_format_at)
        self.w.show_status_message(safe_tr("格式刷：单击要应用格式的对象"), 5000)

    @staticmethod
    def _first_run_format(shape: Any) -> dict[str, Any] | None:
        text = getattr(shape, "text", None)
        for p in getattr(text, "paragraphs", []) or []:
            for r in p.runs:
                return {
                    k: getattr(r, k)
                    for k in ("font", "size", "color", "bold", "italic", "underline")
                }
        return None

    def _paint_format_at(self, scene_pos: QPointF) -> bool:
        self._pick_filter = None
        fmt, self._painter_source = self._painter_source, None
        act = self.w.action_registry.get_action("formatPainter")
        if act is not None:
            act.setChecked(False)
        sc = self.scene
        if fmt is None or sc is None:
            return False
        target = None
        for it in sc.items(scene_pos):
            if getattr(it, "model", None) is not None and hasattr(it, "is_editing_text"):
                target = it
                break
        if target is None:
            return False
        shape = target.model
        shape.fill = copy.deepcopy(fmt["fill"])
        shape.line = copy.deepcopy(fmt["line"])
        shape.shadow = copy.deepcopy(fmt["shadow"])
        run_fmt = fmt["run"]
        if run_fmt and shape.text:
            for p in shape.text.paragraphs:
                for r in p.runs:
                    for key, val in run_fmt.items():
                        setattr(r, key, val)
        sc.clearSelection()
        target.setSelected(True)
        self._update_items([target], safe_tr("已应用格式"))
        return True

    # ------------------------------------------------------------------ binding
    def bind(self) -> None:
        reg = self.w.action_registry
        w = self.w
        handlers: dict[str, Callable[[], Any]] = {
            # Edit / View / Insert / Format / Tools menus
            "find": self.open_find,
            "edit_find": self.open_find,
            "replace": lambda: self.open_find(replace=True),
            "edit_replace": lambda: self.open_find(replace=True),
            "view_normal": lambda: w.set_view_mode("normal"),
            "view_ruler": self.toggle_ruler,
            "headerFooter": self.header_footer,
            "insert_page_number": self.header_footer,
            "insert_date_time": self.header_footer,
            "insert_symbol": self.insert_symbol,
            "insert_shape": lambda: w.set_drawing_tool({"kind": "shape", "geom": "rect"}),
            "format_font": self.format_font,
            "format_paragraph": self.line_spacing,
            "tools_language": self.set_language,
            "slideshow_rehearse": w.start_rehearse,
            "slideshow_transition": self.open_transition_pane,
            "transitionPane": self.open_transition_pane,
            "customAnimation": self.open_custom_animation_pane,
            # Former toast-only stubs
            "formatPainter": self.toggle_format_painter,
            "hyperlink": self.open_hyperlink,
            "insert_hyperlink": self.open_hyperlink,
            "expandAll": self.expand_all_outline,
            "showFormatting": self.toggle_show_formatting,
            "outline_showFormatting": self.toggle_show_formatting,
            "spelling": self.check_spelling,
            "tools_spelling": self.check_spelling,
            "research": lambda: w.open_research(),
            "tools_research": lambda: w.open_research(),
            "thesaurus": lambda: w.open_research("thesaurus"),
            "help": w.show_help,
            "help_contents": w.show_help,
            "summarySlide": self.create_summary_slide,
            "outline_summarySlide": self.create_summary_slide,
            "speakerNotes": self.edit_speaker_notes,
            "moveParaUp": lambda: self.move_paragraph(-1),
            "moveParaDown": lambda: self.move_paragraph(1),
            "insertSlideMaster": self.insert_slide_master,
            "insertTitleMaster": self.insert_title_master,
            "deleteTitleMaster": self.delete_title_master,
            "preserveMaster": self.preserve_master,
            "renameMaster": self.rename_master,
            "formatObject": self.format_object,
            "wa_format": self.format_object,
            "picTransparent": self.set_transparent_color,
            "insertClipArt": w.open_clipart_dialog,
            # Draw menu: shape alignment (distinct from paragraph alignment)
            "draw_align_left": lambda: w._align_shapes("L"),
            "draw_align_center": lambda: w._align_shapes("C"),
            "draw_align_right": lambda: w._align_shapes("R"),
            "draw_insertDiagram": self.insert_diagram,
            "insertDiagram": self.insert_diagram,
            # Tables and Borders toolbar
            "tableMergeCells": self.table_merge,
            "tableSplitCell": self.table_split,
            "cellTop": lambda: self.table_valign("top"),
            "cellMiddle": lambda: self.table_valign("middle"),
            "cellBottom": lambda: self.table_valign("bottom"),
            "distRows": lambda: self.table_distribute(True),
            "distCols": lambda: self.table_distribute(False),
            "tbl_insert_col_left": lambda: self.table_insert_col(True),
            "tbl_insert_col_right": lambda: self.table_insert_col(False),
            "tbl_insert_row_above": lambda: self.table_insert_row(True),
            "tbl_insert_row_below": lambda: self.table_insert_row(False),
            "tbl_delete_col": self.table_delete_cols,
            "tbl_delete_row": self.table_delete_rows,
            "tbl_select_table": self.table_select,
            "tbl_borders_and_shading": self.table_borders_and_shading,
            "tableBordersAll": lambda: self.table_border("all"),
        }
        for mode in ("all", "outside", "inside", "none", "top", "bottom", "left", "right"):
            handlers[f"tbl_border_{mode}"] = lambda m=mode: self.table_border(m)
        for key, dash in TABLE_DASHES.items():
            handlers[f"tbl_line_{key}"] = lambda d=dash: self.set_table_pen(dash=d)
        for key, pts in TABLE_WEIGHTS.items():
            handlers[f"tbl_weight_{key}"] = lambda p=pts: self.set_table_pen(w=p)
        for key, color in TABLE_COLORS.items():
            handlers[f"tbl_color_{key}"] = lambda c=color: self.set_table_pen(c=c)
        for key, color in TABLE_SHADES.items():
            handlers[f"tbl_shade_{key}"] = lambda c=color: self.table_shading(c)
        for key, pts in PICTURE_WEIGHTS.items():
            handlers[f"pic_weight_{key}"] = lambda p=pts: self.picture_weight(p)
        for key in shape_styles.DASH_STYLES:
            handlers[f"draw_dash_{key}"] = lambda k=key: self.apply_dash(k)
        for key in shape_styles.ARROW_STYLES:
            handlers[f"draw_arrow_{key}"] = lambda k=key: self.apply_arrows(k)
        for key in shape_styles.SHADOW_STYLES:
            handlers[f"draw_shadow_{key}"] = lambda k=key: self.apply_shadow(k)
        for key in WORDART_SHAPES:
            handlers[f"wa_shape_{key}"] = lambda k=key: self.wordart_shape(k)
        for key in WORDART_SPACING:
            handlers[f"wa_spacing_{key}"] = lambda k=key: self.wordart_spacing(k)
        for align in ("left", "center", "right", "justify"):
            handlers[f"wa_align_{align}"] = lambda a=align: self.wordart_align(a)
        for key in DIAGRAM_LAYOUTS:
            handlers[f"diag_layout_{key}"] = lambda k=key: self.diagram_layout(k)
        for key in DIAGRAM_COLORS:
            handlers[f"diag_color_{key}"] = lambda k=key: self.diagram_colors(k)
        for key in DIAGRAM_STYLES:
            handlers[f"diag_style_{key}"] = lambda k=key: self.diagram_style(k)

        for aid, handler in handlers.items():
            reg.set_handler(aid, handler)
        for aid in CONTAINER_COMMANDS:
            reg.register_whitelist_action(aid, kind="setMenu", reason="drop-down menu button")
        for aid in PLACEHOLDER_COMMANDS:
            reg.register_whitelist_action(aid, kind="abstract", reason="empty-history placeholder")
            reg.set_enabled(aid, False)
        spec = reg.get_spec("slideshow_record")
        if spec is not None:
            spec.disabled_reason = RECORD_REASON
            reg.register_whitelist_action(
                "slideshow_record", kind="abstract", reason="narration recording"
            )
            reg.set_enabled("slideshow_record", False)


def bind_lectern_commands(window: LecternWindow) -> LecternCommands:
    commands = LecternCommands(window)
    commands.bind()
    return commands
