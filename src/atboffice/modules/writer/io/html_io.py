"""Quire HTML Document Bidirectional Reader, Writer, and Web Page Serializer."""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from atboffice.modules.writer.models.document import (
    BreakItem,
    Cell,
    Document,
    Paragraph,
    Row,
    Story,
    SymbolItem,
    TabItem,
    Table,
    TextItem,
)
from atboffice.modules.writer.models.drawing import PictureItem
from atboffice.modules.writer.models.properties import (
    CellProperties,
    ParagraphProperties,
    RunProperties,
    ShadingProperties,
)

# ---------------------------------------------------------------------------
# CSS and Unit Helpers
# ---------------------------------------------------------------------------

SIZE_KEYWORDS: dict[str, float] = {
    "xx-small": 7.5,
    "x-small": 7.5,
    "small": 10.0,
    "medium": 12.0,
    "large": 13.5,
    "x-large": 18.0,
    "xx-large": 24.0,
    "smaller": 10.0,
    "larger": 14.0,
}

FONT_SIZE_ATTR: list[float] = [0.0, 7.5, 10.0, 12.0, 13.5, 18.0, 24.0, 36.0]

NAMED_COLORS: dict[str, str] = {
    "black": "000000",
    "white": "FFFFFF",
    "red": "FF0000",
    "green": "008000",
    "blue": "0000FF",
    "yellow": "FFFF00",
    "gray": "808080",
    "grey": "808080",
    "silver": "C0C0C0",
    "maroon": "800000",
    "navy": "000080",
    "purple": "800080",
    "teal": "008080",
    "olive": "808000",
    "lime": "00FF00",
    "aqua": "00FFFF",
    "fuchsia": "FF00FF",
    "orange": "FFA500",
}


def pt(v: Any, base: float = 12.0) -> float | None:
    """Convert CSS length strings (pt, px, in, cm, mm, em, rem, %) to points."""
    if v is None or v == "":
        return None
    s = str(v).strip()
    m = re.match(r"^(-?[\d.]+)(pt|px|in|cm|mm|em|rem|%|pc)?$", s, re.IGNORECASE)
    if not m:
        return None
    n = float(m.group(1))
    unit = (m.group(2) or "px").lower()
    match unit:
        case "pt":
            return n
        case "px":
            return n * 0.75
        case "in":
            return n * 72.0
        case "cm":
            return n * 28.3465
        case "mm":
            return n * 2.83465
        case "pc":
            return n * 12.0
        case "em" | "rem":
            return n * base
        case "%":
            return (n / 100.0) * base
        case _:
            return n


def parse_color(c: Any) -> str | None:
    """Parse color into standard 6-character hex string without leading '#'."""
    if not c:
        return None
    s = str(c).strip().lower()
    if s in {"transparent", "inherit", "initial", "windowtext", "currentcolor"}:
        return None

    # Hex 3-digit: #RGB -> RRGGBB
    m3 = re.match(r"^#([0-9a-f]{3})$", s)
    if m3:
        return "".join(ch * 2 for ch in m3.group(1)).upper()

    # Hex 6-digit: #RRGGBB
    m6 = re.match(r"^#([0-9a-f]{6})", s)
    if m6:
        return m6.group(1).upper()

    # rgb(...) or rgba(...)
    mr = re.match(r"^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:[\s,/]+([\d.]+%?))?", s)
    if mr:
        if mr.group(4) is not None:
            alpha = float(mr.group(4).rstrip("%"))
            if mr.group(4).endswith("%"):
                alpha /= 100.0
            if alpha == 0.0:
                return None
        r_val, g_val, b_val = int(mr.group(1)), int(mr.group(2)), int(mr.group(3))
        return f"{r_val:02X}{g_val:02X}{b_val:02X}"

    return NAMED_COLORS.get(s)


def style_map(style_str: str | None) -> dict[str, str]:
    """Parse inline CSS style string into a dictionary of property-value pairs."""
    out: dict[str, str] = {}
    if not style_str:
        return out
    for part in style_str.split(";"):
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        k = key.strip().lower()
        v = re.sub(r"\s*!important$", "", val.strip(), flags=re.IGNORECASE)
        if k:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# HTML Parser (Import Engine)
# ---------------------------------------------------------------------------

