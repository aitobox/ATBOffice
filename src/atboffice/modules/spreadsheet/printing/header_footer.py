"""Excel header/footer codes: &L &C &R sections and &P &N &D &T &F &A fields."""

from __future__ import annotations

import datetime as _dt
import re

_FONT_CODE = re.compile(r'&"[^"]*"|&\d{1,3}|&[BIUSEXYKbiuseyxk](?:[0-9A-Fa-f]{6})?')


def split_sections(text: str) -> tuple[str, str, str]:
    """Split ``&L…&C…&R…`` into (left, center, right); text without a code is centred."""
    sections = {"L": "", "C": "", "R": ""}
    current = "C"
    i = 0
    buf = []
    while i < len(text):
        ch = text[i]
        if ch == "&" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "&":
                buf.append("&&")
                i += 2
                continue
            if nxt.upper() in ("L", "C", "R"):
                sections[current] += "".join(buf)
                buf = []
                current = nxt.upper()
                i += 2
                continue
        buf.append(ch)
        i += 1
    sections[current] += "".join(buf)
    return sections["L"], sections["C"], sections["R"]


def expand(
    section: str,
    page: int,
    pages: int,
    sheet_name: str = "",
    file_name: str = "",
    file_path: str = "",
    now: _dt.datetime | None = None,
) -> str:
    """Replace field codes and drop font/style codes (&"Arial,Bold", &12, &B …)."""
    now = now or _dt.datetime.now()
    out = _FONT_CODE.sub("", section)
    fields = {
        "&P": str(page),
        "&N": str(pages),
        "&D": now.strftime("%Y/%m/%d"),
        "&T": now.strftime("%H:%M"),
        "&F": file_name,
        "&A": sheet_name,
        "&Z": file_path,
    }
    result = []
    i = 0
    while i < len(out):
        two = out[i : i + 2]
        if two == "&&":
            result.append("&")
            i += 2
        elif two.upper() in fields:
            result.append(fields[two.upper()])
            i += 2
        else:
            result.append(out[i])
            i += 1
    return "".join(result)


def join_sections(left: str, center: str, right: str) -> str:
    parts = []
    if left:
        parts.append("&L" + left)
    if center:
        parts.append("&C" + center)
    if right:
        parts.append("&R" + right)
    return "".join(parts)
