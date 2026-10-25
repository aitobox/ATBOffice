"""Classic 6-tab Format Cells Dialog for ATBOffice Ledger."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.dialogs.tab_alignment import AlignmentTab
from atboffice.modules.spreadsheet.dialogs.tab_border import BorderTab
from atboffice.modules.spreadsheet.dialogs.tab_font import FontTab
from atboffice.modules.spreadsheet.dialogs.tab_number import NumberFormatTab
from atboffice.modules.spreadsheet.dialogs.tab_patterns import PatternsTab
from atboffice.modules.spreadsheet.dialogs.tab_protection import ProtectionTab
from atboffice.modules.spreadsheet.models.selection_model import SelectionModel
from atboffice.modules.spreadsheet.models.sheet_model import (
    CellData,
    FormatDelta,
    SheetDataModel,
)


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("FormatCellsDialog", text)


class FormatCellsDialog(QDialog):
    """Excel 2003 Classic 6-Tab Format Cells Dialog."""

    def __init__(
        self,
        target_cell: CellData | None = None,
        model: SheetDataModel | None = None,
        selection: SelectionModel | None = None,
        initial_tab: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(safe_tr("设置单元格格式"))
        self.resize(520, 440)

        self.target_cell = target_cell or CellData()
        self.model = model
        self.selection = selection

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Tab 1: Number
        sample_val = self.target_cell.value if self.target_cell.value is not None else 1234.5
        self.tab_number = NumberFormatTab(
            current_format=self.target_cell.format_code,
            sample_value=sample_val,
        )
        self.tab_widget.addTab(self.tab_number, safe_tr("数字"))

        # Tab 2: Alignment
        is_merged = False
        if self.model and self.selection:
            ar, ac = self.selection.active_cell
            is_merged = self.model.is_merged(ar, ac)

        self.tab_alignment = AlignmentTab(
            align_h=self.target_cell.align_h,
            align_v=self.target_cell.align_v,
            indent=self.target_cell.indent,
            wrap_text=self.target_cell.wrap_text,
            shrink_to_fit=self.target_cell.shrink_to_fit,
            text_rotation=self.target_cell.text_rotation,
            text_direction=self.target_cell.text_direction,
            merged=is_merged,
        )
        self.tab_widget.addTab(self.tab_alignment, safe_tr("对齐"))

        # Tab 3: Font
        self.tab_font = FontTab(
            font_family=self.target_cell.font_family,
            font_size=self.target_cell.font_size,
            bold=self.target_cell.bold,
            italic=self.target_cell.italic,
            underline_style=self.target_cell.underline_style,
            strike=self.target_cell.strike,
            vert_align=self.target_cell.vert_align,
            fg_color=self.target_cell.fg_color,
        )
        self.tab_widget.addTab(self.tab_font, safe_tr("字体"))

        # Tab 4: Border
        borders = {
            "top": self.target_cell.border_top,
            "bottom": self.target_cell.border_bottom,
            "left": self.target_cell.border_left,
            "right": self.target_cell.border_right,
            "diag_up": self.target_cell.border_diag_up,
            "diag_down": self.target_cell.border_diag_down,
        }
        self.tab_border = BorderTab(borders=borders)
        self.tab_widget.addTab(self.tab_border, safe_tr("边框"))

        # Tab 5: Patterns
        self.tab_patterns = PatternsTab(
            bg_color=self.target_cell.bg_color,
            pattern=self.target_cell.pattern,
            pattern_color=self.target_cell.pattern_color,
        )
        self.tab_widget.addTab(self.tab_patterns, safe_tr("图案"))

        # Tab 6: Protection
        self.tab_protection = ProtectionTab(
            locked=self.target_cell.locked,
            hidden=self.target_cell.hidden,
        )
        self.tab_widget.addTab(self.tab_protection, safe_tr("保护"))

        self.tab_widget.setCurrentIndex(max(0, min(5, initial_tab)))
        layout.addWidget(self.tab_widget)

        # OK / Cancel Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.retranslate_ui()

    def _on_accept(self) -> None:
        if self.model and self.selection:
            self.apply_to_selection()
        self.accept()

    def get_delta(self) -> FormatDelta:
        """Extract user configuration from all 6 tabs into a FormatDelta."""
        nf = self.tab_number.get_format_code()
        align = self.tab_alignment.get_alignment()
        fnt = self.tab_font.get_font()
        brd = self.tab_border.get_borders()
        pat = self.tab_patterns.get_patterns()
        prot = self.tab_protection.get_protection()

        return FormatDelta(
            format_code=nf,
            align_h=align["align_h"],
            align_v=align["align_v"],
            indent=align["indent"],
            wrap_text=align["wrap_text"],
            shrink_to_fit=align["shrink_to_fit"],
            text_rotation=align["text_rotation"],
            text_direction=align["text_direction"],
            just_last=align["just_last"],
            font_family=fnt["font_family"],
            font_size=fnt["font_size"],
            bold=fnt["bold"],
            italic=fnt["italic"],
            underline_style=fnt["underline_style"],
            underline=(fnt["underline_style"] != "none"),
            strike=fnt["strike"],
            vert_align=fnt["vert_align"],
            fg_color=fnt["fg_color"],
            border_top=brd.get("top"),
            border_bottom=brd.get("bottom"),
            border_left=brd.get("left"),
            border_right=brd.get("right"),
            border_diag_up=brd.get("diag_up"),
            border_diag_down=brd.get("diag_down"),
            bg_color=pat.get("bg_color"),
            pattern=pat.get("pattern"),
            pattern_color=pat.get("pattern_color"),
            locked=prot.get("locked"),
            hidden=prot.get("hidden"),
        )

    def apply_to_selection(self) -> None:
        """Apply the format delta to all selected cells in SheetDataModel."""
        if not self.model or not self.selection:
            return

        delta = self.get_delta()
        align_data = self.tab_alignment.get_alignment()
        should_merge = align_data.get("merge_cells", False)

        for rg in self.selection.ranges:
            for r in range(rg.min_r, rg.max_r + 1):
                for c in range(rg.min_c, rg.max_c + 1):
                    self.model.apply_format_delta(r, c, delta)

            if should_merge and (rg.min_r != rg.max_r or rg.min_c != rg.max_c):
                self.model.add_merge(rg.min_r, rg.min_c, rg.max_r, rg.max_c)
            elif not should_merge:
                for r in range(rg.min_r, rg.max_r + 1):
                    for c in range(rg.min_c, rg.max_c + 1):
                        self.model.remove_merge(r, c)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(safe_tr("设置单元格格式"))
        self.tab_widget.setTabText(0, safe_tr("数字"))
        self.tab_widget.setTabText(1, safe_tr("对齐"))
        self.tab_widget.setTabText(2, safe_tr("字体"))
        self.tab_widget.setTabText(3, safe_tr("边框"))
        self.tab_widget.setTabText(4, safe_tr("图案"))
        self.tab_widget.setTabText(5, safe_tr("保护"))

        self.tab_number.retranslate_ui()
        self.tab_alignment.retranslate_ui()
        self.tab_font.retranslate_ui()
        self.tab_border.retranslate_ui()
        self.tab_patterns.retranslate_ui()
        self.tab_protection.retranslate_ui()


__all__ = [
    "AlignmentTab",
    "BorderTab",
    "FontTab",
    "FormatCellsDialog",
    "NumberFormatTab",
    "PatternsTab",
    "ProtectionTab",
]
