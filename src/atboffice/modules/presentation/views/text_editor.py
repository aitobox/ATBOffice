"""In-place rich text editor, outline list indent, and Text AutoFit for Lectern shapes."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QFont,
    QKeyEvent,
    QPainter,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsTextItem,
    QMenu,
)

from atboffice.modules.presentation.models.text import (
    BODY_BULLETS,
    BODY_INDENT,
    BODY_MARL,
    BODY_SIZES,
    Paragraph,
    TextBody,
    TextRun,
)

if TYPE_CHECKING:
    from atboffice.modules.presentation.views.shape_item import ShapeGraphicsItem


# Custom QTextFormat property keys
PROP_OUTLINE_LEVEL = QTextFormat.Property.UserProperty + 1
PROP_BULLET_TYPE = QTextFormat.Property.UserProperty + 2
PROP_BULLET_CHAR = QTextFormat.Property.UserProperty + 3
PROP_TEXT_SHADOW = QTextFormat.Property.UserProperty + 4

STANDARD_FONT_SIZES = [
    8.0, 9.0, 10.0, 11.0, 12.0, 14.0, 16.0, 18.0, 20.0,
    24.0, 28.0, 32.0, 36.0, 40.0, 44.0, 48.0, 54.0, 60.0, 66.0, 72.0, 80.0, 88.0, 96.0,
]


def safe_tr(text: str) -> str:
    """Translate user-facing text with native Chinese fallback."""
    app = QApplication.instance()
    if app:
        translated = app.translate("TextEditor", text)
        if translated and translated != text:
            return translated
    # Translation dictionary for common actions
    translations = {
        "Bold": "加粗",
        "Italic": "倾斜",
        "Underline": "下划线",
        "Increase Font Size": "增大字号",
        "Decrease Font Size": "减小字号",
        "Font Color": "字体颜色",
        "Increase Indent": "增加缩进 (降级)",
        "Decrease Indent": "减少缩进 (升级)",
        "Bullets": "项目符号",
        "Numbering": "编号",
        "Align Left": "左对齐",
        "Center": "居中",
        "Align Right": "右对齐",
        "Justify": "两端对齐",
        "Reset Formatting": "清除格式",
        "Cut": "剪切",
        "Copy": "复制",
        "Paste": "粘贴",
        "Select All": "全选",
    }
    return translations.get(text, text)


def clamp_outline_level(level: int) -> int:
    """Clamp an outline level between 0 and 8 (PowerPoint 9 levels)."""
    return max(0, min(8, int(level)))


def calculate_autofit_scale(
    need_height: float,
    avail_height: float,
    current_scale: float = 1.0,
    min_scale: float = 0.25,
    max_scale: float = 1.0,
) -> float:
    """Calculate PowerPoint-style shrink text on overflow factor.

    Reference: .vibeoffice/public/lectern/js/textedit.js shrinkToFit
    - When need_height <= avail_height and current_scale is 1.0, returns 1.0.
    - When need_height > avail_height, quantizes scale down to 0.05 step
      down to min_scale (default 0.25).
    - When need_height < avail_height and current_scale < 1.0, scales back up.
    """
    if need_height <= 0.0 or avail_height <= 0.0:
        return 1.0

    if need_height <= avail_height + 1.0 and abs(current_scale - 1.0) < 0.01:
        return 1.0

    raw_ratio = current_scale * (avail_height / need_height)
    # Quantize to 0.05 increments: Math.floor(x * 20) / 20
    stepped = math.floor(raw_ratio * 20.0) / 20.0

    if need_height > avail_height + 1.0:
        scale = max(min_scale, stepped)
    elif current_scale < 1.0:
        scale = min(max_scale, stepped)
    else:
        scale = current_scale

    if scale >= 0.99:
        return 1.0
    return round(scale, 3)


def calculate_shape_autofit_size(
    content_width: float,
    content_height: float,
    insets: tuple[float, float, float, float] = (7.2, 3.6, 7.2, 3.6),
    min_width: float = 18.0,
    min_height: float = 10.0,
    wrap: bool = True,
) -> tuple[float, float]:
    """Calculate shape auto-size dimensions when autofit == 'shape'."""
    ins_left, ins_top, ins_right, ins_bottom = insets
    h = max(min_height, content_height + ins_top + ins_bottom)
    w = max(min_width, content_width + ins_left + ins_right + (1.0 if not wrap else 0.0))
    return round(w, 2), round(h, 2)


def resolve_color(color_name: str | None) -> QColor:
    """Resolve color name or hex code to QColor."""
    if not color_name:
        return QColor("#000000")
    if color_name.startswith("#") or color_name.startswith("rgb"):
        return QColor(color_name)
    preset_map = {
        "tx1": "#000000",
        "tx2": "#595959",
        "bg1": "#FFFFFF",
        "bg2": "#EBEBEB",
        "accent1": "#2B579A",
        "accent2": "#D24726",
        "accent3": "#008A00",
        "accent4": "#825A2C",
        "accent5": "#002050",
        "accent6": "#E2B200",
        "white": "#FFFFFF",
        "black": "#000000",
        "red": "#FF0000",
        "blue": "#0000FF",
        "green": "#008000",
    }
    return QColor(preset_map.get(color_name.lower(), "#000000"))


class ShapeTextEditorItem(QGraphicsTextItem):
    """In-place interactive rich text editor attached to a ShapeGraphicsItem."""

    editingFinished = Signal(str, object)  # (shape_id, TextBody)
    formatChanged = Signal()

    def __init__(
        self,
        shape_item: ShapeGraphicsItem,
        parent: QGraphicsItem | None = None,
    ) -> None:
        import copy

        super().__init__(parent or shape_item)
        self.shape_item = shape_item
        self.shape = shape_item.shape
        self._is_finishing = False
        self._orig_text_body = copy.deepcopy(self.shape.text) if self.shape.text else None

        self.setZValue(200.0)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setTabChangesFocus(False)  # Intercept Tab for outline demote/promote

        # Layout positioning
        self._sync_geometry_from_shape()

        # Load text model into document
        self.load_from_text_body(self.shape.text)

        # Connect contents change
        self.document().contentsChanged.connect(self._on_contents_changed)

    def _sync_geometry_from_shape(self) -> None:
        """Update editor position and bounds matching shape insets."""
        w = max(10.0, self.shape.w)
        insets = self.shape.text.insets if self.shape.text else (7.2, 3.6, 7.2, 3.6)
        ins_l, ins_t, ins_r, ins_b = insets

        avail_w = max(10.0, w - ins_l - ins_r)
        self.setPos(ins_l, ins_t)
        self.setTextWidth(avail_w)

    # ------------------------------------------------------------------
    # Static Rendering Helper
    # ------------------------------------------------------------------
    @staticmethod
    def render_static_text(
        painter: QPainter,
        text_body: TextBody,
        text_rect: QRectF,
        color_resolver: Any = resolve_color,
    ) -> None:
        """Render formatted multiline text for static canvas painting."""
        if not text_body or text_body.is_empty():
            return

        doc = QTextDocument()
        avail_w = max(10.0, text_rect.width())
        avail_h = max(10.0, text_rect.height())
        doc.setTextWidth(avail_w)

        font_scale = text_body.font_scale or 1.0
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        paragraphs = text_body.paragraphs if text_body.paragraphs else [Paragraph(level=0)]
        for p_idx, para in enumerate(paragraphs):
            if p_idx > 0:
                cursor.insertBlock()

            level = clamp_outline_level(para.level)
            block_fmt = QTextBlockFormat()

            # Alignment
            algn = para.props.get("algn", "l")
            if algn == "ctr":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            elif algn == "r":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight)
            elif algn == "just":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
            else:
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)

            mar_l = (
                para.props.get("marL", BODY_MARL[level])
                if "marL" in para.props
                else BODY_MARL[level]
            ) * font_scale
            indent = (
                para.props.get("indent", BODY_INDENT[level])
                if "indent" in para.props
                else BODY_INDENT[level]
            ) * font_scale
            block_fmt.setLeftMargin(mar_l)
            block_fmt.setTextIndent(indent)
            cursor.setBlockFormat(block_fmt)

            # Bullet
            bu_info = para.props.get("bu")
            bu_type = bu_info.get("t", "none") if isinstance(bu_info, dict) else "none"
            bu_char = (
                bu_info.get("ch", BODY_BULLETS[level])
                if isinstance(bu_info, dict)
                else BODY_BULLETS[level]
            )

            runs = para.runs if para.runs else [TextRun()]
            for r_idx, run in enumerate(runs):
                char_fmt = QTextCharFormat()
                fam = run.font or "Tahoma"
                if hasattr(char_fmt, "setFontFamilies"):
                    char_fmt.setFontFamilies([fam])
                else:
                    char_fmt.setFontFamily(fam)

                sz = (run.size if run.size is not None else BODY_SIZES[level]) * font_scale
                char_fmt.setFontPointSize(sz)
                if run.bold:
                    char_fmt.setFontWeight(QFont.Weight.Bold)
                if run.italic:
                    char_fmt.setFontItalic(True)
                if run.underline:
                    char_fmt.setFontUnderline(True)
                if run.strike:
                    char_fmt.setFontStrikeOut(True)
                char_fmt.setForeground(color_resolver(run.color))

                prefix = ""
                if r_idx == 0 and bu_type == "char" and bu_char:
                    prefix = f"{bu_char} "

                cursor.insertText(prefix + run.text, char_fmt)

        cursor.endEditBlock()

        painter.save()
        doc_h = doc.size().height()
        dy = 0.0
        if text_body.anchor == "ctr":
            dy = max(0.0, (avail_h - doc_h) / 2.0)
        elif text_body.anchor == "b":
            dy = max(0.0, avail_h - doc_h)

        painter.translate(text_rect.x(), text_rect.y() + dy)
        doc.drawContents(painter, QRectF(0.0, 0.0, avail_w, avail_h))
        painter.restore()

    # ------------------------------------------------------------------
    # Document <-> TextBody Serialization
    # ------------------------------------------------------------------
    def load_from_text_body(self, text_body: TextBody | None) -> None:
        """Populate QTextDocument from a TextBody model."""
        tb = text_body or TextBody.create_empty()
        font_scale = tb.font_scale if tb else 1.0

        doc = self.document()
        doc.clear()

        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        paragraphs = tb.paragraphs if (tb and tb.paragraphs) else [Paragraph(level=0)]

        for p_idx, para in enumerate(paragraphs):
            if p_idx > 0:
                cursor.insertBlock()

            level = clamp_outline_level(para.level)
            block_fmt = QTextBlockFormat()

            # Outline level & margins
            block_fmt.setProperty(PROP_OUTLINE_LEVEL, level)
            mar_l = (
                para.props.get("marL", BODY_MARL[level])
                if "marL" in para.props
                else BODY_MARL[level]
            ) * font_scale
            indent = (
                para.props.get("indent", BODY_INDENT[level])
                if "indent" in para.props
                else BODY_INDENT[level]
            ) * font_scale
            block_fmt.setLeftMargin(mar_l)
            block_fmt.setTextIndent(indent)

            # Alignment
            algn = para.props.get("algn", "l")
            if algn == "ctr":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
            elif algn == "r":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight)
            elif algn == "just":
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
            else:
                block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)

            # Bullets
            bu_info = para.props.get("bu")
            bu_type = bu_info.get("t", "none") if isinstance(bu_info, dict) else "none"
            bu_char = (
                bu_info.get("ch", BODY_BULLETS[level])
                if isinstance(bu_info, dict)
                else BODY_BULLETS[level]
            )
            block_fmt.setProperty(PROP_BULLET_TYPE, bu_type)
            block_fmt.setProperty(PROP_BULLET_CHAR, bu_char)

            cursor.setBlockFormat(block_fmt)
            cursor.block().setUserState(level)

            # Runs
            runs = para.runs if para.runs else [TextRun()]
            for run in runs:
                char_fmt = QTextCharFormat()
                family = run.font or "Tahoma"
                if hasattr(char_fmt, "setFontFamilies"):
                    char_fmt.setFontFamilies([family])
                else:
                    char_fmt.setFontFamily(family)

                sz = (run.size if run.size is not None else BODY_SIZES[level]) * font_scale
                char_fmt.setFontPointSize(sz)

                if run.bold:
                    char_fmt.setFontWeight(QFont.Weight.Bold)
                if run.italic:
                    char_fmt.setFontItalic(True)
                if run.underline:
                    char_fmt.setFontUnderline(True)
                if run.strike:
                    char_fmt.setFontStrikeOut(True)

                c = resolve_color(run.color)
                char_fmt.setForeground(c)

                if run.text:
                    cursor.insertText(run.text, char_fmt)
                else:
                    cursor.setCharFormat(char_fmt)

        cursor.endEditBlock()

        # Set caret at end
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)

    def to_text_body(self) -> TextBody:
        """Convert QTextDocument contents back to an ATBOffice TextBody model."""
        orig_tb = self.shape.text
        anchor = orig_tb.anchor if orig_tb else "t"
        wrap = orig_tb.wrap if orig_tb else True
        autofit = orig_tb.autofit if orig_tb else "none"
        insets = orig_tb.insets if orig_tb else (7.2, 3.6, 7.2, 3.6)
        vert = orig_tb.vert if orig_tb else None
        font_scale = orig_tb.font_scale if orig_tb else 1.0

        paragraphs: list[Paragraph] = []
        doc = self.document()

        block = doc.begin()
        while block.isValid():
            block_fmt = block.blockFormat()
            level = clamp_outline_level(
                block_fmt.property(PROP_OUTLINE_LEVEL)
                if block_fmt.hasProperty(PROP_OUTLINE_LEVEL)
                else block.userState()
            )

            # Alignment
            qt_align = block_fmt.alignment()
            if qt_align & Qt.AlignmentFlag.AlignCenter:
                algn = "ctr"
            elif qt_align & Qt.AlignmentFlag.AlignRight:
                algn = "r"
            elif qt_align & Qt.AlignmentFlag.AlignJustify:
                algn = "just"
            else:
                algn = "l"

            props: dict[str, Any] = {"algn": algn}

            bu_type = block_fmt.property(PROP_BULLET_TYPE) or "none"
            bu_char = block_fmt.property(PROP_BULLET_CHAR) or BODY_BULLETS[level]
            if bu_type != "none":
                props["bu"] = {"t": bu_type, "ch": bu_char}

            runs: list[TextRun] = []
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    txt = frag.text()
                    cf = frag.charFormat()
                    raw_sz = cf.fontPointSize()
                    norm_sz = round(raw_sz / font_scale, 1) if raw_sz > 0 else BODY_SIZES[level]
                    color_hex = cf.foreground().color().name().upper()

                    fam = None
                    if hasattr(cf, "fontFamilies") and cf.fontFamilies():
                        fam = cf.fontFamilies()[0]
                    if not fam:
                        fam = cf.fontFamily() or "Tahoma"

                    runs.append(
                        TextRun(
                            text=txt,
                            font=fam,
                            size=norm_sz,
                            color=color_hex,
                            bold=cf.fontWeight() >= QFont.Weight.Bold,
                            italic=cf.fontItalic(),
                            underline=cf.fontUnderline(),
                            strike=cf.fontStrikeOut(),
                        )
                    )
                it += 1

            if not runs and block.length() <= 1:
                runs = []

            paragraphs.append(Paragraph(level=level, props=props, runs=runs))
            block = block.next()

        return TextBody(
            anchor=anchor,
            wrap=wrap,
            autofit=autofit,
            insets=insets,
            paragraphs=paragraphs,
            vert=vert,
            font_scale=font_scale,
        )

    # ------------------------------------------------------------------
    # Formatting APIs
    # ------------------------------------------------------------------
    def set_bold(self, enabled: bool | None = None) -> None:
        """Toggle or set bold weight on selected text or current word."""
        cursor = self.textCursor()
        cf = cursor.charFormat()
        current_bold = cf.fontWeight() >= QFont.Weight.Bold
        new_val = (not current_bold) if enabled is None else bool(enabled)

        new_fmt = QTextCharFormat()
        new_fmt.setFontWeight(QFont.Weight.Bold if new_val else QFont.Weight.Normal)
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def set_italic(self, enabled: bool | None = None) -> None:
        """Toggle or set italic style on selected text."""
        cursor = self.textCursor()
        cf = cursor.charFormat()
        new_val = (not cf.fontItalic()) if enabled is None else bool(enabled)

        new_fmt = QTextCharFormat()
        new_fmt.setFontItalic(new_val)
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def set_underline(self, enabled: bool | None = None) -> None:
        """Toggle or set underline on selected text."""
        cursor = self.textCursor()
        cf = cursor.charFormat()
        new_val = (not cf.fontUnderline()) if enabled is None else bool(enabled)

        new_fmt = QTextCharFormat()
        new_fmt.setFontUnderline(new_val)
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def set_font_size(self, size: float) -> None:
        """Set font point size for selected text."""
        if size <= 0:
            return
        font_scale = self.shape.text.font_scale if self.shape.text else 1.0
        new_fmt = QTextCharFormat()
        new_fmt.setFontPointSize(size * font_scale)
        cursor = self.textCursor()
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def step_font_size(self, direction: int) -> None:
        """Step font size up (+1) or down (-1) through standard size ladder."""
        cursor = self.textCursor()
        cur_sz = cursor.charFormat().fontPointSize() or 18.0
        font_scale = self.shape.text.font_scale if self.shape.text else 1.0
        base_sz = cur_sz / font_scale

        if direction > 0:
            next_sz = next((s for s in STANDARD_FONT_SIZES if s > base_sz + 0.1), base_sz + 4.0)
        else:
            next_sz = next(
                (s for s in reversed(STANDARD_FONT_SIZES) if s < base_sz - 0.1),
                max(6.0, base_sz - 2.0),
            )
        self.set_font_size(next_sz)

    def selectAll(self) -> None:
        """Select all text in document."""
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(cursor)

    def cut(self) -> None:
        """Cut selected text to system clipboard."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            app = QApplication.instance()
            if app:
                app.clipboard().setText(cursor.selectedText())
            cursor.removeSelectedText()

    def copy(self) -> None:
        """Copy selected text to system clipboard."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            app = QApplication.instance()
            if app:
                app.clipboard().setText(cursor.selectedText())

    def paste(self) -> None:
        """Paste text from system clipboard."""
        app = QApplication.instance()
        if app:
            clip_text = app.clipboard().text()
            if clip_text:
                self.textCursor().insertText(clip_text)

    def set_font_family(self, family: str) -> None:
        """Set font family for selected text."""
        new_fmt = QTextCharFormat()
        if hasattr(new_fmt, "setFontFamilies"):
            new_fmt.setFontFamilies([family])
        else:
            new_fmt.setFontFamily(family)
        cursor = self.textCursor()
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def set_font_color(self, color_name: str) -> None:
        """Set text color for selected text."""
        c = resolve_color(color_name)
        new_fmt = QTextCharFormat()
        new_fmt.setForeground(c)
        cursor = self.textCursor()
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def set_text_shadow(self, enabled: bool) -> None:
        """Set shadow metadata for selected text."""
        new_fmt = QTextCharFormat()
        new_fmt.setProperty(PROP_TEXT_SHADOW, bool(enabled))
        cursor = self.textCursor()
        cursor.mergeCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    def reset_formatting(self) -> None:
        """Reset character formatting back to level default."""
        cursor = self.textCursor()
        block = cursor.block()
        level = clamp_outline_level(block.userState())
        font_scale = self.shape.text.font_scale if self.shape.text else 1.0

        new_fmt = QTextCharFormat()
        new_fmt.setFontFamily("Tahoma")
        new_fmt.setFontPointSize(BODY_SIZES[level] * font_scale)
        new_fmt.setFontWeight(QFont.Weight.Normal)
        new_fmt.setFontItalic(False)
        new_fmt.setFontUnderline(False)
        new_fmt.setFontStrikeOut(False)
        new_fmt.setForeground(QColor("#000000"))
        cursor.setCharFormat(new_fmt)
        self.setTextCursor(cursor)
        self.formatChanged.emit()

    # ------------------------------------------------------------------
    # Outline & List Indent (Demote / Promote)
    # ------------------------------------------------------------------
    def demote(self) -> None:
        """Increase indent / decrease outline rank (Tab / Alt+Shift+Right)."""
        self.indent(1)

    def promote(self) -> None:
        """Decrease indent / increase outline rank (Shift+Tab / Alt+Shift+Left)."""
        self.indent(-1)

    def indent(self, delta: int) -> None:
        """Adjust outline level of all paragraphs spanned by selection."""
        cursor = self.textCursor()
        doc = self.document()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()

        start_block = doc.findBlock(start)
        end_block = doc.findBlock(end)

        cursor.beginEditBlock()
        font_scale = self.shape.text.font_scale if self.shape.text else 1.0

        block = start_block
        while block.isValid():
            cur_level = clamp_outline_level(block.userState())
            new_level = clamp_outline_level(cur_level + delta)

            block_fmt = block.blockFormat()
            block_fmt.setProperty(PROP_OUTLINE_LEVEL, new_level)
            block_fmt.setLeftMargin(BODY_MARL[new_level] * font_scale)
            block_fmt.setTextIndent(BODY_INDENT[new_level] * font_scale)

            # Auto-update bullet character for the new level if char bullet is active
            bu_type = block_fmt.property(PROP_BULLET_TYPE) or "char"
            if bu_type == "char":
                block_fmt.setProperty(PROP_BULLET_CHAR, BODY_BULLETS[new_level])

            temp_cursor = QTextCursor(block)
            temp_cursor.setBlockFormat(block_fmt)
            block.setUserState(new_level)

            # Update font sizes within block if using standard level size
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    cf = frag.charFormat()
                    cur_sz = cf.fontPointSize()
                    # If matches old level size or default, update to new level size
                    old_expected = BODY_SIZES[cur_level] * font_scale
                    if abs(cur_sz - old_expected) < 0.5 or cur_sz <= 0:
                        cf.setFontPointSize(BODY_SIZES[new_level] * font_scale)
                        frag_cursor = QTextCursor(doc)
                        frag_cursor.setPosition(frag.position())
                        frag_cursor.setPosition(
                            frag.position() + frag.length(),
                            QTextCursor.MoveMode.KeepAnchor,
                        )
                        frag_cursor.setCharFormat(cf)
                it += 1

            if block == end_block:
                break
            block = block.next()

        cursor.endEditBlock()
        self.formatChanged.emit()

    def set_alignment(self, align: str) -> None:
        """Set paragraph alignment ('l', 'ctr', 'r', 'just')."""
        cursor = self.textCursor()
        block_fmt = cursor.blockFormat()
        if align == "ctr":
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        elif align == "r":
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif align == "just":
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignJustify)
        else:
            block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cursor.setBlockFormat(block_fmt)
        self.formatChanged.emit()

    def set_bullet_type(self, bu_type: str, char: str | None = None) -> None:
        """Toggle or set bullet formatting ('none', 'char', 'num')."""
        cursor = self.textCursor()
        block = cursor.block()
        level = clamp_outline_level(block.userState())

        block_fmt = block.blockFormat()
        block_fmt.setProperty(PROP_BULLET_TYPE, bu_type)
        if char:
            block_fmt.setProperty(PROP_BULLET_CHAR, char)
        elif bu_type == "char":
            block_fmt.setProperty(PROP_BULLET_CHAR, BODY_BULLETS[level])

        cursor.setBlockFormat(block_fmt)
        self.formatChanged.emit()

    # ------------------------------------------------------------------
    # AutoFit Execution
    # ------------------------------------------------------------------
    def apply_autofit(self, mode: str | None = None) -> None:
        """Calculate and apply Text AutoFit scaling or shape auto-sizing."""
        af_mode = mode or (self.shape.text.autofit if self.shape.text else "norm")
        insets = self.shape.text.insets if self.shape.text else (7.2, 3.6, 7.2, 3.6)
        ins_l, ins_t, ins_r, ins_b = insets

        avail_h = max(10.0, self.shape.h - ins_t - ins_b)
        need_h = self.document().size().height()

        if af_mode == "norm":
            cur_scale = self.shape.text.font_scale if self.shape.text else 1.0
            new_scale = calculate_autofit_scale(need_h, avail_h, cur_scale)
            if abs(new_scale - cur_scale) > 0.01:
                if self.shape.text:
                    self.shape.text.font_scale = new_scale
                # Re-scale document fonts
                self._rescale_document(new_scale / cur_scale)
        elif af_mode == "shape":
            avail_w = self.document().idealWidth()
            new_w, new_h = calculate_shape_autofit_size(
                avail_w,
                need_h,
                insets,
                wrap=self.shape.text.wrap if self.shape.text else True,
            )
            self.shape.w = new_w
            self.shape.h = new_h
            self.shape_item.update()

    def _rescale_document(self, ratio: float) -> None:
        """Multiply all font sizes and margins in the document by ratio."""
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()

        block = doc.begin()
        while block.isValid():
            bf = block.blockFormat()
            bf.setLeftMargin(bf.leftMargin() * ratio)
            bf.setTextIndent(bf.textIndent() * ratio)
            tc = QTextCursor(block)
            tc.setBlockFormat(bf)

            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    cf = frag.charFormat()
                    sz = cf.fontPointSize()
                    if sz > 0:
                        cf.setFontPointSize(round(sz * ratio, 1))
                        frag_cursor = QTextCursor(doc)
                        frag_cursor.setPosition(frag.position())
                        frag_cursor.setPosition(
                            frag.position() + frag.length(),
                            QTextCursor.MoveMode.KeepAnchor,
                        )
                        frag_cursor.setCharFormat(cf)
                it += 1
            block = block.next()

        cursor.endEditBlock()

    # ------------------------------------------------------------------
    # Lifecycle & Commit
    # ------------------------------------------------------------------
    def commit_and_finish(self) -> None:
        """Sync changes back to shape.text model and end in-place editing."""
        if self._is_finishing:
            return
        self._is_finishing = True
        updated_tb = self.to_text_body()
        self.shape.text = updated_tb

        # Run AutoFit before closing
        self.apply_autofit()

        # Emit completion signal
        self.editingFinished.emit(self.shape.id, self.shape.text)

        # Notify parent shape item
        self.shape_item.finish_text_editing()

    def cancel_editing(self) -> None:
        """Cancel editing without committing newly typed changes."""
        if self._is_finishing:
            return
        self._is_finishing = True
        if self._orig_text_body is not None:
            self.shape.text = self._orig_text_body
        self.shape_item.finish_text_editing()

    def _on_contents_changed(self) -> None:
        """Handle real-time document typing changes."""
        if self.shape.text and self.shape.text.autofit == "shape":
            self.apply_autofit("shape")

    # ------------------------------------------------------------------
    # Event Overrides
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        # 1. Escape: Cancel and rollback
        if key == Qt.Key.Key_Escape:
            event.accept()
            self.cancel_editing()
            return

        # 2. Tab & Shift+Tab: Demote / Promote
        if key == Qt.Key.Key_Tab:
            event.accept()
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.promote()
            else:
                self.demote()
            return

        # 3. Backspace: If at start of paragraph and level > 0, promote
        if key == Qt.Key.Key_Backspace and not modifiers:
            cursor = self.textCursor()
            if cursor.atBlockStart() and not cursor.hasSelection():
                level = clamp_outline_level(cursor.block().userState())
                if level > 0:
                    event.accept()
                    self.promote()
                    return

        # 4. Standard shortcuts (Ctrl+B, Ctrl+I, Ctrl+U)
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_B:
                event.accept()
                self.set_bold()
                return
            if key == Qt.Key.Key_I:
                event.accept()
                self.set_italic()
                return
            if key == Qt.Key.Key_U:
                event.accept()
                self.set_underline()
                return

        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Auto-commit when losing focus."""
        super().focusOutEvent(event)
        if not self._is_finishing:
            self.commit_and_finish()

    def contextMenuEvent(self, event: Any) -> None:
        """Display rich text formatting context menu."""
        menu = QMenu()
        self._populate_context_menu(menu)
        menu.exec(event.screenPos())

    def _populate_context_menu(self, menu: QMenu) -> None:
        """Build context menu with i18n support."""
        act_cut = menu.addAction(safe_tr("Cut"))
        act_cut.triggered.connect(self.cut)
        act_copy = menu.addAction(safe_tr("Copy"))
        act_copy.triggered.connect(self.copy)
        act_paste = menu.addAction(safe_tr("Paste"))
        act_paste.triggered.connect(self.paste)
        menu.addSeparator()

        act_bold = menu.addAction(safe_tr("Bold"))
        act_bold.triggered.connect(lambda: self.set_bold())
        act_italic = menu.addAction(safe_tr("Italic"))
        act_italic.triggered.connect(lambda: self.set_italic())
        act_underline = menu.addAction(safe_tr("Underline"))
        act_underline.triggered.connect(lambda: self.set_underline())
        menu.addSeparator()

        act_inc_sz = menu.addAction(safe_tr("Increase Font Size"))
        act_inc_sz.triggered.connect(lambda: self.step_font_size(1))
        act_dec_sz = menu.addAction(safe_tr("Decrease Font Size"))
        act_dec_sz.triggered.connect(lambda: self.step_font_size(-1))
        menu.addSeparator()

        act_demote = menu.addAction(safe_tr("Increase Indent"))
        act_demote.triggered.connect(self.demote)
        act_promote = menu.addAction(safe_tr("Decrease Indent"))
        act_promote.triggered.connect(self.promote)
        menu.addSeparator()

        act_reset = menu.addAction(safe_tr("Reset Formatting"))
        act_reset.triggered.connect(self.reset_formatting)
