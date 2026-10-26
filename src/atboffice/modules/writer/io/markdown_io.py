"""GitHub Flavored Markdown (GFM) Reader, Writer, and ZIP Package handler for Quire."""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from atboffice.modules.writer.models.document import (
    Cell,
    Document,
    Paragraph,
    Row,
    Story,
    Table,
    TextItem,
    ptext,
)
from atboffice.modules.writer.models.properties import (
    CellProperties,
    RunProperties,
)

# Alerts configuration mapping alert names to title and theme color
ALERTS: dict[str, tuple[str, str]] = {
    "note": ("Note", "0969DA"),
    "tip": ("Tip", "1A7F37"),
    "important": ("Important", "8250DF"),
    "warning": ("Warning", "9A6700"),
    "caution": ("Caution", "CF222E"),
}


class MarkdownReader:
    """Reader converting GitHub Flavored Markdown into Quire Document DOM."""

    def __init__(self, resolve_image: Callable[[str], bytes | None] | None = None) -> None:
        self.resolve_image = resolve_image

    def read(self, src: str | bytes) -> Document:
        """Parse Markdown source string or bytes into a Document."""
        if isinstance(src, bytes):
            src = src.decode("utf-8", errors="replace")

        text = str(src or "")
        if text.startswith("\ufeff"):
            text = text[1:]
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        doc = Document()
        doc.main = Story(kind="main", blocks=[])

        if not text.strip():
            doc.main.blocks.append(Paragraph())
            return doc

        # Check and extract YAML Front Matter
        fm_match = re.match(r"^---[ \t]*\n(.*?)\n(?:---|\.\.\.)[ \t]*(?:\n|$)", text, re.DOTALL)
        if fm_match:
            doc.props["front_matter"] = fm_match.group(1)
            text = text[fm_match.end() :]

        lines = text.split("\n")
        blocks = self._parse_blocks(lines)
        if not blocks:
            blocks = [Paragraph()]

        doc.main.blocks = blocks
        return doc

    def _parse_blocks(self, lines: list[str]) -> list[Paragraph | Table]:
        blocks: list[Paragraph | Table] = []
        i = 0
        n = len(lines)

        delim_pattern = r"^[ \t]*\|?([ \t]*:?-+:?[ \t]*\|)+([ \t]*:?-+:?[ \t]*)?$"
        list_pattern = r"^[ \t]*([-*+]|\d+\.)[ \t]+"

        while i < n:
            line = lines[i]

            # 1. Blank lines
            if not line.strip():
                i += 1
                continue

            # 2. Fenced code block
            fenced_match = re.match(r"^[ \t]*(```+|~~~+)(.*)$", line)
            if fenced_match:
                fence = fenced_match.group(1)
                info = fenced_match.group(2).strip()
                code_lines: list[str] = []
                i += 1
                while i < n:
                    if lines[i].strip().startswith(fence[:3]):
                        i += 1
                        break
                    code_lines.append(lines[i])
                    i += 1

                for cl in code_lines:
                    p = Paragraph()
                    p.p_pr.style = "HTMLPreformatted"
                    setattr(p.p_pr, "md_info", info)
                    p.runs.append(TextItem(cl, RunProperties(font="Courier New", sz=10.0)))
                    blocks.append(p)
                continue

            # 3. ATX Headings: # Heading
            heading_match = re.match(r"^[ \t]*(#{1,6})[ \t]+(.*)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                content = heading_match.group(2).strip()
                content = re.sub(r"[ \t]+#+[ \t]*$", "", content)
                p = Paragraph()
                p.p_pr.style = f"Heading{level}"
                p.runs = self._parse_inlines(content)
                blocks.append(p)
                i += 1
                continue

            # 4. Thematic break: ---, ***, ___
            if re.match(r"^[ \t]*([*_-][ \t]*){3,}$", line):
                p = Paragraph()
                p.p_pr.borders = {"bottom": {"val": "single", "sz": 1.5, "color": "D0D7DE"}}
                blocks.append(p)
                i += 1
                continue

            # 5. Pipe Table: check if current line looks like table and next is delimiter
            if "|" in line and i + 1 < n and re.match(delim_pattern, lines[i + 1]):
                table_lines = [line]
                i += 1
                while i < n and "|" in lines[i] and lines[i].strip():
                    table_lines.append(lines[i])
                    i += 1
                tbl = self._parse_table(table_lines)
                if tbl:
                    blocks.append(tbl)
                continue

            # 6. Blockquote & Alerts
            if line.strip().startswith(">"):
                quote_lines = [line]
                i += 1
                while i < n and (
                    lines[i].strip().startswith(">")
                    or (lines[i].strip() and not self._is_block_start(lines[i]))
                ):
                    quote_lines.append(lines[i])
                    i += 1
                quote_blocks = self._parse_blockquote(quote_lines)
                blocks.extend(quote_blocks)
                continue

            # 7. Lists (Unordered, Ordered, Task Lists)
            list_match = re.match(list_pattern, line)
            if list_match:
                list_lines = [line]
                i += 1
                while i < n:
                    if not lines[i].strip():
                        if i + 1 < n and (
                            re.match(list_pattern, lines[i + 1])
                            or lines[i + 1].startswith("    ")
                            or lines[i + 1].startswith("\t")
                        ):
                            list_lines.append(lines[i])
                            i += 1
                            continue
                        break
                    list_lines.append(lines[i])
                    i += 1
                list_blocks = self._parse_list(list_lines)
                blocks.extend(list_blocks)
                continue

            # 8. Regular paragraph
            para_lines = [line]
            i += 1
            while i < n and lines[i].strip() and not self._is_block_start(lines[i]):
                para_lines.append(lines[i])
                i += 1
            p = Paragraph()
            p.runs = self._parse_inlines(" ".join(para_lines))
            blocks.append(p)

        return blocks

    def _is_block_start(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return True
        if re.match(r"^(#{1,6}[ \t]|```|~~~|>|([-*+]|\d+\.)[ \t]|\|)", s):
            return True
        if re.match(r"^([*_-][ \t]*){3,}$", s):
            return True
        return False

    def _parse_table(self, lines: list[str]) -> Table | None:
        if len(lines) < 2:
            return None

        def split_row(row_str: str) -> list[str]:
            raw = row_str.strip()
            if raw.startswith("|"):
                raw = raw[1:]
            if raw.endswith("|"):
                raw = raw[:-1]
            return [c.strip() for c in raw.split("|")]

        header_cells = split_row(lines[0])
        delims = split_row(lines[1])
        num_cols = max(len(header_cells), len(delims))

        alignments: list[str] = []
        for d in delims:
            d = d.strip()
            if d.startswith(":") and d.endswith(":"):
                alignments.append("center")
            elif d.endswith(":"):
                alignments.append("right")
            elif d.startswith(":"):
                alignments.append("left")
            else:
                alignments.append("left")

        while len(alignments) < num_cols:
            alignments.append("left")

        tbl = Table()
        tbl.tbl_pr.style = "MarkdownTable"
        tbl.grid = [120.0] * num_cols

        # Header Row
        h_row = Row()
        h_row.tr_pr.header = True
        for col_idx in range(num_cols):
            text = header_cells[col_idx] if col_idx < len(header_cells) else ""
            align = alignments[col_idx]
            p = Paragraph()
            p.p_pr.jc = align
            p.runs = self._parse_inlines(text)
            for r in p.runs:
                r.r_pr.b = True
            c = Cell(blocks=[p], tc_pr=CellProperties(w=tbl.grid[col_idx]))
            h_row.cells.append(c)
        tbl.rows.append(h_row)

        # Data Rows
        for r_line in lines[2:]:
            cells_data = split_row(r_line)
            d_row = Row()
            for col_idx in range(num_cols):
                text = cells_data[col_idx] if col_idx < len(cells_data) else ""
                align = alignments[col_idx]
                p = Paragraph()
                p.p_pr.jc = align
                p.runs = self._parse_inlines(text)
                c = Cell(blocks=[p], tc_pr=CellProperties(w=tbl.grid[col_idx]))
                d_row.cells.append(c)
            tbl.rows.append(d_row)

        return tbl

    def _parse_blockquote(self, lines: list[str]) -> list[Paragraph]:
        cleaned: list[str] = []
        alert_type: str | None = None
        alert_regex = r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*$"

        for idx, line in enumerate(lines):
            stripped = re.sub(r"^[ \t]*>[ \t]?", "", line)
            if idx == 0:
                alert_m = re.match(alert_regex, stripped, re.IGNORECASE)
                if alert_m:
                    alert_type = alert_m.group(1).lower()
                    continue
            cleaned.append(stripped)

        raw_text = "\n".join(cleaned).strip()
        sub_lines = raw_text.split("\n")
        out_blocks: list[Paragraph] = []

        for sl in sub_lines:
            if not sl.strip():
                continue
            p = Paragraph()
            p.p_pr.style = "Quote"
            if alert_type:
                setattr(p.p_pr, "md_alert", alert_type)
                color = ALERTS.get(alert_type, ("Note", "0969DA"))[1]
                p.p_pr.borders = {"left": {"val": "single", "sz": 3.0, "color": color}}
            else:
                p.p_pr.borders = {"left": {"val": "single", "sz": 2.0, "color": "D0D7DE"}}
            p.runs = self._parse_inlines(sl)
            out_blocks.append(p)

        return out_blocks

    def _parse_list(self, lines: list[str]) -> list[Paragraph]:
        blocks: list[Paragraph] = []
        for line in lines:
            if not line.strip():
                continue
            m = re.match(r"^[ \t]*([-*+]|\d+\.)[ \t]+(.*)$", line)
            if not m:
                if blocks:
                    p = blocks[-1]
                    p.runs.append(TextItem(" "))
                    p.runs.extend(self._parse_inlines(line.strip()))
                continue

            content = m.group(2).strip()
            p = Paragraph()
            p.p_pr.style = "ListParagraph"

            task_m = re.match(r"^\[([ xX])\][ \t]+(.*)$", content)
            if task_m:
                checked = task_m.group(1).lower() == "x"
                content = task_m.group(2)
                setattr(p.p_pr, "md_task", checked)
                box_str = "☒ " if checked else "☐ "
                p.runs.append(TextItem(box_str, RunProperties(font="Arial")))

            p.runs.extend(self._parse_inlines(content))
            blocks.append(p)

        return blocks

    def _parse_inlines(self, text: str) -> list[TextItem]:
        runs: list[TextItem] = []
        pos = 0
        n = len(text)

        token_re = re.compile(
            r"(\*\*\*(.*?)\*\*\*|"
            r"\*\*(.*?)\*\*|"
            r"__(.*?)__|"
            r"\*(.*?)\*|"
            r"_(.*?)_|"
            r"~~(.*?)~~|"
            r"`(.*?)`|"
            r"!\[(.*?)\]\((.*?)\)|"
            r"\[(.*?)\]\((.*?)\))",
            re.DOTALL,
        )

        for match in token_re.finditer(text):
            start, end = match.span()
            if start > pos:
                plain = text[pos:start]
                runs.append(TextItem(plain))

            matched = match.group(0)
            if matched.startswith("***") and matched.endswith("***"):
                inner = match.group(2)
                runs.append(TextItem(inner, RunProperties(b=True, i=True)))
            elif matched.startswith("**") and matched.endswith("**"):
                inner = match.group(3)
                runs.append(TextItem(inner, RunProperties(b=True)))
            elif matched.startswith("__") and matched.endswith("__"):
                inner = match.group(4)
                runs.append(TextItem(inner, RunProperties(b=True)))
            elif matched.startswith("*") and matched.endswith("*"):
                inner = match.group(5)
                runs.append(TextItem(inner, RunProperties(i=True)))
            elif matched.startswith("_") and matched.endswith("_"):
                inner = match.group(6)
                runs.append(TextItem(inner, RunProperties(i=True)))
            elif matched.startswith("~~") and matched.endswith("~~"):
                inner = match.group(7)
                runs.append(TextItem(inner, RunProperties(strike=True)))
            elif matched.startswith("`") and matched.endswith("`"):
                inner = match.group(8)
                runs.append(
                    TextItem(inner, RunProperties(font="Courier New", sz=10.0, style="HTMLCode"))
                )
            elif matched.startswith("!["):
                alt = match.group(9)
                url = match.group(10)
                item = TextItem(f"[{alt}]", RunProperties(color="59636E"))
                setattr(item, "image_url", url)
                setattr(item, "image_alt", alt)
                runs.append(item)
            elif matched.startswith("["):
                link_text = match.group(11)
                url = match.group(12)
                item = TextItem(
                    link_text, RunProperties(color="0969DA", u="single", style="Hyperlink")
                )
                item.r_pr.link = {"url": url}
                runs.append(item)

            pos = end

        if pos < n:
            runs.append(TextItem(text[pos:]))

        return runs


class MarkdownWriter:
    """Writer serializing Quire Document DOM to GitHub Flavored Markdown and extracted images."""

    def write(self, doc: Document, keep_raw: bool = True) -> tuple[str, list[tuple[str, bytes]]]:
        """Convert document to Markdown text and list of (image_filename, bytes)."""
        out_lines: list[str] = []
        images: list[tuple[str, bytes]] = []

        front = doc.props.get("front_matter")
        if front:
            out_lines.append(f"---\n{front.strip()}\n---")

        blocks = doc.main.blocks
        i = 0
        n = len(blocks)

        while i < n:
            b = blocks[i]

            if isinstance(b, Table):
                out_lines.append(self._write_table(b))
                i += 1
                continue

            if isinstance(b, Paragraph):
                style = b.p_pr.style or ""
                # Code block: collect consecutive HTMLPreformatted paragraphs
                if style == "HTMLPreformatted":
                    code_lines: list[str] = []
                    info = getattr(b.p_pr, "md_info", "") or ""
                    while (
                        i < n
                        and isinstance(blocks[i], Paragraph)
                        and blocks[i].p_pr.style == "HTMLPreformatted"
                    ):
                        code_lines.append(ptext(blocks[i]))
                        i += 1
                    fence = "```" + info
                    out_lines.append(f"{fence}\n" + "\n".join(code_lines) + "\n```")
                    continue

                # Headings
                if style.startswith("Heading") and len(style) == 8 and style[7].isdigit():
                    level = int(style[7])
                    hashes = "#" * max(1, min(6, level))
                    txt = self._write_inlines(b.runs)
                    out_lines.append(f"{hashes} {txt}")
                    i += 1
                    continue

                # Blockquotes and alerts
                alert = getattr(b.p_pr, "md_alert", None)
                if alert:
                    alert_upper = alert.upper()
                    txt = self._write_inlines(b.runs)
                    out_lines.append(f"> [!{alert_upper}]\n> {txt}")
                    i += 1
                    continue
                elif style == "Quote":
                    txt = self._write_inlines(b.runs)
                    out_lines.append(f"> {txt}")
                    i += 1
                    continue

                # Task lists and bullet lists
                is_task = hasattr(b.p_pr, "md_task")
                if is_task:
                    checked = getattr(b.p_pr, "md_task")
                    box = "[x]" if checked else "[ ]"
                    txt = self._write_inlines(b.runs, skip_box=True)
                    out_lines.append(f"- {box} {txt.strip()}")
                    i += 1
                    continue

                if style == "ListParagraph":
                    txt = self._write_inlines(b.runs)
                    out_lines.append(f"- {txt.strip()}")
                    i += 1
                    continue

                # Regular paragraph
                txt = self._write_inlines(b.runs)
                if txt.strip():
                    out_lines.append(txt)
                i += 1
                continue

            i += 1

        md_text = "\n\n".join(out_lines).strip() + "\n"
        return md_text, images

    def _write_table(self, tbl: Table) -> str:
        lines: list[str] = []
        if not tbl.rows:
            return ""

        # Header row
        header_row = tbl.rows[0]
        h_cols = [ptext(c.blocks[0]).strip() if c.blocks else "" for c in header_row.cells]
        lines.append("| " + " | ".join(h_cols) + " |")

        # Delimiter row
        delims: list[str] = []
        for c in header_row.cells:
            jc = c.blocks[0].p_pr.jc if c.blocks else "left"
            if jc == "center":
                delims.append(":---:")
            elif jc == "right":
                delims.append("---:")
            else:
                delims.append("---")
        lines.append("| " + " | ".join(delims) + " |")

        # Data rows
        for row in tbl.rows[1:]:
            cols = [ptext(c.blocks[0]).strip() if c.blocks else "" for c in row.cells]
            lines.append("| " + " | ".join(cols) + " |")

        return "\n".join(lines)

    def _write_inlines(self, runs: list[Any], skip_box: bool = False) -> str:
        parts: list[str] = []
        for r in runs:
            if not isinstance(r, TextItem):
                continue
            txt = r.text
            if skip_box and txt in {"☒ ", "☐ ", "[ ] ", "[x] ", "[X] "}:
                continue

            r_pr = r.r_pr
            link = getattr(r_pr, "link", None)
            is_code = r_pr.style == "HTMLCode" or r_pr.font == "Courier New"

            if is_code:
                txt = f"`{txt}`"
            else:
                if r_pr.b and r_pr.i:
                    txt = f"***{txt}***"
                elif r_pr.b:
                    txt = f"**{txt}**"
                elif r_pr.i:
                    txt = f"*{txt}*"
                if r_pr.strike:
                    txt = f"~~{txt}~~"

            if link and link.get("url"):
                url = link["url"]
                txt = f"[{txt}]({url})"

            parts.append(txt)

        return "".join(parts)


def read_markdown(
    src: str | bytes, resolve_image: Callable[[str], bytes | None] | None = None
) -> Document:
    """Read Markdown text or bytes and return a Quire Document."""
    reader = MarkdownReader(resolve_image=resolve_image)
    return reader.read(src)


def write_markdown(doc: Document, keep_raw: bool = True) -> tuple[str, list[tuple[str, bytes]]]:
    """Write Quire Document to Markdown text and list of images."""
    writer = MarkdownWriter()
    return writer.write(doc, keep_raw=keep_raw)


def read_markdown_zip(zip_source: str | Path | bytes | io.BytesIO) -> Document:
    """Read a .zip archive containing a markdown file and bundled images into a Document."""
    if isinstance(zip_source, (str, Path)):
        zf = zipfile.ZipFile(zip_source, "r")
    elif isinstance(zip_source, bytes):
        zf = zipfile.ZipFile(io.BytesIO(zip_source), "r")
    else:
        zf = zipfile.ZipFile(zip_source, "r")

    with zf:
        md_names = [
            name
            for name in zf.namelist()
            if name.lower().endswith(".md") and not name.startswith("__MACOSX")
        ]
        if not md_names:
            raise ValueError("No .md file found in the zip archive")

        md_file = md_names[0]
        for candidate in ["index.md", "README.md", "document.md"]:
            if candidate in md_names:
                md_file = candidate
                break

        md_bytes = zf.read(md_file)

        def resolve(img_path: str) -> bytes | None:
            clean = img_path.lstrip("./")
            if clean in zf.namelist():
                return zf.read(clean)
            return None

        return read_markdown(md_bytes, resolve_image=resolve)


def write_markdown_zip(doc: Document, main_filename: str = "document.md") -> bytes:
    """Export Quire Document to a zipped archive containing the markdown text and pictures."""
    md_text, images = write_markdown(doc)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(main_filename, md_text.encode("utf-8"))
        for path, data in images:
            zf.writestr(path, data)

    return buf.getvalue()
