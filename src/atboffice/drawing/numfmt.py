"""Excel number and date format engine.

Converts values into formatted strings and rendering segments according to
ECMA-376 / Excel format codes, supporting accounting padding (`_x`), fill
characters (`*x`), locale currency tokens (`[$text-lcid]`), width-aware
`General` formatting, conditional sections, fractions, scientific notation,
and East-Asian weekday localization (`aaa`, `aaaa`).
"""

from __future__ import annotations

import datetime
import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Any, Final, Literal

# Excel color names mapping
COLOR_MAP: Final[dict[str, str]] = {
    "black": "#000000",
    "blue": "#0000FF",
    "cyan": "#00FFFF",
    "green": "#008000",
    "magenta": "#FF00FF",
    "red": "#FF0000",
    "white": "#FFFFFF",
    "yellow": "#FFFF00",
}

# 56-color legacy Excel palette for [ColorN]
COLOR_PALETTE_56: Final[tuple[str, ...]] = (
    "#000000", "#FFFFFF", "#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF",
    "#800000", "#008000", "#000080", "#808000", "#800080", "#008080", "#C0C0C0", "#808080",
    "#9999FF", "#993366", "#FFFFCC", "#CCFFFF", "#660066", "#FF8080", "#0066CC", "#CCCCFF",
    "#000080", "#FF00FF", "#FFFF00", "#00FFFF", "#800080", "#800000", "#008080", "#0000FF",
    "#00CCFF", "#CCFFFF", "#CCFFCC", "#FFFF99", "#99CCFF", "#FF99CC", "#CC99FF", "#FFCC99",
    "#3366FF", "#33CCCC", "#99CC00", "#FFCC00", "#FF9900", "#FF6600", "#666699", "#969696",
    "#003366", "#339966", "#003300", "#333300", "#993300", "#993366", "#333399", "#333333",
)

MONTHS_LONG: Final[tuple[str, ...]] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

# East Asian / European weekdays (index 0 = Sunday, 6 = Saturday)
ZH_WEEKDAYS_SHORT: Final[list[str]] = ["日", "一", "二", "三", "四", "五", "六"]
ZH_WEEKDAYS_LONG: Final[list[str]] = [
    "星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六",
]
EN_WEEKDAYS_SHORT: Final[list[str]] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
EN_WEEKDAYS_LONG: Final[list[str]] = [
    "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
]
JA_WEEKDAYS_SHORT: Final[list[str]] = ["日", "月", "火", "水", "木", "金", "土"]
JA_WEEKDAYS_LONG: Final[list[str]] = [f"{d}曜日" for d in JA_WEEKDAYS_SHORT]
KO_WEEKDAYS_SHORT: Final[list[str]] = ["일", "월", "화", "수", "목", "금", "토"]
KO_WEEKDAYS_LONG: Final[list[str]] = [f"{d}요일" for d in KO_WEEKDAYS_SHORT]
DE_WEEKDAYS_SHORT: Final[list[str]] = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"]
DE_WEEKDAYS_LONG: Final[list[str]] = [
    "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag",
]
FR_WEEKDAYS_SHORT: Final[list[str]] = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."]
FR_WEEKDAYS_LONG: Final[list[str]] = [
    "dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi",
]

WEEKDAYS_BY_LANG: Final[dict[int, tuple[list[str], list[str]]]] = {
    0x04: (ZH_WEEKDAYS_SHORT, ZH_WEEKDAYS_LONG),
    0x07: (DE_WEEKDAYS_SHORT, DE_WEEKDAYS_LONG),
    0x09: (EN_WEEKDAYS_SHORT, EN_WEEKDAYS_LONG),
    0x0C: (FR_WEEKDAYS_SHORT, FR_WEEKDAYS_LONG),
    0x11: (JA_WEEKDAYS_SHORT, JA_WEEKDAYS_LONG),
    0x12: (KO_WEEKDAYS_SHORT, KO_WEEKDAYS_LONG),
}
LANG_TAG_IDS: Final[dict[str, int]] = {
    "zh": 0x04, "de": 0x07, "en": 0x09, "fr": 0x0C, "ja": 0x11, "ko": 0x12,
}


@dataclass(frozen=True)
class DateParts:
    year: int
    month: int
    day: int
    weekday: int  # 0=Sunday, 6=Saturday
    hour: int = 0
    minute: int = 0
    second: int = 0
    sub: float = 0.0
    days: int = 0
    secs: float = 0.0


@dataclass(frozen=True)
class FormatSegment:
    """Single rendering segment produced by the number formatter."""

    kind: Literal["text", "pad", "fill"]
    value: str


@dataclass(frozen=True)
class FormattedResult:
    text: str
    color: str | None = None
    is_numeric: bool = False
    is_error: bool = False
    segments: tuple[FormatSegment, ...] = ()
    fill_pos: int | None = None
    has_fill: bool = False


def date_to_serial(y: int, m: int, d: int, date1904: bool = False) -> int:
    """Convert year, month, day to an Excel serial number."""
    if date1904:
        base = datetime.date(1904, 1, 1)
        target = datetime.date(y, m, d)
        return (target - base).days

    # Excel 1900 system with leap year quirk (serial 60 is 1900-02-29)
    if y == 1900 and m == 2 and d == 29:
        return 60

    target = datetime.date(y, m, d)
    base = datetime.date(1899, 12, 30)
    serial = (target - base).days
    if serial <= 60:
        serial -= 1
    return serial


