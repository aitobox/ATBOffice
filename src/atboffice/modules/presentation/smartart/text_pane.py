"""IntelliArt Outline Text Pane Widget with keyboard shortcuts and two-way sync."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.shape import Shape
from atboffice.modules.presentation.smartart.engine import (
    CATEGORIES,
    LAYOUTS,
    PALETTES,
    STYLES,
    SmartArtEngine,
    SmartArtItem,
    relayout,
    to_shapes,
)


def safe_tr(text: str) -> str:
    """Safe translation fallback for IntelliArt UI."""
    try:
        return QCoreApplication.translate("SmartArtTextPane", text)
    except Exception:
        return text


class SmartArtRowEdit(QLineEdit):
    """Custom QLineEdit for an outline item row capturing Enter/Tab/Arrow keys."""

    item_key_pressed = Signal(str, object)  # action_name, QKeyEvent

    def __init__(self, item_id: str, level: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self.level = level
        self.setPlaceholderText(safe_tr("[文本]"))
        self.setStyleSheet(f"margin-left: {level * 16}px; padding: 4px 6px; font-size: 13px;")

    def keyPressEvent(self, event: Any) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            event.accept()
            self.item_key_pressed.emit("after", event)
            return

        if key == Qt.Key.Key_Tab:
            event.accept()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.item_key_pressed.emit("promote", event)
            else:
                self.item_key_pressed.emit("demote", event)
            return

        if key == Qt.Key.Key_Backtab:
            event.accept()
            self.item_key_pressed.emit("promote", event)
            return

        if (modifiers & Qt.KeyboardModifier.AltModifier) and (modifiers & Qt.KeyboardModifier.ShiftModifier):
            if key == Qt.Key.Key_Up:
                event.accept()
                self.item_key_pressed.emit("up", event)
                return
            if key == Qt.Key.Key_Down:
                event.accept()
                self.item_key_pressed.emit("down", event)
                return

        if key == Qt.Key.Key_Backspace and not self.text():
            event.accept()
            self.item_key_pressed.emit("remove", event)
            return

        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.accept()
            self.item_key_pressed.emit("nav_up" if key == Qt.Key.Key_Up else "nav_down", event)
            return

        super().keyPressEvent(event)


class SmartArtTextPane(QWidget):
    """Task pane widget for editing IntelliArt outline text, layout, colors, and styles."""

    diagram_changed = Signal(Shape)
    item_selected = Signal(str)
    converted_to_shapes = Signal(Shape)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.engine = SmartArtEngine()
        self.current_shape: Shape | None = None
        self.active_item_id: str | None = None
        self.row_inputs: list[SmartArtRowEdit] = []

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Header Label
        self.lbl_title = QLabel(self)
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_title)

        # 2. Action Buttons Toolbar
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.btn_add = QPushButton(self)
        self.btn_add.clicked.connect(self._on_add_after)
        btn_layout.addWidget(self.btn_add)

        self.btn_promote = QPushButton(self)
        self.btn_promote.clicked.connect(self._on_promote)
        btn_layout.addWidget(self.btn_promote)

        self.btn_demote = QPushButton(self)
        self.btn_demote.clicked.connect(self._on_demote)
        btn_layout.addWidget(self.btn_demote)

        self.btn_up = QPushButton(self)
        self.btn_up.clicked.connect(self._on_move_up)
        btn_layout.addWidget(self.btn_up)

        self.btn_down = QPushButton(self)
        self.btn_down.clicked.connect(self._on_move_down)
        btn_layout.addWidget(self.btn_down)

        layout.addLayout(btn_layout)

        # 3. Outline Scroll Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.StyledPanel)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(4, 4, 4, 4)
        self.rows_layout.setSpacing(4)
        self.rows_layout.addStretch()

        self.scroll_area.setWidget(self.rows_container)
        layout.addWidget(self.scroll_area, 1)

        # 4. Shortcut Hint Note
        self.lbl_note = QLabel(self)
        self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.lbl_note)

        # 5. Design Controls (Layout, Colors, Styles)
        design_frame = QFrame(self)
        design_frame.setFrameShape(QFrame.Shape.StyledPanel)
        d_layout = QVBoxLayout(design_frame)
        d_layout.setContentsMargins(6, 6, 6, 6)
        d_layout.setSpacing(6)

        # Layout selector
        self.lbl_layout = QLabel(self)
        d_layout.addWidget(self.lbl_layout)
        self.cmb_layout = QComboBox(self)
        for lay in LAYOUTS:
            self.cmb_layout.addItem(f"{lay['cat'].capitalize()}: {lay['name']}", lay["id"])
        self.cmb_layout.currentIndexChanged.connect(self._on_layout_changed)
        d_layout.addWidget(self.cmb_layout)

        # Colors selector
        self.lbl_colors = QLabel(self)
        d_layout.addWidget(self.lbl_colors)
        self.cmb_colors = QComboBox(self)
        for cid, info in PALETTES.items():
            self.cmb_colors.addItem(str(info[0]), cid)
        self.cmb_colors.currentIndexChanged.connect(self._on_colors_changed)
        d_layout.addWidget(self.cmb_colors)

        # Styles selector
        self.lbl_styles = QLabel(self)
        d_layout.addWidget(self.lbl_styles)
        self.cmb_styles = QComboBox(self)
        for s in STYLES:
            self.cmb_styles.addItem(str(s[1]), s[0])
        self.cmb_styles.currentIndexChanged.connect(self._on_style_changed)
        d_layout.addWidget(self.cmb_styles)

        layout.addWidget(design_frame)

        # 6. Bottom Conversion Buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self.btn_reset = QPushButton(self)
        self.btn_reset.clicked.connect(self._on_reset_graphic)
        bottom_row.addWidget(self.btn_reset)

        self.btn_convert = QPushButton(self)
        self.btn_convert.clicked.connect(self._on_convert_to_shapes)
        bottom_row.addWidget(self.btn_convert)

        layout.addLayout(bottom_row)

    def retranslate_ui(self) -> None:
        """Apply localized strings to all UI components."""
        self.lbl_title.setText(safe_tr("在此键入文字:"))
        self.btn_add.setText(safe_tr("添加形状 (&A)"))
        self.btn_add.setToolTip(safe_tr("在当前项后插入新项目 (Enter)"))

        self.btn_promote.setText(safe_tr("升级 (&P)"))
        self.btn_promote.setToolTip(safe_tr("将当前项提升一级 (Shift+Tab)"))

        self.btn_demote.setText(safe_tr("降级 (&D)"))
        self.btn_demote.setToolTip(safe_tr("将当前项降低一级 (Tab)"))

        self.btn_up.setText(safe_tr("上移 (&U)"))
        self.btn_up.setToolTip(safe_tr("向上调整同级次序 (Alt+Shift+Up)"))

        self.btn_down.setText(safe_tr("下移 (&N)"))
        self.btn_down.setToolTip(safe_tr("向下调整同级次序 (Alt+Shift+Down)"))

        self.lbl_note.setText(
            safe_tr("提示: 回车创建新项；Tab/Shift+Tab 升降层级；Alt+Shift+上下键交换顺序；空行退格删除节点。")
        )
        self.lbl_layout.setText(safe_tr("图示版式:"))
        self.lbl_colors.setText(safe_tr("调色板色彩:"))
        self.lbl_styles.setText(safe_tr("材质样式:"))

        self.btn_reset.setText(safe_tr("重置图形 (&R)"))
        self.btn_reset.setToolTip(safe_tr("恢复图示默认版式与配色风格"))

        self.btn_convert.setText(safe_tr("转换为普通形状 (&C)"))
        self.btn_convert.setToolTip(safe_tr("解除智能图示约束并转为可自由分解的普通图形组合"))

    def set_diagram(self, shape: Shape | None) -> None:
        """Bind target diagram group shape to the editor pane."""
        self.current_shape = shape
        if not shape or not shape.sa:
            self.setEnabled(False)
            self._clear_rows()
            return

        self.setEnabled(True)
        sa = shape.sa
        cur_layout = sa.get("layout", "process")
        cur_colors = sa.get("colors", "ocean")
        cur_style = sa.get("style", "moderate")

        idx_l = self.cmb_layout.findData(cur_layout)
        if idx_l >= 0:
            self.cmb_layout.blockSignals(True)
            self.cmb_layout.setCurrentIndex(idx_l)
            self.cmb_layout.blockSignals(False)

        idx_c = self.cmb_colors.findData(cur_colors)
        if idx_c >= 0:
            self.cmb_colors.blockSignals(True)
            self.cmb_colors.setCurrentIndex(idx_c)
            self.cmb_colors.blockSignals(False)

        idx_s = self.cmb_styles.findData(cur_style)
        if idx_s >= 0:
            self.cmb_styles.blockSignals(True)
            self.cmb_styles.setCurrentIndex(idx_s)
            self.cmb_styles.blockSignals(False)

        self.refresh_rows()

    def _clear_rows(self) -> None:
        while self.rows_layout.count() > 1:
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.row_inputs.clear()

    def refresh_rows(self) -> None:
        """Reconstruct rows from current diagram items."""
        self._clear_rows()
        if not self.current_shape or not self.current_shape.sa:
            return

        raw_items = self.current_shape.sa.get("items", [])
        items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]
        outline_list = self.engine.outline(items)

        focus_edit: SmartArtRowEdit | None = None
        for row in outline_list:
            it = row["item"]
            level = row["level"]
            row_edit = SmartArtRowEdit(it.id, level, self.rows_container)
            row_edit.setText(it.text or "")
            row_edit.textChanged.connect(lambda txt, i_id=it.id: self._on_text_changed(i_id, txt))
            row_edit.item_key_pressed.connect(self._on_row_action)
            row_edit.installEventFilter(self)

            self.rows_layout.insertWidget(self.rows_layout.count() - 1, row_edit)
            self.row_inputs.append(row_edit)

            if self.active_item_id and it.id == self.active_item_id:
                focus_edit = row_edit

        if focus_edit:
            focus_edit.setFocus()
            focus_edit.setCursorPosition(len(focus_edit.text()))
        elif self.row_inputs:
            self.row_inputs[0].setFocus()

    def _on_text_changed(self, item_id: str, new_text: str) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        items = self._get_items()
        info = self.engine.locate(items, item_id)
        if info:
            info["item"].text = new_text
            self._save_and_relayout(items, refresh=False)

    def _on_row_action(self, action_name: str, event: Any) -> None:
        sender = self.sender()
        if not isinstance(sender, SmartArtRowEdit):
            return
        target_id = sender.item_id
        items = self._get_items()

        if action_name == "after":
            new_id = self.engine.add_after(items, target_id, "")
            self.active_item_id = new_id
            self._save_and_relayout(items, refresh=True)

        elif action_name == "promote":
            if self.engine.promote(items, target_id):
                self.active_item_id = target_id
                self._save_and_relayout(items, refresh=True)

        elif action_name == "demote":
            if self.engine.demote(items, target_id):
                self.active_item_id = target_id
                self._save_and_relayout(items, refresh=True)

        elif action_name == "up":
            if self.engine.move_up(items, target_id):
                self.active_item_id = target_id
                self._save_and_relayout(items, refresh=True)

        elif action_name == "down":
            if self.engine.move_down(items, target_id):
                self.active_item_id = target_id
                self._save_and_relayout(items, refresh=True)

        elif action_name == "remove":
            if len(self.row_inputs) > 1 and self.engine.remove_item(items, target_id):
                idx = self.row_inputs.index(sender)
                next_focus = self.row_inputs[max(0, idx - 1)].item_id
                self.active_item_id = next_focus
                self._save_and_relayout(items, refresh=True)

        elif action_name == "nav_up":
            idx = self.row_inputs.index(sender)
            if idx > 0:
                self.row_inputs[idx - 1].setFocus()

        elif action_name == "nav_down":
            idx = self.row_inputs.index(sender)
            if idx < len(self.row_inputs) - 1:
                self.row_inputs[idx + 1].setFocus()

    def _get_items(self) -> list[SmartArtItem]:
        if not self.current_shape or not self.current_shape.sa:
            return []
        raw = self.current_shape.sa.get("items", [])
        return [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw]

    def _save_and_relayout(self, items: list[SmartArtItem], refresh: bool = True) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        self.current_shape.sa["items"] = [it.to_dict() for it in items]
        relayout(self.current_shape)
        if refresh:
            self.refresh_rows()
        self.diagram_changed.emit(self.current_shape)

    def _on_add_after(self) -> None:
        items = self._get_items()
        tid = self.active_item_id or (items[-1].id if items else "")
        new_id = self.engine.add_after(items, tid, "") if tid else self.engine.blank("process", 1)[0].id
        self.active_item_id = new_id
        self._save_and_relayout(items, refresh=True)

    def _on_promote(self) -> None:
        if self.active_item_id:
            items = self._get_items()
            if self.engine.promote(items, self.active_item_id):
                self._save_and_relayout(items, refresh=True)

    def _on_demote(self) -> None:
        if self.active_item_id:
            items = self._get_items()
            if self.engine.demote(items, self.active_item_id):
                self._save_and_relayout(items, refresh=True)

    def _on_move_up(self) -> None:
        if self.active_item_id:
            items = self._get_items()
            if self.engine.move_up(items, self.active_item_id):
                self._save_and_relayout(items, refresh=True)

    def _on_move_down(self) -> None:
        if self.active_item_id:
            items = self._get_items()
            if self.engine.move_down(items, self.active_item_id):
                self._save_and_relayout(items, refresh=True)

    def _on_layout_changed(self, index: int) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        layout_id = self.cmb_layout.currentData()
        if layout_id and self.current_shape.sa.get("layout") != layout_id:
            self.current_shape.sa["layout"] = layout_id
            relayout(self.current_shape)
            self.refresh_rows()
            self.diagram_changed.emit(self.current_shape)

    def _on_colors_changed(self, index: int) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        colors_id = self.cmb_colors.currentData()
        if colors_id and self.current_shape.sa.get("colors") != colors_id:
            self.current_shape.sa["colors"] = colors_id
            relayout(self.current_shape)
            self.diagram_changed.emit(self.current_shape)

    def _on_style_changed(self, index: int) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        style_id = self.cmb_styles.currentData()
        if style_id and self.current_shape.sa.get("style") != style_id:
            self.current_shape.sa["style"] = style_id
            relayout(self.current_shape)
            self.diagram_changed.emit(self.current_shape)

    def _on_reset_graphic(self) -> None:
        if not self.current_shape or not self.current_shape.sa:
            return
        self.current_shape.sa["colors"] = "ocean"
        self.current_shape.sa["style"] = "moderate"
        relayout(self.current_shape)
        self.set_diagram(self.current_shape)
        self.diagram_changed.emit(self.current_shape)

    def _on_convert_to_shapes(self) -> None:
        if not self.current_shape:
            return
        to_shapes(self.current_shape)
        self.converted_to_shapes.emit(self.current_shape)
        self.set_diagram(None)

    def eventFilter(self, watched: Any, event: QEvent) -> bool:
        if event.type() == QEvent.Type.FocusIn and isinstance(watched, SmartArtRowEdit):
            self.active_item_id = watched.item_id
            self.item_selected.emit(watched.item_id)
        return super().eventFilter(watched, event)
