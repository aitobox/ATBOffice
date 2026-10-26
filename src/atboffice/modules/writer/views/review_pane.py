"""Word 2003 styled Reviewing Pane, Review Toolbar, and Comment Balloons for Quire."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QCoreApplication, QLocale, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.writer.models.document import Document, Paragraph
from atboffice.modules.writer.models.revision import (
    BalloonItem,
    BalloonPlacement,
    Comment,
    RevisionItem,
    accept_all_revisions,
    accept_revision,
    author_color,
    comment_number,
    delete_all_comments,
    delete_comment,
    edit_comment,
    insert_comment,
    is_tracking,
    layout_balloons,
    list_authors,
    list_revisions,
    navigate_revision,
    reject_all_revisions,
    reject_revision,
    reply_comment,
    set_tracking,
    toggle_tracking,
)

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        "Reviewing Pane": "审阅窗格",
        "Close Reviewing Pane": "关闭审阅窗格",
        "Track Changes": "修订",
        "Track Changes (Ctrl+Shift+E)": "启用或停用修订追踪 (Ctrl+Shift+E)",
        "Track Changes is on": "修订已开启",
        "Track Changes is off": "修订已停用",
        "Display for Review": "显示以供审阅",
        "Final Showing Markup": "显示标记的最终状态",
        "Final": "最终状态",
        "Original Showing Markup": "显示标记的原始状态",
        "Original": "原始状态",
        "Show": "显示",
        "Comments": "批注",
        "Insertions and Deletions": "插入和删除",
        "Formatting": "格式修改",
        "Reviewers": "审阅者",
        "All Reviewers": "所有审阅者",
        "Previous": "上一个",
        "Previous change or comment": "定位到上一个修订或批注",
        "Next": "下一个",
        "Next change or comment": "定位到下一个修订或批注",
        "Accept": "接受",
        "Accept Change": "接受修订",
        "Accept All Changes": "接受文档中的所有修订",
        "Reject": "拒绝",
        "Reject Change": "拒绝修订",
        "Reject All Changes": "拒绝文档中的所有修订",
        "New Comment": "新建批注",
        "Insert a comment at selection": "在选区插入新批注",
        "Delete": "删除",
        "Delete Comment": "删除批注",
        "Delete All Comments": "删除文档中的所有批注",
        "Reply to Comment": "回复批注",
        "Edit Comment": "编辑批注",
        "There are no tracked changes or comments in this document.": "此文档中没有修订或批注。",
        "Inserted": "已插入",
        "Deleted": "已删除",
        "Formatted": "已设置格式",
        "Paragraph formatting": "段落格式",
        "Comment [{0}{1}]": "批注 [{0}{1}]",
        "Comment [{0}{1}] (reply)": "批注 [{0}{1}] (回复)",
        "OK": "确定",
        "Cancel": "取消",
        "Close": "关闭",
        "Total Changes:": "修订总数:",
        "Total Comments:": "批注总数:",
        "Summary": "摘要",
        "Main document changes and comments": "文档中的修订和批注",
    }
}


def safe_tr(text: str) -> str:
    """Translate UI text safely with context and Chinese fallback."""
    tr_text = QCoreApplication.translate("ReviewUI", text)
    if tr_text != text and tr_text:
        return tr_text
    locale = QLocale.system().name()
    if locale.startswith("zh") and text in _TRANSLATIONS["zh"]:
        return _TRANSLATIONS["zh"][text]
    return text


# ---------------------------------------------------------------------------
# Comment Edit Dialog
# ---------------------------------------------------------------------------
class CommentEditDialog(QDialog):
    """Small modal dialog to view and edit comment text."""

    def __init__(
        self,
        title: str,
        initial_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(360, 220)

        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(initial_text)
        layout.addWidget(self.editor)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_text(self) -> str:
        """Return the edited comment text."""
        return self.editor.toPlainText().strip()


# ---------------------------------------------------------------------------
# Review Toolbar
# ---------------------------------------------------------------------------
class ReviewToolbar(QToolBar):
    """Word 2003 styled Reviewing toolbar."""

    # Action Signals
    track_changes_toggled = Signal(bool)
    display_mode_changed = Signal(str)
    previous_requested = Signal()
    next_requested = Signal()
    accept_change_requested = Signal()
    accept_all_requested = Signal()
    reject_change_requested = Signal()
    reject_all_requested = Signal()
    new_comment_requested = Signal()
    delete_comment_requested = Signal()
    delete_all_comments_requested = Signal()
    review_pane_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReviewToolbar")
        self.setMovable(True)
        self.setFloatable(True)

        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        # 1. Track Changes Toggle
        self.act_track = QAction(self)
        self.act_track.setCheckable(True)
        self.act_track.toggled.connect(self.track_changes_toggled.emit)
        self.addAction(self.act_track)

        self.addSeparator()

        # 2. Display for Review Combobox
        self.combo_display = QComboBox(self)
        self.combo_display.addItems(
            [
                "Final Showing Markup",
                "Final",
                "Original Showing Markup",
                "Original",
            ]
        )
        self.combo_display.currentTextChanged.connect(self.display_mode_changed.emit)
        self.addWidget(self.combo_display)

        # 3. Show Markup Dropdown Menu
        self.btn_show = QToolButton(self)
        self.btn_show.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_show = QMenu(self.btn_show)
        self.act_show_comments = self.menu_show.addAction("Comments")
        self.act_show_comments.setCheckable(True)
        self.act_show_comments.setChecked(True)
        self.act_show_ins_del = self.menu_show.addAction("Insertions and Deletions")
        self.act_show_ins_del.setCheckable(True)
        self.act_show_ins_del.setChecked(True)
        self.act_show_formatting = self.menu_show.addAction("Formatting")
        self.act_show_formatting.setCheckable(True)
        self.act_show_formatting.setChecked(True)
        self.btn_show.setMenu(self.menu_show)
        self.addWidget(self.btn_show)

        self.addSeparator()

        # 4. Previous & Next Navigation
        self.act_prev = QAction(self)
        self.act_prev.triggered.connect(self.previous_requested.emit)
        self.addAction(self.act_prev)

        self.act_next = QAction(self)
        self.act_next.triggered.connect(self.next_requested.emit)
        self.addAction(self.act_next)

        self.addSeparator()

        # 5. Accept dropdown
        self.btn_accept = QToolButton(self)
        self.btn_accept.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menu_accept = QMenu(self.btn_accept)
        self.act_accept_this = self.menu_accept.addAction("Accept Change")
        self.act_accept_this.triggered.connect(self.accept_change_requested.emit)
        self.act_accept_all = self.menu_accept.addAction("Accept All Changes")
        self.act_accept_all.triggered.connect(self.accept_all_requested.emit)
        self.btn_accept.setMenu(self.menu_accept)
        self.btn_accept.setDefaultAction(self.act_accept_this)
        self.addWidget(self.btn_accept)

        # 6. Reject dropdown
        self.btn_reject = QToolButton(self)
        self.btn_reject.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menu_reject = QMenu(self.btn_reject)
        self.act_reject_this = self.menu_reject.addAction("Reject Change")
        self.act_reject_this.triggered.connect(self.reject_change_requested.emit)
        self.act_reject_all = self.menu_reject.addAction("Reject All Changes")
        self.act_reject_all.triggered.connect(self.reject_all_requested.emit)
        self.btn_reject.setMenu(self.menu_reject)
        self.btn_reject.setDefaultAction(self.act_reject_this)
        self.addWidget(self.btn_reject)

        self.addSeparator()

        # 7. New Comment button
        self.act_new_comment = QAction(self)
        self.act_new_comment.triggered.connect(self.new_comment_requested.emit)
        self.addAction(self.act_new_comment)

        # 8. Delete Comment dropdown
        self.btn_delete_comment = QToolButton(self)
        self.btn_delete_comment.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.menu_delete = QMenu(self.btn_delete_comment)
        self.act_del_this = self.menu_delete.addAction("Delete Comment")
        self.act_del_this.triggered.connect(self.delete_comment_requested.emit)
        self.act_del_all = self.menu_delete.addAction("Delete All Comments")
        self.act_del_all.triggered.connect(self.delete_all_comments_requested.emit)
        self.btn_delete_comment.setMenu(self.menu_delete)
        self.btn_delete_comment.setDefaultAction(self.act_del_this)
        self.addWidget(self.btn_delete_comment)

        self.addSeparator()

        # 9. Reviewing Pane toggle
        self.act_pane = QAction(self)
        self.act_pane.setCheckable(True)
        self.act_pane.toggled.connect(self.review_pane_toggled.emit)
        self.addAction(self.act_pane)

    def set_tracking_state(self, tracking: bool) -> None:
        """Update toggle button checked state without re-emitting signal."""
        self.act_track.blockSignals(True)
        self.act_track.setChecked(tracking)
        self.act_track.blockSignals(False)

    def set_pane_state(self, visible: bool) -> None:
        """Update pane toggle checked state."""
        self.act_pane.blockSignals(True)
        self.act_pane.setChecked(visible)
        self.act_pane.blockSignals(False)

    def retranslate_ui(self) -> None:
        """Translate all toolbar buttons, menus, tooltips, and combobox entries."""
        self.setWindowTitle(safe_tr("Reviewing"))
        self.act_track.setText(safe_tr("Track Changes"))
        self.act_track.setToolTip(safe_tr("Track Changes (Ctrl+Shift+E)"))

        # Combobox display items
        cur_idx = self.combo_display.currentIndex()
        self.combo_display.blockSignals(True)
        self.combo_display.clear()
        self.combo_display.addItems(
            [
                safe_tr("Final Showing Markup"),
                safe_tr("Final"),
                safe_tr("Original Showing Markup"),
                safe_tr("Original"),
            ]
        )
        if 0 <= cur_idx < self.combo_display.count():
            self.combo_display.setCurrentIndex(cur_idx)
        self.combo_display.blockSignals(False)

        self.btn_show.setText(safe_tr("Show"))
        self.act_show_comments.setText(safe_tr("Comments"))
        self.act_show_ins_del.setText(safe_tr("Insertions and Deletions"))
        self.act_show_formatting.setText(safe_tr("Formatting"))

        self.act_prev.setText(safe_tr("Previous"))
        self.act_prev.setToolTip(safe_tr("Previous change or comment"))
        self.act_next.setText(safe_tr("Next"))
        self.act_next.setToolTip(safe_tr("Next change or comment"))

        self.act_accept_this.setText(safe_tr("Accept Change"))
        self.act_accept_all.setText(safe_tr("Accept All Changes"))
        self.btn_accept.setText(safe_tr("Accept"))

        self.act_reject_this.setText(safe_tr("Reject Change"))
        self.act_reject_all.setText(safe_tr("Reject All Changes"))
        self.btn_reject.setText(safe_tr("Reject"))

        self.act_new_comment.setText(safe_tr("New Comment"))
        self.act_new_comment.setToolTip(safe_tr("Insert a comment at selection"))

        self.act_del_this.setText(safe_tr("Delete Comment"))
        self.act_del_all.setText(safe_tr("Delete All Comments"))
        self.btn_delete_comment.setText(safe_tr("Delete"))

        self.act_pane.setText(safe_tr("Reviewing Pane"))
        self.act_pane.setToolTip(safe_tr("Reviewing Pane"))


# ---------------------------------------------------------------------------
# Reviewing Pane
# ---------------------------------------------------------------------------
class ReviewPaneItemWidget(QWidget):
    """Custom widget rendered for each entry in the Reviewing Pane list."""

    def __init__(
        self,
        header_text: str,
        body_text: str,
        color_hex: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Header with colored dot and metadata
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(6)

        color_tag = QLabel(self)
        color_tag.setFixedSize(10, 10)
        color_tag.setStyleSheet(
            f"background-color: {color_hex}; border: 1px solid #777; border-radius: 2px;"
        )
        h_layout.addWidget(color_tag)

        self.lbl_head = QLabel(header_text, self)
        font_h = QFont()
        font_h.setBold(True)
        font_h.setPointSize(9)
        self.lbl_head.setFont(font_h)
        self.lbl_head.setStyleSheet(f"color: {color_hex};")
        h_layout.addWidget(self.lbl_head)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        # Body snippet
        self.lbl_body = QLabel(body_text, self)
        self.lbl_body.setWordWrap(True)
        font_b = QFont()
        font_b.setPointSize(9)
        self.lbl_body.setFont(font_b)
        layout.addWidget(self.lbl_body)


class ReviewPane(QWidget):
    """Word 2003 styled side / bottom Reviewing Pane."""

    # Navigation & Interaction signals
    item_activated = Signal(Paragraph, int, int)  # para, start, end
    comment_edit_requested = Signal(str)  # comment_id
    comment_reply_requested = Signal(str)  # parent comment_id
    revision_action_requested = Signal(object, bool)  # revision, accept

    def __init__(
        self,
        doc: Document | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.doc = doc
        self.setObjectName("ReviewPane")
        self.setMinimumWidth(260)

        self._build_ui()
        self.retranslate_ui()
        if self.doc:
            self.refresh_items()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # 1. Header with title and close button
        header_frame = QFrame(self)
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(6, 4, 4, 4)

        self.lbl_title = QLabel(self)
        font_t = QFont()
        font_t.setBold(True)
        self.lbl_title.setFont(font_t)
        h_layout.addWidget(self.lbl_title)

        h_layout.addStretch()

        self.btn_close = QPushButton("✕", self)
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet("border: none; font-weight: bold; font-size: 11px;")
        self.btn_close.clicked.connect(self.hide)
        h_layout.addWidget(self.btn_close)
        main_layout.addWidget(header_frame)

        # 2. Filter & Summary bar
        bar_layout = QHBoxLayout()
        bar_layout.setContentsMargins(2, 2, 2, 2)

        self.combo_authors = QComboBox(self)
        self.combo_authors.currentIndexChanged.connect(self._on_filter_changed)
        bar_layout.addWidget(self.combo_authors)

        self.lbl_summary = QLabel(self)
        self.lbl_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bar_layout.addWidget(self.lbl_summary)
        main_layout.addLayout(bar_layout)

        # 3. Item List Widget
        self.list_widget = QListWidget(self)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.list_widget)

    def set_document(self, doc: Document) -> None:
        """Set the active document and refresh."""
        self.doc = doc
        self.refresh_items()

    def refresh_items(self) -> None:
        """Populate the review items list from document revisions and comments."""
        self.list_widget.clear()
        if not self.doc:
            return

        # Update authors filter combobox
        current_author_filter = self.combo_authors.currentText()
        all_authors = list_authors(self.doc)
        self.combo_authors.blockSignals(True)
        self.combo_authors.clear()
        self.combo_authors.addItem(safe_tr("All Reviewers"))
        for a in all_authors:
            self.combo_authors.addItem(a)

        # Restore selection
        idx = self.combo_authors.findText(current_author_filter)
        self.combo_authors.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo_authors.blockSignals(False)

        selected_author = (
            None
            if self.combo_authors.currentIndex() <= 0
            else self.combo_authors.currentText()
        )

        # Collect revisions
        revs = list_revisions(self.doc)
        if selected_author:
            revs = [r for r in revs if r.stamp.author == selected_author]

        # Collect comments
        cmts = list(self.doc.comments.values())
        if selected_author:
            cmts = [c for c in cmts if getattr(c, "author", "") == selected_author]

        # Summary label
        self.lbl_summary.setText(
            f"{safe_tr('Total Changes:')} {len(revs)} | {safe_tr('Total Comments:')} {len(cmts)}"
        )

        # Combined sorted items
        type_labels = {
            "ins": safe_tr("Inserted"),
            "del": safe_tr("Deleted"),
            "chg": safe_tr("Formatted"),
            "pchg": safe_tr("Paragraph formatting"),
            "mins": safe_tr("Inserted"),
            "mdel": safe_tr("Deleted"),
        }

        # Empty state
        if not revs and not cmts:
            empty_item = QListWidgetItem()
            empty_lbl = QLabel(safe_tr("There are no tracked changes or comments in this document."))
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet("color: #777; padding: 12px; font-style: italic;")
            empty_item.setSizeHint(empty_lbl.sizeHint())
            self.list_widget.addItem(empty_item)
            self.list_widget.setItemWidget(empty_item, empty_lbl)
            return

        # Add Revisions
        for r in revs:
            color = author_color(r.stamp.author)
            action_desc = type_labels.get(r.type, r.type)
            date_str = r.stamp.date[:10] if r.stamp.date else ""
            header = f"[{action_desc}] {r.stamp.author} {date_str}"
            body = r.text if r.text else ("¶" if r.type in {"mins", "mdel"} else "")

            item = QListWidgetItem()
            widget = ReviewPaneItemWidget(header, body, color, self)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, ("rev", r))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        # Add Comments
        for c in cmts:
            cid = getattr(c, "id", "0")
            num = comment_number(self.doc, cid)
            author = getattr(c, "author", "Author")
            initials = getattr(c, "initials", "") or author[:2].upper()
            color = author_color(author)
            is_reply = bool(getattr(c, "parent", None))
            template = (
                safe_tr("Comment [{0}{1}] (reply)")
                if is_reply
                else safe_tr("Comment [{0}{1}]")
            )
            head_title = template.format(initials, num)
            header = f"{head_title} {author}"
            body = c.text if isinstance(c, Comment) else str(c)

            item = QListWidgetItem()
            widget = ReviewPaneItemWidget(header, body, color, self)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, ("cmt", c))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _on_filter_changed(self) -> None:
        self.refresh_items()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, obj = data
        if kind == "rev":
            rev: RevisionItem = obj
            self.item_activated.emit(rev.para, rev.start, rev.end)
        elif kind == "cmt":
            cid = getattr(obj, "id", "0")
            # Locate comment range start
            if self.doc:
                for p in self.doc.main.paras:
                    o = 0
                    for it in p.runs:
                        if hasattr(it, "comment_id") and str(it.comment_id) == str(cid):
                            self.item_activated.emit(p, o, o)
                            return
                        from atboffice.modules.writer.models.document import ilen
                        o += ilen(it)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, obj = data
        if kind == "cmt":
            cid = getattr(obj, "id", "0")
            self.comment_edit_requested.emit(str(cid))

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, obj = data

        menu = QMenu(self)
        if kind == "rev":
            rev: RevisionItem = obj
            act_accept = menu.addAction(safe_tr("Accept Change"))
            act_accept.triggered.connect(
                lambda: self._handle_rev_action(rev, accept=True)
            )
            act_reject = menu.addAction(safe_tr("Reject Change"))
            act_reject.triggered.connect(
                lambda: self._handle_rev_action(rev, accept=False)
            )
        elif kind == "cmt":
            cid = str(getattr(obj, "id", "0"))
            act_edit = menu.addAction(safe_tr("Edit Comment"))
            act_edit.triggered.connect(lambda: self.comment_edit_requested.emit(cid))
            act_reply = menu.addAction(safe_tr("Reply to Comment"))
            act_reply.triggered.connect(lambda: self.comment_reply_requested.emit(cid))
            menu.addSeparator()
            act_del = menu.addAction(safe_tr("Delete Comment"))
            act_del.triggered.connect(lambda: self._handle_del_comment(cid))

        menu.exec(self.list_widget.mapToGlobal(pos))

    def _handle_rev_action(self, rev: RevisionItem, accept: bool) -> None:
        if self.doc:
            if accept:
                accept_revision(self.doc, rev)
            else:
                reject_revision(self.doc, rev)
            self.refresh_items()
            self.revision_action_requested.emit(rev, accept)

    def _handle_del_comment(self, comment_id: str) -> None:
        if self.doc:
            delete_comment(self.doc, comment_id)
            self.refresh_items()

    def retranslate_ui(self) -> None:
        """Translate pane header, buttons, and summary strings."""
        self.setWindowTitle(safe_tr("Reviewing Pane"))
        self.lbl_title.setText(safe_tr("Main document changes and comments"))
        self.btn_close.setToolTip(safe_tr("Close Reviewing Pane"))
        if self.combo_authors.count() > 0:
            self.combo_authors.setItemText(0, safe_tr("All Reviewers"))
        if self.doc:
            self.refresh_items()


# ---------------------------------------------------------------------------
# Comment Balloon Overlay Widget
# ---------------------------------------------------------------------------
class CommentBalloonWidget(QFrame):
    """Renderable comment balloon card displayed in the page margin."""

    clicked = Signal(str)  # comment_id
    double_clicked = Signal(str)  # comment_id

    def __init__(
        self,
        placement: BalloonPlacement,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.placement = placement
        self.setObjectName(f"Balloon_{placement.id}")
        self.setFrameShape(QFrame.Shape.Box)

        # Style card border with author color and soft warm background
        self.setStyleSheet(
            f"""
            QFrame#Balloon_{placement.id} {{
                background-color: #FFFDF4;
                border: 1.5px solid {placement.color};
                border-radius: 4px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Header: Comment [AU1]: Author, Date
        head_text = (
            safe_tr("Comment [{0}{1}] (reply):").format(
                placement.initials, placement.id
            )
            if placement.reply
            else safe_tr("Comment [{0}{1}]:").format(
                placement.initials, placement.id
            )
        )
        lbl_head = QLabel(f"{head_text} {placement.author}", self)
        font_h = QFont()
        font_h.setBold(True)
        font_h.setPointSize(8)
        lbl_head.setFont(font_h)
        lbl_head.setStyleSheet(f"color: {placement.color};")
        layout.addWidget(lbl_head)

        # Body: Text
        lbl_body = QLabel(placement.text, self)
        lbl_body.setWordWrap(True)
        font_b = QFont()
        font_b.setPointSize(8)
        lbl_body.setFont(font_b)
        layout.addWidget(lbl_body)

    def mousePressEvent(self, event: Any) -> None:
        self.clicked.emit(self.placement.id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.double_clicked.emit(self.placement.id)
        super().mouseDoubleClickEvent(event)