def serial_to_parts(v: float, date1904: bool = False, sub_digits: int = 3) -> DateParts:
    """Convert an Excel serial number to date and time components."""
    days = int(math.floor(v))
    secs = (v - days) * 86400.0
    secs = round(secs, sub_digits)
    if secs >= 86400.0:
        secs -= 86400.0
        days += 1

    if date1904:
        base = datetime.date(1904, 1, 1)
        dt = base + datetime.timedelta(days=days)
        y, m, d = dt.year, dt.month, dt.day
        wd = (dt.weekday() + 1) % 7  # Python: 0=Mon, 6=Sun -> Excel: 0=Sun, 6=Sat
    elif days == 0:
        y, m, d, wd = 1900, 1, 0, 6
    elif days == 60:
        y, m, d, wd = 1900, 2, 29, 3  # Wednesday
    else:
        # Before 1900-03-01, day is offset
        base = datetime.date(1899, 12, 31 if days < 60 else 30)
        dt = base + datetime.timedelta(days=days)
        y, m, d = dt.year, dt.month, dt.day
        wd = (days % 7 + 6) % 7

    whole_secs = int(secs)
    h = whole_secs // 3600
    minute = (whole_secs % 3600) // 60
    s = whole_secs % 60
    sub = secs - whole_secs

    return DateParts(
        year=y,
        month=m,
        day=d,
        weekday=wd,
        hour=h,
        minute=minute,
        second=s,
        sub=sub,
        days=days,
        secs=secs,
    )


def _weekday_names(lcid: int | str, full: bool) -> list[str]:
    """Resolve localized weekday name table for `aaa`/`aaaa`."""
    lang_id: int | None = None
    if isinstance(lcid, int):
        lang_id = lcid & 0x3FF
    else:
        s = str(lcid or "").strip()
        if re.fullmatch(r"[0-9A-Fa-f]{1,8}", s):
            lang_id = int(s, 16) & 0x3FF
        elif s:
            prefix = s.split("-")[0].lower()
            lang_id = LANG_TAG_IDS.get(prefix)
    pair = WEEKDAYS_BY_LANG.get(lang_id if lang_id is not None else 0x09, WEEKDAYS_BY_LANG[0x09])
    return pair[1] if full else pair[0]


# ---------------------------------------------------------------------------
# Rounding & General Format (15 significant digits, 11-char Excel default)
# ---------------------------------------------------------------------------

_RE_STRIP_DEC: Final[re.Pattern[str]] = re.compile(r"(?:\.0*|(\.\d*[1-9])0+)$")
_RE_NORM_EXP: Final[re.Pattern[str]] = re.compile(r"(?:\.0*|(\.\d*[1-9])0+)E")
_RE_PAD_EXP: Final[re.Pattern[str]] = re.compile(r"E([+-])(\d)$")


def _round_decimal_fixed(x: float, dec: int) -> str:
    """Decimal string of |x| rounded half-away-from-zero to `dec` places (15 sig figs)."""
    ax = abs(x)
    if not math.isfinite(ax):
        return "NaN"
    if ax == 0.0:
        return f"0.{'0' * dec}" if dec > 0 else "0"
    d_val = Decimal(f"{ax:.15g}")
    if dec <= 0:
        q = Decimal("1")
    else:
        q = Decimal(1).scaleb(-dec)
    rounded = d_val.quantize(q, rounding=ROUND_HALF_UP)
    return f"{rounded:.{max(0, dec)}f}"


def _strip_dec(s: str) -> str:
    if "." not in s or "e" in s.lower():
        return s
    return _RE_STRIP_DEC.sub(lambda m: m.group(1) or "", s)


def _norm_exp(s: str) -> str:
    if "E" not in s:
        return s
    s = _RE_NORM_EXP.sub(lambda m: (m.group(1) or "") + "E", s)
    s = _RE_PAD_EXP.sub(r"E\g<1>0\2", s)
    return s


def _format_sci_for_width(d_val: Decimal, v_exp: int, width: int) -> str:
    """Format positive Decimal in scientific notation fitting within `width` chars."""
    exp_part = 5 if abs(v_exp) >= 100 else 4  # E+XX or E+XXX
    start_d = max(0, width - 2 - exp_part)
    best = ""
    for d in range(start_d, -1, -1):
        s = f"{d_val:.{d}E}"
        s = re.sub(
            r"E([+-])(\d+)$",
            lambda m: f"E{m.group(1)}{m.group(2).zfill(2)}",
            s,
        )
        s = _norm_exp(s)
        best = s
        if len(s) <= width or d == 0:
            break
    return best


def _format_general(num: float, max_chars: int = 11, fn_mode: bool = False) -> tuple[str, bool]:
    """Format a finite float using Excel's `General` rules up to `max_chars` characters.

    Returns (formatted_text, is_error).
    """
    if num == 0.0:
        return "0", False
    width = max(1, max_chars)
    neg = num < 0
    a = abs(num)
    d_val = Decimal(f"{a:.15g}")
    if d_val == 0:
        return "0", False
    v_exp = int(math.floor(d_val.log10()))
    min_plain_exp = -(width - 2) if fn_mode else -4

    out: str | None = None
    if v_exp + 1 <= width and v_exp >= min_plain_exp:
        int_len = v_exp + 1 if v_exp >= 0 else 1
        max_dec = max(0, width - int_len - 1)
        for dec in range(max_dec, -1, -1):
            s = _strip_dec(_round_decimal_fixed(a, min(dec, 30)))
            if len(s) <= width:
                if s == "0" or re.fullmatch(r"0\.?0*", s):
                    s_cand: str | None = None
                else:
                    s_cand = s
                out = s_cand
                break
        if out is not None and v_exp < 0:
            sig_dec = len(re.sub(r"^0\.0*", "", out))
            sci = _format_sci_for_width(d_val, v_exp, width)
            sig_sci = len(re.sub(r"E.*$", "", sci).replace(".", ""))
            if sig_dec < 1 or (fn_mode and sig_dec < sig_sci):
                out = None

    if out is None:
        out = _format_sci_for_width(d_val, v_exp, width)
        if len(out) > width:
            return "#" * width, True

    return ("-" + out if neg else out), False


# ---------------------------------------------------------------------------
# Section Splitting & Single-Pass Tokenization
# ---------------------------------------------------------------------------

