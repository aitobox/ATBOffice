"""Hyperlink dialog for inserting and editing cell hyperlinks in Ledger."""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr


class HyperlinkDialog(QDialog):
    """Excel 2003 classic insert and edit hyperlink dialog."""

    def __init__(
        self,
        existing_text: str = "",
        existing_target: str = "",
        existing_location: str = "",
        existing_tooltip: str = "",
        sheets: list[str] | None = None,
        is_existing: bool = False,
        cell_ref: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_existing = is_existing
        self.cell_ref = cell_ref
        self.sheets = sheets or []
        self.is_removed = False

        self.setWindowTitle(
            safe_tr("Edit Hyperlink") if is_existing else safe_tr("Insert Hyperlink")
        )
        self.resize(520, 360)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Text to display
        form_top = QFormLayout()
        self.lbl_text = QLabel(safe_tr("Text to &display:"), self)
        self.edit_text = QLineEdit(existing_text, self)
        self.edit_text.setPlaceholderText(safe_tr("Cell Text"))
        form_top.addRow(self.lbl_text, self.edit_text)
        main_layout.addLayout(form_top)

        # 2. Tab widget for link destinations
        self.tab_widget = QTabWidget(self)

        # Tab 1: Web / Existing File
        self.tab_web = QWidget(self)
        web_layout = QVBoxLayout(self.tab_web)
        self.lbl_addr = QLabel(safe_tr("&Address:"), self.tab_web)
        self.edit_addr = QLineEdit(existing_target, self.tab_web)
        self.edit_addr.setPlaceholderText("https://")
        web_layout.addWidget(self.lbl_addr)
        web_layout.addWidget(self.edit_addr)
        web_layout.addStretch()
        self.tab_widget.addTab(self.tab_web, safe_tr("Existing &File or Web Page"))

        # Tab 2: Place in This Document
        self.tab_doc = QWidget(self)
        doc_layout = QVBoxLayout(self.tab_doc)
        self.lbl_cell_ref = QLabel(safe_tr("Type the cell &reference:"), self.tab_doc)
        loc_cell = "A1"
        loc_sheet = self.sheets[0] if self.sheets else ""
        if existing_location:
            if "!" in existing_location:
                loc_sheet_part, loc_cell = existing_location.split("!", 1)
                loc_sheet = loc_sheet_part.strip("'")
            else:
                loc_cell = existing_location

        self.edit_cell_ref = QLineEdit(loc_cell, self.tab_doc)
        self.lbl_sheet = QLabel(safe_tr("Or &select a place in this document:"), self.tab_doc)
        self.combo_sheet = QComboBox(self.tab_doc)
        for s in self.sheets:
            self.combo_sheet.addItem(s)
        if loc_sheet in self.sheets:
            self.combo_sheet.setCurrentText(loc_sheet)

        doc_layout.addWidget(self.lbl_cell_ref)
        doc_layout.addWidget(self.edit_cell_ref)
        doc_layout.addWidget(self.lbl_sheet)
        doc_layout.addWidget(self.combo_sheet)
        doc_layout.addStretch()
        self.tab_widget.addTab(self.tab_doc, safe_tr("&Place in This Document"))

        # Tab 3: Email Address
        self.tab_mail = QWidget(self)
        mail_layout = QVBoxLayout(self.tab_mail)
        self.lbl_email = QLabel(safe_tr("&E-mail address:"), self.tab_mail)
        mail_val = ""
        subj_val = ""
        if existing_target.lower().startswith("mailto:"):
            mail_part = existing_target[7:]
            if "?" in mail_part:
                mail_val, query = mail_part.split("?", 1)
                parsed = urllib.parse.parse_qs(query)
                subj_val = parsed.get("subject", [""])[0]
            else:
                mail_val = mail_part

        self.edit_email = QLineEdit(mail_val, self.tab_mail)
        self.edit_email.setPlaceholderText("user@example.com")
        self.lbl_subj = QLabel(safe_tr("&Subject:"), self.tab_mail)
        self.edit_subj = QLineEdit(subj_val, self.tab_mail)
        mail_layout.addWidget(self.lbl_email)
        mail_layout.addWidget(self.edit_email)
        mail_layout.addWidget(self.lbl_subj)
        mail_layout.addWidget(self.edit_subj)
        mail_layout.addStretch()
        self.tab_widget.addTab(self.tab_mail, safe_tr("&E-mail Address"))

        # Select initial tab based on existing target/location
        if existing_target.lower().startswith("mailto:"):
            self.tab_widget.setCurrentIndex(2)
        elif existing_location:
            self.tab_widget.setCurrentIndex(1)
        else:
            self.tab_widget.setCurrentIndex(0)

        main_layout.addWidget(self.tab_widget)

        # 3. ScreenTip
        form_bottom = QFormLayout()
        self.lbl_tip = QLabel(safe_tr("Screen&Tip..."), self)
        self.edit_tip = QLineEdit(existing_tooltip, self)
        form_bottom.addRow(self.lbl_tip, self.edit_tip)
        main_layout.addLayout(form_bottom)

        # 4. Buttons
        btn_layout = QHBoxLayout()
        if self.is_existing:
            self.btn_remove = QPushButton(safe_tr("&Remove Link"), self)
            self.btn_remove.clicked.connect(self._on_remove_clicked)
            btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self._on_accepted)
        self.button_box.rejected.connect(self.reject)
        btn_layout.addWidget(self.button_box)
        main_layout.addLayout(btn_layout)

    def _on_remove_clicked(self) -> None:
        """Handle Remove Link button click."""
        self.is_removed = True
        self.accept()

    def _on_accepted(self) -> None:
        """Validate input and accept dialog."""
        self.accept()

    def get_data(self) -> dict[str, Any]:
        """Return parsed hyperlink data payload."""
        if self.is_removed:
            return {"is_removed": True}

        tab_idx = self.tab_widget.currentIndex()
        target = ""
        location = ""

        if tab_idx == 0:  # Web
            addr = self.edit_addr.text().strip()
            if addr:
                is_proto = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", addr))
                if not is_proto and not addr.lower().startswith("mailto:"):
                    if addr.startswith("www.") or "." in addr:
                        addr = "http://" + addr
                target = addr
        elif tab_idx == 1:  # Document
            sheet = self.combo_sheet.currentText()
            cell = self.edit_cell_ref.text().strip() or "A1"
            location = f"'{sheet}'!{cell}" if sheet else cell
        elif tab_idx == 2:  # Mail
            email = self.edit_email.text().strip()
            if email:
                target = f"mailto:{email}"
                subj = self.edit_subj.text().strip()
                if subj:
                    target += f"?subject={urllib.parse.quote(subj)}"

        display = self.edit_text.text().strip()
        if not display:
            display = target or location

        tooltip = self.edit_tip.text().strip()

        return {
            "is_removed": False,
            "display": display,
            "target": target,
            "location": location,
            "tooltip": tooltip,
        }

    def retranslate_ui(self) -> None:
        """Update localized strings."""
        self.setWindowTitle(
            safe_tr("Edit Hyperlink") if self.is_existing else safe_tr("Insert Hyperlink")
        )
        self.lbl_text.setText(safe_tr("Text to &display:"))
        self.edit_text.setPlaceholderText(safe_tr("Cell Text"))
        self.tab_widget.setTabText(0, safe_tr("Existing &File or Web Page"))
        self.tab_widget.setTabText(1, safe_tr("&Place in This Document"))
        self.tab_widget.setTabText(2, safe_tr("&E-mail Address"))
        self.lbl_addr.setText(safe_tr("&Address:"))
        self.lbl_cell_ref.setText(safe_tr("Type the cell &reference:"))
        self.lbl_sheet.setText(safe_tr("Or &select a place in this document:"))
        self.lbl_email.setText(safe_tr("&E-mail address:"))
        self.lbl_subj.setText(safe_tr("&Subject:"))
        self.lbl_tip.setText(safe_tr("Screen&Tip..."))
        if hasattr(self, "btn_remove"):
            self.btn_remove.setText(safe_tr("&Remove Link"))
        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("OK"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("Cancel"))
