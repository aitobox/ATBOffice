"""Declarative Office 2003 Luna toolbar cluster for Lectern presentation editor.

Implements all 10 PowerPoint 2003 Luna toolbars with 1:1 action parity against
the original application:
1. Standard (常用)
2. Formatting (格式)
3. Slide Sorter (幻灯片浏览)
4. Slide Master View (母版视图)
5. Outlining (大纲)
6. Diagram (IntelliArt 关系图)
7. Tables and Borders (表格和边框)
8. Picture (图片)
9. WordArt (艺术字)
10. Drawing (绘图)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMenu,
)

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.core.i18n import clean_asian_mnemonic
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar
from atboffice.ui.components.toolbar_buttons import (
    OfficeDropDownButton,
    OfficeSplitButton,
)
from atboffice.ui.icons import get_office_icon, has_office_icon


def safe_tr(text: str) -> str:
    """Translate UI text safely for Lectern toolbars."""
    return core_safe_tr(text)


_LECTERN_DROP_ICONS: Final[dict[str, str]] = {
    "Border Style": "dashStyle",
    "边框样式": "dashStyle",
    "Border Width": "lineStyle",
    "边框粗细": "lineStyle",
    "Border Color": "lineColor",
    "边框颜色": "lineColor",
    "Borders": "bordersAll",
    "边框": "bordersAll",
    "Fill Color": "fillColor",
    "填充颜色": "fillColor",
    "LettersArt Shape": "waShape",
    "艺术字形状": "waShape",
    "LettersArt Alignment": "alignCenter",
    "艺术字对齐": "alignCenter",
    "LettersArt Character Spacing": "charSpacing",
    "艺术字字符间距": "charSpacing",
    "Change Layout": "layout",
    "更改版式": "layout",
    "Change Colors": "colorPic",
    "更改颜色": "colorPic",
    "IntelliArt Styles": "themes",
    "样式": "themes",
    "线型": "lineStyle",
    "虚线线型": "dashStyle",
    "箭头样式": "arrowStyle",
    "阴影样式": "shadowStyle",
    "颜色": "colorPic",
    "线条样式": "lineStyle",
}

_LECTERN_DROP_AIDS_MAP: Final[dict[str, str]] = {
    # Diagram
    "版式(&L)": "diagram_layout_menu",
    "版式": "diagram_layout_menu",
    "更改颜色(&C)": "diagram_colors_menu",
    "更改颜色": "diagram_colors_menu",
    "样式(&S)": "diagram_style_menu",
    "样式": "diagram_style_menu",
    # Tables
    "表格(&T)": "table_menu",
    "表格": "table_menu",
    "粗细": "tbl_line_weight",
    "线条颜色": "tbl_line_color",
    "底纹颜色": "tbl_shading_color",
    # Picture
    "颜色(&C)": "pic_color_mode",
    "颜色": "pic_color_mode",
    "线条样式": "pic_line_style",
    # WordArt
    "艺术字形状(&S)": "wa_shape_menu",
    "艺术字形状": "wa_shape_menu",
    "艺术字对齐(&A)": "wa_align_menu",
    "艺术字对齐": "wa_align_menu",
    "字符间距(&P)": "wa_char_spacing_menu",
    "字符间距": "wa_char_spacing_menu",
    # Drawing
    "绘图(&R)": "draw_menu",
    "绘图": "draw_menu",
    "自选图形(&U)": "autoshapes_menu",
    "自选图形": "autoshapes_menu",
    "虚线线型": "draw_dash_style",
    "箭头样式": "draw_arrow_style",
    "阴影样式": "draw_shadow_style",
}

_LECTERN_DROP_AIDS: Final[list[str]] = [
    # Diagram
    "diagram_layout_menu",
    "diagram_colors_menu",
    "diagram_style_menu",
    # Tables
    "table_menu",
    "tbl_dash_style",
    "tbl_line_weight",
    "tbl_line_color",
    "tbl_shading_color",
    # Picture
    "pic_color_mode",
    "pic_line_style",
    # WordArt
    "wa_shape_menu",
    "wa_align_menu",
    "wa_char_spacing_menu",
    # Drawing
    "draw_menu",
    "autoshapes_menu",
    "lineStyle",
    "draw_dash_style",
    "draw_arrow_style",
    "draw_shadow_style",
]

_LECTERN_KNOWN_ITEM_AIDS: Final[dict[str, tuple[str, str, bool, bool]]] = {
    # Undo / Redo
    "undo_empty": ("undo_empty", "无操作可撤销", False, False),
    "redo_empty": ("redo_empty", "无操作可重做", False, False),
    # View Gray Split
    "view_color": ("view_color", "彩色(&C)", True, True),
    "view_grayscale": ("view_grayscale", "灰度(&G)", True, True),
    "view_black_and_white": ("view_black_and_white", "纯黑白(&B)", True, True),
    # Diagram: Layout Drop
    "diag_layout_org": ("diag_layout_org", "组织结构图", True, False),
    "diag_layout_hierarchy": ("diag_layout_hierarchy", "层次结构", True, False),
    "diag_layout_cycle": ("diag_layout_cycle", "循环图", True, False),
    "diag_layout_radial": ("diag_layout_radial", "射线图", True, False),
    "diag_layout_pyramid": ("diag_layout_pyramid", "金字塔图", True, False),
    "diag_layout_venn": ("diag_layout_venn", "维恩图", True, False),
    "diag_layout_target": ("diag_layout_target", "目标图", True, False),
    # Diagram: Colors Drop
    "diag_color_primary": ("diag_color_primary", "主色调", True, False),
    "diag_color_colorful": ("diag_color_colorful", "多彩", True, False),
    "diag_color_dark": ("diag_color_dark", "深色", True, False),
    "diag_color_light": ("diag_color_light", "轻快", True, False),
    # Diagram: Styles Drop
    "diag_style_flat": ("diag_style_flat", "平面样式", True, False),
    "diag_style_3d": ("diag_style_3d", "3D 凸起", True, False),
    "diag_style_metal": ("diag_style_metal", "金属质感", True, False),
    "diag_style_gradient": ("diag_style_gradient", "渐变填充", True, False),
    # Tables: Dash Style Drop
    "tbl_line_single": ("tbl_line_single", "实线", True, False),
    "tbl_line_dash": ("tbl_line_dash", "虚线", True, False),
    "tbl_line_dot": ("tbl_line_dot", "点线", True, False),
    "tbl_line_double": ("tbl_line_double", "双线", True, False),
    # Tables: Line Weight Drop
    "tbl_weight_05": ("tbl_weight_05", "0.5 磅", True, False),
    "tbl_weight_10": ("tbl_weight_10", "1.0 磅", True, False),
    "tbl_weight_15": ("tbl_weight_15", "1.5 磅", True, False),
    "tbl_weight_225": ("tbl_weight_225", "2.25 磅", True, False),
    "tbl_weight_30": ("tbl_weight_30", "3.0 磅", True, False),
    "tbl_weight_45": ("tbl_weight_45", "4.5 磅", True, False),
    "tbl_weight_60": ("tbl_weight_60", "6.0 磅", True, False),
    # Tables: Line Color Drop
    "tbl_color_auto": ("tbl_color_auto", "自动", True, False),
    "tbl_color_black": ("tbl_color_black", "黑色", True, False),
    "tbl_color_red": ("tbl_color_red", "红色", True, False),
    "tbl_color_blue": ("tbl_color_blue", "蓝色", True, False),
    "tbl_color_gray": ("tbl_color_gray", "灰色", True, False),
    # Tables: Table Borders Split
    "tbl_border_all": ("tbl_border_all", "所有框线", True, False),
    "tbl_border_outside": ("tbl_border_outside", "外侧框线", True, False),
    "tbl_border_inside": ("tbl_border_inside", "内侧框线", True, False),
    "tbl_border_none": ("tbl_border_none", "无框线", True, False),
    "tbl_border_top": ("tbl_border_top", "顶端框线", True, False),
    "tbl_border_bottom": ("tbl_border_bottom", "底端框线", True, False),
    "tbl_border_left": ("tbl_border_left", "左侧框线", True, False),
    "tbl_border_right": ("tbl_border_right", "右侧框线", True, False),
    # Tables: Shading Color Drop
    "tbl_shade_none": ("tbl_shade_none", "无填充", True, False),
    "tbl_shade_gray": ("tbl_shade_gray", "浅灰色", True, False),
    "tbl_shade_yellow": ("tbl_shade_yellow", "黄色", True, False),
    "tbl_shade_blue": ("tbl_shade_blue", "浅蓝色", True, False),
    "tbl_shade_green": ("tbl_shade_green", "浅绿色", True, False),
    # Tables: Table Menu Drop
    "tbl_insert_table": ("tbl_insert_table", "插入表格(&I)...", True, False),
    "tbl_insert_col_left": ("tbl_insert_col_left", "在左侧插入列", True, False),
    "tbl_insert_col_right": ("tbl_insert_col_right", "在右侧插入列", True, False),
    "tbl_insert_row_above": ("tbl_insert_row_above", "在上方插入行", True, False),
    "tbl_insert_row_below": ("tbl_insert_row_below", "在下方插入行", True, False),
    "tbl_delete_col": ("tbl_delete_col", "删除列(&C)", True, False),
    "tbl_delete_row": ("tbl_delete_row", "删除行(&R)", True, False),
    "tableMergeCells": ("tableMergeCells", "合并单元格(&M)", True, False),
    "tableSplitCell": ("tableSplitCell", "拆分单元格(&P)...", True, False),
    "tbl_select_table": ("tbl_select_table", "选择表格(&S)", True, False),
    "tbl_borders_and_shading": ("tbl_borders_and_shading", "边框和底纹(&B)...", True, False),
    # Picture: Color Mode Drop
    "pic_color_auto": ("pic_color_auto", "自动(&A)", True, False),
    "pic_color_gray": ("pic_color_gray", "灰度(&G)", True, False),
    "pic_color_bw": ("pic_color_bw", "黑白(&B)", True, False),
    "pic_color_washout": ("pic_color_washout", "冲蚀(&W)", True, False),
    # Picture: Line Style Drop
    "pic_weight_075": ("pic_weight_075", "0.75 磅", True, False),
    "pic_weight_15": ("pic_weight_15", "1.5 磅", True, False),
    "pic_weight_30": ("pic_weight_30", "3 磅", True, False),
    "pic_weight_45": ("pic_weight_45", "4.5 磅", True, False),
    "pic_weight_60": ("pic_weight_60", "6 磅", True, False),
    # WordArt: Shape Drop
    "wa_shape_plain": ("wa_shape_plain", "纯文本", True, False),
    "wa_shape_wave": ("wa_shape_wave", "波浪", True, False),
    "wa_shape_arch_up": ("wa_shape_arch_up", "上凸", True, False),
    "wa_shape_arch_down": ("wa_shape_arch_down", "下凹", True, False),
    "wa_shape_circle": ("wa_shape_circle", "环形", True, False),
    "wa_shape_triangle_down": ("wa_shape_triangle_down", "倒三角形", True, False),
    # WordArt: Alignment Drop
    "wa_align_left": ("wa_align_left", "左对齐(&L)", True, False),
    "wa_align_center": ("wa_align_center", "居中(&C)", True, False),
    "wa_align_right": ("wa_align_right", "右对齐(&R)", True, False),
    "wa_align_justify": ("wa_align_justify", "两端对齐(&J)", True, False),
    # WordArt: Character Spacing Drop
    "wa_spacing_very_tight": ("wa_spacing_very_tight", "很紧(&V)", True, False),
    "wa_spacing_tight": ("wa_spacing_tight", "紧密(&T)", True, False),
    "wa_spacing_normal": ("wa_spacing_normal", "常规(&N)", True, False),
    "wa_spacing_loose": ("wa_spacing_loose", "稀疏(&L)", True, False),
    "wa_spacing_very_loose": ("wa_spacing_very_loose", "很松(&E)", True, False),
    # Drawing: AutoShapes Drop
    "ashape_lines": ("ashape_lines", "线条", True, False),
    "ashape_connectors": ("ashape_connectors", "连接符", True, False),
    "ashape_basic": ("ashape_basic", "基本形状", True, False),
    "ashape_arrows": ("ashape_arrows", "箭头总汇", True, False),
    "ashape_flowchart": ("ashape_flowchart", "流程图", True, False),
    "ashape_stars": ("ashape_stars", "星与旗帜", True, False),
    "ashape_callouts": ("ashape_callouts", "标注", True, False),
    # Drawing: Dash Style Drop
    "draw_dash_round_dot": ("draw_dash_round_dot", "圆点", True, False),
    "draw_dash_short_dash": ("draw_dash_short_dash", "短划线", True, False),
    "draw_dash_long_dash": ("draw_dash_long_dash", "长划线", True, False),
    "draw_dash_dash_dot": ("draw_dash_dash_dot", "点划线", True, False),
    # Drawing: Arrow Style Drop
    "draw_arrow_none": ("draw_arrow_none", "无箭头", True, False),
    "draw_arrow_style1": ("draw_arrow_style1", "箭头样式 1", True, False),
    "draw_arrow_style2": ("draw_arrow_style2", "箭头样式 2", True, False),
    "draw_arrow_double": ("draw_arrow_double", "双向箭头", True, False),
    # Drawing: Shadow Style Drop
    "draw_shadow_none": ("draw_shadow_none", "无阴影", True, False),
    "draw_shadow_style1": ("draw_shadow_style1", "阴影样式 1", True, False),
    "draw_shadow_style2": ("draw_shadow_style2", "阴影样式 2", True, False),
    "draw_shadow_style3": ("draw_shadow_style3", "阴影样式 3", True, False),
}

_LECTERN_LABEL_TO_AID: Final[dict[str, tuple[str, str, bool, bool]]] = {
    v[1]: v for v in _LECTERN_KNOWN_ITEM_AIDS.values()
}


class LecternToolBarCluster:
    """Builder for Lectern 10 toolbars cluster connected to ActionRegistry."""

    def __init__(self, window: QMainWindow, action_registry: ActionRegistry) -> None:
        self.window = window
        self.action_registry = action_registry
        self.toolbars: dict[str, OfficeToolBar] = {}

    def build_all(self) -> dict[str, OfficeToolBar]:
        """Build and register all 10 toolbars."""
        self.toolbars["standard"] = self._build_standard_toolbar()
        self.toolbars["formatting"] = self._build_formatting_toolbar()
        self.toolbars["sorter"] = self._build_sorter_toolbar()
        self.toolbars["master"] = self._build_master_toolbar()
        self.toolbars["outlining"] = self._build_outlining_toolbar()
        self.toolbars["diagram"] = self._build_diagram_toolbar()
        self.toolbars["tables"] = self._build_tables_toolbar()
        self.toolbars["picture"] = self._build_picture_toolbar()
        self.toolbars["wordart"] = self._build_wordart_toolbar()
        self.toolbars["drawing"] = self._build_drawing_toolbar()
        return self.toolbars

    def _reg_act(
        self,
        aid: str,
        label: str,
        tip: str = "",
        shortcut: Any = None,
        checkable: bool = False,
        checked: bool = False,
        enabled: bool = True,
        is_split: bool = False,
        is_drop: bool = False,
        handler: Callable[[], Any] | None = None,
        icon: QIcon | str | None = None,
    ) -> QAction:
        existing = self.action_registry.get_action(aid)
        if existing is not None:
            if checkable and not existing.isCheckable():
                existing.setCheckable(True)
            return existing

        resolved_icon = None
        if isinstance(icon, QIcon):
            resolved_icon = icon
        elif isinstance(icon, str) and has_office_icon(icon):
            resolved_icon = get_office_icon(icon)
        elif has_office_icon(aid):
            resolved_icon = get_office_icon(aid)

        spec = ActionSpec(
            id=aid,
            label=safe_tr(label),
            icon=resolved_icon,
            tip=safe_tr(tip) if tip else "",
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
            enabled=enabled,
            is_split=is_split,
            is_drop=is_drop,
            handler=handler,
        )
        return self.action_registry.register_action(spec, parent=self.window)

    def _add(
        self,
        tb: OfficeToolBar,
        aid: str,
        label: str,
        tip: str = "",
        shortcut: Any = None,
        checkable: bool = False,
        checked: bool = False,
        enabled: bool = True,
        is_split: bool = False,
        is_drop: bool = False,
        handler: Callable[[], Any] | None = None,
        icon: QIcon | str | None = None,
    ) -> QAction:
        act = self._reg_act(
            aid=aid,
            label=label,
            tip=tip,
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
            enabled=enabled,
            is_split=is_split,
            is_drop=is_drop,
            handler=handler,
            icon=icon,
        )
        tb.addAction(act)
        return act

    def _add_menu_item(
        self,
        menu: QMenu,
        item: Any,
        parent_aid: str | None = None,
    ) -> QAction | None:
        if item == "-":
            menu.addSeparator()
            return None

        aid = ""
        label = ""
        tip = ""
        enabled = True
        checkable = False
        checked = False
        handler = None
        icon = None

        if isinstance(item, QAction):
            menu.addAction(item)
            return item

        if isinstance(item, tuple):
            aid = item[0]
            label = item[1]
            if len(item) > 2:
                enabled = item[2]
            if len(item) > 3:
                checkable = item[3]
            if len(item) > 4:
                checked = item[4]
            if len(item) > 5:
                handler = item[5]
            if len(item) > 6:
                icon = item[6]
        elif isinstance(item, str):
            if self.action_registry.has_action(item):
                act = self.action_registry.get_action(item)
                if act:
                    menu.addAction(act)
                    return act
            if item in _LECTERN_KNOWN_ITEM_AIDS:
                aid, label, enabled, checkable = _LECTERN_KNOWN_ITEM_AIDS[item]
            elif item in _LECTERN_LABEL_TO_AID:
                aid, label, enabled, checkable = _LECTERN_LABEL_TO_AID[item]
            else:
                aid = f"{parent_aid}_{item}" if parent_aid else item
                label = item
        else:
            return None

        act = self._reg_act(
            aid=aid,
            label=label,
            tip=tip,
            enabled=enabled,
            checkable=checkable,
            checked=checked,
            handler=handler,
            icon=icon,
        )
        menu.addAction(act)
        return act

    def _add_drop(
        self,
        tb: OfficeToolBar,
        label: str,
        items: list[Any],
        icon: QIcon | str | None = None,
        aid: str | None = None,
    ) -> OfficeDropDownButton:
        menu = QMenu(tb)
        menu.setProperty("drop_label", label)
        plain_lbl = clean_asian_mnemonic(label)
        resolved_aid = (
            aid or _LECTERN_DROP_AIDS_MAP.get(label) or _LECTERN_DROP_AIDS_MAP.get(plain_lbl)
        )
        if resolved_aid:
            self._reg_act(
                aid=resolved_aid,
                label=label,
                is_drop=True,
                icon=icon,
            )
            menu.setProperty("drop_aid", resolved_aid)

        for item in items:
            self._add_menu_item(menu, item, parent_aid=resolved_aid)

        resolved_icon = None
        if isinstance(icon, QIcon):
            resolved_icon = icon
        elif isinstance(icon, str) and has_office_icon(icon):
            resolved_icon = get_office_icon(icon)
        elif not icon:
            drop_key = _LECTERN_DROP_ICONS.get(label)
            if drop_key and has_office_icon(drop_key):
                resolved_icon = get_office_icon(drop_key)

        keep_text = (
            "绘图" in label
            or "自选图形" in label
            or "Table" in label
            or "表格" in label
            or "版式" in label
            or "更改颜色" in label
            or "样式" in label
            or "艺术字" in label
        )
        btn_text = safe_tr(label) if not resolved_icon or keep_text else ""
        btn = tb.add_drop_button(btn_text, resolved_icon, menu, tooltip=label)
        if resolved_icon and not btn_text:
            btn.setToolTip(safe_tr(label))
        return btn

    def _add_split(
        self,
        tb: OfficeToolBar,
        aid: str,
        label: str,
        tip: str,
        items: list[Any],
        shortcut: Any = None,
        icon: QIcon | str | None = None,
    ) -> OfficeSplitButton:
        act = self._reg_act(
            aid=aid,
            label=label,
            tip=tip,
            shortcut=shortcut,
            is_split=True,
            icon=icon,
        )
        menu = QMenu(tb)
        menu.setProperty("split_aid", aid)
        for item in items:
            self._add_menu_item(menu, item, parent_aid=aid)
        return tb.add_split_action(act, menu)

    def _build_standard_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("常用"), self.window)

        self._add(tb, "new", "新建(&N)", "新建空白演示文稿 (Ctrl+N)", QKeySequence.StandardKey.New)
        self._add(tb, "open", "打开(&O)...", "打开演示文稿 (Ctrl+O)", QKeySequence.StandardKey.Open)
        self._add(tb, "save", "保存(&S)", "保存演示文稿 (Ctrl+S)", QKeySequence.StandardKey.Save)

        tb.add_office_separator()

        self._add(
            tb, "print", "打印(&P)...", "打印演示文稿 (Ctrl+P)", QKeySequence.StandardKey.Print
        )
        self._add(tb, "printPreview", "打印预览(&V)", "打印预览")
        self._add(tb, "spelling", "拼写检查(&S)...", "拼写检查 (F7)", "F7")

        tb.add_office_separator()

        self._add(tb, "cut", "剪切(&T)", "剪切 (Ctrl+X)", QKeySequence.StandardKey.Cut)
        self._add(tb, "copy", "复制(&C)", "复制 (Ctrl+C)", QKeySequence.StandardKey.Copy)
        self._add(tb, "paste", "粘贴(&P)", "粘贴 (Ctrl+V)", QKeySequence.StandardKey.Paste)
        self._add(tb, "formatPainter", "格式刷(&P)", "格式刷 (双击可连续应用)")

        tb.add_office_separator()

        self._add_split(
            tb, "undo", "撤销(&U)", "撤销 (Ctrl+Z)", ["无操作可撤销"], QKeySequence.StandardKey.Undo
        )
        self._add_split(
            tb, "redo", "重做(&R)", "重做 (Ctrl+Y)", ["无操作可重做"], QKeySequence.StandardKey.Redo
        )

        tb.add_office_separator()

        self._add(tb, "insertChart", "插入图表(&H)...", "插入统计图表")
        self._add(tb, "insertTable", "插入表格(&B)...", "插入表格")
        self._add(tb, "tb_tables", "表格和边框(&T)", "显示或隐藏表格和边框工具栏")
        self._add(tb, "hyperlink", "插入超链接(&I)...", "插入超链接 (Ctrl+K)", "Ctrl+K")

        tb.add_office_separator()

        self._add(tb, "expandAll", "全部展开(&E)", "在左侧大纲窗格中全部展开")
        self._add(tb, "showFormatting", "显示格式(&F)", "显示纯文本或格式化文本")
        self._add(tb, "showGrid", "网格和参考线(&G)", "显示或隐藏对齐网格与参考线", checkable=True)
        self._add_split(
            tb,
            "viewGray",
            "颜色/灰度(&C)",
            "切换彩色、灰度或纯黑白显示模式",
            [
                ("view_color", "彩色(&C)", True, True),
                ("view_grayscale", "灰度(&G)", True, True),
                ("view_black_and_white", "纯黑白(&B)", True, True),
            ],
        )

        zoom_combo = QComboBox(tb)
        zoom_combo.setObjectName("Lectern_ZoomCombo")
        zoom_combo.setEditable(True)
        zoom_combo.addItems(
            [
                safe_tr("适合比例"),
                "400%",
                "200%",
                "150%",
                "100%",
                "75%",
                "66%",
                "50%",
                "33%",
                "25%",
            ]
        )
        zoom_combo.setCurrentText(safe_tr("适合比例"))
        zoom_combo.setToolTip(safe_tr("显示比例"))
        tb.addWidget(zoom_combo)

        tb.add_office_separator()

        self._add(tb, "help", "帮助(&H)", "Microsoft PowerPoint 帮助 (F1)", "F1")

        return tb

    def _build_formatting_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("格式"), self.window)

        font_combo = QComboBox(tb)
        font_combo.setObjectName("Lectern_FontCombo")
        font_combo.setEditable(True)
        font_combo.addItems(
            [
                "Arial",
                "Calibri",
                "宋体",
                "黑体",
                "微软雅黑",
                "Times New Roman",
                "Courier New",
                "Verdana",
            ]
        )
        font_combo.setToolTip(safe_tr("字体"))
        tb.addWidget(font_combo)

        size_combo = QComboBox(tb)
        size_combo.setObjectName("Lectern_SizeCombo")
        size_combo.setEditable(True)
        size_combo.addItems(
            [
                "8",
                "9",
                "10",
                "11",
                "12",
                "14",
                "16",
                "18",
                "20",
                "24",
                "28",
                "32",
                "36",
                "44",
                "48",
                "54",
                "60",
                "66",
                "72",
                "80",
                "88",
                "96",
            ]
        )
        size_combo.setCurrentText("24")
        size_combo.setToolTip(safe_tr("字号"))
        tb.addWidget(size_combo)

        tb.add_office_separator()

        self._add(tb, "bold", "加粗(&B)", "加粗 (Ctrl+B)", "Ctrl+B", checkable=True)
        self._add(tb, "italic", "倾斜(&I)", "倾斜 (Ctrl+I)", "Ctrl+I", checkable=True)
        self._add(tb, "underline", "下划线(&U)", "下划线 (Ctrl+U)", "Ctrl+U", checkable=True)
        self._add(tb, "shadowText", "阴影(&S)", "文字阴影效果", checkable=True)

        tb.add_office_separator()

        self._add(tb, "alignLeft", "左对齐(&L)", "左对齐 (Ctrl+L)", "Ctrl+L", checkable=True)
        self._add(tb, "alignCenter", "居中(&E)", "居中 (Ctrl+E)", "Ctrl+E", checkable=True)
        self._add(tb, "alignRight", "右对齐(&R)", "右对齐 (Ctrl+R)", "Ctrl+R", checkable=True)

        tb.add_office_separator()

        self._add(tb, "numbering", "项目编号(&N)", "添加或清除编号列表", checkable=True)
        self._add(tb, "bullets", "项目符号(&B)", "添加或清除项目符号列表", checkable=True)

        tb.add_office_separator()

        self._add(tb, "growFont", "增大字号(&G)", "增大文本字号")
        self._add(tb, "shrinkFont", "减小字号(&K)", "减小文本字号")

        tb.add_office_separator()

        self._add(
            tb,
            "promote",
            "提升级别(&P)",
            "降低缩进量 / 提升级别 (Alt+Shift+Left)",
            "Alt+Shift+Left",
        )
        self._add(
            tb,
            "demote",
            "降低级别(&D)",
            "增加缩进量 / 降低级别 (Alt+Shift+Right)",
            "Alt+Shift+Right",
        )

        tb.add_office_separator()

        font_color_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
        font_color_btn.setObjectName("Lectern_FontColorBtn")
        font_color_btn.setToolTip(safe_tr("字体颜色"))
        font_color_btn.setStatusTip(safe_tr("更改文本字体颜色"))
        tb.addWidget(font_color_btn)

        tb.add_office_separator()

        self._add(tb, "slideDesign", "幻灯片设计(&D)", "打开幻灯片设计任务窗格")
        self._add(tb, "newSlide", "新幻灯片(&M)", "插入新幻灯片 (Ctrl+M)", "Ctrl+M")
        # Register aliases for standard action IDs
        self._reg_act("new_slide", "新幻灯片(&M)", "插入新幻灯片 (Ctrl+M)", "Ctrl+M")
        self._reg_act("start_slideshow", "放映幻灯片(&S)", "从首页开始放映 (F5)", "F5")
        self._reg_act(
            "start_slideshow_current",
            "从当前开始放映(&C)",
            "从当前幻灯片开始放映 (Shift+F5)",
            "Shift+F5",
        )
        self._reg_act("viewNormal", "普通视图(&N)", "切换为普通视图")
        self._reg_act("viewSorter", "幻灯片浏览(&D)", "切换为幻灯片浏览视图")
        self._reg_act("viewNotesPage", "备注页(&P)", "切换为备注页视图")
        self._reg_act("viewNotes", "备注页(&P)", "切换为备注页视图")
        self._reg_act("viewMaster", "幻灯片母版(&M)", "切换为幻灯片母版视图")

        return tb

    def _build_sorter_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("幻灯片浏览"), self.window)

        self._add(tb, "hideSlide", "隐藏幻灯片(&H)", "在放映中隐藏选定幻灯片", checkable=True)
        self._add(tb, "rehearse", "排练计时(&R)", "启动排练计时幻灯片放映")

        tb.add_office_separator()

        self._add(tb, "summarySlide", "摘要幻灯片(&S)", "根据选定幻灯片标题生成摘要幻灯片")
        self._add(tb, "speakerNotes", "演讲者备注(&N)", "编辑演讲者备注")

        tb.add_office_separator()

        self._add(tb, "transitionPane", "幻灯片切换(&T)...", "打开幻灯片切换任务窗格")
        self._add(tb, "sorter_slideDesign", "设计(&D)", "打开幻灯片设计任务窗格")
        self._add(tb, "sorter_newSlide", "新幻灯片(&M)", "插入新幻灯片")

        return tb

    def _build_master_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("母版视图"), self.window)

        self._add(tb, "insertSlideMaster", "插入幻灯片母版(&M)", "在演示文稿中插入新的幻灯片母版")
        self._add(tb, "insertTitleMaster", "插入标题母版(&T)", "插入新的标题母版")
        self._add(tb, "preserveMaster", "保留母版(&P)", "保留所选母版以防止其未被使用时被自动删除")
        self._add(tb, "renameMaster", "重命名母版(&R)...", "重命名所选母版")
        self._add(tb, "deleteTitleMaster", "删除母版(&D)", "删除所选母版")

        tb.add_office_separator()

        self._add(tb, "closeMaster", "关闭母版视图(&C)", "退出母版视图并返回普通视图")

        return tb

    def _build_outlining_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("大纲"), self.window)

        self._add(
            tb, "outline_promote", "提升(&P)", "提升大纲级别 (Alt+Shift+Left)", "Alt+Shift+Left"
        )
        self._add(
            tb, "outline_demote", "降低(&D)", "降低大纲级别 (Alt+Shift+Right)", "Alt+Shift+Right"
        )
        self._add(tb, "moveParaUp", "上移(&U)", "上移选定段落 (Alt+Shift+Up)", "Alt+Shift+Up")
        self._add(tb, "moveParaDown", "下移(&O)", "下移选定段落 (Alt+Shift+Down)", "Alt+Shift+Down")

        tb.add_office_separator()

        self._add(tb, "outline_summarySlide", "摘要幻灯片(&S)", "生成摘要幻灯片")
        self._add(
            tb,
            "outline_showFormatting",
            "显示格式(&F)",
            "在大纲视图中显示或隐藏文本格式",
            checkable=True,
        )

        return tb

    def _build_diagram_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("关系图"), self.window)

        add_menu = QMenu(tb)
        act_add_after = self._reg_act(
            "diagramAddAfter", "在后面添加形状(&A)", "在所选元素后添加形状"
        )
        act_add_before = self._reg_act(
            "diagramAddBefore", "在前面添加形状(&B)", "在所选元素前添加形状"
        )
        act_add_above = self._reg_act(
            "diagramAddAbove", "在上方添加形状(&O)", "在所选元素上方添加形状"
        )
        act_add_below = self._reg_act(
            "diagramAddBelow", "在下方添加形状(&E)", "在所选元素下方添加形状"
        )
        add_menu.addAction(act_add_after)
        add_menu.addAction(act_add_before)
        add_menu.addAction(act_add_above)
        add_menu.addAction(act_add_below)

        act_main = self._reg_act(
            "diagramAddShape",
            "添加形状(&A)",
            "在所选关系图元素周围添加新形状",
            is_split=True,
        )
        tb.add_split_action(act_main, add_menu)

        self._add(tb, "diagramPromote", "升级(&P)", "提升所选图示元素层级")
        self._add(tb, "diagramDemote", "降级(&D)", "降低所选图示元素层级")
        self._add(tb, "diagramMoveUp", "上移(&U)", "在同层级中向前移动")
        self._add(tb, "diagramMoveDown", "下移(&W)", "在同层级中向后移动")

        tb.add_office_separator()

        self._add_drop(
            tb,
            "版式(&L)",
            ["组织结构图", "层次结构", "循环图", "射线图", "金字塔图", "维恩图", "目标图"],
        )
        self._add_drop(tb, "更改颜色(&C)", ["主色调", "多彩", "深色", "轻快"])
        self._add_drop(tb, "样式(&S)", ["平面样式", "3D 凸起", "金属质感", "渐变填充"])

        tb.add_office_separator()

        self._add(
            tb,
            "diagramTextPane",
            "文本窗格(&T)",
            "显示或隐藏 IntelliArt 文本大纲窗格",
            checkable=True,
        )
        self._add(tb, "diagramReset", "重设图形(&R)", "撤销格式修改并重置默认样式")
        self._add(
            tb, "diagramToShapes", "转换为形状(&S)", "将 IntelliArt 关系图解散为标准独立自选图形"
        )

        return tb

    def _build_tables_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("表格和边框"), self.window)

        self._add_drop(tb, "线型", ["实线", "虚线", "点线", "双线"], aid="tbl_dash_style")
        self._add_drop(
            tb,
            "粗细",
            [
                ("tbl_weight_05", "0.5 磅", True, False),
                ("tbl_weight_10", "1.0 磅", True, False),
                ("tbl_weight_15", "1.5 磅", True, False),
                ("tbl_weight_225", "2.25 磅", True, False),
                ("tbl_weight_30", "3.0 磅", True, False),
                ("tbl_weight_45", "4.5 磅", True, False),
                ("tbl_weight_60", "6.0 磅", True, False),
            ],
            aid="tbl_line_weight",
        )
        self._add_drop(tb, "线条颜色", ["自动", "黑色", "红色", "蓝色", "灰色"])
        self._add_split(
            tb,
            "tableBordersAll",
            "边框(&B)",
            "应用表格边框样式",
            [
                "所有框线",
                "外侧框线",
                "内侧框线",
                "无框线",
                "顶端框线",
                "底端框线",
                "左侧框线",
                "右侧框线",
            ],
        )
        self._add_drop(tb, "底纹颜色", ["无填充", "浅灰色", "黄色", "浅蓝色", "浅绿色"])

        tb.add_office_separator()

        self._add_drop(
            tb,
            "表格(&T)",
            [
                "插入表格(&I)...",
                "-",
                "在左侧插入列",
                "在右侧插入列",
                "在上方插入行",
                "在下方插入行",
                "-",
                "删除列(&C)",
                "删除行(&R)",
                "-",
                "合并单元格(&M)",
                "拆分单元格(&P)...",
                "-",
                "选择表格(&S)",
                "-",
                "边框和底纹(&B)...",
            ],
        )

        self._add(tb, "tableMergeCells", "合并单元格(&M)", "合并所选单元格")
        self._add(tb, "tableSplitCell", "拆分单元格(&P)...", "拆分单元格")

        tb.add_office_separator()

        self._add(tb, "cellTop", "顶端对齐(&T)", "单元格文本靠上对齐")
        self._add(tb, "cellMiddle", "居中对齐(&C)", "单元格文本垂直居中")
        self._add(tb, "cellBottom", "底端对齐(&B)", "单元格文本靠下对齐")

        tb.add_office_separator()

        self._add(tb, "distRows", "平均分布各行(&R)", "使所选行具有相同的高度")
        self._add(tb, "distCols", "平均分布各列(&O)", "使所选列具有相同的宽度")

        return tb

    def _build_picture_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("图片"), self.window)

        self._add(tb, "pic_insert", "插入图片(&I)...", "从磁盘文件插入图片")
        self._add_drop(tb, "颜色(&C)", ["自动(&A)", "灰度(&G)", "黑白(&B)", "冲蚀(&W)"])

        self._add(tb, "picMoreContrast", "增加对比度(&M)", "增加图片对比度")
        self._add(tb, "picLessContrast", "降低对比度(&L)", "降低图片对比度")
        self._add(tb, "picMoreBright", "增加亮度(&B)", "增加图片亮度")
        self._add(tb, "picLessBright", "降低亮度(&D)", "降低图片亮度")

        tb.add_office_separator()

        self._add(tb, "picCrop", "裁剪(&C)", "裁剪图片尺寸与显示区域", checkable=True)
        self._add(tb, "rotateLeft", "向左旋转 90°(&R)", "将图片逆时针旋转 90 度")
        self._add_drop(
            tb,
            "线条样式",
            [
                ("pic_weight_075", "0.75 磅", True, False),
                ("pic_weight_15", "1.5 磅", True, False),
                ("pic_weight_30", "3 磅", True, False),
                ("pic_weight_45", "4.5 磅", True, False),
                ("pic_weight_60", "6 磅", True, False),
            ],
            aid="pic_line_style",
        )

        tb.add_office_separator()

        self._add(tb, "formatObject", "设置图片格式(&O)...", "打开图片格式与尺寸属性对话框")
        self._add(tb, "picTransparent", "设置透明色(&T)", "拾取图片特定像素并将其设为透明")
        self._add(tb, "picReset", "重设图片(&P)", "恢复图片的原始尺寸和色彩效果")

        return tb

    def _build_wordart_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("艺术字"), self.window)

        self._add(tb, "wa_insert", "插入艺术字(&W)...", "创建新的艺术字对象")
        self._add(tb, "wordartEdit", "编辑文字(&E)...", "修改艺术字文本内容及字体")
        self._add(tb, "wordartGallery", "艺术字库(&G)...", "打开艺术字预设样式库")
        self._add(tb, "wa_format", "设置艺术字格式(&O)...", "设置艺术字填充、线条与三维效果")

        tb.add_office_separator()

        self._add_drop(tb, "艺术字形状(&S)", ["纯文本", "波浪", "上凸", "下凹", "环形", "倒三角形"])
        self._add(
            tb,
            "waSameHeight",
            "艺术字同样高度(&H)",
            "使所选艺术字大小写字母具有相同高度",
            checkable=True,
        )
        self._add(
            tb, "waVertical", "艺术字垂直文字(&V)", "将艺术字排列方向切换为纵向排版", checkable=True
        )

        tb.add_office_separator()

        self._add_drop(
            tb, "艺术字对齐(&A)", ["左对齐(&L)", "居中(&C)", "右对齐(&R)", "两端对齐(&J)"]
        )
        self._add_drop(
            tb, "字符间距(&P)", ["很紧(&V)", "紧密(&T)", "常规(&N)", "稀疏(&L)", "很松(&E)"]
        )

        return tb

    def _build_drawing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("绘图"), self.window)

        draw_menu = QMenu(tb)
        act_front = self._reg_act("bringFront", "置于顶层(&F)", "将选定对象置于顶层")
        act_back = self._reg_act("sendBack", "置于底层(&B)", "将选定对象置于底层")
        act_forward = self._reg_act("bringForward", "上移一层(&U)", "将选定对象向前移动一层")
        act_backward = self._reg_act("sendBackward", "下移一层(&D)", "将选定对象向后移动一层")
        draw_menu.addAction(act_front)
        draw_menu.addAction(act_back)
        draw_menu.addAction(act_forward)
        draw_menu.addAction(act_backward)
        draw_menu.addSeparator()

        act_grp = self._reg_act(
            "group",
            "组合(&G)",
            "将多个选定对象组合为一个整体 (Ctrl+G)",
            "Ctrl+G",
        )
        act_ungrp = self._reg_act(
            "ungroup",
            "取消组合(&U)",
            "解散选定组合对象 (Ctrl+Shift+G)",
            "Ctrl+Shift+G",
        )
        act_regrp = self._reg_act("regroup", "重新组合(&R)", "重新组合最近解散的对象")
        draw_menu.addAction(act_grp)
        draw_menu.addAction(act_ungrp)
        draw_menu.addAction(act_regrp)
        draw_menu.addSeparator()

        align_sub = draw_menu.addMenu(safe_tr("对齐或分布(&A)"))
        act_al = self._reg_act("alignLeft", "左对齐(&L)", "将选定对象靠左对齐")
        act_ac = self._reg_act("alignCenter", "水平居中(&C)", "将选定对象水平居中")
        act_ar = self._reg_act("alignRight", "右对齐(&R)", "将选定对象靠右对齐")
        align_sub.addAction(act_al)
        align_sub.addAction(act_ac)
        align_sub.addAction(act_ar)
        align_sub.addSeparator()
        act_at = self._reg_act("alignTop", "顶端对齐(&T)", "将选定对象顶端对齐")
        act_am = self._reg_act("alignMiddle", "垂直居中(&M)", "将选定对象垂直居中")
        act_ab = self._reg_act("alignBottom", "底端对齐(&B)", "将选定对象底端对齐")
        align_sub.addAction(act_at)
        align_sub.addAction(act_am)
        align_sub.addAction(act_ab)
        align_sub.addSeparator()
        act_dh = self._reg_act("distributeH", "横向分布(&H)", "将选定对象水平等间距分布")
        act_dv = self._reg_act("distributeV", "纵向分布(&V)", "将选定对象垂直等间距分布")
        align_sub.addAction(act_dh)
        align_sub.addAction(act_dv)

        self._reg_act(
            aid="draw_menu",
            label="绘图(&R)",
            tip=safe_tr("绘图菜单"),
            is_drop=True,
        )
        draw_menu.setProperty("drop_aid", "draw_menu")
        draw_menu.setProperty("drop_label", "绘图(&R)")
        tb.add_drop_button(safe_tr("绘图(&R)"), None, draw_menu)
        self._add(tb, "selectObjects", "选择对象(&S)", "框选画布中的图形对象", checkable=True)

        tb.add_office_separator()

        self._add_drop(
            tb,
            "自选图形(&U)",
            ["线条", "连接符", "基本形状", "箭头总汇", "流程图", "星与旗帜", "标注"],
        )

        self._add(tb, "drawLine", "线条(&L)", "自由绘制直线段", checkable=True)
        self._add(tb, "drawArrow", "箭头(&A)", "绘制单向箭头线", checkable=True)
        self._add(tb, "drawRect", "矩形(&R)", "绘制矩形几何图形", checkable=True)
        self._add(tb, "drawOval", "椭圆(&O)", "绘制椭圆或正圆形", checkable=True)
        self._add(tb, "textBox", "文本框(&T)", "在幻灯片中绘制横向文本框", checkable=True)
        self._add(tb, "draw_insertWordArt", "插入艺术字(&W)...", "插入艺术字")
        self._add(tb, "draw_insertDiagram", "插入图示(&D)...", "插入组织结构图或循环图")
        self._add(tb, "insertClipArt", "剪贴画(&C)...", "从剪贴画库中插入素材")
        self._add(tb, "draw_insertPicture", "来自文件的图片(&P)...", "从磁盘文件插入图片")

        tb.add_office_separator()

        draw_fill_btn = ColorPickerButton(mode="fill", default_color="#FFFF00", parent=tb)
        draw_fill_btn.setObjectName("Lectern_DrawFillColor")
        draw_fill_btn.setToolTip(safe_tr("填充颜色"))
        draw_fill_btn.setStatusTip(safe_tr("更改选定图形的填充背景颜色"))
        tb.addWidget(draw_fill_btn)

        draw_line_btn = ColorPickerButton(mode="line", default_color="#000000", parent=tb)
        draw_line_btn.setObjectName("Lectern_DrawLineColor")
        draw_line_btn.setToolTip(safe_tr("线条颜色"))
        draw_line_btn.setStatusTip(safe_tr("更改选定形状的轮廓边框颜色"))
        tb.addWidget(draw_line_btn)

        draw_font_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
        draw_font_btn.setObjectName("Lectern_DrawFontColor")
        draw_font_btn.setToolTip(safe_tr("字体颜色"))
        draw_font_btn.setStatusTip(safe_tr("更改文本字体颜色"))
        tb.addWidget(draw_font_btn)

        tb.add_office_separator()

        self._add_drop(tb, "线型", ["0.75 磅", "1.5 磅", "3 磅", "4.5 磅", "6 磅"], aid="lineStyle")
        self._add_drop(tb, "虚线线型", ["实线", "圆点", "短划线", "长划线", "点划线"])
        self._add_drop(tb, "箭头样式", ["无箭头", "箭头样式 1", "箭头样式 2", "双向箭头"])
        self._add_drop(tb, "阴影样式", ["无阴影", "阴影样式 1", "阴影样式 2", "阴影样式 3"])

        return tb


def build_lectern_toolbars(
    window: QMainWindow,
    action_registry: ActionRegistry,
) -> dict[str, OfficeToolBar]:
    """Factory creating all 10 Lectern toolbars and binding to ActionRegistry."""
    cluster = LecternToolBarCluster(window, action_registry)
    return cluster.build_all()


def retranslate_lectern_toolbars(
    toolbars: dict[str, OfficeToolBar],
    tr_func: Callable[[str], str] | None = None,
) -> None:
    """Update localized window titles, drop buttons, and combos across all 10 toolbars."""
    translate = tr_func or safe_tr
    titles: dict[str, str] = {
        "standard": translate("常用"),
        "formatting": translate("格式"),
        "sorter": translate("幻灯片浏览"),
        "master": translate("母版视图"),
        "outlining": translate("大纲"),
        "diagram": translate("关系图"),
        "tables": translate("表格和边框"),
        "picture": translate("图片"),
        "wordart": translate("艺术字"),
        "drawing": translate("绘图"),
    }
    for name, title in titles.items():
        tb = toolbars.get(name)
        if tb is not None:
            tb.setWindowTitle(title)
            for btn in tb.findChildren(OfficeDropDownButton):
                btn.retranslate_ui(translate)
            for btn in tb.findChildren(OfficeSplitButton):
                btn.retranslate_ui(translate)
            for btn in tb.findChildren(ColorPickerButton):
                btn.retranslate_ui(translate)

            zoom_combo = tb.findChild(QComboBox, "Lectern_ZoomCombo")
            if zoom_combo:
                zoom_combo.setToolTip(translate("显示比例"))
                if zoom_combo.count() > 0:
                    zoom_combo.setItemText(0, translate("适合比例"))

            font_combo = tb.findChild(QComboBox, "Lectern_FontCombo")
            if font_combo:
                font_combo.setToolTip(translate("字体"))

            size_combo = tb.findChild(QComboBox, "Lectern_SizeCombo")
            if size_combo:
                size_combo.setToolTip(translate("字号"))
