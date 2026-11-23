"""Formatted (HTML) clipboard flavour for a Quire selection."""

from __future__ import annotations

import html
from typing import Any

from atboffice.modules.writer.models.document import ilen


def _run_style(r_pr: Any) -> str:
    parts = []
    font = getattr(r_pr, "font", None)
    if font:
        parts.append(f"font-family:'{html.escape(str(font), quote=True)}'")
    sz = getattr(r_pr, "sz", None)
    if sz:
        parts.append(f"font-size:{float(sz):g}pt")
    color = getattr(r_pr, "color", "auto")
    if color and color != "auto":
        parts.append(f"color:#{str(color).lstrip('#')}")
    hl = getattr(r_pr, "highlight", None)
    if hl and hl != "none":
        parts.append(f"background-color:{html.escape(str(hl))}")
    return ";".join(parts)


def _wrap(text: str, r_pr: Any) -> str:
    out = html.escape(text).replace("\t", "&emsp;").replace("\n", "<br/>")
    if getattr(r_pr, "b", False):
        out = f"<b>{out}</b>"
    if getattr(r_pr, "i", False):
        out = f"<i>{out}</i>"
    if getattr(r_pr, "u", "none") not in (None, "", "none"):
        out = f"<u>{out}</u>"
    if getattr(r_pr, "strike", False):
        out = f"<s>{out}</s>"
    vert = getattr(r_pr, "vert", "baseline")
    if vert == "superscript":
        out = f"<sup>{out}</sup>"
    elif vert == "subscript":
        out = f"<sub>{out}</sub>"
    style = _run_style(r_pr)
    return f'<span style="{style}">{out}</span>' if style else out


def paragraph_html(p: Any, start: int = 0, end: int | None = None) -> str:
    """HTML for characters [start, end) of paragraph ``p`` (offsets as in ``ptext``)."""
    pieces: list[str] = []
    pos = 0
    for it in p.runs:
        length = ilen(it)
        a, b = pos, pos + length
        pos = b
        lo = max(a, start)
        hi = b if end is None else min(b, end)
        if hi <= lo:
            continue
        r_pr = getattr(it, "r_pr", None)
        if it.t == "text":
            pieces.append(_wrap(it.text[lo - a : hi - a], r_pr))
        elif it.t == "tab":
            pieces.append("&emsp;")
        elif it.t == "br":
            pieces.append("<br/>")
    return "".join(pieces)


def selection_html(segments: list[tuple[Any, int, int | None]]) -> str:
    """``segments`` = [(paragraph, start, end)] in document order."""
    body = "".join(f"<p>{paragraph_html(p, a, b)}</p>" for p, a, b in segments)
    return f"<html><body><!--StartFragment-->{body}<!--EndFragment--></body></html>"