_DATE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r"^(yyyy|yyy|yy|y|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|aaaa|aaa|hh|h|ss|s|e|bbbb|bb|b|gggg|ggg|gg|g)",
    re.IGNORECASE,
)
_AMPM_RE: Final[re.Pattern[str]] = re.compile(r"^(am/pm|a/p)", re.IGNORECASE)
_COLOR_N_RE: Final[re.Pattern[str]] = re.compile(r"^color\s*(\d+)$")
_COND_RE: Final[re.Pattern[str]] = re.compile(r"^(<=|>=|<>|<|>|=)\s*(-?[\d.]+(?:e[+-]?\d+)?)$")
_ELAPSED_RE: Final[re.Pattern[str]] = re.compile(r"^(h+|m+|s+)$")
_DBNUM_RE: Final[re.Pattern[str]] = re.compile(r"^(?:dbnum\d|natnum\d)$")


@dataclass
class _Tok:
    t: str  # lit, pad, fill, gen, dt, el, ampm, sub, d, ., ,, %, /, @, exp, skip
    s: str = ""
    ch: str = ""
    u: str = ""
    length: int = 0
    sign: str = ""
    upper: bool = True
    is_min: bool = False
    bare: bool = False


@dataclass
class _Section:
    toks: list[_Tok]
    src: str
    kind: str  # date, general, num, text, lit
    color: str | None = None
    cond: tuple[str, float] | None = None
    lcid: str = ""
    elapsed: bool = False
    fill: bool = False
    pct: int = 0
    scale: int = 0
    group: bool = False
    int_end: int = 0
    dec_at: int = -1
    exp_at: int = -1
    int_d: int = 0
    dec_d: int = 0
    exp_d: int = 0
    frac: bool = False
    frac_int: bool = False
    frac_int_toks: list[_Tok] | None = None
    frac_num: list[_Tok] | None = None
    frac_mid: list[_Tok] | None = None
    frac_den: list[_Tok] | None = None
    fixed_den: int | None = None
    frac_pre: list[_Tok] | None = None
    frac_tail: list[_Tok] | None = None


def _split_sections(code: str) -> list[str]:
    """Split an Excel format code into sections at `;` outside quotes, brackets, and escapes."""
    sections: list[str] = []
    cur: list[str] = []
    in_quotes = False
    in_brackets = False
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if in_quotes:
            cur.append(ch)
            if ch == '"':
                in_quotes = False
            i += 1
            continue
        if ch in ("\\", "_", "*"):
            cur.append(ch)
            if i + 1 < n:
                cur.append(code[i + 1])
            i += 2
            continue
        if ch == '"':
            in_quotes = True
            cur.append(ch)
            i += 1
            continue
        if ch == "[":
            in_brackets = True
            cur.append(ch)
            i += 1
            continue
        if ch == "]":
            in_brackets = False
            cur.append(ch)
            i += 1
            continue
        if ch == ";" and not in_brackets:
            sections.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    sections.append("".join(cur))
    return sections


def _push_lit(toks: list[_Tok], s: str) -> None:
    if not s:
        return
    if toks and toks[-1].t == "lit" and not toks[-1].bare:
        toks[-1].s += s
    else:
        toks.append(_Tok(t="lit", s=s))


def _tokenize_section(sec: str) -> _Section:
    """Tokenize one format section in a single pass."""
    toks: list[_Tok] = []
    color: str | None = None
    cond: tuple[str, float] | None = None
    lcid = ""
    elapsed = False
    has_date = False
    has_text = False
    has_general = False
    has_num = False
    has_fill = False

    i = 0
    n = len(sec)
    while i < n:
        ch = sec[i]
        rest = sec[i:]
        if ch == '"':
            j = sec.find('"', i + 1)
            lit_s = sec[i + 1 :] if j < 0 else sec[i + 1 : j]
            _push_lit(toks, lit_s)
            i = n if j < 0 else j + 1
            continue
        if ch == "\\":
            _push_lit(toks, sec[i + 1] if i + 1 < n else "")
            i += 2
            continue
        if ch == "_":
            pad_ch = sec[i + 1] if i + 1 < n else " "
            toks.append(_Tok(t="pad", ch=pad_ch))
            i += 2
            continue
        if ch == "*":
            fill_ch = sec[i + 1] if i + 1 < n else " "
            toks.append(_Tok(t="fill", ch=fill_ch))
            has_fill = True
            i += 2
            continue
        if ch == "[":
            j = sec.find("]", i)
            body = sec[i + 1 :] if j < 0 else sec[i + 1 : j]
            i = n if j < 0 else j + 1
            lb = body.strip().lower()
            if lb in COLOR_MAP:
                color = COLOR_MAP[lb]
                continue
            m_col = _COLOR_N_RE.match(lb)
            if m_col:
                idx = (int(m_col.group(1)) - 1) % len(COLOR_PALETTE_56)
                color = COLOR_PALETTE_56[idx]
                continue
            m_cond = _COND_RE.match(lb)
            if m_cond:
                cond = (m_cond.group(1), float(m_cond.group(2)))
                continue
            if _ELAPSED_RE.match(lb):
                toks.append(_Tok(t="el", u=lb[0], length=len(lb)))
                elapsed = True
                has_date = True
                continue
            if body.startswith("$"):
                dash = body.find("-", 1)
                sym = body[1:] if dash < 0 else body[1:dash]
                lcid_part = "" if dash < 0 else body[dash + 1 :]
                lcid = lcid_part.upper()
                if sym:
                    _push_lit(toks, sym)
                continue
            if _DBNUM_RE.match(lb):
                continue
            continue  # unknown bracket token: ignore
        if rest[:7].lower() == "general":
            toks.append(_Tok(t="gen"))
            has_general = True
            i += 7
            continue
        m_ampm = _AMPM_RE.match(rest)
        if m_ampm:
            toks.append(_Tok(t="ampm", s=m_ampm.group(1)))
            has_date = True
            i += len(m_ampm.group(1))
            continue
        m_dt = _DATE_TOKEN_RE.match(rest)
        if m_dt:
            dt_str = m_dt.group(1)
            low_ch = ch.lower()
            if low_ch == "e":
                if i + 1 < n and sec[i + 1] in ("+", "-"):
                    toks.append(_Tok(t="exp", sign=sec[i + 1], upper=(ch == "E")))
                    has_num = True
                    i += 2
                    continue
                toks.append(_Tok(t="dt", s="yyyy"))
                has_date = True
                i += 1
                continue
            if low_ch == "b":
                toks.append(_Tok(t="dt", s="bbbb" if len(dt_str) > 2 else "bb"))
                has_date = True
                i += len(dt_str)
                continue
            if low_ch == "g":
                has_date = True
                i += len(dt_str)
                continue
            toks.append(_Tok(t="dt", s=dt_str.lower()))
            has_date = True
            i += len(dt_str)
            continue
        if ch in ("0", "#", "?"):
            toks.append(_Tok(t="d", ch=ch))
            has_num = True
            i += 1
            continue
        if ch == ".":
            if has_date:
                m_sub = re.match(r"^\.(0+)", rest)
                if m_sub:
                    toks.append(_Tok(t="sub", length=len(m_sub.group(1))))
                    i += len(m_sub.group(0))
                    continue
            toks.append(_Tok(t="."))
            i += 1
            continue
        if ch == ",":
            toks.append(_Tok(t=","))
            i += 1
            continue
        if ch == "%":
            toks.append(_Tok(t="%"))
            has_num = True
            i += 1
            continue
        if ch == "/":
            toks.append(_Tok(t="/"))
            i += 1
            continue
        if ch == "@":
            toks.append(_Tok(t="@"))
            has_text = True
            i += 1
            continue
        _push_lit(toks, ch)
        i += 1

    if has_date and not has_num:
        kind = "date"
    elif has_general:
        kind = "general"
    elif has_num:
        kind = "num"
    elif has_text:
        kind = "text"
    elif has_date:
        kind = "date"
    else:
        kind = "lit"

    parsed = _Section(
        toks=toks,
        src=sec,
        kind=kind,
        color=color,
        cond=cond,
        lcid=lcid,
        elapsed=elapsed,
        fill=has_fill,
    )

    if parsed.kind == "date" and parsed.lcid in ("F800", "F400"):
        sys_fmt = "dddd, mmmm d, yyyy" if parsed.lcid == "F800" else "h:mm:ss AM/PM"
        parsed.toks = _tokenize_section(sys_fmt).toks

    if parsed.kind == "date":
        _mark_minutes(parsed.toks)
    elif parsed.kind == "num":
        _analyse_number(parsed)

    return parsed


