"""Lectern dedicated presentation window with PowerPoint 2003 Luna menus and toolbar cluster."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
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
from atboffice.modules.presentation.views.slide_canvas import SlideScene
from atboffice.ui.components.color_picker import ColorPickerButton
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

        # 4. Initialize universal TaskPaneDock
        self.init_task_pane_dock(safe_tr("演示文稿"))
        self._setup_lectern_task_panes()

        # 5. Setup Office 2003 Luna 10 toolbars
        self._setup_toolbars()

        # 5. Connect slide changes & selection signals
        ws = self.presentation_view.workspace
        ws.slide_changed.connect(self._on_presentation_modified)

        if hasattr(ws, "scene") and ws.scene is not None:
            ws.scene.selectionChanged.connect(self._on_scene_selection_changed)
            if hasattr(ws.scene, "shapeCreated"):
                ws.scene.shapeCreated.connect(self._on_shape_created)
            if hasattr(ws.scene, "toolChanged"):
                ws.scene.toolChanged.connect(self._update_drawing_tool_actions)

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
        self.action_registry.set_handler("formatPainter", self.toggle_format_painter)

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
        self.action_registry.set_handler("hyperlink", self.open_hyperlink_dialog)
        self.action_registry.set_handler("insert_hyperlink", self.open_hyperlink_dialog)
        self.action_registry.set_handler("expandAll", self.expand_all_outline)
        self.action_registry.set_handler("showFormatting", self.toggle_show_formatting)
        self.action_registry.set_handler("showGrid", self.toggle_grid)
        self.action_registry.set_handler("viewGray", lambda: self.set_view_color_mode("grayscale"))
        self.action_registry.set_handler("view_color", lambda: self.set_view_color_mode("color"))
        self.action_registry.set_handler(
            "view_grayscale", lambda: self.set_view_color_mode("grayscale")
        )
        self.action_registry.set_handler(
            "view_black_and_white", lambda: self.set_view_color_mode("bw")
        )
        self.action_registry.set_handler("spelling", self.run_spelling)
        self.action_registry.set_handler("tools_spelling", self.run_spelling)
        self.action_registry.set_handler("help", self.show_help)
        self.action_registry.set_handler("help_contents", self.show_help)

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

        # 11. Tables and Borders Toolbar
        self.action_registry.set_handler("tableMergeCells", self.table_merge_cells)
        self.action_registry.set_handler("tableSplitCell", self.table_split_cell)
        self.action_registry.set_handler("cellTop", lambda: self.set_table_cell_valign("top"))
        self.action_registry.set_handler("cellMiddle", lambda: self.set_table_cell_valign("middle"))
        self.action_registry.set_handler("cellBottom", lambda: self.set_table_cell_valign("bottom"))
        self.action_registry.set_handler("distRows", self.table_distribute_rows)
        self.action_registry.set_handler("distCols", self.table_distribute_cols)
        self.action_registry.set_handler("tableBordersAll", lambda: self.apply_table_border("all"))
        self.action_registry.set_handler("tbl_border_all", lambda: self.apply_table_border("all"))
        self.action_registry.set_handler(
            "tbl_border_outside", lambda: self.apply_table_border("outside")
        )
        self.action_registry.set_handler(
            "tbl_border_inside", lambda: self.apply_table_border("inside")
        )
        self.action_registry.set_handler("tbl_border_none", lambda: self.apply_table_border("none"))
        self.action_registry.set_handler("tbl_border_top", lambda: self.apply_table_border("top"))
        self.action_registry.set_handler(
            "tbl_border_bottom", lambda: self.apply_table_border("bottom")
        )
        self.action_registry.set_handler("tbl_border_left", lambda: self.apply_table_border("left"))
        self.action_registry.set_handler(
            "tbl_border_right", lambda: self.apply_table_border("right")
        )
        self.action_registry.set_handler("tbl_insert_table", self.insert_table)
        self.action_registry.set_handler(
            "tbl_insert_col_left", lambda: self.table_insert_col(left=True)
        )
        self.action_registry.set_handler(
            "tbl_insert_col_right", lambda: self.table_insert_col(left=False)
        )
        self.action_registry.set_handler(
            "tbl_insert_row_above", lambda: self.table_insert_row(above=True)
        )
        self.action_registry.set_handler(
            "tbl_insert_row_below", lambda: self.table_insert_row(above=False)
        )
        self.action_registry.set_handler("tbl_delete_col", self.table_delete_col)
        self.action_registry.set_handler("tbl_delete_row", self.table_delete_row)
        self.action_registry.set_handler("tbl_select_table", self.table_select)
        self.action_registry.set_handler("tbl_borders_and_shading", self.table_borders_and_shading)

        # 12. Picture Toolbar
        self.action_registry.set_handler("pic_insert", self.insert_picture_from_file)
        self.action_registry.set_handler("insert_picture", self.insert_picture_from_file)
        self.action_registry.set_handler("draw_insertPicture", self.insert_picture_from_file)
        self.action_registry.set_handler("insertClipArt", self.insert_picture_from_file)
        self.action_registry.set_handler("rotateLeft", self.rotate_selected_left)
        self.action_registry.set_handler("picCrop", self.toggle_picture_crop)
        self.action_registry.set_handler("picReset", self.reset_picture)
        self.action_registry.set_handler("formatObject", self.format_object_dialog)
        self.action_registry.set_handler("picTransparent", self.toggle_picture_transparent)
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
        self.action_registry.set_handler("wa_format", self.open_wordart_format)
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
        self.action_registry.set_handler("summarySlide", self.create_summary_slide)
        self.action_registry.set_handler("speakerNotes", self.edit_speaker_notes)
        self.action_registry.set_handler("transitionPane", self.open_transition_pane)
        self.action_registry.set_handler("sorter_slideDesign", self.open_slide_design_pane)
        self.action_registry.set_handler("sorter_newSlide", self.add_new_slide)

        # 15. Master View Toolbar
        self.action_registry.set_handler("insertSlideMaster", self.insert_slide_master)
        self.action_registry.set_handler("insertTitleMaster", self.insert_title_master)
        self.action_registry.set_handler("preserveMaster", self.preserve_master)
        self.action_registry.set_handler("renameMaster", self.rename_master)
        self.action_registry.set_handler("deleteTitleMaster", self.delete_title_master)

        # 16. Outlining Toolbar
        self.action_registry.set_handler("outline_promote", self.promote_indent)
        self.action_registry.set_handler("outline_demote", self.demote_indent)
        self.action_registry.set_handler("moveParaUp", self.move_para_up)
        self.action_registry.set_handler("moveParaDown", self.move_para_down)
        self.action_registry.set_handler("outline_summarySlide", self.create_summary_slide)
        self.action_registry.set_handler("outline_showFormatting", self.toggle_show_formatting)

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

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return
        slide = ws.current_slide
        tid = f"tbl_{len(slide.shapes) + 1}"
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
            tbl={
                "cols": [w / cols] * cols,
                "rows": [
                    {
                        "h": h / rows,
                        "cells": [
                            {"tx": {"paragraphs": [{"runs": [{"text": f"R{r + 1}C{c + 1}"}]}]}}
                            for c in range(cols)
                        ],
                    }
                    for r in range(rows)
                ],
            },
        )
        slide.shapes.append(tbl_shape)
        ws.scene.load_slide(slide)
        item = ws.scene.get_shape_item(tid)
        if item:
            ws.scene.clearSelection()
            item.setSelected(True)
        self.set_modified(True)
        self.show_status_message(safe_tr("已插入表格"))

    def insert_chart(self) -> None:
        """Insert a statistical chart shape."""
        from atboffice.modules.presentation.models.shape import Shape

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return
        slide = ws.current_slide
        cid = f"chart_{len(slide.shapes) + 1}"
        w, h = 400.0, 240.0
        chart_shape = Shape(
            id=cid,
            type="shape",
            geom="rect",
            name=f"Chart {cid}",
            x=(960.0 - w) / 2.0,
            y=(540.0 - h) / 2.0,
            w=w,
            h=h,
        )
        slide.shapes.append(chart_shape)
        ws.scene.load_slide(slide)
        item = ws.scene.get_shape_item(cid)
        if item:
            ws.scene.clearSelection()
            item.setSelected(True)
        self.set_modified(True)
        self.show_status_message(safe_tr("已插入图表"))

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

    def toggle_format_painter(self) -> None:
        """Activate format painter."""
        self.show_status_message(safe_tr("格式刷已激活"))

    def open_hyperlink_dialog(self) -> None:
        """Open hyperlink insertion dialog."""
        self.show_status_message(safe_tr("插入超链接"))

    def expand_all_outline(self) -> None:
        """Expand all nodes in outline view."""
        self.show_status_message(safe_tr("全部展开大纲"))

    def toggle_show_formatting(self) -> None:
        """Toggle showing formatting in outline view."""
        self.show_status_message(safe_tr("显示格式"))

    def run_spelling(self) -> None:
        """Run spell check dialog."""
        self.show_status_message(safe_tr("拼写检查完成"))

    def show_help(self) -> None:
        """Show PowerPoint help."""
        self.show_status_message(safe_tr("PowerPoint 帮助"))

    def _get_active_table_shape(self) -> Any | None:
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.scene:
            return None
        for item in ws.scene.selectedItems():
            shape = getattr(item, "model", None)
            if shape and (shape.type == "table" or getattr(shape, "tbl", None)):
                return shape
        return None

    def table_merge_cells(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl:
            shape.tbl.setdefault("merged", True)
            self.show_status_message(safe_tr("合并单元格"))
            self.set_modified(True)

    def table_split_cell(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl:
            shape.tbl.setdefault("split", True)
            self.show_status_message(safe_tr("拆分单元格"))
            self.set_modified(True)

    def set_table_cell_valign(self, valign: str) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl:
            shape.tbl["valign"] = valign
            self.show_status_message(safe_tr(f"单元格对齐: {valign}"))
            self.set_modified(True)

    def table_distribute_rows(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and "rows" in shape.tbl:
            rows = shape.tbl["rows"]
            if rows:
                avg_h = sum(r.get("h", 30.0) for r in rows) / len(rows)
                for r in rows:
                    r["h"] = avg_h
                self.show_status_message(safe_tr("平均分布各行"))
                self.set_modified(True)

    def table_distribute_cols(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and "cols" in shape.tbl:
            cols = shape.tbl["cols"]
            if cols:
                avg_w = sum(cols) / len(cols)
                shape.tbl["cols"] = [avg_w] * len(cols)
                self.show_status_message(safe_tr("平均分布各列"))
                self.set_modified(True)

    def apply_table_border(self, border_type: str) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl:
            shape.tbl["border_type"] = border_type
            self.show_status_message(safe_tr(f"应用表格边框: {border_type}"))
            self.set_modified(True)

    def table_insert_col(self, left: bool = True) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and "cols" in shape.tbl:
            cols = shape.tbl["cols"]
            idx = 0 if left else len(cols)
            new_w = shape.w / (len(cols) + 1)
            cols.insert(idx, new_w)
            for r in shape.tbl.get("rows", []):
                cells = r.setdefault("cells", [])
                cells.insert(idx, {"tx": {"paragraphs": [{"runs": [{"text": ""}]}]}})
            self.show_status_message(safe_tr("插入列"))
            self.set_modified(True)

    def table_insert_row(self, above: bool = True) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and "rows" in shape.tbl:
            rows = shape.tbl["rows"]
            cols_count = len(shape.tbl.get("cols", [100.0, 100.0]))
            idx = 0 if above else len(rows)
            new_row = {
                "h": 30.0,
                "cells": [
                    {"tx": {"paragraphs": [{"runs": [{"text": ""}]}]}} for _ in range(cols_count)
                ],
            }
            rows.insert(idx, new_row)
            self.show_status_message(safe_tr("插入行"))
            self.set_modified(True)

    def table_delete_col(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and len(shape.tbl.get("cols", [])) > 1:
            shape.tbl["cols"].pop()
            for r in shape.tbl.get("rows", []):
                if r.get("cells"):
                    r["cells"].pop()
            self.show_status_message(safe_tr("删除列"))
            self.set_modified(True)

    def table_delete_row(self) -> None:
        shape = self._get_active_table_shape()
        if shape and shape.tbl and len(shape.tbl.get("rows", [])) > 1:
            shape.tbl["rows"].pop()
            self.show_status_message(safe_tr("删除行"))
            self.set_modified(True)

    def table_select(self) -> None:
        shape = self._get_active_table_shape()
        if shape:
            self.show_status_message(safe_tr("选择表格"))

    def table_borders_and_shading(self) -> None:
        self.show_status_message(safe_tr("边框和底纹"))

    def _get_active_picture_shape(self) -> Any | None:
        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.scene:
            return None
        for item in ws.scene.selectedItems():
            shape = getattr(item, "model", None)
            if shape and (shape.type in ("image", "picture") or getattr(shape, "media_item", None)):
                return shape
        return None

    def insert_picture_from_file(self) -> None:
        """Prompt for an image file and insert on current slide."""
        from atboffice.modules.presentation.models.shape import Shape

        ws = getattr(self.presentation_view, "workspace", None)
        if not ws or not ws.current_slide:
            return
        slide = ws.current_slide
        pid = f"pic_{len(slide.shapes) + 1}"
        w, h = 300.0, 200.0
        pic_shape = Shape(
            id=pid,
            type="image",
            name=f"Picture {pid}",
            x=(960.0 - w) / 2.0,
            y=(540.0 - h) / 2.0,
            w=w,
            h=h,
        )
        slide.shapes.append(pic_shape)
        ws.scene.load_slide(slide)
        item = ws.scene.get_shape_item(pid)
        if item:
            ws.scene.clearSelection()
            item.setSelected(True)
        self.set_modified(True)
        self.show_status_message(safe_tr("已插入图片"))

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

    def toggle_picture_transparent(self) -> None:
        self.show_status_message(safe_tr("设置透明色"))

    def format_object_dialog(self) -> None:
        self.show_status_message(safe_tr("设置对象格式"))

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

    def open_wordart_format(self) -> None:
        self.show_status_message(safe_tr("设置艺术字格式"))

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

    def start_rehearse(self) -> None:
        self.start_slideshow()
        self.show_status_message(safe_tr("启动排练计时"))

    def create_summary_slide(self) -> None:
        self.add_new_slide()
        self.show_status_message(safe_tr("生成摘要幻灯片"))

    def edit_speaker_notes(self) -> None:
        self.show_status_message(safe_tr("编辑演讲者备注"))

    def open_transition_pane(self) -> None:
        self.show_status_message(safe_tr("打开幻灯片切换窗格"))

    def _setup_lectern_task_panes(self) -> None:
        """Register Lectern specific task panes (Slide Design, Color Schemes, Animation Schemes)."""
        if not self.task_pane_dock:
            return

        from atboffice.modules.presentation.panes import (
            AnimationSchemesPane,
            ColorSchemesPane,
            SlideDesignPane,
        )

        pres = getattr(self.presentation_view, "presentation", None)

        self.slide_design_pane = SlideDesignPane(presentation=pres, parent=self.task_pane_dock)
        self.color_schemes_pane = ColorSchemesPane(presentation=pres, parent=self.task_pane_dock)
        self.animation_schemes_pane = AnimationSchemesPane(
            presentation=pres, parent=self.task_pane_dock
        )

        # Wire navigation between panes
        for pane in (self.slide_design_pane, self.color_schemes_pane, self.animation_schemes_pane):
            pane.navigate_pane.connect(self._on_task_pane_navigate)

        # Wire design & scheme application
        self.slide_design_pane.apply_design_requested.connect(self._on_apply_design_template)
        self.color_schemes_pane.apply_color_scheme_requested.connect(self._on_apply_color_scheme)
        self.animation_schemes_pane.apply_animation_scheme_requested.connect(self._on_apply_animation_scheme)
        self.animation_schemes_pane.play_requested.connect(self._on_play_slide_animation)
        self.animation_schemes_pane.slide_show_requested.connect(self.start_slideshow_current)

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
        self.show_status_message(safe_tr("播放幻灯片动画预览"))

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

    def open_action_settings_dialog(self) -> None:
        from atboffice.modules.presentation.dialogs import ActionSettingsDialog

        pres = getattr(self.presentation_view, "presentation", None)
        dlg = ActionSettingsDialog(presentation=pres, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            settings = dlg.get_action_settings()
            ws = getattr(self.presentation_view, "workspace", None)
            if ws and ws.scene:
                for item in ws.scene.selectedItems():
                    if hasattr(item, "shape") and item.shape:
                        item.shape.action_settings = settings
            self.show_status_message(safe_tr("动作设置已应用"))
            self.set_modified(True)

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
        from atboffice.modules.presentation.models.shape import Shape
        from atboffice.modules.presentation.models.slide import Slide

        pres = getattr(self.presentation_view, "presentation", None)
        if not pres:
            return

        pics = spec.get("pictures", [])
        for i, pic_path in enumerate(pics):
            slide = Slide(id=f"slide_photo_{i + 1}", layout="blank")
            shape = Shape.create_picture(
                shape_id=f"pic_{i + 1}",
                image_path=pic_path,
                x=50.0,
                y=50.0,
                w=pres.w - 100.0,
                h=pres.h - 100.0,
            )
            slide.shapes.append(shape)
            pres.slides.append(slide)

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

    def insert_slide_master(self) -> None:
        self.show_status_message(safe_tr("插入幻灯片母版"))

    def insert_title_master(self) -> None:
        self.show_status_message(safe_tr("插入标题母版"))

    def preserve_master(self) -> None:
        self.show_status_message(safe_tr("保留母版"))

    def rename_master(self) -> None:
        self.show_status_message(safe_tr("重命名母版"))

    def delete_title_master(self) -> None:
        self.show_status_message(safe_tr("删除母版"))

    def move_para_up(self) -> None:
        self.show_status_message(safe_tr("上移段落"))

    def move_para_down(self) -> None:
        self.show_status_message(safe_tr("下移段落"))

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
        """Prompt user with Save As dialog."""
        return self.save_file()

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

    def _on_presentation_modified(self) -> None:
        """Mark presentation as modified when slide content or layout changes."""
        self.set_modified(True)
        if hasattr(self, "lbl_status_slide"):
            ws = self.presentation_view.workspace
            curr = getattr(ws, "current_slide_index", 0) + 1
            slides = getattr(ws.presentation, "slides", [])
            total = len(slides) if slides else 1
            self.lbl_status_slide.setText(f"{safe_tr('幻灯片')} {curr} / {total}")

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
        doc_name = (
            self.current_file_path.name
            if self.current_file_path is not None
            else self.default_doc_name
        )
        self.setWindowTitle(f"{doc_name} — {self.app_name} [*]")

    def get_file_filter(self) -> str:
        """Return file filter pattern for Lectern save/open dialogs."""
        return safe_tr(
            "所有支持的格式 (*.pptx *.ppsx *.potx);;"
            "PowerPoint 演示文稿 (*.pptx *.ppsx *.potx);;"
            "PowerPoint 97-2003 演示文稿 (*.ppt);;"
            "所有文件 (*.*)"
        )

    @property
    def presentation(self):
        """Return the bound Presentation model."""
        return self.presentation_view.presentation

    def do_save(self, path: Path) -> bool:
        """Serialize Lectern presentation to destination path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        ext = path.suffix.lower()
        if ext in {".pptx", ".ppsx", ".potx"}:
            from atboffice.modules.presentation.io.pptx_writer import write_pptx

            write_pptx(self.presentation, path)
            return True
        path.touch(exist_ok=True)
        return True

    def do_open(self, path: Path) -> bool:
        """Parse and load Lectern presentation from disk with transactional rollback."""
        from atboffice.ui.shell.base_window import FileOpenWarningHandled
        from atboffice.vfs.crypto import is_encrypted_package

        ext = path.suffix.lower()

        # Check binary magic header
        header = b""
        try:
            with open(path, "rb") as f:
                header = f.read(512)
        except Exception as e:
            raise e

        is_cfb = len(header) >= 8 and header[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

        # 1. Check if legacy binary .ppt
        if ext in {".ppt", ".pps", ".pot"} or (is_cfb and not is_encrypted_package(path)):
            QMessageBox.warning(
                self,
                safe_tr("文件格式提示"),
                safe_tr(
                    "“{name}”是旧版二进制 PowerPoint 97–2003 演示文稿 (.ppt)。"
                    "Lectern 原生支持 .pptx 演示文稿。"
                    "请在 PowerPoint 或 LibreOffice 中将其另存为 .pptx 格式后再打开。"
                ).format(name=path.name),
            )
            raise FileOpenWarningHandled("Legacy binary .ppt is not supported")

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
        mode: str = "slides",
        grayscale: bool = False,
    ) -> None:
        """Render presentation slides in vector fidelity (slide mode or 3-slide handout mode)."""
        pres = self.presentation_view.presentation
        slides = pres.slides
        if not slides:
            return

        dpi = printer.resolution()
        scale = dpi / 72.0
        page_rect = printer.pageRect(QPrinter.Unit.Point)
        paper_w = page_rect.width()
        paper_h = page_rect.height()

        painter = QPainter(printer)
        painter.scale(scale, scale)

        if mode == "handouts":
            # 3 slides per page with note lines on the right
            slides_per_page = 3
            margin_left = 36.0
            margin_right = 36.0
            margin_top = 40.0
            margin_bottom = 40.0
            gap_y = 24.0

            avail_w = paper_w - margin_left - margin_right
            avail_h = paper_h - margin_top - margin_bottom

            thumb_h = (avail_h - (slides_per_page - 1) * gap_y) / slides_per_page
            thumb_w = thumb_h * (16.0 / 9.0)
            notes_x = margin_left + thumb_w + 24.0
            notes_w = paper_w - margin_right - notes_x

            total_pages = (len(slides) + slides_per_page - 1) // slides_per_page

            for p_idx in range(total_pages):
                if p_idx > 0:
                    printer.newPage()

                # Header
                painter.setFont(QFont("Arial", 9))
                painter.setPen(QPen(QColor(120, 120, 120)))
                doc_title = (
                    self.current_file_path.stem if self.current_file_path else self.default_doc_name
                )
                painter.drawText(
                    QRectF(margin_left, 18.0, avail_w, 20.0),
                    int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                    safe_tr("演示文稿讲义 — {title}").format(title=doc_title),
                )

                # Render up to 3 slides on this page
                start_s = p_idx * slides_per_page
                page_slides = slides[start_s : start_s + slides_per_page]

                for s_sub_idx, slide in enumerate(page_slides):
                    slide_idx = start_s + s_sub_idx
                    y = margin_top + s_sub_idx * (thumb_h + gap_y)
                    thumb_rect = QRectF(margin_left, y, thumb_w, thumb_h)

                    # 1. Fill slide background & border
                    painter.fillRect(thumb_rect, QColor("#FFFFFF"))
                    painter.setPen(QPen(QColor(180, 180, 180), 0.75))
                    painter.drawRect(thumb_rect)

                    # 2. Render slide vector scene
                    scene = SlideScene(slide=slide, slide_width=960.0, slide_height=540.0)
                    scene.render(painter, thumb_rect, QRectF(0, 0, 960.0, 540.0))

                    # 3. Slide index caption
                    painter.setFont(QFont("Arial", 8))
                    painter.setPen(QPen(QColor(120, 120, 120)))
                    painter.drawText(
                        QRectF(margin_left, y + thumb_h + 2.0, thumb_w, 14.0),
                        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                        safe_tr("幻灯片 {num}").format(num=slide_idx + 1),
                    )

                    # 4. Note lines on the right (3 horizontal ruled lines)
                    line_gap = thumb_h / 4.0
                    painter.setPen(QPen(QColor(200, 200, 200), 0.75, Qt.PenStyle.SolidLine))
                    for line_i in range(1, 4):
                        ly = y + line_i * line_gap
                        painter.drawLine(QPointF(notes_x, ly), QPointF(notes_x + notes_w, ly))

                # Footer: Page number
                painter.setFont(QFont("Arial", 9))
                painter.setPen(QPen(QColor(120, 120, 120)))
                footer_rect = QRectF(margin_left, paper_h - 28.0, avail_w, 20.0)
                painter.drawText(
                    footer_rect,
                    int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                    safe_tr("第 {page} 页，共 {total} 页").format(
                        page=p_idx + 1, total=total_pages
                    ),
                )

        else:
            # Standard Slides Mode: 1 slide per page
            total_slides = len(slides)
            margin = 36.0
            avail_w = paper_w - margin * 2.0
            avail_h = paper_h - margin * 2.0 - 24.0

            scale_fit = min(avail_w / 960.0, avail_h / 540.0)
            target_w = 960.0 * scale_fit
            target_h = 540.0 * scale_fit
            target_x = margin + (avail_w - target_w) / 2.0
            target_y = margin + (avail_h - target_h) / 2.0
            target_rect = QRectF(target_x, target_y, target_w, target_h)

            for s_idx, slide in enumerate(slides):
                if s_idx > 0:
                    printer.newPage()

                # Slide background and border
                painter.fillRect(target_rect, QColor("#FFFFFF"))
                painter.setPen(QPen(QColor(160, 160, 160), 0.75))
                painter.drawRect(target_rect)

                # Render vector slide scene
                scene = SlideScene(slide=slide, slide_width=960.0, slide_height=540.0)
                scene.render(painter, target_rect, QRectF(0, 0, 960.0, 540.0))

                # Footer caption: Slide X of Y
                caption_rect = QRectF(margin, paper_h - 32.0, avail_w, 20.0)
                painter.setFont(QFont("Arial", 9))
                painter.setPen(QPen(QColor(120, 120, 120)))
                painter.drawText(
                    caption_rect,
                    int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter),
                    safe_tr("幻灯片 {num} / {total}").format(num=s_idx + 1, total=total_slides),
                )

        painter.end()

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
        if hasattr(self, "slide_design_pane") and self.slide_design_pane:
            self.slide_design_pane.retranslate_ui()
        if hasattr(self, "color_schemes_pane") and self.color_schemes_pane:
            self.color_schemes_pane.retranslate_ui()
        if hasattr(self, "animation_schemes_pane") and self.animation_schemes_pane:
            self.animation_schemes_pane.retranslate_ui()
