"""Writer canvas editing commands: formatting, styles, tables, revisions, outline."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from atboffice.core.i18n import safe_tr
from atboffice.modules.writer.models.document import (
    Paragraph,
    TextItem,
    info,
    normalize,
    paras_between,
    plen,
    ptext,
    reindex,
    split_at,
)
from atboffice.modules.writer.models.properties import (
    IndentProperties,
    NumberingRef,
    ParagraphProperties,
    RunProperties,
    SpacingProperties,
)
from atboffice.modules.writer.models.revision import (
    accept_all_revisions,
    accept_revision,
    insert_comment,
    list_revisions,
    reject_all_revisions,
    reject_revision,
    toggle_tracking,
)
from atboffice.modules.writer.models.table import (
    create_simple_table,
    delete_cols,
    delete_rows,
    insert_cols,
    insert_rows,
    merge_cells,
    split_cells,
    table_map,
)
from atboffice.modules.writer.views.canvas_common import (
    _undoable,
    _undoable_document,
)
from atboffice.modules.writer.views.caret_controller import (
    DocPos,
    Selection,
)


class CanvasEditingMixin:
    """Paragraph and character formatting, styles, table commands, revisions and outline moves."""

    def _get_selected_paragraphs(self) -> list[Paragraph]:
        """Return all paragraphs covered by the current selection."""
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            return [p] if p is not None else []
        a, b = self.controller.selection.ordered_range(self.doc)
        pa = self.controller._paragraph_by_id(a.para_id)
        pb = self.controller._paragraph_by_id(b.para_id)
        if pa is not None and pb is not None:
            return paras_between(self.doc, pa, pb)
        return [pa] if pa is not None else []

    @_undoable("设置格式")
    def set_paragraph_alignment(self, jc: str) -> None:
        """Set paragraph alignment (left, center, right, both/justify)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.jc = jc
        self._on_formatting_applied()

    @_undoable("段落缩进")
    def change_indent(self, delta_pt: float) -> None:
        """Increase or decrease left indent for selected paragraphs."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.ind is None:
                p.p_pr.ind = IndentProperties()
            p.p_pr.ind.left = max(0.0, (p.p_pr.ind.left or 0.0) + delta_pt)
        self._on_formatting_applied()

    @_undoable("设置格式")
    def set_line_spacing(self, line: float, line_rule: str = "auto") -> None:
        """Set line spacing multiplier (e.g. 1.0, 1.5, 2.0)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if p.p_pr.sp is None:
                p.p_pr.sp = SpacingProperties()
            p.p_pr.sp.line = line
            p.p_pr.sp.line_rule = line_rule
        self._on_formatting_applied()

    @_undoable("项目符号和编号")
    def toggle_list_style(self, kind: str) -> None:
        """Toggle bullet or numbering list on selected paragraphs."""
        paras = self._get_selected_paragraphs()
        if not paras:
            return
        first = paras[0]
        has_num = first.p_pr and first.p_pr.num is not None
        num_target = "1" if kind == "bullet" else "2"
        is_same = has_num and first.p_pr.num.id == num_target

        for p in paras:
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            if is_same:
                p.p_pr.num = None
            else:
                p.p_pr.num = NumberingRef(id=num_target, lvl=0)
        self._on_formatting_applied()

    def format_range(self, fn: Callable[[RunProperties], None]) -> None:
        """Apply a formatting function to all runs in the current selection (one undo step)."""
        with self.controller.edit_scope("设置格式"):
            self._format_range(fn)

    def _format_range(self, fn: Callable[[RunProperties], None]) -> None:
        if self.controller.selection.is_collapsed:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                if p.r_pr is None:
                    p.r_pr = RunProperties()
                fn(p.r_pr)
                for r in p.runs:
                    if getattr(r, "t", "") == "text":
                        if r.r_pr is None:
                            r.r_pr = RunProperties()
                        fn(r.r_pr)
        else:
            a, b = self.controller.selection.ordered_range(self.doc)
            pa = self.controller._paragraph_by_id(a.para_id)
            pb = self.controller._paragraph_by_id(b.para_id)
            if pa is not None and pb is not None:
                paras = paras_between(self.doc, pa, pb)
                for p in paras:
                    s = a.offset if p == pa else 0
                    e = b.offset if p == pb else plen(p)
                    if s < e:
                        i0 = split_at(p, s)
                        i1 = split_at(p, e)
                        for i in range(i0, i1):
                            it = p.runs[i]
                            if getattr(it, "t", "") == "text":
                                if it.r_pr is None:
                                    it.r_pr = RunProperties()
                                fn(it.r_pr)
                        normalize(p)
        self._on_formatting_applied()

    def toggle_character_format(self, attr: str) -> None:
        """Toggle a boolean or choice character formatting attribute."""
        curr_val = False
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            if attr == "bold":
                curr_val = bool(p.r_pr and p.r_pr.b)
            elif attr == "italic":
                curr_val = bool(p.r_pr and p.r_pr.i)
            elif attr == "underline":
                curr_val = bool(p.r_pr and p.r_pr.u and p.r_pr.u != "none")
            elif attr == "strike":
                curr_val = bool(p.r_pr and p.r_pr.strike)
            elif attr == "superscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "superscript")
            elif attr == "subscript":
                curr_val = bool(p.r_pr and p.r_pr.vert == "subscript")

        def _apply(r: RunProperties) -> None:
            if attr == "bold":
                r.b = not curr_val
            elif attr == "italic":
                r.i = not curr_val
            elif attr == "underline":
                r.u = "none" if curr_val else "single"
            elif attr == "strike":
                r.strike = not curr_val
                r.strike_off = curr_val
            elif attr == "superscript":
                r.vert = "baseline" if curr_val else "superscript"
            elif attr == "subscript":
                r.vert = "baseline" if curr_val else "subscript"

        self.format_range(_apply)

    def set_font_family(self, name: str) -> None:
        """Set font family for selection."""
        self.format_range(lambda r: setattr(r, "font", name))

    def set_font_size(self, size_pt: float) -> None:
        """Set font size in points for selection."""
        self.format_range(lambda r: setattr(r, "sz", size_pt))

    def set_font_color(self, color: str) -> None:
        """Set font color (hex string or 'auto') for selection."""
        self.format_range(lambda r: setattr(r, "color", color))

    def set_highlight_color(self, color: str | None) -> None:
        """Highlight the selection with a Word highlight colour; ``None``/"none" removes it.

        Accepts a w:highlight name ("yellow") or one of the palette's hex colours.
        """
        from atboffice.ui.components.color_picker import HIGHLIGHT_NAME_BY_HEX

        if color in (None, "", "none", "auto"):
            value: str | None = None
        else:
            value = HIGHLIGHT_NAME_BY_HEX.get(str(color).upper(), str(color))
        self.run_undoable(lambda: self.format_range(lambda r: setattr(r, "highlight", value)))

    def get_current_style_id(self) -> str:
        """Return the paragraph style ID at the current caret position."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p and p.p_pr and p.p_pr.style:
            return p.p_pr.style
        return "Normal"

    @_undoable("样式", ("styles",))
    def apply_style(self, style_id: str) -> None:
        """Apply a named style to the currently selected paragraph(s)."""
        from atboffice.modules.writer.models.styles import builtin_styles

        if style_id not in self.doc.styles:
            b_styles = builtin_styles()
            if style_id in b_styles:
                self.doc.styles[style_id] = copy.deepcopy(b_styles[style_id])

        paras = self._get_selected_paragraphs()
        if not paras:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                paras = [p]

        for p in paras:
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.style = style_id

        self._on_formatting_applied()

    @_undoable("清除格式")
    def clear_formatting(self) -> None:
        """Reset paragraph style to Normal and clear run character overrides."""
        paras = self._get_selected_paragraphs()
        if not paras:
            p = self.controller._paragraph_by_id(self.controller.pos.para_id)
            if p is not None:
                paras = [p]

        for p in paras:
            if p.p_pr is not None:
                p.p_pr.style = "Normal"
                p.p_pr.jc = "left"
                p.p_pr.num = None
            if p.r_pr is not None:
                p.r_pr = RunProperties()
            for r in p.runs:
                if getattr(r, "t", "") == "text":
                    r.r_pr = RunProperties()

        self._on_formatting_applied()

    def _on_formatting_applied(self) -> None:
        """Repaginate and re-render in place (keeps undo history, caret and selection)."""
        self.refresh_layout()

    def get_current_table_context(self) -> dict[str, Any] | None:
        """Return table, row, cell and grid coordinates if caret is within a table."""
        inf = info(self.doc, self.controller.pos.para_id)
        if not inf or not inf.get("parents"):
            return None
        for parent in inf["parents"]:
            if isinstance(parent, dict) and "tbl" in parent:
                tbl = parent["tbl"]
                cell = parent.get("cell")
                r_idx, c_idx = 0, 0
                grid = table_map(tbl)
                for r_i, row in enumerate(grid):
                    for entry in row:
                        if entry.cell is cell:
                            r_idx, c_idx = entry.row_idx, entry.col_idx
                            break
                return {
                    "tbl": tbl,
                    "row": parent.get("row"),
                    "cell": cell,
                    "row_idx": r_idx,
                    "col_idx": c_idx,
                }
        return None

    @_undoable("插入表格")
    def insert_table(self, rows: int = 2, cols: int = 2) -> None:
        """Insert a new table at the current position."""
        tbl = create_simple_table(rows, cols)
        inf = info(self.doc, self.controller.pos.para_id)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        curr_p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        idx = story.blocks.index(curr_p) if curr_p in story.blocks else len(story.blocks)
        story.blocks.insert(idx + 1, tbl)
        reindex(self.doc)
        first_p = tbl.rows[0].cells[0].blocks[0]
        self.controller.pos = DocPos(first_p.id, 0)
        self.controller.selection = Selection(self.controller.pos, self.controller.pos)
        self.controller.repaginate_and_refresh()

    @_undoable("插入行")
    def insert_table_row(self, above: bool = False) -> None:
        """Insert a row above or below current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        insert_rows(tbl, r_idx, count=1, above=above)
        self._on_formatting_applied()

    @_undoable("插入列")
    def insert_table_col(self, left: bool = False) -> None:
        """Insert a column to the left or right of current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        insert_cols(tbl, c_idx, count=1, left=left)
        self._on_formatting_applied()

    @_undoable("删除行")
    def delete_table_row(self) -> None:
        """Delete the current table row."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        if len(tbl.rows) > 1:
            target_r = r_idx - 1 if r_idx > 0 else r_idx + 1
            surviving_p = tbl.rows[target_r].cells[0].blocks[0]
            delete_rows(tbl, r_idx, r_idx)
            self._on_formatting_applied()
            self.controller.pos = DocPos(surviving_p.id, 0)
            self.controller.selection = Selection(self.controller.pos, self.controller.pos)
            self.controller.caret_changed.emit()

    @_undoable("删除列")
    def delete_table_col(self) -> None:
        """Delete the current table column."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        r_idx = ctx["row_idx"]
        if len(tbl.grid) > 1:
            delete_cols(tbl, c_idx, c_idx)
            self._on_formatting_applied()
            grid = table_map(tbl)
            target_c = min(c_idx, len(tbl.grid) - 1)
            target_r = min(r_idx, len(tbl.rows) - 1)
            surviving_cell = grid[target_r][target_c].cell
            surviving_p = surviving_cell.blocks[0] if surviving_cell.blocks else None
            if surviving_p is not None:
                self.controller.pos = DocPos(surviving_p.id, 0)
                self.controller.selection = Selection(self.controller.pos, self.controller.pos)
                self.controller.caret_changed.emit()

    @_undoable("合并单元格")
    def merge_table_cells(self) -> None:
        """Merge cells in the current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        if c_idx + 1 < len(tbl.grid):
            merge_cells(tbl, r_idx, r_idx, c_idx, c_idx + 1)
            self._on_formatting_applied()

    @_undoable("拆分单元格")
    def split_table_cells(self, num_rows: int = 1, num_cols: int = 2) -> None:
        """Split the current cell into num_rows x num_cols."""
        ctx = self.get_current_table_context()
        if not ctx or not ctx["cell"]:
            return
        split_cells(ctx["tbl"], ctx["cell"], num_rows, num_cols)
        self._on_formatting_applied()

    @_undoable("平均分布各行")
    def distribute_table_rows(self) -> None:
        """Equalize height of all rows in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        for row in tbl.rows:
            row.tr_pr.h = 24.0
            row.tr_pr.h_rule = "exact"
        self._on_formatting_applied()

    @_undoable("平均分布各列")
    def distribute_table_cols(self) -> None:
        """Equalize width of all columns in current table."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        if tbl.grid:
            avg = sum(tbl.grid) / len(tbl.grid)
            tbl.grid = [round(avg, 2)] * len(tbl.grid)
        self._on_formatting_applied()

    @_undoable("排序")
    def sort_table(self, ascending: bool = True) -> None:
        """Sort data rows of the current table by the current column text."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        c_idx = ctx["col_idx"]
        if len(tbl.rows) > 1:
            grid = table_map(tbl)

            def _key(row_entry: list):
                if c_idx < len(row_entry):
                    p = row_entry[c_idx].cell.blocks[0] if row_entry[c_idx].cell.blocks else None
                    return ptext(p) if p else ""
                return ""

            header = tbl.rows[0]
            rest = tbl.rows[1:]
            rest.sort(key=lambda r: _key(grid[tbl.rows.index(r)]), reverse=not ascending)
            tbl.rows = [header] + rest
            self._on_formatting_applied()

    @_undoable("自动求和")
    def auto_sum_table(self) -> None:
        """Calculate and insert the sum of numbers above current cell."""
        ctx = self.get_current_table_context()
        if not ctx:
            return
        tbl = ctx["tbl"]
        r_idx = ctx["row_idx"]
        c_idx = ctx["col_idx"]
        grid = table_map(tbl)
        total = 0.0
        for r in range(r_idx):
            cell = grid[r][c_idx].cell
            for b in cell.blocks:
                if isinstance(b, Paragraph):
                    txt = ptext(b).strip()
                    try:
                        total += float(txt)
                    except ValueError:
                        pass
        curr_p = ctx["cell"].blocks[0] if ctx["cell"].blocks else None
        if curr_p is not None:
            curr_p.runs = [TextItem(text=f"{total:g}", r_pr=copy.deepcopy(curr_p.r_pr))]
            self._on_formatting_applied()

    def toggle_track_changes(self) -> bool:
        """Toggle track changes mode on document."""
        res = toggle_tracking(self.doc)
        self._on_formatting_applied()
        return res

    @_undoable_document("接受修订")
    def accept_current_revision(self, all_revisions: bool = False) -> None:
        """Accept revision at current position or all revisions."""
        if all_revisions:
            accept_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                accept_revision(self.doc, revs[0])
        self._on_formatting_applied()

    @_undoable_document("拒绝修订")
    def reject_current_revision(self, all_revisions: bool = False) -> None:
        """Reject revision at current position or all revisions."""
        if all_revisions:
            reject_all_revisions(self.doc)
        else:
            revs = list_revisions(self.doc)
            if revs:
                reject_revision(self.doc, revs[0])
        self._on_formatting_applied()

    @_undoable("插入批注", ("comments",))
    def insert_comment(self, author: str = "User", text: str = "") -> None:
        """Insert a comment on the current paragraph/selection."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if p is not None:
            a, b = self.controller.selection.ordered_range(self.doc)
            s = a.offset if a.para_id == p.id else 0
            e = b.offset if b.para_id == p.id else plen(p)
            insert_comment(
                self.doc,
                (p, s),
                (p, max(s + 1, e)),
                text=text or safe_tr("新批注"),
                author=author,
            )
            self._on_formatting_applied()

    @_undoable("大纲级别")
    def change_outline_level(self, delta: int) -> None:
        """Promote (delta < 0) or demote (delta > 0) outline level."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            curr = p.p_pr.outline_level or 1
            new_lvl = max(1, min(9, curr + delta))
            p.p_pr.outline_level = new_lvl
        self._on_formatting_applied()

    @_undoable("大纲级别")
    def set_outline_level(self, level: int | None) -> None:
        """Set outline level (1-9 or None for body text)."""
        for p in self._get_selected_paragraphs():
            if p.p_pr is None:
                p.p_pr = ParagraphProperties()
            p.p_pr.outline_level = level
        self._on_formatting_applied()

    @_undoable("移动段落")
    def move_paragraph(self, delta: int) -> None:
        """Move selected paragraph up (delta < 0) or down (delta > 0)."""
        p = self.controller._paragraph_by_id(self.controller.pos.para_id)
        if not p:
            return
        inf = info(self.doc, p)
        story = inf["story"] if inf and "story" in inf else self.doc.main
        if p in story.blocks:
            idx = story.blocks.index(p)
            new_idx = idx + delta
            if 0 <= new_idx < len(story.blocks):
                story.blocks.pop(idx)
                story.blocks.insert(new_idx, p)
                self._on_formatting_applied()
