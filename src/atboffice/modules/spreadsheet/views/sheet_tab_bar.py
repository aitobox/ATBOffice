"""Classic Excel 2003 SheetTabBar component for ATBOffice Ledger spreadsheet."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygon,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QToolButton,
    QWidget,
)

from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import (
    WorkbookModel,
    is_valid_sheet_name,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SheetTabBar", text)


class TabNavButton(QToolButton):
    """Compact 16x20 navigation arrow button matching Excel 2003 tab nav."""

    def __init__(self, kind: str, parent: SheetTabBar) -> None:
        super().__init__(parent)
        self.kind = kind  # "first", "prev", "next", "last"
        self._parent_bar = parent
        self.setFixedSize(16, 22)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAutoRaise(True)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        tips = {
            "first": safe_tr("第一张工作表"),
            "prev": safe_tr("上一张工作表"),
            "next": safe_tr("下一张工作表"),
            "last": safe_tr("最后一张工作表"),
        }
        self.setToolTip(tips.get(self.kind, ""))

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        rect = self.rect()
        is_hover = self.underMouse()
        is_down = self.isDown()

        # Background
        if is_down:
            painter.fillRect(rect, QColor(210, 207, 195))
            painter.setPen(QColor(120, 115, 100))
            painter.drawRect(0, 0, rect.width() - 1, rect.height() - 1)
        elif is_hover:
            painter.fillRect(rect, QColor(245, 244, 238))
            painter.setPen(QColor(160, 155, 140))
            painter.drawRect(0, 0, rect.width() - 1, rect.height() - 1)
        else:
            painter.fillRect(rect, QColor(236, 233, 216))

        # Vector glyph
        painter.setPen(Qt.PenStyle.NoPen)
        arrow_color = QColor(0, 0, 0) if self.isEnabled() else QColor(128, 128, 128)
        painter.setBrush(QBrush(arrow_color))

        cy = rect.height() // 2
        cx = rect.width() // 2

        if self.kind == "first":
            # Bar at left + left arrow
            painter.fillRect(cx - 5, cy - 4, 2, 8, arrow_color)
            poly = QPolygon(
                [
                    QPoint(cx - 2, cy),
                    QPoint(cx + 4, cy - 4),
                    QPoint(cx + 4, cy + 4),
                ]
            )
            painter.drawPolygon(poly)
        elif self.kind == "prev":
            # Left arrow
            poly = QPolygon(
                [
                    QPoint(cx - 3, cy),
                    QPoint(cx + 3, cy - 4),
                    QPoint(cx + 3, cy + 4),
                ]
            )
            painter.drawPolygon(poly)
        elif self.kind == "next":
            # Right arrow
            poly = QPolygon(
                [
                    QPoint(cx + 3, cy),
                    QPoint(cx - 3, cy - 4),
                    QPoint(cx - 3, cy + 4),
                ]
            )
            painter.drawPolygon(poly)
        elif self.kind == "last":
            # Right arrow + bar at right
            poly = QPolygon(
                [
                    QPoint(cx + 2, cy),
                    QPoint(cx - 4, cy - 4),
                    QPoint(cx - 4, cy + 4),
                ]
            )
            painter.drawPolygon(poly)
            painter.fillRect(cx + 4, cy - 4, 2, 8, arrow_color)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Right-click on nav buttons displays full sheets list menu."""
        wb = self._parent_bar.workbook
        if not wb or not wb.sheets:
            return

        menu = QMenu(self)
        for idx, sheet in enumerate(wb.sheets):
            act = menu.addAction(sheet.name)
            act.setCheckable(True)
            act.setChecked(idx == wb.active_sheet_index)
            act.triggered.connect(
                lambda checked=False, target_idx=idx: self._parent_bar.set_active_index(
                    target_idx
                )
            )
        menu.exec(event.globalPos())


class RenameInlineEditor(QLineEdit):
    """Inline QLineEdit editor for renaming worksheet tab in place."""

    def __init__(self, tab_bar: SheetTabBar, index: int, parent: QWidget) -> None:
        super().__init__(parent)
        self._tab_bar = tab_bar
        self._index = index
        self._finished = False

        self.setStyleSheet(
            "QLineEdit { font-size: 11px; padding: 0px 2px; "
            "border: 1px solid #000000; background: #FFFFFF; color: #000000; }"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(commit=True)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._finish(commit=False)
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event: QEvent) -> None:
        super().focusOutEvent(event)
        if not self._finished:
            self._finish(commit=True)

    def _finish(self, commit: bool) -> None:
        if self._finished:
            return
        self._finished = True
        if commit:
            self._tab_bar.commit_rename(self.text())
        else:
            self._tab_bar.cancel_rename()


