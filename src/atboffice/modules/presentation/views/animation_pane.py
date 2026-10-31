"""Custom Animation timing and task pane for Lectern presentation editor.

Ported from PowerPoint 2003 and .vibeoffice/public/lectern/js/panes.js.
Provides effect addition, attribute tuning (trigger, direction, speed),
list reordering, deletion, and preview controls with complete i18n support.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.slide import Animation, Slide
from atboffice.modules.presentation.slideshow.animations import (
    E_EMPH,
    E_ENTR,
    E_EXIT,
    E_PATH,
    SPEEDS,
    default_dir,
    effect_display_name,
    find_effect,
    safe_tr,
)

if TYPE_CHECKING:
    pass


def _make_star_icon(color_hex: str) -> QIcon:
    """Create a colored star badge icon for animation category distinction."""
    pix = QPixmap(16, 16)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color_hex))
    # Simple star or circle marker
    painter.drawEllipse(2, 2, 12, 12)
    painter.end()
    return QIcon(pix)


class AnimationPane(QWidget):
    """Custom Animation task pane for managing shape animation sequence and timings."""

    animationAdded = Signal(str, str)  # cls, eff
    animationRemoved = Signal(str)  # anim_id
    animationModified = Signal(str, str, object)  # anim_id, property_key, value
    animationReordered = Signal(int, int)  # old_idx, new_idx
    playRequested = Signal(str)  # anim_id (or "" for entire slide)
    slideshowRequested = Signal()
    shapeSelectionRequested = Signal(str)  # shape_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slide: Slide | None = None
        self.selected_shape_ids: list[str] = []
        self._selected_anim_id: str | None = None
        self._updating_ui: bool = False

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(240)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Title Label
        self.lbl_title = QLabel(self)
        font = self.lbl_title.font()
        font.setBold(True)
        font.setPointSize(10)
        self.lbl_title.setFont(font)
        main_layout.addWidget(self.lbl_title)

        # Top Button Bar (Add Effect & Remove)
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(4)

        self.btn_add_effect = QPushButton(self)
        self.btn_add_effect.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.menu_add_effect = QMenu(self)
        self.btn_add_effect.setMenu(self.menu_add_effect)
        self.btn_add_effect.clicked.connect(self.btn_add_effect.showMenu)
        btn_bar.addWidget(self.btn_add_effect, stretch=3)

        self.btn_remove = QPushButton(self)
        self.btn_remove.setEnabled(False)
        self.btn_remove.clicked.connect(self._on_remove_clicked)
        btn_bar.addWidget(self.btn_remove, stretch=2)

        main_layout.addLayout(btn_bar)

        # Modify Property Group Box
        self.grp_modify = QGroupBox(self)
        modify_layout = QVBoxLayout(self.grp_modify)
        modify_layout.setContentsMargins(6, 6, 6, 6)
        modify_layout.setSpacing(4)

        # Start Trigger Row
        row_start = QHBoxLayout()
        self.lbl_start = QLabel(self)
        row_start.addWidget(self.lbl_start, stretch=1)
        self.combo_start = QComboBox(self)
        self.combo_start.currentIndexChanged.connect(self._on_start_changed)
        row_start.addWidget(self.combo_start, stretch=2)
        modify_layout.addLayout(row_start)

        # Direction Row
        row_dir = QHBoxLayout()
        self.lbl_dir = QLabel(self)
        row_dir.addWidget(self.lbl_dir, stretch=1)
        self.combo_dir = QComboBox(self)
        self.combo_dir.currentIndexChanged.connect(self._on_dir_changed)
        row_dir.addWidget(self.combo_dir, stretch=2)
        modify_layout.addLayout(row_dir)

        # Speed Row
        row_speed = QHBoxLayout()
        self.lbl_speed = QLabel(self)
        row_speed.addWidget(self.lbl_speed, stretch=1)
        self.combo_speed = QComboBox(self)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        row_speed.addWidget(self.combo_speed, stretch=2)
        modify_layout.addLayout(row_speed)

        # Delay Row
        row_delay = QHBoxLayout()
        self.lbl_delay = QLabel(self)
        row_delay.addWidget(self.lbl_delay, stretch=1)
        self.spin_delay = QDoubleSpinBox(self)
        self.spin_delay.setRange(0.0, 60.0)
        self.spin_delay.setSingleStep(0.5)
        self.spin_delay.setDecimals(1)
        self.spin_delay.setValue(0.0)
        self.spin_delay.valueChanged.connect(self._on_delay_changed)
        row_delay.addWidget(self.spin_delay, stretch=2)
        modify_layout.addLayout(row_delay)

        main_layout.addWidget(self.grp_modify)

        # Animation Sequence List
        self.list_anims = QListWidget(self)
        self.list_anims.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_anims.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_anims.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list_anims.model().rowsMoved.connect(self._on_rows_moved)
        self.list_anims.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_anims.customContextMenuRequested.connect(self._on_context_menu)
        self.list_anims.currentRowChanged.connect(self._on_list_row_changed)
        self.list_anims.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.list_anims, stretch=1)

        # Empty State Note
        self.lbl_empty = QLabel(self)
        self.lbl_empty.setWordWrap(True)
        self.lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty.setStyleSheet("color: #777777; font-size: 11px; padding: 10px;")
        main_layout.addWidget(self.lbl_empty)

        # Re-Order Toolbar
        reorder_bar = QHBoxLayout()
        self.lbl_reorder = QLabel(self)
        reorder_bar.addWidget(self.lbl_reorder)
        reorder_bar.addStretch()

        self.btn_move_up = QPushButton("▲", self)
        self.btn_move_up.setFixedWidth(32)
        self.btn_move_up.setEnabled(False)
        self.btn_move_up.clicked.connect(lambda: self._move_animation(-1))
        reorder_bar.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("▼", self)
        self.btn_move_down.setFixedWidth(32)
        self.btn_move_down.setEnabled(False)
        self.btn_move_down.clicked.connect(lambda: self._move_animation(1))
        reorder_bar.addWidget(self.btn_move_down)

        main_layout.addLayout(reorder_bar)

        # Play & Slideshow Action Bar
        play_bar = QHBoxLayout()
        self.btn_play = QPushButton(self)
        self.btn_play.clicked.connect(self._on_play_clicked)
        play_bar.addWidget(self.btn_play)

        self.btn_slideshow = QPushButton(self)
        self.btn_slideshow.clicked.connect(self.slideshowRequested.emit)
        play_bar.addWidget(self.btn_slideshow)
        main_layout.addLayout(play_bar)

        # AutoPreview Checkbox
        self.chk_auto_preview = QCheckBox(self)
        self.chk_auto_preview.setChecked(True)
        main_layout.addWidget(self.chk_auto_preview)

    def retranslate_ui(self) -> None:
        """Update all user-facing texts to current language locale."""
        self.lbl_title.setText(safe_tr("Custom Animation"))
        self.btn_add_effect.setText(safe_tr("Add Effect") + " ▼")
        self.btn_remove.setText(safe_tr("Remove"))
        self.grp_modify.setTitle(safe_tr("Modify effect"))
        self.lbl_start.setText(safe_tr("Start:"))
        self.lbl_dir.setText(safe_tr("Direction:"))
        self.lbl_speed.setText(safe_tr("Speed:"))
        self.lbl_delay.setText(safe_tr("Delay:"))
        self.spin_delay.setSuffix(" " + safe_tr("s"))
        self.lbl_reorder.setText(safe_tr("Re-Order"))
        self.btn_play.setText("▶ " + safe_tr("Play"))
        self.btn_slideshow.setText(safe_tr("Slide Show"))
        self.chk_auto_preview.setText(safe_tr("AutoPreview"))
        self.lbl_empty.setText(
            safe_tr("Select an element of the slide, then click 'Add Effect' to add animation.")
        )

        self._rebuild_menus()
        self._rebuild_start_combo()
        self._rebuild_speed_combo()
        self._refresh_list()

    def _rebuild_menus(self) -> None:
        """Populate the 4 categories of Add Effect cascading menus."""
        self.menu_add_effect.clear()
        self._category_menus: list[QMenu] = []

        # Category icons and colors
        categories = [
            ("entr", "Entrance", "#2f9a3a", E_ENTR),
            ("emph", "Emphasis", "#c9a100", E_EMPH),
            ("exit", "Exit", "#d33a2c", E_EXIT),
            ("path", "Motion Paths", "#555555", E_PATH),
        ]

        for cls_key, cls_label, col_hex, effects in categories:
            sub = QMenu(safe_tr(cls_label), self.menu_add_effect)
            sub.setIcon(_make_star_icon(col_hex))
            self.menu_add_effect.addMenu(sub)
            self._category_menus.append(sub)
            for eff_def in effects:
                act = sub.addAction(safe_tr(eff_def.name))
                act.setData((cls_key, eff_def.key))
                act.triggered.connect(
                    lambda checked=False, c=cls_key, e=eff_def.key: self._on_add_effect_chosen(c, e)
                )

    def _rebuild_start_combo(self) -> None:
        curr_val = self.combo_start.currentData()
        self._updating_ui = True
        self.combo_start.clear()
        self.combo_start.addItem(safe_tr("On Click"), "click")
        self.combo_start.addItem(safe_tr("With Previous"), "with")
        self.combo_start.addItem(safe_tr("After Previous"), "after")
        if curr_val:
            idx = self.combo_start.findData(curr_val)
            if idx >= 0:
                self.combo_start.setCurrentIndex(idx)
        self._updating_ui = False

    def _rebuild_speed_combo(self) -> None:
        curr_val = self.combo_speed.currentData()
        self._updating_ui = True
        self.combo_speed.clear()
        for label, ms in SPEEDS:
            self.combo_speed.addItem(safe_tr(label), ms)
        if curr_val:
            idx = self.combo_speed.findData(curr_val)
            if idx >= 0:
                self.combo_speed.setCurrentIndex(idx)
        self._updating_ui = False

    def set_slide(
        self,
        slide: Slide | None,
        selected_shape_ids: list[str] | None = None,
    ) -> None:
        """Bind active slide and selected shape context to the animation pane."""
        self.slide = slide
        self.selected_shape_ids = list(selected_shape_ids or [])
        self._refresh_list()

    def set_selected_shapes(self, shape_ids: list[str] | None = None) -> None:
        """Update selected shape context and highlight matching animation item."""
        self.selected_shape_ids = list(shape_ids or [])
        if not self.selected_shape_ids or not self.slide:
            return
        target_sid = self.selected_shape_ids[0]
        for row in range(self.list_anims.count()):
            it = self.list_anims.item(row)
            if not it:
                continue
            aid = it.data(Qt.ItemDataRole.UserRole)
            for a in self.slide.animations:
                if a.id == aid and a.sid == target_sid:
                    self.list_anims.setCurrentRow(row)
                    return

    def select_animation(self, anim_id: str | None) -> None:
        """Select an animation item in the sequence list."""
        self._selected_anim_id = anim_id
        if not anim_id:
            self.list_anims.clearSelection()
            self._update_property_controls(None)
            return

        for row in range(self.list_anims.count()):
            it = self.list_anims.item(row)
            if it and it.data(Qt.ItemDataRole.UserRole) == anim_id:
                self.list_anims.setCurrentRow(row)
                break

    def _refresh_list(self) -> None:
        """Refresh the animation list and control enable states."""
        self._updating_ui = True
        self.list_anims.clear()

        if not self.slide or not self.slide.animations:
            self.lbl_empty.setVisible(True)
            self.list_anims.setVisible(False)
            self.btn_remove.setEnabled(False)
            self.btn_move_up.setEnabled(False)
            self.btn_move_down.setEnabled(False)
            self.grp_modify.setEnabled(False)
            self._updating_ui = False
            return

        self.lbl_empty.setVisible(False)
        self.list_anims.setVisible(True)

        click_step = 0
        target_row = -1

        for i, a in enumerate(self.slide.animations):
            if a.start == "click" or i == 0:
                click_step += 1 if a.start == "click" else (1 if i == 0 else 0)

            sh = self.slide.find_shape(a.sid)
            sh_name = sh.name if sh else "?"
            sh_snippet = ""
            if sh and sh.text and sh.text.plain_text.strip():
                snippet = sh.text.plain_text.strip().replace("\n", " ")
                sh_snippet = f": {snippet[:20]}"

            eff_name = effect_display_name(a.cls, a.eff)
            step_num_str = f"[{click_step}] " if a.start == "click" else "     "

            color_hex = {
                "entr": "#2f9a3a",
                "emph": "#c9a100",
                "exit": "#d33a2c",
                "path": "#555555",
            }.get(a.cls, "#555555")

            label_text = f"{step_num_str}{eff_name} — {sh_name}{sh_snippet}"
            item = QListWidgetItem(_make_star_icon(color_hex), label_text)
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.list_anims.addItem(item)

            if a.id == self._selected_anim_id:
                target_row = i

        self._updating_ui = False

        if target_row >= 0:
            self.list_anims.setCurrentRow(target_row)
        elif self.list_anims.count() > 0:
            self.list_anims.setCurrentRow(0)
        else:
            self._update_property_controls(None)

    def _get_selected_animation(self) -> Animation | None:
        if not self.slide or not self._selected_anim_id:
            return None
        for a in self.slide.animations:
            if a.id == self._selected_anim_id:
                return a
        return None

    def _update_property_controls(self, anim: Animation | None) -> None:
        """Synchronize the modify property combo boxes with selected animation."""
        self._updating_ui = True
        if not anim:
            self.grp_modify.setEnabled(False)
            self.btn_remove.setEnabled(False)
            self.btn_move_up.setEnabled(False)
            self.btn_move_down.setEnabled(False)
            self.spin_delay.setEnabled(False)
            self.spin_delay.setValue(0.0)
            self._updating_ui = False
            return

        self.grp_modify.setEnabled(True)
        self.btn_remove.setEnabled(True)

        cur_row = self.list_anims.currentRow()
        self.btn_move_up.setEnabled(cur_row > 0)
        self.btn_move_down.setEnabled(cur_row >= 0 and cur_row < self.list_anims.count() - 1)

        eff_title = effect_display_name(anim.cls, anim.eff)
        self.grp_modify.setTitle(f"{safe_tr('Modify:')} {eff_title}")

        # Start trigger
        start_idx = self.combo_start.findData(anim.start)
        if start_idx >= 0:
            self.combo_start.setCurrentIndex(start_idx)

        # Directions
        eff_def = find_effect(anim.cls, anim.eff)
        self.combo_dir.clear()
        if eff_def and eff_def.dirs:
            self.combo_dir.setEnabled(True)
            for d_val, d_label, _ in eff_def.dirs:
                self.combo_dir.addItem(safe_tr(d_label), d_val)
            dir_idx = self.combo_dir.findData(anim.dir)
            if dir_idx >= 0:
                self.combo_dir.setCurrentIndex(dir_idx)
            elif self.combo_dir.count() > 0:
                self.combo_dir.setCurrentIndex(0)
        else:
            self.combo_dir.setEnabled(False)

        # Speed
        self.combo_speed.setEnabled(anim.eff not in ("appear", "disappear"))
        best_diff = float("inf")
        best_idx = 0
        for i in range(self.combo_speed.count()):
            ms = self.combo_speed.itemData(i)
            diff = abs(ms - anim.dur)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        self.combo_speed.setCurrentIndex(best_idx)

        # Delay
        self.spin_delay.setEnabled(True)
        self.spin_delay.setValue(anim.delay / 1000.0 if anim.delay else 0.0)

        self._updating_ui = False

    def _on_add_effect_chosen(self, cls_key: str, eff_key: str) -> None:
        """Handle user selecting an effect from the Add Effect menu."""
        if not self.slide:
            return
        # If no shape is explicitly selected, pick first shape on slide
        target_shape_id = self.selected_shape_ids[0] if self.selected_shape_ids else None
        if not target_shape_id and self.slide.shapes:
            target_shape_id = self.slide.shapes[0].id

        if not target_shape_id:
            return

        default_dur = (
            2000
            if cls_key in ("emph", "path")
            else (0 if eff_key in ("appear", "disappear") else 500)
        )
        new_anim = Animation(
            id=f"a_{uuid.uuid4().hex[:6]}",
            sid=target_shape_id,
            cls=cls_key,
            eff=eff_key,
            dir=default_dir(cls_key, eff_key),
            start="click",
            dur=default_dur,
            delay=0,
            by="all",
        )
        self.slide.animations.append(new_anim)
        self._selected_anim_id = new_anim.id
        self._refresh_list()
        self.animationAdded.emit(cls_key, eff_key)

        if self.chk_auto_preview.isChecked():
            self.playRequested.emit(new_anim.id)

    def _on_remove_clicked(self) -> None:
        """Remove the selected animation effect."""
        if not self.slide or not self._selected_anim_id:
            return
        anim_id = self._selected_anim_id
        self.slide.animations = [a for a in self.slide.animations if a.id != anim_id]
        self._selected_anim_id = None
        self._refresh_list()
        self.animationRemoved.emit(anim_id)

    def _move_animation(self, offset: int) -> None:
        """Re-order selected animation up (-1) or down (+1)."""
        if not self.slide:
            return
        cur_row = self.list_anims.currentRow()
        new_row = cur_row + offset
        if 0 <= new_row < len(self.slide.animations):
            anims = self.slide.animations
            anims[cur_row], anims[new_row] = anims[new_row], anims[cur_row]
            self.animationReordered.emit(cur_row, new_row)
            self._refresh_list()
            self.list_anims.setCurrentRow(new_row)

    def _on_start_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0:
            return
        anim = self._get_selected_animation()
        if not anim:
            return
        val = self.combo_start.itemData(idx)
        if val and anim.start != val:
            anim.start = val
            self.animationModified.emit(anim.id, "start", val)
            self._refresh_list()

    def _on_dir_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0:
            return
        anim = self._get_selected_animation()
        if not anim:
            return
        val = self.combo_dir.itemData(idx)
        if val is not None and anim.dir != val:
            anim.dir = val
            self.animationModified.emit(anim.id, "dir", val)
            if self.chk_auto_preview.isChecked():
                self.playRequested.emit(anim.id)

    def _on_speed_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0:
            return
        anim = self._get_selected_animation()
        if not anim:
            return
        val = self.combo_speed.itemData(idx)
        if val and anim.dur != val:
            anim.dur = val
            self.animationModified.emit(anim.id, "dur", val)
            if self.chk_auto_preview.isChecked():
                self.playRequested.emit(anim.id)

    def _on_delay_changed(self, val: float) -> None:
        if self._updating_ui:
            return
        anim = self._get_selected_animation()
        if not anim:
            return
        ms = int(round(val * 1000))
        if anim.delay != ms:
            anim.delay = ms
            self.animationModified.emit(anim.id, "delay", ms)

    def _on_rows_moved(
        self, parent: object, start: int, end: int, destination: object, row: int
    ) -> None:
        if self._updating_ui or not self.slide:
            return
        new_order_ids = [
            self.list_anims.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_anims.count())
        ]
        id_to_anim = {a.id: a for a in self.slide.animations}
        self.slide.animations = [id_to_anim[aid] for aid in new_order_ids if aid in id_to_anim]
        self.animationReordered.emit(start, row)

    def _on_list_row_changed(self, row: int) -> None:
        if self._updating_ui or row < 0:
            return
        it = self.list_anims.item(row)
        if it:
            anim_id = it.data(Qt.ItemDataRole.UserRole)
            self._selected_anim_id = anim_id
            anim = self._get_selected_animation()
            self._update_property_controls(anim)
            if anim and anim.sid:
                self.shapeSelectionRequested.emit(anim.sid)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if item:
            anim_id = item.data(Qt.ItemDataRole.UserRole)
            self.playRequested.emit(anim_id)

    def _on_play_clicked(self) -> None:
        anim_id = self._selected_anim_id or ""
        self.playRequested.emit(anim_id)

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.list_anims.itemAt(pos)
        if not item or not self.slide:
            return
        anim_id = item.data(Qt.ItemDataRole.UserRole)
        self.select_animation(anim_id)
        anim = self._get_selected_animation()
        if not anim:
            return

        menu = QMenu(self)

        act_click = menu.addAction(safe_tr("Start On Click"))
        act_click.setCheckable(True)
        act_click.setChecked(anim.start == "click")
        act_click.triggered.connect(lambda: self._set_trigger_and_refresh("click"))

        act_with = menu.addAction(safe_tr("Start With Previous"))
        act_with.setCheckable(True)
        act_with.setChecked(anim.start == "with")
        act_with.triggered.connect(lambda: self._set_trigger_and_refresh("with"))

        act_after = menu.addAction(safe_tr("Start After Previous"))
        act_after.setCheckable(True)
        act_after.setChecked(anim.start == "after")
        act_after.triggered.connect(lambda: self._set_trigger_and_refresh("after"))

        menu.addSeparator()

        act_play = menu.addAction(safe_tr("Play"))
        act_play.triggered.connect(lambda: self.playRequested.emit(anim.id))

        act_remove = menu.addAction(safe_tr("Remove"))
        act_remove.triggered.connect(self._on_remove_clicked)

        menu.exec(self.list_anims.mapToGlobal(pos))

    def _set_trigger_and_refresh(self, trigger: str) -> None:
        anim = self._get_selected_animation()
        if anim:
            anim.start = trigger
            self.animationModified.emit(anim.id, "start", trigger)
            self._refresh_list()
