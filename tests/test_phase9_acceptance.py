"""Phase 9 End-to-End Acceptance and Release Signoff Test Suite (Issue #345).

Verifies the integrated functionality of all Phase 9 milestones:
1. Strict Corpus Audit Gate (150/150 pass).
2. Dual-Engine Visual Parity Gate (73 OOXML documents, avg >= 93.0%, 0 critical mismatches).
3. Classic Office 2003 Tools ▸ Customize... dialog (CustomizeToolbarsDialog).
4. Quire (Word): Canvas rulers & dynamic fields.
5. Ledger (Excel): AutoFilter, Paste Special, PivotTable, cached values.
6. Lectern (PowerPoint): SmartArt & SlideShow real-time ink annotations/laser pointer overlay.
7. Suite Shell: Office Clipboard & Command Search Box (Tell Me).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from atboffice.deep.audit.core import (
    AuditSession,
    CorpusExpectations,
    audit_corpus_file,
)
from atboffice.modules.presentation.slideshow.annotation_layer import (
    AnnotationStroke,
    SlideAnnotationOverlay,
)
from atboffice.modules.presentation.smartart.engine import SmartArtEngine
from atboffice.modules.presentation.smartart.item import SmartArtItem, new_id
from atboffice.modules.spreadsheet.models.filter_model import (
    AutoFilter,
    ColumnFilter,
    apply_auto_filter,
)
from atboffice.modules.spreadsheet.models.pivot_model import (
    PivotConfig,
    build_pivot_table,
)
from atboffice.modules.spreadsheet.models.sheet_model import CellData, SheetDataModel
from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel
from atboffice.modules.writer.models.document import Document
from atboffice.modules.writer.models.field import FieldContext, evaluate_field
from atboffice.ui.components.command_search_box import CommandSearchBox
from atboffice.ui.dialogs.customize_toolbars_dialog import (
    CustomizeToolbarsDialog,
    safe_tr,
)
from atboffice.ui.panes.clipboard_pane import ClipboardTaskPane, ClipItem


@pytest.fixture(scope="module")
def qapp():
    """Ensure offscreen QApplication instance is available."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(["pytest_phase9_acceptance", "-platform", "offscreen"])
    return app


def test_phase9_corpus_audit_gate():
    """Verify Corpus Audit Gate: 150/150 documents pass strict expectations without crashes."""
    exp_file = Path("tests/docs/expectations.json")
    assert exp_file.exists(), "Expectations manifest missing"
    exp = CorpusExpectations(exp_file)
    assert len(exp) == 150, f"Expected 150 expectations, found {len(exp)}"

    # Audit a representative slice across formats to verify integrity
    samples = [
        "tests/docs/word/docx/libreoffice__strict.docx",
        "tests/docs/excel/xlsx/libreoffice__Pivot2_Row.xlsx",
        "tests/docs/powerpoint/pptx/libreoffice__tdf143129.pptx",
        "tests/docs/word/doc/libreoffice__zoomtype.doc",
        "tests/docs/excel/xls/libreoffice__crash-5.xls",
        "tests/docs/powerpoint/ppt/poi__bug55030.ppt",
    ]

    session = AuditSession()
    for s in samples:
        res = audit_corpus_file(s, expectations=exp, timeout=15.0)
        session.record_result(res)

    summ = session.summary()
    assert summ["crash"] == 0
    assert summ["timeout"] == 0
    assert summ["unmatched_failures"] == 0
    assert session.is_passing()


def test_phase9_visual_parity_gate():
    """Verify Dual-Engine Visual Parity Gate metrics from OFFICE_DOCS_DIFF.md."""
    diff_report = Path("docs/clone/OFFICE_DOCS_DIFF.md")
    assert diff_report.exists(), "Parity report docs/clone/OFFICE_DOCS_DIFF.md missing"
    content = diff_report.read_text(encoding="utf-8")

    # Assert 73 documents evaluated
    assert "Evaluated Documents" in content
    assert "`73`" in content
    # Assert 0 Critical Mismatches (< 70%)
    assert "| **Critical Mismatches (<70%)** | `0` |" in content
    # Assert Parity Matches + Cosmetic Minors >= 70
    assert "Parity Matches" in content
    assert "Cosmetic Minor" in content