class TabStripWidget(QWidget):
    """Custom-painted horizontal tab strip managing sheet tabs and interactions."""

    def __init__(self, tab_bar: SheetTabBar) -> None:
        super().__init__(tab_bar)
        self._tab_bar = tab_bar
        self._scroll_offset: int = 0
        self._tab_rects: list[QRect] = []
        self._hover_index: int = -1

        self.setMouseTracking(True)
        self.setFixedHeight(22)

    @property
    def scroll_offset(self) -> int:
        return self._scroll_offset

    @scroll_offset.setter
    def scroll_offset(self, val: int) -> None:
        self._scroll_offset = max(0, val)
        self.update()

    def ensure_tab_visible(self, index: int) -> None:
        """Scroll tab strip so tab at index is fully visible in viewport."""
        if 0 <= index < len(self._tab_rects):
            rect = self._tab_rects[index]
            # Convert to absolute strip coordinates (un-offset)
            abs_left = rect.left() + self._scroll_offset
            abs_right = rect.right() + self._scroll_offset
            vw = self.width()

            if abs_left < self._scroll_offset:
                self._scroll_offset = max(0, abs_left - 4)
            elif abs_right > self._scroll_offset + vw:
                self._scroll_offset = max(0, abs_right - vw + 4)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta != 0:
            total_w = sum(r.width() for r in self._tab_rects)
            max_scroll = max(0, total_w - self.width() + 40)
            step = 30 if delta < 0 else -30
            self._scroll_offset = max(0, min(max_scroll, self._scroll_offset + step))
            self.update()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()
        new_hover = -1
        for idx, rect in enumerate(self._tab_rects):
            if rect.contains(pos):
                new_hover = idx
                break
        if new_hover != self._hover_index:
            self._hover_index = new_hover
            self.update()

    def leaveEvent(self, event: QEvent) -> None:
        super().leaveEvent(event)
        self._hover_index = -1
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()
        clicked_idx = -1
        for idx, rect in enumerate(self._tab_rects):
            if rect.contains(pos):
                clicked_idx = idx
                break

        if clicked_idx != -1:
            if event.button() == Qt.MouseButton.LeftButton:
                self._tab_bar.set_active_index(clicked_idx)
            elif event.button() == Qt.MouseButton.RightButton:
                if clicked_idx != self._tab_bar.active_index:
                    self._tab_bar.set_active_index(clicked_idx)
                self._tab_bar._show_tab_context_menu(clicked_idx, event.globalPos())

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            for idx, rect in enumerate(self._tab_rects):
                if rect.contains(pos):
                    self._tab_bar.start_rename(idx)
                    break

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        wb = self._tab_bar.workbook
        if not wb or not wb.sheets:
            return

        font = QFont("Arial", 9)
        painter.setFont(font)
        fm = QFontMetrics(font)

        w = self.width()
        h = self.height()

        # Background bar
        painter.fillRect(0, 0, w, h, QColor(236, 233, 216))

        # Bottom baseline
        painter.setPen(QColor(158, 154, 145))
        painter.drawLine(0, h - 1, w, h - 1)

        # Calculate rects
        cur_x = 4 - self._scroll_offset
        self._tab_rects = []
        tab_widths = []
        for s in wb.sheets:
            tw = max(56, fm.horizontalAdvance(s.name) + 24)
            tab_widths.append(tw)

        for tw in tab_widths:
            self._tab_rects.append(QRect(cur_x, 2, tw, h - 2))
            cur_x += tw - 3

        active_idx = self._tab_bar.active_index

        # Pass 1: Draw inactive tabs
        for idx, rect in enumerate(self._tab_rects):
            if idx == active_idx:
                continue
            self._draw_tab(painter, idx, rect, is_active=False)

        # Pass 2: Draw active tab on top
        if 0 <= active_idx < len(self._tab_rects):
            active_rect = self._tab_rects[active_idx]
            self._draw_tab(painter, active_idx, active_rect, is_active=True)

    def _draw_tab(
        self, painter: QPainter, index: int, rect: QRect, is_active: bool
    ) -> None:
        wb = self._tab_bar.workbook
        if not wb or index >= len(wb.sheets):
            return

        sheet = wb.sheets[index]
        name = sheet.name
        is_hover = index == self._hover_index and not is_active
        tab_color = self._tab_bar.tab_color(index)

        border_color = QColor(158, 154, 145) if not is_active else QColor(127, 157, 185)
        bg_color = (
            QColor(255, 255, 255)
            if is_active
            else (QColor(245, 244, 238) if is_hover else QColor(220, 216, 205))
        )

        r = rect.adjusted(0, 0, 0, 0 if not is_active else 1)

        # Tab polygon with classic slanted top corners
        x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()
        poly = QPolygon(
            [
                QPoint(x1, y2),
                QPoint(x1 + 3, y1 + 1),
                QPoint(x1 + 5, y1),
                QPoint(x2 - 5, y1),
                QPoint(x2 - 3, y1 + 1),
                QPoint(x2, y2),
            ]
        )

        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        painter.drawPolygon(poly)

        # Tab Color stripe if set
        if tab_color:
            painter.fillRect(x1 + 4, y2 - 3, x2 - x1 - 7, 3, tab_color)

        # If active, erase bottom baseline so tab seamlessly connects to grid
        if is_active:
            painter.setPen(QColor(255, 255, 255))
            painter.drawLine(x1 + 1, y2, x2 - 1, y2)

        # Draw sheet name text
        painter.setPen(QColor(0, 0, 0))
        font = painter.font()
        font.setBold(is_active)
        painter.setFont(font)

        text_rect = r.adjusted(4, 1, -4, -1)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
            name,
        )


