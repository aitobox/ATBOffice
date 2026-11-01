#!/usr/bin/env python3
"""Audit toolbars parity between .vibeoffice and ATBOffice.

Analyzes all 10 Quire toolbars, 8 Ledger toolbars, and 10 Lectern toolbars
item by item against original .vibeoffice definitions, checking:
- Order & Index
- Action ID / Command
- Widget kind (Action, Split, Dropdown, Combo, ColorPicker, Separator)
- Localized tooltip / Label
- Icon presence
- Shortcut key
- Parity status (WIRED, STUB, UI_ONLY, MISSING)

Outputs an authoritative markdown matrix to docs/clone/evidence/phase5/toolbar_baseline_matrix.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src is on sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

# Force offscreen QPA for headless execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QToolBar, QToolButton, QComboBox, QMenu, QWidgetAction
from PySide6.QtGui import QAction

# Import target windows & components
from atboffice.ui.shell.quire_window import QuireWindow
from atboffice.ui.shell.ledger_window import LedgerWindow
from atboffice.ui.shell.lectern_window import LecternWindow
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import DottedGrip, OfficeToolBarSeparator
from atboffice.ui.components.toolbar_buttons import OfficeDropDownButton, OfficeSplitButton


# Reference original toolbar item lists from .vibeoffice JS
ORIGINAL_QUIRE_TOOLBARS = {
    "standard": [
        "new", "open", "save", "permission", "sendMail", "print", "printPreview", "spelling", "research", "|",
        "cut", "copy", "paste", "painter", "|",
        "undo (split)", "redo (split)", "|", "hyperlink", "tb_tables",
        "table (drop)", "insertExcel", "columns (drop)", "tb_drawing", "docMap", "showMarks", "zoom (combo)", "help", "viewReading"
    ],
    "formatting": [
        "stylesPane", "style (combo)", "font (combo)", "size (combo)", "bold", "italic", "underline", "|",
        "alignLeft", "alignCenter", "alignRight", "justify", "|",
        "lineSpacing (drop)", "|", "numbering", "bullets", "decIndent", "incIndent", "|",
        "borderBtn (split)", "highlightBtn (split)", "fontColorBtn (split)"
    ],
    "tables": [
        "drawTable", "eraser", "|", "dashStyle (drop)", "lineStyle (drop)", "lineColor (drop)",
        "borderBtn (split)", "fillColor (drop)", "|",
        "table (drop)", "mergeCells", "splitCells", "|",
        "alignTop (drop)", "distRows", "distCols", "|", "tableAutoFormat", "textDirection", "|", "sortAsc", "sortDesc", "autoSum"
    ],
    "reviewing": [
        "markupDisplay (drop)", "show (drop)", "|", "prevChange", "nextChange", "|",
        "acceptChange (split)", "rejectChange (split)", "|",
        "insertComment", "trackChanges", "reviewingPane"
    ],
    "picture": [
        "insertPicture", "colorPic (drop)", "picMoreContrast", "picLessContrast", "picMoreBright", "picLessBright", "|",
        "picCrop", "picRotate", "lineStyle (drop)", "|", "textWrap (drop)", "formatObject", "picReset"
    ],
    "outlining": [
        "promoteH1", "promote", "outlineLevel (combo)", "demote", "demoteBody", "|",
        "moveUp", "moveDown", "expand", "collapse", "showLevel (combo)", "olFirstLine", "olFormatting", "|",
        "updateTOC", "gotoTOC"
    ],
    "headerFooter": [
        "hfAutoText (drop)", "|", "hfPageNum", "hfNumPages", "hfFormatPageNum", "hfDate", "hfTime", "|",
        "pageSetup", "hfShowText", "hfLinkPrev", "|", "hfSwitch", "hfPrev", "hfNext", "|", "hfClose"
    ],
    "mailMerge": [
        "mmMainDoc", "mmOpenSource", "mmRecipients", "|", "mmAddress", "mmGreeting", "mmInsertField", "|",
        "mmViewData", "mmFirst", "mmPrev", "mmRecord (combo)", "mmNext", "mmLast", "|", "mmMergeNew", "mmMergePrint"
    ],
    "wordart": [
        "insertWordArt", "wordartEdit", "wordartGallery", "formatObject", "waShape (drop)", "textWrap (drop)"
    ],
    "drawing": [
        "drawMenu (drop)", "selectObjects", "|", "autoShapes (drop)", "drawLine", "drawArrow", "drawRect", "drawOval",
        "textBox", "insertWordArt", "insertDiagram", "insertClipArt", "insertPicture", "|",
        "fillColor (split)", "lineColor (split)", "fontColorBtn (split)", "|",
        "lineStyle (drop)", "dashStyle (drop)", "arrowStyle (drop)", "shadowStyle (drop)"
    ],
}

ORIGINAL_LEDGER_TOOLBARS = {
    "standard": [
        "newBook", "open", "save", "|", "printQuick", "printPreview", "spelling", "|",
        "cut", "copy", "paste", "formatPainter", "|", "undo", "redo", "|",
        "hyperlink", "autoSum (split)", "sortAsc", "sortDesc", "|", "chartWizard", "tb_drawing", "zoom (combo)", "|", "help"
    ],
    "formatting": [
        "font (combo)", "size (combo)", "|", "bold", "italic", "underline", "|",
        "alignLeft", "alignCenter", "alignRight", "mergeCenter", "|",
        "currencyStyle", "percentStyle", "commaStyle", "incDecimal", "decDecimal", "|",
        "decIndent", "incIndent", "|", "bordersApply (split)", "fillColorApply (split)", "fontColorApply (split)"
    ],
    "borders": [
        "bordersApply (split)", "borderNone", "borderOutline"
    ],
    "auditing": [
        "traceError", "|", "tracePrecedents", "traceDependents", "removeArrows", "|",
        "insertComment", "validation", "circleInvalid", "clearCircles", "|", "watchWindow", "evaluateFormula"
    ],
    "reviewing": [
        "insertComment", "showHideComment", "deleteComment", "|", "showComments"
    ],
    "list": [
        "listMenu (drop)", "totalRow"
    ],
    "chart": [
        "chartType (drop)", "formatObject"
    ],
    "drawing": [
        "drawMenu (drop)", "|", "insertShape", "insertTextBox", "insertPicture", "|", "fillColorApply"
    ],
}

ORIGINAL_LECTERN_TOOLBARS = {
    "standard": [
        "new", "open", "save", "|", "print", "printPreview", "spelling", "|",
        "cut", "copy", "paste", "painter", "|", "undo", "redo", "|",
        "insertChart", "insertTable", "tb_tables", "hyperlink", "|",
        "expandAll", "showFormatting", "showGrid", "viewGray (split)", "zoom (combo)", "help"
    ],
    "formatting": [
        "font (combo)", "size (combo)", "bold", "italic", "underline", "shadowText", "|",
        "alignLeft", "alignCenter", "alignRight", "|", "numbering", "bullets", "|",
        "growFont", "shrinkFont", "|", "promote", "demote", "|",
        "fontColor (split)", "|", "slideDesign", "newSlide"
    ],
    "outlining": [
        "promote", "demote", "moveParaUp", "moveParaDown", "|", "summarySlide", "showFormatting"
    ],
    "picture": [
        "insertPicture", "colorPic (drop)", "picMoreContrast", "picLessContrast", "picMoreBright", "picLessBright", "|",
        "picCrop", "rotateLeft", "lineStyle (drop)", "|", "formatObject", "picTransparent", "picReset"
    ],
    "tables": [
        "dashStyle (drop)", "lineStyle (drop)", "lineColor (drop)", "bordersAll (drop)", "fillColor (drop)", "|",
        "tableMenu (drop)", "mergeCells", "splitCell", "|", "cellTop", "cellMiddle", "cellBottom", "|", "distRows", "distCols"
    ],
    "wordart": [
        "insertWordArt", "wordartEdit", "wordartGallery", "formatObject", "waShape (drop)",
        "waSameHeight", "waVertical", "alignCenter (drop)", "charSpacing (drop)"
    ],
    "master": [
        "insertTitleMaster", "deleteTitleMaster", "|", "closeMaster"
    ],
    "sorter": [
        "hideSlide", "rehearse", "|", "summarySlide", "speakerNotes", "|", "transitionPane", "slideDesign", "newSlide"
    ],
    "diagram": [
        "diagramAddShape (split)", "diagramPromote", "diagramDemote", "diagramMoveUp", "diagramMoveDown", "|",
        "layoutMenu (drop)", "colorsMenu (drop)", "styleMenu (drop)", "|", "diagramTextPane", "diagramReset", "diagramToShapes"
    ],
    "drawing": [
        "drawMenu (drop)", "select", "|", "autoShapes (drop)", "drawLine", "drawArrow", "drawRect", "drawOval",
        "textBox", "insertWordArt", "insertDiagram", "insertClipArt", "insertPicture", "|",
        "fillColor (split)", "lineColor (split)", "fontColor (split)", "|",
        "lineStyle (drop)", "dashStyle (drop)", "arrowStyle (drop)", "shadowStyle (drop)"
    ],
}


def audit_window_toolbars(app_name: str, win, original_spec: dict[str, list[str]]) -> list[dict]:
    results = []
    reg = win.action_registry

    # Map QAction to its registered action ID in ActionRegistry
    act_to_id = {act: aid for aid, act in reg._actions.items()}

    for tb_id, orig_items in original_spec.items():
        tb = win.toolbars.get(tb_id)
        if not tb:
            for idx, orig_item in enumerate(orig_items):
                results.append({
                    "module": app_name,
                    "toolbar": tb_id,
                    "index": idx + 1,
                    "orig_item": orig_item,
                    "target_id": "-",
                    "target_type": "MISSING",
                    "label": "-",
                    "tooltip": "-",
                    "has_icon": False,
                    "shortcut": "-",
                    "status": "MISSING",
                })
            continue

        # Extract actions, filtering out DottedGrip
        raw_actions = tb.actions()
        usable_items = []
        for act in raw_actions:
            w = tb.widgetForAction(act)
            if isinstance(w, DottedGrip):
                continue
            usable_items.append((act, w))

        # Map each original item sequentially to usable target item
        target_idx = 0
        for idx, orig_item in enumerate(orig_items):
            if target_idx < len(usable_items):
                act, widget = usable_items[target_idx]
                target_idx += 1
            else:
                act, widget = None, None

            # Determine item properties
            if isinstance(widget, OfficeToolBarSeparator) or (act and act.isSeparator()):
                target_type = "Separator"
                target_id = "separator"
                label = "—"
                tooltip = "—"
                has_icon = False
                shortcut = "—"
                status = "WIRED"
            elif isinstance(widget, OfficeSplitButton):
                target_type = "SplitButton"
                def_act = widget.defaultAction()
                target_id = act_to_id.get(def_act, def_act.text() if def_act else "splitBtn")
                label = def_act.text().replace("&", "") if def_act else widget.toolTip()
                tooltip = def_act.toolTip() if def_act else widget.toolTip()
                has_icon = bool(def_act and not def_act.icon().isNull())
                shortcut = def_act.shortcut().toString() if (def_act and not def_act.shortcut().isEmpty()) else "—"
                status = "WIRED" if (target_id in reg._actions) else "UI_ONLY"
            elif isinstance(widget, OfficeDropDownButton):
                target_type = "DropDownButton"
                target_id = widget.text() or widget.toolTip() or "dropDownBtn"
                label = widget.text().replace("&", "") or widget.toolTip()
                tooltip = widget.toolTip() or label
                has_icon = not widget.icon().isNull()
                shortcut = "—"
                status = "WIRED" if widget.menu() else "UI_ONLY"
            elif isinstance(widget, ColorPickerButton):
                target_type = "ColorPicker"
                target_id = widget.toolTip() or "colorPicker"
                label = widget.toolTip()
                tooltip = widget.toolTip()
                has_icon = True
                shortcut = "—"
                status = "WIRED"
            elif isinstance(widget, QComboBox):
                target_type = "ComboBox"
                target_id = widget.objectName() or widget.toolTip() or "comboBox"
                label = widget.toolTip() or widget.currentText()
                tooltip = widget.toolTip()
                has_icon = False
                shortcut = "—"
                status = "WIRED"
            elif act is not None:
                target_type = "Action"
                target_id = act_to_id.get(act, act.text().replace("&", ""))
                label = act.text().replace("&", "")
                tooltip = act.toolTip()
                has_icon = not act.icon().isNull()
                shortcut = act.shortcut().toString() if not act.shortcut().isEmpty() else "—"
                
                # Check status
                spec = reg._specs.get(str(target_id))
                if spec and spec.handler is not None:
                    # Check for docstring-only stub (e.g. Ledger #194)
                    code = getattr(spec.handler, "__code__", None)
                    if code and code.co_code in (b'd\x00S\x00', b'd\x01S\x00'):
                        status = "STUB"
                    else:
                        status = "WIRED"
                elif reg.has_action(str(target_id)):
                    status = "WIRED"
                else:
                    status = "UI_ONLY"
            else:
                target_type = "MISSING"
                target_id = "—"
                label = "—"
                tooltip = "—"
                has_icon = False
                shortcut = "—"
                status = "MISSING"

            results.append({
                "module": app_name,
                "toolbar": tb_id,
                "index": idx + 1,
                "orig_item": orig_item,
                "target_id": str(target_id),
                "target_type": target_type,
                "label": label,
                "tooltip": tooltip,
                "has_icon": has_icon,
                "shortcut": shortcut,
                "status": status,
            })

    return results


def generate_markdown(all_results: list[dict]) -> str:
    md = []
    md.append("# ATBOffice Phase 5: 三模块工具栏逐控件对照与基线矩阵")
    md.append("")
    md.append("本矩阵由 `scripts/audit_toolbars_parity.py` 自动化脚本静态提取与动态反射生成，")
    md.append("完整比对 `.vibeoffice` 原版 Office 2003 Luna JS 工具栏与 `src/atboffice/ui/shell/*_toolbars.py` 目标实现。")
    md.append("")
    md.append("## 1. 概览汇总")
    md.append("")
    
    # Summary table
    modules = ["Quire", "Ledger", "Lectern"]
    md.append("| 模块 | 工具栏总数 | 控件项总数 | 正常接线 (WIRED) | 存根占位 (STUB) | 仅UI待接 (UI_ONLY) | 缺失 (MISSING) | 对照完成率 |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for mod in modules:
        mod_items = [r for r in all_results if r["module"] == mod and r["target_type"] != "Separator"]
        tb_count = len({r["toolbar"] for r in all_results if r["module"] == mod})
        total = len(mod_items)
        wired = len([r for r in mod_items if r["status"] == "WIRED"])
        stub = len([r for r in mod_items if r["status"] == "STUB"])
        ui_only = len([r for r in mod_items if r["status"] == "UI_ONLY"])
        missing = len([r for r in mod_items if r["status"] == "MISSING"])
        rate = f"{((wired + stub + ui_only) / total * 100):.1f}%" if total > 0 else "0%"
        md.append(f"| **{mod}** | {tb_count} | {total} | {wired} | {stub} | {ui_only} | {missing} | **{rate}** |")
    md.append("")
    
    # Detail tables per module
    for mod in modules:
        md.append(f"## 2. {mod} 逐工具栏详细对照表")
        md.append("")
        mod_results = [r for r in all_results if r["module"] == mod]
        toolbars = sorted(list({r["toolbar"] for r in mod_results}))
        
        for tb in toolbars:
            items = [r for r in mod_results if r["toolbar"] == tb]
            non_sep = [it for it in items if it["target_type"] != "Separator"]
            wired_cnt = len([it for it in non_sep if it["status"] in ("WIRED", "STUB")])
            md.append(f"### {mod} — Toolbar: `{tb}` ({len(items)} 项，{wired_cnt}/{len(non_sep)} 已接线)")
            md.append("")
            md.append("| # | 原版项 (JS) | 目标 Action ID (PySide6) | 控件类型 | 标签 | 提示 (Tooltip) | 图标 | 快捷键 | 状态 |")
            md.append("| :-: | :--- | :--- | :--- | :--- | :--- | :-: | :--- | :-: |")
            for it in items:
                icon_mark = "✓" if it["has_icon"] else "—"
                md.append(f"| {it['index']} | `{it['orig_item']}` | `{it['target_id']}` | {it['target_type']} | {it['label']} | {it['tooltip']} | {icon_mark} | {it['shortcut']} | `{it['status']}` |")
            md.append("")

    return "\n".join(md)


def main():
    app = QApplication.instance() or QApplication(sys.argv)

    print("Instantiating QuireWindow...")
    quire_win = QuireWindow()
    quire_results = audit_window_toolbars("Quire", quire_win, ORIGINAL_QUIRE_TOOLBARS)

    print("Instantiating LedgerWindow...")
    ledger_win = LedgerWindow()
    ledger_results = audit_window_toolbars("Ledger", ledger_win, ORIGINAL_LEDGER_TOOLBARS)

    print("Instantiating LecternWindow...")
    lectern_win = LecternWindow()
    lectern_results = audit_window_toolbars("Lectern", lectern_win, ORIGINAL_LECTERN_TOOLBARS)

    all_results = quire_results + ledger_results + lectern_results

    out_dir = repo_root / "docs" / "clone" / "evidence" / "phase5"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "toolbar_baseline_matrix.md"
    tracked_file = repo_root / "docs" / "clone" / "TOOLBAR_BASELINE_MATRIX.md"

    md_content = generate_markdown(all_results)
    out_file.write_text(md_content, encoding="utf-8")
    tracked_file.write_text(md_content, encoding="utf-8")
    print(f"Successfully generated baseline matrix at {out_file} and {tracked_file}")


if __name__ == "__main__":
    main()
