"""Unit tests for Excel number formatting engine (numfmt.py)."""


from atboffice.drawing.numfmt import (
    date_to_serial,
    format_value,
    serial_to_parts,
)


class TestSerialDateConversion:
    def test_date_to_serial_1900(self) -> None:
        # Excel serial 1 is 1900-01-01
        assert date_to_serial(1900, 1, 1) == 1
        # Excel 1900 leap year bug: 1900-02-29 is serial 60
        assert date_to_serial(1900, 2, 29) == 60
        assert date_to_serial(1900, 3, 1) == 61
        # 2026-10-24
        s = date_to_serial(2026, 10, 24)
        assert s > 40000

    def test_serial_to_parts(self) -> None:
        parts = serial_to_parts(1)
        assert parts.year == 1900
        assert parts.month == 1
        assert parts.day == 1
        assert parts.weekday == 0  # Sunday in Excel 1900-01-01

        # 2026-10-24 is Saturday
        s = date_to_serial(2026, 10, 24)
        p = serial_to_parts(s)
        assert (p.year, p.month, p.day) == (2026, 10, 24)
        assert p.weekday == 6  # Saturday


class TestGeneralFormat:
    def test_none_and_empty(self) -> None:
        assert format_value(None).text == ""
        assert format_value("").text == ""

    def test_booleans(self) -> None:
        assert format_value(True).text == "TRUE"
        assert format_value(False).text == "FALSE"

    def test_integers_and_floats(self) -> None:
        assert format_value(42).text == "42"
        assert format_value(3.14159).text == "3.14159"
        assert format_value(-100).text == "-100"

    def test_string_literal(self) -> None:
        assert format_value("Hello").text == "Hello"


class TestNumericFormatting:
    def test_integer_patterns(self) -> None:
        assert format_value(5, "000").text == "005"
        assert format_value(1234, "#,##0").text == "1,234"
        assert format_value(1234567, "#,##0").text == "1,234,567"

    def test_decimal_patterns(self) -> None:
        assert format_value(12.3456, "0.00").text == "12.35"
        assert format_value(12, "0.00").text == "12.00"
        assert format_value(1234.5, "#,##0.00").text == "1,234.50"

    def test_percentages(self) -> None:
        assert format_value(0.25, "0%").text == "25%"
        assert format_value(0.255, "0.0%").text == "25.5%"
        assert format_value(1.5, "0.00%").text == "150.00%"

    def test_currency_and_escaping(self) -> None:
        assert format_value(1234.56, '"$"#,##0.00').text == "$1,234.56"
        assert format_value(1234.56, "¥#,##0.00").text == "¥1,234.56"

    def test_multiple_sections_positive_negative_zero(self) -> None:
        fmt = '#,##0;(#,##0);"-"'
        assert format_value(1234, fmt).text == "1,234"
        assert format_value(-1234, fmt).text == "(1,234)"
        assert format_value(0, fmt).text == "-"

    def test_color_tags(self) -> None:
        fmt = "[Green]#,##0;[Red]-#,##0"
        pos = format_value(100, fmt)
        assert pos.text == "100"
        is_green = pos.color in ("#008000", "#00FF00") or "green" in (pos.color or "").lower()
        assert is_green

        neg = format_value(-50, fmt)
        assert neg.text == "-50"
        assert neg.color == "#FF0000" or "red" in (neg.color or "").lower()


class TestDateFormatting:
    def test_standard_date(self) -> None:
        # 2026-10-24
        serial = date_to_serial(2026, 10, 24)
        assert format_value(serial, "yyyy-mm-dd").text == "2026-10-24"
        assert format_value(serial, "yyyy/m/d").text == "2026/10/24"
        assert format_value(serial, "yyyy年m月d日").text == "2026年10月24日"

    def test_localized_weekdays_chinese(self) -> None:
        # 2026-10-24 is Saturday (周六 / 星期六)
        serial = date_to_serial(2026, 10, 24)
        res_aaa = format_value(serial, "aaa", lcid=0x04)
        assert res_aaa.text == "六"

        res_aaaa = format_value(serial, "aaaa", lcid=0x04)
        assert res_aaaa.text == "星期六"

        # Combined format: yyyy-mm-dd aaaa
        res_combined = format_value(serial, "yyyy-mm-dd aaaa", lcid=0x04)
        assert res_combined.text == "2026-10-24 星期六"

    def test_english_weekdays(self) -> None:
        serial = date_to_serial(2026, 10, 24)
        assert format_value(serial, "ddd", lcid=0x09).text == "Sat"
        assert format_value(serial, "dddd", lcid=0x09).text == "Saturday"

    def test_negative_date_hashes(self) -> None:
        res = format_value(-1, "yyyy-mm-dd")
        assert res.is_error or res.text.startswith("#")


class TestCurrencyLocaleTokens:
    def test_pound_lcid_currency(self) -> None:
        res = format_value(125.0, "[$£-809]#,##0.00")
        assert res.text == "£125.00"
        assert res.is_numeric is True

    def test_currency_without_lcid_and_date_like_letters(self) -> None:
        # 'd' and 's' inside USD must not trigger date parsing
        res = format_value(125.0, "[$USD]#,##0.00")
        assert res.text == "USD125.00"
        assert res.is_numeric is True

    def test_locale_only_tag_stripped(self) -> None:
        assert format_value(125.0, "[$-409]#,##0.00").text == "125.00"
        assert format_value(125.0, "[$€-2]#,##0.00").text == "€125.00"


class TestAccountingPaddingAndFill:
    def test_accounting_format_strips_tokens_and_exposes_fill_pos(self) -> None:
        res = format_value(1.0, "_($* #,##0.00_)")
        assert "$" in res.text
        assert "1.00" in res.text
        for forbidden in ("_", "*", "("):
            assert forbidden not in res.text
        assert res.has_fill is True
        assert res.fill_pos is not None
        assert "$" in res.text[: res.fill_pos]
        assert "1.00" in res.text[res.fill_pos :]

    def test_accounting_builtin_44_all_sections(self) -> None:
        fmt = '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)'
        pos = format_value(1.0, fmt)
        assert pos.text == " $1.00 "
        assert pos.has_fill is True
        assert pos.fill_pos == 2
        assert [s.kind for s in pos.segments] == ["pad", "text", "fill", "text", "pad"]
        assert pos.segments[0].value == "("
        assert pos.segments[4].value == ")"

        neg = format_value(-1.0, fmt)
        assert "$" in neg.text
        assert "(1.00)" in neg.text
        assert neg.has_fill is True

        zero = format_value(0.0, fmt)
        assert "$" in zero.text
        assert "-" in zero.text
        assert zero.has_fill is True

        txt = format_value("Total", fmt)
        assert txt.text == " Total "
        assert txt.is_numeric is False


class TestGeneralWidthLimit:
    def test_general_11_char_limit(self) -> None:
        res = format_value(0.10000000149011612, "General")
        assert res.text == "0.100000001"
        assert len(res.text) == 11

    def test_general_column_width_rounding(self) -> None:
        res = format_value(5715.046400000001, "General", max_chars=8)
        assert res.text == "5715.046"
        assert len(res.text) <= 8

    def test_general_scientific_overflow_11_chars(self) -> None:
        res = format_value(123456789012, "General")
        assert res.text == "1.23457E+11"
        assert len(res.text) <= 11

    def test_general_too_narrow_hashes(self) -> None:
        res = format_value(12345, "General", max_chars=4)
        assert set(res.text) == {"#"}
        assert res.is_error is True
