"""Shared Office 2003 Research & Offline WordNet Thesaurus task pane."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
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
from atboffice.ui.styles.luna_2003 import theme_tokens, ui_font

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResearchSearchHit:
    """One clickable search match returned by a host editor adapter."""

    label: str
    navigate: Callable[[], None]
    tooltip: str = ""


@dataclass
class ResearchHostAdapter:
    """Host-specific callbacks and scope labels parameterizing ``SuiteResearchPane``."""

    get_selection_text: Callable[[], str] = lambda: ""
    insert_text: Callable[[str], bool] = lambda _word: False
    search_items: Callable[[str, int], list[ResearchSearchHit]] = lambda _q, _limit: []
    scope_label: str = "搜索本文档"
    scope_heading: str = "本文档"
    no_matches_label: str = "在此文档中未找到该文字。"


class SuiteResearchPane(QWidget):
    """Office 2003 Research & Thesaurus task pane shared across Quire, Ledger and Lectern."""

    insert_requested = Signal(str)

    def __init__(
        self,
        adapter: ResearchHostAdapter | None = None,
        *,
        get_selection_text: Callable[[], str] | None = None,
        insert_text: Callable[[str], bool] | None = None,
        search_items: Callable[[str, int], list[ResearchSearchHit]] | None = None,
        scope_label: str | None = None,
        scope_heading: str | None = None,
        no_matches_label: str | None = None,
        engine: ThesaurusEngine | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        base = adapter or ResearchHostAdapter()
        self._adapter = ResearchHostAdapter(
            get_selection_text=get_selection_text or base.get_selection_text,
            insert_text=insert_text or base.insert_text,
            search_items=search_items or base.search_items,
            scope_label=scope_label or base.scope_label,
            scope_heading=scope_heading or base.scope_heading,
            no_matches_label=no_matches_label or base.no_matches_label,
        )
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
        for svc_id, src_label in self._service_specs():
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

    def _service_specs(self) -> tuple[tuple[str, str], ...]:
        return (
            ("thesaurus", "同义词库：英语（美国）"),
            ("thesaurusUK", "同义词库：英语（英国）"),
            ("document", self._adapter.scope_label),
            ("all", "所有参考书籍"),
        )

    def set_adapter(self, adapter: ResearchHostAdapter) -> None:
        """Replace host adapter and refresh scope label in service selector."""
        self._adapter = adapter
        self.retranslate_ui()

    def _apply_theme_colors(self) -> None:
        tok = theme_tokens()
        self.scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {tok.tb_border}; background: {tok.menu_face}; }}"
        )
        self.results_widget.setStyleSheet(f"background: {tok.menu_face};")

    def set_service(self, service: str) -> None:
        """Select a reference service by ID (``thesaurus``, ``thesaurusUK``, ``document``)."""
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

    def open_with_query(self, query: str | None = None, service: str | None = None) -> None:
        """Pre-fill query/service and immediately execute a lookup when query is non-empty."""
        if service:
            self.set_service(service)
        raw = self._adapter.get_selection_text() if query is None else query
        cleaned = (raw or "").strip()
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
        tok = theme_tokens()
        lbl = QLabel(text, self.results_widget)
        lbl.setFont(ui_font(9))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {tok.tb_border}; background: transparent;")
        self.results_layout.addWidget(lbl)

    def _add_section_header(self, text: str, bold: bool = True) -> None:
        tok = theme_tokens()
        lbl = QLabel(text, self.results_widget)
        lbl.setFont(ui_font(9, bold=bold))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {tok.highlight}; margin-top: 4px; background: transparent;")
        self.results_layout.addWidget(lbl)

    def _make_word_button(self, word: str) -> QToolButton:
        tok = theme_tokens()
        btn = QToolButton(self.results_widget)
        btn.setText(word)
        btn.setFont(ui_font(9))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(
            "QToolButton { border: none; text-align: left; padding: 2px 6px; "
            f"color: {tok.highlight}; background: transparent; }}"
            f"QToolButton:hover {{ background: {tok.menu_hot}; text-decoration: underline; }}"
        )
        btn.clicked.connect(lambda _chk=False, b=btn, w=word: self._show_word_menu(b, w))
        btn.installEventFilter(self)
        btn.setProperty("_thes_word", word)
        return btn

    def eventFilter(self, obj: Any, event: Any) -> bool:
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
        """Insert or replace active host selection/target with ``word`` via host adapter."""
        self.insert_requested.emit(word)
        return bool(self._adapter.insert_text(word))

    def go_back(self) -> None:
        """Navigate back to previous query in history stack."""
        if len(self._history) <= 1:
            return
        self._history.pop()
        prev = self._history[-1]
        self.btn_back.setEnabled(len(self._history) > 1)
        self.search(prev, record_history=False)

    def search(self, query: str | None = None, *, record_history: bool = True) -> None:
        """Execute thesaurus and/or host document/workbook/presentation lookup."""
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
            self._render_thesaurus_results(text, service=service)
        if service in ("document", "all"):
            self._render_host_matches(text)

        self.results_layout.addStretch(1)

    def _render_thesaurus_results(self, text: str, *, service: str = "thesaurus") -> None:
        header = (
            safe_tr("同义词库：英语（英国）")
            if service == "thesaurusUK"
            else safe_tr("同义词库：英语")
        )
        self._add_section_header(header)
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

    def _render_host_matches(self, text: str) -> None:
        tok = theme_tokens()
        self._add_section_header(safe_tr(self._adapter.scope_heading))
        limit = 50
        hits = self._adapter.search_items(text, limit)
        if not hits:
            self._add_note(safe_tr(self._adapter.no_matches_label))
            return

        for hit in hits[:limit]:
            btn = QToolButton(self.results_widget)
            btn.setText(hit.label)
            if hit.tooltip:
                btn.setToolTip(hit.tooltip)
            btn.setFont(ui_font(9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setStyleSheet(
                "QToolButton { border: none; text-align: left; padding: 3px 6px; "
                "color: palette(text); background: transparent; }"
                f"QToolButton:hover {{ background: {tok.menu_hot}; }}"
            )
            btn.clicked.connect(lambda _chk=False, cb=hit.navigate: cb())
            self.results_layout.addWidget(btn)

        if len(hits) >= limit:
            self._add_note(safe_tr("显示前 50 个匹配项。"))

    def retranslate_ui(self) -> None:
        """Retranslate static labels, service items, and re-render current query results."""
        self.lbl_search_for.setText(safe_tr("搜索内容："))
        self.btn_go.setText(safe_tr("转到"))
        self.btn_back.setText(safe_tr("◄ 返回"))
        for i, (_svc_id, src_label) in enumerate(self._service_specs()):
            self.service_combo.setItemText(i, safe_tr(src_label))
        self._apply_theme_colors()
        if self._last_query:
            self.search(self._last_query, record_history=False)
