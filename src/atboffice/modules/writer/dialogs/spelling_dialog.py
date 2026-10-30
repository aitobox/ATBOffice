"""Classic Word 2003 / Quire Spelling and Grammar check dialog."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.autocorrect import AutoCorrectEngine
from atboffice.modules.writer.models.document import (
    Document,
    all_paragraphs,
    ptext,
)
from atboffice.modules.writer.spell import SpellEngine
from atboffice.modules.writer.views.caret_controller import (
    CaretController,
    DocPos,
    Selection,
    delete_range_in_paragraph,
    insert_text_in_paragraph,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("SpellingGrammarDialog", text)


class SpellingGrammarDialog(QDialog):
    """Spelling and Grammar dialog with sentence context, suggestions, and batch replacement."""

    def __init__(
        self,
        doc: Document,
        controller: CaretController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.controller = controller
        self.spell_engine = SpellEngine.get_instance()
        self.autocorrect_engine = AutoCorrectEngine()

        self.issues: list[dict[str, Any]] = []
        self.current_idx: int = -1

        self.setWindowTitle(safe_tr("拼写和语法检查: 英语 (美国)"))
        self.resize(540, 360)
        self._init_ui()
        self._scan_document()
        self.show_next_issue()

    def _init_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Left Column: Context, Suggestions, Options
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        self.lbl_status = QLabel(safe_tr("不在词典中:"), self)
        left_layout.addWidget(self.lbl_status)

        self.txt_context = QTextEdit(self)
        self.txt_context.setReadOnly(True)
        self.txt_context.setFixedHeight(90)
        left_layout.addWidget(self.txt_context)

        self.lbl_sugg = QLabel(safe_tr("建议(&N):"), self)
        left_layout.addWidget(self.lbl_sugg)

        self.list_suggestions = QListWidget(self)
        self.list_suggestions.setFixedHeight(120)
        left_layout.addWidget(self.list_suggestions)

        self.lbl_lang = QLabel(safe_tr("词典语言: 英语 (美国)"), self)
        left_layout.addWidget(self.lbl_lang)

        self.chk_grammar = QCheckBox(safe_tr("检查语法(&G)"), self)
        self.chk_grammar.setChecked(True)
        left_layout.addWidget(self.chk_grammar)

        main_layout.addLayout(left_layout, stretch=1)

        # Right Column: Action Buttons
        right_layout = QVBoxLayout()
        right_layout.setSpacing(6)

        self.btn_ignore_once = QPushButton(safe_tr("忽略一次(&I)"), self)
        self.btn_ignore_once.clicked.connect(self._on_ignore_once)
        right_layout.addWidget(self.btn_ignore_once)

        self.btn_ignore_all = QPushButton(safe_tr("全部忽略(&G)"), self)
        self.btn_ignore_all.clicked.connect(self._on_ignore_all)
        right_layout.addWidget(self.btn_ignore_all)

        self.btn_add_dict = QPushButton(safe_tr("添加到词典(&A)"), self)
        self.btn_add_dict.clicked.connect(self._on_add_to_dict)
        right_layout.addWidget(self.btn_add_dict)

        right_layout.addSpacing(6)

        self.btn_change = QPushButton(safe_tr("更改(&C)"), self)
        self.btn_change.clicked.connect(self._on_change)
        right_layout.addWidget(self.btn_change)

        self.btn_change_all = QPushButton(safe_tr("全部更改(&L)"), self)
        self.btn_change_all.clicked.connect(self._on_change_all)
        right_layout.addWidget(self.btn_change_all)

        self.btn_autocorrect = QPushButton(safe_tr("自动更正(&R)"), self)
        self.btn_autocorrect.clicked.connect(self._on_autocorrect)
        right_layout.addWidget(self.btn_autocorrect)

        right_layout.addStretch()

        self.btn_cancel = QPushButton(safe_tr("关闭(&X)"), self)
        self.btn_cancel.clicked.connect(self.reject)
        right_layout.addWidget(self.btn_cancel)

        main_layout.addLayout(right_layout)

    def _scan_document(self) -> None:
        """Scan all paragraphs in document for misspelled words."""
        self.issues.clear()
        paras = all_paragraphs(self.doc)

        # Start from current paragraph if controller provided
        start_p_id = self.controller.pos.para_id if self.controller else None
        start_idx = 0
        if start_p_id is not None:
            for idx, p in enumerate(paras):
                if p.id == start_p_id:
                    start_idx = idx
                    break

        ordered_paras = paras[start_idx:] + paras[:start_idx]

        for p in ordered_paras:
            text = ptext(p)
            for word, start, end in self.spell_engine.tokenize_words(text):
                if not self.spell_engine.is_valid_word(word):
                    self.issues.append({
                        "para": p,
                        "word": word,
                        "start": start,
                        "end": end,
                    })

    def show_next_issue(self) -> None:
        """Advance to next spelling issue or display completion notification."""
        self.current_idx += 1
        while self.current_idx < len(self.issues):
            issue = self.issues[self.current_idx]
            p = issue["para"]
            w = issue["word"]
            # Check if issue word was already fixed or ignored
            if self.spell_engine.is_valid_word(w):
                self.current_idx += 1
                continue

            current_text = ptext(p)
            # Re-locate word in paragraph in case text shifted from prior edits
            if current_text[issue["start"]:issue["end"]] != w:
                pos = current_text.find(w)
                if pos >= 0:
                    issue["start"] = pos
                    issue["end"] = pos + len(w)
                else:
                    self.current_idx += 1
                    continue

            self._display_issue(issue)
            return

        # No further issues found
        QMessageBox.information(
            self,
            safe_tr("拼写和语法检查"),
            safe_tr("拼写和语法检查已完成。"),
        )
        self.accept()

    def _display_issue(self, issue: dict[str, Any]) -> None:
        """Render misspelled word, context sentence, and suggestions."""
        p = issue["para"]
        w = issue["word"]
        start = issue["start"]
        end = issue["end"]
        t = ptext(p)

        # Highlight word in caret controller if present
        if self.controller:
            self.controller.pos = DocPos(p.id, start)
            self.controller.selection = Selection(DocPos(p.id, start), DocPos(p.id, end))
            self.controller.caret_changed.emit()

        # Display context with red bold highlight
        before = t[max(0, start - 40):start]
        after = t[end:min(len(t), end + 40)]
        html_context = f"{before}<font color='red'><b>{w}</b></font>{after}"
        self.txt_context.setHtml(html_context)

        # Query suggestions
        suggestions = self.spell_engine.suggest(w, max_suggestions=8)
        self.list_suggestions.clear()
        if suggestions:
            for s in suggestions:
                self.list_suggestions.addItem(s)
            self.list_suggestions.setCurrentRow(0)
            self.btn_change.setEnabled(True)
            self.btn_change_all.setEnabled(True)
            self.btn_autocorrect.setEnabled(True)
        else:
            self.list_suggestions.addItem(safe_tr("(无建议)"))
            self.btn_change.setEnabled(False)
            self.btn_change_all.setEnabled(False)
            self.btn_autocorrect.setEnabled(False)

    def _get_selected_replacement(self) -> str | None:
        item = self.list_suggestions.currentItem()
        if item and item.text() != safe_tr("(无建议)"):
            return item.text()
        return None

    def _on_ignore_once(self) -> None:
        self.show_next_issue()

    def _on_ignore_all(self) -> None:
        if self.current_idx < len(self.issues):
            w = self.issues[self.current_idx]["word"]
            self.spell_engine.ignore_all(w)
        self.show_next_issue()

    def _on_add_to_dict(self) -> None:
        if self.current_idx < len(self.issues):
            w = self.issues[self.current_idx]["word"]
            self.spell_engine.add_to_custom_dict(w)
        self.show_next_issue()

    def _on_change(self) -> None:
        rep = self._get_selected_replacement()
        if not rep or self.current_idx >= len(self.issues):
            return

        issue = self.issues[self.current_idx]
        p = issue["para"]
        start = issue["start"]
        end = issue["end"]

        delete_range_in_paragraph(p, start, end)
        insert_text_in_paragraph(p, start, rep)
        if self.controller:
            self.controller.pos = DocPos(p.id, start + len(rep))
            self.controller.selection = Selection(self.controller.pos, self.controller.pos)
            self.controller.repaginate_and_refresh()

        self.show_next_issue()

    def _on_change_all(self) -> None:
        rep = self._get_selected_replacement()
        if not rep or self.current_idx >= len(self.issues):
            return

        target_word = self.issues[self.current_idx]["word"]
        paras = all_paragraphs(self.doc)
        for p in paras:
            pt = ptext(p)
            while True:
                pos = pt.find(target_word)
                if pos < 0:
                    break
                delete_range_in_paragraph(p, pos, pos + len(target_word))
                insert_text_in_paragraph(p, pos, rep)
                pt = ptext(p)

        self.spell_engine.ignore_all(target_word)
        if self.controller:
            self.controller.repaginate_and_refresh()

        self.show_next_issue()

    def _on_autocorrect(self) -> None:
        rep = self._get_selected_replacement()
        if not rep or self.current_idx >= len(self.issues):
            return

        target_word = self.issues[self.current_idx]["word"]
        self.autocorrect_engine.typos[target_word.lower()] = rep
        self._on_change()

    def retranslate_ui(self) -> None:
        """Update localized UI text strings."""
        self.setWindowTitle(safe_tr("拼写和语法检查: 英语 (美国)"))
        self.lbl_status.setText(safe_tr("不在词典中:"))
        self.lbl_sugg.setText(safe_tr("建议(&N):"))
        self.lbl_lang.setText(safe_tr("词典语言: 英语 (美国)"))
        self.chk_grammar.setText(safe_tr("检查语法(&G)"))
        self.btn_ignore_once.setText(safe_tr("忽略一次(&I)"))
        self.btn_ignore_all.setText(safe_tr("全部忽略(&G)"))
        self.btn_add_dict.setText(safe_tr("添加到词典(&A)"))
        self.btn_change.setText(safe_tr("更改(&C)"))
        self.btn_change_all.setText(safe_tr("全部更改(&L)"))
        self.btn_autocorrect.setText(safe_tr("自动更正(&R)"))
        self.btn_cancel.setText(safe_tr("关闭(&X)"))
