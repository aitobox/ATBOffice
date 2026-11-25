"""Office 2003 Undo/Redo drop-downs: list the real history, undo several steps at once."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMenu, QWidget

from atboffice.core.i18n import safe_tr

MAX_ITEMS = 20

# undo entry kind -> label (Quire "type" / Ledger "action")
LABELS: dict[str, str] = {
    "doc_snapshot": "编辑",
    "typing": "键入",
    "paragraph_indent": "段落缩进",
    "paragraph_tabs": "制表位",
    "section_margins": "页边距",
    "footnote": "脚注",
    "edit": "键入",
    "paste": "粘贴",
    "paste_special": "选择性粘贴",
    "cut": "剪切",
    "clear_all": "全部清除",
    "clear_contents": "清除内容",
    "clear_formats": "清除格式",
    "clear_comments": "清除批注",
    "autofill": "自动填充",
    "row_resize": "行高",
    "col_resize": "列宽",
    "filter": "筛选",
    "total_row": "汇总行",
    "hyperlink": "超链接",
    "format_painter": "格式刷",
    "copy_to": "复制到",
    "text_to_columns": "分列",
    "spelling": "拼写检查",
    "insert_symbol": "插入符号",
    "data_table": "模拟运算表",
    "scenario_show": "显示方案",
    "sort": "排序",
    "format": "设置格式",
    "insert_rows": "插入行",
    "insert_cols": "插入列",
    "delete_rows": "删除行",
    "delete_cols": "删除列",
    "merge": "合并单元格",
    "auto_sum": "自动求和",
    "edit_cell": "键入",
}


def entry_label(entry: Any) -> str:
    """Readable label for one undo stack entry (dict with "label"/"type"/"action")."""
    if isinstance(entry, dict):
        if entry.get("label"):
            return str(entry["label"])
        kind = entry.get("type") or entry.get("action") or ""
    else:
        kind = getattr(entry, "label", "") or getattr(entry, "type", "") or ""
    return safe_tr(LABELS.get(str(kind), "编辑"))


def populate(menu: QMenu, window: Any, kind: str) -> None:
    """Rebuild ``menu`` from ``window.undo_history(kind)`` (most recent first)."""
    menu.clear()
    labels = (
        list(window.undo_history(kind) or [])[:MAX_ITEMS] if hasattr(window, "undo_history") else []
    )
    if not labels:
        empty = menu.addAction(safe_tr("无操作可撤销" if kind == "undo" else "无操作可重做"))
        empty.setEnabled(False)
        return
    for i, label in enumerate(labels):
        act = menu.addAction(label)
        steps = i + 1
        act.setToolTip(
            safe_tr("撤销 {0} 步操作" if kind == "undo" else "重做 {0} 步操作").format(steps)
        )
        act.triggered.connect(lambda _checked=False, n=steps: window.undo_steps(kind, n))


def attach_undo_history(window: QWidget) -> int:
    """Hook every Undo/Redo split-button menu of ``window``; returns how many were hooked."""
    hooked = 0
    for menu in window.findChildren(QMenu):
        kind = menu.property("split_aid")
        if kind not in ("undo", "redo") or menu.property("undo_history_hooked"):
            continue
        menu.setProperty("undo_history_hooked", True)
        menu.aboutToShow.connect(lambda m=menu, k=kind: populate(m, window, k))
        populate(menu, window, kind)
        hooked += 1
    return hooked
