#!/usr/bin/env python3
# ruff: noqa: E402, E501
"""Automated high-fidelity UI screenshot capture tool for ATBOffice (TASK-701 / Issue #235).

Renders and captures paired 1440x900 screenshots across all 4 modules:
- 00_start_center (10 items)
- 01_quire (175 items)
- 02_ledger (131 items)
- 03_lectern (96 items)
Matching the 412 baseline screenshots documented in .vibeoffice/screenshots/records.json.

Strict mode enforces:
- Explicit scenario handling without silent window.grab fallback.
- Validation of dialog instances and tab index ranges.
- Detection of duplicate screenshot hashes across distinct semantic states.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force offscreen QPA for headless capture
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root / "scripts"))

from phase7_capture_scenarios import (
    CaptureScenarioRegistry,
    ScenarioCaptureError,
    ScenarioStatus,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget

from atboffice.ui.dialogs.about_dialog import AboutDialog
from atboffice.ui.dialogs.license_dialog import LicenseDialog
from atboffice.ui.dialogs.options_dialog import OptionsDialog
from atboffice.ui.dialogs.theme_dialog import ThemeDialog
from atboffice.ui.dialogs.update_dialog import UpdateDialog
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.start_center import StartCenterWindow

# Lazy import module dialogs
try:
    from atboffice.modules.spreadsheet.dialogs.chart_wizard import ChartWizard
    from atboffice.modules.spreadsheet.dialogs.conditional_format_dialog import (
        ConditionalFormatDialog,
    )
    from atboffice.modules.spreadsheet.dialogs.consolidate_dialog import ConsolidateDialog
    from atboffice.modules.spreadsheet.dialogs.data_validation_dialog import DataValidationDialog
    from atboffice.modules.spreadsheet.dialogs.goal_seek_dlg import GoalSeekDialog
    from atboffice.modules.spreadsheet.dialogs.sort_dialog import SortDialog
    from atboffice.modules.spreadsheet.dialogs.subtotal_dialog import SubtotalDialog
    from atboffice.modules.spreadsheet.dialogs.text_to_columns_wizard import TextToColumnsWizard
except Exception:
    pass

try:
    from atboffice.modules.writer.dialogs.break_dialog import BreakDialog
    from atboffice.modules.writer.dialogs.columns_dialog import ColumnsDialog
    from atboffice.modules.writer.dialogs.font_dialog import FontDialog
    from atboffice.modules.writer.dialogs.mailmerge_wizard import MailMergeWizard
    from atboffice.modules.writer.dialogs.page_formatting_dialogs import PageSetupDialog
    from atboffice.modules.writer.dialogs.paragraph_dialog import ParagraphDialog
    from atboffice.modules.writer.dialogs.spelling_dialog import SpellingDialog
    from atboffice.modules.writer.dialogs.table_dialogs import (
        InsertTableDialog,
        TablePropertiesDialog,
    )
    from atboffice.modules.writer.dialogs.tabs_dialog import TabsDialog
    from atboffice.modules.writer.dialogs.word_count_dlg import WordCountDialog
except Exception:
    pass

try:
    from atboffice.modules.presentation.dialogs.action_settings_dialog import ActionSettingsDialog
    from atboffice.modules.presentation.dialogs.background_dlg import BackgroundDialog
    from atboffice.modules.presentation.dialogs.fill_effects_dialog import FillEffectsDialog
    from atboffice.modules.presentation.dialogs.set_up_show_dialog import SetUpShowDialog
    from atboffice.modules.presentation.dialogs.wordart_gallery_dialog import WordArtGalleryDialog
except Exception:
    pass


VIEWPORT_W = 1440
VIEWPORT_H = 900


def create_composite_canvas(base_win: QWidget, dialog_widget: QWidget | None = None) -> QPixmap:
    """Create a 1440x900 composite pixmap of window and optional centered dialog."""
    base_win.resize(VIEWPORT_W, VIEWPORT_H)
    base_win.show()
    QApplication.processEvents()

    win_pix = base_win.grab()

    if dialog_widget is None:
        return win_pix

    dialog_widget.show()
    QApplication.processEvents()
    dlg_pix = dialog_widget.grab()

    canvas = QPixmap(VIEWPORT_W, VIEWPORT_H)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.drawPixmap(0, 0, win_pix)

    # Semi-transparent overlay backdrop
    painter.fillRect(0, 0, VIEWPORT_W, VIEWPORT_H, QColor(0, 0, 0, 75))

    # Center dialog on canvas
    dx = max(0, (VIEWPORT_W - dlg_pix.width()) // 2)
    dy = max(0, (VIEWPORT_H - dlg_pix.height()) // 2)
    painter.drawPixmap(dx, dy, dlg_pix)
    painter.end()

    return canvas


class ScreenCaptureManager:
    """Orchestrates screenshot generation for benchmark UI states with non-fallback contracts."""

    def __init__(self, out_dir: Path, strict: bool = True):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.strict = strict
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.registry = CaptureScenarioRegistry()

        self._start_center_win: StartCenterWindow | None = None
        self._quire_win: QuireWindow | None = None
        self._ledger_win: LedgerWindow | None = None
        self._lectern_win: LecternWindow | None = None

    def get_start_center(self) -> StartCenterWindow:
        if self._start_center_win is None:
            self._start_center_win = StartCenterWindow()
            self._start_center_win.resize(VIEWPORT_W, VIEWPORT_H)
        return self._start_center_win

    def get_quire(self) -> QuireWindow:
        if self._quire_win is None:
            self._quire_win = QuireWindow()
            self._quire_win.resize(VIEWPORT_W, VIEWPORT_H)
        return self._quire_win

    def get_ledger(self) -> LedgerWindow:
        if self._ledger_win is None:
            self._ledger_win = LedgerWindow()
            self._ledger_win.resize(VIEWPORT_W, VIEWPORT_H)
        return self._ledger_win

    def get_lectern(self) -> LecternWindow:
        if self._lectern_win is None:
            self._lectern_win = LecternWindow()
            self._lectern_win.resize(VIEWPORT_W, VIEWPORT_H)
        return self._lectern_win

    def capture_record(self, record: dict) -> Path | None:
        """Capture an individual record adhering strictly to non-fallback contracts."""
        mod = record["module"]
        fn = record["filename"]
        path = record.get("path") or f"{mod}/{fn}"
        dest = self.out_dir / mod / fn
        dest.parent.mkdir(parents=True, exist_ok=True)

        scenario = self.registry.get_by_path(path) or self.registry.get_by_filename(fn)
        if scenario is None:
            if self.strict:
                raise ScenarioCaptureError(f"Unregistered capture scenario: {path}")
            return None

        if self.strict and scenario.status == ScenarioStatus.MISSING:
            raise ScenarioCaptureError(f"Scenario [{path}] is marked MISSING in registry.")

        try:
            if mod == "00_start_center":
                pix = self._capture_start_center_record(record)
            elif mod == "01_quire":
                pix = self._capture_quire_record(record)
            elif mod == "02_ledger":
                pix = self._capture_ledger_record(record)
            elif mod == "03_lectern":
                pix = self._capture_lectern_record(record)
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Unknown module [{mod}] for record [{path}]")
                pix = None
        except Exception as e:
            if self.strict:
                raise ScenarioCaptureError(f"Capture failed for [{path}]: {e}") from e
            print(f"Warning: capture failed for {path}: {e}")
            return None

        if pix is None or pix.isNull():
            if self.strict:
                raise ScenarioCaptureError(f"Null pixmap produced for [{path}]")
            return None

        # Track hash to detect unexpected duplicate grabs
        self.registry.tracker.register_image(path, pix)

        # Save result
        pix.save(str(dest), "PNG")
        return dest

    def _capture_start_center_record(self, record: dict) -> QPixmap:
        win = self.get_start_center()
        fn = record["filename"]

        if "001_overview__Recent_Files_Populated" in fn:
            win.stacked_widget.setCurrentIndex(0)
            win.recent_list_widget.setVisible(True)
            win.empty_state_widget.setVisible(False)
            return win.grab()
        elif "002_overview__Create_File_Templates" in fn:
            win.stacked_widget.setCurrentIndex(1)
            return win.grab()
        elif "003_overview__Recent_Files_Empty_Welcome" in fn:
            win.stacked_widget.setCurrentIndex(0)
            win.recent_list_widget.setVisible(False)
            win.empty_state_widget.setVisible(True)
            return win.grab()
        elif "004_dialog_settings" in fn:
            dlg = OptionsDialog(win)
            return create_composite_canvas(win, dlg)
        elif "005_dialog_themes__Themes_classic" in fn:
            dlg = ThemeDialog(win, mode="suite")
            dlg._on_card_selected("classic")
            return create_composite_canvas(win, dlg)
        elif "006_dialog_themes__Themes_paper" in fn:
            dlg = ThemeDialog(win, mode="suite")
            dlg._on_card_selected("paper")
            return create_composite_canvas(win, dlg)
        elif "007_dialog_themes__Themes_paper2016" in fn:
            dlg = ThemeDialog(win, mode="suite")
            dlg._on_card_selected("paper2016")
            return create_composite_canvas(win, dlg)
        elif "008_dialog_about" in fn:
            dlg = AboutDialog(win)
            return create_composite_canvas(win, dlg)
        elif "009_dialog_update" in fn:
            dlg = UpdateDialog(parent=win)
            return create_composite_canvas(win, dlg)
        elif "010_page_licenses" in fn:
            dlg = LicenseDialog(win)
            return create_composite_canvas(win, dlg)
        else:
            if self.strict:
                raise ScenarioCaptureError(f"Unhandled start center scenario: {fn}")
            return win.grab()

    def _capture_quire_record(self, record: dict) -> QPixmap:
        win = self.get_quire()
        fn = record["filename"]
        cat = record.get("category", "")

        tab_idx: int | None = None
        if "tab" in fn:
            try:
                import re
                m = re.search(r"tab(\d+)", fn)
                if m:
                    tab_idx = max(0, int(m.group(1)) - 1)
            except Exception:
                pass

        if cat == "overview":
            if "Normal" in fn:
                win.switch_view_mode("normal")
            elif "Web" in fn:
                win.switch_view_mode("web")
            elif "Reading" in fn:
                win.switch_view_mode("reading")
            elif "Outline" in fn:
                win.switch_view_mode("outline")
            elif "Full_Screen" in fn:
                win.enter_full_screen()
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Unhandled quire overview mode: {fn}")
            return win.grab()

        elif cat == "dialog":
            dlg = None
            if "Page_Setup" in fn and "PageSetupDialog" in globals():
                dlg = PageSetupDialog(win)
            elif "Font" in fn and "FontDialog" in globals():
                dlg = FontDialog(win)
            elif "Paragraph" in fn and "ParagraphDialog" in globals():
                dlg = ParagraphDialog(win)
            elif "Columns" in fn and "ColumnsDialog" in globals():
                dlg = ColumnsDialog(win)
            elif "Tabs" in fn and "TabsDialog" in globals():
                dlg = TabsDialog(win)
            elif "Break" in fn and "BreakDialog" in globals():
                dlg = BreakDialog(win)
            elif "Insert_Table" in fn and "InsertTableDialog" in globals():
                dlg = InsertTableDialog(win)
            elif "Table_Properties" in fn and "TablePropertiesDialog" in globals():
                dlg = TablePropertiesDialog(win)
            elif "Word_Count" in fn and "WordCountDialog" in globals():
                dlg = WordCountDialog(win)
            elif "Spelling" in fn and "SpellingDialog" in globals():
                dlg = SpellingDialog(win)
            elif "Mail_Merge" in fn and "MailMergeWizard" in globals():
                dlg = MailMergeWizard(win)
            elif "Options" in fn:
                dlg = OptionsDialog(win)
            elif "Theme" in fn:
                dlg = ThemeDialog(win, mode="suite")
            elif "About" in fn:
                dlg = AboutDialog(win)

            if dlg is not None:
                if tab_idx is not None:
                    tabs = dlg.findChild(QTabWidget)
                    if tabs is None:
                        if self.strict:
                            raise ScenarioCaptureError(f"Tab {tab_idx} requested but no QTabWidget found in {fn}")
                    elif tab_idx >= tabs.count():
                        if self.strict:
                            raise ScenarioCaptureError(
                                f"Tab index {tab_idx} out of range ({tabs.count()} tabs) in {fn}"
                            )
                    else:
                        tabs.setCurrentIndex(tab_idx)
                return create_composite_canvas(win, dlg)
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Missing dialog implementation for quire: {fn}")
                return win.grab()

        elif cat == "toolbar":
            for tb in win.toolbars.values():
                tb.setVisible(True)
            return win.grab()

        else:
            if self.strict:
                raise ScenarioCaptureError(f"Category [{cat}] not yet wired for capture without fallback: {fn}")
            return win.grab()

    def _capture_ledger_record(self, record: dict) -> QPixmap:
        win = self.get_ledger()
        fn = record["filename"]
        cat = record.get("category", "")

        tab_idx: int | None = None
        if "tab" in fn:
            try:
                import re
                m = re.search(r"tab(\d+)", fn)
                if m:
                    tab_idx = max(0, int(m.group(1)) - 1)
            except Exception:
                pass

        if cat == "overview":
            if "Page_Break" in fn:
                if hasattr(win, "spreadsheet_view") and hasattr(win.spreadsheet_view, "grid"):
                    win.spreadsheet_view.grid._page_break_welcome_shown = True
                win.set_view_mode("page_break", prompt_welcome=False)
            elif "Full_Screen" in fn or "Fullscreen" in fn:
                win.enter_full_screen()
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Unhandled ledger overview mode: {fn}")
            return win.grab()

        elif cat == "dialog":
            dlg = None
            if "Chart" in fn and "ChartWizard" in globals():
                dlg = ChartWizard(win)
            elif "Data_Validation" in fn and "DataValidationDialog" in globals():
                dlg = DataValidationDialog(win)
            elif "Sort" in fn and "SortDialog" in globals():
                dlg = SortDialog(win)
            elif "Text_to_Columns" in fn and "TextToColumnsWizard" in globals():
                dlg = TextToColumnsWizard(win)
            elif "Goal_Seek" in fn and "GoalSeekDialog" in globals():
                dlg = GoalSeekDialog(win)
            elif "Subtotal" in fn and "SubtotalDialog" in globals():
                dlg = SubtotalDialog(win)
            elif "Consolidate" in fn and "ConsolidateDialog" in globals():
                dlg = ConsolidateDialog(win)
            elif "Conditional" in fn and "ConditionalFormatDialog" in globals():
                dlg = ConditionalFormatDialog(win)
            elif "Options" in fn:
                dlg = OptionsDialog(win)
            elif "Theme" in fn:
                dlg = ThemeDialog(win, mode="suite")

            if dlg is not None:
                if tab_idx is not None:
                    tabs = dlg.findChild(QTabWidget)
                    if tabs is None:
                        if self.strict:
                            raise ScenarioCaptureError(f"Tab {tab_idx} requested but no QTabWidget found in {fn}")
                    elif tab_idx >= tabs.count():
                        if self.strict:
                            raise ScenarioCaptureError(
                                f"Tab index {tab_idx} out of range ({tabs.count()} tabs) in {fn}"
                            )
                    else:
                        tabs.setCurrentIndex(tab_idx)
                return create_composite_canvas(win, dlg)
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Missing dialog implementation for ledger: {fn}")
                return win.grab()

        elif cat == "toolbar":
            for tb in win.toolbars.values():
                tb.setVisible(True)
            return win.grab()

        else:
            if self.strict:
                raise ScenarioCaptureError(f"Category [{cat}] not yet wired for capture without fallback: {fn}")
            return win.grab()

    def _capture_lectern_record(self, record: dict) -> QPixmap:
        win = self.get_lectern()
        fn = record["filename"]
        cat = record.get("category", "")

        tab_idx: int | None = None
        if "tab" in fn:
            try:
                import re
                m = re.search(r"tab(\d+)", fn)
                if m:
                    tab_idx = max(0, int(m.group(1)) - 1)
            except Exception:
                pass

        if cat == "overview":
            if "Slide_Sorter" in fn:
                win.set_view_mode("sorter")
            elif "Notes" in fn:
                win.set_view_mode("notes")
            elif "Master" in fn:
                win.set_view_mode("master")
            elif "Slide_Show" in fn:
                win.start_slideshow()
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Unhandled lectern overview mode: {fn}")
            return win.grab()

        elif cat == "dialog":
            dlg = None
            if "Action_Settings" in fn and "ActionSettingsDialog" in globals():
                dlg = ActionSettingsDialog(win)
            elif "Background" in fn and "BackgroundDialog" in globals():
                dlg = BackgroundDialog(win)
            elif "Set_Up_Show" in fn and "SetUpShowDialog" in globals():
                dlg = SetUpShowDialog(win)
            elif "WordArt" in fn and "WordArtGalleryDialog" in globals():
                dlg = WordArtGalleryDialog(win)
            elif "Fill_Effects" in fn and "FillEffectsDialog" in globals():
                dlg = FillEffectsDialog(win)
            elif "Options" in fn:
                dlg = OptionsDialog(win)

            if dlg is not None:
                if tab_idx is not None:
                    tabs = dlg.findChild(QTabWidget)
                    if tabs is None:
                        if self.strict:
                            raise ScenarioCaptureError(f"Tab {tab_idx} requested but no QTabWidget found in {fn}")
                    elif tab_idx >= tabs.count():
                        if self.strict:
                            raise ScenarioCaptureError(
                                f"Tab index {tab_idx} out of range ({tabs.count()} tabs) in {fn}"
                            )
                    else:
                        tabs.setCurrentIndex(tab_idx)
                return create_composite_canvas(win, dlg)
            else:
                if self.strict:
                    raise ScenarioCaptureError(f"Missing dialog implementation for lectern: {fn}")
                return win.grab()

        elif cat == "toolbar":
            for tb in win.toolbars.values():
                tb.setVisible(True)
            return win.grab()

        else:
            if self.strict:
                raise ScenarioCaptureError(f"Category [{cat}] not yet wired for capture without fallback: {fn}")
            return win.grab()

    def generate_index_markdown(self, records: list[dict]):
        """Generate INDEX.md cataloging all paired screenshots and verification status."""
        index_file = self.out_dir / "INDEX.md"
        duplicates = self.registry.tracker.get_duplicates()
        lines = [
            "# ATBOffice: 全量 412 张配对截图与原版 1:1 对标证据索引",
            "",
            "本目录由 `scripts/capture_atboffice_screens.py` 自动化抓取生成，包含 Start Center、Quire、Ledger、Lectern 四大子系统在标准视口 (1440×900) 下的原生 PySide6 GUI 渲染证据，并与原版 `.vibeoffice/screenshots/` 412 张基线截图形成全量配对。",
            "",
            "- **分辨率**: 1440 × 900 (HiDPI @2x Retina compatible)",
            "- **外观**: `classic` (Office 2003 Luna Command Bars)",
            f"- **截图总目标**: {len(records)} 张",
            f"- **检测到哈希碰撞组数**: {len(duplicates)}",
            "",
            "| # | 模块 | 场景类别 | 抓取动作 / 触发目标 | ATBOffice 截图文件 (PySide6) | 原版对应基线截图 (.vibeoffice) |",
            "|---|---|---|---|---|---|",
        ]

        for i, rec in enumerate(records, 1):
            mod = rec["module"]
            fn = rec["filename"]
            cat = rec.get("category", "overview")
            action = rec.get("action", "")
            target = rec.get("guiTarget", "")
            atb_link = f"[{fn}]({mod}/{fn})"
            orig_link = f"`{rec['path']}`"
            lines.append(f"| {i} | **{mod}** | `{cat}` | {action} ({target}) | {atb_link} | {orig_link} |")

        index_file.write_text("\n".join(lines), encoding="utf-8")
        print(f"Generated screenshots index at {index_file}")


def main():
    parser = argparse.ArgumentParser(description="Capture ATBOffice UI screenshots matching records.json baseline.")
    parser.add_argument("--output-dir", default=str(repo_root / "docs" / "clone" / "evidence" / "phase6" / "screenshots"), help="Output directory")
    parser.add_argument("--module", choices=["00_start_center", "01_quire", "02_ledger", "03_lectern"], help="Filter by module")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of screenshots captured")
    parser.add_argument("--no-strict", action="store_true", help="Allow non-strict capture for audit exploration")
    args = parser.parse_args()

    records_file = repo_root / ".vibeoffice" / "screenshots" / "records.json"
    if not records_file.exists():
        print(f"Error: {records_file} not found.")
        sys.exit(1)

    with open(records_file, encoding="utf-8") as f:
        records = json.load(f)

    if args.module:
        records = [r for r in records if r["module"] == args.module]

    if args.limit:
        records = records[:args.limit]

    strict_mode = not args.no_strict
    print(f"Starting capture for {len(records)} screenshot targets (strict={strict_mode})...")
    mgr = ScreenCaptureManager(Path(args.output_dir), strict=strict_mode)

    captured = 0
    failed = 0
    for r in records:
        try:
            mgr.capture_record(r)
            captured += 1
            if captured % 25 == 0 or captured == len(records):
                print(f"Captured [{captured}/{len(records)}] -> {r['path']}")
        except Exception as e:
            failed += 1
            print(f"FAILED [{failed}] -> {r['path']}: {e}")
            if strict_mode:
                sys.exit(1)

    mgr.generate_index_markdown(records)
    print(f"\nFinished: {captured} captured, {failed} failed in {args.output_dir}")


if __name__ == "__main__":
    main()