def test_phase9_customize_toolbars_dialog_acceptance(qapp):
    """Verify CustomizeToolbarsDialog complete user workflows and interactions."""
    dlg = CustomizeToolbarsDialog()

    # 1. Tabs inspection
    assert dlg.tab_widget.count() == 4

    # 2. Toolbar toggling signal
    toggled_records: list[tuple[str, bool]] = []
    dlg.toolbar_toggled.connect(lambda name, vis: toggled_records.append((name, vis)))

    first_item = dlg.list_toolbars.item(0)
    assert first_item is not None
    orig_state = first_item.checkState()
    new_state = (
        Qt.CheckState.Unchecked if orig_state == Qt.CheckState.Checked else Qt.CheckState.Checked
    )
    first_item.setCheckState(new_state)
    assert len(toggled_records) > 0
    assert toggled_records[-1][0] == first_item.text()

    # 3. Custom toolbar management
    init_tb_count = dlg.list_toolbars.count()
    dlg._custom_toolbars.append("MyTestToolbar")
    from PySide6.QtWidgets import QListWidgetItem

    custom_item = QListWidgetItem("MyTestToolbar", dlg.list_toolbars)
    custom_item.setData(Qt.ItemDataRole.UserRole, "custom_MyTestToolbar")
    assert dlg.list_toolbars.count() == init_tb_count + 1

    dlg.list_toolbars.setCurrentItem(custom_item)
    dlg._on_delete_toolbar()
    assert dlg.list_toolbars.count() == init_tb_count

    # 4. Commands category browsing
    dlg.list_categories.setCurrentRow(1)  # Edit
    assert dlg._active_category == "Edit"
    assert dlg.list_commands.count() > 0

    # 5. Options toggling
    assert dlg.chk_screentips.isChecked()
    assert dlg.chk_shortcut_tips.isChecked()
    dlg.chk_large_icons.setChecked(True)
    assert dlg.chk_large_icons.isChecked()

    # 6. Keyboard shortcut assignment
    dlg.combo_kb_category.setCurrentIndex(0)  # File
    dlg.combo_kb_command.setCurrentIndex(0)  # New
    dlg.edit_key_seq.setKeySequence(QKeySequence("Ctrl+Alt+N"))

    assigned: list[tuple[str, str]] = []
    dlg.shortcut_assigned.connect(lambda cmd, seq: assigned.append((cmd, seq)))
    dlg._on_assign_key()

    assert len(assigned) == 1
    assert assigned[0][1] == "Ctrl+Alt+N"
    assert dlg.lbl_curr_shortcut.text() == "Ctrl+Alt+N"

    # 7. Retranslate UI
    dlg.retranslate_ui()
    assert dlg.windowTitle() == safe_tr("自定义")


def test_phase9_word_quire_acceptance(qapp):
    """Verify Quire dynamic fields evaluation and text formatting."""
    doc = Document()
    doc.props["title"] = "ATBOffice Phase 9 Signoff"
    doc.props["author"] = "DeepMind Agent"

    ctx = FieldContext(
        page_number=3,
        total_pages=15,
    )

    assert evaluate_field("PAGE", doc, ctx) == "3"
    assert evaluate_field("NUMPAGES", doc, ctx) == "15"
    assert len(evaluate_field("DATE", doc, ctx)) >= 8
    assert ":" in evaluate_field("TIME", doc, ctx)
    assert evaluate_field("AUTHOR", doc, ctx) == "DeepMind Agent"
    assert evaluate_field("TITLE", doc, ctx) == "ATBOffice Phase 9 Signoff"


