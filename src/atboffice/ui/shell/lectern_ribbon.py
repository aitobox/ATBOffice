"""Declarative Paper 2016 Ribbon specification for Lectern presentation editor."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from atboffice.ui.components.ribbon_bar import (
    RibbonContextSetSpec,
    RibbonGroupSpec,
    RibbonItemSpec,
    RibbonSpec,
    RibbonTabSpec,
    make_mirrored_combo,
    make_ribbon_color_button,
)
from atboffice.ui.components.ribbon_bar import (
    toolbar_menu_builder as _menu_from,
)


def _lectern_selected_kind(window: Any) -> str | None:
    ws = getattr(getattr(window, "presentation_view", None), "workspace", None)
    scene = getattr(ws, "scene", None) if ws is not None else None
    if scene is None:
        return None
    selected = scene.selectedItems()
    if not selected:
        return None
    for item in selected:
        shape = getattr(item, "model", None)
        stype = getattr(shape, "type", "") if shape else ""
        if stype == "table" or (shape and getattr(shape, "tbl", None)):
            return "table"
        if stype in ("image", "picture") or (shape and getattr(shape, "media_item", None)):
            return "picture"
        if (
            stype in ("diagram", "smartart")
            or (shape and getattr(shape, "is_diagram", False))
            or (shape and getattr(shape, "sa", None))
        ):
            return "smartart"
        if stype == "wordart" or (shape and getattr(shape, "name", "").startswith("WordArt")):
            return "wordart"
    return "drawing"


def _lectern_in_master(window: Any) -> bool:
    return getattr(getattr(window, "presentation_view", None), "view_mode", "normal") == "master"


def _lectern_in_handout_master(window: Any) -> bool:
    return (
        getattr(getattr(window, "presentation_view", None), "view_mode", "normal")
        == "handout_master"
    )


def _lectern_in_notes_master(window: Any) -> bool:
    return (
        getattr(getattr(window, "presentation_view", None), "view_mode", "normal") == "notes_master"
    )


def build_lectern_ribbon_spec(window: Any) -> RibbonSpec:
    """Build the Paper 2016 RibbonSpec over ``LecternWindow``'s live ``ActionRegistry``."""
    icons: dict[str, str] = {
        "save_as": "save",
        "tools_options": "options",
        "start_slideshow": "slideshow",
        "start_slideshow_current": "slideshow",
        "officeClipboard": "clipboard",
        "format_font": "font",
        "format_paragraph": "paragraph",
        "autoshapes_menu": "autoshapes",
        "insert_date_time": "date",
        "insert_page_number": "slideNumber",
        "insert_symbol": "symbol",
        "slideshow_transition": "transition",
        "slideshow_setup": "setupShow",
        "slideshow_rehearse": "rehearse",
        "slideshow_record": "sound",
        "viewNormal": "normalView",
        "viewSorter": "sorterView",
        "viewNotes": "notesView",
        "viewMaster": "master",
        "view_handout_master": "master",
        "view_notes_master": "master",
        "view_ruler": "ruler",
        "taskPane": "taskpane",
        "window_zoom": "zoom",
        "view_color": "colorPic",
        "view_grayscale": "grayscale",
        "view_black_and_white": "grayscale",
        "insertSlideMaster": "master",
        "preserveMaster": "protect",
        "renameMaster": "editText",
        "diagram_layout_menu": "layout",
        "diagram_colors_menu": "colorPic",
        "diagram_style_menu": "themes",
        "draw_shadow_style": "shadowStyle",
        "draw_dash_style": "dashStyle",
        "draw_arrow_style": "arrowStyle",
        "draw_align_left": "alignL",
        "draw_align_center": "alignC",
        "draw_align_right": "alignR",
        "pic_color_mode": "colorPic",
        "pic_line_style": "lineStyle",
        "tbl_shading_color": "fillColor",
        "tableBordersAll": "bordersAll",
        "tbl_select_table": "selectTable",
        "tbl_insert_row_above": "rowAbove",
        "tbl_insert_row_below": "rowBelow",
        "tbl_insert_col_left": "colLeft",
        "tbl_insert_col_right": "colRight",
        "tbl_delete_row": "deleteRow",
        "tbl_delete_col": "deleteCol",
        "tableMergeCells": "mergeCells",
        "tableSplitCell": "splitCells",
        "wa_shape_menu": "waShape",
        "research": "research",
        "thesaurus": "thesaurus",
    }

    def _font_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "font_combo", None),
            window._on_font_combo_changed,
            126,
            "字体",
            parent,
        )

    def _size_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "size_combo", None),
            window._on_size_combo_changed,
            48,
            "字号",
            parent,
        )

    def _zoom_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "zoom_combo", None),
            window._on_zoom_combo_changed,
            78,
            "显示比例",
            parent,
        )

    def _font_color_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "font", "#FF0000", "字体颜色", window._on_font_color_selected, parent
        )

    def _draw_fill_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "fill", "#CFE0FB", "填充颜色", window._on_shape_fill_color_selected, parent
        )

    def _draw_line_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "line", "#1D4F9E", "线条颜色", window._on_shape_line_color_selected, parent
        )

    qat = (
        "save",
        RibbonItemSpec(
            cmd="undo",
            size="small",
            split=True,
            menu_builder=_menu_from(window, "standard", "undo"),
        ),
        RibbonItemSpec(
            cmd="redo",
            size="small",
            split=True,
            menu_builder=_menu_from(window, "standard", "redo"),
        ),
        "start_slideshow",
    )

    file_actions = (
        "new",
        "open",
        "-",
        "save",
        "save_as",
        "-",
        "printPreview",
        "print",
        "-",
        "properties",
        "-",
        "tools_options",
        "help",
        "about",
        "-",
        "close",
    )

    tabs = (
        RibbonTabSpec(
            tab_id="home",
            label="开始",
            groups=(
                RibbonGroupSpec(
                    label="剪贴板",
                    launcher="officeClipboard",
                    items=(
                        RibbonItemSpec(cmd="paste", size="large"),
                        "cut",
                        "copy",
                        "formatPainter",
                    ),
                ),
                RibbonGroupSpec(
                    label="幻灯片",
                    items=(
                        RibbonItemSpec(cmd="newSlide", size="large", label="新建幻灯片"),
                        "slideDesign",
                        "hideSlide",
                    ),
                ),
                RibbonGroupSpec(
                    label="字体",
                    icon="font",
                    launcher="format_font",
                    items=(
                        RibbonItemSpec(
                            row=(
                                RibbonItemSpec(widget_factory=_font_combo),
                                RibbonItemSpec(widget_factory=_size_combo),
                                "growFont",
                                "shrinkFont",
                            )
                        ),
                        RibbonItemSpec(
                            row=(
                                "bold",
                                "italic",
                                "underline",
                                "shadowText",
                                "|",
                                RibbonItemSpec(widget_factory=_font_color_btn),
                            )
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="段落",
                    icon="paragraph",
                    launcher="format_paragraph",
                    items=(
                        RibbonItemSpec(row=("bullets", "numbering", "|", "promote", "demote")),
                        RibbonItemSpec(row=("alignLeft", "alignCenter", "alignRight")),
                    ),
                ),
                RibbonGroupSpec(
                    label="绘图",
                    launcher="formatObject",
                    items=(
                        RibbonItemSpec(
                            cmd="autoshapes_menu",
                            size="large",
                            label="形状",
                            drop=True,
                            menu_builder=_menu_from(window, "drawing", tooltip_src="自选图形"),
                        ),
                        "drawRect",
                        "drawOval",
                        "textBox",
                        "bringFront",
                        "sendBack",
                        RibbonItemSpec(widget_factory=_draw_fill_btn),
                        RibbonItemSpec(widget_factory=_draw_line_btn),
                    ),
                ),
                RibbonGroupSpec(
                    label="编辑",
                    items=("find", "replace", "selectAll"),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="insert",
            label="插入",
            groups=(
                RibbonGroupSpec(
                    label="幻灯片",
                    items=(RibbonItemSpec(cmd="newSlide", size="large", label="新建幻灯片"),),
                ),
                RibbonGroupSpec(
                    label="表格",
                    items=(RibbonItemSpec(cmd="insertTable", size="large", label="表格"),),
                ),
                RibbonGroupSpec(
                    label="图像",
                    items=(
                        RibbonItemSpec(cmd="draw_insertPicture", size="large", label="图片"),
                        "insertClipArt",
                    ),
                ),
                RibbonGroupSpec(
                    label="插图",
                    items=(
                        RibbonItemSpec(
                            cmd="autoshapes_menu",
                            size="large",
                            label="形状",
                            drop=True,
                            menu_builder=_menu_from(window, "drawing", tooltip_src="自选图形"),
                        ),
                        RibbonItemSpec(cmd="draw_insertDiagram", size="large", label="图示"),
                        RibbonItemSpec(cmd="insertChart", size="large", label="图表"),
                    ),
                ),
                RibbonGroupSpec(
                    label="链接",
                    items=(RibbonItemSpec(cmd="hyperlink", size="large", label="超链接"),),
                ),
                RibbonGroupSpec(
                    label="文本",
                    items=(
                        RibbonItemSpec(cmd="textBox", size="large", label="文本框"),
                        RibbonItemSpec(cmd="headerFooter", size="large", label="页眉和页脚"),
                        RibbonItemSpec(cmd="draw_insertWordArt", size="large", label="艺术字"),
                        "insert_date_time",
                        "insert_page_number",
                    ),
                ),
                RibbonGroupSpec(
                    label="符号",
                    items=(RibbonItemSpec(cmd="insert_symbol", size="large", label="符号"),),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="design",
            label="设计",
            groups=(
                RibbonGroupSpec(
                    label="主题",
                    items=(RibbonItemSpec(cmd="slideDesign", size="large", label="幻灯片设计"),),
                ),
                RibbonGroupSpec(
                    label="自定义",
                    items=(RibbonItemSpec(cmd="background", size="large", label="背景"),),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="transitions",
            label="切换",
            groups=(
                RibbonGroupSpec(
                    label="切换到此幻灯片",
                    items=(RibbonItemSpec(cmd="transitionPane", size="large", label="幻灯片切换"),),
                ),
                RibbonGroupSpec(
                    label="计时",
                    items=(RibbonItemSpec(cmd="rehearse", size="large", label="排练计时"),),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="slideShow",
            label="幻灯片放映",
            groups=(
                RibbonGroupSpec(
                    label="开始放映幻灯片",
                    items=(
                        RibbonItemSpec(cmd="start_slideshow", size="large", label="从头开始"),
                        RibbonItemSpec(
                            cmd="start_slideshow_current", size="large", label="从当前幻灯片开始"
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="设置",
                    items=(
                        RibbonItemSpec(cmd="slideshow_setup", size="large", label="设置放映方式"),
                        "hideSlide",
                        "slideshow_rehearse",
                        "slideshow_record",
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="review",
            label="审阅",
            groups=(
                RibbonGroupSpec(
                    label="校对",
                    items=(
                        RibbonItemSpec(cmd="spelling", size="large", label="拼写检查"),
                        "research",
                        "thesaurus",
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="view",
            label="视图",
            groups=(
                RibbonGroupSpec(
                    label="演示文稿视图",
                    items=(
                        RibbonItemSpec(cmd="viewNormal", size="large", label="普通视图"),
                        RibbonItemSpec(cmd="viewSorter", size="large", label="幻灯片浏览"),
                        RibbonItemSpec(cmd="viewNotes", size="large", label="备注页"),
                    ),
                ),
                RibbonGroupSpec(
                    label="母版视图",
                    items=(
                        RibbonItemSpec(cmd="viewMaster", size="large", label="幻灯片母版"),
                        RibbonItemSpec(cmd="view_handout_master", size="large", label="讲义母版"),
                        RibbonItemSpec(cmd="view_notes_master", size="large", label="备注母版"),
                    ),
                ),
                RibbonGroupSpec(
                    label="显示",
                    items=("view_ruler", "showGrid", "speakerNotes", "taskPane"),
                ),
                RibbonGroupSpec(
                    label="显示比例",
                    items=(
                        RibbonItemSpec(cmd="window_zoom", size="large", label="显示比例"),
                        RibbonItemSpec(widget_factory=_zoom_combo),
                    ),
                ),
                RibbonGroupSpec(
                    label="颜色/灰度",
                    items=(
                        RibbonItemSpec(
                            cmd="viewGray",
                            split=True,
                            menu_builder=_menu_from(window, "standard", cmd_id="viewGray"),
                        ),
                        "view_color",
                        "view_grayscale",
                        "view_black_and_white",
                    ),
                ),
            ),
        ),
    )

    contextual = (
        RibbonContextSetSpec(
            set_id="master",
            set_label="幻灯片母版",
            auto_open=True,
            when=lambda: _lectern_in_master(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="masterTab",
                    label="幻灯片母版",
                    groups=(
                        RibbonGroupSpec(
                            label="编辑母版",
                            items=(
                                RibbonItemSpec(
                                    cmd="insertTitleMaster", size="large", label="插入标题母版"
                                ),
                                "deleteTitleMaster",
                                "insertSlideMaster",
                                "preserveMaster",
                                "renameMaster",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="关闭",
                            items=(
                                RibbonItemSpec(
                                    cmd="closeMaster", size="large", label="关闭母版视图"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="handout_master",
            set_label="讲义母版",
            auto_open=True,
            when=lambda: _lectern_in_handout_master(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="handoutMasterTab",
                    label="讲义母版",
                    groups=(
                        RibbonGroupSpec(
                            label="关闭",
                            items=(
                                RibbonItemSpec(
                                    cmd="closeMaster", size="large", label="关闭母版视图"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="notes_master",
            set_label="备注母版",
            auto_open=True,
            when=lambda: _lectern_in_notes_master(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="notesMasterTab",
                    label="备注母版",
                    groups=(
                        RibbonGroupSpec(
                            label="关闭",
                            items=(
                                RibbonItemSpec(
                                    cmd="closeMaster", size="large", label="关闭母版视图"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="smartart",
            set_label="IntelliArt 工具",
            when=lambda: _lectern_selected_kind(window) == "smartart",
            tabs=(
                RibbonTabSpec(
                    tab_id="smartartDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="创建图形",
                            items=(
                                RibbonItemSpec(
                                    cmd="diagramAddShape",
                                    size="large",
                                    label="添加形状",
                                    split=True,
                                    menu_builder=_menu_from(
                                        window, "diagram", cmd_id="diagramAddShape"
                                    ),
                                ),
                                RibbonItemSpec(row=("diagramPromote", "diagramDemote")),
                                RibbonItemSpec(row=("diagramMoveUp", "diagramMoveDown")),
                                RibbonItemSpec(cmd="diagramTextPane", size="large"),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="布局",
                            items=(
                                RibbonItemSpec(
                                    cmd="diagram_layout_menu",
                                    size="large",
                                    label="更改版式",
                                    drop=True,
                                    menu_builder=_menu_from(window, "diagram", tooltip_src="版式"),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="IntelliArt 样式",
                            items=(
                                RibbonItemSpec(
                                    cmd="diagram_colors_menu",
                                    size="large",
                                    label="更改颜色",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "diagram", tooltip_src="更改颜色"
                                    ),
                                ),
                                RibbonItemSpec(
                                    cmd="diagram_style_menu",
                                    size="large",
                                    label="样式",
                                    drop=True,
                                    menu_builder=_menu_from(window, "diagram", tooltip_src="样式"),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="重设",
                            items=(
                                RibbonItemSpec(cmd="diagramReset", size="large"),
                                "diagramToShapes",
                            ),
                        ),
                    ),
                ),
                RibbonTabSpec(
                    tab_id="smartartFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="形状样式",
                            launcher="formatObject",
                            items=(
                                RibbonItemSpec(widget_factory=_draw_fill_btn),
                                RibbonItemSpec(widget_factory=_draw_line_btn),
                                RibbonItemSpec(
                                    cmd="draw_shadow_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="阴影样式"
                                    ),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=(
                                "bringFront",
                                "sendBack",
                                "draw_align_left",
                                "draw_align_center",
                                "draw_align_right",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="drawing",
            set_label="绘图工具",
            when=lambda: _lectern_selected_kind(window) == "drawing",
            tabs=(
                RibbonTabSpec(
                    tab_id="drawingFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="插入形状",
                            items=(
                                RibbonItemSpec(
                                    cmd="autoshapes_menu",
                                    size="large",
                                    label="形状",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="自选图形"
                                    ),
                                ),
                                "drawRect",
                                "drawOval",
                                "textBox",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="形状样式",
                            launcher="formatObject",
                            items=(
                                RibbonItemSpec(widget_factory=_draw_fill_btn),
                                RibbonItemSpec(widget_factory=_draw_line_btn),
                                RibbonItemSpec(
                                    cmd="draw_dash_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="虚线线型"
                                    ),
                                ),
                                RibbonItemSpec(
                                    cmd="draw_arrow_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="箭头样式"
                                    ),
                                ),
                                RibbonItemSpec(
                                    cmd="draw_shadow_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="阴影样式"
                                    ),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=(
                                "bringFront",
                                "sendBack",
                                "group",
                                "ungroup",
                                "draw_align_left",
                                "draw_align_center",
                                "draw_align_right",
                                "rotateLeft",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="picture",
            set_label="图片工具",
            when=lambda: _lectern_selected_kind(window) == "picture",
            tabs=(
                RibbonTabSpec(
                    tab_id="pictureFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="调整",
                            items=(
                                RibbonItemSpec(
                                    row=(
                                        "picMoreBright",
                                        "picLessBright",
                                        "picMoreContrast",
                                        "picLessContrast",
                                    )
                                ),
                                RibbonItemSpec(
                                    cmd="pic_color_mode",
                                    drop=True,
                                    menu_builder=_menu_from(window, "picture", tooltip_src="颜色"),
                                ),
                                "picTransparent",
                                "picReset",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="图片样式",
                            launcher="formatObject",
                            items=(
                                RibbonItemSpec(
                                    cmd="pic_line_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "picture", tooltip_src="线条样式"
                                    ),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=("bringFront", "sendBack", "rotateLeft"),
                        ),
                        RibbonGroupSpec(
                            label="大小",
                            items=(RibbonItemSpec(cmd="picCrop", size="large", label="裁剪"),),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="table",
            set_label="表格工具",
            when=lambda: _lectern_selected_kind(window) == "table",
            tabs=(
                RibbonTabSpec(
                    tab_id="tableDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="表格样式",
                            items=(
                                RibbonItemSpec(
                                    cmd="tbl_shading_color",
                                    size="large",
                                    label="底纹",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "tables", tooltip_src="底纹颜色"
                                    ),
                                ),
                                RibbonItemSpec(
                                    cmd="tableBordersAll",
                                    size="large",
                                    label="边框",
                                    split=True,
                                    menu_builder=_menu_from(
                                        window, "tables", cmd_id="tableBordersAll"
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
                RibbonTabSpec(
                    tab_id="tableLayout",
                    label="布局",
                    groups=(
                        RibbonGroupSpec(
                            label="表",
                            items=(
                                RibbonItemSpec(
                                    cmd="tbl_select_table", size="large", label="选择表格"
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="行和列",
                            items=(
                                "tbl_insert_row_above",
                                "tbl_insert_row_below",
                                "tbl_insert_col_left",
                                "tbl_insert_col_right",
                                "tbl_delete_row",
                                "tbl_delete_col",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="合并",
                            items=("tableMergeCells", "tableSplitCell"),
                        ),
                        RibbonGroupSpec(
                            label="单元格大小",
                            items=("distRows", "distCols"),
                        ),
                        RibbonGroupSpec(
                            label="对齐方式",
                            items=("cellTop", "cellMiddle", "cellBottom"),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="wordart",
            set_label="艺术字工具",
            when=lambda: _lectern_selected_kind(window) == "wordart",
            tabs=(
                RibbonTabSpec(
                    tab_id="wordartFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="文字",
                            items=(
                                RibbonItemSpec(cmd="wordartEdit", size="large", label="编辑文字"),
                                "wordartGallery",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="艺术字样式",
                            launcher="wa_format",
                            items=(
                                RibbonItemSpec(
                                    cmd="wa_shape_menu",
                                    size="large",
                                    label="艺术字形状",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "wordart", tooltip_src="艺术字形状"
                                    ),
                                ),
                                "waSameHeight",
                                "waVertical",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    return RibbonSpec(
        app_id="lectern",
        qat=qat,
        file_actions=file_actions,
        tabs=tabs,
        contextual=contextual,
        icons=icons,
    )
