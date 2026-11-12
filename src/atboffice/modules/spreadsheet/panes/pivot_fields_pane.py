"""Interactive PivotTable Field List task pane for ATBOffice Ledger."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QByteArray, QCoreApplication, QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.pivots import (
    AGG_FUNCTIONS,
    PivotFieldSpec,
    PivotLayoutSpec,
    PivotReport,
    PivotValueSpec,
    extract_source_fields,
    get_unique_field_values,
    refresh_pivot_report,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel

PIVOT_FIELD_MIME = "application/x-atb-pivot-field"

_ROLE_COL_IDX = Qt.ItemDataRole.UserRole + 1
_ROLE_FIELD_NAME = Qt.ItemDataRole.UserRole + 2
_ROLE_AGG_FUNC = Qt.ItemDataRole.UserRole + 3
_ROLE_SELECTED_VALS = Qt.ItemDataRole.UserRole + 4

_AGG_DISPLAY_NAMES: dict[str, str] = {
    "sum": "求和项",
    "count": "计数项",
    "average": "平均值项",
    "max": "最大值项",
    "min": "最小值项",
    "product": "乘积项",
    "countNums": "数值计数项",
}


def safe_tr(text: str) -> str:
    """Translate UI text safely for PivotFieldsTaskPane."""
    return QCoreApplication.translate("PivotFieldsTaskPane", text)


class ValueFieldSettingsDialog(QDialog):
    """Dialog to choose aggregation function for a Values zone field."""

    def __init__(
        self,
        field_name: str,
        current_func: str = "sum",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.field_name = field_name
        self.selected_func = current_func
        self.setWindowTitle(safe_tr("值字段设置"))
        self.resize(280, 260)

        layout = QVBoxLayout(self)
        self.lbl_field = QLabel(f"{safe_tr('源字段')}: {field_name}", self)
        self.lbl_field.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.lbl_field)

        self.lbl_prompt = QLabel(safe_tr("选择计算类型(&S):"), self)
        layout.addWidget(self.lbl_prompt)

        self.func_list = QListWidget(self)
        for fn in AGG_FUNCTIONS:
            lbl = safe_tr(_AGG_DISPLAY_NAMES.get(fn, fn))
            item = QListWidgetItem(f"{lbl} ({fn})")
            item.setData(Qt.ItemDataRole.UserRole, fn)
            self.func_list.addItem(item)
            if fn.lower() == current_func.lower():
                self.func_list.setCurrentItem(item)
        self.func_list.itemDoubleClicked.connect(self._on_accept)
        layout.addWidget(self.func_list)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self) -> None:
        cur = self.func_list.currentItem()
        if cur is not None:
            self.selected_func = cur.data(Qt.ItemDataRole.UserRole) or self.selected_func
        self.accept()


class PivotFieldListWidget(QListWidget):
    """Top list widget showing available fields with checkboxes and drag support."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def mimeTypes(self) -> list[str]:
        return [PIVOT_FIELD_MIME]

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:
        mime = QMimeData()
        if items:
            item = items[0]
            payload = {
                "col_idx": item.data(_ROLE_COL_IDX),
                "name": item.data(_ROLE_FIELD_NAME) or item.text(),
                "source_zone": None,
                "source_index": -1,
                "agg_func": None,
            }
            mime.setData(PIVOT_FIELD_MIME, QByteArray(json.dumps(payload).encode("utf-8")))
        return mime


