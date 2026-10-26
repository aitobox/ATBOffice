"""CSV, TSV, and delimited/fixed-width text file I/O for ATBOffice Ledger."""

from __future__ import annotations

import re
from typing import Any


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
            # Simple count outside quotes if possible
            cnt = line.count(d)
            counts.append(cnt)

        # Delimiter must appear at least once per line on average
        if not counts or sum(counts) == 0:
            continue

        min_c = min(counts)
        avg_c = sum(counts) / len(counts)

        # Perfect consistency gives high score
        if min_c >= 1:
            variance = sum((c - avg_c) ** 2 for c in counts) / len(counts)
            # Preference weight for standard delimiters over space
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
    # Check space frequency at each column index across all lines
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
                # The break is typically after the non-space token or at the end of space run
                if run_start > 0:
                    breaks.append(run_start)

    return sorted(list(set(breaks)))