BLOCK_TAGS = frozenset(
    {
        "P",
        "DIV",
        "H1",
        "H2",
        "H3",
        "H4",
        "H5",
        "H6",
        "LI",
        "BLOCKQUOTE",
        "PRE",
        "ADDRESS",
        "CENTER",
        "SECTION",
        "ARTICLE",
        "HEADER",
        "FOOTER",
        "MAIN",
        "ASIDE",
        "NAV",
        "FIGURE",
        "FORM",
        "FIELDSET",
    }
)

SKIP_TAGS = frozenset(
    {
        "SCRIPT",
        "STYLE",
        "HEAD",
        "META",
        "LINK",
        "NOSCRIPT",
        "TEMPLATE",
        "IFRAME",
        "OBJECT",
        "EMBED",
        "BUTTON",
        "SELECT",
        "INPUT",
        "TEXTAREA",
        "SVG",
        "CANVAS",
        "VIDEO",
        "AUDIO",
    }
)

VOID_TAGS = frozenset(
    {
        "META",
        "LINK",
        "BASE",
        "INPUT",
        "IMG",
        "BR",
        "HR",
        "COL",
        "AREA",
        "PARAM",
        "SOURCE",
        "TRACK",
        "WBR",
    }
)


class _HtmlDomParser(HTMLParser):
    """HTML Parser creating Quire Document DOM structure."""

    def __init__(self, doc: Document) -> None:
        super().__init__(convert_charrefs=True)
        self.doc = doc
        self.doc_title: str = ""

        # Stacks and state
        self.r_pr_stack: list[RunProperties] = [RunProperties()]
        self.p_pr_stack: list[ParagraphProperties] = [ParagraphProperties()]
        self.link_stack: list[dict[str, str]] = []

        # Current container blocks (either doc.main.blocks or table cell blocks)
        self.target_blocks: list[Paragraph | Table] = self.doc.main.blocks
        self.cur_p: Paragraph | None = None

        # Lists management
        self.list_stack: list[dict[str, Any]] = []  # [{kind, type, id, lvl}]
        self.list_counter = 100

        # Tables management
        self.table_stack: list[Table] = []
        self.current_rows: list[Row] = []
        self.current_row: Row | None = None
        self.current_cells: list[Cell] = []
        self.current_cell: Cell | None = None
        self.cell_grid_widths: list[float] = []

        self.in_pre: bool = False
        self.skip_depth: int = 0
        self.in_title: bool = False

    @property
    def current_r_pr(self) -> RunProperties:
        return self.r_pr_stack[-1]

    @property
    def current_p_pr(self) -> ParagraphProperties:
        return self.p_pr_stack[-1]

    def _ensure_para(self) -> Paragraph:
        if self.cur_p is None:
            p_pr = ParagraphProperties()
            # Copy properties from current stack
            top_p = self.current_p_pr
            p_pr.style_id = top_p.style_id
            p_pr.jc = top_p.jc
            p_pr.ind.left = top_p.ind.left
            p_pr.ind.right = top_p.ind.right
            p_pr.ind.first_line = top_p.ind.first_line
            p_pr.sp.space_before = top_p.sp.space_before
            p_pr.sp.space_after = top_p.sp.space_after
            p_pr.sp.line = top_p.sp.line
            p_pr.sp.line_rule = top_p.sp.line_rule
            p_pr.num_id = top_p.num_id
            p_pr.num_level = top_p.num_level

            self.cur_p = Paragraph(runs=[], p_pr=p_pr)
            self.target_blocks.append(self.cur_p)
        return self.cur_p

    def _flush_para(self) -> None:
        self.cur_p = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        u_tag = tag.upper()
        attrs_dict = {k.lower(): (v or "") for k, v in attrs}

        if u_tag in SKIP_TAGS:
            if u_tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return

        if u_tag == "TITLE":
            self.in_title = True
            return

        styles = style_map(attrs_dict.get("style"))

        # 1. Update Paragraph Properties for block elements
        new_p_pr = ParagraphProperties()
        prev_p_pr = self.current_p_pr
        new_p_pr.style_id = prev_p_pr.style_id
        new_p_pr.jc = prev_p_pr.jc
        new_p_pr.ind.left = prev_p_pr.ind.left
        new_p_pr.ind.right = prev_p_pr.ind.right
        new_p_pr.ind.first_line = prev_p_pr.ind.first_line
        new_p_pr.sp.space_before = prev_p_pr.sp.space_before
        new_p_pr.sp.space_after = prev_p_pr.sp.space_after
        new_p_pr.sp.line = prev_p_pr.sp.line
        new_p_pr.sp.line_rule = prev_p_pr.sp.line_rule

        # Check alignment
        align = styles.get("text-align") or attrs_dict.get("align")
        if align:
            a = align.lower()
            if a == "center" or u_tag == "CENTER":
                new_p_pr.jc = "center"
            elif a in {"right", "end"}:
                new_p_pr.jc = "right"
            elif a in {"justify", "both"}:
                new_p_pr.jc = "both"
            elif a in {"left", "start"}:
                new_p_pr.jc = None
        elif u_tag == "CENTER":
            new_p_pr.jc = "center"

        # Margins & Indents
        ml = pt(styles.get("margin-left") or styles.get("padding-left"))
        if ml is not None:
            new_p_pr.ind.left = ml
        mr = pt(styles.get("margin-right") or styles.get("padding-right"))
        if mr is not None:
            new_p_pr.ind.right = mr
        ti = pt(styles.get("text-indent"))
        if ti is not None:
            new_p_pr.ind.first_line = ti
        mt = pt(styles.get("margin-top"))
        if mt is not None:
            new_p_pr.sp.space_before = mt
        mb = pt(styles.get("margin-bottom"))
        if mb is not None:
            new_p_pr.sp.space_after = mb

        # Heading style
        if re.match(r"^H[1-6]$", u_tag):
            lvl = u_tag[1]
            new_p_pr.style_id = f"Heading {lvl}"

        # List context
        if u_tag == "LI" and self.list_stack:
            cur_list = self.list_stack[-1]
            new_p_pr.num_id = cur_list["id"]
            new_p_pr.num_level = cur_list["lvl"]

        self.p_pr_stack.append(new_p_pr)

        # 2. Update Run Properties for inline elements
        new_r_pr = RunProperties()
        prev_r_pr = self.current_r_pr
        new_r_pr.bold = prev_r_pr.bold
        new_r_pr.italic = prev_r_pr.italic
        new_r_pr.underline = prev_r_pr.underline
        new_r_pr.strike = prev_r_pr.strike
        new_r_pr.vert_align = prev_r_pr.vert_align
        new_r_pr.font_family = prev_r_pr.font_family
        new_r_pr.font_size = prev_r_pr.font_size
        new_r_pr.color = prev_r_pr.color
        new_r_pr.highlight = prev_r_pr.highlight

        if u_tag in {"B", "STRONG"} or re.match(r"^H[1-6]$", u_tag):
            new_r_pr.bold = True
        if u_tag in {"I", "EM", "CITE", "DFN", "VAR"}:
            new_r_pr.italic = True
        if u_tag in {"U", "INS"}:
            new_r_pr.underline = "single"
        if u_tag in {"S", "STRIKE", "DEL"}:
            new_r_pr.strike = True
        if u_tag == "SUP":
            new_r_pr.vert_align = "superscript"
        if u_tag == "SUB":
            new_r_pr.vert_align = "subscript"
        if u_tag in {"CODE", "TT", "KBD", "SAMP", "PRE"}:
            new_r_pr.font_family = "Courier New"
        if u_tag == "MARK":
            new_r_pr.highlight = "yellow"
        if u_tag == "FONT":
            if attrs_dict.get("face"):
                new_r_pr.font_family = attrs_dict["face"].split(",")[0].strip("\"' ")
            if attrs_dict.get("size"):
                try:
                    s_idx = int(attrs_dict["size"])
                    if 1 <= s_idx <= 7:
                        new_r_pr.font_size = FONT_SIZE_ATTR[s_idx]
                except ValueError:
                    pass
            if attrs_dict.get("color"):
                c = parse_color(attrs_dict["color"])
                if c:
                    new_r_pr.color = c

        # Apply CSS styles
        if "font-family" in styles:
            fam = styles["font-family"].split(",")[0].strip("\"' ")
            generic_fonts = {"inherit", "initial", "serif", "sans-serif", "monospace"}
            if fam and fam.lower() not in generic_fonts:
                new_r_pr.font_family = fam

        if "font-size" in styles:
            sz_str = styles["font-size"]
            if sz_str in SIZE_KEYWORDS:
                new_r_pr.font_size = SIZE_KEYWORDS[sz_str]
            else:
                sz_val = pt(sz_str, prev_r_pr.font_size or 12.0)
                if sz_val:
                    new_r_pr.font_size = round(sz_val, 1)

        if "font-weight" in styles:
            w = styles["font-weight"]
            if w in {"bold", "bolder"}:
                new_r_pr.bold = True
            elif w in {"normal", "lighter"}:
                new_r_pr.bold = False
            else:
                try:
                    new_r_pr.bold = int(w) >= 600
                except ValueError:
                    pass

        if "font-style" in styles:
            new_r_pr.italic = "italic" in styles["font-style"] or "oblique" in styles["font-style"]

        if "text-decoration" in styles or "text-decoration-line" in styles:
            td = styles.get("text-decoration", "") + styles.get("text-decoration-line", "")
            if "underline" in td:
                new_r_pr.underline = "single"
            elif "none" in td:
                new_r_pr.underline = None
            if "line-through" in td:
                new_r_pr.strike = True

        if "color" in styles:
            c = parse_color(styles["color"])
            if c:
                new_r_pr.color = c

        bg = styles.get("background-color") or styles.get("background")
        if bg and u_tag not in {"P", "DIV", "TD", "TH", "BODY"}:
            c = parse_color(bg.split()[0])
            if c:
                new_r_pr.highlight = c

        if "vertical-align" in styles:
            va = styles["vertical-align"]
            if va == "super":
                new_r_pr.vert_align = "superscript"
            elif va == "sub":
                new_r_pr.vert_align = "subscript"
            elif va == "baseline":
                new_r_pr.vert_align = None

        # Link stack
        if u_tag == "A" and attrs_dict.get("href"):
            href = attrs_dict["href"]
            link_obj = {"anchor": href[1:]} if href.startswith("#") else {"url": href}
            self.link_stack.append(link_obj)
            new_r_pr.link = link_obj
            new_r_pr.underline = "single"
            if not new_r_pr.color:
                new_r_pr.color = "0000FF"
        elif self.link_stack:
            new_r_pr.link = self.link_stack[-1]

        self.r_pr_stack.append(new_r_pr)

        # 3. Handle Structural & Tag-Specific Actions
        if u_tag in BLOCK_TAGS:
            self._flush_para()
            self._ensure_para()

        elif u_tag == "PRE":
            self._flush_para()
            self.in_pre = True
            self._ensure_para()

        elif u_tag == "BR":
            p = self._ensure_para()
            p.runs.append(BreakItem(break_type="line", r_pr=self.current_r_pr))

        elif u_tag == "HR":
            self._flush_para()
            hr_p = Paragraph(
                runs=[],
                p_pr=ParagraphProperties(
                    borders={"bottom": {"val": "single", "sz": 1.5, "color": "auto", "space": 1}}
                ),
            )
            self.target_blocks.append(hr_p)
            self._flush_para()

        elif u_tag in {"UL", "OL"}:
            self._flush_para()
            self.list_counter += 1
            lvl = len(self.list_stack)
            self.list_stack.append(
                {
                    "kind": u_tag.lower(),
                    "type": attrs_dict.get("type", "1"),
                    "id": self.list_counter,
                    "lvl": lvl,
                }
            )

        elif u_tag == "TABLE":
            self._flush_para()
            new_tbl = Table()
            self.table_stack.append(new_tbl)
            self.current_rows = []
            self.cell_grid_widths = []

        elif u_tag == "TR":
            self.current_row = Row()
            self.current_rows.append(self.current_row)

        elif u_tag in {"TD", "TH"}:
            tc_pr = CellProperties()
            span = max(1, int(attrs_dict.get("colspan", "1") or "1"))
            rowspan = max(1, int(attrs_dict.get("rowspan", "1") or "1"))
            if span > 1:
                tc_pr.span = span
            if rowspan > 1:
                tc_pr.v_merge = "restart"

            bg_raw = (
                attrs_dict.get("bgcolor")
                or styles.get("background-color")
                or styles.get("background")
            )
            bg_c = parse_color(bg_raw)
            if bg_c and bg_c != "FFFFFF":
                tc_pr.shd = ShadingProperties(val="clear", fill=bg_c, color="auto")

            va = styles.get("vertical-align") or attrs_dict.get("valign")
            if va in {"middle", "center"}:
                tc_pr.v_align = "center"
            elif va == "bottom":
                tc_pr.v_align = "bottom"

            w = pt(styles.get("width") or attrs_dict.get("width"))
            if w:
                self.cell_grid_widths.append(w)

            cell = Cell(tc_pr=tc_pr, blocks=[])
            if self.current_row:
                self.current_row.cells.append(cell)
            self.current_cell = cell
            # Redirect paragraph target blocks into cell
            self.target_blocks = cell.blocks
            self._flush_para()

        elif u_tag == "IMG":
            src = attrs_dict.get("src", "")
            alt = attrs_dict.get("alt", "")
            w = pt(styles.get("width") or attrs_dict.get("width")) or 72.0
            h = pt(styles.get("height") or attrs_dict.get("height")) or 72.0

            pic = PictureItem(
                width=w,
                height=h,
                alt_text=alt,
                image_part=src,
                r_pr=self.current_r_pr,
            )
            p = self._ensure_para()
            p.runs.append(pic)

    def handle_endtag(self, tag: str) -> None:
        u_tag = tag.upper()

        if u_tag in SKIP_TAGS:
            if u_tag not in VOID_TAGS and self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return

        if u_tag == "TITLE":
            self.in_title = False
            return

        if len(self.p_pr_stack) > 1:
            self.p_pr_stack.pop()
        if len(self.r_pr_stack) > 1:
            self.r_pr_stack.pop()

        if u_tag == "A" and self.link_stack:
            self.link_stack.pop()

        if u_tag == "PRE":
            self.in_pre = False
            self._flush_para()

        elif u_tag in BLOCK_TAGS:
            self._flush_para()

        elif u_tag in {"UL", "OL"}:
            if self.list_stack:
                self.list_stack.pop()
            self._flush_para()

        elif u_tag in {"TD", "TH"}:
            # Ensure cell has at least one paragraph
            if self.current_cell and not self.current_cell.blocks:
                self.current_cell.blocks.append(Paragraph())
            self.current_cell = None
            self._flush_para()

        elif u_tag == "TR":
            self.current_row = None

        elif u_tag == "TABLE":
            if self.table_stack:
                tbl = self.table_stack.pop()
                tbl.rows = self.current_rows

                # Calculate grid
                num_cols = max((len(r.cells) for r in tbl.rows), default=1)
                grid: list[float] = []
                avail = 432.0  # 6 inches default available width
                if self.cell_grid_widths and len(self.cell_grid_widths) >= num_cols:
                    grid = self.cell_grid_widths[:num_cols]
                else:
                    grid = [round(avail / num_cols, 2)] * num_cols
                tbl.grid = grid

                # Restore target_blocks
                if self.table_stack:
                    pass  # nested table
                else:
                    self.target_blocks = self.doc.main.blocks
                self.target_blocks.append(tbl)
                self._flush_para()

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        if self.in_title:
            self.doc_title += data
            return

        text = data
        if not self.in_pre:
            text = re.sub(r"[\r\n\t ]+", " ", text)
            if not text or text == " ":
                if not self.cur_p or not self.cur_p.runs:
                    return

        p = self._ensure_para()
        p.runs.append(TextItem(text=text, r_pr=self.current_r_pr))


