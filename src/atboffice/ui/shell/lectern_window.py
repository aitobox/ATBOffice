"""Lectern dedicated presentation window with PowerPoint 2003 Luna menus and presenter toolbar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QMessageBox, QWidget

from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.view import PresentationView
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


def safe_tr(text: str) -> str:
    """Translate UI text safely for LecternWindow."""
    return QCoreApplication.translate("LecternWindow", text)


class LecternWindow(BaseOfficeWindow):
    """Dedicated presentation window embedding PresentationView with PowerPoint 2003 styling."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self.app_name = "ATBOffice Lectern"
        self.app_type = "lectern"
        super().__init__(parent)
        self.resize(1100, 720)

        # 1. Embed PresentationView
        self.presentation_view = PresentationView(parent=self)
        self.setCentralWidget(self.presentation_view)
        self.thumbnail_list = self.presentation_view.workspace.thumbnail_list

        # 2. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 3. Setup Office 2003 Luna toolbars
        self._setup_toolbars()

        # 4. Connect slide changes to dirty tracking
        self.presentation_view.workspace.slide_changed.connect(self._on_presentation_modified)

        # 5. Load file or set initial document title
        if file_path is not None:
            resolved = Path(file_path).resolve()
            self.current_file_path = resolved
            self.update_window_title()
        else:
            self.update_window_title()

        self.set_modified(False)

    def _on_presentation_modified(self) -> None:
        """Mark presentation as modified when slide content or layout changes."""
        self.set_modified(True)

    @property
    def default_doc_name(self) -> str:
        """Default document name for Lectern presentations."""
        return safe_tr("未命名演示文稿")

    def update_window_title(self) -> None:
        """Set window title according to active presentation and dirty flag."""
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Lectern save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.pptx *.ppt *.odp);;"
            "PowerPoint 演示文稿 (*.pptx);;"
            "PowerPoint 97-2003 演示文稿 (*.ppt);;"
            "OpenDocument 演示文稿 (*.odp);;"
            "所有文件 (*.*)"
        )

    def do_save(self, path: Path) -> bool:
        """Serialize Lectern presentation to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return True

    def _setup_toolbars(self) -> None:
        """Initialize PowerPoint 2003 Luna Standard and Presentation toolbars."""
        # 1. Standard Toolbar
        self.toolbar_standard = OfficeToolBar(safe_tr("常用"), self)
        self.addToolBar(self.toolbar_standard)

        self.toolbar_standard.add_office_action(
            safe_tr("新建(&N)"),
            tooltip=safe_tr("新建空白演示文稿 (Ctrl+N)"),
            callback=self.new_file,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("打开(&O)..."),
            tooltip=safe_tr("打开演示文稿 (Ctrl+O)"),
            callback=self.open_file_dialog,
        )
        self.toolbar_standard.add_office_action(
            safe_tr("保存(&S)"),
            tooltip=safe_tr("保存演示文稿 (Ctrl+S)"),
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

        # 2. Presentation Toolbar
        self.toolbar_presentation = OfficeToolBar(safe_tr("演示"), self)
        self.addToolBar(self.toolbar_presentation)

        self.toolbar_presentation.add_office_action(
            safe_tr("新建幻灯片(&M)"),
            tooltip=safe_tr("在当前演示文稿中插入新幻灯片 (Ctrl+M)"),
            callback=self.add_new_slide,
        )
        self.toolbar_presentation.add_office_action(
            safe_tr("放映幻灯片(&S)"),
            tooltip=safe_tr("从首页开始放映 (F5)"),
            callback=self.start_slideshow,
        )
        self.toolbar_presentation.add_office_action(
            safe_tr("从当前页放映(&C)"),
            tooltip=safe_tr("从当前选定幻灯片开始放映 (Shift+F5)"),
            callback=self.start_slideshow_current,
        )
        self.toolbar_presentation.add_office_separator()

        self.act_view_normal = self.toolbar_presentation.add_office_action(
            safe_tr("普通视图(&O)"),
            tooltip=safe_tr("切换至普通编辑视图"),
            callback=lambda: self.set_view_mode("normal"),
            checkable=True,
        )
        self.act_view_sorter = self.toolbar_presentation.add_office_action(
            safe_tr("幻灯片浏览(&R)"),
            tooltip=safe_tr("切换至幻灯片浏览视图"),
            callback=lambda: self.set_view_mode("sorter"),
            checkable=True,
        )
        self.act_view_master = self.toolbar_presentation.add_office_action(
            safe_tr("母版视图(&T)"),
            tooltip=safe_tr("切换至幻灯片母版视图"),
            callback=lambda: self.set_view_mode("master"),
            checkable=True,
        )
        self.act_view_normal.setChecked(True)

    def add_new_slide(self) -> None:
        """Create and append a blank slide to the active presentation."""
        new_slide = Slide()
        self.presentation_view.presentation.add_slide(new_slide)
        self.presentation_view.load_slide(new_slide)
        self.set_modified(True)

    def start_slideshow(self) -> None:
        """Start presentation slideshow from the beginning."""
        self.presentation_view.start_slideshow(from_current=False, fullscreen=True)

    def start_slideshow_current(self) -> None:
        """Start presentation slideshow from the current slide."""
        self.presentation_view.start_slideshow(from_current=True, fullscreen=True)

    def set_view_mode(self, mode: str) -> None:
        """Switch workspace view mode ('normal', 'sorter', or 'master')."""
        self.presentation_view.set_view_mode(mode)
        if hasattr(self, "act_view_normal"):
            self.act_view_normal.setChecked(mode == "normal")
        if hasattr(self, "act_view_sorter"):
            self.act_view_sorter.setChecked(mode == "sorter")
        if hasattr(self, "act_view_master"):
            self.act_view_master.setChecked(mode == "master")

    def show_about(self) -> None:
        """Show about dialog for ATBOffice Lectern."""
        QMessageBox.about(
            self,
            safe_tr("关于 ATBOffice Lectern"),
            safe_tr(
                "<h3>ATBOffice Lectern</h3>"
                "<p>经典 PowerPoint 2003 风格跨平台原生演示文稿与幻灯片放映引擎。</p>"
            ),
        )

    def retranslate_ui(self) -> None:
        """Update localized UI strings when application language changes."""
        super().retranslate_ui()
        if hasattr(self, "toolbar_standard"):
            self.toolbar_standard.setWindowTitle(safe_tr("常用"))
        if hasattr(self, "toolbar_presentation"):
            self.toolbar_presentation.setWindowTitle(safe_tr("演示"))
        if hasattr(self, "presentation_view"):
            self.presentation_view.retranslate_ui()
        if hasattr(self, "menu_bar"):
            self.menu_bar.retranslate_ui()
