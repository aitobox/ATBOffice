"""Declarative Paper 2016 Ribbon specification for Quire word processor."""

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


def _quire_is_picture(window: Any) -> bool:
    ctx = getattr(window, "_toolbar_context", {})
    if ctx.get("is_picture"):
        return True
    from atboffice.modules.writer.models.drawing import PictureItem, ShapeItem

    canvas = window.writer_view.canvas_view
    item = canvas.selected_float()
    if item is None or isinstance(item, ShapeItem):
        return False
    return isinstance(item, PictureItem) or getattr(item, "t", "") in ("picture", "img")


def _quire_is_drawing(window: Any) -> bool:
    ctx = getattr(window, "_toolbar_context", {})
    if ctx.get("is_drawing"):
        return True
    canvas = window.writer_view.canvas_view
    item = canvas.selected_float()
    return item is not None and not _quire_is_picture(window)


def _quire_in_table(window: Any) -> bool:
    return window.writer_view.canvas_view.get_current_table_context() is not None


def _quire_in_header_footer(window: Any) -> bool:
    return bool(getattr(window, "_toolbar_context", {}).get("hf_edit"))


def _quire_in_outline(window: Any) -> bool:
    from atboffice.modules.writer.views.view_modes import ViewMode

    return getattr(window.writer_view, "view_mode", None) == ViewMode.OUTLINE


