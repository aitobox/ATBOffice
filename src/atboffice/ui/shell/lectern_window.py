"""Lectern dedicated presentation window with PowerPoint 2003 Luna menus and toolbar cluster."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QResizeEvent, QShowEvent
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QToolButton,
    QWidget,
)

from atboffice.core.action_registry import ActionRegistry
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.modules.presentation.view import PresentationView
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.shell.base_window import BaseOfficeWindow, UnsupportedSaveFormatError
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

    recovery_suffix = ".pptx"

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

        # 4. Initialize universal TaskPaneDock
        self.init_task_pane_dock(safe_tr("演示文稿"))
        self._setup_lectern_task_panes()

        # 5. Setup Office 2003 Luna 10 toolbars
        self._setup_toolbars()

        # 5. Connect slide changes & selection signals
        ws = self.presentation_view.workspace
        ws.slide_changed.connect(self._on_slide_changed)

        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.selectionChanged.connect(self._on_scene_selection_changed)
            if hasattr(ws.scene, "shapeCreated"):
                ws.scene.shapeCreated.connect(self._on_shape_created)
            if hasattr(ws.scene, "toolChanged"):
                ws.scene.toolChanged.connect(self._update_drawing_tool_actions)

        if hasattr(ws, "left_pane") and ws.left_pane is not None:
            ws.left_pane.currentChanged.connect(self._on_left_pane_tab_changed)

        if hasattr(ws, "canvas_view") and ws.canvas_view is not None:
            if hasattr(ws.canvas_view, "zoom_changed"):
                ws.canvas_view.zoom_changed.connect(self._on_canvas_zoom_changed)
            if hasattr(ws.canvas_view, "auto_fit_changed"):
                ws.canvas_view.auto_fit_changed.connect(
                    lambda _: self._on_canvas_zoom_changed(ws.canvas_view.zoom)
                )

        # 6. Load file or set initial document title
        if file_path is not None:
            p = Path(file_path)
            if p.exists() or p.is_symlink():
                self.open_file(p)
            else:
                self.current_file_path = p.resolve()
                self.update_window_title()
        else:
            self.update_window_title()

        # 7. Real handlers for formerly stubbed / unbound commands (after menus & toolbars)
        from atboffice.ui.shell.lectern_commands import bind_lectern_commands

        self.lectern_commands = bind_lectern_commands(self)
        # The window's task pane dock replaces the workspace's embedded task pane
        ws.set_embedded_task_pane_enabled(False)
        self.attach_undo_history()  # Lectern has no undo stack yet: shows "nothing to undo"

        self.set_modified(False)
        self._setup_status_bar_view_buttons()
        self.menu_bar.retranslate_ui()

    def _setup_status_bar_view_buttons(self) -> None:
        """Create view mode switcher buttons and slide indicator in status bar."""
        sb = self.statusBar()
        if not sb:
            return

        self.lbl_status_slide = QLabel(safe_tr("幻灯片 1 / 1"), sb)
        self.lbl_status_slide.setStyleSheet("color: #444444; padding: 0 8px;")
        sb.addWidget(self.lbl_status_slide)

        self.lbl_status_design = QLabel(safe_tr("默认设计模板"), sb)
        self.lbl_status_design.setStyleSheet("color: #666666; padding: 0 8px;")
        sb.addWidget(self.lbl_status_design)

        # Right-aligned view mode switcher buttons
        self.status_view_group = QWidget(sb)
        vg_layout = QHBoxLayout(self.status_view_group)
        vg_layout.setContentsMargins(0, 0, 0, 0)
        vg_layout.setSpacing(2)

        self.btn_view_normal = QToolButton(self.status_view_group)
        self.btn_view_normal.setText("▤")
        self.btn_view_normal.setToolTip(safe_tr("普通视图 (Normal View)"))
        self.btn_view_normal.setCheckable(True)
        self.btn_view_normal.setChecked(True)
        self.btn_view_normal.clicked.connect(lambda: self.set_view_mode("normal"))
        vg_layout.addWidget(self.btn_view_normal)

        self.btn_view_sorter = QToolButton(self.status_view_group)
        self.btn_view_sorter.setText("田")
        self.btn_view_sorter.setToolTip(safe_tr("幻灯片浏览视图 (Slide Sorter View)"))
        self.btn_view_sorter.setCheckable(True)
        self.btn_view_sorter.clicked.connect(lambda: self.set_view_mode("sorter"))
        vg_layout.addWidget(self.btn_view_sorter)

        self.btn_view_notes = QToolButton(self.status_view_group)
        self.btn_view_notes.setText("🗎")
        self.btn_view_notes.setToolTip(safe_tr("备注页视图 (Notes Page View)"))
        self.btn_view_notes.setCheckable(True)
        self.btn_view_notes.clicked.connect(lambda: self.set_view_mode("notes"))
        vg_layout.addWidget(self.btn_view_notes)

        self.btn_view_show = QToolButton(self.status_view_group)
        self.btn_view_show.setText("▶")
        self.btn_view_show.setToolTip(safe_tr("幻灯片放映 (Slide Show)"))
        self.btn_view_show.clicked.connect(self.start_slideshow)
        vg_layout.addWidget(self.btn_view_show)

        sb.addPermanentWidget(self.status_view_group)

    def _bind_action_handlers(self) -> None:
        """Bind window callbacks to core action IDs in ActionRegistry."""
        # 1. File & Print
        self.action_registry.set_handler("new", self.new_file)
        self.action_registry.set_handler("file_new", self.new_file)
        self.action_registry.set_handler("open", self.open_file_dialog)
        self.action_registry.set_handler("file_open", self.open_file_dialog)
        self.action_registry.set_handler("save", self.save_file)
        self.action_registry.set_handler("file_save", self.save_file)
        self.action_registry.set_handler("save_as", self.save_as_dialog)
        self.action_registry.set_handler("file_save_as", self.save_as_dialog)
        self.action_registry.set_handler("print", self.print_document)
        self.action_registry.set_handler("file_print", self.print_document)
        self.action_registry.set_handler("printPreview", self.print_preview)
        self.action_registry.set_handler("file_print_preview", self.print_preview)
        self.action_registry.set_handler("properties", self.show_document_properties_dialog)
        self.action_registry.set_handler("file_properties", self.show_document_properties_dialog)
        self.action_registry.set_handler("taskPane", self.toggle_task_pane)
        self.action_registry.set_handler("view_task_pane", self.toggle_task_pane)
        self.action_registry.set_handler("slideLayout", self.open_slide_layout_pane)
        self.action_registry.set_handler("slide_layout", self.open_slide_layout_pane)
        self.action_registry.set_handler("format_slide_layout", self.open_slide_layout_pane)

        # 2. Edit & Clipboard
        self.action_registry.set_handler("cut", self.cut)
        self.action_registry.set_handler("edit_cut", self.cut)
        self.action_registry.set_handler("copy", self.copy)
        self.action_registry.set_handler("edit_copy", self.copy)
        self.action_registry.set_handler("paste", self.paste)
        self.action_registry.set_handler("edit_paste", self.paste)
        self.action_registry.set_handler("undo", self.undo)
        self.action_registry.set_handler("edit_undo", self.undo)
        self.action_registry.set_handler("redo", self.redo)
        self.action_registry.set_handler("edit_redo", self.redo)
        self.action_registry.set_handler("selectAll", self.select_all)
        self.action_registry.set_handler("edit_select_all", self.select_all)

        # 3. Formatting (Character & Paragraph)
        self.action_registry.set_handler("bold", self._toggle_bold)
        self.action_registry.set_handler("italic", self._toggle_italic)
        self.action_registry.set_handler("underline", self._toggle_underline)
        self.action_registry.set_handler("shadowText", self._toggle_shadow)
        self.action_registry.set_handler("growFont", lambda: self.step_font_size(1))
        self.action_registry.set_handler("shrinkFont", lambda: self.step_font_size(-1))
        self.action_registry.set_handler("numbering", self.toggle_numbering)
        self.action_registry.set_handler("format_numbering", self.toggle_numbering)
        self.action_registry.set_handler("bullets", self.toggle_bullets)
        self.action_registry.set_handler("format_bullets", self.toggle_bullets)
        self.action_registry.set_handler("promote", self.promote_indent)
        self.action_registry.set_handler("demote", self.demote_indent)
        self.action_registry.set_handler("alignLeft", self._handle_align_left)
        self.action_registry.set_handler("alignCenter", self._handle_align_center)
        self.action_registry.set_handler("alignRight", self._handle_align_right)
        self.action_registry.set_handler("slideDesign", self.open_slide_design_pane)
        self.action_registry.set_handler("slide_design", self.open_slide_design_pane)
        self.action_registry.set_handler("sorter_slideDesign", self.open_slide_design_pane)
        self.action_registry.set_handler("slideColorSchemes", self.open_color_schemes_pane)
        self.action_registry.set_handler("slide_color_schemes", self.open_color_schemes_pane)
        self.action_registry.set_handler("color_schemes", self.open_color_schemes_pane)
        self.action_registry.set_handler("slideAnimationSchemes", self.open_animation_schemes_pane)
        self.action_registry.set_handler(
            "slide_animation_schemes", self.open_animation_schemes_pane
        )
        self.action_registry.set_handler("animation_schemes", self.open_animation_schemes_pane)
        self.action_registry.set_handler("slideshow_setup", self.open_setup_show_dialog)
        self.action_registry.set_handler("setupShow", self.open_setup_show_dialog)
        self.action_registry.set_handler("slide_setup_show", self.open_setup_show_dialog)
        self.action_registry.set_handler("actionSettings", self.open_action_settings_dialog)
        self.action_registry.set_handler("slide_action_settings", self.open_action_settings_dialog)
        self.action_registry.set_handler("action_settings", self.open_action_settings_dialog)
        self.action_registry.set_handler("photoAlbum", self.open_photo_album_dialog)
        self.action_registry.set_handler("insert_photo_album", self.open_photo_album_dialog)
        self.action_registry.set_handler("lecternOptions", self.open_options_dialog)
        self.action_registry.set_handler("tools_options", self.open_options_dialog)
        self.action_registry.set_handler("options", self.open_options_dialog)
        self.action_registry.set_handler("fillEffects", self.open_fill_effects_dialog)
        self.action_registry.set_handler("fill_effects", self.open_fill_effects_dialog)
        self.action_registry.set_handler("newSlide", self.add_new_slide)
        self.action_registry.set_handler("new_slide", self.add_new_slide)

        # 4. Standard Extras
        self.action_registry.set_handler("insertChart", self.insert_chart)
        self.action_registry.set_handler("insertTable", self.insert_table)
        self.action_registry.set_handler("tb_tables", self.toggle_tables_toolbar)
        self.action_registry.set_handler("showGrid", self.toggle_grid)
        self.action_registry.set_handler("viewGray", lambda: self.set_view_color_mode("grayscale"))
        self.action_registry.set_handler("view_color", lambda: self.set_view_color_mode("color"))
        self.action_registry.set_handler(
            "view_grayscale", lambda: self.set_view_color_mode("grayscale")
        )
        self.action_registry.set_handler(
            "view_black_and_white", lambda: self.set_view_color_mode("bw")
        )

        # 5. Slideshow
        self.action_registry.set_handler("start_slideshow", self.start_slideshow)
        self.action_registry.set_handler("start_slideshow_current", self.start_slideshow_current)

        # 6. View mode switching
        self.action_registry.set_handler("viewNormal", lambda: self.set_view_mode("normal"))
        self.action_registry.set_handler("viewSorter", lambda: self.set_view_mode("sorter"))
        self.action_registry.set_handler("viewNotes", lambda: self.set_view_mode("notes"))
        self.action_registry.set_handler("viewNotesPage", lambda: self.set_view_mode("notes"))
        self.action_registry.set_handler("viewMaster", lambda: self.set_view_mode("master"))
        self.action_registry.set_handler("closeMaster", lambda: self.set_view_mode("normal"))

        # 7. Drawing Tools & AutoShapes
        self.action_registry.set_handler(
            "drawLine", lambda: self.set_drawing_tool({"kind": "line", "geom": "line"})
        )
        self.action_registry.set_handler(
            "drawArrow", lambda: self.set_drawing_tool({"kind": "line", "geom": "rightArrow"})
        )
        self.action_registry.set_handler(
            "drawRect", lambda: self.set_drawing_tool({"kind": "shape", "geom": "rect"})
        )
        self.action_registry.set_handler(
            "drawOval", lambda: self.set_drawing_tool({"kind": "shape", "geom": "ellipse"})
        )
        self.action_registry.set_handler(
            "textBox", lambda: self.set_drawing_tool({"kind": "text", "geom": "rect"})
        )
        self.action_registry.set_handler("selectObjects", lambda: self.set_drawing_tool(None))
        self.action_registry.set_handler(
            "ashape_lines", lambda: self.set_drawing_tool({"kind": "line", "geom": "line"})
        )
        self.action_registry.set_handler(
            "ashape_connectors",
            lambda: self.set_drawing_tool({"kind": "line", "geom": "bentConnector"}),
        )
        self.action_registry.set_handler(
            "ashape_basic", lambda: self.set_drawing_tool({"kind": "shape", "geom": "rect"})
        )
        self.action_registry.set_handler(
            "ashape_arrows", lambda: self.set_drawing_tool({"kind": "line", "geom": "rightArrow"})
        )
        self.action_registry.set_handler(
            "ashape_flowchart",
            lambda: self.set_drawing_tool({"kind": "shape", "geom": "flowChartProcess"}),
        )
        self.action_registry.set_handler(
            "ashape_stars", lambda: self.set_drawing_tool({"kind": "shape", "geom": "star5"})
        )
        self.action_registry.set_handler(
            "ashape_callouts",
            lambda: self.set_drawing_tool({"kind": "shape", "geom": "wedgeRectCallout"}),
        )

        # 8. Shape z-order & Grouping
        self.action_registry.set_handler("bringFront", self._on_bring_to_front)
        self.action_registry.set_handler("sendBack", self._on_send_to_back)
        self.action_registry.set_handler("bringForward", self._on_bring_forward)
        self.action_registry.set_handler("sendBackward", self._on_send_backward)
        self.action_registry.set_handler("group", self._on_group_shapes)
        self.action_registry.set_handler("ungroup", self._on_ungroup_shapes)
        self.action_registry.set_handler("regroup", self._on_regroup_shapes)

        # 9. Shape Alignment & Distribution
        self.action_registry.set_handler("alignTop", lambda: self._align_shapes("T"))
        self.action_registry.set_handler("alignMiddle", lambda: self._align_shapes("M"))
        self.action_registry.set_handler("alignBottom", lambda: self._align_shapes("B"))
        self.action_registry.set_handler("distributeH", lambda: self._distribute_shapes("h"))
        self.action_registry.set_handler("distributeV", lambda: self._distribute_shapes("v"))

        # 10. SmartArt / IntelliArt Diagram
        self.action_registry.set_handler(
            "diagramAddShape", lambda: self._on_diagram_add_shape("after")
        )
        self.action_registry.set_handler(
            "diagramAddAfter", lambda: self._on_diagram_add_shape("after")
        )
        self.action_registry.set_handler(
            "diagramAddBefore", lambda: self._on_diagram_add_shape("before")
        )
        self.action_registry.set_handler(
            "diagramAddAbove", lambda: self._on_diagram_add_shape("above")
        )
        self.action_registry.set_handler(
            "diagramAddBelow", lambda: self._on_diagram_add_shape("below")
        )
        self.action_registry.set_handler("diagramPromote", self._on_diagram_promote)
        self.action_registry.set_handler("diagramDemote", self._on_diagram_demote)
        self.action_registry.set_handler("diagramMoveUp", lambda: self._on_diagram_move("up"))
        self.action_registry.set_handler("diagramMoveDown", lambda: self._on_diagram_move("down"))
        self.action_registry.set_handler("diagramReset", self._on_diagram_reset)
        self.action_registry.set_handler("diagramToShapes", self._on_diagram_to_shapes)
        self.action_registry.set_handler("diagramTextPane", self.show_smartart_pane)

        # 11. Tables and Borders Toolbar
        self.action_registry.set_handler("tbl_insert_table", self.insert_table)

        # 12. Picture Toolbar
        self.action_registry.set_handler("pic_insert", self.insert_picture_from_file)
        self.action_registry.set_handler("insert_picture", self.insert_picture_from_file)
        self.action_registry.set_handler("draw_insertPicture", self.insert_picture_from_file)
        self.action_registry.set_handler("insertClipArt", self.open_clipart_dialog)
        self.action_registry.set_handler("rotateLeft", self.rotate_selected_left)
        self.action_registry.set_handler("picCrop", self.toggle_picture_crop)
        self.action_registry.set_handler("picReset", self.reset_picture)
        self.action_registry.set_handler(
            "picMoreContrast", lambda: self.adjust_picture_contrast(0.1)
        )
        self.action_registry.set_handler(
            "picLessContrast", lambda: self.adjust_picture_contrast(-0.1)
        )
        self.action_registry.set_handler(
            "picMoreBright", lambda: self.adjust_picture_brightness(0.1)
        )
        self.action_registry.set_handler(
            "picLessBright", lambda: self.adjust_picture_brightness(-0.1)
        )
        self.action_registry.set_handler(
            "pic_color_auto", lambda: self.set_picture_color_mode("auto")
        )
        self.action_registry.set_handler(
            "pic_color_gray", lambda: self.set_picture_color_mode("gray")
        )
        self.action_registry.set_handler("pic_color_bw", lambda: self.set_picture_color_mode("bw"))
        self.action_registry.set_handler(
            "pic_color_washout", lambda: self.set_picture_color_mode("washout")
        )

        # 13. WordArt Toolbar
        self.action_registry.set_handler("insertWordArt", self.open_wordart_gallery)
        self.action_registry.set_handler("draw_insertWordArt", self.open_wordart_gallery)
        self.action_registry.set_handler("wa_insert", self.open_wordart_gallery)
        self.action_registry.set_handler("wordartGallery", self.open_wordart_gallery)
        self.action_registry.set_handler("wordartEdit", self.open_wordart_gallery)
        self.action_registry.set_handler("waSameHeight", self.toggle_wordart_same_height)
        self.action_registry.set_handler("waVertical", self.toggle_wordart_vertical)
        self.action_registry.set_handler("wa_shape_plain", lambda: self.set_wordart_shape("plain"))
        self.action_registry.set_handler("wa_shape_wave", lambda: self.set_wordart_shape("wave"))
        self.action_registry.set_handler("wa_align_left", lambda: self.set_wordart_align("left"))
        self.action_registry.set_handler(
            "wa_align_center", lambda: self.set_wordart_align("center")
        )
        self.action_registry.set_handler("wa_align_right", lambda: self.set_wordart_align("right"))

        # 14. Slide Sorter Toolbar
        self.action_registry.set_handler("hideSlide", self.toggle_hide_slide)
        self.action_registry.set_handler("rehearse", self.start_rehearse)
        self.action_registry.set_handler("sorter_slideDesign", self.open_slide_design_pane)
        self.action_registry.set_handler("sorter_newSlide", self.add_new_slide)

        # 15. Master View Toolbar

        # 16. Outlining Toolbar
        self.action_registry.set_handler("outline_promote", self.promote_indent)
        self.action_registry.set_handler("outline_demote", self.demote_indent)

        # 17. Background Formatting
        self.action_registry.set_handler("background", self.open_background_dialog)
        self.action_registry.set_handler("format_background", self.open_background_dialog)

    def open_background_dialog(self) -> None:
        """Open the slide background formatting dialog."""
        from atboffice.modules.presentation.dialogs.background_dlg import BackgroundDialog

        if not self.presentation or not self.presentation.slides:
            return
        ws = getattr(self.presentation_view, "workspace", None)
        curr_slide = getattr(ws, "current_slide", None) or self.presentation.slides[0]
        dlg = BackgroundDialog(curr_slide, self.presentation, self)
        dlg.backgroundApplied.connect(self._on_background_applied)
        dlg.exec()

    def _on_background_applied(self, fill: Any, apply_to_all: bool) -> None:
        """Handle background dialog application."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws is not None:
            if hasattr(ws, "scene") and ws.scene is not None:
                ws.scene.update()
            if hasattr(ws, "refresh_thumbnails"):
                ws.refresh_thumbnails()
        self.set_modified(True)

    def set_drawing_tool(self, tool: dict[str, Any] | None) -> None:
        """Activate drawing tool on canvas and update drawing toolbar check states."""
        ws = self.presentation_view.workspace
        if hasattr(ws, "canvas_view") and ws.canvas_view is not None:
            ws.canvas_view.set_drawing_tool(tool)
        self._update_drawing_tool_actions(tool)

    def _update_drawing_tool_actions(self, active_tool: dict[str, Any] | None = None) -> None:
        """Update toggle check states for drawing tool actions."""
        kind = active_tool.get("kind") if active_tool else None
        geom = active_tool.get("geom") if active_tool else None

        tools_map = {
            "drawLine": kind == "line" and geom == "line",
            "drawArrow": kind == "line" and geom in ("rightArrow", "arrow"),
            "drawRect": kind == "shape" and geom == "rect",
            "drawOval": kind == "shape" and geom in ("ellipse", "oval"),
            "textBox": kind == "text",
            "selectObjects": active_tool is None,
        }

        for aid, is_active in tools_map.items():
            act = self.action_registry.get_action(aid)
            if act and act.isCheckable():
                act.blockSignals(True)
                act.setChecked(is_active)
                act.blockSignals(False)

    def _on_shape_created(self, shape: Any) -> None:
        """Mark presentation dirty and refresh contextual toolbars when a new shape is created."""
        self.set_modified(True)
        self._on_scene_selection_changed()

    def _on_bring_to_front(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.bring_to_front()
            self.set_modified(True)

    def _on_send_to_back(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.send_to_back()
            self.set_modified(True)

    def _on_bring_forward(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.bring_forward()
            self.set_modified(True)

    def _on_send_backward(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.send_backward()
            self.set_modified(True)

    def _on_group_shapes(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            new_grp = ws.scene.group_selected()
            if new_grp:
                self.set_modified(True)
                self._sync_toolbar_states()

    def _on_ungroup_shapes(self) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ungrouped_items = ws.scene.ungroup_selected()
            self._last_ungrouped_ids = [
                item.model.id for item in ungrouped_items if hasattr(item, "model") and item.model
            ]
            self.set_modified(True)
            self._sync_toolbar_states()

    def _on_regroup_shapes(self) -> None:
        ws = self.presentation_view.workspace
        if (
            hasattr(ws, "scene")
            and ws.scene is not None
            and getattr(self, "_last_ungrouped_ids", None)
        ):
            ws.scene.clearSelection()
            for sid in self._last_ungrouped_ids:
                item = ws.scene.get_shape_item(sid)
                if item:
                    item.setSelected(True)
            self._on_group_shapes()

    def _align_shapes(self, mode: str) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.align_shapes(mode)
            self.set_modified(True)

    def _distribute_shapes(self, axis: str) -> None:
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.distribute_shapes(axis)
            self.set_modified(True)

    def _get_active_diagram_shape(self) -> Any | None:
        ws = self.presentation_view.workspace
        if not hasattr(ws, "scene") or ws.scene is None:
            return None
        for item in ws.scene.selectedItems():
            shape = getattr(item, "model", None)
            if shape and (getattr(shape, "is_diagram", False) or getattr(shape, "sa", None)):
                return shape
            parent = item.parentItem() if hasattr(item, "parentItem") else None
            p_shape = getattr(parent, "model", None) if parent else None
            if p_shape and (getattr(p_shape, "is_diagram", False) or getattr(p_shape, "sa", None)):
                return p_shape
        if hasattr(ws, "current_slide") and ws.current_slide:
            for sh in ws.current_slide.shapes:
                if getattr(sh, "is_diagram", False) or getattr(sh, "sa", None):
                    return sh
        return None

    def _on_diagram_add_shape(self, pos: str = "after") -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        from atboffice.modules.presentation.smartart.engine import SmartArtEngine, relayout
        from atboffice.modules.presentation.smartart.item import SmartArtItem, outline

        eng = SmartArtEngine()
        raw_items = diag.sa.get("items", [])
        items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]
        flat_tree = outline(items)
        target_id = flat_tree[-1]["item"].id if flat_tree else ""

        if pos == "after":
            eng.add_after(items, target_id, safe_tr("新项目"))
        elif pos == "before":
            eng.add_before(items, target_id, safe_tr("新项目"))
        elif pos == "above":
            eng.add_above(items, target_id, safe_tr("新项目"))
        elif pos == "below":
            eng.add_below(items, target_id, safe_tr("新项目"))

        diag.sa["items"] = items
        relayout(diag)
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
            ws.scene.load_slide(ws.current_slide)
            if hasattr(diag, "id") and hasattr(ws.scene, "get_shape_item"):
                item = ws.scene.get_shape_item(diag.id)
                if item:
                    item.setSelected(True)
        self.set_modified(True)

    def _on_diagram_promote(self) -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        from atboffice.modules.presentation.smartart.engine import SmartArtEngine, relayout
        from atboffice.modules.presentation.smartart.item import SmartArtItem, outline

        eng = SmartArtEngine()
        raw_items = diag.sa.get("items", [])
        items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]
        flat_tree = outline(items)
        if not flat_tree:
            return
        target_id = flat_tree[-1]["item"].id
        if eng.promote(items, target_id):
            diag.sa["items"] = items
            relayout(diag)
            ws = self.presentation_view.workspace
            if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
                ws.scene.load_slide(ws.current_slide)
                if hasattr(diag, "id") and hasattr(ws.scene, "get_shape_item"):
                    item = ws.scene.get_shape_item(diag.id)
                    if item:
                        item.setSelected(True)
            self.set_modified(True)

    def _on_diagram_demote(self) -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        from atboffice.modules.presentation.smartart.engine import SmartArtEngine, relayout
        from atboffice.modules.presentation.smartart.item import SmartArtItem, outline

        eng = SmartArtEngine()
        raw_items = diag.sa.get("items", [])
        items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]
        flat_tree = outline(items)
        if not flat_tree:
            return
        target_id = flat_tree[-1]["item"].id
        if eng.demote(items, target_id):
            diag.sa["items"] = items
            relayout(diag)
            ws = self.presentation_view.workspace
            if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
                ws.scene.load_slide(ws.current_slide)
                if hasattr(diag, "id") and hasattr(ws.scene, "get_shape_item"):
                    item = ws.scene.get_shape_item(diag.id)
                    if item:
                        item.setSelected(True)
            self.set_modified(True)

    def _on_diagram_move(self, direction: str = "up") -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        from atboffice.modules.presentation.smartart.engine import SmartArtEngine, relayout
        from atboffice.modules.presentation.smartart.item import SmartArtItem, outline

        eng = SmartArtEngine()
        raw_items = diag.sa.get("items", [])
        items = [SmartArtItem.from_dict(it) if isinstance(it, dict) else it for it in raw_items]
        flat_tree = outline(items)
        if not flat_tree:
            return
        target_id = flat_tree[-1]["item"].id
        if direction == "up":
            changed = eng.move_up(items, target_id)
        else:
            changed = eng.move_down(items, target_id)
        if changed:
            diag.sa["items"] = items
            relayout(diag)
            ws = self.presentation_view.workspace
            if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
                ws.scene.load_slide(ws.current_slide)
            self.set_modified(True)

    def _on_diagram_to_shapes(self) -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        diag.sa = None
        diag.name = safe_tr("已解散关系图")
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
            ws.scene.load_slide(ws.current_slide)
        self.set_modified(True)

    def _on_diagram_reset(self) -> None:
        diag = self._get_active_diagram_shape()
        if not diag or not diag.sa:
            return
        from atboffice.modules.presentation.smartart.engine import relayout
        from atboffice.modules.presentation.smartart.palettes import DEFAULT_COLORS, DEFAULT_STYLE

        diag.sa["colors"] = DEFAULT_COLORS
        diag.sa["style"] = DEFAULT_STYLE
        relayout(diag)
        ws = self.presentation_view.workspace
        if hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
            ws.scene.load_slide(ws.current_slide)
        self.set_modified(True)

    def _toggle_bold(self) -> None:
        """Toggle bold formatting for active selection or text editor."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_bold()
                elif getattr(item, "model", None) and item.model.text:
                    curr = any(r.bold for p in item.model.text.paragraphs for r in p.runs)
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.bold = not curr
                    item.update()
        self.set_modified(True)
        self._sync_toolbar_states()

    def _toggle_italic(self) -> None:
        """Toggle italic formatting for active selection or text editor."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_italic()
                elif getattr(item, "model", None) and item.model.text:
                    curr = any(r.italic for p in item.model.text.paragraphs for r in p.runs)
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.italic = not curr
                    item.update()
        self.set_modified(True)
        self._sync_toolbar_states()

    def _toggle_underline(self) -> None:
        """Toggle underline formatting for active selection or text editor."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_underline()
                elif getattr(item, "model", None) and item.model.text:
                    curr = any(r.underline for p in item.model.text.paragraphs for r in p.runs)
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.underline = not curr
                    item.update()
        self.set_modified(True)
        self._sync_toolbar_states()

    def _toggle_shadow(self) -> None:
        """Toggle text shadow for active selection."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    act = self.action_registry.get_action("shadowText")
                    chk = act.isChecked() if act else True
                    item._text_editor.set_text_shadow(chk)
        self.set_modified(True)

    def step_font_size(self, direction: int) -> None:
        """Step font size up (+1) or down (-1)."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.step_font_size(direction)
                elif getattr(item, "model", None) and item.model.text:
                    delta = 2.0 if direction > 0 else -2.0
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            sz = (r.size or 18.0) + delta
                            r.size = max(4.0, min(144.0, sz))
                    item.update()
        self.set_modified(True)

    def toggle_numbering(self) -> None:
        """Toggle numbering on active text."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_bullet_type("number")
        self.set_modified(True)

    def toggle_bullets(self) -> None:
        """Toggle bullets on active text."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_bullet_type("bullet")
        self.set_modified(True)

    def promote_indent(self) -> None:
        """Promote text outline level / decrease indent."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.promote()
        self.set_modified(True)

    def demote_indent(self) -> None:
        """Demote text outline level / increase indent."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.demote()
        self.set_modified(True)

    def set_paragraph_align(self, align_str: str) -> None:
        """Set paragraph alignment on active text."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_alignment(align_str)
                elif getattr(item, "model", None) and item.model.text:
                    code_map = {"left": "l", "center": "ctr", "right": "r", "justify": "just"}
                    code = code_map.get(align_str, "l")
                    for p in item.model.text.paragraphs:
                        p.props["algn"] = code
                    item.update()
        self.set_modified(True)
        self._sync_toolbar_states()

    def _handle_align_left(self) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            items = ws.scene.selectedItems()
            if items and (
                getattr(items[0], "is_editing_text", False)
                or (
                    len(items) == 1
                    and getattr(items[0], "model", None)
                    and getattr(items[0].model, "text", None)
                )
            ):
                self.set_paragraph_align("left")
                return
        self._align_shapes("L")

    def _handle_align_center(self) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            items = ws.scene.selectedItems()
            if items and (
                getattr(items[0], "is_editing_text", False)
                or (
                    len(items) == 1
                    and getattr(items[0], "model", None)
                    and getattr(items[0].model, "text", None)
                )
            ):
                self.set_paragraph_align("center")
                return
        self._align_shapes("C")

    def _handle_align_right(self) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            items = ws.scene.selectedItems()
            if items and (
                getattr(items[0], "is_editing_text", False)
                or (
                    len(items) == 1
                    and getattr(items[0], "model", None)
                    and getattr(items[0].model, "text", None)
                )
            ):
                self.set_paragraph_align("right")
                return
        self._align_shapes("R")

    def show_status_message(self, message: str, timeout: int = 2000) -> None:
        """Show temporary message on the status bar."""
        sb = self.statusBar()
        if sb:
            sb.showMessage(message, timeout)

    def insert_table(self, rows: int = 2, cols: int = 2) -> None:
        """Insert a new table shape on the active slide."""
        from atboffice.modules.presentation.models.shape import Shape
        from atboffice.modules.presentation.tools import table_ops

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return
        slide = ws.current_slide
        from atboffice.modules.presentation.tools.pictures import unique_shape_id

        tid = unique_shape_id(slide, "tbl")
        w, h = 360.0, 160.0
        x = (960.0 - w) / 2.0
        y = (540.0 - h) / 2.0
        tbl_shape = Shape(
            id=tid,
            type="table",
            name=f"Table {tid}",
            x=x,
            y=y,
            w=w,
            h=h,
            tbl=table_ops.new_table(rows, cols, w, h),
        )
        slide.shapes.append(tbl_shape)
        ws.scene.load_slide(slide)
        item = ws.scene.get_shape_item(tid)
        if item:
            ws.scene.clearSelection()
            item.setSelected(True)
        self.set_modified(True)
        self.show_status_message(safe_tr("已插入表格"))

    def insert_chart(self, edit_data: bool = True) -> None:
        """Insert > Chart: a sample column chart, then its datasheet (PowerPoint 2003)."""
        from atboffice.modules.presentation.chart.model import ChartData
        from atboffice.modules.presentation.models.shape import Shape
        from atboffice.modules.presentation.tools.pictures import unique_shape_id

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return
        slide = ws.current_slide
        pres = self.presentation_view.presentation
        cid = unique_shape_id(slide, "chart")
        w, h = pres.w * 0.6, pres.h * 0.6
        chart_shape = Shape(
            id=cid,
            type="chart",
            name=f"Chart {cid.split('_')[-1]}",
            x=(pres.w - w) / 2.0,
            y=(pres.h - h) / 2.0,
            w=w,
            h=h,
            chart=ChartData.create_sample("col").to_dict(),
        )
        self.add_shape(chart_shape, message=safe_tr("已插入图表"))
        if edit_data:
            self.edit_chart_data(chart_shape)

    def edit_chart_data(self, chart_shape: Any) -> bool:
        """Open the Datasheet for ``chart_shape``; returns True when data changed."""
        from atboffice.modules.presentation.chart.model import ChartData
        from atboffice.modules.presentation.dialogs.datasheet_dialog import DatasheetDialog

        data = (
            chart_shape.chart
            if isinstance(chart_shape.chart, ChartData)
            else ChartData.from_dict(chart_shape.chart)
        )
        dlg = DatasheetDialog(chart=data, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        chart_shape.chart = dlg.get_chart_data().to_dict()
        item = self.presentation_view.workspace.scene.get_shape_item(chart_shape.id)
        if item is not None:
            item.update()
        self.set_modified(True)
        return True

    def add_shape(self, shape: Any, message: str = "") -> Any:
        """Add ``shape`` to the slide being edited, select it and mark the document dirty.

        Used by Insert commands and the shared WordArt / Clip Art insertion helpers.
        """
        ws = getattr(self.presentation_view, "workspace", None)
        if ws is None:
            return None
        slide = ws.master_slide if ws.view_mode == "master" and ws.master_slide else (
            ws.current_slide if ws.presentation.slides else None
        )
        if slide is None:
            return None
        slide.shapes.append(shape)
        ws.scene.load_slide(slide)
        item = ws.scene.get_shape_item(shape.id)
        if item is not None:
            ws.scene.clearSelection()
            item.setSelected(True)
        if ws.view_mode != "master" and hasattr(ws, "_refresh_current_thumbnail"):
            ws._refresh_current_thumbnail()
        self.set_modified(True)
        if message:
            self.show_status_message(message)
        return item

    def toggle_tables_toolbar(self) -> None:
        """Toggle visibility of the tables toolbar."""
        tb = self.toolbars.get("tables")
        if tb:
            tb.setVisible(not tb.isVisible())

    def set_view_color_mode(self, mode: str) -> None:
        """Set presentation viewport color mode ('color', 'grayscale', 'bw')."""
        self._color_mode = mode
        self.show_status_message(safe_tr(f"切换颜色模式: {mode}"))

    def toggle_grid(self) -> None:
        """Toggle slide alignment grid."""
        act = self.action_registry.get_action("showGrid")
        show = act.isChecked() if act else True
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "show_grid"):
            ws.show_grid = show
            if hasattr(ws, "update"):
                ws.update()
        self.show_status_message(safe_tr("显示网格与参考线" if show else "隐藏网格与参考线"))

    def _get_active_picture_shape(self) -> Any | None:
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.scene:
            return None
        for item in ws.scene.selectedItems():
            shape = getattr(item, "model", None)
            if shape and (shape.type in ("image", "picture") or getattr(shape, "media_item", None)):
                return shape
        return None

    def insert_picture_from_file(self, path: str | Path | None = None) -> Any:
        """Insert > Picture > From File: prompt for an image and embed its bytes."""
        from PySide6.QtWidgets import QFileDialog

        from atboffice.modules.presentation.tools.pictures import (
            IMAGE_EXTENSIONS,
            picture_shape_from_file,
        )

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return None
        if path is None:
            patterns = " ".join(f"*.{ext}" for ext in IMAGE_EXTENSIONS)
            chosen, _ = QFileDialog.getOpenFileName(
                self,
                safe_tr("插入图片"),
                "",
                safe_tr("所有图片") + f" ({patterns});;" + safe_tr("所有文件") + " (*)",
            )
            if not chosen:
                return None
            path = chosen
        try:
            shape = picture_shape_from_file(
                self.presentation_view.presentation, ws.current_slide, path
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                safe_tr("插入图片"),
                safe_tr("无法插入图片“{0}”：{1}").format(
                    Path(path).name,
                    safe_tr("文件不是可识别的图片格式")
                    if isinstance(exc, ValueError)
                    else exc.strerror or str(exc),
                ),
            )
            return None
        return self.add_shape(shape, message=safe_tr("已插入图片"))

    def compat_model_losses(self) -> list[Any]:
        return list(getattr(self.presentation, "losses", None) or [])

    def render_thumbnail(self, width: int = 240) -> Any:
        """Slide 1 with its design background."""
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QImage, QPainter

        from atboffice.modules.presentation.printing import paint_slide

        pres = self.presentation_view.presentation
        if not pres.slides:
            return None
        height = max(1, int(width * float(pres.h or 540.0) / float(pres.w or 960.0)))
        img = QImage(width, height, QImage.Format.Format_ARGB32)
        img.fill(QColor("#FFFFFF"))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        paint_slide(painter, pres.slides[0], pres, QRectF(0, 0, width, height))
        painter.end()
        return img

    def insert_image_bytes(self, data: bytes, ext: str = "png", name: str = "") -> bool:
        """Picture adapter used by Clip Art (and Paste of images)."""
        from atboffice.modules.presentation.tools.pictures import picture_shape_from_bytes

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.presentation.slides:
            return False
        try:
            shape = picture_shape_from_bytes(
                self.presentation_view.presentation, ws.current_slide, data, ext=ext, name=name
            )
        except ValueError:
            return False
        return self.add_shape(shape, message=safe_tr("已插入图片")) is not None

    def insert_wordart(self, png: bytes, spec: dict[str, Any]) -> bool:
        """Insert rendered WordArt and keep its spec so toolbar changes re-render it."""
        from atboffice.modules.common.wordart_gallery import wordart_box
        from atboffice.modules.presentation.tools.pictures import picture_shape_from_bytes

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.presentation.slides:
            return False
        pres = self.presentation_view.presentation
        w, h = wordart_box(spec)
        w, h = min(w + 12.0, pres.w * 0.9), min(h + 12.0, pres.h * 0.9)
        box = ((pres.w - w) / 2.0, (pres.h - h) / 2.0, w, h)
        shape = picture_shape_from_bytes(
            pres, ws.current_slide, png, ext="png", name=f"WordArt: {spec['text'][:20]}", box=box
        )
        shape.wordart = spec
        return self.add_shape(shape, message=safe_tr("已插入艺术字")) is not None

    def rotate_selected_left(self) -> None:
        """Rotate selected object 90 degrees counter-clockwise."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if hasattr(item, "model") and item.model:
                    item.model.rot = (item.model.rot - 90.0) % 360.0
                    item.setRotation(item.model.rot)
                    item.update()
        self.set_modified(True)
        self.show_status_message(safe_tr("向左旋转 90°"))

    def toggle_picture_crop(self) -> None:
        shape = self._get_active_picture_shape()
        if shape:
            shape.crop = not getattr(shape, "crop", False)
            self.show_status_message(safe_tr("裁剪图片"))
            self.set_modified(True)

    def reset_picture(self) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if hasattr(item, "model") and item.model:
                    item.model.rot = 0.0
                    item.setRotation(0.0)
                    item.update()
        self.show_status_message(safe_tr("重设图片"))
        self.set_modified(True)

    def adjust_picture_contrast(self, delta: float) -> None:
        shape = self._get_active_picture_shape()
        if shape:
            shape.contrast = getattr(shape, "contrast", 1.0) + delta
            self.show_status_message(safe_tr("调整对比度"))
            self.set_modified(True)

    def adjust_picture_brightness(self, delta: float) -> None:
        shape = self._get_active_picture_shape()
        if shape:
            shape.brightness = getattr(shape, "brightness", 1.0) + delta
            self.show_status_message(safe_tr("调整亮度"))
            self.set_modified(True)

    def set_picture_color_mode(self, mode: str) -> None:
        shape = self._get_active_picture_shape()
        if shape:
            shape.color_mode = mode
            self.show_status_message(safe_tr(f"图片颜色模式: {mode}"))
            self.set_modified(True)

    def _get_active_wordart_shape(self) -> Any | None:
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.scene:
            return None
        for item in ws.scene.selectedItems():
            shape = getattr(item, "model", None)
            if shape and (
                shape.type == "wordart" or getattr(shape, "name", "").startswith("WordArt")
            ):
                return shape
        return None

    def toggle_wordart_same_height(self) -> None:
        shape = self._get_active_wordart_shape()
        if shape:
            shape.same_height = not getattr(shape, "same_height", False)
            self.show_status_message(safe_tr("艺术字同样高度"))
            self.set_modified(True)

    def toggle_wordart_vertical(self) -> None:
        shape = self._get_active_wordart_shape()
        if shape:
            shape.vertical = not getattr(shape, "vertical", False)
            self.show_status_message(safe_tr("艺术字垂直文字"))
            self.set_modified(True)

    def set_wordart_shape(self, shape_name: str) -> None:
        shape = self._get_active_wordart_shape()
        if shape:
            shape.wa_shape = shape_name
            self.show_status_message(safe_tr(f"艺术字形状: {shape_name}"))
            self.set_modified(True)

    def set_wordart_align(self, alignment: str) -> None:
        shape = self._get_active_wordart_shape()
        if shape:
            shape.wa_align = alignment
            self.show_status_message(safe_tr(f"艺术字对齐: {alignment}"))
            self.set_modified(True)

    def toggle_hide_slide(self) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.current_slide:
            ws.current_slide.hidden = not getattr(ws.current_slide, "hidden", False)
            self.show_status_message(
                safe_tr("隐藏幻灯片" if ws.current_slide.hidden else "显示幻灯片")
            )
            self.set_modified(True)

    def start_rehearse(self) -> Any:
        """Slide Show > Rehearse Timings: record each slide's time into its transition."""
        recorder = self.presentation_view.workspace.start_rehearsal(fullscreen=True)
        if recorder is not None:
            recorder.timings_saved.connect(lambda _t: self.set_modified(True))
            self.show_status_message(safe_tr("排练计时：放映结束时可保留新的计时"))
        return recorder

    def _setup_lectern_task_panes(self) -> None:
        """Register Lectern specific task panes (Layout, Design, Color, Animation)."""
        if not self.task_pane_dock:
            return

        from atboffice.modules.presentation.panes import (
            AnimationSchemesPane,
            ColorSchemesPane,
            SlideDesignPane,
            SlideLayoutPane,
            SmartArtPane,
        )

        pres = getattr(self.presentation_view, "presentation", None)

        self.slide_layout_pane = SlideLayoutPane(presentation=pres, parent=self.task_pane_dock)
        self.slide_design_pane = SlideDesignPane(presentation=pres, parent=self.task_pane_dock)
        self.color_schemes_pane = ColorSchemesPane(presentation=pres, parent=self.task_pane_dock)
        self.animation_schemes_pane = AnimationSchemesPane(
            presentation=pres, parent=self.task_pane_dock
        )
        self.smartart_pane = SmartArtPane(presentation=pres, parent=self.task_pane_dock)
        self.smartart_pane.diagram_changed.connect(self._on_smartart_diagram_changed)
        self.smartart_pane.converted_to_shapes.connect(self._on_smartart_converted)

        # Wire navigation between panes
        for pane in (self.slide_design_pane, self.color_schemes_pane, self.animation_schemes_pane):
            pane.navigate_pane.connect(self._on_task_pane_navigate)

        # Wire layout, design & scheme application
        self.slide_layout_pane.layout_applied.connect(self._on_apply_slide_layout)
        self.slide_design_pane.apply_design_requested.connect(self._on_apply_design_template)
        self.color_schemes_pane.apply_color_scheme_requested.connect(self._on_apply_color_scheme)
        self.animation_schemes_pane.apply_animation_scheme_requested.connect(self._on_apply_animation_scheme)
        self.animation_schemes_pane.play_requested.connect(self._on_play_slide_animation)
        self.animation_schemes_pane.slide_show_requested.connect(self.start_slideshow_current)

        self.task_pane_dock.register_pane(
            "slide_layout",
            safe_tr("幻灯片版式"),
            self.slide_layout_pane,
        )
        self.task_pane_dock.register_pane(
            "slide_design",
            safe_tr("幻灯片设计 - 设计模板"),
            self.slide_design_pane,
        )
        self.task_pane_dock.register_pane(
            "color_schemes",
            safe_tr("幻灯片设计 - 配色方案"),
            self.color_schemes_pane,
        )
        self.task_pane_dock.register_pane(
            "animation_schemes",
            safe_tr("幻灯片设计 - 动画方案"),
            self.animation_schemes_pane,
        )
        self.task_pane_dock.register_pane(
            "smartart_pane",
            safe_tr("IntelliArt 智能图示"),
            self.smartart_pane,
        )

    def _on_apply_slide_layout(self, layout_key: str) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws:
            ws.apply_layout(layout_key)
        self.show_status_message(safe_tr(f"已应用版式: {layout_key}"))

    def open_slide_layout_pane(self) -> None:
        """Open or activate the Slide Layout task pane."""
        self.show_status_message(safe_tr("打开幻灯片版式窗格"))
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("slide_layout")

    def _on_task_pane_navigate(self, target: str) -> None:
        if not self.task_pane_dock:
            return
        mapping = {
            "design": "slide_design",
            "colors": "color_schemes",
            "animations": "animation_schemes",
        }
        pane_id = mapping.get(target, target)
        self.task_pane_dock.show_pane(pane_id)

    def _on_apply_design_template(self, design_key: str, apply_to_all: bool) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        pres = getattr(self.presentation_view, "presentation", None)
        if not pres:
            return
        curr = [ws.current_slide] if ws and getattr(ws, "current_slide", None) else pres.slides
        target_slides = pres.slides if apply_to_all else curr
        pres.apply_design(design_key, target_slides)
        if ws:
            if hasattr(ws, "render_current_slide"):
                ws.render_current_slide()
            elif hasattr(ws, "update"):
                ws.update()
        if hasattr(self, "slide_design_pane"):
            self.slide_design_pane.refresh_used_designs()
        self.show_status_message(safe_tr(f"已应用设计模板: {design_key}"))
        self.set_modified(True)

    def _on_apply_color_scheme(self, scheme: Any, apply_to_all: bool) -> None:
        import copy
        ws = getattr(self.presentation_view, "workspace", None)
        pres = getattr(self.presentation_view, "presentation", None)
        if not pres:
            return
        curr = [ws.current_slide] if ws and getattr(ws, "current_slide", None) else pres.slides
        target_slides = pres.slides if apply_to_all else curr
        for s in target_slides:
            did = getattr(s, "design_id", None) or getattr(s, "design", None)
            d = pres.designs.get(did) if hasattr(pres, "designs") else None
            if d:
                d.colors = copy.deepcopy(scheme)
        if ws:
            if hasattr(ws, "render_current_slide"):
                ws.render_current_slide()
            elif hasattr(ws, "update"):
                ws.update()
        self.show_status_message(safe_tr("已应用配色方案"))
        self.set_modified(True)

    def _on_apply_animation_scheme(self, scheme_key: str, apply_to_all: bool) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        pres = getattr(self.presentation_view, "presentation", None)
        if not pres:
            return
        curr = [ws.current_slide] if ws and getattr(ws, "current_slide", None) else pres.slides
        target_slides = pres.slides if apply_to_all else curr
        for s in target_slides:
            s.animation_scheme = scheme_key
        self.show_status_message(safe_tr(f"已应用动画方案: {scheme_key}"))
        self.set_modified(True)

    def _on_play_slide_animation(self) -> None:
        self.lectern_commands.play_slide_animation()

    def open_slide_design_pane(self) -> None:
        self.show_status_message(safe_tr("打开幻灯片设计窗格"))
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("slide_design")

    def open_color_schemes_pane(self) -> None:
        self.show_status_message(safe_tr("打开配色方案窗格"))
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("color_schemes")

    def open_animation_schemes_pane(self) -> None:
        self.show_status_message(safe_tr("打开动画方案窗格"))
        if self.task_pane_dock is not None:
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("animation_schemes")

    def show_smartart_pane(self, shape: Any = None) -> None:
        """Open or activate the IntelliArt SmartArt task pane."""
        self.show_status_message(safe_tr("打开智能图示窗格"))
        if self.task_pane_dock is not None:
            if hasattr(self, "smartart_pane") and self.smartart_pane is not None:
                diag = (
                    shape
                    if shape is not None and hasattr(shape, "sa")
                    else self._get_active_diagram_shape()
                )
                self.smartart_pane.set_diagram(diag)
            self.task_pane_dock.show()
            self.task_pane_dock.show_pane("smartart_pane")

    def _on_smartart_diagram_changed(self, shape: Any) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
            ws.scene.load_slide(ws.current_slide)
            if hasattr(shape, "id") and hasattr(ws.scene, "get_shape_item"):
                item = ws.scene.get_shape_item(shape.id)
                if item:
                    item.setSelected(True)
        self.set_modified(True)

    def _on_smartart_converted(self, shape: Any) -> None:
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "scene") and ws.scene and hasattr(ws, "current_slide"):
            ws.scene.load_slide(ws.current_slide)
        self.set_modified(True)

    def open_action_settings_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import ActionSettingsDialog

        pres = getattr(self.presentation_view, "presentation", None)
        dlg = ActionSettingsDialog(presentation=pres, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            settings = dlg.get_action_settings()
            if self.lectern_commands.apply_action_settings(settings):
                self.show_status_message(safe_tr("动作设置已应用"))
                self.set_modified(True)
            else:
                self.show_status_message(safe_tr("请先选择要设置动作的对象"), 3000)

    def open_setup_show_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import SetUpShowDialog

        pres = getattr(self.presentation_view, "presentation", None)
        dlg = SetUpShowDialog(presentation=pres, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_status_message(safe_tr("放映设置已更新"))
            self.set_modified(True)

    def open_photo_album_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import PhotoAlbumDialog

        dlg = PhotoAlbumDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            spec = dlg.get_album_spec()
            self._create_photo_album_slides(spec)
            self.show_status_message(safe_tr("相册幻灯片已创建"))
            self.set_modified(True)

    def _create_photo_album_slides(self, spec: dict[str, Any]) -> None:
        from atboffice.modules.presentation.models.slide import Slide
        from atboffice.modules.presentation.tools.pictures import picture_shape_from_file

        pres = getattr(self.presentation_view, "presentation", None)
        if not pres:
            return

        pics = spec.get("pictures", [])
        failed: list[str] = []
        for pic_path in pics:
            slide = Slide(id=f"sl_photo_{len(pres.slides) + 1}", layout="blank")
            try:
                shape = picture_shape_from_file(
                    pres, slide, pic_path, box=(50.0, 50.0, pres.w - 100.0, pres.h - 100.0)
                )
            except (OSError, ValueError):
                failed.append(Path(pic_path).name)
                continue
            slide.shapes.append(shape)
            pres.slides.append(slide)
        if failed:
            QMessageBox.warning(
                self,
                safe_tr("相册"),
                safe_tr("以下图片无法插入：\n{0}").format("\n".join(failed)),
            )

        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "update_slides"):
            ws.update_slides()

    def open_options_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import LecternOptionsDialog

        dlg = LecternOptionsDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_status_message(safe_tr("选项设置已更新"))

    def open_fill_effects_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import FillEffectsDialog

        dlg = FillEffectsDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.show_status_message(safe_tr("填充效果已配置"))
            self.set_modified(True)

    def select_all(self) -> None:
        """Select all shapes on current slide or all text in active editor."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.selectAll()
                    return
            for item in ws.scene.items():
                if hasattr(item, "setSelected"):
                    item.setSelected(True)
        self._sync_toolbar_states()

    def save_as_dialog(self) -> bool:
        """Prompt user with Save As dialog (never silently overwrites the current file)."""
        return self.save_file_as()

    def _wire_toolbar_widgets(self) -> None:
        """Connect toolbar combo boxes, color pickers, and menus."""
        # 1. Formatting toolbar widgets
        fmt_tb = self.toolbars.get("formatting")
        if fmt_tb:
            font_combo = fmt_tb.findChild(QComboBox, "Lectern_FontCombo")
            if font_combo:
                self.font_combo = font_combo
                font_combo.currentTextChanged.connect(self._on_font_combo_changed)

            size_combo = fmt_tb.findChild(QComboBox, "Lectern_SizeCombo")
            if size_combo:
                self.size_combo = size_combo
                size_combo.currentTextChanged.connect(self._on_size_combo_changed)

            font_color_btn = fmt_tb.findChild(ColorPickerButton, "Lectern_FontColorBtn")
            if font_color_btn:
                self.font_color_btn = font_color_btn
                font_color_btn.color_applied.connect(self._on_font_color_selected)

        # 2. Standard toolbar zoom combo
        std_tb = self.toolbars.get("standard")
        if std_tb:
            zoom_combo = std_tb.findChild(QComboBox, "Lectern_ZoomCombo")
            if zoom_combo:
                self.zoom_combo = zoom_combo
                zoom_combo.currentTextChanged.connect(self._on_zoom_combo_changed)

        # 3. Drawing toolbar color pickers
        draw_tb = self.toolbars.get("drawing")
        if draw_tb:
            draw_fill_btn = draw_tb.findChild(ColorPickerButton, "Lectern_DrawFillColor")
            if draw_fill_btn:
                self.draw_fill_btn = draw_fill_btn
                draw_fill_btn.color_applied.connect(self._on_shape_fill_color_selected)

            draw_line_btn = draw_tb.findChild(ColorPickerButton, "Lectern_DrawLineColor")
            if draw_line_btn:
                self.draw_line_btn = draw_line_btn
                draw_line_btn.color_applied.connect(self._on_shape_line_color_selected)

            draw_font_btn = draw_tb.findChild(ColorPickerButton, "Lectern_DrawFontColor")
            if draw_font_btn:
                self.draw_font_btn = draw_font_btn
                draw_font_btn.color_applied.connect(self._on_font_color_selected)

    def _on_font_combo_changed(self, font_name: str) -> None:
        """Apply font family to selected text or active text editor."""
        if getattr(self, "_syncing_toolbars", False):
            return
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_font_family(font_name)
                elif getattr(item, "model", None) and item.model.text:
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.font = font_name
                    item.update()
        self.set_modified(True)

    def _on_size_combo_changed(self, size_text: str) -> None:
        """Apply font size to selected text or active text editor."""
        if getattr(self, "_syncing_toolbars", False):
            return
        try:
            sz = float(size_text.strip().replace("pt", ""))
        except ValueError:
            return
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_font_size(sz)
                elif getattr(item, "model", None) and item.model.text:
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.size = sz
                    item.update()
        self.set_modified(True)

    def _on_zoom_combo_changed(self, zoom_text: str) -> None:
        """Adjust viewport zoom level based on zoom combo selection."""
        if getattr(self, "_syncing_toolbars", False):
            return
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws:
            return
        clean = zoom_text.strip().replace("%", "")
        try:
            pct = float(clean)
            scale_val = pct / 100.0
            if hasattr(ws, "set_zoom"):
                ws.set_zoom(scale_val)
        except ValueError:
            if hasattr(ws, "fit_to_window"):
                ws.fit_to_window()

    def _on_canvas_zoom_changed(self, zoom: float) -> None:
        """Synchronize zoom combobox when canvas zoom level changes."""
        if getattr(self, "_syncing_toolbars", False):
            return
        if not hasattr(self, "zoom_combo") or not self.zoom_combo:
            return
        ws = getattr(self.presentation_view, "workspace", None)
        is_fit = getattr(ws, "is_auto_fit", False)
        self._syncing_toolbars = True
        try:
            if is_fit:
                self.zoom_combo.setCurrentText(safe_tr("适合比例"))
            else:
                self.zoom_combo.setCurrentText(f"{int(round(zoom * 100))}%")
        finally:
            self._syncing_toolbars = False

    def fit_to_window(self) -> None:
        """Fit presentation canvas into current workspace viewport."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "fit_to_window"):
            ws.fit_to_window()

    def set_zoom(self, zoom: float) -> None:
        """Set zoom scale on presentation canvas."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and hasattr(ws, "set_zoom"):
            ws.set_zoom(zoom)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._safe_fit_to_window()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._safe_fit_to_window()

    def _safe_fit_to_window(self) -> None:
        """Fit canvas to window only when visible with non-zero viewport and without re-entrancy."""
        if getattr(self, "_is_fitting_window", False) or not self.isVisible():
            return
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not getattr(ws, "is_auto_fit", False) or not hasattr(ws, "fit_to_window"):
            return
        canvas_view = getattr(ws, "canvas_view", None)
        if canvas_view is not None:
            vp = canvas_view.viewport()
            if vp is None or vp.width() <= 0 or vp.height() <= 0:
                return
        self._is_fitting_window = True
        try:
            ws.fit_to_window()
        finally:
            self._is_fitting_window = False

    def _on_font_color_selected(self, color_hex: str) -> None:
        """Apply font color to selected text."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                    item._text_editor.set_font_color(color_hex)
                elif getattr(item, "model", None) and item.model.text:
                    for p in item.model.text.paragraphs:
                        for r in p.runs:
                            r.color = color_hex
                    item.update()
        self.set_modified(True)

    def _on_shape_fill_color_selected(self, color_hex: str) -> None:
        """Apply background fill color to selected shapes."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if hasattr(item, "model") and item.model:
                    from atboffice.modules.presentation.models.shape import Fill

                    item.model.fill = Fill.solid(color_hex)
                    item.update()
        self.set_modified(True)

    def _on_shape_line_color_selected(self, color_hex: str) -> None:
        """Apply outline color to selected shapes."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws and ws.scene:
            for item in ws.scene.selectedItems():
                if hasattr(item, "model") and item.model:
                    item.model.line.color = color_hex
                    item.update()
        self.set_modified(True)

    def _sync_toolbar_states(self) -> None:
        """Synchronize toolbar toggle buttons, combos, and contextual enablement
        with current selection."""
        if not hasattr(self, "presentation_view") or not hasattr(self, "action_registry"):
            return

        ws = getattr(self.presentation_view, "workspace", None)
        if ws is None or not hasattr(ws, "scene") or ws.scene is None:
            return

        selected_items = ws.scene.selectedItems()
        sel_count = len(selected_items)

        is_table = False
        is_picture = False
        is_diagram = False
        is_wordart = False
        has_group = False

        active_editor = None
        target_shape = None

        for item in selected_items:
            shape = getattr(item, "model", None)
            stype = getattr(shape, "type", "") if shape else ""
            if stype in ("table",) or (shape and getattr(shape, "tbl", None)):
                is_table = True
            elif stype in ("image", "picture") or (shape and getattr(shape, "media_item", None)):
                is_picture = True
            elif (
                stype in ("diagram", "smartart")
                or (shape and getattr(shape, "is_diagram", False))
                or (shape and getattr(shape, "sa", None))
            ):
                is_diagram = True
            elif stype in ("wordart",) or (
                shape and getattr(shape, "name", "").startswith("WordArt")
            ):
                is_wordart = True
            elif stype == "group":
                has_group = True

            if getattr(item, "is_editing_text", False) and getattr(item, "_text_editor", None):
                active_editor = item._text_editor
            if target_shape is None and shape is not None:
                target_shape = shape

        if not is_diagram and hasattr(self, "toolbars"):
            diag_tb = self.toolbars.get("diagram")
            if diag_tb and diag_tb.isVisible():
                is_diagram = True
        if not is_table and hasattr(self, "toolbars"):
            tbl_tb = self.toolbars.get("tables")
            if tbl_tb and tbl_tb.isVisible():
                is_table = True
        if not is_picture and hasattr(self, "toolbars"):
            pic_tb = self.toolbars.get("picture")
            if pic_tb and pic_tb.isVisible():
                is_picture = True
        if not is_wordart and hasattr(self, "toolbars"):
            wa_tb = self.toolbars.get("wordart")
            if wa_tb and wa_tb.isVisible():
                is_wordart = True

        # 1. Update text formatting states (bold, italic, underline, shadow, alignment)
        is_bold = False
        is_italic = False
        is_underline = False
        align_code = "left"

        if active_editor is not None:
            cursor = active_editor.textCursor()
            fmt = cursor.charFormat()
            is_bold = fmt.fontWeight() == QFont.Weight.Bold or fmt.font().bold()
            is_italic = fmt.fontItalic()
            is_underline = fmt.fontUnderline()
            block_fmt = cursor.blockFormat()
            alignment = block_fmt.alignment()
            if alignment & Qt.AlignmentFlag.AlignHCenter:
                align_code = "center"
            elif alignment & Qt.AlignmentFlag.AlignRight:
                align_code = "right"
            elif alignment & Qt.AlignmentFlag.AlignJustify:
                align_code = "justify"
            else:
                align_code = "left"
        elif target_shape and target_shape.text and target_shape.text.paragraphs:
            p0 = target_shape.text.paragraphs[0]
            if p0.runs:
                r0 = p0.runs[0]
                is_bold = bool(r0.bold)
                is_italic = bool(r0.italic)
                is_underline = bool(r0.underline)
            algn = p0.props.get("algn", "l")
            if algn in ("ctr", "center"):
                align_code = "center"
            elif algn in ("r", "right"):
                align_code = "right"
            elif algn in ("just", "justify"):
                align_code = "justify"
            else:
                align_code = "left"

        act_b = self.action_registry.get_action("bold")
        if act_b:
            act_b.setChecked(is_bold)
        act_i = self.action_registry.get_action("italic")
        if act_i:
            act_i.setChecked(is_italic)
        act_u = self.action_registry.get_action("underline")
        if act_u:
            act_u.setChecked(is_underline)

        for aid, code in [
            ("alignLeft", "left"),
            ("alignCenter", "center"),
            ("alignRight", "right"),
        ]:
            act_al = self.action_registry.get_action(aid)
            if act_al:
                act_al.setChecked(align_code == code)

        # 2. Contextual enablement rules
        act_grp = self.action_registry.get_action("group")
        if act_grp:
            act_grp.setEnabled(sel_count >= 2)
        act_ungrp = self.action_registry.get_action("ungroup")
        if act_ungrp:
            act_ungrp.setEnabled(has_group)
        act_regrp = self.action_registry.get_action("regroup")
        if act_regrp:
            act_regrp.setEnabled(bool(getattr(self, "_last_ungrouped_ids", None)))

        for aid in ("bringFront", "sendBack", "bringForward", "sendBackward"):
            act = self.action_registry.get_action(aid)
            if act:
                act.setEnabled(sel_count >= 1)

        for aid in (
            "alignLeft",
            "alignCenter",
            "alignRight",
            "alignTop",
            "alignMiddle",
            "alignBottom",
            "distributeH",
            "distributeV",
        ):
            act = self.action_registry.get_action(aid)
            if act and not act.isCheckable():
                act.setEnabled(sel_count >= 1)

        table_actions = [
            "tableMergeCells",
            "tableSplitCell",
            "cellTop",
            "cellMiddle",
            "cellBottom",
            "distRows",
            "distCols",
            "tableBordersAll",
            "tbl_insert_col_left",
            "tbl_insert_col_right",
            "tbl_insert_row_above",
            "tbl_insert_row_below",
            "tbl_delete_col",
            "tbl_delete_row",
            "tbl_border_all",
            "tbl_border_outside",
            "tbl_border_none",
        ]
        for aid in table_actions:
            act = self.action_registry.get_action(aid)
            if act:
                act.setEnabled(is_table)

        pic_actions = [
            "picCrop",
            "rotateLeft",
            "picMoreContrast",
            "picLessContrast",
            "picMoreBright",
            "picLessBright",
            "picReset",
            "picTransparent",
            "formatObject",
            "pic_color_mode",
            "pic_color_auto",
            "pic_color_gray",
            "pic_color_bw",
            "pic_color_washout",
            "pic_weight_075",
            "pic_weight_15",
            "pic_weight_30",
            "pic_weight_45",
            "pic_weight_60",
        ]
        for aid in pic_actions:
            act = self.action_registry.get_action(aid)
            if act:
                act.setEnabled(is_picture)

        wordart_actions = [
            "wordartEdit",
            "wordartGallery",
            "wa_format",
            "waSameHeight",
            "waVertical",
            "wa_align_left",
            "wa_align_center",
            "wa_align_right",
            "wa_align_justify",
            "wa_spacing_very_tight",
            "wa_spacing_tight",
            "wa_spacing_normal",
            "wa_spacing_loose",
            "wa_spacing_very_loose",
        ]
        for aid in wordart_actions:
            act = self.action_registry.get_action(aid)
            if act:
                act.setEnabled(is_wordart)

        diag_actions = [
            "diagramAddShape",
            "diagramAddAfter",
            "diagramAddBefore",
            "diagramAddAbove",
            "diagramAddBelow",
            "diagramPromote",
            "diagramDemote",
            "diagramMoveUp",
            "diagramMoveDown",
            "diagramReset",
            "diagramToShapes",
        ]
        for aid in diag_actions:
            act = self.action_registry.get_action(aid)
            if act:
                act.setEnabled(is_diagram)

    def _on_slide_changed(self, _index: int = 0) -> None:
        """Update slide indicator on navigation without marking dirty."""
        if hasattr(self, "lbl_status_slide"):
            ws = self.presentation_view.workspace
            curr = getattr(ws, "current_slide_index", 0) + 1
            slides = getattr(ws.presentation, "slides", [])
            total = len(slides) if slides else 1
            self.lbl_status_slide.setText(f"{safe_tr('幻灯片')} {curr} / {total}")

    def _on_presentation_modified(self) -> None:
        """Mark presentation as modified when slide content or layout changes."""
        self.set_modified(True)
        self._on_slide_changed()

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
            shape = getattr(item, "model", None)
            stype = getattr(shape, "type", "") if shape else ""
            if stype in ("table",) or (shape and getattr(shape, "tbl", None)):
                is_table = True
            elif stype in ("image", "picture") or (shape and getattr(shape, "media_item", None)):
                is_picture = True
            elif (
                stype in ("diagram", "smartart")
                or (shape and getattr(shape, "is_diagram", False))
                or (shape and getattr(shape, "sa", None))
            ):
                is_diagram = True
            elif stype in ("wordart",) or (
                shape and getattr(shape, "name", "").startswith("WordArt")
            ):
                is_wordart = True

        self.update_context_toolbars(
            {
                "is_table": is_table,
                "is_picture": is_picture,
                "is_diagram": is_diagram,
                "is_wordart": is_wordart,
            }
        )
        if hasattr(self, "smartart_pane") and self.smartart_pane is not None:
            if is_diagram:
                diag = self._get_active_diagram_shape()
                if diag and getattr(diag, "sa", None) and self.smartart_pane.current_shape != diag:
                    self.smartart_pane.set_diagram(diag)
        self._sync_toolbar_states()

    def _on_left_pane_tab_changed(self, index: int) -> None:
        """Handle left pane tab change between Slides (0) and Outline (1)."""
        is_outline = index == 1
        self.update_context_toolbars({"is_outline": is_outline})
        self._sync_toolbar_states()

    @property
    def default_doc_name(self) -> str:
        """Default document name for Lectern presentations."""
        return safe_tr("未命名演示文稿")

    def update_window_title(self) -> None:
        """Set window title according to active presentation and dirty flag."""
        if self.current_file_path is not None:
            doc_name = self.current_file_path.name
        elif getattr(self, "active_template", None) is not None:
            tag = safe_tr("基于模板")
            doc_name = f"{self.default_doc_name} [{tag}: {self.active_template.name}]"
        else:
            doc_name = self.default_doc_name
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Lectern save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.pptx *.ppsx *.potx);;"
            "PowerPoint 演示文稿 (*.pptx *.ppsx *.potx);;"
            "PowerPoint 97-2003 演示文稿 (*.ppt *.pps *.pot);;"
            "所有文件 (*.*)"
        )

    @property
    def presentation(self):
        """Return the bound Presentation model."""
        return self.presentation_view.presentation

    def _apply_template_result(self, result: Any) -> None:
        """Apply generated template Presentation model to presentation view."""
        if result is not None:
            from atboffice.modules.presentation.models.presentation import Presentation

            if isinstance(result, Presentation):
                self.presentation_view.load_presentation(result)

    def new_file(self) -> bool:
        """Create a new blank presentation document."""
        if not super().new_file():
            return False
        from atboffice.modules.presentation.models.presentation import Presentation

        self.presentation_view.load_presentation(Presentation.create_new())
        return True

    def do_save(self, path: Path) -> bool:
        """Serialize Lectern presentation to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in {".ppt", ".pps", ".pot"}:
            return False
        if ext in {".pptx", ".pptm", ".ppsx", ".potx"}:
            from atboffice.modules.presentation.io.pptx_writer import write_pptx

            # Text typed into an open in-place editor must reach the file (and drafts)
            # without ending the user's editing session.
            ws = getattr(self.presentation_view, "workspace", None)
            scene = getattr(ws, "scene", None)
            if scene is not None and hasattr(scene, "sync_active_text_editing"):
                scene.sync_active_text_editing()

            if not self.confirm_compatibility_losses(
                getattr(self.presentation, "losses", None)
            ):
                return False
            write_pptx(self.presentation, path)
            return True
        raise UnsupportedSaveFormatError(ext)

    def do_open(self, path: Path) -> bool:
        """Parse and load Lectern presentation from disk with transactional rollback."""
        self._cleanup_active_editing_and_overlays()

        if path.stat().st_size == 0:
            from atboffice.modules.presentation.models.presentation import Presentation

            candidate_pres = Presentation.create_new()
            self.presentation_view.load_presentation(candidate_pres)
            return True

        ext = path.suffix.lower()

        # 1. Check if legacy or disguised binary presentation
        self.check_legacy_or_disguised_file(path, "lectern")

        # 2. Check for encrypted package
        decrypted_bytes, is_enc = self.try_decrypt_if_encrypted(path)

        # 3. Parse into candidate presentation
        candidate_pres = None
        if ext in {".pptx", ".ppsx", ".potx"} or is_enc:
            from atboffice.modules.presentation.io.pptx_reader import read_pptx

            source = decrypted_bytes if is_enc and decrypted_bytes is not None else path
            candidate_pres = read_pptx(source)
        else:
            return False

        if candidate_pres is None:
            return False

        # 4. Transactional UI binding with rollback
        old_pres = self.presentation_view.presentation
        try:
            self.presentation_view.load_presentation(candidate_pres)
        except Exception as bind_err:
            try:
                self.presentation_view.load_presentation(old_pres)
            except Exception:
                pass
            raise bind_err

        return True

    def _cleanup_active_editing_and_overlays(self) -> None:
        """Close active text editor, comment cards, or running slideshow before opening."""
        ws = getattr(self.presentation_view, "workspace", None)
        if ws is None:
            return
        active_show = getattr(ws, "_active_slideshow", None)
        if active_show is not None:
            try:
                active_show.end_show(prompt_ink=False)
            except Exception:
                pass
            ws._active_slideshow = None
        canvas_view = getattr(ws, "canvas_view", None)
        if canvas_view is not None and getattr(canvas_view, "_active_card", None) is not None:
            try:
                canvas_view._active_card.close()
            except Exception:
                pass
            canvas_view._active_card = None
        scene = getattr(ws, "scene", None)
        if scene is not None and hasattr(scene, "finish_active_text_editing"):
            scene.finish_active_text_editing(commit=False)

    def _setup_toolbars(self) -> None:
        """Initialize PowerPoint 2003 Luna 10 toolbars cluster."""
        self.toolbars: dict[str, OfficeToolBar] = build_lectern_toolbars(self, self.action_registry)

        # Row 1: Standard toolbar
        if "standard" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["standard"])

        # Row 2: Formatting toolbar
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        if "formatting" in self.toolbars:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.toolbars["formatting"])

        # Row 3: Drawing and presentation toolbars
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        for name in [
            "drawing",
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
        self._wire_toolbar_widgets()
        self._sync_toolbar_states()

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
        new_slide = self.presentation_view.presentation.add_slide()
        self.presentation_view.load_slide(new_slide)
        self.set_modified(True)

    def start_slideshow(self) -> None:
        """Start presentation slideshow from the beginning."""
        self.presentation_view.start_slideshow(from_current=False, fullscreen=True)

    def start_slideshow_current(self) -> None:
        """Start presentation slideshow from the current slide."""
        self.presentation_view.start_slideshow(from_current=True, fullscreen=True)

    def set_view_mode(self, mode: str) -> None:
        """Switch workspace view mode ('normal', 'sorter', 'notes', or 'master')."""
        self.presentation_view.set_view_mode(mode)
        act_normal = self.action_registry.get_action("viewNormal")
        if act_normal:
            act_normal.setChecked(mode == "normal")
        act_sorter = self.action_registry.get_action("viewSorter")
        if act_sorter:
            act_sorter.setChecked(mode == "sorter")
        act_notes = self.action_registry.get_action("viewNotesPage")
        if act_notes:
            act_notes.setChecked(mode == "notes")
        act_master = self.action_registry.get_action("viewMaster")
        if act_master:
            act_master.setChecked(mode == "master")
        if hasattr(self, "act_view_normal") and self.act_view_normal:
            self.act_view_normal.setChecked(mode == "normal")
        if hasattr(self, "act_view_sorter") and self.act_view_sorter:
            self.act_view_sorter.setChecked(mode == "sorter")
        if hasattr(self, "act_view_notes") and self.act_view_notes:
            self.act_view_notes.setChecked(mode == "notes")
        if hasattr(self, "act_view_master") and self.act_view_master:
            self.act_view_master.setChecked(mode == "master")

        # Sync status bar buttons
        if hasattr(self, "btn_view_normal") and self.btn_view_normal:
            self.btn_view_normal.setChecked(mode == "normal")
        if hasattr(self, "btn_view_sorter") and self.btn_view_sorter:
            self.btn_view_sorter.setChecked(mode == "sorter")
        if hasattr(self, "btn_view_notes") and self.btn_view_notes:
            self.btn_view_notes.setChecked(mode == "notes")

        self.update_context_toolbars({"view_mode": mode})
        self._sync_toolbar_states()

    def render_to_printer(
        self,
        printer: QPrinter,
        mode: str | None = None,
        grayscale: bool = False,
    ) -> None:
        """Print / preview / PDF using the current print options (File > Print What)."""
        import dataclasses

        from atboffice.modules.presentation.printing import render_presentation

        options = dataclasses.replace(self.print_options)
        if mode is not None:
            options.what = mode
        if grayscale:
            options.color = "grayscale"
        if not options.title:
            options.title = (
                self.current_file_path.stem if self.current_file_path else self.default_doc_name
            )
        render_presentation(printer, self.presentation_view.presentation, options)

    @property
    def print_options(self) -> Any:
        from atboffice.modules.presentation.printing import PresentationPrintOptions

        opts = getattr(self, "_print_options", None)
        if opts is None:
            opts = self._print_options = PresentationPrintOptions()
        return opts

    def print_preview_extras(self, panel: Any) -> None:
        """PowerPoint 2003 preview controls: Print What, Color/Grayscale, Frame, Hidden."""
        from PySide6.QtWidgets import QCheckBox, QComboBox

        from atboffice.modules.presentation.printing import HANDOUT_COUNTS

        opts = self.print_options
        what = QComboBox()
        what.setObjectName("printWhatCombo")
        # Item data are plain strings ("handouts:4"): tuples do not survive QVariant.
        choices: list[tuple[str, str]] = [(safe_tr("幻灯片"), "slides")]
        choices += [
            (safe_tr("讲义（每页 {0} 张幻灯片）").format(n), f"handouts:{n}")
            for n in HANDOUT_COUNTS
        ]
        choices += [(safe_tr("备注页"), "notes"), (safe_tr("大纲视图"), "outline")]
        for label, data in choices:
            what.addItem(label, data)
        current = f"handouts:{opts.per_page}" if opts.what == "handouts" else opts.what
        what.setCurrentIndex(max(0, what.findData(current)))
        what.setToolTip(safe_tr("打印内容"))

        color = QComboBox()
        color.setObjectName("printColorCombo")
        for label, key in ((safe_tr("颜色"), "color"), (safe_tr("灰度"), "grayscale"),
                           (safe_tr("纯黑白"), "bw")):
            color.addItem(label, key)
        color.setCurrentIndex(max(0, color.findData(opts.color)))
        color.setToolTip(safe_tr("颜色/灰度"))

        frame = QCheckBox(safe_tr("幻灯片加框"))
        frame.setObjectName("printFrameCheck")
        frame.setChecked(opts.frame_slides)
        hidden = QCheckBox(safe_tr("打印隐藏幻灯片"))
        hidden.setObjectName("printHiddenCheck")
        hidden.setChecked(opts.print_hidden)

        def apply() -> None:
            kind, _sep, per = str(what.currentData() or "slides").partition(":")
            opts.what = kind
            if per:
                opts.per_page = int(per)
            opts.color = color.currentData()
            opts.frame_slides = frame.isChecked()
            opts.print_hidden = hidden.isChecked()
            panel.refresh()

        what.currentIndexChanged.connect(lambda _i: apply())
        color.currentIndexChanged.connect(lambda _i: apply())
        frame.toggled.connect(lambda _c: apply())
        hidden.toggled.connect(lambda _c: apply())
        for w in (what, color, frame, hidden):
            panel.add_extra_widget(w)

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
        if hasattr(self, "action_registry") and self.action_registry:
            self.action_registry.retranslate_ui(safe_tr)
        if hasattr(self, "toolbars") and self.toolbars:
            retranslate_lectern_toolbars(self.toolbars, safe_tr)
        if hasattr(self, "presentation_view"):
            self.presentation_view.retranslate_ui()
        if hasattr(self, "menu_bar"):
            self.menu_bar.retranslate_ui()
        if hasattr(self, "btn_view_normal") and self.btn_view_normal:
            self.btn_view_normal.setToolTip(safe_tr("普通视图 (Normal View)"))
        if hasattr(self, "btn_view_sorter") and self.btn_view_sorter:
            self.btn_view_sorter.setToolTip(safe_tr("幻灯片浏览视图 (Slide Sorter View)"))
        if hasattr(self, "btn_view_notes") and self.btn_view_notes:
            self.btn_view_notes.setToolTip(safe_tr("备注页视图 (Notes Page View)"))
        if hasattr(self, "btn_view_show") and self.btn_view_show:
            self.btn_view_show.setToolTip(safe_tr("幻灯片放映 (Slide Show)"))
        if hasattr(self, "lbl_status_design") and self.lbl_status_design:
            self.lbl_status_design.setText(safe_tr("默认设计模板"))
        if hasattr(self, "slide_layout_pane") and self.slide_layout_pane:
            self.slide_layout_pane.retranslate_ui()
        if hasattr(self, "slide_design_pane") and self.slide_design_pane:
            self.slide_design_pane.retranslate_ui()
        if hasattr(self, "color_schemes_pane") and self.color_schemes_pane:
            self.color_schemes_pane.retranslate_ui()
        if hasattr(self, "animation_schemes_pane") and self.animation_schemes_pane:
            self.animation_schemes_pane.retranslate_ui()