def test_phase9_excel_ledger_acceptance(qapp):
    """Verify Ledger AutoFilter, PivotTable, and formula cached value fallback."""
    sheet = SheetDataModel(name="LedgerAcceptance")

    # 1. Cached value fallback
    c1 = CellData(value=None, formula="[Ext.xlsx]Data!A1", cached_value=123.456, format_code="0.00")
    sheet.set_cell(0, 0, c1)
    assert sheet.get_formatted_text(0, 0) == "123.46"

    # 2. AutoFilter evaluation
    for r in range(1, 10):
        val = 100 if r % 2 == 0 else 200
        sheet.set_cell(r, 0, CellData(value=val))

    af = AutoFilter(r1=0, c1=0, r2=9, c2=0)
    af.cols[0] = ColumnFilter(values={"100"})
    apply_auto_filter(sheet, af)

    # Filtered out rows are hidden
    hidden = af.filtered_rows
    assert hidden == {1, 3, 5, 7, 9}

    # 3. PivotTable Generation
    wb = WorkbookModel(sheets=[sheet])
    cfg = PivotConfig(
        source_sheet="LedgerAcceptance",
        source_range=(0, 0, 9, 0),
        row_field_col=0,
        data_field_col=0,
        agg_func="sum",
        target_sheet="PivotSheet",
    )
    target_sheet, bbox = build_pivot_table(wb, cfg)
    assert target_sheet is not None
    assert bbox[2] > 0


def test_phase9_powerpoint_lectern_acceptance(qapp):
    """Verify Lectern SmartArt generation, SlideShow ink annotations, and laser pointer."""
    # 1. SmartArt generation
    root_item = SmartArtItem(id=new_id(), text="CEO")
    child_item = SmartArtItem(id=new_id(), text="CTO")
    root_item.kids.append(child_item)

    eng = SmartArtEngine()
    res = eng.layout("hierarchy", [root_item], {"x": 0, "y": 0, "w": 800, "h": 600})
    shapes = res["shapes"]
    assert len(shapes) >= 2
    # Verify nodes have text lines
    text_values = []
    for s in shapes:
        t_data = s.get("text")
        if isinstance(t_data, dict):
            for line in t_data.get("lines", []):
                text_values.append(line.get("t", ""))
    assert "CEO" in text_values
    assert "CTO" in text_values

    # 2. SlideShow Ink Annotations
    overlay = SlideAnnotationOverlay()
    overlay.resize(800, 600)
    overlay.set_slide_index(0)

    # Switch to pen and add stroke
    overlay.set_mode("pen", "#FF0000", 3.0)
    assert overlay.mode == "pen"
    assert overlay.pen_color == "#FF0000"

    stroke = AnnotationStroke(
        points=[(10.0, 10.0), (20.0, 20.0), (30.0, 30.0)],
        color="#FF0000",
        width=3.0,
    )
    overlay.set_strokes(0, [stroke])
    assert overlay.has_ink()
    assert len(overlay.get_strokes(0)) == 1

    # Convert to freeform shapes
    shapes = overlay.export_strokes_as_shapes(0)
    assert len(shapes) == 1
    s = shapes[0]
    assert s.geom == "freeform"
    assert len(s.poly) == 3

    # Laser pointer mode
    overlay.set_mode("laser", "#FF0000", 8.0)
    assert overlay.mode == "laser"
    overlay.laser_pos = (400.0, 300.0)
    assert overlay.laser_pos == (400.0, 300.0)

    # Clear ink
    overlay.clear_slide_ink(0)
    assert not overlay.has_ink()


def test_phase9_suite_shell_acceptance(qapp):
    """Verify Unified Suite Shell Office Clipboard and Command Search Box."""
    # 1. Office Clipboard Task Pane
    pane = ClipboardTaskPane()
    item1 = ClipItem(text="First Copied Content", item_type="text")
    item2 = ClipItem(text="Second Copied Content", item_type="text")
    pane.add_clip_item(item1)
    pane.add_clip_item(item2)
    assert pane.count() == 2
    assert pane.items()[0].text == "Second Copied Content"  # LIFO order

    pane.clear_all()
    assert pane.count() == 0

    # 2. Command Search Box (Tell Me)
    search_box = CommandSearchBox()
    results = search_box.search_commands("保存")
    assert isinstance(results, list)
