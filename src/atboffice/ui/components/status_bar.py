"""Status bar component with mode indicator and selection AutoCalculate."""

from __future__ import annotations

import math

from PySide6.QtCore import QCoreApplication, QPoint, Qt
from PySide6.QtGui import QAction, QActionGroup, QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QLabel, QMenu, QStatusBar, QWidget

from atboffice.modules.spreadsheet.calc.coercion import round_15
from atboffice.modules.spreadsheet.calc.errors import ExcelError, is_error
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def safe_tr(text: str) -> str:
    """Translate UI text safely for StatusBar."""
    return QCoreApplication.translate("StatusBar", text)


class AutoCalcLabel(QLabel):
    """Clickable/right-clickable label for selecting and viewing AutoCalculate results."""

    def __init__(self, status_bar: StatusBar, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.status_bar = status_bar
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.status_bar.show_calc_menu(event.globalPos())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.status_bar.show_calc_menu(event.globalPosition().toPoint())
        else:
            super().mousePressEvent(event)


class StatusBar(QStatusBar):
    """Excel 2003 / Office Luna style status bar with mode and AutoCalculate."""

    CALC_FUNCTIONS = [
        ("NONE", "无"),
        ("AVERAGE", "平均值"),
        ("COUNTA", "计数"),
        ("COUNT", "数值计数"),
        ("MAX", "最大值"),
        ("MIN", "最小值"),
        ("SUM", "求和"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.calc_function: str = "SUM"
        self._current_mode: str = "ready"
        self._last_model: SheetDataModel | None = None
        self._last_selection: SelectionModel | None = None

        self.setSizeGripEnabled(False)
        self.setStyleSheet(
            "QStatusBar { background: #ece9d8; color: #000000; "
            "border-top: 1px solid #9eb6ce; font-size: 11px; } "
            "QLabel { padding: 1px 6px; } "
            "QLabel.cell-border { border-left: 1px solid #ffffff; "
            "border-right: 1px solid #aca899; }"
        )

        # 1. Mode indicator (Ready, Enter, Edit, Point)
        self.lbl_mode = QLabel(self)
        self.lbl_mode.setProperty("class", "cell-border")
        self.lbl_mode.setMinimumWidth(55)
        self.lbl_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addWidget(self.lbl_mode, 0)

        # 2. Message area (Elastic)
        self.lbl_message = QLabel(self)
        self.addWidget(self.lbl_message, 1)

        # 3. AutoCalculate indicator (Sum, Average, etc.)
        self.lbl_calc = AutoCalcLabel(self, self)
        self.lbl_calc.setProperty("class", "cell-border")
        self.lbl_calc.setMinimumWidth(110)
        self.lbl_calc.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.addPermanentWidget(self.lbl_calc, 0)

        # 4. Keyboard lock indicators
        self.lbl_caps = QLabel("CAPS", self)
        self.lbl_caps.setStyleSheet("color: #a0a0a0; font-size: 10px;")
        self.addPermanentWidget(self.lbl_caps, 0)

        self.lbl_num = QLabel("NUM", self)
        self.lbl_num.setStyleSheet("color: #a0a0a0; font-size: 10px;")
        self.addPermanentWidget(self.lbl_num, 0)

        self.lbl_scrl = QLabel("SCRL", self)
        self.lbl_scrl.setStyleSheet("color: #a0a0a0; font-size: 10px;")
        self.addPermanentWidget(self.lbl_scrl, 0)

        self.set_mode("ready")
        self.retranslate_ui()

    def set_mode(self, mode: str) -> None:
        """Update active mode string: 'ready', 'enter', 'edit', 'point'."""
        self._current_mode = mode.lower()
        mode_names = {
            "ready": safe_tr("就绪"),
            "enter": safe_tr("输入"),
            "edit": safe_tr("编辑"),
            "point": safe_tr("点选"),
        }
        self.lbl_mode.setText(mode_names.get(self._current_mode, safe_tr("就绪")))

    def set_message(self, message: str) -> None:
        """Set informational status text in the elastic area."""
        self.lbl_message.setText(message)

    def set_calc_function(self, func_name: str) -> None:
        """Change the active AutoCalculate aggregation function."""
        self.calc_function = func_name.upper()
        if self._last_model is not None and self._last_selection is not None:
            self.update_calculation(self._last_model, self._last_selection)

    def show_calc_menu(self, global_pos: QPoint) -> None:
        """Display right-click context menu to choose AutoCalculate function."""
        menu = QMenu(self)
        action_group = QActionGroup(menu)
        action_group.setExclusive(True)

        for key, name in self.CALC_FUNCTIONS:
            translated = safe_tr(name)
            action = QAction(translated, menu)
            action.setCheckable(True)
            if self.calc_function == key:
                action.setChecked(True)
            action.setData(key)
            action_group.addAction(action)
            menu.addAction(action)

        chosen = menu.exec(global_pos)
        if chosen is not None:
            new_fn = chosen.data()
            if isinstance(new_fn, str):
                self.set_calc_function(new_fn)

    def update_calculation(
        self, model: SheetDataModel, selection: SelectionModel
    ) -> None:
        """Recalculate AutoCalculate aggregation for the current selection."""
        self._last_model = model
        self._last_selection = selection

        if self.calc_function == "NONE":
            self.lbl_calc.setText("")
            return

        ranges = selection.ranges
        is_multi = len(ranges) > 1 or any(
            r.min_r != r.max_r or r.min_c != r.max_c for r in ranges
        )
        if not is_multi:
            self.lbl_calc.setText("")
            return

        total_sum: float = 0.0
        numeric_count: int = 0
        non_empty_count: int = 0
        max_val: float = -math.inf
        min_val: float = math.inf
        has_error: bool = False

        guard = 0
        for rg in ranges:
            for r in range(rg.min_r, rg.max_r + 1):
                for c in range(rg.min_c, rg.max_c + 1):
                    guard += 1
                    if guard > 100000:
                        break
                    val = model.get_cell_value(r, c)
                    if val is None or val == "":
                        continue

                    non_empty_count += 1
                    if is_error(val) or isinstance(val, ExcelError):
                        has_error = True
                        continue

                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        num = float(val)
                        total_sum += num
                        numeric_count += 1
                        if num > max_val:
                            max_val = num
                        if num < min_val:
                            min_val = num

        def fmt_num(v: float) -> str:
            res = round_15(v)
            if res == int(res):
                return str(int(res))
            return str(res)

        result_text = ""
        fn = self.calc_function
        if has_error and fn not in ("COUNTA", "COUNT"):
            result_text = ""
        elif fn == "SUM":
            result_text = safe_tr(f"求和={fmt_num(total_sum)}")
        elif fn == "AVERAGE":
            if numeric_count > 0:
                avg = total_sum / numeric_count
                result_text = safe_tr(f"平均值={fmt_num(avg)}")
        elif fn == "COUNTA":
            result_text = safe_tr(f"计数={non_empty_count}")
        elif fn == "COUNT":
            result_text = safe_tr(f"数值计数={numeric_count}")
        elif fn == "MAX":
            if numeric_count > 0:
                result_text = safe_tr(f"最大值={fmt_num(max_val)}")
        elif fn == "MIN":
            if numeric_count > 0:
                result_text = safe_tr(f"最小值={fmt_num(min_val)}")

        self.lbl_calc.setText(result_text)

    def retranslate_ui(self) -> None:
        """Update localized UI strings."""
        self.set_mode(self._current_mode)
        self.lbl_calc.setToolTip(safe_tr("右键单击选择自动计算函数"))
