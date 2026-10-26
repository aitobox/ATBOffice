"""Rich Text Format (RTF 1.5) Reader and Writer for Quire."""

from __future__ import annotations

import copy
import re
from typing import Any

from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Story,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.properties import (
    ParagraphProperties,
    RunProperties,
)


class RtfReader:
    """Reader converting RTF 1.5 byte strings or strings into Quire Document DOM."""

    def read(self, src: str | bytes) -> Document:
        """Parse RTF source into a Document."""
        if isinstance(src, bytes):
            try:
                src_text = src.decode("utf-8")
            except UnicodeDecodeError:
                src_text = src.decode("latin-1", errors="replace")
        else:
            src_text = str(src or "")

        doc = Document()
        doc.main = Story(kind="main", blocks=[])

        if not src_text.strip():
            doc.main.blocks.append(Paragraph())
            return doc

        parser = _RtfParser(src_text, doc)
        parser.parse()
        if not doc.main.blocks:
            doc.main.blocks.append(Paragraph())

        return doc


class _RtfState:
    """Parser state for RTF group nesting."""

    def __init__(self) -> None:
        self.dest: str = "body"
        self.skip: bool = False
        self.uc: int = 1  # Number of replacement characters to skip after \uN
        self.r_pr: RunProperties = RunProperties()
        self.p_pr: ParagraphProperties = ParagraphProperties()
        self.in_table: bool = False
        self.cell_widths: list[float] = []


