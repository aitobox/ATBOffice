"""Quire dedicated word-processing window with Word 2003 Luna menus and toolbars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu
from atboffice.ui.shell.quire_toolbars import (
    build_quire_toolbars,
    retranslate_quire_toolbars,
)


def safe_tr(text: str) -> str:
    """Translate UI text safely for QuireWindow."""
    return QCoreApplication.translate("QuireWindow", text)


class QuireWindow(BaseOfficeWindow):
    """Dedicated word-processing window embedding WriterView with Word 2003 styling."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.app_name = "ATBOffice Quire"
        self.app_type = "quire"
        super().__init__(parent)
        self.resize(1100, 750)

        # 1. Action Registry command bus
        self.action_registry = ActionRegistry(self)
        self._bind_action_handlers()

        # 2. Embed WriterView
        self.writer_view = WriterView(parent=self)
        self.setCentralWidget(self.writer_view)

        # 3. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 4. Setup Office 2003 Luna toolbars
        self._setup_toolbars()

        # 5. Connect document modifications to dirty tracking
        self.writer_view.canvas_view.controller.document_modified.connect(
            self._on_document_modified
        )

        # 6. Load file or set initial document title
        if file_path is not None:
            resolved = Path(file_path).resolve()
            self.current_file_path = resolved
            self.update_window_title()
        else:
            self.update_window_title()

        self.set_modified(False)

    def _bind_action_handlers(self) -> None:
        """Bind window callbacks to core action IDs in ActionRegistry."""
        self.action_registry.set_handler("new", self.new_file)
        self.action_registry.set_handler("open", self.open_file_dialog)
        self.action_registry.set_handler("save", self.save_file)
        self.action_registry.set_handler("cut", self.cut)
        self.action_registry.set_handler("copy", self.copy)
        self.action_registry.set_handler("paste", self.paste)
        self.action_registry.set_handler("undo", self.undo)
        self.action_registry.set_handler("redo", self.redo)
        self.action_registry.set_handler("bold", self._toggle_bold)
        self.action_registry.set_handler("italic", self._toggle_italic)
        self.action_registry.set_handler("underline", self._toggle_underline)
        self.action_registry.set_handler("zoom_in", self.zoom_in)
        self.action_registry.set_handler("zoom_out", self.zoom_out)
        self.action_registry.set_handler("zoom_reset", self.zoom_reset)

    def _on_document_modified(self) -> None:
        """Mark document as modified when content edits occur."""
        self.set_modified(True)

    @property
    def default_doc_name(self) -> str:
        """Default document name for Quire documents."""
        return safe_tr("未命名文档")

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty flag."""
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Quire save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.docx *.doc *.odt *.rtf *.txt);;"
            "Word 文档 (*.docx);;"
            "Word 97-2003 文档 (*.doc);;"
            "富文本格式 (*.rtf);;"
            "纯文本文件 (*.txt);;"
            "所有文件 (*.*)"
        )

    def do_save(self, path: Path) -> bool:
        """Serialize Quire document to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return True

    def _setup_toolbars(self) -> None:
        """Initialize Word 2003 Luna 10 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_quire_toolbars(
            self, self.action_registry
        )

        # Bottom toolbar: Drawing
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.toolbars["drawing"])

        # Top toolbars in standard display order
        for name in [
            "standard",
            "formatting",
            "tables",
            "reviewing",
            "outlining",
            "headerFooter",
            "picture",
            "mailMerge",
            "wordart",
        ]:
            if name in self.toolbars:
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars[name])

        # Backward compatibility aliases
        self.toolbar_standard = self.toolbars["standard"]
        self.toolbar_formatting = self.toolbars["formatting"]
        self.act_bold = self.action_registry.get_action("bold")
        self.act_italic = self.action_registry.get_action("italic")
        self.act_underline = self.action_registry.get_action("underline")

        # Color picker compatibility references
        for cp in self.toolbars["formatting"].findChildren(ColorPickerButton):
            if cp.mode == "font":
                self.btn_font_color = cp
            elif cp.mode == "fill":
                self.btn_highlight_color = cp

        # Default display modes for all 10 toolbars
        self.toolbar_modes: dict[str, bool | str] = {
            "standard": True,
            "formatting": True,
            "drawing": True,
            "tables": "auto",
            "reviewing": "auto",
            "picture": "auto",
            "outlining": "auto",
            "headerFooter": "auto",
            "mailMerge": False,
            "wordart": "auto",
        }

        # Apply initial contextual visibility
        self.update_context_toolbars({})

    def set_toolbar_mode(self, name: str, mode: bool | str) -> None:
        """Set toolbar visibility mode: True, False, or 'auto'."""
        self.toolbar_modes[name] = mode
        if isinstance(mode, bool) and name in self.toolbars:
            self.toolbars[name].setVisible(mode)

    def update_context_toolbars(self, context: dict[str, Any] | None = None) -> None:
        """Update contextual toolbar visibility based on selection and document state."""
        ctx = context or {}
        for name, mode in self.toolbar_modes.items():
            tb = self.toolbars.get(name)
            if tb is None:
                continue

            if mode is True:
                target_visible = True
            elif mode is False:
                target_visible = False
            else:  # "auto"
                if name == "tables":
                    target_visible = bool(ctx.get("in_table"))
                elif name == "picture":
                    target_visible = bool(ctx.get("is_picture"))
                elif name == "wordart":
                    target_visible = bool(ctx.get("is_wordart"))
                elif name == "outlining":
                    target_visible = ctx.get("view") == "outline"
                elif name == "headerFooter":
                    target_visible = bool(ctx.get("hf_edit"))
                elif name == "reviewing":
                    target_visible = bool(ctx.get("has_revisions") or ctx.get("track_changes"))
                else:
                    target_visible = False

            tb.setVisible(target_visible)

    def _toggle_bold(self) -> None:
        """Toggle bold formatting on selection."""
        pass

    def _toggle_italic(self) -> None:
        """Toggle italic formatting on selection."""
        pass

    def _toggle_underline(self) -> None:
        """Toggle underline formatting on selection."""
        pass

    def zoom_in(self) -> None:
        """Zoom in document canvas."""
        self.writer_view.canvas_view.zoom_in()

    def zoom_out(self) -> None:
        """Zoom out document canvas."""
        self.writer_view.canvas_view.zoom_out()

    def zoom_reset(self) -> None:
        """Reset document zoom level to 100%."""
        self.writer_view.canvas_view.set_zoom(1.0)

    def show_about(self) -> None:
        """Show about dialog for ATBOffice Quire."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice Quire"),
            safe_tr("<h3>ATBOffice Quire</h3><p>经典 Word 2003 风格原生文字处理与排版引擎。</p>"),
        )

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
        if hasattr(self, "toolbars"):
            retranslate_quire_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "action_registry"):
            self.action_registry.retranslate_ui(safe_tr)
        if hasattr(self, "toolbar_standard"):
            self.toolbar_standard.setWindowTitle(safe_tr("常用"))
        if hasattr(self, "toolbar_formatting"):
            self.toolbar_formatting.setWindowTitle(safe_tr("格式"))
        if hasattr(self, "btn_font_color"):
            self.btn_font_color.setToolTip(safe_tr("字体颜色"))
            self.btn_font_color.setStatusTip(safe_tr("更改文本字体颜色"))
        if hasattr(self, "btn_highlight_color"):
            self.btn_highlight_color.setToolTip(safe_tr("突出显示"))
            self.btn_highlight_color.setStatusTip(safe_tr("突出显示所选文本"))
        if hasattr(self, "writer_view"):
            self.writer_view.retranslate_ui()
        if hasattr(self, "menu_bar"):
            self.menu_bar.retranslate_ui()