# ---------------------------------------------------------------------------
# HTML Reader API
# ---------------------------------------------------------------------------


class HtmlReader:
    """Reader converting HTML source strings or files into Quire Document DOM."""

    def read(self, src: str | bytes | Path) -> Document:
        """Parse HTML source into a Quire Document."""
        if isinstance(src, Path):
            src_text = src.read_text(encoding="utf-8", errors="replace")
        elif isinstance(src, bytes):
            src_text = src.decode("utf-8", errors="replace")
        else:
            src_text = str(src or "")

        doc = Document()
        doc.main = Story(kind="main", blocks=[])

        if not src_text.strip():
            doc.main.blocks.append(Paragraph())
            return doc

        parser = _HtmlDomParser(doc)
        parser.feed(src_text)
        parser.close()

        if parser.doc_title:
            doc.props["title"] = parser.doc_title.strip()

        # Clean empty blocks
        if not doc.main.blocks:
            doc.main.blocks.append(Paragraph())

        return doc


def read_html(src: str | bytes | Path) -> Document:
    """Convenience helper to read HTML into a Quire Document."""
    return HtmlReader().read(src)


# ---------------------------------------------------------------------------
# HTML Writer API (Export Engine)
# ---------------------------------------------------------------------------


class HtmlWriter:
    """Writer serializing Quire Document DOM into clean, semantic HTML5."""

    def write(self, doc: Document, standalone: bool = True) -> str:
        """Serialize document to HTML5 string."""
        title = doc.props.get("title") or "Document"
        body_html = self.blocks_to_html(doc.main.blocks)

        if not standalone:
            return f"<meta charset=\"utf-8\"><div>{body_html}</div>"

        return (
            "<!DOCTYPE html>\n"
            "<html lang=\"zh-CN\">\n"
            "<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"generator\" content=\"Quire\">\n"
            f"<title>{html.escape(title)}</title>\n"
            "<style>\n"
            "body { font-family: 'Times New Roman', serif; font-size: 12pt; "
            "margin: 1in; line-height: 1.25; }\n"
            "p, h1, h2, h3, h4, h5, h6, li { margin-top: 0; margin-bottom: 4pt; }\n"
            "table { border-collapse: collapse; margin: 6pt 0; }\n"
            "td, th { padding: 4pt 6pt; border: 1px solid #C0C0C0; }\n"
            "a { color: #0000FF; text-decoration: underline; }\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"{body_html}\n"
            "</body>\n"
            "</html>\n"
        )

    def blocks_to_html(self, blocks: list[Paragraph | Table]) -> str:
        """Render a list of paragraph and table blocks to HTML string."""
        buf: list[str] = []
        in_list_kind: str | None = None
        list_level: int = 0

        def close_list() -> None:
            nonlocal in_list_kind, list_level
            while list_level > 0:
                buf.append(f"</{in_list_kind or 'ul'}>")
                list_level -= 1
            in_list_kind = None

        for b in blocks:
            if isinstance(b, Table):
                close_list()
                buf.append(self._table_to_html(b))
            elif isinstance(b, Paragraph):
                # Check if it's a list paragraph
                if b.p_pr.num_id is not None:
                    target_level = (b.p_pr.num_level or 0) + 1
                    kind = "ul"
                    if in_list_kind != kind:
                        close_list()
                        in_list_kind = kind

                    while list_level < target_level:
                        buf.append(f"<{kind}>")
                        list_level += 1
                    while list_level > target_level:
                        buf.append(f"</{kind}>")
                        list_level -= 1

                    buf.append(f"<li>{self._paragraph_inner_html(b)}</li>")
                else:
                    close_list()
                    buf.append(self._paragraph_to_html(b))

        close_list()
        return "\n".join(buf)

    def _paragraph_to_html(self, p: Paragraph) -> str:
        style_id = (p.p_pr.style_id or "").lower()
        tag = "p"
        if style_id.startswith("heading"):
            m = re.search(r"\d", style_id)
            if m:
                tag = f"h{m.group(0)}"

        styles: list[str] = []
        if p.p_pr.jc:
            jc_map = {"both": "justify", "center": "center", "right": "right"}
            if p.p_pr.jc in jc_map:
                styles.append(f"text-align:{jc_map[p.p_pr.jc]}")
        if p.p_pr.ind.left:
            styles.append(f"margin-left:{p.p_pr.ind.left:.1f}pt")
        if p.p_pr.ind.right:
            styles.append(f"margin-right:{p.p_pr.ind.right:.1f}pt")
        if p.p_pr.ind.first_line:
            styles.append(f"text-indent:{p.p_pr.ind.first_line:.1f}pt")
        if p.p_pr.sp.space_before:
            styles.append(f"margin-top:{p.p_pr.sp.space_before:.1f}pt")
        if p.p_pr.sp.space_after:
            styles.append(f"margin-bottom:{p.p_pr.sp.space_after:.1f}pt")

        style_attr = f' style="{";".join(styles)}"' if styles else ""
        inner = self._paragraph_inner_html(p)
        return f"<{tag}{style_attr}>{inner or '&nbsp;'}</{tag}>"

    def _paragraph_inner_html(self, p: Paragraph) -> str:
        buf: list[str] = []
        open_link: str | None = None

        for r in p.runs:
            # Check link
            link_href: str | None = None
            if r.r_pr and r.r_pr.link:
                if "url" in r.r_pr.link:
                    link_href = r.r_pr.link["url"]
                elif "anchor" in r.r_pr.link:
                    link_href = f"#{r.r_pr.link['anchor']}"

            if link_href != open_link:
                if open_link is not None:
                    buf.append("</a>")
                if link_href is not None:
                    buf.append(f'<a href="{html.escape(link_href)}">')
                open_link = link_href

            piece = ""
            if isinstance(r, TextItem):
                piece = html.escape(r.text)
            elif isinstance(r, TabItem):
                piece = "&emsp;"
            elif isinstance(r, BreakItem):
                piece = "<br>"
            elif isinstance(r, SymbolItem):
                piece = html.escape(r.char or "")
            elif isinstance(r, PictureItem) or getattr(r, "t", "") in {"img", "picture"}:
                src = getattr(r, "image_part", "") or ""
                alt = html.escape(getattr(r, "alt_text", "") or "")
                w = getattr(r, "width", 72.0)
                h = getattr(r, "height", 72.0)
                img_src = html.escape(src)
                piece = f'<img src="{img_src}" width="{w:.1f}" height="{h:.1f}" alt="{alt}">'

            if not piece:
                continue

            # Run styles
            st: list[str] = []
            if r.r_pr.font_family:
                st.append(f"font-family:'{r.r_pr.font_family}'")
            if r.r_pr.font_size:
                st.append(f"font-size:{r.r_pr.font_size:.1f}pt")
            if r.r_pr.color and r.r_pr.color.lower() != "auto":
                st.append(f"color:#{r.r_pr.color}")
            if r.r_pr.highlight:
                st.append(f"background:#{r.r_pr.highlight}")

            styled_piece = piece
            if r.r_pr.bold:
                styled_piece = f"<b>{styled_piece}</b>"
            if r.r_pr.italic:
                styled_piece = f"<i>{styled_piece}</i>"
            if r.r_pr.underline:
                styled_piece = f"<u>{styled_piece}</u>"
            if r.r_pr.strike:
                styled_piece = f"<s>{styled_piece}</s>"
            if r.r_pr.vert_align == "superscript":
                styled_piece = f"<sup>{styled_piece}</sup>"
            elif r.r_pr.vert_align == "subscript":
                styled_piece = f"<sub>{styled_piece}</sub>"

            if st:
                buf.append(f'<span style="{";".join(st)}">{styled_piece}</span>')
            else:
                buf.append(styled_piece)

        if open_link is not None:
            buf.append("</a>")

        return "".join(buf)

    def _table_to_html(self, t: Table) -> str:
        s = ["<table style=\"border-collapse:collapse;width:100%\">"]
        for row in t.rows:
            s.append("  <tr>")
            for cell in row.cells:
                attrs: list[str] = []
                styles: list[str] = ["padding:4pt 6pt", "border:1px solid #C0C0C0"]
                if cell.tc_pr.span > 1:
                    attrs.append(f'colspan="{cell.tc_pr.span}"')
                if cell.tc_pr.shd and cell.tc_pr.shd.get("fill"):
                    fill = cell.tc_pr.shd["fill"]
                    styles.append(f"background-color:#{fill}")
                if cell.tc_pr.v_align:
                    styles.append(f"vertical-align:{cell.tc_pr.v_align}")

                attrs.append(f'style="{";".join(styles)}"')
                cell_inner = self.blocks_to_html(cell.blocks)
                s.append(f"    <td {' '.join(attrs)}>{cell_inner}</td>")
            s.append("  </tr>")
        s.append("</table>")
        return "\n".join(s)


def write_html(doc: Document, path: str | Path | None = None) -> str:
    """Convenience helper to write a Quire Document to HTML string and optional file."""
    res = HtmlWriter().write(doc)
    if path is not None:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(res, encoding="utf-8")
    return res


def web_page(doc: Document, title: str | None = None) -> str:
    """Export document as standalone HTML5 Web Page."""
    if title:
        doc.props["title"] = title
    return HtmlWriter().write(doc, standalone=True)