def _mark_minutes(toks: list[_Tok]) -> None:
    """Disambiguate `m`/`mm` as minutes when adjacent to hour or second tokens."""
    dts = [t for t in toks if t.t in ("dt", "el", "ampm")]
    for k, t in enumerate(dts):
        if t.t != "dt" or t.s not in ("m", "mm"):
            continue
        prev = dts[k - 1] if k > 0 else None
        nxt = dts[k + 1] if k + 1 < len(dts) else None
        prev_hs = prev is not None and (
            (prev.t == "dt" and prev.s[0] in ("h", "s"))
            or (prev.t == "el" and prev.u in ("h", "s"))
        )
        next_s = nxt is not None and (
            (nxt.t == "dt" and nxt.s[0] == "s")
            or (nxt.t == "el" and nxt.u == "s")
        )
        if prev_hs or next_s:
            t.is_min = True

    el_units = {t.u for t in toks if t.t == "el"}
    if el_units:
        for idx, t in enumerate(toks):
            if t.t != "dt":
                continue
            u = "h" if t.s[0] == "h" else "s" if t.s[0] == "s" else ("m" if t.is_min else None)
            if u and u in el_units:
                toks[idx] = _Tok(t="el", u=u, length=len(t.s))


def _analyse_number(sec: _Section) -> None:
    """Extract scaling, grouping, integer/decimal/exponent/fraction structure."""
    toks = sec.toks
    sec.pct = sum(1 for t in toks if t.t == "%")
    ei = next((i for i, t in enumerate(toks) if t.t == "exp"), -1)
    si = next((i for i, t in enumerate(toks) if t.t == "/"), -1)

    has_frac_num = si >= 0 and any(t.t == "d" for t in toks[:si])
    has_frac_den = si >= 0 and any(
        t.t == "d" or (t.t == "lit" and bool(re.fullmatch(r"\d+", t.s.strip())))
        for t in toks[si:]
    )
    sec.frac = has_frac_num and has_frac_den
    if sec.frac:
        before = toks[:si]
        after = list(toks[si + 1 :])
        k = len(before) - 1
        while k >= 0 and before[k].t != "d":
            k -= 1
        num_end = k
        while k >= 0 and before[k].t in ("d", ","):
            k -= 1
        num_start = k + 1
        sec.frac_num = [t for t in before[num_start : num_end + 1] if t.t == "d"]
        sec.frac_int = any(t.t == "d" for t in before[:num_start])
        sec.frac_int_toks = before[:num_start]
        sec.frac_mid = before[num_end + 1 :]

        fixed_den: int | None = None
        den_toks: list[_Tok] = []
        j = 0
        while j < len(after):
            t = after[j]
            if t.t == "d":
                den_toks.append(t)
            elif t.t == "lit" and re.match(r"^\d+", t.s) and not den_toks:
                m = re.match(r"^(\d+)(.*)$", t.s)
                assert m is not None
                fixed_den = int(m.group(1))
                if m.group(2):
                    after.insert(j + 1, _Tok(t="lit", s=m.group(2)))
                j += 1
                break
            elif den_toks:
                break
            elif t.t in ("lit", "pad"):
                j += 1
                continue
            else:
                break
            j += 1
        sec.frac_den = den_toks
        sec.fixed_den = fixed_den if fixed_den and fixed_den > 0 else None
        if sec.fixed_den:
            sec.frac_tail = after[j:]
            sec.frac_pre = after[: max(0, j - 1)]
        elif den_toks:
            last_den_idx = len(after) - 1 - after[::-1].index(den_toks[-1])
            first_den_idx = after.index(den_toks[0])
            sec.frac_tail = after[last_den_idx + 1 :]
            sec.frac_pre = after[:first_den_idx]
        else:
            sec.frac_tail = []
            sec.frac_pre = []
        return

    end = ei if ei >= 0 else len(toks)
    di = next((i for i, t in enumerate(toks[:end]) if t.t == "."), -1)
    int_end = di if di >= 0 else end

    first_d = -1
    last_d = -1
    for i in range(int_end):
        if toks[i].t == "d":
            if first_d < 0:
                first_d = i
            last_d = i

    group = False
    scale = 0
    for i in range(int_end):
        if toks[i].t != ",":
            continue
        if first_d < i < last_d:
            group = True
        elif i > last_d >= 0:
            if all(toks[k].t == "," for k in range(last_d + 1, i)):
                scale += 1
            else:
                toks[i] = _Tok(t="lit", s=",", bare=True)
        else:
            toks[i] = _Tok(t="lit", s=",", bare=True)

    if di >= 0:
        for i in range(di + 1, end):
            if toks[i].t == ",":
                if all(toks[k].t != "d" for k in range(i + 1, end)):
                    scale += 1
                    toks[i] = _Tok(t="skip")
                else:
                    toks[i] = _Tok(t="lit", s=",", bare=True)

    if ei >= 0:
        for i in range(len(toks)):
            if toks[i].bare or (i > ei and toks[i].t == ","):
                toks[i] = _Tok(t="skip")

    sec.group = group
    sec.scale = scale
    sec.int_end = int_end
    sec.dec_at = di
    sec.exp_at = ei
    sec.int_d = sum(1 for t in toks[:int_end] if t.t == "d")
    sec.dec_d = sum(1 for t in toks[di + 1 : end] if t.t == "d") if di >= 0 else 0
    if ei >= 0:
        sec.exp_d = sum(1 for t in toks[ei + 1 :] if t.t == "d")


