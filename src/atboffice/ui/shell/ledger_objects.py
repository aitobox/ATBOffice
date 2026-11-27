"""Ledger window: charts, drawings, pictures and hyperlinks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
)
from atboffice.modules.spreadsheet.views.object_layer import (
    AnchorType,
    CellAnchorPoint,
    FloatingObject,
)
from atboffice.ui.shell.ledger_common import (
    _cell_edit,
)


class LedgerObjectsMixin:
    """Charts, the Drawing toolbar, text boxes, shapes, pictures and hyperlinks."""

    def _record_drawings_snapshot(
        self, sheet: Any, layer: Any, svc: Any, label: str, before: list[Any]
    ) -> bool:
        """Record an undo/redo step if ``sheet.drawings`` changed relative to ``before``."""
        import copy as _copy

        if sheet is None or svc is None or not svc.is_recording:
            return False
        after = _copy.deepcopy(getattr(sheet, "drawings", []))
        if len(after) == len(before) and repr(after) == repr(before):
            return False

        def _restore(snapshot: list[Any]) -> None:
            sheet.drawings = _copy.deepcopy(snapshot)
            if layer is not None and getattr(layer, "model", None) is sheet:
                layer.set_model(sheet)
            if hasattr(self.spreadsheet_view, "grid"):
                self.spreadsheet_view.grid.viewport().update()

        svc.record(
            safe_tr(label),
            lambda s=before: _restore(s),
            lambda s=after: _restore(s),
        )
        return True

    def _record_drawing_edit(self, label: str, mutate: Any) -> Any:
        """Apply a sheet drawing mutation and record an UndoService snapshot step."""
        import copy as _copy

        sheet = getattr(self.spreadsheet_view, "model", None)
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        svc = self.undo_service() if hasattr(self, "undo_service") else None
        if sheet is None or svc is None or not svc.is_recording:
            res = mutate()
            if layer is not None:
                layer.update()
            return res

        before = _copy.deepcopy(getattr(sheet, "drawings", []))
        with svc.paused():
            res = mutate()
        if self._record_drawings_snapshot(sheet, layer, svc, label, before):
            self.set_modified(True)
        return res

    def set_chart_type(self, chart_type: str) -> None:
        """Set the chart type of the selected chart object or create a new chart."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        sel_obj = getattr(layer, "selected_object", None) if layer else None
        if sel_obj and getattr(sel_obj, "kind", None) == "chart":
            from atboffice.modules.spreadsheet.tools.chart_builder import chart_kind

            def _mutate_chart() -> None:
                setattr(sel_obj, "chart_type", chart_type)
                data = dict(sel_obj.chart_data or {})
                if not data:
                    from atboffice.modules.presentation.chart.model import ChartData

                    data = ChartData.create_sample().to_dict()
                data["kind"] = chart_kind(chart_type)
                sel_obj.chart_data = data
                layer.update()

            self._record_drawing_edit("更改图表类型", _mutate_chart)
        else:
            self.open_chart_wizard(initial_type=chart_type)

    def toggle_drawing_toolbar(self) -> None:
        """Toggle bottom drawing toolbar visibility."""
        tb = self.toolbars.get("drawing")
        if tb:
            cur = self.toolbar_modes.get("drawing", False)
            new_mode = not cur if isinstance(cur, bool) else tb.isHidden()
            self.set_toolbar_mode("drawing", new_mode)

    def _next_object_id_and_z(self) -> tuple[int, int]:
        """Return the next unique drawing id and top z-index for the active sheet."""
        drawings = getattr(getattr(self.spreadsheet_view, "model", None), "drawings", None) or []
        max_id = max((getattr(o, "id", 0) for o in drawings), default=0)
        max_z = max((getattr(o, "z_index", -1) for o in drawings), default=-1)
        return max_id + 1, max_z + 1

    def insert_textbox(self) -> None:
        """Insert floating text box at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj_id, z_idx = self._next_object_id_and_z()
        obj = FloatingObject(
            id=obj_id,
            kind="textbox",
            text="TextBox",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
            z_index=z_idx,
        )

        def _add() -> None:
            self.spreadsheet_view.object_layer.add_object(obj)
            self.spreadsheet_view.object_layer.select_object(obj)

        self._record_drawing_edit("插入文本框", _add)
        self.set_modified(True)

    def insert_shape(self, kind: str = "rect") -> None:
        """Insert floating geometric shape at current selection."""
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        obj_id, z_idx = self._next_object_id_and_z()
        obj = FloatingObject(
            id=obj_id,
            kind=kind,
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + 2, row=r + 3),
            z_index=z_idx,
        )

        def _add() -> None:
            self.spreadsheet_view.object_layer.add_object(obj)
            self.spreadsheet_view.object_layer.select_object(obj)

        self._record_drawing_edit("插入图形", _add)
        self.set_modified(True)

    def chart_wizard(self) -> None:
        """Standard toolbar Chart Wizard button: open the 4-step wizard."""
        self.open_chart_wizard()

    def bring_to_front(self) -> None:
        """Bring selected floating object to top of z-order."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            target = layer.selected_object
            self._record_drawing_edit("置于顶层", lambda: layer.bring_to_front(target))

    def send_to_back(self) -> None:
        """Send selected floating object to bottom of z-order."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            target = layer.selected_object
            self._record_drawing_edit("置于底层", lambda: layer.send_to_back(target))

    def _apply_drawing_fill_color(self, color: str) -> None:
        """Apply fill color to selected floating drawing object."""
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        if layer and hasattr(layer, "selected_object") and layer.selected_object:
            target = layer.selected_object

            def _apply() -> None:
                target.fill_color = color
                if hasattr(target, "fill_type"):
                    target.fill_type = "solid"
                layer.update()

            self._record_drawing_edit("设置填充色", _apply)

    def _on_object_selected(self, obj: Any) -> None:
        """Update contextual toolbars and RB.follow task pane when selection changes."""
        kind = getattr(obj, "kind", None) if obj is not None else None
        is_chart = kind == "chart"
        self.update_context_toolbars({"is_chart": is_chart})
        act_format_obj = self.action_registry.get_action("formatObject")
        if act_format_obj:
            act_format_obj.setEnabled(obj is not None)
        if obj is None:
            ctx_kind = None
        elif is_chart:
            ctx_kind = "chart"
        elif kind in ("image", "picture"):
            ctx_kind = "picture"
        else:
            ctx_kind = "drawing"
        if hasattr(self, "notify_selection_context"):
            self.notify_selection_context(ctx_kind)

    def open_chart_wizard(self, initial_type: str | None = None) -> None:
        """Open Excel 2003 classic Chart Wizard (4 步图表向导) on the current selection."""
        from atboffice.modules.spreadsheet.calc.references import abs_range_name
        from atboffice.modules.spreadsheet.dialogs.chart_wizard import (
            CHART_TYPES,
            ChartWizardDialog,
        )

        sheet = getattr(self.spreadsheet_view, "model", None)
        workbook = getattr(self.spreadsheet_view, "workbook", None)
        r1, c1, r2, c2 = self._get_selected_cell_range()
        if (r1, c1) == (r2, c2) and sheet is not None:
            r1, c1, r2, c2 = self._current_region(sheet, r1, c1)
        rng = abs_range_name({"r1": r1, "c1": c1, "r2": r2, "c2": c2})
        sheet_name = getattr(sheet, "name", "Sheet1")
        quoted = f"'{sheet_name}'" if not sheet_name.isalnum() else sheet_name
        dlg = ChartWizardDialog(
            sheet_model=sheet,
            workbook_model=workbook,
            initial_range=f"={quoted}!{rng}",
            parent=self,
            anchor_cell=(r1, c2 + 2),
        )
        if initial_type:
            row = next((i for i, t in enumerate(CHART_TYPES) if t["id"] == initial_type), -1)
            if row >= 0 and hasattr(dlg, "list_types"):
                dlg.list_types.setCurrentRow(row)
        created: list[object] = []
        dlg.chart_created.connect(lambda obj, _target: created.append(obj))

        import copy as _copy

        svc = self.undo_service() if hasattr(self, "undo_service") else None
        before_drawings = (
            _copy.deepcopy(getattr(sheet, "drawings", [])) if sheet is not None else []
        )
        before_sheet_idx = (
            workbook.sheet_index(sheet) if (workbook is not None and sheet is not None) else 0
        )

        if dlg.exec() != QDialog.DialogCode.Accepted or not created:
            return
        chart_obj = created[0]
        # Keep the legacy attribute that set_chart_type / the chart toolbar read.
        setattr(chart_obj, "chart_type", dlg.selected_type_id)
        layer = getattr(self.spreadsheet_view, "object_layer", None)

        if dlg.created_sheet is not None and workbook is not None:
            created_sheet = dlg.created_sheet
            created_idx = workbook.sheet_index(created_sheet)

            def _switch_to(target_sheet: Any, fallback_idx: int) -> None:
                idx = workbook.sheet_index(target_sheet) if target_sheet is not None else -1
                if idx < 0:
                    idx = max(0, min(fallback_idx, len(workbook) - 1))
                if hasattr(self.spreadsheet_view, "set_active_sheet_index"):
                    self.spreadsheet_view.set_active_sheet_index(idx)
                if layer is not None:
                    layer.set_model(getattr(self.spreadsheet_view, "model", None))
                    layer.update()
                if hasattr(self.spreadsheet_view, "grid"):
                    self.spreadsheet_view.grid.viewport().update()

            def _undo_chart_sheet() -> None:
                cur_idx = workbook.sheet_index(created_sheet)
                if cur_idx >= 0 and len(workbook) > 1:
                    workbook.remove_sheet(cur_idx)
                _switch_to(sheet, before_sheet_idx)
                self.set_toolbar_mode("chart", False)

            def _redo_chart_sheet() -> None:
                if workbook.sheet_index(created_sheet) < 0:
                    target_idx = created_idx if created_idx >= 0 else len(workbook)
                    workbook.add_sheet(
                        name=created_sheet.name, index=target_idx, sheet=created_sheet
                    )
                _switch_to(created_sheet, created_idx)
                if layer is not None:
                    layer.select_object(chart_obj)
                    layer.update()
                self.set_toolbar_mode("chart", True)

            if hasattr(self.spreadsheet_view, "set_active_sheet_index") and created_idx >= 0:
                self.spreadsheet_view.set_active_sheet_index(created_idx)
            if layer is not None:
                layer.set_model(getattr(self.spreadsheet_view, "model", None))
                layer.select_object(chart_obj)
                layer.update()
            self.set_toolbar_mode("chart", True)
            self.set_modified(True)
            if svc is not None and svc.is_recording:
                svc.record(safe_tr("插入图表"), _undo_chart_sheet, _redo_chart_sheet)
        else:
            if layer is not None:
                layer.set_model(getattr(self.spreadsheet_view, "model", None))
                layer.select_object(chart_obj)
                layer.update()
            self.set_toolbar_mode("chart", True)
            self.set_modified(True)
            self._record_drawings_snapshot(sheet, layer, svc, "插入图表", before_drawings)

    def format_selected_object(self) -> None:
        """Format properties of selected chart or floating shape."""
        import copy as _copy

        sheet = getattr(self.spreadsheet_view, "model", None)
        layer = getattr(self.spreadsheet_view, "object_layer", None)
        sel_obj = getattr(layer, "selected_object", None) if layer else None
        if sel_obj is None:
            return
        from atboffice.modules.spreadsheet.dialogs.format_object_dialog import (
            FormatObjectDialog,
        )

        svc = self.undo_service() if hasattr(self, "undo_service") else None
        before = _copy.deepcopy(getattr(sheet, "drawings", [])) if sheet is not None else []
        dlg = FormatObjectDialog(sel_obj, parent=self)
        if dlg.exec():
            self._record_drawings_snapshot(sheet, layer, svc, "设置对象格式", before)
            layer.update()
            self.set_modified(True)

    def insert_picture(self, path: str | None = None) -> None:
        """Insert an image file from disk into the floating object layer."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                safe_tr("插入图片"),
                "",
                safe_tr("图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"),
            )
        if not path:
            return
        try:
            data = Path(path).read_bytes()
        except OSError as exc:
            QMessageBox.warning(
                self, safe_tr("插入图片"), safe_tr("无法读取图片文件：{0}").format(str(exc))
            )
            return
        if not self.insert_image_bytes(data, Path(path).suffix, Path(path).stem):
            QMessageBox.warning(
                self, safe_tr("插入图片"), safe_tr("所选文件不是可识别的图片格式。")
            )

    def insert_image_bytes(self, data: bytes, ext: str = "png", name: str = "") -> bool:
        """Picture adapter (Insert Picture, Clip Art, WordArt): a floating image at the
        active cell, sized from its pixels and capped to a sensible area."""
        from PySide6.QtGui import QImage

        image = QImage()
        if not data or not image.loadFromData(data):
            return False
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "bmp": "image/bmp",
        }.get((ext or "png").lower().lstrip("."), "image/png")
        sel = self.spreadsheet_view.selection
        r, c = sel.active_cell
        model = self.spreadsheet_view.model
        w = min(image.width(), 640)
        h = max(1, round(image.height() * w / max(1, image.width())))
        cols, width_px = 0, 0
        while width_px < w and cols < 60:
            width_px += model.geometry.col_size(c + cols)
            cols += 1
        rows, height_px = 0, 0
        while height_px < h and rows < 200:
            height_px += model.geometry.row_size(r + rows)
            rows += 1
        layer = self.spreadsheet_view.object_layer
        obj_id, z_idx = self._next_object_id_and_z()
        obj = FloatingObject(
            id=obj_id,
            name=name or "Picture",
            kind="image",
            anchor_type=AnchorType.TWO_CELL,
            from_point=CellAnchorPoint(col=c, row=r),
            to_point=CellAnchorPoint(col=c + max(1, cols), row=r + max(1, rows)),
            image_data=data,
            image_mime=mime,
            z_index=z_idx,
            lock_aspect=True,
        )

        def _add_img() -> None:
            layer.add_object(obj)
            layer.select_object(obj)

        self._record_drawing_edit("插入图片", _add_img)
        self.set_modified(True)
        return True

    @_cell_edit("hyperlink")
    def insert_hyperlink(self) -> None:
        """Open insert or edit hyperlink dialog."""
        r1, c1, r2, c2 = self._get_selected_cell_range()
        model = self.spreadsheet_view.model
        cname = cell_name(r1, c1)

        links = getattr(model, "links", [])
        existing_link = None
        for lk in links:
            if isinstance(lk, dict) and (
                lk.get("ref") == cname or (lk.get("r") == r1 and lk.get("c") == c1)
            ):
                existing_link = lk
                break

        is_existing = existing_link is not None
        cur_cell = model.get_cell(r1, c1)
        if cur_cell is None:
            cur_cell = CellData()
        existing_text = str(cur_cell.value) if cur_cell and cur_cell.value is not None else ""
        existing_target = existing_link.get("target", "") if existing_link else ""
        existing_location = existing_link.get("location", "") if existing_link else ""
        existing_tooltip = existing_link.get("tooltip", "") if existing_link else ""

        wb = getattr(self.spreadsheet_view, "workbook", None)
        sheets = (
            [s.name for s in wb.sheets]
            if wb and hasattr(wb, "sheets")
            else [getattr(model, "sheet_name", "Sheet1")]
        )

        from atboffice.modules.spreadsheet.dialogs.hyperlink_dialog import (
            HyperlinkDialog,
        )

        dlg = HyperlinkDialog(
            existing_text=existing_text,
            existing_target=existing_target,
            existing_location=existing_location,
            existing_tooltip=existing_tooltip,
            sheets=sheets,
            is_existing=is_existing,
            cell_ref=cname,
            parent=self,
        )
        if not dlg.exec():
            return

        data = dlg.get_data()
        grid = getattr(self.spreadsheet_view, "grid", None)
        before_cells = {k: v.clone() for k, v in model.cells.items()}
        before_links = [dict(lk) if isinstance(lk, dict) else lk for lk in links]

        if data.get("is_removed"):
            model.links = [
                lk
                for lk in links
                if not (lk.get("ref") == cname or (lk.get("r") == r1 and lk.get("c") == c1))
            ]
            if cur_cell and cur_cell.underline and cur_cell.fg_color == "#0000FF":
                cur_cell.underline = False
                cur_cell.fg_color = None
                model.set_cell(r1, c1, cur_cell)
        else:
            disp = data.get("display", "")
            target = data.get("target", "")
            loc = data.get("location", "")
            tip = data.get("tooltip", "")
            new_links = [
                lk
                for lk in links
                if not (lk.get("ref") == cname or (lk.get("r") == r1 and lk.get("c") == c1))
            ]
            new_links.append(
                {
                    "r": r1,
                    "c": c1,
                    "ref": cname,
                    "target": target,
                    "location": loc,
                    "display": disp,
                    "tooltip": tip,
                }
            )
            model.links = new_links
            if disp:
                cur_cell.value = disp
            cur_cell.underline = True
            cur_cell.fg_color = "#0000FF"
            model.set_cell(r1, c1, cur_cell)

        if grid and hasattr(grid, "_record_entry"):
            grid._record_entry(
                {
                    "action": "hyperlink",
                    "before_cells": before_cells,
                    "after_cells": {k: v.clone() for k, v in model.cells.items()},
                    "before_links": before_links,
                    "after_links": [dict(lk) if isinstance(lk, dict) else lk for lk in model.links],
                    "before_merges": list(model.merges),
                    "after_merges": list(model.merges),
                    "before_sel": grid.selection.snapshot(),
                    "after_sel": grid.selection.snapshot(),
                }
            )

        self.spreadsheet_view.grid.viewport().update()
        self.set_modified(True)
