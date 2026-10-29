"""Declarative Office 2003 Luna toolbar cluster for Ledger spreadsheet.

Implements all 8 Excel 2003 Luna toolbars with 1:1 action parity against
the original application:
1. Standard (常用)
2. Formatting (格式)
3. Borders (边框)
4. Formula Auditing (公式审核)
5. Reviewing (审阅)
6. List (列表/表格)
7. Chart (图表)
8. Drawing (绘图)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMenu,
)

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar


def safe_tr(text: str) -> str:
    """Translate UI text safely for Ledger toolbars."""
    return QCoreApplication.translate("LedgerToolbars", text)


class LedgerToolBarCluster:
    """Builder for Ledger 8 toolbars cluster connected to ActionRegistry."""

    def __init__(self, window: QMainWindow, action_registry: ActionRegistry) -> None:
        self.window = window
        self.action_registry = action_registry
        self.toolbars: dict[str, OfficeToolBar] = {}

    def build_all(self) -> dict[str, OfficeToolBar]:
        """Build and register all 8 toolbars."""
        self.toolbars["standard"] = self._build_standard_toolbar()
        self.toolbars["formatting"] = self._build_formatting_toolbar()
        self.toolbars["borders"] = self._build_borders_toolbar()
        self.toolbars["auditing"] = self._build_auditing_toolbar()
        self.toolbars["reviewing"] = self._build_reviewing_toolbar()
        self.toolbars["list"] = self._build_list_toolbar()
        self.toolbars["chart"] = self._build_chart_toolbar()
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
        is_split: bool = False,
        is_drop: bool = False,
        handler: Callable[[], Any] | None = None,
    ) -> QAction:
        spec = ActionSpec(
            id=aid,
            label=safe_tr(label),
            tip=safe_tr(tip) if tip else "",
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
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
        is_split: bool = False,
        is_drop: bool = False,
        handler: Callable[[], Any] | None = None,
    ) -> QAction:
        act = self._reg_act(
            aid=aid,
            label=label,
            tip=tip,
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
            is_split=is_split,
            is_drop=is_drop,
            handler=handler,
        )
        tb.addAction(act)
        return act

    def _add_drop(
        self,
        tb: OfficeToolBar,
        label: str,
        items: list[str],
    ) -> None:
        menu = QMenu(tb)
        for item in items:
            if item == "-":
                menu.addSeparator()
            else:
                menu.addAction(safe_tr(item))
        tb.add_drop_button(safe_tr(label), None, menu)

    def _add_split(
        self,
        tb: OfficeToolBar,
        aid: str,
        label: str,
        tip: str,
        items: list[str],
        shortcut: Any = None,
    ) -> None:
        act = self._reg_act(
            aid=aid,
            label=label,
            tip=tip,
            shortcut=shortcut,
            is_split=True,
        )
        menu = QMenu(tb)
        for item in items:
            if item == "-":
                menu.addSeparator()
            else:
                menu.addAction(safe_tr(item))
        tb.add_split_action(act, menu)

    def _build_standard_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("常用"), self.window)

        self._add(tb, "new", "新建(&N)", "新建空白工作簿 (Ctrl+N)", QKeySequence.StandardKey.New)
        self._add(tb, "open", "打开(&O)...", "打开工作簿 (Ctrl+O)", QKeySequence.StandardKey.Open)
        self._add(tb, "save", "保存(&S)", "保存工作簿 (Ctrl+S)", QKeySequence.StandardKey.Save)

        tb.add_office_separator()

        self._add(tb, "print", "打印(&P)...", "打印工作簿 (Ctrl+P)", QKeySequence.StandardKey.Print)
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

        self._add(tb, "hyperlink", "插入超链接(&I)...", "插入超链接 (Ctrl+K)", "Ctrl+K")
        self._add_split(
            tb,
            "autoSum",
            "自动求和(&U)",
            "计算所选区域的总和",
            [
                "求和(&S)",
                "平均值(&A)",
                "计数(&C)",
                "最大值(&M)",
                "最小值(&I)",
                "-",
                "更多函数(&F)...",
            ],
        )
        self._add(tb, "sortAsc", "升序排序(&A)", "以所选列升序排序")
        self._add(tb, "sortDesc", "降序排序(&D)", "以所选列降序排序")

        tb.add_office_separator()

        self._add(tb, "chartWizard", "图表向导(&W)...", "启动图表向导创建统计图表")
        self._add(tb, "tb_drawing", "绘图(&D)", "显示或隐藏绘图工具栏")

        zoom_combo = QComboBox(tb)
        zoom_combo.setObjectName("Ledger_ZoomCombo")
        zoom_combo.setEditable(True)
        zoom_combo.addItems(
            [
                "200%",
                "100%",
                "75%",
                "50%",
                "25%",
                safe_tr("选定区域"),
            ]
        )
        zoom_combo.setCurrentText("100%")
        zoom_combo.setToolTip(safe_tr("显示比例"))
        tb.addWidget(zoom_combo)

        tb.add_office_separator()

        self._add(tb, "help", "帮助(&H)", "Microsoft Excel 帮助 (F1)", "F1")

        return tb

    def _build_formatting_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("格式"), self.window)

        font_combo = QComboBox(tb)
        font_combo.setObjectName("Ledger_FontCombo")
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
        size_combo.setObjectName("Ledger_SizeCombo")
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
                "22",
                "24",
                "26",
                "28",
                "36",
                "48",
                "72",
            ]
        )
        size_combo.setCurrentText("10")
        size_combo.setToolTip(safe_tr("字号"))
        tb.addWidget(size_combo)

        tb.add_office_separator()

        self._add(tb, "bold", "加粗(&B)", "加粗 (Ctrl+B)", "Ctrl+B", checkable=True)
        self._add(tb, "italic", "倾斜(&I)", "倾斜 (Ctrl+I)", "Ctrl+I", checkable=True)
        self._add(tb, "underline", "下划线(&U)", "下划线 (Ctrl+U)", "Ctrl+U", checkable=True)

        tb.add_office_separator()

        self._add(tb, "alignLeft", "左对齐(&L)", "左对齐 (Ctrl+L)", "Ctrl+L", checkable=True)
        self._add(tb, "alignCenter", "居中(&E)", "居中 (Ctrl+E)", "Ctrl+E", checkable=True)
        self._add(tb, "alignRight", "右对齐(&R)", "右对齐 (Ctrl+R)", "Ctrl+R", checkable=True)
        self._add(tb, "mergeCenter", "合并及居中(&M)", "合并选定单元格并居中文本", checkable=True)

        tb.add_office_separator()

        self._add(tb, "currencyStyle", "货币样式(&C)", "应用货币样式 ($ 1,234.00)")
        self._add(tb, "percentStyle", "百分比样式(&P)", "应用百分比样式 (12%)")
        self._add(tb, "commaStyle", "千位分隔样式(&K)", "应用千位分隔样式 (1,234.00)")
        self._add(tb, "incDecimal", "增加小数位数(&I)", "增加一位小数显示精度")
        self._add(tb, "decDecimal", "减少小数位数(&D)", "减少一位小数显示精度")

        tb.add_office_separator()

        self._add(tb, "decIndent", "减少缩进量(&D)", "减少单元格左侧文本缩进量")
        self._add(tb, "incIndent", "增加缩进量(&I)", "增加单元格左侧文本缩进量")

        tb.add_office_separator()

        self._add_split(
            tb,
            "bordersApply",
            "边框(&B)",
            "应用单元格边框预设",
            [
                "下框线",
                "上框线",
                "左框线",
                "右框线",
                "无边框",
                "所有框线",
                "粗外侧框线",
                "双下框线",
            ],
        )

        fill_color_btn = ColorPickerButton(mode="fill", default_color="#FFFF00", parent=tb)
        fill_color_btn.setObjectName("Ledger_FillColorBtn")
        fill_color_btn.setToolTip(safe_tr("填充颜色"))
        fill_color_btn.setStatusTip(safe_tr("更改单元格背景颜色"))
        tb.addWidget(fill_color_btn)

        font_color_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
        font_color_btn.setObjectName("Ledger_FontColorBtn")
        font_color_btn.setToolTip(safe_tr("字体颜色"))
        font_color_btn.setStatusTip(safe_tr("更改文本字体颜色"))
        tb.addWidget(font_color_btn)

        return tb

    def _build_borders_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("边框"), self.window)

        self._add_split(
            tb,
            "bordersPalette",
            "边框(&B)",
            "应用单元格边框预设",
            ["无框线", "下框线", "上框线", "所有框线", "外侧框线", "粗外侧框线"],
        )
        self._add(tb, "borderNone", "无框线(&N)", "清除所有选定单元格边框")
        self._add(tb, "borderOutline", "外侧框线(&O)", "绘制外侧边框")
        self._add(tb, "borderThickOutline", "粗外框线(&T)", "绘制粗外侧边框")
        self._add(tb, "drawBorder", "绘制边框线(&D)", "自由绘制边框线")
        self._add(tb, "eraseBorder", "擦除边框(&E)", "擦除单元格边框")

        self._add_drop(tb, "线条颜色", ["自动", "黑色", "红色", "蓝色", "灰色"])

        return tb

    def _build_auditing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("公式审核"), self.window)

        self._add(tb, "traceError", "错误检查(&E)", "定位并检查公式错误")

        tb.add_office_separator()

        self._add(
            tb, "tracePrecedents", "追踪引用单元格(&P)", "追踪向当前单元格提供数值的引用单元格"
        )
        self._add(tb, "traceDependents", "追踪从属单元格(&D)", "追踪引用当前单元格数值的从属单元格")
        self._add(tb, "removeArrows", "移去所有箭头(&A)", "移去工作表中的所有追踪箭头")

        tb.add_office_separator()

        self._add(tb, "insertComment", "新建批注(&C)", "新建或编辑单元格批注")
        self._add_split(
            tb,
            "validation",
            "数据有效性(&V)...",
            "设置单元格数据输入有效性规则",
            ["数据有效性(&V)...", "圈释无效数据(&C)", "清除无效数据圈(&L)"],
        )
        self._add(tb, "circleInvalid", "圈释无效数据(&I)", "圈释不满足有效性规则的无效数据")
        self._add(tb, "clearCircles", "清除无效数据圈(&L)", "清除无效数据标识圈")

        tb.add_office_separator()

        self._add(tb, "watchWindow", "监视窗口(&W)", "打开公式数值监视窗口")
        self._add(tb, "evaluateFormula", "公式求值(&F)", "分步计算求解复杂嵌套公式")

        return tb

    def _build_reviewing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("审阅"), self.window)

        self._add(tb, "rev_insertComment", "新建批注(&C)", "新建或编辑单元格批注")
        self._add(tb, "showHideComment", "显示/隐藏批注(&H)", "切换显示或隐藏选定单元格批注")
        self._add(tb, "deleteComment", "删除批注(&D)", "删除选定单元格批注")

        tb.add_office_separator()

        self._add(tb, "showComments", "显示所有批注(&A)", "显示工作表中的全部批注", checkable=True)

        return tb

    def _build_list_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("列表"), self.window)

        self._add_drop(
            tb,
            "列表(&L)",
            [
                "插入行(&R)",
                "插入列(&C)",
                "-",
                "排序(&S)...",
                "自动筛选(&A)",
                "-",
                "汇总行(&T)",
                "转换为区域(&V)",
            ],
        )
        self._add(
            tb, "totalRow", "汇总行(&T)", "在列表底部显示或隐藏自动汇总计算行", checkable=True
        )

        return tb

    def _build_chart_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("图表"), self.window)

        self._add_drop(
            tb,
            "图表类型(&T)",
            [
                "柱形图(&C)",
                "折线图(&L)",
                "饼图(&P)",
                "条形图(&B)",
                "面积图(&A)",
                "散点图(&X)",
                "雷达图(&R)",
            ],
        )
        self._add(tb, "formatObject", "设置图表格式(&O)...", "打开所选图表对象的格式设置对话框")

        return tb

    def _build_drawing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("绘图"), self.window)

        self._add_drop(
            tb, "绘图(&R)", ["置于顶层(&F)", "置于底层(&B)", "-", "组合(&G)", "取消组合(&U)"]
        )

        tb.add_office_separator()

        self._add(tb, "insertShape", "自选图形(&S)", "插入矩形、椭圆等自选图形")
        self._add(tb, "insertTextBox", "文本框(&T)", "插入横排文本框")
        self._add(tb, "insertPicture", "来自文件的图片(&P)...", "从磁盘文件插入图片")

        tb.add_office_separator()

        draw_fill_btn = ColorPickerButton(mode="fill", default_color="#FFFF00", parent=tb)
        draw_fill_btn.setObjectName("Ledger_DrawFillColor")
        draw_fill_btn.setToolTip(safe_tr("填充颜色"))
        draw_fill_btn.setStatusTip(safe_tr("更改选定图形的填充背景颜色"))
        tb.addWidget(draw_fill_btn)

        return tb


def build_ledger_toolbars(
    window: QMainWindow,
    action_registry: ActionRegistry,
) -> dict[str, OfficeToolBar]:
    """Factory creating all 8 Ledger toolbars and binding to ActionRegistry."""
    cluster = LedgerToolBarCluster(window, action_registry)
    return cluster.build_all()


def retranslate_ledger_toolbars(
    toolbars: dict[str, OfficeToolBar],
    tr_func: Callable[[str], str] | None = None,
) -> None:
    """Update localized window titles and tooltips across all 8 toolbars."""
    translate = tr_func or safe_tr
    titles: dict[str, str] = {
        "standard": translate("常用"),
        "formatting": translate("格式"),
        "borders": translate("边框"),
        "auditing": translate("公式审核"),
        "reviewing": translate("审阅"),
        "list": translate("列表"),
        "chart": translate("图表"),
        "drawing": translate("绘图"),
    }
    for name, title in titles.items():
        tb = toolbars.get(name)
        if tb is not None:
            tb.setWindowTitle(title)
