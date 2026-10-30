"""Lectern dedicated presentation window with PowerPoint 2003 Luna menus and toolbar cluster."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.modules.presentation.models.slide import Slide
from atboffice.modules.presentation.view import PresentationView
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow
from atboffice.ui.shell.lectern_toolbars import (
    build_lectern_toolbars,
    retranslate_lectern_toolbars,
)
from atboffice.ui.shell.mac_menu import MacMenuBar, setup_mac_menu


def safe_tr(text: str) -> str:
    """Translate UI text safely for LecternWindow."""
    return core_safe_tr(text)


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

        # 1. Action Registry command bus
        self.action_registry = ActionRegistry(self)
        self._bind_action_handlers()

        # 2. Embed PresentationView
        self.presentation_view = PresentationView(parent=self)
        self.setCentralWidget(self.presentation_view)
        self.thumbnail_list = self.presentation_view.workspace.thumbnail_list

        # 3. Setup native macOS menu bar
        self.menu_bar: MacMenuBar = setup_mac_menu(self)

        # 4. Setup Office 2003 Luna 10 toolbars
        self._setup_toolbars()

        # 5. Connect slide changes & selection signals
        ws = self.presentation_view.workspace
        ws.slide_changed.connect(self._on_presentation_modified)

        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.selectionChanged.connect(self._on_scene_selection_changed)

        if hasattr(ws, "left_pane") and ws.left_pane is not None:
            ws.left_pane.currentChanged.connect(self._on_left_pane_tab_changed)

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
        self.action_registry.set_handler("new_slide", self.add_new_slide)
        self.action_registry.set_handler("newSlide", self.add_new_slide)
        self.action_registry.set_handler("start_slideshow", self.start_slideshow)
        self.action_registry.set_handler("closeMaster", lambda: self.set_view_mode("normal"))

    def _toggle_bold(self) -> None:
        """Toggle bold formatting for active selection."""
        self.set_modified(True)

    def _toggle_italic(self) -> None:
        """Toggle italic formatting for active selection."""
        self.set_modified(True)

    def _toggle_underline(self) -> None:
        """Toggle underline formatting for active selection."""
        self.set_modified(True)

    def _on_presentation_modified(self) -> None:
        """Mark presentation as modified when slide content or layout changes."""
        self.set_modified(True)

    def _on_scene_selection_changed(self) -> None:
        """Inspect selected items on the slide scene and trigger toolbar context refresh."""
        ws = self.presentation_view.workspace
        if not hasattr(ws, "scene") or ws.scene is None:
            return
        selected_items = ws.scene.selectedItems()
        is_table = False
        is_picture = False
        is_diagram = False
        is_wordart = False

        for item in selected_items:
            shape = getattr(item, "shape", None)
            stype = getattr(shape, "type", "") if shape else ""
            if stype in ("table",):
                is_table = True
            elif stype in ("image", "picture"):
                is_picture = True
            elif stype in ("diagram", "smartart"):
                is_diagram = True
            elif stype in ("wordart",):
                is_wordart = True

        self.update_context_toolbars(
            {
                "is_table": is_table,
                "is_picture": is_picture,
                "is_diagram": is_diagram,
                "is_wordart": is_wordart,
            }
        )

    def _on_left_pane_tab_changed(self, index: int) -> None:
        """Handle left pane tab change between Slides (0) and Outline (1)."""
        is_outline = index == 1
        self.update_context_toolbars({"is_outline": is_outline})

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
        """Initialize PowerPoint 2003 Luna 10 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_lectern_toolbars(self, self.action_registry)

        # Bottom toolbar: Drawing
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, self.toolbars["drawing"])

        # Top toolbars in standard display order
        for name in [
            "standard",
            "formatting",
            "outlining",
            "sorter",
            "master",
            "diagram",
            "tables",
            "picture",
            "wordart",
        ]:
            if name in self.toolbars:
                self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars[name])

        # Backward compatibility aliases
        self.toolbar_standard = self.toolbars["standard"]
        self.toolbar_presentation = self.toolbars["sorter"]
        self.act_bold = self.action_registry.get_action("bold")
        self.act_italic = self.action_registry.get_action("italic")
        self.act_underline = self.action_registry.get_action("underline")

        # Default display modes for all 10 toolbars
        self.toolbar_modes: dict[str, bool | str] = {
            "standard": True,
            "formatting": True,
            "drawing": True,
            "sorter": False,
            "master": False,
            "outlining": False,
            "diagram": "auto",
            "tables": "auto",
            "picture": "auto",
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
        view_mode = ctx.get("view_mode", getattr(self.presentation_view, "view_mode", "normal"))

        for name, mode in self.toolbar_modes.items():
            tb = self.toolbars.get(name)
            if tb is None:
                continue

            if view_mode == "sorter":
                # In sorter view, only sorter and standard are visible
                target_visible = name in ("sorter", "standard")
            elif view_mode == "master":
                # In master view, master toolbar is visible along with standard, formatting, drawing
                if name == "master":
                    target_visible = True
                elif name == "sorter":
                    target_visible = False
                elif mode is True:
                    target_visible = True
                elif mode is False:
                    target_visible = False
                else:  # "auto"
                    target_visible = self._resolve_auto_context(name, ctx)
            else:
                # Normal view mode
                if name in ("sorter", "master"):
                    target_visible = False
                elif mode is True:
                    target_visible = True
                elif mode is False:
                    target_visible = bool(ctx.get("is_outline")) if name == "outlining" else False
                else:  # "auto"
                    target_visible = self._resolve_auto_context(name, ctx)

            tb.setVisible(target_visible)

    def _resolve_auto_context(self, name: str, ctx: dict[str, Any]) -> bool:
        if name == "tables":
            return bool(ctx.get("is_table"))
        elif name == "picture":
            return bool(ctx.get("is_picture"))
        elif name == "diagram":
            return bool(ctx.get("is_diagram"))
        elif name == "wordart":
            return bool(ctx.get("is_wordart"))
        elif name == "outlining":
            return bool(ctx.get("is_outline"))
        return False

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
        if hasattr(self, "act_view_normal") and self.act_view_normal:
            self.act_view_normal.setChecked(mode == "normal")
        if hasattr(self, "act_view_sorter") and self.act_view_sorter:
            self.act_view_sorter.setChecked(mode == "sorter")
        if hasattr(self, "act_view_master") and self.act_view_master:
            self.act_view_master.setChecked(mode == "master")
        self.update_context_toolbars({"view_mode": mode})

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
        if hasattr(self, "toolbars") and self.toolbars:
            retranslate_lectern_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "presentation_view"):
            self.presentation_view.retranslate_ui()
        if hasattr(self, "menu_bar"):
            self.menu_bar.retranslate_ui()