@lru_cache(maxsize=2048)
def _parse_format(code: str) -> tuple[_Section, ...]:
    raw_secs = _split_sections(code)
    return tuple(_tokenize_section(s) for s in raw_secs)


def _is_date_format(code: str) -> bool:
    """Check if format code is a date or time format."""
    if not code or code.lower() == "general":
        return False
    secs = _parse_format(code)
    return bool(secs and secs[0].kind == "date")


# ---------------------------------------------------------------------------
# Section Selection
# ---------------------------------------------------------------------------

def _cond_ok(cond: tuple[str, float], v: float) -> bool:
    op, target = cond
    if op == "<":
        return v < target
    if op == ">":
        return v > target
    if op == "=":
        return v == target
    if op == "<=":
        return v <= target
    if op == ">=":
        return v >= target
    if op == "<>":
        return v != target
    return False


def _pick_numeric_section(
    secs: tuple[_Section, ...] | list[_Section], v: float
) -> tuple[_Section | None, bool]:
    """Select the section for a numeric value; returns (section, use_abs)."""
    has_cond = any(s.cond is not None for s in secs)
    if has_cond:
        c0 = secs[0].cond if secs else None
        c1 = secs[1].cond if len(secs) > 1 else None
        if c0 is not None and _cond_ok(c0, v):
            return secs[0], False
        if len(secs) > 1 and c1 is not None and _cond_ok(c1, v):
            return secs[1], (v < 0 and c1[0].startswith("<") and c1[1] <= 0)
        if len(secs) > 1 and c1 is None and c0 is None:
            return secs[1], v < 0
        if c0 is not None and c1 is None and len(secs) > 1 and secs[1].kind != "text":
            if len(secs) >= 3 and v < 0 and secs[2].kind != "text":
                return secs[1], True
            return secs[1], False
        if len(secs) > 2 and secs[2].kind != "text":
            return secs[2], False
        if c0 is not None and (len(secs) <= 1 or secs[1].kind == "text"):
            return _tokenize_section("General"), False
        return None, False

    non_text = [
        s
        for idx, s in enumerate(secs)
        if not (s.kind == "text" and len(secs) > 1 and idx == 3)
    ]
    if len(non_text) == 1 or len(secs) == 1:
        return secs[0], False
    if v > 0 or (v == 0 and len(secs) < 3):
        return secs[0], False
    if v < 0:
        if len(secs) > 1 and secs[1].kind != "text":
            return secs[1], True
        return secs[0], False
    if len(secs) > 2 and secs[2].kind != "text":
        return secs[2], False
    return secs[0], False


# ---------------------------------------------------------------------------
# Segment Assembly & Rendering
# ---------------------------------------------------------------------------

def _append_text_seg(segs: list[FormatSegment], s: str) -> None:
    if not s:
        return
    if segs and segs[-1].kind == "text":
        segs[-1] = FormatSegment("text", segs[-1].value + s)
    else:
        segs.append(FormatSegment("text", s))


def _emit_non_digit_tok(segs: list[FormatSegment], t: _Tok) -> None:
    if t.t == "lit":
        _append_text_seg(segs, t.s)
    elif t.t == "pad":
        segs.append(FormatSegment("pad", t.ch))
    elif t.t == "fill":
        segs.append(FormatSegment("fill", t.ch))
    elif t.t in ("%", ".", "/", ","):
        _append_text_seg(segs, t.t)


def _finalize_segments(
    segs: list[FormatSegment],
    color: str | None = None,
    is_numeric: bool = False,
    is_error: bool = False,
) -> FormattedResult:
    parts: list[str] = []
    fill_pos: int | None = None
    has_fill = False
    pos = 0
    for seg in segs:
        if seg.kind == "text":
            parts.append(seg.value)
            pos += len(seg.value)
        elif seg.kind == "pad":
            parts.append(" ")
            pos += 1
        elif seg.kind == "fill":
            if fill_pos is None:
                fill_pos = pos
            has_fill = True
    return FormattedResult(
        text="".join(parts),
        color=color,
        is_numeric=is_numeric,
        is_error=is_error,
        segments=tuple(segs),
        fill_pos=fill_pos,
        has_fill=has_fill,
    )


