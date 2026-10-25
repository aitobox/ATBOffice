"""Excel number and date format engine.

Converts values into formatted strings according to Excel format codes (ECMA-376),
with full support for Chinese/East-Asian weekday localization (`aaa`, `aaaa`).
"""

from __future__ import annotations

import datetime
import math
import re
from dataclasses import dataclass
from typing import Any, Final

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

# East Asian / Chinese weekdays
# Index 0 is Sunday, 6 is Saturday
ZH_WEEKDAYS_SHORT: Final[list[str]] = ["日", "一", "二", "三", "四", "五", "六"]
ZH_WEEKDAYS_LONG: Final[list[str]] = [
    "星期日",
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
]

EN_WEEKDAYS_SHORT: Final[list[str]] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
EN_WEEKDAYS_LONG: Final[list[str]] = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


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


@dataclass(frozen=True)
class FormattedResult:
    text: str
    color: str | None = None
    is_numeric: bool = False
    is_error: bool = False


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


def serial_to_parts(v: float, date1904: bool = False) -> DateParts:
    """Convert an Excel serial number to date and time components."""
    days = int(math.floor(v))
    secs = (v - days) * 86400.0
    secs = round(secs, 3)
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

    return DateParts(year=y, month=m, day=d, weekday=wd, hour=h, minute=minute, second=s, sub=sub)


def _split_sections(code: str) -> list[str]:
    """Split an Excel format code into sections separated by unquoted semicolons."""
    sections: list[str] = []
    current: list[str] = []
    in_quotes = False
    in_brackets = False
    escaped = False

    for char in code:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if char == '"':
            in_quotes = not in_quotes
            current.append(char)
            continue
        if char == "[" and not in_quotes:
            in_brackets = True
            current.append(char)
            continue
        if char == "]" and not in_quotes:
            in_brackets = False
            current.append(char)
            continue
        if char == ";" and not in_quotes and not in_brackets:
            sections.append("".join(current))
            current = []
            continue
        current.append(char)

    sections.append("".join(current))
    return sections


def _parse_tokens(section: str) -> tuple[str, str | None, str | None]:
    """Extract color and condition from section, returning (clean_section, color, condition)."""
    color: str | None = None
    condition: str | None = None

    def repl(m: re.Match[str]) -> str:
        nonlocal color, condition
        content = m.group(1).strip()
        lower = content.lower()
        if lower in COLOR_MAP:
            color = COLOR_MAP[lower]
            return ""
        if lower.startswith("color"):
            return ""
        if any(lower.startswith(op) for op in ("<=", ">=", "<>", "<", ">", "=")):
            condition = content
            return ""
        if lower.startswith("$-"):
            return ""
        return m.group(0)

    clean = re.sub(r"\[([^\]]+)\]", repl, section)
    return clean, color, condition


def _is_date_format(code: str) -> bool:
    """Check if format code is a date or time format."""
    tokens = ["yyyy", "yy", "m", "d", "h", "s", "aaa", "am/pm", "a/p"]
    clean = re.sub(r'"[^"]*"', "", code).lower()
    return any(t in clean for t in tokens)


# Regex for single-pass date tokenization
DATE_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r'(".*?"|\\.|aaaa|aaa|dddd|ddd|dd|d|mmmm|mmm|mm|m|yyyy|yy|hh|h|ss|s|am/pm|a/p|.)',
    re.IGNORECASE,
)


def _format_date(parts: DateParts, code: str, lcid: int | str) -> str:
    """Format date parts using single-pass tokenization."""
    is_chinese = lcid == 0x04 or str(lcid).lower().startswith("zh")
    tokens = DATE_TOKEN_RE.findall(code)
    out: list[str] = []

    for tok in tokens:
        if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
            out.append(tok[1:-1])
        elif tok.startswith("\\") and len(tok) == 2:
            out.append(tok[1])
        else:
            low = tok.lower()
            if low == "aaaa":
                out.append(
                    ZH_WEEKDAYS_LONG[parts.weekday] if is_chinese else EN_WEEKDAYS_LONG[parts.weekday]
                )
            elif low == "aaa":
                out.append(
                    ZH_WEEKDAYS_SHORT[parts.weekday] if is_chinese else EN_WEEKDAYS_SHORT[parts.weekday]
                )
            elif low == "dddd":
                out.append(EN_WEEKDAYS_LONG[parts.weekday])
            elif low == "ddd":
                out.append(EN_WEEKDAYS_SHORT[parts.weekday])
            elif low == "dd":
                out.append(f"{parts.day:02d}")
            elif low == "d":
                out.append(str(parts.day))
            elif low == "yyyy":
                out.append(f"{parts.year:04d}")
            elif low == "yy":
                out.append(f"{parts.year % 100:02d}")
            elif low == "mm":
                out.append(f"{parts.month:02d}")
            elif low == "m":
                out.append(str(parts.month))
            elif low == "hh":
                out.append(f"{parts.hour:02d}")
            elif low == "h":
                out.append(str(parts.hour))
            elif low == "ss":
                out.append(f"{parts.second:02d}")
            elif low == "s":
                out.append(str(parts.second))
            else:
                out.append(tok)

    return "".join(out)


