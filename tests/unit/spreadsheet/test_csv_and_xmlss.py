"""Unit and GUI tests for CSV / TXT import wizard and XML Spreadsheet 2003 I/O."""

import pytest
from atboffice.modules.spreadsheet.io.csv_io import (
    decode_bytes,
    guess_fixed_breaks,
    sniff_delimiter,
)


def test_decode_bytes_bom():
    # UTF-8 BOM
    utf8_data = b"\xef\xbb\xbfHello,World\n1,2"
    text, enc = decode_bytes(utf8_data)
    assert enc == "utf-8"
    assert text.startswith("Hello,World")
    assert not text.startswith("\ufeff")

    # UTF-16LE BOM
    utf16le_data = "\ufeffName,Score\nAlice,100".encode("utf-16le")
    text, enc = decode_bytes(utf16le_data)
    assert enc == "utf-16le"
    assert "Alice,100" in text

    # UTF-16BE BOM
    utf16be_data = "\ufeffName,Score\nBob,90".encode("utf-16be")
    text, enc = decode_bytes(utf16be_data)
    assert enc == "utf-16be"
    assert "Bob,90" in text


def test_decode_bytes_utf16_no_bom():
    raw_le = "ID,Value\n1,10\n2,20\n3,30\n".encode("utf-16le")
    text, enc = decode_bytes(raw_le)
    assert enc == "utf-16le"
    assert "ID,Value" in text


def test_decode_bytes_gb18030():
    chinese_text = "姓名,部门,薪资\n张三,研发部,15000\n李四,市场部,12000\n"
    gb_data = chinese_text.encode("gb18030")
    text, enc = decode_bytes(gb_data)
    assert enc == "gb18030"
    assert "张三" in text
    assert "研发部" in text


def test_decode_bytes_windows1252():
    # Byte 0x80 is Euro sign in Windows-1252 (not valid UTF-8)
    w1252_data = b"Price\n\x80100\n\x80200"
    text, enc = decode_bytes(w1252_data)
    assert enc == "windows-1252"
    assert "100" in text


def test_decode_bytes_explicit():
    sample = "Col1,Col2\nA,B".encode("utf-8")
    text, enc = decode_bytes(sample, encoding="utf-8")
    assert enc == "utf-8"
    assert text == "Col1,Col2\nA,B"


def test_sniff_delimiter():
    csv_text = "A,B,C\n1,2,3\n4,5,6"
    assert sniff_delimiter(csv_text) == ","

    tsv_text = "A\tB\tC\n1\t2\t3\n4\t5\t6"
    assert sniff_delimiter(tsv_text) == "\t"

    semicolon_text = "A;B;C\n1;2;3\n4;5;6"
    assert sniff_delimiter(semicolon_text) == ";"

    pipe_text = "A|B|C\n1|2|3\n4|5|6"
    assert sniff_delimiter(pipe_text) == "|"


def test_guess_fixed_breaks():
    lines = [
        "1001   Alice Smith     Engineering   ",
        "1002   Bob Jones       Marketing     ",
        "1003   Charlie Brown   Sales         ",
    ]
    text = "\n".join(lines)
    breaks = guess_fixed_breaks(text)
    assert len(breaks) >= 2
    assert 4 in breaks or 7 in breaks
