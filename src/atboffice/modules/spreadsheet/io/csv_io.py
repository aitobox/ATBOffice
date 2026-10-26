"""CSV, TSV, and delimited/fixed-width text file I/O for ATBOffice Ledger."""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel


def decode_bytes(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """Decode raw bytes into text, automatically detecting BOM, UTF-16, UTF-8, GB18030, or Windows-1252.

    Returns:
        tuple[str, str]: (decoded_text, detected_encoding)
    """
    if encoding and encoding != "auto":
        norm_enc = encoding.lower()
        if norm_enc in ("windows-1252", "cp1252"):
            try:
                t = data.decode("cp1252")
            except Exception:
                t = data.decode("latin1", errors="replace")
        else:
            try:
                t = data.decode(encoding)
            except Exception:
                t = data.decode(encoding, errors="replace")
        if t.startswith("\ufeff"):
            t = t[1:]
        return t, encoding

    # 1. BOM Detection
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace"), "utf-8"
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16le", errors="replace"), "utf-16le"
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16be", errors="replace"), "utf-16be"

    # 2. UTF-16 without BOM heuristic: many zero bytes in alternating positions
    n = len(data)
    if n >= 4:
        sample_len = min(n, 2000)
        z0 = 0
        z1 = 0
        for i in range(0, sample_len - 1, 2):
            if data[i] == 0:
                z0 += 1
            if data[i + 1] == 0:
                z1 += 1
        if z1 > sample_len / 6 and z0 < sample_len / 50:
            return data.decode("utf-16le", errors="replace"), "utf-16le"
        if z0 > sample_len / 6 and z1 < sample_len / 50:
            return data.decode("utf-16be", errors="replace"), "utf-16be"

    # 3. Strict UTF-8 trial
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass

    # 4. Chinese GB18030 trial
    try:
        gb_text = data.decode("gb18030")
        if any("\u4e00" <= ch <= "\u9fff" for ch in gb_text):
            return gb_text, "gb18030"
    except UnicodeDecodeError:
        pass

    # 5. Windows-1252 / Latin-1 fallback
    try:
        return data.decode("cp1252"), "windows-1252"
    except Exception:
        return data.decode("latin1", errors="replace"), "windows-1252"


def sniff_delimiter(text: str) -> str:
    """Sniff the most likely column delimiter in the sample text.

    Tests candidate delimiters: ',', '\\t', ';', '|', ' '.
    """
    candidates = [",", "\t", ";", "|", " "]
    lines = [line for line in text.splitlines() if line.strip()][:30]
    if not lines:
        return ","

    best_delim = ","
    max_score = -1.0

    for d in candidates:
        counts: list[int] = []
        for line in lines:
            cnt = line.count(d)
            counts.append(cnt)

        if not counts or sum(counts) == 0:
            continue

        min_c = min(counts)
        avg_c = sum(counts) / len(counts)

        if min_c >= 1:
            variance = sum((c - avg_c) ** 2 for c in counts) / len(counts)
            weight = 1.0 if d in (",", "\t", ";", "|") else 0.5
            score = (avg_c / (1.0 + variance)) * weight
            if score > max_score:
                max_score = score
                best_delim = d

    return best_delim


def guess_fixed_breaks(text: str) -> list[int]:
    """Guess column break positions for fixed-width text."""
    lines = [line for line in text.splitlines() if line.strip()][:30]
    if not lines:
        return []

    max_len = min(max(len(l) for l in lines), 500)
    space_freq = [0] * max_len
    for line in lines:
        for idx in range(min(len(line), max_len)):
            if line[idx] == " ":
                space_freq[idx] += 1

    total_lines = len(lines)
    threshold = total_lines * 0.7

    breaks: list[int] = []
    in_space_run = False
    run_start = -1

    for idx in range(max_len):
        if space_freq[idx] >= threshold:
            if not in_space_run:
                in_space_run = True
                run_start = idx
        else:
            if in_space_run:
                in_space_run = False
                if run_start > 0:
                    breaks.append(run_start)

    return sorted(list(set(breaks)))


def parse_delimited(
    text: str,
    delims: str = ",",
    quote: str = '"',
    merge: bool = False,
    max_rows: int | None = None,
) -> list[list[str]]:
    """Parse delimited text into rows of strings according to RFC 4180 rules."""
    rows: list[list[str]] = []
    row: list[str] = []
    field = ""
    i = 0
    n = len(text)
    quoted = False
    was_quoted = False
    q = quote if quote else ""
    delim_set = set(delims) if delims else {","}

    def end_field() -> None:
        nonlocal field, was_quoted
        row.append(field)
        field = ""
        was_quoted = False

    def end_row() -> None:
        nonlocal row
        end_field()
        rows.append(row)
        row = []

    while i < n:
        ch = text[i]
        if quoted:
            if q and ch == q:
                if i + 1 < n and text[i + 1] == q:
                    field += q
                    i += 2
                    continue
                quoted = False
                i += 1
                continue
            field += ch
            i += 1
            continue

        if q and ch == q and field == "" and not was_quoted:
            quoted = True
            was_quoted = True
            i += 1
            continue

        if ch in delim_set:
            end_field()
            i += 1
            if merge:
                while i < n and text[i] in delim_set:
                    i += 1
            continue

        if ch in ("\r", "\n"):
            end_row()
            if ch == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            i += 1
            if max_rows is not None and len(rows) >= max_rows:
                return rows
            continue

        field += ch
        i += 1

    if field != "" or row or quoted or was_quoted:
        end_row()

    return rows


def parse_fixed_width(
    text: str, breaks: list[int], max_rows: int | None = None
) -> list[list[str]]:
    """Parse fixed-width lines into rows of strings by break column indices."""
    lines = text.splitlines()
    if lines and lines[-1] == "":
        lines.pop()

    sorted_breaks = sorted([b for b in breaks if b > 0])
    out: list[list[str]] = []

    for line in lines[:max_rows] if max_rows else lines:
        row: list[str] = []
        prev = 0
        for b in sorted_breaks:
            row.append(line[prev:b].strip())
            prev = b
        row.append(line[prev:].strip())
        out.append(row)

    return out


def convert_cell_value(val_str: str | None, col_type: str = "General") -> Any:
    """Convert raw text into typed cell value conforming to Excel's General rules.

    col_type options: 'General', 'Text', 'Date', 'Skip'.
    """
    if val_str is None:
        return None

    if col_type.lower() == "skip":
        return None

    if col_type.lower() == "text":
        return str(val_str)

    s = val_str.strip()
    if not s:
        return None

    # Booleans
    upper_s = s.upper()
    if upper_s == "TRUE":
        return True
    if upper_s == "FALSE":
        return False

    # Numbers
    # Percentage (e.g. 25%, -12.5%)
    if s.endswith("%"):
        try:
            return float(s[:-1].strip()) / 100.0
        except ValueError:
            pass

    # Strip currency symbol ($ or € or ¥) if prefix
    cleaned_num = re.sub(r"^[\$¥€£]\s*", "", s)

    # Check for thousand commas like 1,234.50 or 1,234,567
    if re.match(r"^-?\d{1,3}(,\d{3})+(\.\d+)?$", cleaned_num):
        cleaned_num = cleaned_num.replace(",", "")

    try:
        if re.match(r"^-?\d+$", cleaned_num):
            return int(cleaned_num)
        float_val = float(cleaned_num)
        if not math.isnan(float_val) and not math.isinf(float_val):
            return float_val
    except ValueError:
        pass

    # Date parsing (simple ISO, YMD, DMY, MDY checks)
    if col_type.lower().startswith("date") or re.match(
        r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$", s
    ):
        return s

    return val_str


def populate_sheet(
    model: SheetDataModel,
    rows: list[list[str]],
    start_row: int = 0,
    start_col: int = 0,
    col_formats: list[str] | dict[int, str] | None = None,
) -> None:
    """Populate SheetDataModel with 2D rows of text values."""
    for r_idx, row in enumerate(rows):
        r = start_row + r_idx
        for c_idx, val in enumerate(row):
            c = start_col + c_idx
            fmt = "General"
            if col_formats:
                if isinstance(col_formats, dict):
                    fmt = col_formats.get(c_idx, "General")
                elif c_idx < len(col_formats):
                    fmt = col_formats[c_idx]

            if fmt.lower() == "skip":
                continue

            converted = convert_cell_value(val, fmt)
            if converted is not None:
                model.set_cell_value(r, c, converted)


def export_csv(
    model: SheetDataModel,
    delimiter: str = ",",
    quote: str = '"',
    encoding: str = "utf-8",
) -> str:
    """Export non-empty SheetDataModel cells to delimited CSV / TSV text."""
    if not model.cells:
        return ""

    min_r = min(r for r, _ in model.cells.keys())
    max_r = max(r for r, _ in model.cells.keys())
    min_c = min(c for _, c in model.cells.keys())
    max_c = max(c for _, c in model.cells.keys())

    lines: list[str] = []
    q = quote if quote else '"'
    double_q = q + q

    for r in range(min_r, max_r + 1):
        row_fields: list[str] = []
        for c in range(min_c, max_c + 1):
            cell = model.get_cell(r, c)
            if cell is None or cell.value is None:
                t = ""
            else:
                t = model.get_formatted_text(r, c)
                if not t and cell.value is not None:
                    t = str(cell.value)

            # Quoting rules: quote if contains delimiter, quote, \r, or \n
            if delimiter in t or q in t or "\n" in t or "\r" in t:
                escaped = t.replace(q, double_q)
                row_fields.append(f"{q}{escaped}{q}")
            else:
                row_fields.append(t)

        lines.append(delimiter.join(row_fields))

    return "\r\n".join(lines) + "\r\n"