# Regex for numeric tokenization
NUM_TOKEN_RE: Final[re.Pattern[str]] = re.compile(
    r'(".*?"|\\.|[\#0\,\.]+(?:[eE][\+\-]0+)?|.)'
)


def _format_number_pattern(val: float, pattern: str) -> str:
    """Format float into standard Excel numeric pattern using tokenized parsing."""
    is_percent = "%" in pattern
    if is_percent:
        val = val * 100.0

    tokens = NUM_TOKEN_RE.findall(pattern)
    out: list[str] = []

    # Find the main numeric mask token (the one containing # or 0)
    for tok in tokens:
        if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
            out.append(tok[1:-1])
        elif tok.startswith("\\") and len(tok) == 2:
            out.append(tok[1])
        elif any(c in tok for c in ("#", "0")):
            # This is the numeric mask token!
            dec_match = re.search(r"\.([0#]+)", tok)
            dec_places = len(dec_match.group(1)) if dec_match else 0
            use_comma = "," in tok.replace(dec_match.group(0) if dec_match else "", "")

            if re.search(r"[eE][\+\-]0+", tok):
                fmt = f"{{:.{dec_places}e}}"
                num_str = fmt.format(val).upper()
            else:
                rounded = round(val, dec_places)
                if dec_places > 0:
                    if use_comma:
                        num_str = f"{rounded:,.{dec_places}f}"
                    else:
                        num_str = f"{rounded:.{dec_places}f}"
                else:
                    int_val = int(round(val))
                    zero_match = re.search(r"0+", tok)
                    zero_count = len(zero_match.group(0)) if zero_match else 1
                    if use_comma:
                        num_str = f"{int_val:,}"
                    elif zero_count > 1:
                        num_str = f"{int_val:0{zero_count}d}"
                    else:
                        num_str = str(int_val)
            out.append(num_str)
        else:
            out.append(tok)

    return "".join(out)


def format_value(
    value: Any,
    format_str: str = "General",
    lcid: int | str = 0x04,
    date1904: bool = False,
) -> FormattedResult:
    """Format any scalar value according to Excel format specifications."""
    if value is None or value == "":
        return FormattedResult(text="", is_numeric=False)

    if isinstance(value, bool):
        return FormattedResult(text="TRUE" if value else "FALSE", is_numeric=False)

    # Error string (e.g. #DIV/0!)
    if isinstance(value, str) and value.startswith("#") and value.endswith("!"):
        return FormattedResult(text=value, is_error=True)

    # Text string
    if isinstance(value, str):
        if not format_str or format_str.lower() == "general":
            return FormattedResult(text=value, is_numeric=False)
        sections = _split_sections(format_str)
        sec_text = sections[3] if len(sections) >= 4 else None
        if sec_text:
            clean, col, _ = _parse_tokens(sec_text)
            clean = clean.replace("@", value)
            return FormattedResult(text=clean, color=col, is_numeric=False)
        return FormattedResult(text=value, is_numeric=False)

    # Numeric value
    if isinstance(value, (int, float)):
        num = float(value)
        if math.isnan(num) or math.isinf(num):
            return FormattedResult(text="#NUM!", is_error=True)

        if not format_str or format_str.lower() == "general":
            if num.is_integer():
                text = str(int(num))
            else:
                text = f"{num:.10g}"
            return FormattedResult(text=text, is_numeric=True)

        sections = _split_sections(format_str)
        sec_idx = 0
        is_neg = num < 0
        if is_neg:
            if len(sections) > 1:
                sec_idx = 1
                num = abs(num)
            else:
                sec_idx = 0
        elif num == 0.0 and len(sections) > 2:
            sec_idx = 2

        chosen_sec = sections[sec_idx] if sec_idx < len(sections) else sections[0]
        clean_code, color, _ = _parse_tokens(chosen_sec)

        # Date formatting check
        if _is_date_format(clean_code):
            if num < 0:
                return FormattedResult(
                    text="##########", color=color, is_numeric=False, is_error=True
                )
            parts = serial_to_parts(num, date1904=date1904)
            formatted_text = _format_date(parts, clean_code, lcid=lcid)
            return FormattedResult(text=formatted_text, color=color, is_numeric=False)

        # Number pattern formatting
        formatted_text = _format_number_pattern(num, clean_code)
        if is_neg and len(sections) == 1 and not formatted_text.startswith("-"):
            formatted_text = "-" + formatted_text

        return FormattedResult(text=formatted_text, color=color, is_numeric=True)

    return FormattedResult(text=str(value), is_numeric=False)