def _approx_fraction(x: float, max_den: int) -> tuple[int, int]:
    """Best rational approximation with denominator <= max_den (continued fractions)."""
    a = math.floor(x)
    h1, h0, k1, k0 = 1, 0, 0, 1
    b = x
    hb, kb = a, 1
    for _ in range(64):
        a = math.floor(b)
        h2 = a * h1 + h0
        k2 = a * k1 + k0
        if k2 > max_den:
            t = (max_den - k0) // k1 if k1 else 0
            hs = t * h1 + h0
            ks = t * k1 + k0
            if ks > 0 and abs(x - hs / ks) < abs(x - hb / kb):
                hb, kb = hs, ks
            break
        h0, h1, k0, k1 = h1, h2, k1, k2
        hb, kb = h2, k2
        f = b - a
        if f < 1e-12:
            break
        b = 1.0 / f
    return hb, kb


def _format_fraction_section(sec: _Section, x: float, neg: bool) -> list[FormatSegment]:
    segs: list[FormatSegment] = []
    frac_den = sec.frac_den or []
    frac_num = sec.frac_num or []
    frac_mid = sec.frac_mid or []
    frac_pre = sec.frac_pre or []
    frac_tail = sec.frac_tail or []
    frac_int_toks = sec.frac_int_toks or []

    d_digits = len(frac_den)
    ip = 0
    if sec.frac_int:
        ip = math.floor(x)
        x -= ip
    if sec.fixed_den:
        den = sec.fixed_den
        num = round(x * den)
    else:
        max_den = (10 ** max(1, d_digits)) - 1
        num, den = _approx_fraction(x, max_den)
    if sec.frac_int and num == den and den > 0:
        ip += 1
        num = 0
    if neg and (ip or num):
        _append_text_seg(segs, "-")

    def pad_to(s: str, toks: list[_Tok], left: bool = False) -> str:
        n = len(toks)
        if len(s) >= n:
            return s
        extra = n - len(s)
        pad_chars: list[str] = []
        for k in range(extra):
            tok = toks[len(s) + k] if left else toks[k]
            pad_chars.append("0" if tok.ch == "0" else (" " if tok.ch == "?" else ""))
        pad_str = "".join(pad_chars)
        return s + pad_str if left else pad_str + s

    if sec.frac_int:
        ph = [t for t in frac_int_toks if t.t == "d"]
        is_str = str(ip) if ip else ""
        if not is_str and any(t.ch == "0" for t in ph):
            is_str = "0"
        if not ip and not num and not is_str:
            is_str = "0"
        placed = False
        for t in frac_int_toks:
            if t.t == "d":
                if not placed:
                    _append_text_seg(segs, pad_to(is_str, ph))
                    placed = True
            elif t.t == "lit" and not ip and num and not t.s.strip() and not is_str:
                _append_text_seg(segs, t.s)
            else:
                _emit_non_digit_tok(segs, t)
    else:
        for t in frac_int_toks:
            if t.t != "d":
                _emit_non_digit_tok(segs, t)

    if num == 0 and sec.frac_int:
        den_len = len(str(sec.fixed_den)) if sec.fixed_den else d_digits
        blank = " " * (len(frac_num) + 1 + den_len)
        for t in frac_mid:
            _emit_non_digit_tok(segs, t)
        _append_text_seg(segs, blank)
        for t in frac_tail:
            _emit_non_digit_tok(segs, t)
        return segs

    _append_text_seg(segs, pad_to(str(num), frac_num))
    for t in frac_mid:
        _emit_non_digit_tok(segs, t)
    _append_text_seg(segs, "/")
    for t in frac_pre:
        _emit_non_digit_tok(segs, t)
    _append_text_seg(segs, str(den) if sec.fixed_den else pad_to(str(den), frac_den, left=True))
    for t in frac_tail:
        _emit_non_digit_tok(segs, t)
    return segs


