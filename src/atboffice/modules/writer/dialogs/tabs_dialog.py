"""Classic Tabs Dialog for Quire Writer."""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.properties import (
    TabStop,
    format_length,
    parse_length,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("TabsDialog", text)


class TabsDialog(QDialog):
    """Word 2003 classic Tabs modal dialog."""

    def __init__(
        self,
        parent: QWidget | None = None,
        tabs: list[TabStop] | None = None,
        default_tab: float = 36.0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("制表位"))
        self.setModal(True)
        self.setMinimumWidth(380)

        self._tabs: list[TabStop] = (
            [TabStop(pos=t.pos, align=t.align, leader=t.leader) for t in tabs] if tabs else []
        )
        self._tabs.sort(key=lambda x: x.pos)
        self._cleared: list[float] = []

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # 1. Top Section (Position / List & Default Tab)
        top_layout = QHBoxLayout()

        # Left column: Tab position & list
        col_pos = QVBoxLayout()
        self.label_pos = QLabel(self)
        self.edit_pos = QLineEdit(self)
        self.list_tabs = QListWidget(self)
        self.list_tabs.setFixedHeight(95)
        self.list_tabs.currentTextChanged.connect(self._on_list_item_selected)

        col_pos.addWidget(self.label_pos)
        col_pos.addWidget(self.edit_pos)
        col_pos.addWidget(self.list_tabs)
        top_layout.addLayout(col_pos, stretch=1)

        # Right column: Default tab stop
        col_def = QVBoxLayout()
        self.label_default = QLabel(self)
        self.spin_default = QDoubleSpinBox(self)
        self.spin_default.setRange(1.0, 500.0)
        self.spin_default.setValue(float(default_tab) if default_tab > 0 else 36.0)
        self.spin_default.setSuffix(" pt")

        self.label_clear_info = QLabel(self)
        self.label_clear_info.setWordWrap(True)
        self.label_clear_info.setStyleSheet("color: #666; font-size: 11px;")

        col_def.addWidget(self.label_default)
        col_def.addWidget(self.spin_default)
        col_def.addWidget(self.label_clear_info)
        col_def.addStretch(1)
        top_layout.addLayout(col_def, stretch=1)

        main_layout.addLayout(top_layout)

        # 2. Options row (Alignment & Leader)
        opt_layout = QHBoxLayout()

        # Alignment Group
        self.group_align = QGroupBox(self)
        v_align = QVBoxLayout(self.group_align)
        v_align.setSpacing(4)
        self.btn_group_align = QButtonGroup(self)

        self.radio_left = QRadioButton(self.group_align)
        self.radio_center = QRadioButton(self.group_align)
        self.radio_right = QRadioButton(self.group_align)
        self.radio_decimal = QRadioButton(self.group_align)
        self.radio_bar = QRadioButton(self.group_align)
        self.radio_left.setChecked(True)

        for i, rb in enumerate(
            [
                self.radio_left,
                self.radio_center,
                self.radio_right,
                self.radio_decimal,
                self.radio_bar,
            ]
        ):
            v_align.addWidget(rb)
            self.btn_group_align.addButton(rb, i)
        opt_layout.addWidget(self.group_align)

        # Leader Group
        self.group_leader = QGroupBox(self)
        v_lead = QVBoxLayout(self.group_leader)
        v_lead.setSpacing(4)
        self.btn_group_leader = QButtonGroup(self)

        self.radio_none = QRadioButton(self.group_leader)
        self.radio_dot = QRadioButton(self.group_leader)
        self.radio_hyphen = QRadioButton(self.group_leader)
        self.radio_underscore = QRadioButton(self.group_leader)
        self.radio_none.setChecked(True)

        for i, rb in enumerate(
            [self.radio_none, self.radio_dot, self.radio_hyphen, self.radio_underscore]
        ):
            v_lead.addWidget(rb)
            self.btn_group_leader.addButton(rb, i)
        opt_layout.addWidget(self.group_leader)

        main_layout.addLayout(opt_layout)

        # 3. Action Buttons (Set, Clear, Clear All)
        btn_action_layout = QHBoxLayout()
        self.btn_set = QPushButton(self)
        self.btn_clear = QPushButton(self)
        self.btn_clear_all = QPushButton(self)

        self.btn_set.clicked.connect(self._on_set_clicked)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        self.btn_clear_all.clicked.connect(self._on_clear_all_clicked)

        btn_action_layout.addWidget(self.btn_set)
        btn_action_layout.addWidget(self.btn_clear)
        btn_action_layout.addWidget(self.btn_clear_all)
        main_layout.addLayout(btn_action_layout)

        # 4. Dialog Buttons (OK, Cancel)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )
        self.button_box.accepted.connect(self._on_ok_clicked)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self._refresh_list()
        self.retranslate_ui()

    def _refresh_list(self) -> None:
        self.list_tabs.clear()
        self._tabs.sort(key=lambda t: t.pos)
        for t in self._tabs:
            self.list_tabs.addItem(format_length(t.pos, "pt"))

        if self._cleared:
            info = safe_tr("待清除的制表位: ") + ", ".join(
                format_length(p, "pt") for p in self._cleared
            )
            self.label_clear_info.setText(info)
        else:
            self.label_clear_info.clear()

    def _on_list_item_selected(self, text: str) -> None:
        if not text:
            return
        self.edit_pos.setText(text)
        p = parse_length(text, default_unit="pt")
        if p is None:
            return
        t = next((x for x in self._tabs if abs(x.pos - p) < 0.5), None)
        if t:
            # Set alignment
            al_map = {
                "left": self.radio_left,
                "center": self.radio_center,
                "right": self.radio_right,
                "decimal": self.radio_decimal,
                "bar": self.radio_bar,
            }
            rb = al_map.get(t.align, self.radio_left)
            rb.setChecked(True)

            # Set leader
            lead_map = {
                "none": self.radio_none,
                "dot": self.radio_dot,
                "hyphen": self.radio_hyphen,
                "underscore": self.radio_underscore,
            }
            rl = lead_map.get(t.leader, self.radio_none)
            rl.setChecked(True)

    def _get_selected_alignment(self) -> str:
        if self.radio_center.isChecked():
            return "center"
        if self.radio_right.isChecked():
            return "right"
        if self.radio_decimal.isChecked():
            return "decimal"
        if self.radio_bar.isChecked():
            return "bar"
        return "left"

    def _get_selected_leader(self) -> str:
        if self.radio_dot.isChecked():
            return "dot"
        if self.radio_hyphen.isChecked():
            return "hyphen"
        if self.radio_underscore.isChecked():
            return "underscore"
        return "none"

    def _on_set_clicked(self) -> bool:
        raw = self.edit_pos.text().strip()
        p = parse_length(raw, default_unit="pt")
        if p is None:
            return False
        p = round(p, 2)
        align = self._get_selected_alignment()
        leader = self._get_selected_leader()

        existing = next((t for t in self._tabs if abs(t.pos - p) < 0.5), None)
        if existing:
            existing.align = align
            existing.leader = leader
        else:
            self._tabs.append(TabStop(pos=p, align=align, leader=leader))

        self._refresh_list()
        return True

    def _on_clear_clicked(self) -> None:
        raw = self.edit_pos.text().strip()
        p = parse_length(raw, default_unit="pt")
        if p is None:
            row = self.list_tabs.currentRow()
            if 0 <= row < len(self._tabs):
                p = self._tabs[row].pos
            else:
                return
        self._tabs = [t for t in self._tabs if abs(t.pos - p) >= 0.5]
        self._cleared.append(p)
        self.edit_pos.clear()
        self._refresh_list()

    def _on_clear_all_clicked(self) -> None:
        for t in self._tabs:
            self._cleared.append(t.pos)
        self._tabs.clear()
        self.edit_pos.clear()
        self._refresh_list()

    def _on_ok_clicked(self) -> None:
        raw = self.edit_pos.text().strip()
        if raw:
            p = parse_length(raw, default_unit="pt")
            if p is not None and not any(abs(t.pos - p) < 0.5 for t in self._tabs):
                self._on_set_clicked()
        self.accept()

    def retranslate_ui(self) -> None:
        """Update all translatable strings dynamically."""
        self.setWindowTitle(safe_tr("制表位"))
        self.label_pos.setText(safe_tr("制表位位置(&T):"))
        self.label_default.setText(safe_tr("默认制表位(&D):"))

        self.group_align.setTitle(safe_tr("对齐方式"))
        self.radio_left.setText(safe_tr("左对齐(&L)"))
        self.radio_center.setText(safe_tr("居中(&C)"))
        self.radio_right.setText(safe_tr("右对齐(&R)"))
        self.radio_decimal.setText(safe_tr("小数点对齐(&D)"))
        self.radio_bar.setText(safe_tr("竖线对齐(&B)"))

        self.group_leader.setTitle(safe_tr("前导符"))
        self.radio_none.setText(safe_tr("1 无(&1)"))
        self.radio_dot.setText(safe_tr("2 .......(&2)"))
        self.radio_hyphen.setText(safe_tr("3 -------(&3)"))
        self.radio_underscore.setText(safe_tr("4 ______(&4)"))

        self.btn_set.setText(safe_tr("设置(&S)"))
        self.btn_clear.setText(safe_tr("清除(&C)"))
        self.btn_clear_all.setText(safe_tr("全部清除(&A)"))

        ok_btn = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(safe_tr("确定"))
        cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setText(safe_tr("取消"))

    def get_tabs(self) -> list[TabStop]:
        """Return the configured list of tab stops."""
        return [TabStop(pos=t.pos, align=t.align, leader=t.leader) for t in self._tabs]

    def get_default_tab(self) -> float:
        """Return the default tab spacing in points."""
        return float(self.spin_default.value())

    def get_cleared(self) -> list[float]:
        """Return list of explicitly cleared tab stop positions."""
        return list(self._cleared)
