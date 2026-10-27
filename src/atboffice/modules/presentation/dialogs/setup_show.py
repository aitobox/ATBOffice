"""PowerPoint 2003 Classic Set Up Show Dialog for Lectern."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.dialogs.format_shape import ColorButton
from atboffice.modules.presentation.models.presentation import Presentation, SlideShowSettings


def safe_tr(text: str) -> str:
    """Translate UI text safely for SetupShowDialog."""
    return QCoreApplication.translate("SetupShowDialog", text)


class SetupShowDialog(QDialog):
    """Set Up Show dialog configuring slide show display modes and options."""

    def __init__(
        self,
        presentation: Presentation,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.settings: SlideShowSettings = presentation.show or SlideShowSettings()
        self.total_slides = max(1, len(presentation.slides))
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("Set Up Show"))
        self.resize(540, 380)

        main_layout = QVBoxLayout(self)
        cols_layout = QHBoxLayout()

        # Left Column: Show type & Show options
        left_col = QVBoxLayout()

        # 1. Show type
        self.type_group = QGroupBox(safe_tr("Show type"))
        type_layout = QVBoxLayout(self.type_group)

        self.speaker_radio = QRadioButton(safe_tr("Presented by a speaker (full screen)"))
        self.window_radio = QRadioButton(safe_tr("Browsed by an individual (window)"))
        self.kiosk_radio = QRadioButton(safe_tr("Browsed at a kiosk (full screen)"))

        self.type_button_group = QButtonGroup(self)
        self.type_button_group.addButton(self.speaker_radio, 1)
        self.type_button_group.addButton(self.window_radio, 2)
        self.type_button_group.addButton(self.kiosk_radio, 3)

        is_window = getattr(self.settings, "window_mode", False)
        if self.settings.kiosk:
            self.kiosk_radio.setChecked(True)
        elif is_window:
            self.window_radio.setChecked(True)
        else:
            self.speaker_radio.setChecked(True)

        self.speaker_radio.toggled.connect(self._on_type_changed)
        self.window_radio.toggled.connect(self._on_type_changed)
        self.kiosk_radio.toggled.connect(self._on_type_changed)

        type_layout.addWidget(self.speaker_radio)
        type_layout.addWidget(self.window_radio)
        type_layout.addWidget(self.kiosk_radio)
        left_col.addWidget(self.type_group)

        # 2. Show options
        self.options_group = QGroupBox(safe_tr("Show options"))
        opt_layout = QVBoxLayout(self.options_group)

        self.loop_chk = QCheckBox(safe_tr("Loop continuously until 'Esc'"))
        self.loop_chk.setChecked(bool(self.settings.loop or self.settings.kiosk))

        self.no_narration_chk = QCheckBox(safe_tr("Show without narration"))
        self.no_narration_chk.setChecked(bool(getattr(self.settings, "no_narration", False)))

        self.no_anim_chk = QCheckBox(safe_tr("Show without animation"))
        self.no_anim_chk.setChecked(bool(self.settings.no_anim))

        pen_layout = QHBoxLayout()
        self.pen_color_lbl = QLabel(safe_tr("Pen color:"))
        init_pen = self.settings.pen_color or "#FF0000"
        self.pen_color_btn = ColorButton(init_pen)
        pen_layout.addWidget(self.pen_color_lbl)
        pen_layout.addWidget(self.pen_color_btn)
        pen_layout.addStretch()

        opt_layout.addWidget(self.loop_chk)
        opt_layout.addWidget(self.no_narration_chk)
        opt_layout.addWidget(self.no_anim_chk)
        opt_layout.addLayout(pen_layout)
        left_col.addWidget(self.options_group)

        cols_layout.addLayout(left_col)

        # Right Column: Show slides & Advance slides
        right_col = QVBoxLayout()

        # 3. Show slides
        self.slides_group = QGroupBox(safe_tr("Show slides"))
        slides_layout = QVBoxLayout(self.slides_group)

        self.all_slides_radio = QRadioButton(safe_tr("All"))
        self.from_to_radio = QRadioButton(safe_tr("From:"))

        self.slides_button_group = QButtonGroup(self)
        self.slides_button_group.addButton(self.all_slides_radio, 1)
        self.slides_button_group.addButton(self.from_to_radio, 2)

        has_rng = bool(self.settings.from_slide and self.settings.to_slide)
        if has_rng:
            self.from_to_radio.setChecked(True)
        else:
            self.all_slides_radio.setChecked(True)

        range_layout = QHBoxLayout()
        self.from_spin = QSpinBox()
        self.from_spin.setRange(1, self.total_slides)
        self.from_spin.setValue(self.settings.from_slide or 1)

        self.to_lbl = QLabel(safe_tr("To:"))
        self.to_spin = QSpinBox()
        self.to_spin.setRange(1, self.total_slides)
        self.to_spin.setValue(self.settings.to_slide or self.total_slides)

        range_layout.addWidget(self.from_to_radio)
        range_layout.addWidget(self.from_spin)
        range_layout.addWidget(self.to_lbl)
        range_layout.addWidget(self.to_spin)

        self.all_slides_radio.toggled.connect(self._sync_range_enabled)
        self.from_to_radio.toggled.connect(self._sync_range_enabled)
        self._sync_range_enabled()

        slides_layout.addWidget(self.all_slides_radio)
        slides_layout.addLayout(range_layout)
        right_col.addWidget(self.slides_group)

        # 4. Advance slides
        self.adv_group = QGroupBox(safe_tr("Advance slides"))
        adv_layout = QVBoxLayout(self.adv_group)

        self.manual_adv_radio = QRadioButton(safe_tr("Manually"))
        self.timings_adv_radio = QRadioButton(safe_tr("Using timings, if present"))

        self.adv_button_group = QButtonGroup(self)
        self.adv_button_group.addButton(self.manual_adv_radio, 1)
        self.adv_button_group.addButton(self.timings_adv_radio, 2)

        if self.settings.use_timings is False:
            self.manual_adv_radio.setChecked(True)
        else:
            self.timings_adv_radio.setChecked(True)

        adv_layout.addWidget(self.manual_adv_radio)
        adv_layout.addWidget(self.timings_adv_radio)
        right_col.addWidget(self.adv_group)

        cols_layout.addLayout(right_col)
        main_layout.addLayout(cols_layout)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _on_type_changed(self) -> None:
        if self.kiosk_radio.isChecked():
            self.loop_chk.setChecked(True)
            self.loop_chk.setEnabled(False)
        else:
            self.loop_chk.setEnabled(True)

    def _sync_range_enabled(self) -> None:
        enabled = self.from_to_radio.isChecked()
        self.from_spin.setEnabled(enabled)
        self.to_lbl.setEnabled(enabled)
        self.to_spin.setEnabled(enabled)

    def apply_changes(self) -> None:
        """Apply dialog input changes to presentation settings."""
        is_kiosk = self.kiosk_radio.isChecked()
        is_window = self.window_radio.isChecked()

        self.settings.kiosk = is_kiosk
        setattr(self.settings, "window_mode", is_window)
        self.settings.loop = self.loop_chk.isChecked() or is_kiosk
        self.settings.no_anim = self.no_anim_chk.isChecked()
        setattr(self.settings, "no_narration", self.no_narration_chk.isChecked())
        self.settings.pen_color = self.pen_color_btn.get_color()

        if self.from_to_radio.isChecked():
            f = self.from_spin.value()
            t = self.to_spin.value()
            if f > t:
                f, t = t, f
            self.settings.from_slide = f
            self.settings.to_slide = t
        else:
            self.settings.from_slide = 0
            self.settings.to_slide = 0

        self.settings.use_timings = self.timings_adv_radio.isChecked()

    def _on_accept(self) -> None:
        self.apply_changes()
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("Set Up Show"))
        self.type_group.setTitle(safe_tr("Show type"))
        self.speaker_radio.setText(safe_tr("Presented by a speaker (full screen)"))
        self.window_radio.setText(safe_tr("Browsed by an individual (window)"))
        self.kiosk_radio.setText(safe_tr("Browsed at a kiosk (full screen)"))
        self.options_group.setTitle(safe_tr("Show options"))
        self.loop_chk.setText(safe_tr("Loop continuously until 'Esc'"))
        self.no_narration_chk.setText(safe_tr("Show without narration"))
        self.no_anim_chk.setText(safe_tr("Show without animation"))
        self.pen_color_lbl.setText(safe_tr("Pen color:"))
        self.slides_group.setTitle(safe_tr("Show slides"))
        self.all_slides_radio.setText(safe_tr("All"))
        self.from_to_radio.setText(safe_tr("From:"))
        self.to_lbl.setText(safe_tr("To:"))
        self.adv_group.setTitle(safe_tr("Advance slides"))
        self.manual_adv_radio.setText(safe_tr("Manually"))
        self.timings_adv_radio.setText(safe_tr("Using timings, if present"))
