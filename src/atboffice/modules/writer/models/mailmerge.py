"""Word 2003 / Quire Mail Merge engine, data models, and document generator.

Supports:
- Tabular data sources (.csv, .tsv, .txt, or typed in-memory address list).
- Standard Word recipient filtering (included/excluded) and column sorting.
- MERGEFIELD dynamic instruction parsing, alias matching, and formatting switches.
- Word classic address block and greeting line generation.
- Blank-line suppression for missing address data.
- Batch merging to a multi-section Document with nextPage breaks or PDF export.
"""

from __future__ import annotations

import copy
import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from atboffice.modules.writer.models.document import (
    Document,
    FieldBeginItem,
    FieldEndItem,
    FieldSeparateItem,
    Paragraph,
    RunItem,
    TextItem,
)
from atboffice.modules.writer.models.field import (
    apply_field_formatting,
    parse_field_instruction,
    update_fields,
)
from atboffice.modules.writer.models.properties import RunProperties

if TYPE_CHECKING:
    pass

# Standard 13 Word Address List fields
ADDRESS_FIELDS: list[str] = [
    "Title",
    "First Name",
    "Last Name",
    "Company Name",
    "Address Line 1",
    "Address Line 2",
    "City",
    "State",
    "ZIP Code",
    "Country",
    "Home Phone",
    "Work Phone",
    "E-mail Address",
]

# Field alias mapping for fuzzy matching
FIELD_ALIASES: dict[str, list[str]] = {
    "firstname": ["first", "fname", "givenname", "firstname", "first_name"],
    "lastname": ["last", "lname", "surname", "familyname", "lastname", "last_name"],
    "addressline1": ["address", "address1", "street", "addressline1", "address_line_1"],
    "addressline2": ["address2", "suite", "apt", "addressline2", "address_line_2"],
    "zipcode": ["zip", "postalcode", "postcode", "zipcode", "zip_code"],
    "state": ["province", "region", "state"],
    "city": ["city", "town"],
    "country": ["country", "nation"],
    "companyname": ["company", "organization", "org", "companyname", "company_name"],
    "title": ["salutation", "prefix", "title"],
    "emailaddress": ["email", "e-mail", "mail", "emailaddress", "email_address"],
    "homephone": ["phone", "home", "homephone", "home_phone"],
    "workphone": ["work", "officephone", "workphone", "work_phone"],
}


def norm_field_name(name: str) -> str:
    """Normalize field name for comparison (lowercased alphanumeric)."""
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


def parse_delimited(text: str) -> list[list[str]]:
    """Parse delimited text (CSV, TSV, semicolon-separated) with robust dialect detection."""
    if not text:
        return []

    # Strip UTF-8 BOM if present
    text = text.lstrip("\ufeff")

    # Determine delimiter from the first non-empty line
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    first_line = lines[0]
    tab_count = first_line.count("\t")
    semi_count = first_line.count(";")
    comma_count = first_line.count(",")

    if tab_count > comma_count and tab_count >= semi_count:
        delim = "\t"
    elif semi_count > comma_count and semi_count > tab_count:
        delim = ";"
    else:
        delim = ","

    # Use Python csv reader with strict quotes handling
    reader = csv.reader(io.StringIO(text), delimiter=delim, skipinitialspace=True)
    rows: list[list[str]] = []
    for row in reader:
        # Filter out completely empty lines
        if any(cell.strip() for cell in row):
            rows.append([cell.strip() for cell in row])

    return rows


