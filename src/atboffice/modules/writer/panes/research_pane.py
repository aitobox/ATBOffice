"""Quire Research and Offline WordNet Thesaurus task pane."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.core.i18n import safe_tr
from atboffice.modules.common.thesaurus import POS_ABBR, ThesaurusEngine, get_thesaurus_engine
from atboffice.modules.writer.models.document import (
    Paragraph,
    all_paragraphs,
    plen,
    ptext,
    reindex,
)
from atboffice.modules.writer.views.caret_controller import (
    DocPos,
    Selection,
    delete_range_in_paragraph,
    insert_text_in_paragraph,
)
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\w+")

_SERVICES: tuple[tuple[str, str], ...] = (
    ("thesaurus", "同义词库：英语（美国）"),
    ("thesaurusUK", "同义词库：英语（英国）"),
    ("document", "搜索本文档"),
    ("all", "所有参考书籍"),
)


class ResearchTaskPane(QWidget):
    """Office 2003 Research task pane backed by offline WordNet thesaurus & document search."""

    insert_requested = Signal(str)

    def __init__(
        self,
        canvas_getter: Callable[[], Any] | None = None,
        engine: ThesaurusEngine | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._canvas_getter = canvas_getter
        self._engine = engine or get_thesaurus_engine()
        self._history: list[str] = []
        self._last_query: str = ""
        self._last_service: str = "thesaurus"

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        self.lbl_search_for = QLabel(safe_tr("搜索内容："), self)
        self.lbl_search_for.setFont(ui_font(9, bold=True))
        root.addWidget(self.lbl_search_for)

        row_q = QHBoxLayout()
        row_q.setSpacing(4)
        self.query_edit = QLineEdit(self)
        self.query_edit.setFont(ui_font(9))
        self.query_edit.returnPressed.connect(lambda: self.search())
        row_q.addWidget(self.query_edit, stretch=1)

        self.btn_go = QPushButton(safe_tr("转到"), self)
        self.btn_go.setFont(ui_font(9))
        self.btn_go.clicked.connect(lambda: self.search())
        row_q.addWidget(self.btn_go)
        root.addLayout(row_q)

        self.service_combo = QComboBox(self)
        self.service_combo.setFont(ui_font(9))
        for svc_id, src_label in _SERVICES:
            self.service_combo.addItem(safe_tr(src_label), svc_id)
        self.service_combo.currentIndexChanged.connect(self._on_service_changed)
        root.addWidget(self.service_combo)

        row_nav = QHBoxLayout()
        row_nav.setSpacing(4)
        self.btn_back = QPushButton(safe_tr("◄ 返回"), self)
        self.btn_back.setFont(ui_font(9))
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.go_back)
        row_nav.addWidget(self.btn_back)
        row_nav.addStretch(1)
        root.addLayout(row_nav)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.results_widget = QWidget(self.scroll)
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(6, 6, 6, 6)
        self.results_layout.setSpacing(4)
        self.results_layout.addStretch(1)
        self.scroll.setWidget(self.results_widget)
        root.addWidget(self.scroll, stretch=1)

        self._apply_theme_colors()

    def _apply_theme_colors(self) -> None:
        tok = theme_tokens()
        self.scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {tok.tb_border}; background: {tok.menu_face}; }}"
        )
        self.results_widget.setStyleSheet(f"background: {tok.menu_face};")

    def _canvas(self) -> Any | None:
        return self._canvas_getter() if self._canvas_getter is not None else None

    def set_service(self, service: str) -> None:
        """Select a reference service by ID (``thesaurus``, ``thesaurusUK``, ``document``, etc.)."""
        idx = self.service_combo.findData(service)
        if idx >= 0:
            self.service_combo.blockSignals(True)
            self.service_combo.setCurrentIndex(idx)
            self.service_combo.blockSignals(False)
            self._last_service = service

    def _on_service_changed(self, _idx: int) -> None:
        svc = self.service_combo.currentData()
        if isinstance(svc, str):
            self._last_service = svc
        if self.query_edit.text().strip():
            self.search(self.query_edit.text().strip(), record_history=False)

    def open_with_query(self, query: str = "", service: str | None = None) -> None:
        """Pre-fill query/service and immediately execute a lookup when query is non-empty."""
        if service:
            self.set_service(service)
        cleaned = query.strip()
        self.query_edit.setText(cleaned)
        self.query_edit.setFocus()
        self.query_edit.selectAll()
        if cleaned:
            self.search(cleaned)

    def _clear_results(self) -> None:
        while self.results_layout.count():
            item = self.results_layout.takeAt(0)
            w = item.widget() if item is not None else None
            if w is not None:
                w.deleteLater()

    def _add_note(self, text: str) -> None:
        lbl = QLabel(text, self.results_widget)
        lbl.setFont(ui_font(9))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #4B5563; background: transparent;")
        self.results_layout.addWidget(lbl)

    def _add_section_header(self, text: str, bold: bool = True) -> None:
        lbl = QLabel(text, self.results_widget)
        lbl.setFont(ui_font(9, bold=bold))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color: #1E3A8A; margin-top: 4px; background: transparent;")
        self.results_layout.addWidget(lbl)

    def _make_word_button(self, word: str) -> QToolButton:
        btn = QToolButton(self.results_widget)
        btn.setText(word)
        btn.setFont(ui_font(9))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            "QToolButton { border: none; text-align: left; padding: 2px 6px; "
            "color: #003399; background: transparent; }"
            "QToolButton:hover { background: #E5EEF8; text-decoration: underline; }"
        )
        btn.clicked.connect(lambda _chk=False, b=btn, w=word: self._show_word_menu(b, w))
        # Double-clicking any candidate word immediately triggers a follow-up lookup.
        btn.installEventFilter(self)
        btn.setProperty("_thes_word", word)
        return btn

    def eventFilter(self, obj: Any, event: Any) -> bool:
        from PySide6.QtCore import QEvent

        if event is not None and event.type() == QEvent.Type.MouseButtonDblClick:
            word = obj.property("_thes_word")
            if isinstance(word, str) and word:
                self.search(word)
                return True
        return super().eventFilter(obj, event)

    def _show_word_menu(self, anchor: QToolButton, word: str) -> None:
        menu = QMenu(anchor)
        act_insert = menu.addAction(safe_tr("插入"))
        act_copy = menu.addAction(safe_tr("复制"))
        act_lookup = menu.addAction(safe_tr("查阅"))
        act_insert.triggered.connect(lambda: self.insert_word(word))
        act_copy.triggered.connect(lambda: self.copy_word(word))
        act_lookup.triggered.connect(lambda: self.search(word))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def copy_word(self, word: str) -> None:
        """Copy candidate word to system clipboard."""
        cb = QGuiApplication.clipboard()
        if cb is not None:
            cb.setText(word)

    def insert_word(self, word: str) -> bool:
        """Replace active selection or word under caret with ``word`` (undoable)."""
        self.insert_requested.emit(word)
        canvas = self._canvas()
        if canvas is None or not getattr(canvas, "doc", None):
            return False

        ctl = canvas.controller
        p = ctl._paragraph_by_id(ctl.pos.para_id)
        if p is None:
            return False

        if ctl.selection.is_collapsed:
            txt = ptext(p)
            off = ctl.pos.offset
            for m in _WORD_RE.finditer(txt):
                if m.start() <= off <= m.end():
                    ctl.selection = Selection(DocPos(p.id, m.start()), DocPos(p.id, m.end()))
                    ctl.pos = ctl.selection.focus
                    break

        start, end = ctl.selection.ordered_range(canvas.doc)

        def _mutate() -> bool:
            p_start = ctl._paragraph_by_id(start.para_id)
            p_end = ctl._paragraph_by_id(end.para_id)
            if p_start is None or p_end is None:
                return False
            if start.para_id == end.para_id:
                delete_range_in_paragraph(p_start, start.offset, end.offset)
            else:
                delete_range_in_paragraph(p_start, start.offset, plen(p_start))
                delete_range_in_paragraph(p_end, 0, end.offset)
                paras = all_paragraphs(canvas.doc)
                remove_ids = {
                    paras[k].id for k in range(min(p_start._o + 1, p_end._o), p_end._o + 1)
                }
                p_start.runs.extend(p_end.runs)
                canvas.doc.main.blocks = [
                    b
                    for b in canvas.doc.main.blocks
                    if not (isinstance(b, Paragraph) and b.id in remove_ids)
                ]
                reindex(canvas.doc)
            insert_text_in_paragraph(p_start, start.offset, word)
            new_pos = DocPos(p_start.id, start.offset + len(word))
            ctl.pos = new_pos
            ctl.selection = Selection(new_pos, new_pos)
            return True

        res = canvas.run_undoable(_mutate, safe_tr("插入同义词"))
        if res is False:
            return False
        win = self.window()
        if hasattr(win, "set_modified"):
            win.set_modified(True)
        canvas.viewport().update()
        return True

    def go_back(self) -> None:
        """Navigate back to previous query in history stack."""
        if len(self._history) <= 1:
            return
        self._history.pop()
        prev = self._history[-1]
        self.btn_back.setEnabled(len(self._history) > 1)
        self.search(prev, record_history=False)

    def search(self, query: str | None = None, *, record_history: bool = True) -> None:
        """Execute thesaurus and/or in-document lookup for ``query``."""
        text = (self.query_edit.text() if query is None else query).strip()
        if not text:
            return
        self.query_edit.setText(text)
        self._last_query = text
        if record_history and (not self._history or self._history[-1] != text):
            self._history.append(text)
        self.btn_back.setEnabled(len(self._history) > 1)

        service = self.service_combo.currentData()
        if not isinstance(service, str):
            service = "thesaurus"
        self._last_service = service

        self._clear_results()

        if service in ("thesaurus", "thesaurusUK", "all"):
            self._render_thesaurus_results(text)
        if service in ("document", "all"):
            self._render_document_matches(text)

        self.results_layout.addStretch(1)

    def _render_thesaurus_results(self, text: str) -> None:
        self._add_section_header(safe_tr("同义词库：英语"))
        try:
            entry = self._engine.lookup(text)
        except OSError as exc:
            logger.exception("Thesaurus lookup failed for %r", text)
            self._add_note(safe_tr("无法加载离线同义词库：{0}").format(exc))
            return

        if entry is None:
            self._add_note(safe_tr("未找到“{0}”的结果。按字母顺序列出：").format(text))
            for cand in self._engine.near(text, limit=12):
                self.results_layout.addWidget(self._make_word_button(cand))
            return

        if entry.from_base:
            self._add_note(safe_tr("“{0}”的搜索结果。").format(entry.head))

        for sense in entry.senses:
            pos_str = POS_ABBR.get(sense.pos, sense.pos)
            self._add_section_header(f"{sense.synonyms[0]} ({pos_str})")
            for syn in sense.synonyms:
                self.results_layout.addWidget(self._make_word_button(syn))

        if entry.antonyms:
            self._add_section_header(safe_tr("{0}（反义词）").format(entry.antonyms[0]))
            for ant in entry.antonyms:
                self.results_layout.addWidget(self._make_word_button(ant))

    def _render_document_matches(self, text: str) -> None:
        self._add_section_header(safe_tr("本文档"))
        canvas = self._canvas()
        doc = getattr(canvas, "doc", None)
        if canvas is None or doc is None:
            self._add_note(safe_tr("在此文档中未找到该文字。"))
            return

        reindex(doc)
        needle = text.lower()
        count = 0
        for p in all_paragraphs(doc):
            txt = ptext(p)
            low = txt.lower()
            idx = low.find(needle)
            while idx >= 0 and count < 50:
                start_off = idx
                end_off = idx + len(needle)
                pre = ("…" if start_off > 30 else "") + txt[max(0, start_off - 30) : start_off]
                post = txt[end_off : end_off + 40] + ("…" if len(txt) > end_off + 40 else "")
                snippet = f"{pre}[{txt[start_off:end_off]}]{post}".replace("\t", " ")
                hit_btn = QToolButton(self.results_widget)
                hit_btn.setText(snippet)
                hit_btn.setFont(ui_font(9))
                hit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                hit_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                hit_btn.setStyleSheet(
                    "QToolButton { border: none; text-align: left; padding: 3px 6px; "
                    "color: #111827; background: transparent; }"
                    "QToolButton:hover { background: #E5EEF8; }"
                )
                hit_btn.clicked.connect(
                    lambda _chk=False, pid=p.id, a=start_off, b=end_off: self._goto_match(pid, a, b)
                )
                self.results_layout.addWidget(hit_btn)
                count += 1
                idx = low.find(needle, end_off)
            if count >= 50:
                break

        if count == 0:
            self._add_note(safe_tr("在此文档中未找到该文字。"))
        elif count >= 50:
            self._add_note(safe_tr("显示前 50 个匹配项。"))

    def _goto_match(self, para_id: int, start_off: int, end_off: int) -> None:
        canvas = self._canvas()
        if canvas is None:
            return
        ctl = canvas.controller
        ctl.set_pos(DocPos(para_id, start_off), extend_selection=False)
        ctl.set_pos(DocPos(para_id, end_off), extend_selection=True)
        canvas.scroll_to_caret()
        canvas.viewport().update()

    def retranslate_ui(self) -> None:
        """Retranslate static labels, service items, and re-render current query results."""
        self.lbl_search_for.setText(safe_tr("搜索内容："))
        self.btn_go.setText(safe_tr("转到"))
        self.btn_back.setText(safe_tr("◄ 返回"))
        for i, (_svc_id, src_label) in enumerate(_SERVICES):
            self.service_combo.setItemText(i, safe_tr(src_label))
        if self._last_query:
            self.search(self._last_query, record_history=False)
