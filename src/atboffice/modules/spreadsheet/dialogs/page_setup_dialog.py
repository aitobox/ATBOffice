"""Excel 2003 File > Page Setup (Page / Margins / Header-Footer / Sheet)."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.spreadsheet.calc.references import cell_name, parse_range
from atboffice.modules.spreadsheet.printing import header_footer
from atboffice.modules.spreadsheet.printing.setup import PAPER_SIZES, SheetPrintSetup

PT_PER_CM = 72.0 / 2.54
HF_PRESETS = [
    ("(无)", ""),
    ("第 &P 页", "&C第 &P 页"),
    ("第 &P 页，共 &N 页", "&C第 &P 页，共 &N 页"),
    ("&A", "&C&A"),
    ("&F", "&C&F"),
    ("&A，第 &P 页", "&L&A&R第 &P 页"),
    ("&D &T", "&R&D &T"),
]


def _col_letters(c: int) -> str:
    return "".join(ch for ch in cell_name(0, c) if ch.isalpha())


def format_range(rng: tuple[int, int, int, int] | None) -> str:
    if rng is None:
        return ""
    r1, c1, r2, c2 = rng
    return f"${_col_letters(c1)}${r1 + 1}:${_col_letters(c2)}${r2 + 1}"


def parse_area(text: str) -> tuple[int, int, int, int] | None:
    """``A1:D20`` / ``$A$1:$D$20`` -> (r1, c1, r2, c2); empty -> None. Raises ValueError."""
    text = text.replace("$", "").strip()
    if not text:
        return None
    rng = parse_range(text if ":" in text else f"{text}:{text}")
    if not rng:
        raise ValueError(text)
    r1, c1, r2, c2 = rng["r1"], rng["c1"], rng["r2"], rng["c2"]
    return min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2)


def parse_rows(text: str) -> tuple[int, int] | None:
    """``$1:$2`` -> (0, 1)."""
    text = text.replace("$", "").strip()
    if not text:
        return None
    a, _, b = text.partition(":")
    r1, r2 = int(a) - 1, int(b or a) - 1
    if r1 < 0 or r2 < r1:
        raise ValueError(text)
    return r1, r2


def parse_cols(text: str) -> tuple[int, int] | None:
    """``$A:$B`` -> (0, 1)."""
    text = text.replace("$", "").strip().upper()
    if not text:
        return None
    a, _, b = text.partition(":")

    def col(s: str) -> int:
        if not s.isalpha():
            raise ValueError(s)
        n = 0
        for ch in s:
            n = n * 26 + (ord(ch) - 64)
        return n - 1

    c1, c2 = col(a), col(b or a)
    if c2 < c1:
        raise ValueError(text)
    return c1, c2


class LedgerPageSetupDialog(QDialog):
    """Edits a copy of ``setup``; ``result_setup()`` returns the accepted settings."""

    def __init__(self, setup: SheetPrintSetup, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup = copy.deepcopy(setup)
        self.resize(500, 420)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)
        self._build_page_tab()
        self._build_margins_tab()
        self._build_hf_tab()
        self._build_sheet_tab()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._load()
        self.retranslate_ui()

    # ------------------------------------------------------------------ tabs
    def _build_page_tab(self) -> None:
        page = QWidget()
        v = QVBoxLayout(page)
        self.grp_orient = QGroupBox(page)
        h = QHBoxLayout(self.grp_orient)
        self.rb_portrait = QRadioButton(self.grp_orient)
        self.rb_landscape = QRadioButton(self.grp_orient)
        h.addWidget(self.rb_portrait)
        h.addWidget(self.rb_landscape)
        v.addWidget(self.grp_orient)

        self.grp_scale = QGroupBox(page)
        g = QGridLayout(self.grp_scale)
        self.rb_adjust = QRadioButton(self.grp_scale)
        self.spin_scale = QSpinBox(self.grp_scale)
        self.spin_scale.setRange(10, 400)
        self.spin_scale.setSuffix("%")
        self.rb_fit = QRadioButton(self.grp_scale)
        self.spin_fit_w = QSpinBox(self.grp_scale)
        self.spin_fit_w.setRange(0, 32767)
        self.lbl_wide = QLabel(self.grp_scale)
        self.spin_fit_h = QSpinBox(self.grp_scale)
        self.spin_fit_h.setRange(0, 32767)
        self.lbl_tall = QLabel(self.grp_scale)
        self.scale_group = QButtonGroup(self)
        self.scale_group.addButton(self.rb_adjust)
        self.scale_group.addButton(self.rb_fit)
        g.addWidget(self.rb_adjust, 0, 0)
        g.addWidget(self.spin_scale, 0, 1)
        g.addWidget(self.rb_fit, 1, 0)
        g.addWidget(self.spin_fit_w, 1, 1)
        g.addWidget(self.lbl_wide, 1, 2)
        g.addWidget(self.spin_fit_h, 1, 3)
        g.addWidget(self.lbl_tall, 1, 4)
        v.addWidget(self.grp_scale)

        form = QFormLayout()
        self.combo_paper = QComboBox(page)
        for name in PAPER_SIZES:
            self.combo_paper.addItem(name, name)
        self.edit_first_page = QLineEdit(page)
        self.lbl_paper = QLabel(page)
        self.lbl_first = QLabel(page)
        form.addRow(self.lbl_paper, self.combo_paper)
        form.addRow(self.lbl_first, self.edit_first_page)
        v.addLayout(form)
        v.addStretch(1)
        self.tabs.addTab(page, "")

    def _build_margins_tab(self) -> None:
        page = QWidget()
        v = QVBoxLayout(page)
        form = QFormLayout()
        self.margin_spins: dict[str, QDoubleSpinBox] = {}
        self.margin_labels: dict[str, QLabel] = {}
        for key in ("top", "bottom", "left", "right", "header", "footer"):
            spin = QDoubleSpinBox(page)
            spin.setRange(0.0, 20.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.1)
            spin.setSuffix(" cm")
            lbl = QLabel(page)
            form.addRow(lbl, spin)
            self.margin_spins[key] = spin
            self.margin_labels[key] = lbl
        v.addLayout(form)
        self.grp_center = QGroupBox(page)
        h = QHBoxLayout(self.grp_center)
        self.chk_center_h = QCheckBox(self.grp_center)
        self.chk_center_v = QCheckBox(self.grp_center)
        h.addWidget(self.chk_center_h)
        h.addWidget(self.chk_center_v)
        v.addWidget(self.grp_center)
        v.addStretch(1)
        self.tabs.addTab(page, "")

    def _build_hf_tab(self) -> None:
        page = QWidget()
        v = QVBoxLayout(page)
        self.lbl_header = QLabel(page)
        self.combo_header = QComboBox(page)
        self.hf_edits: dict[str, QLineEdit] = {}
        self.hf_labels: list[QLabel] = []
        v.addWidget(self.lbl_header)
        v.addWidget(self.combo_header)
        grid_h = QGridLayout()
        for col, key in enumerate(("header_l", "header_c", "header_r")):
            edit = QLineEdit(page)
            self.hf_edits[key] = edit
            grid_h.addWidget(edit, 0, col)
        v.addLayout(grid_h)
        self.lbl_footer = QLabel(page)
        self.combo_footer = QComboBox(page)
        v.addWidget(self.lbl_footer)
        v.addWidget(self.combo_footer)
        grid_f = QGridLayout()
        for col, key in enumerate(("footer_l", "footer_c", "footer_r")):
            edit = QLineEdit(page)
            self.hf_edits[key] = edit
            grid_f.addWidget(edit, 0, col)
        v.addLayout(grid_f)
        self.lbl_codes = QLabel(page)
        self.lbl_codes.setWordWrap(True)
        v.addWidget(self.lbl_codes)
        v.addStretch(1)
        for combo in (self.combo_header, self.combo_footer):
            for _label, code in HF_PRESETS:
                combo.addItem("", code)
        self.combo_header.activated.connect(lambda i: self._apply_preset("header", i))
        self.combo_footer.activated.connect(lambda i: self._apply_preset("footer", i))
        self.tabs.addTab(page, "")

    def _build_sheet_tab(self) -> None:
        page = QWidget()
        v = QVBoxLayout(page)
        form = QFormLayout()
        self.edit_area = QLineEdit(page)
        self.edit_title_rows = QLineEdit(page)
        self.edit_title_cols = QLineEdit(page)
        self.lbl_area = QLabel(page)
        self.lbl_title_rows = QLabel(page)
        self.lbl_title_cols = QLabel(page)
        form.addRow(self.lbl_area, self.edit_area)
        form.addRow(self.lbl_title_rows, self.edit_title_rows)
        form.addRow(self.lbl_title_cols, self.edit_title_cols)
        v.addLayout(form)
        self.grp_print = QGroupBox(page)
        g = QVBoxLayout(self.grp_print)
        self.chk_gridlines = QCheckBox(self.grp_print)
        self.chk_bw = QCheckBox(self.grp_print)
        self.chk_headings = QCheckBox(self.grp_print)
        for w in (self.chk_gridlines, self.chk_bw, self.chk_headings):
            g.addWidget(w)
        v.addWidget(self.grp_print)
        self.grp_order = QGroupBox(page)
        h = QHBoxLayout(self.grp_order)
        self.rb_down = QRadioButton(self.grp_order)
        self.rb_over = QRadioButton(self.grp_order)
        h.addWidget(self.rb_down)
        h.addWidget(self.rb_over)
        v.addWidget(self.grp_order)
        v.addStretch(1)
        self.tabs.addTab(page, "")

    # ------------------------------------------------------------------ data
    def _apply_preset(self, which: str, index: int) -> None:
        combo = self.combo_header if which == "header" else self.combo_footer
        left, center, right = header_footer.split_sections(str(combo.itemData(index) or ""))
        self.hf_edits[f"{which}_l"].setText(left)
        self.hf_edits[f"{which}_c"].setText(center)
        self.hf_edits[f"{which}_r"].setText(right)

    def _load(self) -> None:
        s = self.setup
        (self.rb_landscape if s.orientation == "landscape" else self.rb_portrait).setChecked(True)
        (self.rb_fit if s.fit_to else self.rb_adjust).setChecked(True)
        self.spin_scale.setValue(int(s.scale))
        self.spin_fit_w.setValue(int(s.fit_width))
        self.spin_fit_h.setValue(int(s.fit_height))
        self.combo_paper.setCurrentIndex(max(0, self.combo_paper.findData(s.paper)))
        self.edit_first_page.setText("" if s.first_page_number is None else
                                     str(s.first_page_number))
        for key, spin in self.margin_spins.items():
            spin.setValue(s.margins[key] / PT_PER_CM)
        self.chk_center_h.setChecked(s.center_h)
        self.chk_center_v.setChecked(s.center_v)
        for which, text in (("header", s.header), ("footer", s.footer)):
            left, center, right = header_footer.split_sections(text)
            self.hf_edits[f"{which}_l"].setText(left)
            self.hf_edits[f"{which}_c"].setText(center)
            self.hf_edits[f"{which}_r"].setText(right)
        self.edit_area.setText(format_range(s.print_area))
        self.edit_title_rows.setText(
            f"${s.title_rows[0] + 1}:${s.title_rows[1] + 1}" if s.title_rows else ""
        )
        self.edit_title_cols.setText(
            f"${_col_letters(s.title_cols[0])}:${_col_letters(s.title_cols[1])}"
            if s.title_cols else ""
        )
        self.chk_gridlines.setChecked(s.gridlines)
        self.chk_bw.setChecked(s.black_white)
        self.chk_headings.setChecked(s.headings)
        (self.rb_over if s.page_order == "over_then_down" else self.rb_down).setChecked(True)

    def result_setup(self) -> SheetPrintSetup:
        """Settings from the widgets. Raises ValueError (with the field) on bad input."""
        s = copy.deepcopy(self.setup)
        s.orientation = "landscape" if self.rb_landscape.isChecked() else "portrait"
        s.fit_to = self.rb_fit.isChecked()
        s.scale = self.spin_scale.value()
        s.fit_width = self.spin_fit_w.value()
        s.fit_height = self.spin_fit_h.value()
        s.paper = str(self.combo_paper.currentData())
        first = self.edit_first_page.text().strip()
        if first and not first.lstrip("-").isdigit():
            raise ValueError(safe_tr("起始页码"))
        s.first_page_number = int(first) if first else None
        s.margins = {k: round(spin.value() * PT_PER_CM, 2) for k, spin in self.margin_spins.items()}
        s.center_h = self.chk_center_h.isChecked()
        s.center_v = self.chk_center_v.isChecked()
        e = self.hf_edits
        s.header = header_footer.join_sections(
            e["header_l"].text(), e["header_c"].text(), e["header_r"].text()
        )
        s.footer = header_footer.join_sections(
            e["footer_l"].text(), e["footer_c"].text(), e["footer_r"].text()
        )
        for label, edit, parser, attr in (
            (safe_tr("打印区域"), self.edit_area, parse_area, "print_area"),
            (safe_tr("顶端标题行"), self.edit_title_rows, parse_rows, "title_rows"),
            (safe_tr("左端标题列"), self.edit_title_cols, parse_cols, "title_cols"),
        ):
            try:
                setattr(s, attr, parser(edit.text()))
            except (ValueError, TypeError) as exc:
                raise ValueError(label) from exc
        s.gridlines = self.chk_gridlines.isChecked()
        s.black_white = self.chk_bw.isChecked()
        s.headings = self.chk_headings.isChecked()
        s.page_order = "over_then_down" if self.rb_over.isChecked() else "down_then_over"
        return s

    def accept(self) -> None:
        try:
            self.setup = self.result_setup()
        except ValueError as exc:
            QMessageBox.warning(
                self, safe_tr("页面设置"), safe_tr("“{0}”中的引用无效。").format(exc)
            )
            return
        super().accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("页面设置"))
        for i, name in enumerate((safe_tr("页面"), safe_tr("页边距"), safe_tr("页眉/页脚"),
                                  safe_tr("工作表"))):
            self.tabs.setTabText(i, name)
        self.grp_orient.setTitle(safe_tr("方向"))
        self.rb_portrait.setText(safe_tr("纵向(&T)"))
        self.rb_landscape.setText(safe_tr("横向(&L)"))
        self.grp_scale.setTitle(safe_tr("缩放"))
        self.rb_adjust.setText(safe_tr("缩放比例(&A):"))
        self.rb_fit.setText(safe_tr("调整为(&F):"))
        self.lbl_wide.setText(safe_tr("页宽"))
        self.lbl_tall.setText(safe_tr("页高"))
        self.lbl_paper.setText(safe_tr("纸张大小(&Z):"))
        self.lbl_first.setText(safe_tr("起始页码(&R):"))
        self.edit_first_page.setPlaceholderText(safe_tr("自动"))
        names = {"top": "上(&T):", "bottom": "下(&B):", "left": "左(&L):", "right": "右(&R):",
                 "header": "页眉(&A):", "footer": "页脚(&F):"}
        for key, label in names.items():
            self.margin_labels[key].setText(safe_tr(label))
        self.grp_center.setTitle(safe_tr("居中方式"))
        self.chk_center_h.setText(safe_tr("水平(&Z)"))
        self.chk_center_v.setText(safe_tr("垂直(&V)"))
        self.lbl_header.setText(safe_tr("页眉(&A):"))
        self.lbl_footer.setText(safe_tr("页脚(&F):"))
        for combo in (self.combo_header, self.combo_footer):
            for i, (label, _code) in enumerate(HF_PRESETS):
                combo.setItemText(i, safe_tr(label))
        for key, tip in (("l", "左"), ("c", "中"), ("r", "右")):
            for which in ("header", "footer"):
                self.hf_edits[f"{which}_{key}"].setPlaceholderText(safe_tr(tip))
        self.lbl_codes.setText(safe_tr(
            "代码：&P 页码，&N 总页数，&D 日期，&T 时间，&F 文件名，&A 工作表名"
        ))
        self.lbl_area.setText(safe_tr("打印区域(&A):"))
        self.lbl_title_rows.setText(safe_tr("顶端标题行(&R):"))
        self.lbl_title_cols.setText(safe_tr("左端标题列(&C):"))
        self.grp_print.setTitle(safe_tr("打印"))
        self.chk_gridlines.setText(safe_tr("网格线(&G)"))
        self.chk_bw.setText(safe_tr("单色打印(&B)"))
        self.chk_headings.setText(safe_tr("行号列标(&L)"))
        self.grp_order.setTitle(safe_tr("打印顺序"))
        self.rb_down.setText(safe_tr("先列后行(&D)"))
        self.rb_over.setText(safe_tr("先行后列(&V)"))
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok is not None:
            ok.setText(safe_tr("确定"))
        if cancel is not None:
            cancel.setText(safe_tr("取消"))