def _format_number_section(sec: _Section, v: float, use_abs: bool) -> list[FormatSegment]:
    neg = v < 0 and not use_abs
    x = abs(v)
    if sec.pct and sec.exp_at < 0:
        x *= 100.0 ** sec.pct
    if sec.scale and sec.exp_at < 0:
        x /= 1000.0 ** sec.scale
    if sec.frac:
        return _format_fraction_section(sec, x, neg)

    segs: list[FormatSegment] = []
    toks = sec.toks
    exp_val = 0
    if sec.exp_at >= 0:
        ip = max(1, sec.int_d)
        e = 0 if x == 0.0 else math.floor(math.log10(x))
        if sec.int_d > 1:
            e = math.floor(e / ip) * ip
        elif sec.int_d == 0:
            e = e + 1
        m = 0.0 if x == 0.0 else x / (10.0**e)
        f = _round_decimal_fixed(m, sec.dec_d)
        int_digits = len(f.split(".")[0].lstrip("0"))
        limit = 0 if sec.int_d == 0 else (1 if sec.int_d == 1 else ip)
        if x != 0.0 and int_digits > max(1, limit):
            e += ip if sec.int_d > 1 else 1
            m = x / (10.0**e)
            f = _round_decimal_fixed(m, sec.dec_d)
        parts = f.split(".")
        int_str = parts[0]
        dec_str = parts[1] if len(parts) > 1 else ""
        exp_val = e
    else:
        f = _round_decimal_fixed(x, sec.dec_d)
        parts = f.split(".")
        int_str = parts[0]
        dec_str = parts[1] if len(parts) > 1 else ""

    if sec.exp_at >= 0 and x == 0.0:
        int_str = "0" * max(1, sec.int_d)
    elif int_str == "0":
        int_str = ""

    if neg:
        _append_text_seg(segs, "-")

    int_toks = toks[: sec.int_end]
    n_int_d = sec.int_d
    digits = int_str
    placeholders = [t for t in int_toks if t.t == "d"]
    di = len(digits) - len(placeholders)
    pi = 0

    def group_digits(s: str, start_pos: int) -> str:
        if not sec.group:
            return s
        res: list[str] = []
        for k, ch in enumerate(s):
            pos_from_right = len(digits) - (start_pos + k) - 1
            res.append(ch)
            if pos_from_right > 0 and pos_from_right % 3 == 0:
                res.append(",")
        return "".join(res)

    emitted = False
    for t in int_toks:
        if t.t == "d":
            s = ""
            if pi == 0 and di > 0:
                s = group_digits(digits[:di], 0)
            idx = di + pi
            if 0 <= idx < len(digits):
                s += digits[idx]
                emitted = True
            elif t.ch == "0":
                s += "0"
                emitted = True
            elif t.ch == "?":
                s += " "
                pos_from_right = n_int_d - pi - 1
                if sec.group and pos_from_right > 0 and pos_from_right % 3 == 0 and idx < 0:
                    s += " "
            if sec.group and 0 <= idx < len(digits):
                pos_from_right = len(digits) - idx - 1
                if pos_from_right > 0 and pos_from_right % 3 == 0:
                    s += ","
            elif sec.group and t.ch == "0" and emitted and idx < 0:
                pos_from_right = n_int_d - pi - 1
                if 0 < pos_from_right < n_int_d and pos_from_right % 3 == 0:
                    s += ","
            _append_text_seg(segs, s)
            pi += 1
        elif t.t == ",":
            continue
        else:
            _emit_non_digit_tok(segs, t)

    if sec.dec_at >= 0:
        end = sec.exp_at if sec.exp_at >= 0 else len(toks)
        dec_toks = toks[sec.dec_at + 1 : end]
        ph = [t for t in dec_toks if t.t == "d"]
        last_sig = len(dec_str) - 1
        while (
            last_sig >= 0
            and dec_str[last_sig] == "0"
            and last_sig < len(ph)
            and ph[last_sig].ch != "0"
        ):
            last_sig -= 1
        _append_text_seg(segs, ".")
        q = 0
        for t in dec_toks:
            if t.t == "d":
                if q <= last_sig and q < len(dec_str):
                    _append_text_seg(segs, dec_str[q])
                elif t.ch == "?":
                    _append_text_seg(segs, " ")
                q += 1
            else:
                _emit_non_digit_tok(segs, t)

    if sec.exp_at >= 0:
        exp_tok = toks[sec.exp_at]
        e_toks = toks[sec.exp_at + 1 :]
        ph = [t for t in e_toks if t.t == "d"]
        _append_text_seg(segs, "E" if exp_tok.upper else "e")
        sign = "-" if exp_val < 0 else ("+" if exp_tok.sign == "+" else "")
        es = str(abs(exp_val))
        if len(es) < len(ph):
            pad = "".join(
                "0" if ph[k].ch == "0" else (" " if ph[k].ch == "?" else "")
                for k in range(len(ph) - len(es))
            )
            es = pad + es
        first = True
        if not ph:
            _append_text_seg(segs, sign)
        for tk in e_toks:
            if tk.t == "d":
                if first:
                    _append_text_seg(segs, sign + es)
                    first = False
            else:
                _emit_non_digit_tok(segs, tk)

    return segs