def build_quire_ribbon_spec(window: Any) -> RibbonSpec:
    """Build the Paper 2016 RibbonSpec over ``QuireWindow``'s live ``ActionRegistry``."""
    canvas = window.writer_view.canvas_view

    icons: dict[str, str] = {
        "save_as": "save",
        "tools_options": "options",
        "officeClipboard": "clipboard",
        "format_font": "font",
        "format_paragraph": "paragraph",
        "format_borders": "tablesBorders",
        "format_tabs": "tabStops",
        "insert_page_break": "pageBreak",
        "table_insert": "table",
        "tb_table_drop": "table",
        "autoshapes_menu": "autoshapes",
        "insertComment": "comment",
        "insert_page_number": "pageNum",
        "insert_date_time": "date",
        "insert_symbol": "symbol",
        "columns_menu": "columns",
        "lineSpacing_menu": "lineSpacing",
        "draw_order_front": "bringFront",
        "draw_order_back": "sendBack",
        "draw_group": "group",
        "draw_ungroup": "ungroup",
        "draw_shadow_style": "shadowStyle",
        "tools_word_count": "wordCount",
        "tools_language": "language",
        "rev_delete_all_comments": "delete",
        "rev_display_mode": "reveal",
        "rev_show_menu": "comment",
        "view_reading": "read",
        "view_print": "printView",
        "view_web": "webView",
        "view_outline": "outlineView",
        "view_normal": "normalView",
        "view_ruler": "ruler",
        "view_doc_map": "docMap",
        "view_thumbnails": "thumbnails",
        "taskPane": "taskpane",
        "window_zoom": "zoom",
        "view_fullscreen": "fullScreen",
        "window_bring_all": "arrangeAll",
        "window_minimize": "collapse",
        "tbl_dash_style": "dashStyle",
        "tbl_line_weight": "lineStyle",
        "table_select": "selectTable",
        "table_properties": "tableProps",
        "tbl_insert_row_above": "rowAbove",
        "tbl_insert_row_below": "rowBelow",
        "tbl_insert_col_left": "colLeft",
        "tbl_insert_col_right": "colRight",
        "table_delete": "deleteTable",
        "tbl_align_menu": "alignTop",
        "pic_color_mode": "colorPic",
        "pic_wrap_mode": "textWrap",
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
            52,
            "字号",
            parent,
        )

    def _style_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "style_combo", None),
            window._on_style_combo_changed,
            128,
            "样式",
            parent,
        )

    def _zoom_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "zoom_combo", None),
            window._on_zoom_combo_changed,
            84,
            "显示比例",
            parent,
        )

    def _highlight_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "highlight", "#FFFF00", "突出显示", canvas.set_highlight_color, parent
        )

    def _font_color_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "font", "#FF0000", "字体颜色", canvas.set_font_color, parent
        )

    def _draw_fill_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "fill",
            "#CFE0FB",
            "填充颜色",
            lambda c: getattr(canvas, "set_float_fill_color", lambda _c: None)(c),
            parent,
        )

    def _draw_line_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "line",
            "#1D4F9E",
            "线条颜色",
            lambda c: getattr(canvas, "set_float_line_color", lambda _c: None)(c),
            parent,
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
    )

    file_actions = (
        "new",
        "open",
        "-",
        "save",
        "save_as",
        "-",
        "pageSetup",
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
                        "painter",
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
                            )
                        ),
                        RibbonItemSpec(
                            row=(
                                "bold",
                                "italic",
                                "underline",
                                "|",
                                RibbonItemSpec(widget_factory=_highlight_btn),
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
                        RibbonItemSpec(
                            row=("bullets", "numbering", "decIndent", "incIndent", "|", "showMarks")
                        ),
                        RibbonItemSpec(
                            row=(
                                "alignLeft",
                                "alignCenter",
                                "alignRight",
                                "justify",
                                "|",
                                RibbonItemSpec(
                                    cmd="lineSpacing_menu",
                                    size="small",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "formatting", tooltip_src="行距"
                                    ),
                                ),
                                RibbonItemSpec(
                                    cmd="borderBtn",
                                    size="small",
                                    split=True,
                                    menu_builder=_menu_from(
                                        window, "formatting", cmd_id="borderBtn"
                                    ),
                                ),
                            )
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="样式",
                    launcher="stylesPane",
                    items=(
                        RibbonItemSpec(widget_factory=_style_combo),
                        "stylesPane",
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
                    label="页",
                    items=(RibbonItemSpec(cmd="insert_page_break", size="large", label="分页符"),),
                ),
                RibbonGroupSpec(
                    label="表格",
                    items=(
                        RibbonItemSpec(
                            cmd="tb_table_drop",
                            size="large",
                            label="表格",
                            drop=True,
                            menu_builder=_menu_from(window, "standard", tooltip_src="插入表格"),
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="插图",
                    items=(
                        RibbonItemSpec(cmd="insertPicture", size="large", label="图片"),
                        "insertClipArt",
                        RibbonItemSpec(
                            cmd="autoshapes_menu",
                            drop=True,
                            menu_builder=_menu_from(window, "drawing", tooltip_src="自选图形"),
                        ),
                        "insertDiagram",
                        "insertExcel",
                    ),
                ),
                RibbonGroupSpec(
                    label="链接",
                    items=(RibbonItemSpec(cmd="hyperlink", size="large", label="超链接"),),
                ),
                RibbonGroupSpec(
                    label="批注",
                    items=(RibbonItemSpec(cmd="insertComment", size="large", label="批注"),),
                ),
                RibbonGroupSpec(
                    label="页眉和页脚",
                    items=("headerFooter", "insert_page_number"),
                ),
                RibbonGroupSpec(
                    label="文本",
                    items=(
                        RibbonItemSpec(cmd="textBox", size="large", label="文本框"),
                        "insertWordArt",
                        "insert_date_time",
                    ),
                ),
                RibbonGroupSpec(
                    label="符号",
                    items=(RibbonItemSpec(cmd="insert_symbol", size="large", label="符号"),),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="layout",
            label="页面布局",
            groups=(
                RibbonGroupSpec(
                    label="页面设置",
                    launcher="pageSetup",
                    items=(
                        RibbonItemSpec(cmd="pageSetup", size="large", label="页面设置"),
                        RibbonItemSpec(
                            cmd="columns_menu",
                            size="large",
                            label="分栏",
                            drop=True,
                            menu_builder=_menu_from(window, "standard", tooltip_src="分栏"),
                        ),
                        "insert_page_break",
                        "textDirection",
                    ),
                ),
                RibbonGroupSpec(
                    label="段落",
                    icon="paragraph",
                    launcher="format_paragraph",
                    items=("incIndent", "decIndent", "format_tabs"),
                ),
                RibbonGroupSpec(
                    label="页面背景",
                    items=(RibbonItemSpec(cmd="format_borders", size="large", label="边框和底纹"),),
                ),
                RibbonGroupSpec(
                    label="排列",
                    items=(
                        "draw_order_front",
                        "draw_order_back",
                        "draw_group",
                        "draw_ungroup",
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="mailings",
            label="邮件",
            groups=(
                RibbonGroupSpec(
                    label="开始邮件合并",
                    items=(
                        RibbonItemSpec(cmd="mmMainDoc", size="large", label="主文档设置"),
                        "mmOpenSource",
                        "mmRecipients",
                    ),
                ),
                RibbonGroupSpec(
                    label="编写和插入域",
                    items=("mmAddress", "mmGreeting", "mmInsertField"),
                ),
                RibbonGroupSpec(
                    label="预览结果",
                    items=(
                        RibbonItemSpec(cmd="mmViewData", size="large", label="查看合并数据"),
                        RibbonItemSpec(row=("mmFirst", "mmPrev", "mmNext", "mmLast")),
                    ),
                ),
                RibbonGroupSpec(
                    label="完成",
                    items=(
                        RibbonItemSpec(cmd="mmMergeNew", size="large", label="合并到新文档"),
                        "mmMergePrint",
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
                        RibbonItemSpec(cmd="spelling", size="large", label="拼写和语法"),
                        "thesaurus",
                        "tools_word_count",
                        "research",
                    ),
                ),
                RibbonGroupSpec(
                    label="语言",
                    items=(RibbonItemSpec(cmd="tools_language", size="large", label="语言"),),
                ),
                RibbonGroupSpec(
                    label="批注",
                    items=(
                        RibbonItemSpec(cmd="insertComment", size="large", label="新建批注"),
                        "rev_delete_all_comments",
                    ),
                ),
                RibbonGroupSpec(
                    label="修订",
                    items=(
                        RibbonItemSpec(cmd="trackChanges", size="large", label="修订"),
                        RibbonItemSpec(
                            cmd="rev_display_mode",
                            drop=True,
                            menu_builder=_menu_from(
                                window, "reviewing", tooltip_src="显示以供审阅"
                            ),
                        ),
                        RibbonItemSpec(
                            cmd="rev_show_menu",
                            drop=True,
                            menu_builder=_menu_from(window, "reviewing", tooltip_src="显示"),
                        ),
                        "reviewingPane",
                    ),
                ),
                RibbonGroupSpec(
                    label="更改",
                    items=(
                        RibbonItemSpec(
                            cmd="acceptChange",
                            size="large",
                            label="接受",
                            split=True,
                            menu_builder=_menu_from(window, "reviewing", cmd_id="acceptChange"),
                        ),
                        RibbonItemSpec(
                            cmd="rejectChange",
                            label="拒绝",
                            split=True,
                            menu_builder=_menu_from(window, "reviewing", cmd_id="rejectChange"),
                        ),
                        "prevChange",
                        "nextChange",
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="view",
            label="视图",
            groups=(
                RibbonGroupSpec(
                    label="文档视图",
                    items=(
                        RibbonItemSpec(cmd="view_reading", size="large", label="阅读版式"),
                        RibbonItemSpec(cmd="view_print", size="large", label="页面视图"),
                        RibbonItemSpec(cmd="view_web", size="large", label="Web 版式"),
                        "view_outline",
                        "view_normal",
                    ),
                ),
                RibbonGroupSpec(
                    label="显示",
                    items=("view_ruler", "view_doc_map", "view_thumbnails", "taskPane"),
                ),
                RibbonGroupSpec(
                    label="显示比例",
                    items=(
                        RibbonItemSpec(cmd="window_zoom", size="large", label="显示比例"),
                        RibbonItemSpec(widget_factory=_zoom_combo),
                        "view_fullscreen",
                    ),
                ),
                RibbonGroupSpec(
                    label="窗口",
                    items=("window_bring_all", "window_minimize"),
                ),
            ),
        ),
    )

    contextual = (
        RibbonContextSetSpec(
            set_id="table",
            set_label="表格工具",
            when=lambda: _quire_in_table(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="tableDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="表格样式",
                            items=(
                                RibbonItemSpec(
                                    cmd="tableAutoFormat", size="large", label="表格自动套用格式"
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="边框",
                            launcher="format_borders",
                            items=(
                                RibbonItemSpec(
                                    cmd="tbl_dash_style",
                                    drop=True,
                                    menu_builder=_menu_from(window, "tables", tooltip_src="线型"),
                                ),
                                RibbonItemSpec(
                                    cmd="tbl_line_weight",
                                    drop=True,
                                    menu_builder=_menu_from(window, "tables", tooltip_src="粗细"),
                                ),
                                RibbonItemSpec(
                                    cmd="tableBorderBtn",
                                    size="large",
                                    label="边框",
                                    split=True,
                                    menu_builder=_menu_from(
                                        window, "tables", cmd_id="tableBorderBtn"
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
                                "table_select",
                                RibbonItemSpec(
                                    cmd="table_properties", size="large", label="表格属性"
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="绘图",
                            items=(
                                RibbonItemSpec(cmd="drawTable", size="large", label="绘制表格"),
                                RibbonItemSpec(cmd="eraser", size="large", label="擦除"),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="行和列",
                            items=(
                                "tbl_insert_row_above",
                                "tbl_insert_row_below",
                                "tbl_insert_col_left",
                                "tbl_insert_col_right",
                                "table_delete",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="合并",
                            items=("mergeCells", "splitCells"),
                        ),
                        RibbonGroupSpec(
                            label="单元格大小",
                            items=("distRows", "distCols"),
                        ),
                        RibbonGroupSpec(
                            label="对齐方式",
                            items=(
                                RibbonItemSpec(
                                    cmd="tbl_align_menu",
                                    drop=True,
                                    menu_builder=_menu_from(window, "tables", tooltip_src="对齐"),
                                ),
                                "textDirection",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="数据",
                            items=("sortAsc", "sortDesc", "autoSum"),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="picture",
            set_label="图片工具",
            when=lambda: _quire_is_picture(window),
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
                                "picReset",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=(
                                RibbonItemSpec(
                                    cmd="pic_wrap_mode",
                                    size="large",
                                    label="文字环绕",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "picture", tooltip_src="文字环绕"
                                    ),
                                ),
                                "draw_order_front",
                                "draw_order_back",
                                "picRotate",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="大小",
                            launcher="formatObject",
                            items=(RibbonItemSpec(cmd="picCrop", size="large", label="裁剪"),),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="drawing",
            set_label="绘图工具",
            when=lambda: _quire_is_drawing(window),
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
                                    label="自选图形",
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
                                    cmd="draw_shadow_style",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "drawing", tooltip_src="阴影样式"
                                    ),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="艺术字样式",
                            items=(
                                RibbonItemSpec(
                                    cmd="wordartGallery", size="large", label="艺术字库"
                                ),
                                "wordartEdit",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=(
                                "draw_order_front",
                                "draw_order_back",
                                "draw_group",
                                "draw_ungroup",
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="headerFooter",
            set_label="页眉和页脚工具",
            auto_open=True,
            when=lambda: _quire_in_header_footer(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="hfDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="页眉和页脚",
                            items=(
                                RibbonItemSpec(cmd="hfPageNum", size="large", label="页码"),
                                "hfNumPages",
                                "hfFormatPageNum",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="插入",
                            items=(
                                RibbonItemSpec(cmd="hfDate", size="large", label="日期"),
                                "hfTime",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="导航",
                            items=(
                                RibbonItemSpec(cmd="hfSwitch", size="large", label="转到页脚"),
                                "hfPrev",
                                "hfNext",
                                "hfLinkPrev",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="选项",
                            items=("hfShowText", "pageSetup"),
                        ),
                        RibbonGroupSpec(
                            label="关闭",
                            items=(
                                RibbonItemSpec(cmd="hfClose", size="large", label="关闭页眉和页脚"),
                            ),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="outlining",
            set_label="大纲",
            auto_open=True,
            when=lambda: _quire_in_outline(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="outlining",
                    label="大纲",
                    groups=(
                        RibbonGroupSpec(
                            label="大纲工具",
                            items=(
                                RibbonItemSpec(
                                    row=("promoteH1", "promote", "demote", "demoteBody")
                                ),
                                RibbonItemSpec(row=("moveUp", "moveDown", "expand", "collapse")),
                                "olFirstLine",
                                "olFormatting",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="目录",
                            items=("updateTOC", "gotoTOC"),
                        ),
                        RibbonGroupSpec(
                            label="关闭",
                            items=(
                                RibbonItemSpec(
                                    cmd="view_print", size="large", label="关闭大纲视图"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    return RibbonSpec(
        app_id="quire",
        qat=qat,
        file_actions=file_actions,
        tabs=tabs,
        contextual=contextual,
        icons=icons,
    )
