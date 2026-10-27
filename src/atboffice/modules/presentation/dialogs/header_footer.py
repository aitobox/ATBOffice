"""PowerPoint 2003 Classic Header and Footer Dialog for Lectern."""

from __future__ import annotations

import datetime

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.presentation.models.presentation import (
    HeaderFooterSettings,
    Presentation,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for HeaderFooterDialog."""
    return QCoreApplication.translate("HeaderFooterDialog", text)


class HeaderFooterDialog(QDialog):
    """Header and Footer Dialog configuring date, footer text, and slide number."""

    def __init__(
        self,
        presentation: Presentation,
        slide_idx: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.presentation = presentation
        self.slide_idx = slide_idx
        self.slide = (
            presentation.slides[slide_idx]
            if presentation.slides and 0 <= slide_idx < len(presentation.slides)
            else None
        )
        self.hf: HeaderFooterSettings = copy_hf(
            getattr(self.slide, "hf", None) or presentation.hf or HeaderFooterSettings()
        )
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("Header and Footer"))
        self.resize(460, 360)

        main_layout = QHBoxLayout(self)

        # Content column
        content_col = QVBoxLayout()
        self.inc_group = QGroupBox(safe_tr("Include on slide"))
        inc_layout = QVBoxLayout(self.inc_group)

        # 1. Date & Time
        self.dt_chk = QCheckBox(safe_tr("Date and time"))
        self.dt_chk.setChecked(bool(self.hf.dt))
        self.dt_chk.toggled.connect(self._sync_enabled)
        inc_layout.addWidget(self.dt_chk)

        dt_inner = QVBoxLayout()
        dt_inner.setContentsMargins(24, 0, 0, 0)

        self.dt_auto_radio = QRadioButton(safe_tr("Update automatically"))
        self.dt_auto_radio.setChecked(bool(self.hf.dt_auto))
        self.dt_fmt_combo = QComboBox()
        now = datetime.datetime.now()
        self.dt_fmt_combo.addItem(now.strftime("%m/%d/%Y"), "datetime1")
        self.dt_fmt_combo.addItem(now.strftime("%A, %B %d, %Y"), "datetime2")
        self.dt_fmt_combo.addItem(now.strftime("%Y-%m-%d"), "datetime3")

        idx = self.dt_fmt_combo.findData(self.hf.dt_fmt)
        if idx >= 0:
            self.dt_fmt_combo.setCurrentIndex(idx)

        self.dt_fixed_radio = QRadioButton(safe_tr("Fixed"))
        self.dt_fixed_radio.setChecked(not self.hf.dt_auto)
        self.dt_fixed_edit = QLineEdit(self.hf.dt_text or now.strftime("%m/%d/%Y"))

        self.dt_btn_group = QButtonGroup(self)
        self.dt_btn_group.addButton(self.dt_auto_radio, 1)
        self.dt_btn_group.addButton(self.dt_fixed_radio, 2)
        self.dt_auto_radio.toggled.connect(self._sync_enabled)
        self.dt_fixed_radio.toggled.connect(self._sync_enabled)

        dt_inner.addWidget(self.dt_auto_radio)
        dt_inner.addWidget(self.dt_fmt_combo)
        dt_inner.addWidget(self.dt_fixed_radio)
        dt_inner.addWidget(self.dt_fixed_edit)
        inc_layout.addLayout(dt_inner)

        # 2. Slide Number
        self.num_chk = QCheckBox(safe_tr("Slide number"))
        self.num_chk.setChecked(bool(self.hf.num))
        inc_layout.addWidget(self.num_chk)

        # 3. Footer
        self.ftr_chk = QCheckBox(safe_tr("Footer"))
        self.ftr_chk.setChecked(bool(self.hf.ftr))
        self.ftr_chk.toggled.connect(self._sync_enabled)
        inc_layout.addWidget(self.ftr_chk)

        ftr_inner = QVBoxLayout()
        ftr_inner.setContentsMargins(24, 0, 0, 0)
        self.ftr_edit = QLineEdit(self.hf.ftr_text or "")
        ftr_inner.addWidget(self.ftr_edit)
        inc_layout.addLayout(ftr_inner)

        # 4. Don't show on title slide
        self.not_on_title_chk = QCheckBox(safe_tr("Don't show on title slide"))
        self.not_on_title_chk.setChecked(bool(self.hf.not_on_title))
        inc_layout.addWidget(self.not_on_title_chk)

        content_col.addWidget(self.inc_group)
        main_layout.addLayout(content_col)

        # Buttons column
        btn_col = QVBoxLayout()
        self.apply_all_btn = QPushButton(safe_tr("Apply to &All"))
        self.apply_all_btn.clicked.connect(self.apply_to_all)
        self.apply_btn = QPushButton(safe_tr("&Apply"))
        self.apply_btn.clicked.connect(self.apply_current)
        self.cancel_btn = QPushButton(safe_tr("Cancel"))
        self.cancel_btn.clicked.connect(self.reject)

        btn_col.addWidget(self.apply_all_btn)
        btn_col.addWidget(self.apply_btn)
        btn_col.addWidget(self.cancel_btn)
        btn_col.addStretch()
        main_layout.addLayout(btn_col)

        self._sync_enabled()

    def _sync_enabled(self) -> None:
        dt_on = self.dt_chk.isChecked()
        self.dt_auto_radio.setEnabled(dt_on)
        self.dt_fixed_radio.setEnabled(dt_on)
        self.dt_fmt_combo.setEnabled(dt_on and self.dt_auto_radio.isChecked())
        self.dt_fixed_edit.setEnabled(dt_on and self.dt_fixed_radio.isChecked())

        ftr_on = self.ftr_chk.isChecked()
        self.ftr_edit.setEnabled(ftr_on)

    def _read_settings(self) -> HeaderFooterSettings:
        return HeaderFooterSettings(
            dt=self.dt_chk.isChecked(),
            dt_auto=self.dt_auto_radio.isChecked(),
            dt_fmt=self.dt_fmt_combo.currentData() or "datetime1",
            dt_text=self.dt_fixed_edit.text().strip(),
            num=self.num_chk.isChecked(),
            ftr=self.ftr_chk.isChecked(),
            ftr_text=self.ftr_edit.text().strip(),
            not_on_title=self.not_on_title_chk.isChecked(),
        )

    def apply_to_all(self) -> None:
        """Apply header and footer settings across the entire presentation."""
        settings = self._read_settings()
        self.presentation.hf = settings
        for s in self.presentation.slides:
            if hasattr(s, "hf"):
                s.hf = None
        self.accept()

    def apply_current(self) -> None:
        """Apply header and footer settings to the active slide."""
        settings = self._read_settings()
        if self.slide is not None:
            self.slide.hf = settings
        else:
            self.presentation.hf = settings
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("Header and Footer"))
        self.inc_group.setTitle(safe_tr("Include on slide"))
        self.dt_chk.setText(safe_tr("Date and time"))
        self.dt_auto_radio.setText(safe_tr("Update automatically"))
        self.dt_fixed_radio.setText(safe_tr("Fixed"))
        self.num_chk.setText(safe_tr("Slide number"))
        self.ftr_chk.setText(safe_tr("Footer"))
        self.not_on_title_chk.setText(safe_tr("Don't show on title slide"))
        self.apply_all_btn.setText(safe_tr("Apply to &All"))
        self.apply_btn.setText(safe_tr("&Apply"))
        self.cancel_btn.setText(safe_tr("Cancel"))


def copy_hf(hf: HeaderFooterSettings) -> HeaderFooterSettings:
    return HeaderFooterSettings(
        dt=hf.dt,
        dt_auto=hf.dt_auto,
        dt_fmt=hf.dt_fmt,
        dt_text=hf.dt_text,
        num=hf.num,
        ftr=hf.ftr,
        ftr_text=hf.ftr_text,
        not_on_title=hf.not_on_title,
    )
