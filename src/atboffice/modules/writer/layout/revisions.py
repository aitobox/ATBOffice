"""Track Changes display: inline markup for insertions, deletions and formatting changes.

The Reviewing toolbar's Display for Review mode is kept in ``doc.settings``:

* ``final_markup`` – insertions underlined, deletions struck through, both in the
  author's colour; formatting changes shown in the author's colour.
* ``final`` – the document as if every change were accepted (deletions hidden).
* ``original_markup`` – the original text with the changes marked: deletions shown
  plain, insertions struck through in the author's colour.
* ``original`` – as if every change were rejected (insertions hidden).

``showInsDel`` (Show > Insertions and Deletions) turns the inline markup off without
changing which text is visible.
"""

from __future__ import annotations

import dataclasses
import zlib
from typing import Any

# Word 2003 "By author" colours
AUTHOR_COLORS = ["C00000", "0000FF", "008000", "7030A0", "C55A11", "00B0F0", "FF00FF", "806000"]

HIDE = "hide"


def mode(doc: Any) -> str:
    settings = getattr(doc, "settings", None) or {}
    value = settings.get("revisionView", "final_markup")
    return value if value in ("final_markup", "final", "original_markup", "original") else \
        "final_markup"


def author_color(stamp: Any) -> str:
    author = str(getattr(stamp, "author", "") or "Author")
    return AUTHOR_COLORS[zlib.crc32(author.encode("utf-8")) % len(AUTHOR_COLORS)]


def apply(doc: Any, item: Any, r_pr: Any) -> Any:
    """Resolved run properties to draw ``item`` with, or ``HIDE`` when it is not shown."""
    src = getattr(item, "r_pr", None)
    ins = getattr(src, "ins", None) or getattr(r_pr, "ins", None)
    dele = getattr(src, "del_rev", None) or getattr(r_pr, "del_rev", None)
    chg = getattr(src, "chg", None) or getattr(r_pr, "chg", None)
    if not (ins or dele or chg):
        return r_pr
    view = mode(doc)
    if dele and view == "final":
        return HIDE
    if ins and view == "original":
        return HIDE
    settings = getattr(doc, "settings", None) or {}
    if not settings.get("showInsDel", True) or view in ("final", "original"):
        return r_pr
    if dele:
        if view == "original_markup":
            return r_pr  # the original text, unmarked
        return dataclasses.replace(r_pr, strike=True, color=author_color(dele))
    if ins:
        if view == "original_markup":
            return dataclasses.replace(r_pr, strike=True, color=author_color(ins))
        return dataclasses.replace(r_pr, u="single", color=author_color(ins))
    if chg and settings.get("showFormatting", True):
        return dataclasses.replace(r_pr, color=author_color(chg))
    return r_pr
