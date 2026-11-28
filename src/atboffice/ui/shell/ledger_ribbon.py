"""Declarative Paper 2016 Ribbon specification for Ledger spreadsheet."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMenu, QWidget

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


def _menu_actions(window: Any, action_ids: tuple[str, ...]):
    def _build() -> QMenu:
        menu = QMenu(window)
        reg = window.action_registry
        for aid in action_ids:
            if aid == "-":
                menu.addSeparator()
                continue
            act = reg.get_action(aid)
            if act is not None and act.isVisible():
                menu.addAction(act)
        return menu

    return _build


def _ledger_selected_kind(window: Any) -> str | None:
    layer = getattr(getattr(window, "spreadsheet_view", None), "object_layer", None)
    obj = getattr(layer, "selected_object", None) if layer is not None else None
    if obj is None:
        return None
    kind = getattr(obj, "kind", None)
    if kind == "chart":
        return "chart"
    if kind in ("image", "picture"):
        return "picture"
    return "drawing"


def _ledger_in_list(window: Any) -> bool:
    return bool(getattr(window, "_toolbar_context", {}).get("in_table"))


def build_ledger_ribbon_spec(window: Any) -> RibbonSpec:
    """Build the Paper 2016 RibbonSpec over ``LedgerWindow``'s live ``ActionRegistry``."""
    icons: dict[str, str] = {
        "save_as": "save",
        "tools_options": "options",
        "officeClipboard": "clipboard",
        "format_font": "font",
        "format_cells": "formatCells",
        "autoFormat": "tableAutoFormat",
        "clearAll": "eraser",
        "clearFormats": "eraser",
        "clearContents": "eraser",
        "clearComments": "comment",
        "data_pivottable": "pivot",
        "insertPivotChart": "chart",
        "insert_clipart": "clipart",
        "insert_wordart": "wordart",
        "insert_symbol": "symbol",
        "insert_page_break": "pageBreak",
        "bringToFront": "bringFront",
        "sendToBack": "sendBack",
        "insert_function": "fx",
        "defineName": "nameBox",
        "importHtml": "webPage",
        "showAllFilter": "filter",
        "advancedFilter": "filterOn",
        "textToColumns": "textToCols",
        "consolidate": "subtotal",
        "scenarios": "goalSeek",
        "tools_goal_seek": "goalSeek",
        "tools_solver": "goalSeek",
        "solver": "goalSeek",
        "dataTable": "table",
        "outlineGroup": "group",
        "outlineUngroup": "ungroup",
        "data_subtotals": "subtotal",
        "outlineShowDetail": "expand",
        "outlineHideDetail": "collapse",
        "outlineClear": "ungroup",
        "rev_insertComment": "comment",
        "showComments": "comment",
        "research": "research",
        "thesaurus": "thesaurus",
        "protectSheet": "protect",
        "protectWorkbook": "protect",
        "view_normal": "normalGrid",
        "view_page_break": "pageBreakView",
        "view_fullscreen": "fullScreen",
        "taskPane": "taskpane",
        "window_zoom": "zoom",
        "windowSplit": "split",
        "window_bring_all": "arrangeAll",
        "window_minimize": "collapse",
        "chart_type_menu": "chart",
        "draw_group": "group",
        "draw_ungroup": "ungroup",
    }

    def _font_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "font_combo", None),
            window._apply_font_family,
            126,
            "字体",
            parent,
        )

    def _size_combo(parent: QWidget) -> QWidget:
        return make_mirrored_combo(
            getattr(window, "size_combo", None),
            window._apply_font_size,
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

    def _fill_color_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "fill", "#FFFF00", "填充颜色", window._apply_fill_color, parent
        )

    def _font_color_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "font", "#FF0000", "字体颜色", window._apply_font_color, parent
        )

    def _draw_fill_btn(parent: QWidget) -> QWidget:
        return make_ribbon_color_button(
            "fill", "#CFE0FB", "填充颜色", window._apply_drawing_fill_color, parent
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
                        "formatPainter",
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
                                RibbonItemSpec(
                                    cmd="bordersApply",
                                    size="small",
                                    split=True,
                                    menu_builder=_menu_from(
                                        window, "formatting", cmd_id="bordersApply"
                                    ),
                                ),
                                RibbonItemSpec(widget_factory=_fill_color_btn),
                                RibbonItemSpec(widget_factory=_font_color_btn),
                            )
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="对齐方式",
                    launcher="format_cells",
                    items=(
                        RibbonItemSpec(
                            row=(
                                "alignLeft",
                                "alignCenter",
                                "alignRight",
                                "|",
                                "decIndent",
                                "incIndent",
                            )
                        ),
                        RibbonItemSpec(cmd="mergeCenter", size="medium", label="合并及居中"),
                    ),
                ),
                RibbonGroupSpec(
                    label="数字",
                    launcher="format_cells",
                    items=(
                        RibbonItemSpec(row=("currencyStyle", "percentStyle", "commaStyle")),
                        RibbonItemSpec(row=("incDecimal", "decDecimal")),
                    ),
                ),
                RibbonGroupSpec(
                    label="样式",
                    items=(
                        RibbonItemSpec(cmd="condFormat", size="large", label="条件格式"),
                        RibbonItemSpec(cmd="autoFormat", size="large", label="自动套用格式"),
                    ),
                ),
                RibbonGroupSpec(
                    label="编辑",
                    items=(
                        RibbonItemSpec(
                            cmd="autoSum",
                            label="自动求和",
                            split=True,
                            menu_builder=_menu_from(window, "standard", cmd_id="autoSum"),
                        ),
                        RibbonItemSpec(
                            label="清除",
                            icon="eraser",
                            drop=True,
                            menu_builder=_menu_actions(
                                window,
                                ("clearAll", "clearFormats", "clearContents", "clearComments"),
                            ),
                        ),
                        RibbonItemSpec(
                            label="排序和筛选",
                            icon="sortAsc",
                            size="large",
                            drop=True,
                            menu_builder=_menu_actions(
                                window,
                                (
                                    "sortAsc",
                                    "sortDesc",
                                    "sortDlg",
                                    "-",
                                    "autoFilter",
                                    "showAllFilter",
                                    "advancedFilter",
                                ),
                            ),
                        ),
                        RibbonItemSpec(
                            label="查找和选择",
                            icon="find",
                            size="large",
                            drop=True,
                            menu_builder=_menu_actions(window, ("find", "replace", "selectAll")),
                        ),
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="insert",
            label="插入",
            groups=(
                RibbonGroupSpec(
                    label="表格",
                    items=(
                        RibbonItemSpec(cmd="data_pivottable", size="large", label="数据透视表"),
                    ),
                ),
                RibbonGroupSpec(
                    label="插图",
                    items=(
                        RibbonItemSpec(cmd="insertPicture", size="large", label="图片"),
                        "insert_clipart",
                        "insertShape",
                    ),
                ),
                RibbonGroupSpec(
                    label="图表",
                    items=(
                        RibbonItemSpec(cmd="chartWizard", size="large", label="图表向导"),
                        "insertChart",
                        "insertPivotChart",
                    ),
                ),
                RibbonGroupSpec(
                    label="链接",
                    items=(RibbonItemSpec(cmd="hyperlink", size="large", label="超链接"),),
                ),
                RibbonGroupSpec(
                    label="文本",
                    items=(
                        RibbonItemSpec(cmd="insertTextBox", size="large", label="文本框"),
                        "headerFooter",
                        "insert_wordart",
                    ),
                ),
                RibbonGroupSpec(
                    label="符号",
                    items=(RibbonItemSpec(cmd="insert_symbol", size="large", label="符号"),),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="pageLayout",
            label="页面布局",
            groups=(
                RibbonGroupSpec(
                    label="页面设置",
                    launcher="pageSetup",
                    items=(
                        RibbonItemSpec(cmd="pageSetup", size="large", label="页面设置"),
                        RibbonItemSpec(cmd="insert_page_break", size="large", label="分页符"),
                    ),
                ),
                RibbonGroupSpec(
                    label="排列",
                    items=("bringToFront", "sendToBack"),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="formulas",
            label="公式",
            groups=(
                RibbonGroupSpec(
                    label="函数库",
                    items=(
                        RibbonItemSpec(cmd="insert_function", size="large", label="插入函数"),
                        RibbonItemSpec(
                            cmd="autoSum",
                            size="large",
                            label="自动求和",
                            split=True,
                            menu_builder=_menu_from(window, "standard", cmd_id="autoSum"),
                        ),
                    ),
                ),
                RibbonGroupSpec(
                    label="定义的名称",
                    items=(RibbonItemSpec(cmd="defineName", size="large", label="定义名称"),),
                ),
                RibbonGroupSpec(
                    label="公式审核",
                    items=(
                        "tracePrecedents",
                        "traceDependents",
                        "removeArrows",
                        "traceError",
                        "evaluateFormula",
                        RibbonItemSpec(cmd="watchWindow", size="large", label="监视窗口"),
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="data",
            label="数据",
            groups=(
                RibbonGroupSpec(
                    label="获取外部数据",
                    items=(RibbonItemSpec(cmd="importHtml", size="large", label="导入网页表格"),),
                ),
                RibbonGroupSpec(
                    label="排序和筛选",
                    items=(
                        RibbonItemSpec(row=("sortAsc", "sortDesc")),
                        RibbonItemSpec(cmd="sortDlg", size="large", label="排序"),
                        RibbonItemSpec(cmd="autoFilter", size="large", label="筛选"),
                        "showAllFilter",
                        "advancedFilter",
                    ),
                ),
                RibbonGroupSpec(
                    label="数据工具",
                    items=(
                        RibbonItemSpec(cmd="textToColumns", size="large", label="分列"),
                        RibbonItemSpec(
                            cmd="validation",
                            split=True,
                            menu_builder=_menu_from(window, "auditing", cmd_id="validation"),
                        ),
                        "consolidate",
                    ),
                ),
                RibbonGroupSpec(
                    label="预测",
                    items=("scenarios", "tools_goal_seek", "dataTable", "tools_solver"),
                ),
                RibbonGroupSpec(
                    label="分级显示",
                    items=(
                        RibbonItemSpec(cmd="outlineGroup", size="large", label="创建组"),
                        RibbonItemSpec(cmd="outlineUngroup", size="large", label="取消组合"),
                        RibbonItemSpec(cmd="data_subtotals", size="large", label="分类汇总"),
                        "outlineShowDetail",
                        "outlineHideDetail",
                        "outlineClear",
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
                RibbonGroupSpec(
                    label="批注",
                    items=(
                        RibbonItemSpec(cmd="rev_insertComment", size="large", label="新建批注"),
                        "deleteComment",
                        "showHideComment",
                        "showComments",
                    ),
                ),
                RibbonGroupSpec(
                    label="更改",
                    items=(
                        RibbonItemSpec(cmd="protectSheet", size="large", label="保护工作表"),
                        RibbonItemSpec(cmd="protectWorkbook", size="large", label="保护工作簿"),
                    ),
                ),
            ),
        ),
        RibbonTabSpec(
            tab_id="view",
            label="视图",
            groups=(
                RibbonGroupSpec(
                    label="工作簿视图",
                    items=(
                        RibbonItemSpec(cmd="view_normal", size="large", label="普通"),
                        RibbonItemSpec(cmd="view_page_break", size="large", label="分页预览"),
                        "view_fullscreen",
                    ),
                ),
                RibbonGroupSpec(
                    label="显示",
                    items=("taskPane",),
                ),
                RibbonGroupSpec(
                    label="显示比例",
                    items=(
                        RibbonItemSpec(cmd="window_zoom", size="large", label="显示比例"),
                        RibbonItemSpec(widget_factory=_zoom_combo),
                    ),
                ),
                RibbonGroupSpec(
                    label="窗口",
                    items=("windowSplit", "window_bring_all", "window_minimize"),
                ),
            ),
        ),
    )

    contextual = (
        RibbonContextSetSpec(
            set_id="chart",
            set_label="图表工具",
            when=lambda: _ledger_selected_kind(window) == "chart",
            tabs=(
                RibbonTabSpec(
                    tab_id="chartDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="类型",
                            items=(
                                RibbonItemSpec(
                                    cmd="chart_type_menu",
                                    size="large",
                                    label="更改图表类型",
                                    drop=True,
                                    menu_builder=_menu_from(
                                        window, "chart", tooltip_src="图表类型(&T)"
                                    ),
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="数据",
                            items=(
                                RibbonItemSpec(cmd="chartWizard", size="large", label="图表向导"),
                            ),
                        ),
                    ),
                ),
                RibbonTabSpec(
                    tab_id="chartFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="当前所选内容",
                            items=(
                                RibbonItemSpec(
                                    cmd="formatObject", size="large", label="设置对象格式"
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=("bringToFront", "sendToBack"),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="picture",
            set_label="图片工具",
            when=lambda: _ledger_selected_kind(window) == "picture",
            tabs=(
                RibbonTabSpec(
                    tab_id="pictureFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="图片",
                            items=(
                                RibbonItemSpec(
                                    cmd="formatObject", size="large", label="设置对象格式"
                                ),
                            ),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=("bringToFront", "sendToBack"),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="drawing",
            set_label="绘图工具",
            when=lambda: _ledger_selected_kind(window) == "drawing",
            tabs=(
                RibbonTabSpec(
                    tab_id="drawingFormat",
                    label="格式",
                    groups=(
                        RibbonGroupSpec(
                            label="插入形状",
                            items=(
                                RibbonItemSpec(cmd="insertShape", size="large", label="自选图形"),
                                "insertTextBox",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="形状样式",
                            launcher="formatObject",
                            items=(RibbonItemSpec(widget_factory=_draw_fill_btn),),
                        ),
                        RibbonGroupSpec(
                            label="排列",
                            items=("bringToFront", "sendToBack", "draw_group", "draw_ungroup"),
                        ),
                    ),
                ),
            ),
        ),
        RibbonContextSetSpec(
            set_id="list",
            set_label="表格工具",
            when=lambda: _ledger_in_list(window),
            tabs=(
                RibbonTabSpec(
                    tab_id="listDesign",
                    label="设计",
                    groups=(
                        RibbonGroupSpec(
                            label="工具",
                            items=(
                                RibbonItemSpec(
                                    cmd="convertToRange", size="large", label="转换为区域"
                                ),
                                "sortDlg",
                                "autoFilter",
                            ),
                        ),
                        RibbonGroupSpec(
                            label="表样式选项",
                            items=("totalRow", "insertRows", "insertCols"),
                        ),
                    ),
                ),
            ),
        ),
    )

    return RibbonSpec(
        app_id="ledger",
        qat=qat,
        file_actions=file_actions,
        tabs=tabs,
        contextual=contextual,
        icons=icons,
    )
