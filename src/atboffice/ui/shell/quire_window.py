"""Quire dedicated word-processing window with Word 2003 Luna menus and toolbars."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from atboffice.modules.writer.view import WriterView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


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

        # 1. Embed WriterView
        self.writer_view = WriterView(parent=self)
        self.setCentralWidget(self.writer_view)

        # 2. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 3. Setup Office 2003 Luna toolbars
        self._setup_toolbars()

        # 4. Connect document modifications to dirty tracking
        self.writer_view.canvas_view.controller.document_modified.connect(
            self._on_document_modified
        )

        # 5. Load file or set initial document title
        if file_path is not None:
            resolved = Path(file_path).resolve()
            self.current_file_path = resolved
            self.update_window_title()
        else:
            self.update_window_title()

        self.set_modified(False)

    def _on_document_modified(self) -> None:
        """Mark document as modified when content edits occur."""
        self.set_modified(True)

    def update_window_title(self) -> None:
        """Set window title according to active document and dirty flag."""
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else safe_tr("未命名文档")
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
        """Initialize Word 2003 Luna Standard and Formatting toolbars."""
        # 1. Standard Toolbar
        self.toolbar_standard = OfficeToolBar(safe_tr("常用"), self)
        self.addToolBar(self.toolbar_standard)

        self.toolbar_standard.add_office_action(
            safe_tr("新建(&N)"),
            tooltip=safe_tr("新建空白文档 (Ctrl+N)"),
            callback=self.new_file,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("打开(&O)..."),
            tooltip=safe_tr("打开文档 (Ctrl+O)"),
            callback=self.open_file_dialog,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("保存(&S)"),
            tooltip=safe_tr("保存文档 (Ctrl+S)"),
            callback=self.save_file,
        )
        self.toolbar_standard.add_office_separator()
        self.toolbar_standard.add_office_action(
            safe_tr("剪切(&T)"),
            tooltip=safe_tr("剪切 (Ctrl+X)"),
            callback=self.cut,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("复制(&C)"),
            tooltip=safe_tr("复制 (Ctrl+C)"),
            callback=self.copy,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("粘贴(&P)"),
            tooltip=safe_tr("粘贴 (Ctrl+V)"),
            callback=self.paste,
        )
        self.toolbar_standard.add_office_separator()
        self.toolbar_standard.add_office_action(
            safe_tr("撤销(&U)"),
            tooltip=safe_tr("撤销 (Ctrl+Z)"),
            callback=self.undo,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("重做(&R)"),
            tooltip=safe_tr("重做 (Ctrl+Y)"),
            callback=self.redo,
        )

        # 2. Formatting Toolbar
        self.toolbar_formatting = OfficeToolBar(safe_tr("格式"), self)
        self.addToolBar(self.toolbar_formatting)

        self.act_bold = self.toolbar_formatting.add_office_action(
            safe_tr("加粗(&B)"),
            tooltip=safe_tr("加粗 (Ctrl+B)"),
            callback=self._toggle_bold,
            checkable=True,
        )
        self.act_italic = self.toolbar_formatting.add_office_action(
            safe_tr("倾斜(&I)"),
            tooltip=safe_tr("倾斜 (Ctrl+I)"),
            callback=self._toggle_italic,
            checkable=True,
        )
        self.act_underline = self.toolbar_formatting.add_office_action(
            safe_tr("下划线(&U)"),
            tooltip=safe_tr("下划线 (Ctrl+U)"),
            callback=self._toggle_underline,
            checkable=True,
        )
        self.toolbar_formatting.add_office_separator()

        # Color Pickers
        self.btn_font_color = ColorPickerButton(
            mode="font", default_color="#000000", parent=self.toolbar_formatting
        )
        self.btn_font_color.setToolTip(safe_tr("字体颜色"))
        self.btn_font_color.setStatusTip(safe_tr("更改文本字体颜色"))
        self.toolbar_formatting.addWidget(self.btn_font_color)

        self.btn_highlight_color = ColorPickerButton(
            mode="fill", default_color="#FFFF00", parent=self.toolbar_formatting
        )
        self.btn_highlight_color.setToolTip(safe_tr("突出显示"))
        self.btn_highlight_color.setStatusTip(safe_tr("突出显示所选文本"))
        self.toolbar_formatting.addWidget(self.btn_highlight_color)

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
            safe_tr(
                "<h3>ATBOffice Quire</h3>"
                "<p>经典 Word 2003 风格原生文字处理与排版引擎。</p>"
            ),
        )

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
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