class PivotDropZoneWidget(QListWidget):
    """Drop-target list widget representing one of the 4 PivotTable field areas."""

    field_dropped = Signal(dict, str, int)  # (payload, target_zone, target_index)
    context_action = Signal(str, str, int)  # (action, zone_id, row_index)

    def __init__(self, zone_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zone_id = zone_id
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMinimumHeight(64)

    def mimeTypes(self) -> list[str]:
        return [PIVOT_FIELD_MIME]

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:
        mime = QMimeData()
        if items:
            item = items[0]
            row = self.row(item)
            payload = {
                "col_idx": item.data(_ROLE_COL_IDX),
                "name": item.data(_ROLE_FIELD_NAME) or item.text(),
                "source_zone": self.zone_id,
                "source_index": row,
                "agg_func": item.data(_ROLE_AGG_FUNC),
            }
            mime.setData(PIVOT_FIELD_MIME, QByteArray(json.dumps(payload).encode("utf-8")))
        return mime

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(PIVOT_FIELD_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(PIVOT_FIELD_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasFormat(PIVOT_FIELD_MIME):
            super().dropEvent(event)
            return

        raw = bytes(event.mimeData().data(PIVOT_FIELD_MIME)).decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            event.ignore()
            return

        pos = event.position().toPoint()
        idx = self.indexAt(pos)
        target_index = idx.row() if idx.isValid() else self.count()

        event.acceptProposedAction()
        self.field_dropped.emit(payload, self.zone_id, target_index)

    def contextMenuEvent(self, event: Any) -> None:
        item = self.itemAt(event.pos())
        if item is None:
            return
        row = self.row(item)
        menu = QMenu(self)

        if self.zone_id == "values":
            act_cfg = menu.addAction(safe_tr("值字段设置(&S)…"))
            act_cfg.triggered.connect(
                lambda: self.context_action.emit("settings", self.zone_id, row)
            )

            agg_sub = menu.addMenu(safe_tr("汇总方式(&A)"))
            for fn in AGG_FUNCTIONS:
                lbl = f"{safe_tr(_AGG_DISPLAY_NAMES.get(fn, fn))} ({fn})"
                act_fn = agg_sub.addAction(lbl)
                act_fn.triggered.connect(
                    lambda _checked=False, f=fn: self.context_action.emit(
                        f"agg:{f}", self.zone_id, row
                    )
                )
            menu.addSeparator()
        elif self.zone_id == "filters":
            act_flt = menu.addAction(safe_tr("选择筛选值(&F)…"))
            act_flt.triggered.connect(
                lambda: self.context_action.emit("filter_values", self.zone_id, row)
            )
            menu.addSeparator()

        move_targets = [
            ("filters", safe_tr("移至报表筛选")),
            ("columns", safe_tr("移至列标签")),
            ("rows", safe_tr("移至行标签")),
            ("values", safe_tr("移至数值")),
        ]
        for target_id, label in move_targets:
            if target_id != self.zone_id:
                act_mv = menu.addAction(label)
                act_mv.triggered.connect(
                    lambda _checked=False, tid=target_id: self.context_action.emit(
                        f"move:{tid}", self.zone_id, row
                    )
                )

        menu.addSeparator()
        if row > 0:
            act_up = menu.addAction(safe_tr("上移(&U)"))
            act_up.triggered.connect(lambda: self.context_action.emit("up", self.zone_id, row))
        if row < self.count() - 1:
            act_dn = menu.addAction(safe_tr("下移(&D)"))
            act_dn.triggered.connect(lambda: self.context_action.emit("down", self.zone_id, row))

        act_rem = menu.addAction(safe_tr("删除字段(&R)"))
        act_rem.triggered.connect(lambda: self.context_action.emit("remove", self.zone_id, row))
        menu.exec(event.globalPos())


class PivotFieldsTaskPane(QWidget):
    """Excel classic PivotTable Field List dockable task pane."""

    layout_changed = Signal(object)  # PivotLayoutSpec
    report_refreshed = Signal(object)  # PivotReport

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self._report: PivotReport | None = None
        self._fields: list[tuple[int, str]] = []
        self._numeric_cols: set[int] = set()
        self._updating: bool = False

        self._init_ui()
        self.retranslate_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Header
        self.lbl_title = QLabel(self)
        self.lbl_title.setStyleSheet("font-weight: bold; color: #003399;")
        root.addWidget(self.lbl_title)

        # Quick field search filter
        self.edit_search = QLineEdit(self)
        self.edit_search.setClearButtonEnabled(True)
        self.edit_search.textChanged.connect(self._on_search_changed)
        root.addWidget(self.edit_search)

        # Top available fields list (checkable + draggable)
        self.field_list = PivotFieldListWidget(self)
        self.field_list.itemChanged.connect(self._on_field_item_changed)
        root.addWidget(self.field_list, stretch=2)

        # Drop areas prompt
        self.lbl_areas_hint = QLabel(self)
        root.addWidget(self.lbl_areas_hint)

        # 2x2 Grid of 4 drop zones
        grid = QGridLayout()
        grid.setSpacing(6)

        self.lbl_filters = QLabel(self)
        self.lbl_columns = QLabel(self)
        self.lbl_rows = QLabel(self)
        self.lbl_values = QLabel(self)

        self.zone_filters = PivotDropZoneWidget("filters", self)
        self.zone_columns = PivotDropZoneWidget("columns", self)
        self.zone_rows = PivotDropZoneWidget("rows", self)
        self.zone_values = PivotDropZoneWidget("values", self)

        self.drop_zones: dict[str, PivotDropZoneWidget] = {
            "filters": self.zone_filters,
            "columns": self.zone_columns,
            "rows": self.zone_rows,
            "values": self.zone_values,
        }

        for zone in self.drop_zones.values():
            zone.field_dropped.connect(self._on_zone_field_dropped)
            zone.context_action.connect(self._on_zone_context_action)
        self.zone_values.itemDoubleClicked.connect(self._on_value_double_clicked)

        grid.addWidget(self.lbl_filters, 0, 0)
        grid.addWidget(self.lbl_columns, 0, 1)
        grid.addWidget(self.zone_filters, 1, 0)
        grid.addWidget(self.zone_columns, 1, 1)
        grid.addWidget(self.lbl_rows, 2, 0)
        grid.addWidget(self.lbl_values, 2, 1)
        grid.addWidget(self.zone_rows, 3, 0)
        grid.addWidget(self.zone_values, 3, 1)

        root.addLayout(grid, stretch=3)

        # Subtotal / Grand Total toggles
        opts_layout = QHBoxLayout()
        opts_layout.setSpacing(8)
        self.chk_subtotals = QCheckBox(self)
        self.chk_subtotals.setChecked(True)
        self.chk_subtotals.toggled.connect(self._on_layout_option_changed)
        opts_layout.addWidget(self.chk_subtotals)

        self.chk_grand_totals = QCheckBox(self)
        self.chk_grand_totals.setChecked(True)
        self.chk_grand_totals.toggled.connect(self._on_layout_option_changed)
        opts_layout.addWidget(self.chk_grand_totals)
        opts_layout.addStretch()
        root.addLayout(opts_layout)

        # Defer update + Update button
        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.chk_defer = QCheckBox(self)
        self.chk_defer.setChecked(False)
        footer.addWidget(self.chk_defer, stretch=1)

        self.btn_update = QPushButton(self)
        self.btn_update.clicked.connect(self.apply_layout_update)
        footer.addWidget(self.btn_update)
        root.addLayout(footer)

    def retranslate_ui(self) -> None:
        """Apply localized strings across all widgets in the task pane."""
        self.lbl_title.setText(safe_tr("选择要添加到报表的字段:"))
        self.edit_search.setPlaceholderText(safe_tr("搜索字段..."))
        self.lbl_areas_hint.setText(safe_tr("在下面区域间拖动字段:"))
        self.lbl_filters.setText(safe_tr("报表筛选(&F)"))
        self.lbl_columns.setText(safe_tr("列标签(&C)"))
        self.lbl_rows.setText(safe_tr("行标签(&R)"))
        self.lbl_values.setText(safe_tr("数值(&V)"))
        self.chk_subtotals.setText(safe_tr("分类汇总(&S)"))
        self.chk_grand_totals.setText(safe_tr("总计(&G)"))
        self.chk_defer.setText(safe_tr("推迟布局更新(&D)"))
        self.btn_update.setText(safe_tr("更新(&U)"))

        # Refresh value item display strings
        prev_guard = self._updating
        self._updating = True
        try:
            for i in range(self.zone_values.count()):
                item = self.zone_values.item(i)
                col_idx = item.data(_ROLE_COL_IDX)
                name = item.data(_ROLE_FIELD_NAME) or self._field_name(col_idx)
                agg = item.data(_ROLE_AGG_FUNC) or "sum"
                item.setText(self._format_value_label(name, agg))
        finally:
            self._updating = prev_guard

    def _field_name(self, col_idx: int) -> str:
        for c, name in self._fields:
            if c == col_idx:
                return name
        return f"Field {col_idx}"

    @staticmethod
    def _format_value_label(name: str, agg_func: str) -> str:
        prefix = safe_tr(_AGG_DISPLAY_NAMES.get(agg_func, agg_func.capitalize()))
        return f"{prefix}: {name}"

    def _on_search_changed(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.field_list.count()):
            item = self.field_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())

    def set_fields(
        self,
        fields: list[tuple[int, str]],
        numeric_cols: set[int] | None = None,
    ) -> None:
        """Populate available fields in the top field list."""
        self._updating = True
        try:
            self._fields = list(fields)
            self._numeric_cols = set(numeric_cols or ())
            self.field_list.clear()
            for col_idx, name in self._fields:
                item = QListWidgetItem(name)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsDragEnabled
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(_ROLE_COL_IDX, col_idx)
                item.setData(_ROLE_FIELD_NAME, name)
                self.field_list.addItem(item)
        finally:
            self._updating = False

    def bind_pivot_report(
        self,
        report: PivotReport | None,
        workbook: WorkbookModel | None = None,
    ) -> None:
        """Bind a live PivotReport and synchronize all UI lists and zones."""
        if workbook is not None:
            self.workbook = workbook
        self._report = report

        self._updating = True
        try:
            for zone in self.drop_zones.values():
                zone.clear()

            if report is None or self.workbook is None:
                self.field_list.clear()
                self._fields = []
                self._numeric_cols = set()
                return

            fields, num_cols = extract_source_fields(
                self.workbook,
                report.layout.source_sheet,
                report.layout.source_range,
            )
            self._fields = fields
            self._numeric_cols = num_cols

            self.field_list.clear()
            for col_idx, name in fields:
                item = QListWidgetItem(name)
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsDragEnabled
                )
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setData(_ROLE_COL_IDX, col_idx)
                item.setData(_ROLE_FIELD_NAME, name)
                self.field_list.addItem(item)

            for zone_key, dim_fields in (
                ("filters", report.layout.filters),
                ("columns", report.layout.columns),
                ("rows", report.layout.rows),
            ):
                for df in dim_fields:
                    self._insert_zone_item(
                        zone_key,
                        df.col_idx,
                        df.name or self._field_name(df.col_idx),
                        selected_vals=df.selected_values,
                    )
            for vf in report.layout.values:
                self._insert_zone_item(
                    "values",
                    vf.col_idx,
                    vf.name or self._field_name(vf.col_idx),
                    agg_func=vf.agg_func,
                )

            self.chk_subtotals.setChecked(report.layout.show_subtotals)
            self.chk_grand_totals.setChecked(
                report.layout.show_grand_total_rows or report.layout.show_grand_total_cols
            )
            self._sync_field_check_states()
        finally:
            self._updating = False

    def _insert_zone_item(
        self,
        zone_id: str,
        col_idx: int,
        name: str,
        agg_func: str | None = None,
        selected_vals: set[str] | None = None,
        target_index: int = -1,
    ) -> QListWidgetItem:
        zone_widget = self.drop_zones[zone_id]
        if zone_id == "values":
            eff_agg = agg_func or ("sum" if col_idx in self._numeric_cols else "count")
            text = self._format_value_label(name, eff_agg)
        else:
            eff_agg = None
            text = name

        item = QListWidgetItem(text)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        item.setData(_ROLE_COL_IDX, col_idx)
        item.setData(_ROLE_FIELD_NAME, name)
        item.setData(_ROLE_AGG_FUNC, eff_agg)
        item.setData(
            _ROLE_SELECTED_VALS,
            set(selected_vals) if selected_vals is not None else None,
        )

        if 0 <= target_index <= zone_widget.count():
            zone_widget.insertItem(target_index, item)
        else:
            zone_widget.addItem(item)
        return item

    def _used_col_indices(self) -> set[int]:
        used: set[int] = set()
        for zone in self.drop_zones.values():
            for i in range(zone.count()):
                col_idx = zone.item(i).data(_ROLE_COL_IDX)
                if col_idx is not None:
                    used.add(int(col_idx))
        return used

    def _sync_field_check_states(self) -> None:
        used = self._used_col_indices()
        prev = self._updating
        self._updating = True
        try:
            for i in range(self.field_list.count()):
                item = self.field_list.item(i)
                col_idx = item.data(_ROLE_COL_IDX)
                state = (
                    Qt.CheckState.Checked
                    if col_idx in used
                    else Qt.CheckState.Unchecked
                )
                item.setCheckState(state)
        finally:
            self._updating = prev

    def _on_field_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating:
            return
        col_idx = item.data(_ROLE_COL_IDX)
        if col_idx is None:
            return
        col_idx = int(col_idx)

        if item.checkState() == Qt.CheckState.Checked:
            # Smart routing: numeric -> Values (if not already in Values), else -> Rows
            if col_idx in self._numeric_cols:
                self.add_field_to_zone(col_idx, "values", agg_func="sum")
            else:
                self.add_field_to_zone(col_idx, "rows")
        else:
            # Uncheck removes field from all 4 zones
            self._updating = True
            try:
                for zone in self.drop_zones.values():
                    for row in range(zone.count() - 1, -1, -1):
                        if zone.item(row).data(_ROLE_COL_IDX) == col_idx:
                            zone.takeItem(row)
            finally:
                self._updating = False
            self._maybe_emit_and_refresh()

    def _on_zone_field_dropped(
        self, payload: dict[str, Any], target_zone: str, target_index: int
    ) -> None:
        col_idx = payload.get("col_idx")
        if col_idx is None:
            return
        col_idx = int(col_idx)
        source_zone = payload.get("source_zone")
        source_index = int(payload.get("source_index", -1))
        agg_func = payload.get("agg_func")

        if source_zone and source_zone in self.drop_zones:
            self.move_field(
                col_idx=col_idx,
                from_zone=source_zone,
                to_zone=target_zone,
                source_index=source_index,
                target_index=target_index,
                agg_func=agg_func,
            )
        else:
            self.add_field_to_zone(
                col_idx=col_idx,
                zone=target_zone,
                agg_func=agg_func,
                target_index=target_index,
            )

    def add_field_to_zone(
        self,
        col_idx: int,
        zone: str,
        agg_func: str | None = None,
        target_index: int = -1,
    ) -> None:
        """Add a field into one of the 4 drop zones."""
        if zone not in self.drop_zones:
            return
        name = self._field_name(col_idx)

        self._updating = True
        try:
            if zone != "values":
                # Keep field unique across non-value dimension zones (filters/columns/rows)
                for z_id in ("filters", "columns", "rows"):
                    zw = self.drop_zones[z_id]
                    for r in range(zw.count() - 1, -1, -1):
                        if zw.item(r).data(_ROLE_COL_IDX) == col_idx:
                            zw.takeItem(r)
            self._insert_zone_item(
                zone, col_idx, name, agg_func=agg_func, target_index=target_index
            )
            self._sync_field_check_states()
        finally:
            self._updating = False

        self._maybe_emit_and_refresh()

    def move_field(
        self,
        col_idx: int,
        from_zone: str,
        to_zone: str,
        source_index: int = -1,
        target_index: int = -1,
        agg_func: str | None = None,
    ) -> None:
        """Move an existing field item from one zone to another (or reorder)."""
        if from_zone not in self.drop_zones or to_zone not in self.drop_zones:
            return
        src_w = self.drop_zones[from_zone]

        self._updating = True
        try:
            taken: QListWidgetItem | None = None
            if (
                0 <= source_index < src_w.count()
                and src_w.item(source_index).data(_ROLE_COL_IDX) == col_idx
            ):
                taken = src_w.takeItem(source_index)
            else:
                for r in range(src_w.count()):
                    if src_w.item(r).data(_ROLE_COL_IDX) == col_idx:
                        taken = src_w.takeItem(r)
                        break

            name = (
                taken.data(_ROLE_FIELD_NAME)
                if taken is not None
                else self._field_name(col_idx)
            )
            sel_vals = taken.data(_ROLE_SELECTED_VALS) if taken is not None else None
            eff_agg = agg_func or (taken.data(_ROLE_AGG_FUNC) if taken is not None else None)

            if from_zone == to_zone and 0 <= source_index < target_index:
                target_index = max(0, target_index - 1)

            if to_zone != "values":
                # Ensure no duplicate in target non-value zones
                for z_id in ("filters", "columns", "rows"):
                    zw = self.drop_zones[z_id]
                    for r in range(zw.count() - 1, -1, -1):
                        if zw.item(r).data(_ROLE_COL_IDX) == col_idx:
                            zw.takeItem(r)

            self._insert_zone_item(
                to_zone,
                col_idx,
                name,
                agg_func=eff_agg,
                selected_vals=sel_vals,
                target_index=target_index,
            )
            self._sync_field_check_states()
        finally:
            self._updating = False

        self._maybe_emit_and_refresh()

    def remove_field_from_zone(
        self, col_idx: int, zone: str, index: int | None = None
    ) -> None:
        """Remove a field from a specified drop zone."""
        if zone not in self.drop_zones:
            return
        zw = self.drop_zones[zone]
        self._updating = True
        try:
            if index is not None and 0 <= index < zw.count():
                zw.takeItem(index)
            else:
                for r in range(zw.count() - 1, -1, -1):
                    if zw.item(r).data(_ROLE_COL_IDX) == col_idx:
                        zw.takeItem(r)
            self._sync_field_check_states()
        finally:
            self._updating = False

        self._maybe_emit_and_refresh()

    def set_value_aggregation(
        self, index_or_col: int, agg_func: str, by_col: bool = False
    ) -> None:
        """Change aggregation function on a Values zone item."""
        self._updating = True
        try:
            changed = False
            for i in range(self.zone_values.count()):
                item = self.zone_values.item(i)
                match = (
                    item.data(_ROLE_COL_IDX) == index_or_col
                    if by_col
                    else i == index_or_col
                )
                if match:
                    name = item.data(_ROLE_FIELD_NAME) or self._field_name(
                        item.data(_ROLE_COL_IDX)
                    )
                    item.setData(_ROLE_AGG_FUNC, agg_func)
                    item.setText(self._format_value_label(name, agg_func))
                    changed = True
                    if not by_col:
                        break
        finally:
            self._updating = False

        if changed:
            self._maybe_emit_and_refresh()

    def set_filter_values(
        self, col_idx: int, selected_values: set[str] | None
    ) -> None:
        """Set active filter values for a field in Filters/Rows/Columns."""
        self._updating = True
        try:
            for z_id in ("filters", "rows", "columns"):
                zw = self.drop_zones[z_id]
                for i in range(zw.count()):
                    item = zw.item(i)
                    if item.data(_ROLE_COL_IDX) == col_idx:
                        item.setData(
                            _ROLE_SELECTED_VALS,
                            set(selected_values) if selected_values is not None else None,
                        )
        finally:
            self._updating = False
        self._maybe_emit_and_refresh()

    def _on_value_double_clicked(self, item: QListWidgetItem) -> None:
        row = self.zone_values.row(item)
        self._open_value_settings(row)

    def _open_value_settings(self, row: int) -> None:
        if not (0 <= row < self.zone_values.count()):
            return
        item = self.zone_values.item(row)
        name = item.data(_ROLE_FIELD_NAME) or item.text()
        cur_agg = item.data(_ROLE_AGG_FUNC) or "sum"
        dlg = ValueFieldSettingsDialog(name, cur_agg, parent=self)
        if dlg.exec():
            self.set_value_aggregation(row, dlg.selected_func)

    def _open_filter_values_menu(self, row: int) -> None:
        if (
            not (0 <= row < self.zone_filters.count())
            or self._report is None
            or self.workbook is None
        ):
            return
        item = self.zone_filters.item(row)
        col_idx = int(item.data(_ROLE_COL_IDX))
        unique_vals = get_unique_field_values(
            self.workbook,
            self._report.layout.source_sheet,
            self._report.layout.source_range,
            col_idx,
        )
        menu = QMenu(self)
        act_all = menu.addAction(safe_tr("(全部)"))
        act_all.triggered.connect(lambda: self.set_filter_values(col_idx, None))
        menu.addSeparator()
        for val in unique_vals:
            act = menu.addAction(val)
            act.triggered.connect(
                lambda _checked=False, v=val: self.set_filter_values(col_idx, {v})
            )
        menu.exec(self.zone_filters.mapToGlobal(self.zone_filters.rect().center()))

    def _on_zone_context_action(self, action: str, zone_id: str, row: int) -> None:
        zw = self.drop_zones.get(zone_id)
        if zw is None or not (0 <= row < zw.count()):
            return
        item = zw.item(row)
        col_idx = int(item.data(_ROLE_COL_IDX))

        if action == "settings":
            self._open_value_settings(row)
        elif action == "filter_values":
            self._open_filter_values_menu(row)
        elif action.startswith("agg:"):
            fn = action.split(":", 1)[1]
            self.set_value_aggregation(row, fn)
        elif action.startswith("move:"):
            target_zone = action.split(":", 1)[1]
            self.move_field(col_idx, zone_id, target_zone, source_index=row)
        elif action == "up" and row > 0:
            self.move_field(col_idx, zone_id, zone_id, source_index=row, target_index=row - 1)
        elif action == "down" and row < zw.count() - 1:
            self.move_field(col_idx, zone_id, zone_id, source_index=row, target_index=row + 2)
        elif action == "remove":
            self.remove_field_from_zone(col_idx, zone_id, index=row)

    def _on_layout_option_changed(self, _checked: bool = False) -> None:
        if self._updating:
            return
        self._maybe_emit_and_refresh()

    def build_layout_spec(self) -> PivotLayoutSpec | None:
        """Build a PivotLayoutSpec from current UI zone lists."""
        if self._report is None:
            return None

        base = self._report.layout

        def extract_dim_fields(zw: PivotDropZoneWidget) -> list[PivotFieldSpec]:
            out: list[PivotFieldSpec] = []
            for i in range(zw.count()):
                it = zw.item(i)
                col_idx = int(it.data(_ROLE_COL_IDX))
                name = it.data(_ROLE_FIELD_NAME) or self._field_name(col_idx)
                sel_vals = it.data(_ROLE_SELECTED_VALS)
                out.append(
                    PivotFieldSpec(
                        col_idx=col_idx,
                        name=name,
                        selected_values=set(sel_vals) if sel_vals is not None else None,
                    )
                )
            return out

        def extract_val_fields(zw: PivotDropZoneWidget) -> list[PivotValueSpec]:
            out: list[PivotValueSpec] = []
            for i in range(zw.count()):
                it = zw.item(i)
                col_idx = int(it.data(_ROLE_COL_IDX))
                name = it.data(_ROLE_FIELD_NAME) or self._field_name(col_idx)
                agg = it.data(_ROLE_AGG_FUNC) or "sum"
                out.append(PivotValueSpec(col_idx=col_idx, name=name, agg_func=agg))
            return out

        show_gt = self.chk_grand_totals.isChecked()
        return PivotLayoutSpec(
            source_sheet=base.source_sheet,
            source_range=base.source_range,
            filters=extract_dim_fields(self.zone_filters),
            columns=extract_dim_fields(self.zone_columns),
            rows=extract_dim_fields(self.zone_rows),
            values=extract_val_fields(self.zone_values),
            show_subtotals=self.chk_subtotals.isChecked(),
            show_grand_total_rows=show_gt,
            show_grand_total_cols=show_gt,
            target_sheet=base.target_sheet,
            target_cell=base.target_cell,
            name=base.name,
        )

    def _maybe_emit_and_refresh(self) -> None:
        if self._updating or self.chk_defer.isChecked():
            return
        self.apply_layout_update()

    def apply_layout_update(self) -> PivotReport | None:
        """Apply current zone layout to bound PivotReport and trigger recalculation."""
        spec = self.build_layout_spec()
        if spec is None or self._report is None:
            return None

        self._report.layout = spec
        self.layout_changed.emit(spec)
        if self.workbook is not None:
            if refresh_pivot_report(self.workbook, self._report):
                self.report_refreshed.emit(self._report)
        return self._report