class _RtfParser:
    """Lexer and parser state machine for RTF documents."""

    def __init__(self, src: str, doc: Document) -> None:
        self.src = src
        self.doc = doc
        self.i = 0
        self.n = len(src)

        self.fonts: dict[int, str] = {}
        self.colors: list[str] = []
        self.stack: list[_RtfState] = []
        self.st = _RtfState()

        self.cur_p: Paragraph | None = None
        self.cur_row: Row | None = None
        self.cur_cell_blocks: list[Paragraph] = []
        self.cur_table: Table | None = None

        self.fld_inst: str = ""
        self.fld_link: str | None = None

        # Font and color table parsing buffers
        self.font_num: int | None = None
        self.font_name: str = ""
        self.color_r = 0
        self.color_g = 0
        self.color_b = 0
        self.color_has = False

    def parse(self) -> None:
        while self.i < self.n:
            ch = self.src[self.i]

            if ch == "{":
                self.i += 1
                self.stack.append(copy.deepcopy(self.st))
            elif ch == "}":
                self.i += 1
                if self.st.dest == "fonttbl" and self.font_num is not None:
                    name = self.font_name.rstrip(";").strip()
                    self.fonts[self.font_num] = name
                    self.font_num = None
                    self.font_name = ""

                if self.stack:
                    self.st = self.stack.pop()
            elif ch == "\\":
                self._parse_control()
            elif ch in ("\r", "\n"):
                self.i += 1
            else:
                self._parse_text()

        self._flush_paragraph()
        self._flush_table()

    def _parse_control(self) -> None:
        self.i += 1
        if self.i >= self.n:
            return

        c = self.src[self.i]

        # Escaped characters
        if c in ("{", "}", "\\"):
            self.i += 1
            self._add_text(c)
            return

        # Escaped hex byte: \'xx
        if c == "'":
            self.i += 1
            hex_str = self.src[self.i : self.i + 2]
            self.i += 2
            try:
                byte_val = int(hex_str, 16)
                self._add_text(chr(byte_val))
            except ValueError:
                pass
            return

        # Control symbol \* (ignore destination if unknown)
        if c == "*":
            self.i += 1
            self.st.skip = True
            return

        # Control word: letters followed by optional signed integer
        match = re.match(r"^([a-zA-Z]+)(-?\d+)?([ \t])?", self.src[self.i :])
        if not match:
            self.i += 1
            return

        word = match.group(1)
        param_str = match.group(2)
        param = int(param_str) if param_str is not None else None

        self.i += match.end()

        self._handle_control_word(word, param)

    def _handle_control_word(self, word: str, param: int | None) -> None:
        # Group destinations
        if word == "fonttbl":
            self.st.dest = "fonttbl"
            return
        if word == "colortbl":
            self.st.dest = "colortbl"
            return
        if word == "stylesheet":
            self.st.dest = "stylesheet"
            return
        if word == "field":
            self.fld_inst = ""
            self.fld_link = None
            return
        if word == "fldinst":
            self.st.dest = "fldinst"
            return
        if word == "fldrslt":
            self.st.dest = "fldrslt"
            link_re = r'HYPERLINK\s+(?:"([^"]+)"|\\?"([^"\\]+)\\?"|([^\s}]+))'
            m = re.search(link_re, self.fld_inst, re.IGNORECASE)
            if m:
                self.fld_link = m.group(1) or m.group(2) or m.group(3)
            return

        # Font table definitions
        if self.st.dest == "fonttbl":
            if word == "f" and param is not None:
                if self.font_num is not None:
                    self.fonts[self.font_num] = self.font_name.rstrip(";").strip()
                self.font_num = param
                self.font_name = ""
            return

        # Color table definitions
        if self.st.dest == "colortbl":
            if word == "red" and param is not None:
                self.color_r = param
                self.color_has = True
            elif word == "green" and param is not None:
                self.color_g = param
                self.color_has = True
            elif word == "blue" and param is not None:
                self.color_b = param
                self.color_has = True
            return

        # Character Formatting
        if word == "plain":
            self.st.r_pr = RunProperties()
            return
        if word == "b":
            self.st.r_pr.b = True if (param is None or param != 0) else False
            return
        if word == "i":
            self.st.r_pr.i = True if (param is None or param != 0) else False
            return
        if word == "ul":
            self.st.r_pr.u = "single" if (param is None or param != 0) else "none"
            return
        if word == "ulnone":
            self.st.r_pr.u = "none"
            return
        if word == "strike":
            self.st.r_pr.strike = True if (param is None or param != 0) else False
            return
        if word == "fs" and param is not None:
            self.st.r_pr.sz = param / 2.0
            return
        if word == "f" and param is not None:
            if param in self.fonts:
                self.st.r_pr.font = self.fonts[param]
            return
        if word == "cf" and param is not None:
            if param == 0:
                self.st.r_pr.color = "auto"
            elif 0 <= param < len(self.colors) and self.colors[param]:
                self.st.r_pr.color = self.colors[param]
            return
        if word == "highlight" and param is not None:
            if 0 < param < len(self.colors) and self.colors[param]:
                self.st.r_pr.highlight = self.colors[param]
            return
        if word == "u" and param is not None:
            val = param if param >= 0 else param + 65536
            self._add_text(chr(val))
            for _ in range(self.st.uc):
                if self.i < self.n and self.src[self.i] not in ("\\", "{", "}"):
                    self.i += 1
            return
        if word == "uc" and param is not None:
            self.st.uc = max(0, param)
            return

        # Paragraph Formatting
        if word == "pard":
            self._flush_paragraph()
            self.st.p_pr = ParagraphProperties()
            return
        if word in ("par", "line"):
            self._flush_paragraph()
            return
        if word == "qc":
            self.st.p_pr.jc = "center"
            return
        if word == "qr":
            self.st.p_pr.jc = "right"
            return
        if word == "qj":
            self.st.p_pr.jc = "both"
            return
        if word == "ql":
            self.st.p_pr.jc = "left"
            return
        if word == "sb" and param is not None:
            self.st.p_pr.sp.before = param / 20.0
            return
        if word == "sa" and param is not None:
            self.st.p_pr.sp.after = param / 20.0
            return

        # Table formatting
        if word == "trowd":
            self.st.cell_widths = []
            return
        if word == "cellx" and param is not None:
            pt_w = param / 20.0
            self.st.cell_widths.append(pt_w)
            return
        if word == "intbl":
            self.st.in_table = True
            return
        if word == "cell":
            self._flush_cell()
            return
        if word == "row":
            self._flush_row()
            return

    def _parse_text(self) -> None:
        start = self.i
        while self.i < self.n and self.src[self.i] not in ("\\", "{", "}", "\r", "\n"):
            self.i += 1
        chunk = self.src[start : self.i]

        if self.st.dest == "colortbl":
            for ch in chunk:
                if ch == ";":
                    if self.color_has:
                        hex_col = f"{self.color_r:02X}{self.color_g:02X}{self.color_b:02X}"
                        self.colors.append(hex_col)
                        self.color_has = False
                    else:
                        self.colors.append("")
            return

        if self.st.dest == "fonttbl":
            self.font_name += chunk
            return

        if self.st.dest == "fldinst":
            self.fld_inst += chunk
            return

        self._add_text(chunk)

    def _add_text(self, text: str) -> None:
        if self.st.skip:
            return
        if self.st.dest not in ("body", "fldrslt"):
            return
        if not text:
            return

        if self.cur_p is None:
            self.cur_p = Paragraph()
            self.cur_p.p_pr = copy.deepcopy(self.st.p_pr)

        r_pr = copy.deepcopy(self.st.r_pr)
        if self.fld_link and self.st.dest == "fldrslt":
            r_pr.link = {"url": self.fld_link}
            r_pr.color = "0969DA"
            r_pr.u = "single"

        if (
            self.cur_p.runs
            and isinstance(self.cur_p.runs[-1], TextItem)
            and self.cur_p.runs[-1].r_pr == r_pr
        ):
            self.cur_p.runs[-1].text += text
        else:
            self.cur_p.runs.append(TextItem(text, r_pr))

    def _flush_paragraph(self) -> None:
        if self.cur_p is not None:
            if not self.cur_p.runs and not self.st.in_table:
                self.cur_p = None
                return
            if self.st.in_table:
                self.cur_cell_blocks.append(self.cur_p)
            else:
                self._flush_table()
                self.doc.main.blocks.append(self.cur_p)
            self.cur_p = None

    def _flush_cell(self) -> None:
        self._flush_paragraph()
        if not self.cur_cell_blocks:
            self.cur_cell_blocks.append(Paragraph())

        cell = Cell(blocks=list(self.cur_cell_blocks))
        self.cur_cell_blocks = []

        if self.cur_row is None:
            self.cur_row = Row()

        idx = len(self.cur_row.cells)
        if idx < len(self.st.cell_widths):
            prev = self.st.cell_widths[idx - 1] if idx > 0 else 0.0
            cell.tc_pr.w = self.st.cell_widths[idx] - prev

        self.cur_row.cells.append(cell)

    def _flush_row(self) -> None:
        if self.cur_row is not None:
            if self.cur_table is None:
                self.cur_table = Table()
                widths: list[float] = []
                for i, b in enumerate(self.st.cell_widths):
                    prev = self.st.cell_widths[i - 1] if i > 0 else 0.0
                    widths.append(b - prev)
                self.cur_table.grid = widths

            self.cur_table.rows.append(self.cur_row)
            self.cur_row = None

    def _flush_table(self) -> None:
        if self.cur_table is not None:
            self.doc.main.blocks.append(self.cur_table)
            self.cur_table = None
            self.st.in_table = False