class SheetTabBar(QWidget):
    """Excel 2003 Classic bottom SheetTabBar widget for ATBOffice Ledger.

    Provides first/prev/next/last navigation buttons, horizontal scrollable
    worksheet tabs, inline renaming, right-click context menu, and bidirectional
    synchronization with WorkbookModel.
    """

    tab_clicked = Signal(int)
    tab_rename_requested = Signal(int, str)
    sheet_insert_requested = Signal()
    sheet_delete_requested = Signal(int)
    sheet_color_requested = Signal(int, QColor)

    def __init__(
        self,
        workbook: WorkbookModel | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._workbook: WorkbookModel = (
            workbook if workbook is not None else WorkbookModel()
        )
        self._tab_colors: dict[SheetDataModel, QColor] = {}
        self._is_renaming: bool = False
        self._rename_editor: RenameInlineEditor | None = None
        self._renaming_index: int = -1

        self.setFixedHeight(22)
        self.setMinimumWidth(200)

        # Main horizontal layout: Nav Buttons Area + Tabs Strip
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Nav Buttons container
        nav_container = QWidget(self)
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        self.btn_first = TabNavButton("first", self)
        self.btn_prev = TabNavButton("prev", self)
        self.btn_next = TabNavButton("next", self)
        self.btn_last = TabNavButton("last", self)

        nav_layout.addWidget(self.btn_first)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.btn_last)

        self.btn_first.clicked.connect(self._on_nav_first)
        self.btn_prev.clicked.connect(self._on_nav_prev)
        self.btn_next.clicked.connect(self._on_nav_next)
        self.btn_last.clicked.connect(self._on_nav_last)

        main_layout.addWidget(nav_container)

        # 2. Tabs Strip
        self._strip = TabStripWidget(self)
        main_layout.addWidget(self._strip, 1)

        # Connect WorkbookModel lifecycle signals
        self._bind_workbook(self._workbook)

        self.retranslate_ui()

    @property
    def workbook(self) -> WorkbookModel:
        """Return the bound WorkbookModel."""
        return self._workbook

    @property
    def tab_count(self) -> int:
        """Return the number of worksheets in the workbook."""
        return len(self._workbook.sheets)

    @property
    def active_index(self) -> int:
        """Return current active worksheet index."""
        return self._workbook.active_sheet_index

    @property
    def is_renaming(self) -> bool:
        """Return True if in inline rename editing mode."""
        return self._is_renaming

    @property
    def rename_editor(self) -> QLineEdit | None:
        """Return the active inline QLineEdit editor or None."""
        return self._rename_editor

    def tab_text(self, index: int) -> str:
        """Return the worksheet name for tab at index."""
        if 0 <= index < len(self._workbook.sheets):
            return self._workbook.sheets[index].name
        return ""

    def tab_color(self, index: int) -> QColor | None:
        """Return custom tab color for worksheet at index if set."""
        if 0 <= index < len(self._workbook.sheets):
            sheet = self._workbook.sheets[index]
            return self._tab_colors.get(sheet)
        return None

    def set_tab_color(self, index: int, color: QColor | None) -> None:
        """Set custom tab color for worksheet at index."""
        if 0 <= index < len(self._workbook.sheets):
            sheet = self._workbook.sheets[index]
            if color is not None and color.isValid():
                self._tab_colors[sheet] = color
            else:
                self._tab_colors.pop(sheet, None)
            self._strip.update()
            if color:
                self.sheet_color_requested.emit(index, color)

    def set_active_index(self, index: int) -> None:
        """Activate worksheet by 0-based index."""
        if 0 <= index < len(self._workbook.sheets):
            if self._is_renaming:
                self.cancel_rename()
            self._workbook.set_active_sheet_index(index)
            self._strip.ensure_tab_visible(index)
            self._strip.update()
            self.tab_clicked.emit(index)

    def set_workbook(self, workbook: WorkbookModel) -> None:
        """Rebind to a different WorkbookModel instance."""
        if self._is_renaming:
            self.cancel_rename()
        self._unbind_workbook()
        self._workbook = workbook
        self._bind_workbook(self._workbook)
        self._strip.update()

    def _bind_workbook(self, wb: WorkbookModel) -> None:
        wb.sheet_added.connect(self._on_sheet_added)
        wb.sheet_removed.connect(self._on_sheet_removed)
        wb.sheet_renamed.connect(self._on_sheet_renamed)
        wb.sheet_moved.connect(self._on_sheet_moved)
        wb.active_sheet_changed.connect(self._on_active_sheet_changed)

    def _unbind_workbook(self) -> None:
        try:
            self._workbook.sheet_added.disconnect(self._on_sheet_added)
            self._workbook.sheet_removed.disconnect(self._on_sheet_removed)
            self._workbook.sheet_renamed.disconnect(self._on_sheet_renamed)
            self._workbook.sheet_moved.disconnect(self._on_sheet_moved)
            self._workbook.active_sheet_changed.disconnect(
                self._on_active_sheet_changed
            )
        except (RuntimeError, TypeError):
            pass

    # Navigation Button Handlers
    def _on_nav_first(self) -> None:
        if self.tab_count > 0:
            self.set_active_index(0)

    def _on_nav_prev(self) -> None:
        if self.tab_count > 0:
            new_idx = max(0, self.active_index - 1)
            self.set_active_index(new_idx)

    def _on_nav_next(self) -> None:
        if self.tab_count > 0:
            new_idx = min(self.tab_count - 1, self.active_index + 1)
            self.set_active_index(new_idx)

    def _on_nav_last(self) -> None:
        if self.tab_count > 0:
            self.set_active_index(self.tab_count - 1)

    # Inline Renaming
    def start_rename(self, index: int) -> None:
        """Begin in-place renaming of tab at index."""
        if not (0 <= index < len(self._workbook.sheets)):
            return

        if self._is_renaming:
            self.cancel_rename()

        self.set_active_index(index)
        self._is_renaming = True
        self._renaming_index = index

        # Position editor exactly over tab rect
        if index < len(self._strip._tab_rects):
            tab_r = self._strip._tab_rects[index]
        else:
            tab_r = QRect(60, 2, 80, 18)

        editor_rect = tab_r.adjusted(4, 2, -4, -2)

        self._rename_editor = RenameInlineEditor(self, index, self._strip)
        self._rename_editor.setText(self._workbook.sheets[index].name)
        self._rename_editor.setGeometry(editor_rect)
        self._rename_editor.selectAll()
        self._rename_editor.show()
        self._rename_editor.setFocus()

    def commit_rename(self, new_name: str) -> bool:
        """Validate and commit a proposed new name for worksheet."""
        if not self._is_renaming or self._renaming_index == -1:
            return False

        idx = self._renaming_index
        old_name = self.tab_text(idx)

        new_name_clean = new_name.strip()
        if new_name_clean == old_name:
            self.cancel_rename()
            return True

        # Validation 1: Naming rules
        if not is_valid_sheet_name(new_name_clean):
            self.cancel_rename()
            return False

        # Validation 2: Conflict check
        try:
            self._workbook.validate_new_name(new_name_clean, current_index=idx)
            self._workbook.rename_sheet(idx, new_name_clean)
        except ValueError:
            self.cancel_rename()
            return False

        self.cancel_rename()
        self.tab_rename_requested.emit(idx, new_name_clean)
        return True

    def cancel_rename(self) -> None:
        """Cancel inline rename and destroy editor."""
        self._is_renaming = False
        self._renaming_index = -1
        if self._rename_editor is not None:
            self._rename_editor.deleteLater()
            self._rename_editor = None
        self._strip.update()

    # Context Menu & Actions
    def insert_sheet(
        self, name: str | None = None, index: int | None = None
    ) -> SheetDataModel:
        """Insert new sheet into workbook, activate it, and return model."""
        new_sheet = self._workbook.add_sheet(name=name, index=index)
        new_idx = self._workbook.sheet_index(new_sheet)
        self.set_active_index(new_idx)
        self.sheet_insert_requested.emit()
        return new_sheet

    def delete_sheet(self, index: int) -> bool:
        """Delete worksheet at index. Protects against removing only sheet."""
        if len(self._workbook.sheets) <= 1:
            return False
        if not (0 <= index < len(self._workbook.sheets)):
            return False

        removed = self._workbook.remove_sheet(index)
        self._tab_colors.pop(removed, None)
        self.sheet_delete_requested.emit(index)
        return True

    def duplicate_sheet(self, index: int) -> SheetDataModel | None:
        """Duplicate worksheet at index and insert copy adjacent to it."""
        if not (0 <= index < len(self._workbook.sheets)):
            return None

        src = self._workbook.sheets[index]
        base_name = src.name
        copy_name = f"{base_name} (2)"
        counter = 2
        while self._workbook.get_sheet_by_name(copy_name) is not None:
            counter += 1
            copy_name = f"{base_name} ({counter})"

        # Shallow copy cell contents
        copy_sheet = SheetDataModel(name=copy_name)
        for coord, cell in src.cells.items():
            copy_sheet.cells[coord] = cell
        copy_sheet.merges = list(src.merges)

        insert_idx = index + 1
        new_sheet = self._workbook.add_sheet(
            name=copy_name, index=insert_idx, sheet=copy_sheet
        )
        self.set_active_index(insert_idx)
        return new_sheet

    def _show_tab_context_menu(self, index: int, global_pos: QPoint) -> None:
        """Display Excel 2003 context menu for tab at index."""
        menu = QMenu(self)

        act_insert = menu.addAction(safe_tr("插入(&I)..."))
        act_delete = menu.addAction(safe_tr("删除(&D)"))
        act_rename = menu.addAction(safe_tr("重命名(&R)"))
        act_copy = menu.addAction(safe_tr("移动或复制(&M)..."))
        act_color = menu.addAction(safe_tr("工作表标签颜色(&T)..."))
        menu.addSeparator()
        act_code = menu.addAction(safe_tr("查看代码(&V)"))
        act_code.setEnabled(False)

        if len(self._workbook.sheets) <= 1:
            act_delete.setEnabled(False)

        action = menu.exec(global_pos)
        if action == act_insert:
            self.insert_sheet()
        elif action == act_delete:
            self.delete_sheet(index)
        elif action == act_rename:
            self.start_rename(index)
        elif action == act_copy:
            self.duplicate_sheet(index)
        elif action == act_color:
            cur_color = self.tab_color(index) or QColor(255, 255, 255)
            color = QColorDialog.getColor(cur_color, self, safe_tr("选择标签颜色"))
            if color.isValid():
                self.set_tab_color(index, color)

    # Workbook Lifecycle Callbacks
    def _on_sheet_added(self, index: int, name: str) -> None:
        self._strip.update()
        self._strip.ensure_tab_visible(index)

    def _on_sheet_removed(self, index: int, name: str) -> None:
        self._strip.update()

    def _on_sheet_renamed(self, index: int, old_name: str, new_name: str) -> None:
        self._strip.update()

    def _on_sheet_moved(self, from_index: int, to_index: int) -> None:
        self._strip.update()

    def _on_active_sheet_changed(self, index: int) -> None:
        self._strip.ensure_tab_visible(index)
        self._strip.update()

    def retranslate_ui(self) -> None:
        """Retranslate all tooltips and child elements."""
        self.btn_first.retranslate_ui()
        self.btn_prev.retranslate_ui()
        self.btn_next.retranslate_ui()
        self.btn_last.retranslate_ui()
        self._strip.update()