def load_data_source_from_csv(file_path: str | Path) -> MailMergeDataSource:
    """Read CSV/TSV file from disk and return a MailMergeDataSource."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Try utf-8 first, then gbk/latin-1 fallback
    content = ""
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            content = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    rows = parse_delimited(content)
    if not rows:
        raise ValueError("The data source contains no records.")

    fields = [
        col if col else f"Field{i + 1}"
        for i, col in enumerate(rows[0])
    ]
    data_rows = rows[1:]

    return MailMergeDataSource(
        name=path.name,
        fields=fields,
        rows=data_rows,
        included=set(range(len(data_rows))),
    )


@dataclass
class MailMergeDataSource:
    """Tabular data source containing merge fields and recipient records."""

    name: str = "Data Source"
    fields: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    included: set[int] = field(default_factory=set)
    is_typed: bool = False

    def __post_init__(self) -> None:
        if not self.included and self.rows:
            self.included = set(range(len(self.rows)))

    def active_records(self) -> list[int]:
        """Return indices of rows included in the merge, in current order."""
        return [i for i in range(len(self.rows)) if i in self.included]

    def find_field_index(self, name: str) -> int:
        """Find index of field matching name or its standard aliases."""
        k = norm_field_name(name)
        # 1. Exact match
        for i, f in enumerate(self.fields):
            if norm_field_name(f) == k:
                return i

        # 2. Alias lookup
        aliases = FIELD_ALIASES.get(k, [])
        for i, f in enumerate(self.fields):
            if norm_field_name(f) in aliases:
                return i

        # 3. Reverse alias lookup: does known key match an alias of name?
        for canonical, alias_list in FIELD_ALIASES.items():
            if k in alias_list:
                for i, f in enumerate(self.fields):
                    if norm_field_name(f) == canonical or norm_field_name(f) in alias_list:
                        return i

        # 4. Substring contains match
        for i, f in enumerate(self.fields):
            fn = norm_field_name(f)
            if k in fn or fn in k:
                return i

        return -1

    def get_value(self, record_index: int, field_name: str) -> str:
        """Retrieve formatted value for field_name at record_index."""
        if not (0 <= record_index < len(self.rows)):
            return ""
        row = self.rows[record_index]
        idx = self.find_field_index(field_name)
        if 0 <= idx < len(row):
            return str(row[idx])
        return ""

    def sort_by(self, column_index: int, descending: bool = False) -> None:
        """Sort rows by column value."""
        if not (0 <= column_index < len(self.fields)):
            return

        def _sort_key(item: tuple[int, list[str]]) -> tuple[int, Any]:
            val = item[1][column_index] if column_index < len(item[1]) else ""
            try:
                num = float(val)
                return (0, num)
            except ValueError:
                return (1, val.lower())

        indexed_rows = list(enumerate(self.rows))
        indexed_rows.sort(key=_sort_key, reverse=descending)

        # Remap included indices
        old_to_new = {old_idx: new_idx for new_idx, (old_idx, _) in enumerate(indexed_rows)}
        new_included = {old_to_new[i] for i in self.included if i in old_to_new}

        self.rows = [row for _, row in indexed_rows]
        self.included = new_included


class MailMergeEngine:
    """Evaluation engine, live preview coordinator, and batch document generator."""

    def __init__(
        self,
        data_source: MailMergeDataSource | None = None,
        doc_type: str = "letters",
    ) -> None:
        self.data_source: MailMergeDataSource | None = data_source
        self.current_record: int = 0
        self.preview: bool = False
        self.doc_type: str = doc_type  # letters, envelopes, labels, directory

    def set_data_source(self, ds: MailMergeDataSource) -> None:
        """Attach a new data source and reset record cursor."""
        self.data_source = ds
        self.current_record = 0

    def active_record_count(self) -> int:
        """Total number of active records."""
        if not self.data_source:
            return 0
        return len(self.data_source.active_records())

    def value(self, field_name: str, record_index: int | None = None) -> str:
        """Resolve value of a field for the given or current record."""
        if not self.data_source:
            return ""
        recs = self.data_source.active_records()
        if not recs:
            return ""

        if record_index is None:
            r_idx = recs[min(max(0, self.current_record), len(recs) - 1)]
        else:
            r_idx = recs[min(max(0, record_index), len(recs) - 1)]

        return self.data_source.get_value(r_idx, field_name)

    def evaluate_merge_instruction(
        self,
        instr: str,
        record_index: int | None = None,
    ) -> str:
        """Evaluate a field instruction (MERGEFIELD, MERGEREC, MERGESEQ)."""
        f = parse_field_instruction(instr)
        t = f.type.upper()

        if t in ("MERGEREC", "MERGESEQ"):
            rec_num = (self.current_record if record_index is None else record_index) + 1
            return str(rec_num)

        if t == "MERGEFIELD":
            field_name = f.args[0] if f.args else ""
            if not self.preview and record_index is None:
                # Design mode: render placeholder «FieldName»
                clean_name = field_name if field_name else "Field"
                return f"«{clean_name}»"

            val = self.value(field_name, record_index=record_index)

            # Switches: \b "prefix", \f "suffix"
            prefix = ""
            suffix = ""
            if val:
                b_sw = f.sw.get(r"\b")
                if isinstance(b_sw, str):
                    prefix = b_sw
                f_sw = f.sw.get(r"\f")
                if isinstance(f_sw, str):
                    suffix = f_sw

            result_text = f"{prefix}{val}{suffix}" if val else ""
            # Apply formatting switches (\* Upper, etc.)
            filtered_fmt = [fmt for fmt in f.fmt if "MERGEFORMAT" not in fmt.upper()]
            if filtered_fmt:
                result_text = apply_field_formatting(result_text, filtered_fmt)

            return result_text

        return ""

    def toggle_preview(self, doc: Document) -> bool:
        """Toggle preview mode on/off and refresh all fields in the document."""
        self.preview = not self.preview
        doc.mailmerge_engine = self  # type: ignore[attr-defined]
        update_fields(doc)
        return self.preview

    def go(self, doc: Document, record_index: int) -> int:
        """Navigate to specific record index and update document fields."""
        n = self.active_record_count()
        if n == 0:
            return 0
        self.current_record = min(max(0, record_index), n - 1)
        if not self.preview:
            self.preview = True
        doc.mailmerge_engine = self  # type: ignore[attr-defined]
        update_fields(doc)
        return self.current_record

    def step(self, doc: Document, delta: int) -> int:
        """Step record cursor by delta (-1 or +1)."""
        return self.go(doc, self.current_record + delta)

    def insert_field(
        self,
        p: Paragraph,
        offset: int,
        field_name: str,
        r_pr: RunProperties | None = None,
    ) -> None:
        """Insert a MERGEFIELD construct into a paragraph."""
        from atboffice.modules.writer.models.document import split_at

        safe_name = field_name.replace(" ", "_")
        instr = f"MERGEFIELD {safe_name}"
        cached = self.evaluate_merge_instruction(instr)

        idx = split_at(p, offset)
        items: list[RunItem] = [
            FieldBeginItem(field_type="MERGEFIELD", instr=instr, r_pr=r_pr),
            FieldSeparateItem(r_pr=r_pr),
            TextItem(text=cached, r_pr=r_pr),
            FieldEndItem(r_pr=r_pr),
        ]
        p.runs[idx:idx] = items

    def insert_greeting_line(
        self,
        p: Paragraph,
        offset: int,
        greeting: str = "Dear",
        salutation: str = ",",
        r_pr: RunProperties | None = None,
    ) -> None:
        """Insert standard Greeting Line (e.g. 'Dear «Title» «First_Name» «Last_Name»,')."""
        from atboffice.modules.writer.models.document import split_at

        idx = split_at(p, offset)
        runs_to_insert: list[RunItem] = [TextItem(text=f"{greeting} ", r_pr=r_pr)]

        # Find available title/first/last fields
        fields_to_add: list[str] = []
        if self.data_source:
            if self.data_source.find_field_index("Title") >= 0:
                fields_to_add.append("Title")
            if self.data_source.find_field_index("First Name") >= 0:
                fields_to_add.append("First Name")
            if self.data_source.find_field_index("Last Name") >= 0:
                fields_to_add.append("Last Name")

        if not fields_to_add:
            fields_to_add = ["First Name", "Last Name"]

        for i, fn in enumerate(fields_to_add):
            if i > 0:
                runs_to_insert.append(TextItem(text=" ", r_pr=r_pr))
            safe_fn = fn.replace(" ", "_")
            instr = f"MERGEFIELD {safe_fn}"
            runs_to_insert.extend([
                FieldBeginItem(field_type="MERGEFIELD", instr=instr, r_pr=r_pr),
                FieldSeparateItem(r_pr=r_pr),
                TextItem(text=f"«{safe_fn}»", r_pr=r_pr),
                FieldEndItem(r_pr=r_pr),
            ])

        runs_to_insert.append(TextItem(text=salutation, r_pr=r_pr))
        p.runs[idx:idx] = runs_to_insert

    def insert_address_block(
        self,
        doc: Document,
        insert_after_p: Paragraph,
        r_pr: RunProperties | None = None,
    ) -> list[Paragraph]:
        """Insert standard Word Address Block paragraphs with blank-line suppression."""
        # 1. Name line
        # 2. Company Name line
        # 3. Address Line 1
        # 4. Address Line 2
        # 5. City, State ZIP Code
        lines = [
            ["Title", "First Name", "Last Name"],
            ["Company Name"],
            ["Address Line 1"],
            ["Address Line 2"],
            [("City", ", "), ("State", " "), ("ZIP Code", "")],
        ]

        created_paras: list[Paragraph] = []
        for line_spec in lines:
            p = Paragraph()
            p._was_address_block = True  # type: ignore[attr-defined]

            first_item = True
            for item in line_spec:
                if isinstance(item, tuple):
                    fn, sep = item
                else:
                    fn, sep = item, " "

                if self.data_source and self.data_source.find_field_index(fn) < 0:
                    continue

                if not first_item and sep:
                    p.runs.append(TextItem(text=sep, r_pr=r_pr))

                safe_fn = fn.replace(" ", "_")
                instr = f"MERGEFIELD {safe_fn}"
                p.runs.extend([
                    FieldBeginItem(field_type="MERGEFIELD", instr=instr, r_pr=r_pr),
                    FieldSeparateItem(r_pr=r_pr),
                    TextItem(text=f"«{safe_fn}»", r_pr=r_pr),
                    FieldEndItem(r_pr=r_pr),
                ])
                first_item = False

            if p.runs:
                created_paras.append(p)

        # Insert created paragraphs into doc.main after insert_after_p
        try:
            target_idx = doc.main.paras.index(insert_after_p) + 1
        except ValueError:
            target_idx = len(doc.main.paras)

        doc.main.paras[target_idx:target_idx] = created_paras
        return created_paras

    def _clone_and_merge_paragraph(
        self,
        src_p: Paragraph,
        record_idx: int,
    ) -> Paragraph:
        """Clone paragraph and replace all MERGEFIELD runs with concrete evaluated TextItems."""
        new_p = Paragraph(
            id=src_p.id,
            p_pr=copy.deepcopy(src_p.p_pr),
            sect=copy.deepcopy(src_p.sect) if src_p.sect else None,
        )
        if hasattr(src_p, "_was_address_block"):
            new_p._was_address_block = src_p._was_address_block  # type: ignore[attr-defined]

        out_runs: list[RunItem] = []
        fb_item: FieldBeginItem | None = None

        for it in src_p.runs:
            if isinstance(it, FieldBeginItem):
                instr = (it.instr or it.field_type).strip()
                if re.match(r"^(MERGEFIELD|MERGEREC|MERGESEQ)\b", instr, re.IGNORECASE):
                    fb_item = it
                    continue
                out_runs.append(copy.deepcopy(it))
            elif isinstance(it, FieldSeparateItem) and fb_item is not None:
                continue
            elif isinstance(it, FieldEndItem) and fb_item is not None:
                # Evaluate and append merged TextItem
                instr = (fb_item.instr or fb_item.field_type).strip()
                val = self.evaluate_merge_instruction(instr, record_index=record_idx)
                if val:
                    out_runs.append(TextItem(text=val, r_pr=copy.deepcopy(fb_item.r_pr)))
                fb_item = None
            elif fb_item is not None:
                # Skip cached field results inside fb...fe
                continue
            else:
                out_runs.append(copy.deepcopy(it))

        new_p.runs = out_runs
        return new_p

    def build_merged_document(self, src_doc: Document) -> Document | None:
        """Generate a complete merged document across all active recipient records."""
        if not self.data_source:
            return None
        active_recs = self.data_source.active_records()
        if not active_recs:
            return None

        # Build target document
        merged_doc = Document()
        merged_doc.styles = copy.deepcopy(src_doc.styles)
        merged_doc.numbering = copy.deepcopy(src_doc.numbering)
        merged_doc.defaults = copy.deepcopy(src_doc.defaults)
        merged_doc.settings = copy.deepcopy(src_doc.settings)
        merged_doc.hf = copy.deepcopy(src_doc.hf)
        merged_doc.sect = copy.deepcopy(src_doc.sect)
        merged_doc.props = copy.deepcopy(src_doc.props)
        orig_title = src_doc.props.get("title") or "Document"
        merged_doc.props["title"] = f"{orig_title} (merged)"

        merged_paras: list[Paragraph] = []

        for rec_num, rec_idx in enumerate(active_recs):
            # Process paragraphs for this recipient
            rec_paras: list[Paragraph] = []
            for p in src_doc.main.paras:
                merged_p = self._clone_and_merge_paragraph(p, rec_idx)

                # Blank-line suppression:
                # If paragraph was part of an address block and is empty, suppress it
                if getattr(merged_p, "_was_address_block", False):
                    p_text = "".join(
                        r.text for r in merged_p.runs if isinstance(r, TextItem)
                    ).strip()
                    if not p_text:
                        continue

                rec_paras.append(merged_p)

            # In letters mode, add nextPage section break on the last paragraph of each recipient
            if self.doc_type != "directory" and rec_num < len(active_recs) - 1:
                if not rec_paras:
                    rec_paras.append(Paragraph())
                last_p = rec_paras[-1]
                # Attach nextPage section property
                sec = copy.deepcopy(src_doc.sect)
                sec.type = "nextPage"
                last_p.sect = sec

            merged_paras.extend(rec_paras)

        merged_doc.main.paras = merged_paras
        return merged_doc

    def export_merged_pdf(self, src_doc: Document, output_path: str | Path) -> bool:
        """Export merged document to PDF using Qt QPrinter."""
        merged_doc = self.build_merged_document(src_doc)
        if not merged_doc:
            return False

        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QFont, QPageSize, QPainter, QPen
        from PySide6.QtPrintSupport import QPrinter

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(output_path))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        # Render document pages
        from atboffice.modules.writer.layout.pagination import paginate_document
        from atboffice.modules.writer.layout.portions import PortionType

        pag_res = paginate_document(merged_doc)

        painter = QPainter(printer)
        try:
            for i, pg in enumerate(pag_res.pages):
                if i > 0:
                    printer.newPage()

                for reg in pg.regions:
                    for col in reg.columns:
                        for frag in col.fragments:
                            frag_top = pg.body_top + col.top + frag.top
                            for line in frag.lines:
                                line_y = frag_top + line.top
                                cur_x = pg.body_left + col.left + line.indent_left
                                for po in line.portions:
                                    if po.type == PortionType.TEXT and po.text:
                                        font = QFont(po.font_family or "Times New Roman")
                                        font.setPointSizeF(po.font_size or 12.0)
                                        painter.setFont(font)
                                        painter.setPen(QPen(QColor(0, 0, 0)))
                                        painter.drawText(
                                            QPointF(cur_x, line_y + line.baseline),
                                            po.text,
                                        )
                                    cur_x += po.width
        finally:
            painter.end()

        return True
