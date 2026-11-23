"""Compatibility Checker: what a save into a given format loses, in plain words.

Only losses with ``notify=True`` are shown to the user (LOSSLESS_SAVE.md); the rest are
recorded for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication


def safe_tr(text: str) -> str:
    return QCoreApplication.translate("CompatibilityChecker", text)


MACRO_SUFFIXES = {".docm": ".docx", ".xlsm": ".xlsx", ".pptm": ".pptx", ".dotm": ".dotx",
                  ".xltm": ".xltx", ".potm": ".potx"}


@dataclass
class Loss:
    feature: str
    where: str = ""
    count: int = 1
    notify: bool = True
    detail: str = ""


def coerce(raw: Any) -> list[Loss]:
    """Model ``losses`` (dicts, strings or Loss objects) as Loss items."""
    out: list[Loss] = []
    for item in list(raw or []):
        if isinstance(item, Loss):
            out.append(item)
        elif isinstance(item, dict):
            out.append(Loss(
                feature=str(
                    item.get("feature") or item.get("what") or item.get("name")
                    or item.get("kind") or ""
                ),
                where=str(item.get("where") or item.get("place") or ""),
                count=int(item.get("count") or 1),
                notify=bool(item.get("notify", True)),
                detail=str(item.get("detail") or ""),
            ))
        elif item:
            out.append(Loss(feature=str(item)))
    return [loss for loss in out if loss.feature]


def macro_loss(source: Path | None, target: Path) -> list[Loss]:
    if source is None:
        return []
    src, dst = source.suffix.lower(), target.suffix.lower()
    if src in MACRO_SUFFIXES and dst not in MACRO_SUFFIXES:
        return [Loss(safe_tr("宏 (VBA 项目)"), safe_tr("整个文档"),
                     detail=safe_tr("所选格式不能包含宏，保存后宏将被删除。"))]
    return []


def notify_only(losses: list[Loss]) -> list[Loss]:
    return [loss for loss in losses if loss.notify]


# ---------------------------------------------------------------- per editor
def _quire_content(doc: Any) -> dict[str, int]:
    """Counts of the document features plain formats cannot hold."""
    from atboffice.modules.writer.models.document import Paragraph, all_paragraphs

    counts = {"formatted": 0, "tables": 0, "objects": 0}
    for block in getattr(doc.main, "blocks", []):
        if not isinstance(block, Paragraph):
            counts["tables"] += 1
    for p in all_paragraphs(doc):
        for run in p.runs:
            if run.t == "text":
                r_pr = getattr(run, "r_pr", None)
                if r_pr is not None and (
                    r_pr.b or r_pr.i or r_pr.u not in ("none", None) or r_pr.strike
                    or (r_pr.color not in ("auto", None, "000000"))
                    or r_pr.highlight
                ):
                    counts["formatted"] += 1
            elif run.t not in ("tab", "br"):
                counts["objects"] += 1
    return counts


def quire_losses(doc: Any, target: Path) -> list[Loss]:
    """Only what this document actually has and the target format cannot keep."""
    ext = target.suffix.lower()
    out: list[Loss] = []
    if ext not in (".txt", ".md", ".markdown", ".html", ".htm"):
        return out
    content = _quire_content(doc)
    if ext == ".txt":
        if content["formatted"]:
            out.append(Loss(safe_tr("文字格式（加粗、倾斜、颜色等）"), safe_tr("正文"),
                            count=content["formatted"]))
        if content["tables"]:
            out.append(Loss(safe_tr("表格（仅保留文字）"), safe_tr("正文"),
                            count=content["tables"]))
        if content["objects"]:
            out.append(Loss(safe_tr("图片、图形和其他对象"), safe_tr("正文"),
                            count=content["objects"]))
    if ext in (".txt", ".md", ".markdown", ".html", ".htm"):
        if getattr(doc, "hf", None):
            out.append(Loss(safe_tr("页眉和页脚"), safe_tr("页眉/页脚"), count=len(doc.hf)))
        if getattr(doc, "comments", None):
            out.append(Loss(safe_tr("批注"), safe_tr("正文"), count=len(doc.comments)))
    return out


def ledger_losses(workbook: Any, active_sheet: Any, target: Path) -> list[Loss]:
    ext = target.suffix.lower()
    out: list[Loss] = []
    if ext in (".csv", ".tsv", ".txt"):
        sheets = list(getattr(workbook, "sheets", []) or [])
        if len(sheets) > 1:
            out.append(Loss(
                safe_tr("其他工作表"),
                safe_tr("仅保存“{0}”").format(getattr(active_sheet, "name", "")),
                count=len(sheets) - 1,
            ))
        formulas = sum(1 for c in active_sheet.cells.values() if getattr(c, "formula", None))
        if formulas:
            out.append(Loss(safe_tr("公式（保存为计算结果）"), active_sheet.name, count=formulas))
        styled = sum(
            1 for c in active_sheet.cells.values()
            if getattr(c, "bg_color", None) or getattr(c, "bold", False)
            or getattr(c, "border_top", None) is not None
        )
        if styled or active_sheet.merges:
            out.append(Loss(safe_tr("单元格格式与合并单元格"), active_sheet.name,
                            count=styled + len(active_sheet.merges)))
        drawings = len(getattr(active_sheet, "drawings", []) or [])
        if drawings:
            out.append(Loss(safe_tr("图表、图片和图形"), active_sheet.name, count=drawings))
    return out
