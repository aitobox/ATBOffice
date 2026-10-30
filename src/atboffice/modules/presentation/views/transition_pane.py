"""Slide Transition task pane for Lectern presentation editor.

Ported from PowerPoint 2003 and .vibeoffice/public/lectern/js/panes.js.
Provides transition effect selection (58 effects), speed, sound,
advance timings (on click and automatic after N seconds), apply to all slides,
and preview triggers with comprehensive i18n support.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
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
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.slide import Slide, Transition
from atboffice.modules.presentation.slideshow.transitions import (
    TRANSITION_CATALOGUE,
    TransitionEffect,
    safe_tr,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.models.presentation import Presentation


class SlideTransitionPane(QWidget):
    """Slide Transition task pane for customizing slide transitions and timing."""

    transitionChanged = Signal(object)  # Transition
    applyToAllRequested = Signal(object)  # Transition
    previewRequested = Signal()
    slideshowRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slide: Slide | None = None
        self.presentation: Presentation | None = None
        self._updating_ui: bool = False

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(240)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Header Title
        self.lbl_title = QLabel(self)
        font = self.lbl_title.font()
        font.setBold(True)
        font.setPointSize(10)
        self.lbl_title.setFont(font)
        main_layout.addWidget(self.lbl_title)

        # 2. Section Header: Apply to selected slides
        self.lbl_apply_to_sel = QLabel(self)
        self.lbl_apply_to_sel.setStyleSheet("color: #333333; font-weight: 500;")
        main_layout.addWidget(self.lbl_apply_to_sel)

        # 3. Transitions List Widget
        self.list_transitions = QListWidget(self)
        self.list_transitions.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_transitions.currentRowChanged.connect(self._on_transition_row_changed)
        main_layout.addWidget(self.list_transitions, stretch=1)

        # 4. Modify Transition GroupBox (Speed & Sound)
        self.grp_modify = QGroupBox(self)
        modify_layout = QVBoxLayout(self.grp_modify)
        modify_layout.setContentsMargins(6, 6, 6, 6)
        modify_layout.setSpacing(4)

        # Speed Row
        row_speed = QHBoxLayout()
        self.lbl_speed = QLabel(self)
        row_speed.addWidget(self.lbl_speed, stretch=1)
        self.combo_speed = QComboBox(self)
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        row_speed.addWidget(self.combo_speed, stretch=2)
        modify_layout.addLayout(row_speed)

        # Sound Row
        row_sound = QHBoxLayout()
        self.lbl_sound = QLabel(self)
        row_sound.addWidget(self.lbl_sound, stretch=1)
        self.combo_sound = QComboBox(self)
        row_sound.addWidget(self.combo_sound, stretch=2)
        modify_layout.addLayout(row_sound)

        main_layout.addWidget(self.grp_modify)

        # 5. Advance Slide GroupBox (On Click & Automatically After)
        self.grp_advance = QGroupBox(self)
        advance_layout = QVBoxLayout(self.grp_advance)
        advance_layout.setContentsMargins(6, 6, 6, 6)
        advance_layout.setSpacing(4)

        self.chk_on_click = QCheckBox(self)
        self.chk_on_click.setChecked(True)
        self.chk_on_click.toggled.connect(self._on_click_toggled)
        advance_layout.addWidget(self.chk_on_click)

        row_auto = QHBoxLayout()
        self.chk_auto_after = QCheckBox(self)
        self.chk_auto_after.toggled.connect(self._on_auto_toggled)
        row_auto.addWidget(self.chk_auto_after)

        self.spin_after_secs = QDoubleSpinBox(self)
        self.spin_after_secs.setRange(0.0, 3600.0)
        self.spin_after_secs.setSingleStep(0.5)
        self.spin_after_secs.setDecimals(1)
        self.spin_after_secs.setValue(0.0)
        self.spin_after_secs.setEnabled(False)
        self.spin_after_secs.valueChanged.connect(self._on_after_changed)
        row_auto.addWidget(self.spin_after_secs)
        advance_layout.addLayout(row_auto)

        main_layout.addWidget(self.grp_advance)

        # 6. Apply to All Slides Button
        self.btn_apply_to_all = QPushButton(self)
        self.btn_apply_to_all.clicked.connect(self._on_apply_to_all_clicked)
        main_layout.addWidget(self.btn_apply_to_all)

        # 7. Action Button Bar (Play & Slide Show)
        action_bar = QHBoxLayout()
        self.btn_play = QPushButton(self)
        self.btn_play.clicked.connect(self._on_play_clicked)
        action_bar.addWidget(self.btn_play)

        self.btn_slideshow = QPushButton(self)
        self.btn_slideshow.clicked.connect(self.slideshowRequested.emit)
        action_bar.addWidget(self.btn_slideshow)
        main_layout.addLayout(action_bar)

        # 8. AutoPreview Checkbox
        self.chk_auto_preview = QCheckBox(self)
        self.chk_auto_preview.setChecked(True)
        main_layout.addWidget(self.chk_auto_preview)

    def retranslate_ui(self) -> None:
        """Update all user-facing texts to current language locale."""
        self.lbl_title.setText(safe_tr("幻灯片切换"))
        self.lbl_apply_to_sel.setText(safe_tr("应用于所选幻灯片:"))
        self.grp_modify.setTitle(safe_tr("修改切换效果"))
        self.lbl_speed.setText(safe_tr("速度:"))
        self.lbl_sound.setText(safe_tr("声音:"))
        self.grp_advance.setTitle(safe_tr("换片方式"))
        self.chk_on_click.setText(safe_tr("单击鼠标时"))
        self.chk_auto_after.setText(safe_tr("自动换片时间"))
        self.spin_after_secs.setSuffix(" " + safe_tr("秒"))
        self.btn_apply_to_all.setText(safe_tr("应用于所有幻灯片"))
        self.btn_play.setText("▶ " + safe_tr("播放"))
        self.btn_slideshow.setText(safe_tr("幻灯片放映"))
        self.chk_auto_preview.setText(safe_tr("自动预览"))

        self._rebuild_speed_combo()
        self._rebuild_sound_combo()
        self._populate_transitions_list()

    def _rebuild_speed_combo(self) -> None:
        curr_val = self.combo_speed.currentData()
        self._updating_ui = True
        self.combo_speed.clear()
        self.combo_speed.addItem(safe_tr("慢速"), "slow")
        self.combo_speed.addItem(safe_tr("中速"), "med")
        self.combo_speed.addItem(safe_tr("快速"), "fast")
        if curr_val:
            idx = self.combo_speed.findData(curr_val)
            if idx >= 0:
                self.combo_speed.setCurrentIndex(idx)
            else:
                self.combo_speed.setCurrentIndex(2)  # default fast
        else:
            self.combo_speed.setCurrentIndex(2)
        self._updating_ui = False

    def _rebuild_sound_combo(self) -> None:
        self.combo_sound.clear()
        self.combo_sound.addItem(safe_tr("[无声音]"), "")
        self.combo_sound.setEnabled(False)

    def _populate_transitions_list(self) -> None:
        curr_eff_key = None
        if self.list_transitions.currentRow() >= 0:
            item = self.list_transitions.currentItem()
            if item:
                eff: TransitionEffect = item.data(Qt.ItemDataRole.UserRole)
                curr_eff_key = eff.key

        self._updating_ui = True
        self.list_transitions.clear()

        target_row = 0
        for i, eff in enumerate(TRANSITION_CATALOGUE):
            # Format text: e.g. "百叶窗 (水平)" or "无切换"
            label = safe_tr(eff.cn_name) if safe_tr(eff.cn_name) else eff.name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, eff)
            item.setToolTip(f"{eff.cn_name} ({eff.name})")
            self.list_transitions.addItem(item)

            if curr_eff_key and eff.key == curr_eff_key:
                target_row = i

        self._updating_ui = False

        if self.slide and self.slide.transition:
            self._sync_active_transition(self.slide.transition)
        elif self.list_transitions.count() > 0:
            self.list_transitions.setCurrentRow(target_row)

    def set_slide(self, slide: Slide | None) -> None:
        """Bind active slide context to the transition pane."""
        self.slide = slide
        if not slide:
            self._sync_active_transition(Transition(type="none"))
            return

        if not slide.transition:
            slide.transition = Transition(type="none")

        self._sync_active_transition(slide.transition)

    def set_presentation(self, presentation: Presentation | None) -> None:
        """Bind active presentation context for 'Apply to All Slides'."""
        self.presentation = presentation

    def _sync_active_transition(self, trans: Transition) -> None:
        """Synchronize UI controls with transition instance."""
        self._updating_ui = True

        # Find matching row in list
        best_row = 0
        for row in range(self.list_transitions.count()):
            it = self.list_transitions.item(row)
            eff: TransitionEffect = it.data(Qt.ItemDataRole.UserRole)
            if eff.type == trans.type:
                if trans.dir is not None and eff.dir != trans.dir:
                    continue
                if trans.thruBlk != eff.thruBlk:
                    continue
                if trans.spokes is not None and eff.spokes != trans.spokes:
                    continue
                if trans.orient is not None and eff.orient != trans.orient:
                    continue
                best_row = row
                break

        self.list_transitions.setCurrentRow(best_row)
        self.list_transitions.scrollToItem(
            self.list_transitions.item(best_row),
            QAbstractItemView.ScrollHint.EnsureVisible,
        )

        # Speed
        spd = trans.speed or "fast"
        idx = self.combo_speed.findData(spd)
        if idx >= 0:
            self.combo_speed.setCurrentIndex(idx)

        # Advance timings
        self.chk_on_click.setChecked(bool(trans.click))
        if trans.after is not None and trans.after > 0:
            self.chk_auto_after.setChecked(True)
            self.spin_after_secs.setEnabled(True)
            self.spin_after_secs.setValue(float(trans.after))
        else:
            self.chk_auto_after.setChecked(False)
            self.spin_after_secs.setEnabled(False)
            self.spin_after_secs.setValue(0.0)

        self._updating_ui = False

    def _on_transition_row_changed(self, row: int) -> None:
        if self._updating_ui or row < 0 or not self.slide:
            return

        it = self.list_transitions.item(row)
        if not it:
            return

        eff: TransitionEffect = it.data(Qt.ItemDataRole.UserRole)
        trans = self.slide.transition or Transition()

        trans.type = eff.type
        trans.dir = eff.dir
        trans.thruBlk = eff.thruBlk
        trans.spokes = eff.spokes
        trans.orient = eff.orient
        self.slide.transition = trans

        self.transitionChanged.emit(trans)

        if self.chk_auto_preview.isChecked():
            self.previewRequested.emit()

    def _on_speed_changed(self, idx: int) -> None:
        if self._updating_ui or idx < 0 or not self.slide:
            return
        spd = self.combo_speed.itemData(idx)
        if spd and self.slide.transition:
            self.slide.transition.speed = spd
            self.transitionChanged.emit(self.slide.transition)
            if self.chk_auto_preview.isChecked():
                self.previewRequested.emit()

    def _on_click_toggled(self, checked: bool) -> None:
        if self._updating_ui or not self.slide or not self.slide.transition:
            return
        self.slide.transition.click = checked
        self.transitionChanged.emit(self.slide.transition)

    def _on_auto_toggled(self, checked: bool) -> None:
        self.spin_after_secs.setEnabled(checked)
        if self._updating_ui or not self.slide or not self.slide.transition:
            return
        if checked:
            self.slide.transition.after = self.spin_after_secs.value()
        else:
            self.slide.transition.after = None
        self.transitionChanged.emit(self.slide.transition)

    def _on_after_changed(self, val: float) -> None:
        if self._updating_ui or not self.slide or not self.slide.transition:
            return
        if self.chk_auto_after.isChecked():
            self.slide.transition.after = val
            self.transitionChanged.emit(self.slide.transition)

    def _on_apply_to_all_clicked(self) -> None:
        """Apply active slide transition to all slides in presentation."""
        if not self.slide or not self.slide.transition:
            return
        source_trans = self.slide.transition
        if self.presentation and self.presentation.slides:
            for s in self.presentation.slides:
                s.transition = copy.deepcopy(source_trans)

        self.applyToAllRequested.emit(source_trans)

    def _on_play_clicked(self) -> None:
        self.previewRequested.emit()