def _format_date_section(
    sec: _Section,
    v: float,
    lcid: int | str,
    date1904: bool,
) -> list[FormatSegment] | None:
    if v < 0 and sec.elapsed and v > -2958466:
        pos_segs = _format_date_section(sec, -v, lcid, date1904)
        if pos_segs is not None:
            return [FormatSegment("text", "-"), *pos_segs]
        return None
    if v < 0 or v >= 2958466:
        return None

    sub_tok = next((t for t in sec.toks if t.t == "sub"), None)
    sub_digits = sub_tok.length if sub_tok is not None else 0
    p = serial_to_parts(v, date1904=date1904, sub_digits=sub_digits)
    has_ampm = any(t.t == "ampm" for t in sec.toks)
    eff_lcid: int | str = sec.lcid if sec.lcid else lcid
    segs: list[FormatSegment] = []

    for t in sec.toks:
        if t.t == "dt":
            s = t.s
            if t.is_min:
                _append_text_seg(segs, f"{p.minute:02d}" if s == "mm" else str(p.minute))
            elif s in ("yy", "y"):
                _append_text_seg(segs, f"{p.year % 100:02d}")
            elif s in ("yyy", "yyyy"):
                _append_text_seg(segs, f"{p.year:04d}")
            elif s == "bb":
                _append_text_seg(segs, f"{(p.year + 543) % 100:02d}")
            elif s == "bbbb":
                _append_text_seg(segs, str(p.year + 543))
            elif s == "m":
                _append_text_seg(segs, str(p.month))
            elif s == "mm":
                _append_text_seg(segs, f"{p.month:02d}")
            elif s == "mmm":
                _append_text_seg(segs, MONTHS_LONG[p.month - 1][:3])
            elif s == "mmmm":
                _append_text_seg(segs, MONTHS_LONG[p.month - 1])
            elif s == "mmmmm":
                _append_text_seg(segs, MONTHS_LONG[p.month - 1][0])
            elif s == "d":
                _append_text_seg(segs, str(p.day))
            elif s == "dd":
                _append_text_seg(segs, f"{p.day:02d}")
            elif s == "ddd":
                _append_text_seg(segs, EN_WEEKDAYS_SHORT[p.weekday])
            elif s == "dddd":
                _append_text_seg(segs, EN_WEEKDAYS_LONG[p.weekday])
            elif s in ("aaa", "aaaa"):
                _append_text_seg(segs, _weekday_names(eff_lcid, s == "aaaa")[p.weekday])
            elif s == "h":
                hr = ((p.hour + 11) % 12) + 1 if has_ampm else p.hour
                _append_text_seg(segs, str(hr))
            elif s == "hh":
                hr = ((p.hour + 11) % 12) + 1 if has_ampm else p.hour
                _append_text_seg(segs, f"{hr:02d}")
            elif s == "s":
                _append_text_seg(segs, str(p.second))
            elif s == "ss":
                _append_text_seg(segs, f"{p.second:02d}")
            else:
                _append_text_seg(segs, s)
        elif t.t == "el":
            total = p.days * 86400 + p.secs
            if t.u == "h":
                val = int(total // 3600)
            elif t.u == "m":
                val = int(total // 60)
            else:
                val = int(total)
            _append_text_seg(segs, str(val).zfill(t.length))
        elif t.t == "sub":
            sub_str = _round_decimal_fixed(p.sub, t.length)
            _append_text_seg(segs, "." + sub_str.split(".")[1])
        elif t.t == "ampm":
            pm = p.hour >= 12
            if t.s.lower() == "a/p":
                _append_text_seg(segs, t.s[2] if pm else t.s[0])
            else:
                _append_text_seg(segs, "PM" if pm else "AM")
        elif t.t == "d":
            if t.ch == "0":
                _append_text_seg(segs, "0")
        else:
            _emit_non_digit_tok(segs, t)

    return segs


def _format_text_section(sec: _Section, text: str) -> list[FormatSegment]:
    segs: list[FormatSegment] = []
    for t in sec.toks:
        if t.t in ("@", "gen"):
            _append_text_seg(segs, text)
        elif t.t in ("d", "dt", "el", "ampm", "sub", "exp"):
            continue
        else:
            _emit_non_digit_tok(segs, t)
    return segs


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def format_value(
    value: Any,
    format_str: str = "General",
    lcid: int | str = 0x04,
    date1904: bool = False,
    max_chars: int | None = None,
) -> FormattedResult:
    """Format any scalar value according to Excel format specifications."""
    if value is None or value == "":
        return FormattedResult(text="", is_numeric=False)

    if isinstance(value, bool):
        text = "TRUE" if value else "FALSE"
        return FormattedResult(
            text=text,
            is_numeric=False,
            segments=(FormatSegment("text", text),),
        )

    # Error string (e.g. #DIV/0!, #NAME?)
    if isinstance(value, str) and value.startswith("#") and (
        value.endswith("!") or value.endswith("?") or value == "#N/A"
    ):
        return FormattedResult(
            text=value,
            is_error=True,
            segments=(FormatSegment("text", value),),
        )

    width = max_chars if max_chars is not None else 11

    # Text string
    if isinstance(value, str):
        if not format_str or format_str.lower() == "general":
            return FormattedResult(
                text=value,
                is_numeric=False,
                segments=(FormatSegment("text", value),),
            )
        secs = _parse_format(format_str)
        sec_text = (
            secs[3]
            if len(secs) >= 4
            else next((s for s in secs if s.kind == "text"), None)
        )
        if sec_text is not None:
            segs = _format_text_section(sec_text, value)
            return _finalize_segments(segs, color=sec_text.color, is_numeric=False)
        return FormattedResult(
            text=value,
            is_numeric=False,
            segments=(FormatSegment("text", value),),
        )

    # Numeric value
    if isinstance(value, (int, float)):
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return FormattedResult(
                text="#NUM!",
                is_error=True,
                segments=(FormatSegment("text", "#NUM!"),),
            )

        if not format_str or format_str.lower() == "general":
            gen_text, is_err = _format_general(num, max_chars=width)
            return FormattedResult(
                text=gen_text,
                is_numeric=True,
                is_error=is_err,
                segments=(FormatSegment("text", gen_text),),
            )

        secs = _parse_format(format_str)
        chosen, use_abs = _pick_numeric_section(secs, num)
        if chosen is None:
            hashes = "#" * min(10, width)
            return FormattedResult(
                text=hashes,
                is_numeric=True,
                is_error=True,
                segments=(FormatSegment("text", hashes),),
            )

        if (
            chosen.kind == "general"
            or (chosen.kind == "text" and len(secs) == 1)
            or (chosen.kind == "lit" and not chosen.toks)
        ):
            gen_val = abs(num) if use_abs else num
            gen_text, is_err = _format_general(gen_val, max_chars=width)
            if chosen.kind == "general":
                segs: list[FormatSegment] = []
                for t in chosen.toks:
                    if t.t == "gen":
                        _append_text_seg(segs, gen_text)
                    else:
                        _emit_non_digit_tok(segs, t)
                return _finalize_segments(
                    segs, color=chosen.color, is_numeric=True, is_error=is_err
                )
            return FormattedResult(
                text=gen_text,
                color=chosen.color,
                is_numeric=True,
                is_error=is_err,
                segments=(FormatSegment("text", gen_text),),
            )

        if chosen.kind == "date":
            date_segs = _format_date_section(chosen, num, lcid=lcid, date1904=date1904)
            if date_segs is None:
                return FormattedResult(
                    text="##########",
                    color=chosen.color,
                    is_numeric=False,
                    is_error=True,
                    segments=(FormatSegment("text", "##########"),),
                )
            return _finalize_segments(date_segs, color=chosen.color, is_numeric=False)

        if chosen.kind == "num":
            num_segs = _format_number_section(chosen, num, use_abs)
            return _finalize_segments(num_segs, color=chosen.color, is_numeric=True)

        if chosen.kind == "text":
            gen_text, is_err = _format_general(num, max_chars=width)
            segs = []
            for t in chosen.toks:
                if t.t == "@":
                    _append_text_seg(segs, gen_text)
                else:
                    _emit_non_digit_tok(segs, t)
            return _finalize_segments(
                segs, color=chosen.color, is_numeric=True, is_error=is_err
            )

        segs = []
        for t in chosen.toks:
            _emit_non_digit_tok(segs, t)
        if num < 0 and not use_abs and chosen is secs[0]:
            segs.insert(0, FormatSegment("text", "-"))
        return _finalize_segments(segs, color=chosen.color, is_numeric=True)

    text_val = str(value)
    return FormattedResult(
        text=text_val,
        is_numeric=False,
        segments=(FormatSegment("text", text_val),),
    )