class RtfWriter:
    """Writer serializing Quire Document DOM to RTF 1.5 byte strings."""

    def write(self, doc: Document) -> bytes:
        """Convert document into RTF 1.5 byte sequence."""
        fonts: list[str] = ["Times New Roman"]
        colors: list[str] = []

        def font_idx(name: str | None) -> int:
            if not name:
                return 0
            if name not in fonts:
                fonts.append(name)
            return fonts.index(name)

        def color_idx(hex_code: str | None) -> int:
            if not hex_code or hex_code.lower() == "auto":
                return 0
            cleaned = hex_code.lstrip("#").upper()
            if cleaned not in colors:
                colors.append(cleaned)
            return colors.index(cleaned) + 1

        for b in doc.main.blocks:
            if isinstance(b, Paragraph):
                self._collect_props(b, font_idx, color_idx)
            elif isinstance(b, Table):
                for r in b.rows:
                    for c in r.cells:
                        for cb in c.blocks:
                            if isinstance(cb, Paragraph):
                                self._collect_props(cb, font_idx, color_idx)

        font_tbl_entries = [f"{{\\f{i}\\fnil\\fcharset0 {f};}}" for i, f in enumerate(fonts)]
        font_tbl = "{\\fonttbl" + "".join(font_tbl_entries) + "}"

        color_tbl_entries = []
        for c in colors:
            try:
                r = int(c[0:2], 16)
                g = int(c[2:4], 16)
                b = int(c[4:6], 16)
                color_tbl_entries.append(f"\\red{r}\\green{g}\\blue{b};")
            except (ValueError, IndexError):
                color_tbl_entries.append(";")
        color_tbl = "{\\colortbl;" + "".join(color_tbl_entries) + "}"

        header = "{\\rtf1\\ansi\\ansicpg1252\\deff0\n" + font_tbl + "\n" + color_tbl + "\n"

        body_parts: list[str] = []
        for b in doc.main.blocks:
            if isinstance(b, Paragraph):
                body_parts.append(self._write_paragraph(b, font_idx, color_idx))
            elif isinstance(b, Table):
                body_parts.append(self._write_table(b, font_idx, color_idx))

        footer = "}"
        rtf_text = header + "\n".join(body_parts) + footer
        return rtf_text.encode("latin-1", errors="replace")

    def _collect_props(self, p: Paragraph, font_idx: Any, color_idx: Any) -> None:
        for r in p.runs:
            if isinstance(r, TextItem):
                if r.r_pr.font:
                    font_idx(r.r_pr.font)
                if r.r_pr.color:
                    color_idx(r.r_pr.color)

    def _write_paragraph(
        self, p: Paragraph, font_idx: Any, color_idx: Any, in_table: bool = False
    ) -> str:
        s = "\\pard\\plain"
        if in_table:
            s += "\\intbl"

        jc = p.p_pr.jc
        if jc == "center":
            s += "\\qc"
        elif jc == "right":
            s += "\\qr"
        elif jc == "both":
            s += "\\qj"
        else:
            s += "\\ql"

        if p.p_pr.sp.before:
            s += f"\\sb{int(p.p_pr.sp.before * 20)}"
        if p.p_pr.sp.after:
            s += f"\\sa{int(p.p_pr.sp.after * 20)}"

        s += " "
        for r in p.runs:
            if isinstance(r, TextItem):
                s += self._write_run(r, font_idx, color_idx)

        if not in_table:
            s += "\\par"
        return s

    def _write_run(self, r: TextItem, font_idx: Any, color_idx: Any) -> str:
        r_pr = r.r_pr
        tags = ""
        if r_pr.font:
            tags += f"\\f{font_idx(r_pr.font)}"
        if r_pr.sz:
            tags += f"\\fs{int(r_pr.sz * 2)}"
        if r_pr.b:
            tags += "\\b"
        if r_pr.i:
            tags += "\\i"
        if r_pr.u and r_pr.u != "none":
            tags += "\\ul"
        if r_pr.strike:
            tags += "\\strike"
        if r_pr.color:
            c_idx = color_idx(r_pr.color)
            if c_idx > 0:
                tags += f"\\cf{c_idx}"

        text = self._escape_rtf(r.text)
        link = getattr(r_pr, "link", None)
        if link and link.get("url"):
            url = self._escape_rtf(link["url"])
            return (
                f"{{\\field{{\\*\\fldinst {{HYPERLINK \"{url}\"}}}}"
                f"{{\\fldrslt {{{tags} {text}}}}}}}"
            )

        if tags:
            return f"{{{tags} {text}}}"
        return text

    def _write_table(self, tbl: Table, font_idx: Any, color_idx: Any) -> str:
        rows_rtf: list[str] = []
        grid = tbl.grid or [120.0] * (len(tbl.rows[0].cells) if tbl.rows else 1)

        for row in tbl.rows:
            row_s = "\\trowd"
            boundary = 0.0
            for col_idx, cell in enumerate(row.cells):
                w = cell.tc_pr.w or (grid[col_idx] if col_idx < len(grid) else 120.0)
                boundary += w
                row_s += f"\\cellx{int(boundary * 20)}"

            row_s += "\n"
            for cell in row.cells:
                for block in cell.blocks:
                    if isinstance(block, Paragraph):
                        row_s += (
                            self._write_paragraph(block, font_idx, color_idx, in_table=True) + " "
                        )
                row_s += "\\cell\n"
            row_s += "\\row"
            rows_rtf.append(row_s)

        return "\n".join(rows_rtf)

    def _escape_rtf(self, text: str) -> str:
        out: list[str] = []
        for ch in text:
            if ch == "\\":
                out.append("\\\\")
            elif ch == "{":
                out.append("\\{")
            elif ch == "}":
                out.append("\\}")
            elif ord(ch) < 128:
                out.append(ch)
            else:
                out.append(f"\\u{ord(ch)}?")
        return "".join(out)


def read_rtf(src: str | bytes) -> Document:
    """Read RTF string or bytes into a Quire Document."""
    reader = RtfReader()
    return reader.read(src)


def write_rtf(doc: Document) -> bytes:
    """Write Quire Document into RTF 1.5 byte sequence."""
    writer = RtfWriter()
    return writer.write(doc)
