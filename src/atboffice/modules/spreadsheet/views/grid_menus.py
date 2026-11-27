"""Context menus of the spreadsheet grid."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QPoint,
)
from PySide6.QtGui import (
    QContextMenuEvent,
)
from PySide6.QtWidgets import (
    QMenu,
)

from atboffice.core.i18n import safe_tr

if TYPE_CHECKING:
    pass
from atboffice.modules.spreadsheet.views.grid_types import (
    HitResult,
    HitZone,
)


class GridMenuMixin:
    """Builds the cell, header and object context menus."""

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Right-click context menu dispatcher."""
        if self._swallow_secondary_button:
            self._swallow_secondary_button = False
            event.accept()
            return

        # If in-cell editor is active and cannot commit, don't open context menu
        if self.editor_controller is not None and self.editor_controller.is_active:
            if not self.editor_controller.commit():
                event.accept()
                return

        self.open_context_menu(
            global_pos=event.globalPos(),
            pos=event.pos(),
            reason=event.reason(),
        )

    def open_context_menu(
        self,
        global_pos: QPoint | None = None,
        pos: QPoint | None = None,
        reason: QContextMenuEvent.Reason = QContextMenuEvent.Reason.Mouse,
    ) -> None:
        """Open context menu according to hit target (object, header, cell) and reason."""
        # 1. Object menu if object selected
        if (
            self.object_layer is not None
            and getattr(self.object_layer, "selected_object", None) is not None
        ):
            menu = self._build_object_menu(self.object_layer.selected_object)
            if global_pos is None:
                global_pos = self.viewport().mapToGlobal(QPoint(100, 100))
            menu.exec(global_pos)
            return

        # 2. Keyboard trigger (Shift+F10)
        if reason == QContextMenuEvent.Reason.Keyboard or pos is None:
            ar, ac = self.selection.active_cell
            c_rect = self.cell_rect(ar, ac)
            global_pos = self._global_pos(c_rect.center())
            hit = HitResult(HitZone.CELL, row=ar, col=ac)
        else:
            hit = self.hit_test(*self.map_from_device(pos.x(), pos.y()))

        # 3. Build appropriate menu based on hit target and selection
        pr = self.selection.primary_range
        is_whole_cols = pr.min_r == 0 and pr.max_r == self.selection.max_rows - 1
        is_whole_rows = pr.min_c == 0 and pr.max_c == self.selection.max_cols - 1

        if hit.zone == HitZone.COL_HEADER or (
            is_whole_cols and hit.zone != HitZone.ROW_HEADER and hit.zone != HitZone.CELL
        ):
            col = hit.col if hit.col is not None else pr.min_c
            menu = self._build_col_header_menu(col)
        elif hit.zone == HitZone.ROW_HEADER or is_whole_rows:
            row = hit.row if hit.row is not None else pr.min_r
            menu = self._build_row_header_menu(row)
        else:
            r = hit.row if hit.row is not None else pr.min_r
            c = hit.col if hit.col is not None else pr.min_c
            menu = self._build_cell_menu(r, c)

        if global_pos is None:
            local_p = pos if pos is not None else QPoint(0, 0)
            global_pos = self.viewport().mapToGlobal(local_p)

        menu.exec(global_pos)

    def _build_col_header_menu(self, col: int) -> QMenu:
        """Build Luna-styled context menu for column headers."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)"))
        act_ins.triggered.connect(self.insert_selected_cols)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.delete_selected_cols)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_cw = menu.addAction(safe_tr("列宽(&C)…"))
        act_cw.triggered.connect(self.set_col_width_dialog)

        act_autofit_col = menu.addAction(safe_tr("最适合的列宽(&A)"))
        act_autofit_col.triggered.connect(self.autofit_selected_cols)

        act_std_cw = menu.addAction(safe_tr("标准列宽(&S)…"))
        act_std_cw.triggered.connect(self.set_standard_col_width_dialog)

        act_hide = menu.addAction(safe_tr("隐藏(&H)"))
        act_hide.setShortcut("Ctrl+0")
        act_hide.triggered.connect(self.hide_selected_cols)

        act_unhide = menu.addAction(safe_tr("取消隐藏(&U)"))
        act_unhide.setShortcut("Ctrl+Shift+)")
        act_unhide.triggered.connect(self.unhide_selected_cols)

        return menu

    def _build_row_header_menu(self, row: int) -> QMenu:
        """Build Luna-styled context menu for row headers."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)"))
        act_ins.triggered.connect(self.insert_selected_rows)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.delete_selected_rows)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_rh = menu.addAction(safe_tr("行高(&R)…"))
        act_rh.triggered.connect(self.set_row_height_dialog)

        act_autofit_row = menu.addAction(safe_tr("最适合的行高(&A)"))
        act_autofit_row.triggered.connect(self.autofit_selected_rows)

        act_hide = menu.addAction(safe_tr("隐藏(&H)"))
        act_hide.setShortcut("Ctrl+9")
        act_hide.triggered.connect(self.hide_selected_rows)

        act_unhide = menu.addAction(safe_tr("取消隐藏(&U)"))
        act_unhide.setShortcut("Ctrl+Shift+(")
        act_unhide.triggered.connect(self.unhide_selected_rows)

        return menu

    def _build_cell_menu(self, r: int, c: int) -> QMenu:
        """Build Luna-styled context menu for worksheet cells."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.setShortcut("Ctrl+X")
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.setShortcut("Ctrl+C")
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.setShortcut("Ctrl+V")
        act_paste.triggered.connect(self.paste)

        act_ps = menu.addAction(safe_tr("选择性粘贴(&S)…"))
        act_ps.triggered.connect(self.paste_special)

        menu.addSeparator()

        act_ins = menu.addAction(safe_tr("插入(&I)…"))
        act_ins.setShortcut("Ctrl+Shift++")
        act_ins.triggered.connect(self.insert_cells_dialog)

        act_del = menu.addAction(safe_tr("删除(&D)…"))
        act_del.setShortcut("Ctrl+-")
        act_del.triggered.connect(self.delete_cells_dialog)

        act_clear = menu.addAction(safe_tr("清除内容(&N)"))
        act_clear.setShortcut("Del")
        act_clear.triggered.connect(self.clear_contents)

        menu.addSeparator()

        # Comment actions
        cm = self.model.get_comment(r, c)
        if cm is not None:
            act_edit_cm = menu.addAction(safe_tr("编辑批注(&M)"))
            act_edit_cm.setShortcut("Shift+F2")
            act_edit_cm.triggered.connect(lambda: self.edit_comment(r, c))

            act_del_cm = menu.addAction(safe_tr("删除批注(&M)"))
            act_del_cm.triggered.connect(lambda: self.delete_comment(r, c))

            act_show_cm = menu.addAction(safe_tr("显示/隐藏批注(&O)"))
            act_show_cm.triggered.connect(lambda: self.toggle_comment_visibility(r, c))
        else:
            act_ins_cm = menu.addAction(safe_tr("插入批注(&M)"))
            act_ins_cm.setShortcut("Shift+F2")
            act_ins_cm.triggered.connect(lambda: self.insert_comment(r, c))

        menu.addSeparator()

        act_fmt = menu.addAction(safe_tr("设置单元格格式(&F)…"))
        act_fmt.setShortcut("Ctrl+1")
        act_fmt.triggered.connect(lambda: self.open_format_cells_dialog())

        act_pick = menu.addAction(safe_tr("从下拉列表中选择(&K)…"))
        act_pick.setShortcut("Alt+Down")
        act_pick.triggered.connect(self.pick_list)

        act_watch = menu.addAction(safe_tr("添加监视(&W)"))
        act_watch.triggered.connect(lambda: self.add_watch(r, c))

        menu.addSeparator()

        # PivotTable conditional branch
        pvt = self.pivot_table_at(r, c)
        if pvt is not None:
            act_refresh_pvt = menu.addAction(safe_tr("刷新数据(&R)"))
            act_refresh_pvt.triggered.connect(lambda: self.refresh_pivot_table(pvt))

            act_show_fields = menu.addAction(safe_tr("显示字段列表(&L)"))
            act_show_fields.triggered.connect(lambda: self.show_pivot_field_list(pvt))

            act_pvt_chart = menu.addAction(safe_tr("插入数据透视图(&C)…"))
            act_pvt_chart.triggered.connect(lambda: self.insert_pivot_chart_for(pvt))

            act_pvt_wizard = menu.addAction(safe_tr("数据透视表向导(&W)…"))
            act_pvt_wizard.triggered.connect(lambda: self.open_pivot_wizard_for(pvt))

            menu.addSeparator()

        # Table / List conditional branch
        tbl = self.table_at(r, c)
        if tbl is not None:
            list_menu = menu.addMenu(safe_tr("列表(&L)"))
            act_tot = list_menu.addAction(safe_tr("汇总行(&T)"))
            act_tot.triggered.connect(lambda: self.toggle_total_row(tbl))
            act_conv = list_menu.addAction(safe_tr("转换为区域(&R)"))
            act_conv.triggered.connect(lambda: self.convert_table_to_range(tbl))
        else:
            act_create_list = menu.addAction(safe_tr("创建列表(&L)…"))
            act_create_list.setShortcut("Ctrl+L")
            act_create_list.triggered.connect(self.create_list)

        menu.addSeparator()

        # Hyperlink actions
        has_link = self._has_hyperlink(r, c)
        if has_link:
            act_edit_hl = menu.addAction(safe_tr("编辑超链接(&H)…"))
            act_edit_hl.triggered.connect(lambda: self.edit_hyperlink(r, c))

            act_open_hl = menu.addAction(safe_tr("打开超链接(&O)"))
            act_open_hl.triggered.connect(lambda: self.open_hyperlink(r, c))

            act_rem_hl = menu.addAction(safe_tr("删除超链接(&R)"))
            act_rem_hl.triggered.connect(lambda: self.remove_hyperlink(r, c))
        else:
            act_ins_hl = menu.addAction(safe_tr("超链接(&I)…"))
            act_ins_hl.setShortcut("Ctrl+K")
            act_ins_hl.triggered.connect(lambda: self.insert_hyperlink(r, c))

        return menu

    def _build_object_menu(self, obj: Any) -> QMenu:
        """Build context menu for floating objects (shapes, pictures, charts)."""
        menu = QMenu(self)
        act_cut = menu.addAction(safe_tr("剪切(&T)"))
        act_cut.triggered.connect(self.cut)

        act_copy = menu.addAction(safe_tr("复制(&C)"))
        act_copy.triggered.connect(self.copy)

        act_paste = menu.addAction(safe_tr("粘贴(&P)"))
        act_paste.triggered.connect(self.paste)

        act_del = menu.addAction(safe_tr("删除(&D)"))
        act_del.triggered.connect(self.clear_contents)

        menu.addSeparator()

        kind = getattr(obj, "kind", None)
        if kind == "chart":
            act_chart_type = menu.addAction(safe_tr("图表类型(&Y)…"))
            act_chart_type.triggered.connect(lambda: self.open_chart_type_dialog(obj))
            act_chart_opts = menu.addAction(safe_tr("图表选项(&O)…"))
            act_chart_opts.triggered.connect(lambda: self.open_chart_options_dialog(obj))
            menu.addSeparator()
        elif kind == "shape":
            act_edit_txt = menu.addAction(safe_tr("编辑文字(&X)"))
            act_edit_txt.triggered.connect(lambda: self.edit_object_text(obj))
            menu.addSeparator()

        order_menu = menu.addMenu(safe_tr("叠放次序(&R)"))
        if self.object_layer is not None:
            order_menu.addAction(
                safe_tr("置于顶层(&T)"),
                lambda: self.object_layer.bring_to_front(obj),
            )
            order_menu.addAction(
                safe_tr("置于底层(&K)"),
                lambda: self.object_layer.send_to_back(obj),
            )
            order_menu.addAction(
                safe_tr("上移一层(&F)"),
                lambda: self.object_layer.bring_forward(obj),
            )
            order_menu.addAction(
                safe_tr("下移一层(&B)"),
                lambda: self.object_layer.send_backward(obj),
            )

        menu.addSeparator()

        fmt_label = safe_tr("设置对象格式(&O)…")
        if kind == "image":
            fmt_label = safe_tr("设置图片格式(&O)…")
        elif kind == "chart":
            fmt_label = safe_tr("设置图表区域格式(&O)…")
        elif kind == "shape" and getattr(obj, "tx_box", False):
            fmt_label = safe_tr("设置文本框格式(&O)…")
        elif kind == "shape":
            fmt_label = safe_tr("设置自选图形格式(&O)…")

        act_fmt = menu.addAction(fmt_label)
        act_fmt.triggered.connect(lambda: self.open_format_object_dialog(obj))

        return menu
