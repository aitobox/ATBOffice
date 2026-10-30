"""Declarative Office 2003 Luna toolbar cluster for Quire word processor.

Implements all 10 Word 2003 Luna toolbars with 1:1 action parity against
the original application:
1. Standard (常用)
2. Formatting (格式)
3. Tables and Borders (表格和边框)
4. Reviewing (审阅)
5. Outlining (大纲)
6. Header and Footer (页眉和页脚)
7. Drawing (绘图)
8. Mail Merge (邮件合并)
9. Picture (图片)
10. WordArt (艺术字)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMenu,
)

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.core.i18n import safe_tr as core_safe_tr
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar


def safe_tr(text: str) -> str:
    """Translate UI text safely for Quire toolbars."""
    return core_safe_tr(text)


class QuireToolBarCluster:
    """Builder for Quire 10 toolbars cluster connected to ActionRegistry."""

    def __init__(self, window: QMainWindow, action_registry: ActionRegistry) -> None:
        self.window = window
        self.action_registry = action_registry
        self.toolbars: dict[str, OfficeToolBar] = {}

    def build_all(self) -> dict[str, OfficeToolBar]:
        """Build and register all 10 toolbars."""
        self.toolbars["standard"] = self._build_standard_toolbar()
        self.toolbars["formatting"] = self._build_formatting_toolbar()
        self.toolbars["tables"] = self._build_tables_toolbar()
        self.toolbars["reviewing"] = self._build_reviewing_toolbar()
        self.toolbars["outlining"] = self._build_outlining_toolbar()
        self.toolbars["headerFooter"] = self._build_header_footer_toolbar()
        self.toolbars["drawing"] = self._build_drawing_toolbar()
        self.toolbars["mailMerge"] = self._build_mail_merge_toolbar()
        self.toolbars["picture"] = self._build_picture_toolbar()
        self.toolbars["wordart"] = self._build_wordart_toolbar()
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
            menu.addAction(safe_tr(item))
        tb.add_split_action(act, menu)

    def _build_standard_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("常用"), self.window)

        self._add(tb, "new", "新建(&N)", "新建空白文档 (Ctrl+N)", QKeySequence.StandardKey.New)
        self._add(tb, "open", "打开(&O)...", "打开文档 (Ctrl+O)", QKeySequence.StandardKey.Open)
        self._add(tb, "save", "保存(&S)", "保存文档 (Ctrl+S)", QKeySequence.StandardKey.Save)
        self._add(tb, "permission", "权限(&M)", "权限设置 (只读/编辑)")
        self._add(tb, "sendMail", "发送(&E)", "通过电子邮件发送")
        self._add(tb, "print", "打印(&P)...", "打印文档 (Ctrl+P)", QKeySequence.StandardKey.Print)
        self._add(tb, "printPreview", "打印预览(&V)", "打印预览")
        self._add(tb, "spelling", "拼写和语法(&S)...", "拼写和语法检查 (F7)", "F7")
        self._add(tb, "research", "信息检索(&R)...", "信息检索与翻译 (Alt+Click)")

        tb.add_office_separator()

        self._add(tb, "cut", "剪切(&T)", "剪切 (Ctrl+X)", QKeySequence.StandardKey.Cut)
        self._add(tb, "copy", "复制(&C)", "复制 (Ctrl+C)", QKeySequence.StandardKey.Copy)
        self._add(tb, "paste", "粘贴(&P)", "粘贴 (Ctrl+V)", QKeySequence.StandardKey.Paste)
        self._add(tb, "painter", "格式刷(&P)", "格式刷 (双击可连续应用)")

        tb.add_office_separator()

        self._add_split(
            tb, "undo", "撤销(&U)", "撤销 (Ctrl+Z)", ["无操作可撤销"], QKeySequence.StandardKey.Undo
        )
        self._add_split(
            tb, "redo", "重做(&R)", "重做 (Ctrl+Y)", ["无操作可重做"], QKeySequence.StandardKey.Redo
        )

        tb.add_office_separator()

        self._add(tb, "hyperlink", "插入超链接(&I)...", "插入超链接 (Ctrl+K)", "Ctrl+K")
        self._add(tb, "tb_tables", "表格和边框(&B)", "显示或隐藏表格和边框工具栏")
        self._add_drop(
            tb, "插入表格", ["插入表格(&I)...", "插入列在左侧", "插入行在上方"]
        )
        self._add(tb, "insertExcel", "插入 Excel 工作表(&E)", "插入 Microsoft Excel 工作表")
        self._add_drop(tb, "分栏", ["一栏", "两栏", "三栏", "偏左", "偏右"])
        self._add(tb, "tb_drawing", "绘图(&D)", "显示或隐藏绘图工具栏")
        self._add(tb, "docMap", "文档结构图(&D)", "显示或隐藏文档结构图", checkable=True)
        self._add(
            tb, "showMarks", "显示/隐藏编辑标记(&S)", "显示或隐藏段落标记与格式", checkable=True
        )

        zoom_combo = QComboBox(tb)
        zoom_combo.setObjectName("Quire_ZoomCombo")
        zoom_combo.setEditable(True)
        zoom_combo.addItems([
            "500%", "200%", "150%", "100%", "75%", "50%", "25%",
            safe_tr("页宽"), safe_tr("整页"),
        ])
        zoom_combo.setCurrentText("100%")
        zoom_combo.setToolTip(safe_tr("显示比例"))
        tb.addWidget(zoom_combo)

        self._add(tb, "help", "帮助(&H)", "Microsoft Word 帮助 (F1)", "F1")
        self._add(tb, "viewReading", "阅读版式(&R)", "进入阅读版式视图")

        return tb

    def _build_formatting_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("格式"), self.window)

        self._add(tb, "stylesPane", "样式和格式(&S)...", "打开样式和格式任务窗格")

        style_combo = QComboBox(tb)
        style_combo.setObjectName("Quire_StyleCombo")
        style_combo.addItems([
            safe_tr("正文"),
            safe_tr("标题 1"),
            safe_tr("标题 2"),
            safe_tr("标题 3"),
            safe_tr("副标题"),
            safe_tr("页眉"),
            safe_tr("页脚"),
        ])
        style_combo.setToolTip(safe_tr("样式"))
        tb.addWidget(style_combo)

        font_combo = QComboBox(tb)
        font_combo.setObjectName("Quire_FontCombo")
        font_combo.setEditable(True)
        font_combo.addItems([
            "宋体", "黑体", "楷体", "仿宋", "Arial", "Times New Roman", "Calibri", "Courier New"
        ])
        font_combo.setToolTip(safe_tr("字体"))
        tb.addWidget(font_combo)

        size_combo = QComboBox(tb)
        size_combo.setObjectName("Quire_SizeCombo")
        size_combo.setEditable(True)
        size_combo.addItems([
            "初号", "小初", "一号", "小一", "二号", "小二", "三号", "小三",
            "四号", "小四", "五号", "小五", "8", "9", "10", "11", "12",
            "14", "16", "18", "20", "22", "24", "26", "28", "36", "48", "72",
        ])
        size_combo.setCurrentText("五号")
        size_combo.setToolTip(safe_tr("字号"))
        tb.addWidget(size_combo)

        self._add(tb, "bold", "加粗(&B)", "加粗 (Ctrl+B)", "Ctrl+B", checkable=True)
        self._add(tb, "italic", "倾斜(&I)", "倾斜 (Ctrl+I)", "Ctrl+I", checkable=True)
        self._add(tb, "underline", "下划线(&U)", "下划线 (Ctrl+U)", "Ctrl+U", checkable=True)

        tb.add_office_separator()

        self._add(tb, "alignLeft", "左对齐(&L)", "左对齐 (Ctrl+L)", "Ctrl+L", checkable=True)
        self._add(tb, "alignCenter", "居中(&E)", "居中 (Ctrl+E)", "Ctrl+E", checkable=True)
        self._add(tb, "alignRight", "右对齐(&R)", "右对齐 (Ctrl+R)", "Ctrl+R", checkable=True)
        self._add(tb, "justify", "两端对齐(&J)", "两端对齐 (Ctrl+J)", "Ctrl+J", checkable=True)

        tb.add_office_separator()

        self._add_drop(tb, "行距", ["1.0", "1.5", "2.0", "2.5", "3.0", "更多..."])

        tb.add_office_separator()

        self._add(tb, "numbering", "编号(&N)", "项目编号", checkable=True)
        self._add(tb, "bullets", "项目符号(&U)", "项目符号", checkable=True)
        self._add(tb, "decIndent", "减少缩进量(&D)", "减少缩进量")
        self._add(tb, "incIndent", "增加缩进量(&I)", "增加缩进量")

        tb.add_office_separator()

        self._add_split(
            tb,
            "borderBtn",
            "边框(&B)",
            "外部边框与网格",
            ["无边框", "全框线", "外侧框线", "下框线"],
        )

        highlight_btn = ColorPickerButton(mode="fill", default_color="#FFFF00", parent=tb)
        highlight_btn.setObjectName("Quire_HighlightBtn")
        highlight_btn.setToolTip(safe_tr("突出显示"))
        highlight_btn.setStatusTip(safe_tr("突出显示所选文本"))
        tb.addWidget(highlight_btn)

        font_color_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
        font_color_btn.setObjectName("Quire_FontColorBtn")
        font_color_btn.setToolTip(safe_tr("字体颜色"))
        font_color_btn.setStatusTip(safe_tr("更改文本字体颜色"))
        tb.addWidget(font_color_btn)

        return tb

    def _build_tables_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("表格和边框"), self.window)

        self._add(tb, "drawTable", "绘制表格(&D)", "绘制表格线")
        self._add(tb, "eraser", "擦除(&E)", "擦除表格线")

        tb.add_office_separator()

        self._add_drop(tb, "线型", ["实线", "虚线", "点线", "双线"])
        self._add_drop(
            tb, "粗细", ["0.5 pt", "0.75 pt", "1.0 pt", "1.5 pt", "2.25 pt", "3.0 pt"]
        )
        self._add_drop(tb, "边框颜色", ["自动", "黑色", "蓝色", "红色"])
        self._add_split(tb, "tableBorderBtn", "边框(&B)", "应用边框", ["所有框线"])
        self._add_drop(tb, "底纹颜色", ["无填充颜色", "浅灰色"])

        tb.add_office_separator()

        self._add_drop(
            tb,
            "插入",
            [
                "插入表格(&I)...",
                "在左侧插入列",
                "在右侧插入列",
                "在上方插入行",
                "在下方插入行",
            ],
        )
        self._add(tb, "mergeCells", "合并单元格(&M)", "合并选定单元格")
        self._add(tb, "splitCells", "拆分单元格(&P)...", "拆分单元格")

        tb.add_office_separator()

        self._add_drop(tb, "对齐", ["靠上对齐", "居中对齐", "靠下对齐"])
        self._add(tb, "distRows", "平均分布各行(&R)", "平均分布各行高度")
        self._add(tb, "distCols", "平均分布各列(&C)", "平均分布各列宽度")

        tb.add_office_separator()

        self._add(tb, "tableAutoFormat", "表格自动套用格式(&F)...", "表格自动套用格式")
        self._add(tb, "textDirection", "更改文字方向(&D)", "更改单元格文字方向")

        tb.add_office_separator()

        self._add(tb, "sortAsc", "升序排序(&A)", "升序排序表格数据")
        self._add(tb, "sortDesc", "降序排序(&Z)", "降序排序表格数据")
        self._add(tb, "autoSum", "自动求和(&S)", "计算单元格总和")

        return tb

    def _build_reviewing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("审阅"), self.window)

        self._add_drop(
            tb,
            "显示以供审阅",
            ["显示标记的最终状态", "最终状态", "显示标记的原始状态", "原始状态"],
        )
        self._add_drop(tb, "显示", ["批注", "墨迹", "插入和删除", "格式"])

        tb.add_office_separator()

        self._add(tb, "prevChange", "前一处修订或批注(&P)", "定位到前一处修订或批注")
        self._add(tb, "nextChange", "后一处修订或批注(&N)", "定位到后一处修订或批注")

        tb.add_office_separator()

        self._add_split(
            tb,
            "acceptChange",
            "接受所选修订(&A)",
            "接受所选修订",
            ["接受所选修订", "接受对文档所做的所有修订"],
        )
        self._add_split(
            tb,
            "rejectChange",
            "拒绝所选修订(&R)",
            "拒绝所选修订或删除批注",
            ["拒绝所选修订", "拒绝对文档所做的所有修订", "删除文档中的所有批注"],
        )

        tb.add_office_separator()

        self._add(tb, "insertComment", "插入批注(&C)", "插入新批注")
        self._add(
            tb,
            "trackChanges",
            "修订(&T)",
            "开启或关闭修订记录 (Ctrl+Shift+E)",
            "Ctrl+Shift+E",
            checkable=True,
        )
        self._add(tb, "reviewingPane", "审阅窗格(&V)", "显示或隐藏审阅窗格", checkable=True)

        return tb

    def _build_outlining_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("大纲"), self.window)

        self._add(tb, "promoteH1", "提升到 1 级(&1)", "直接提升为标题 1")
        self._add(tb, "promote", "提升(&P)", "提升大纲级别 (Alt+Shift+Left)")

        olvl_combo = QComboBox(tb)
        olvl_combo.setObjectName("Quire_OutlineLevelCombo")
        olvl_combo.addItems([safe_tr(f"{n} 级") for n in range(1, 10)] + [safe_tr("正文文本")])
        olvl_combo.setCurrentText(safe_tr("正文文本"))
        olvl_combo.setToolTip(safe_tr("大纲级别"))
        tb.addWidget(olvl_combo)

        self._add(tb, "demote", "降低(&D)", "降低大纲级别 (Alt+Shift+Right)")
        self._add(tb, "demoteBody", "降为正文(&B)", "将标题降为正文文本 (Ctrl+Shift+N)")

        tb.add_office_separator()

        self._add(tb, "moveUp", "上移(&U)", "上移选定段落 (Alt+Shift+Up)")
        self._add(tb, "moveDown", "下移(&O)", "下移选定段落 (Alt+Shift+Down)")
        self._add(tb, "expand", "展开(&E)", "展开下级内容")
        self._add(tb, "collapse", "折叠(&C)", "折叠下级内容")

        show_lvl_combo = QComboBox(tb)
        show_lvl_combo.setObjectName("Quire_ShowLevelCombo")
        show_lvl_combo.addItems(
            [safe_tr("显示所有级别")] + [safe_tr(f"显示级别 {n}") for n in range(1, 10)]
        )
        show_lvl_combo.setToolTip(safe_tr("显示级别"))
        tb.addWidget(show_lvl_combo)

        self._add(tb, "olFirstLine", "仅显示首行(&F)", "仅显示段落首行", checkable=True)
        self._add(tb, "olFormatting", "显示格式(&S)", "显示文本实际格式", checkable=True)

        tb.add_office_separator()

        self._add(tb, "updateTOC", "更新目录(&T)", "更新文档目录")
        self._add(tb, "gotoTOC", "转到目录(&G)", "跳转到目录位置")

        return tb

    def _build_header_footer_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("页眉和页脚"), self.window)

        self._add_drop(
            tb,
            "插入自动图文集",
            ["-页码-", "创建人与日期", "机密", "第 X 页 共 Y 页"],
        )

        tb.add_office_separator()

        self._add(tb, "hfPageNum", "插入页码(&P)", "插入页码字段")
        self._add(tb, "hfNumPages", "插入页数(&N)", "插入总页数字段")
        self._add(tb, "hfFormatPageNum", "设置页码格式(&F)...", "设置页码格式")
        self._add(tb, "hfDate", "插入日期(&D)", "插入当前日期字段")
        self._add(tb, "hfTime", "插入时间(&T)", "插入当前时间字段")

        tb.add_office_separator()

        self._add(tb, "pageSetup", "页面设置(&U)...", "页面设置")
        self._add(
            tb, "hfShowText", "显示/隐藏文档文字(&W)", "显示或隐藏正文文字", checkable=True
        )
        self._add(
            tb, "hfLinkPrev", "链接到前一个(&L)", "链接到前一节页眉页脚", checkable=True
        )

        tb.add_office_separator()

        self._add(tb, "hfSwitch", "在页眉和页脚间切换(&S)", "在页眉与页脚区域之间切换")
        self._add(tb, "hfPrev", "显示前一项(&B)", "跳转到上一节页眉页脚")
        self._add(tb, "hfNext", "显示下一项(&X)", "跳转到下一节页眉页脚")

        tb.add_office_separator()

        self._add(tb, "hfClose", "关闭(&C)", "关闭页眉和页脚")

        return tb

    def _build_drawing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("绘图"), self.window)

        self._add_drop(
            tb,
            "绘图(&R)",
            [
                "组合(&G)",
                "取消组合(&U)",
                "叠放次序(&O)",
                "微移(&N)",
                "对齐或分布(&A)",
                "旋转或翻转(&R)",
            ],
        )
        self._add(tb, "selectObjects", "选择对象(&S)", "选择画布上的图形对象", checkable=True)

        tb.add_office_separator()

        self._add_drop(
            tb,
            "自选图形(&U)",
            ["线条", "连接符", "基本形状", "箭头总汇", "流程图", "星与旗帜", "标注"],
        )

        self._add(tb, "drawLine", "线条(&L)", "绘制直线")
        self._add(tb, "drawArrow", "箭头(&A)", "绘制箭头")
        self._add(tb, "drawRect", "矩形(&R)", "绘制矩形")
        self._add(tb, "drawOval", "椭圆(&O)", "绘制椭圆")
        self._add(tb, "textBox", "文本框(&T)", "绘制文本框")
        self._add(tb, "insertWordArt", "插入艺术字(&W)...", "插入艺术字")
        self._add(tb, "insertDiagram", "插入图示(&D)...", "插入组织结构图或循环图")
        self._add(tb, "insertClipArt", "剪贴画(&C)...", "插入剪贴画")
        self._add(tb, "insertPicture", "插入图片(&P)...", "插入来自文件的图片")

        tb.add_office_separator()

        fill_btn = ColorPickerButton(mode="fill", default_color="#3366FF", parent=tb)
        fill_btn.setObjectName("Quire_DrawFillColor")
        fill_btn.setToolTip(safe_tr("填充颜色"))
        tb.addWidget(fill_btn)

        line_btn = ColorPickerButton(mode="line", default_color="#000000", parent=tb)
        line_btn.setObjectName("Quire_DrawLineColor")
        line_btn.setToolTip(safe_tr("线条颜色"))
        tb.addWidget(line_btn)

        font_btn = ColorPickerButton(mode="font", default_color="#000000", parent=tb)
        font_btn.setObjectName("Quire_DrawFontColor")
        font_btn.setToolTip(safe_tr("字体颜色"))
        tb.addWidget(font_btn)

        tb.add_office_separator()

        self._add_drop(tb, "线型", ["0.75 磅"])
        self._add_drop(tb, "虚线线型", ["短划线"])
        self._add_drop(tb, "箭头样式", ["箭头样式 1"])
        self._add_drop(tb, "阴影样式", ["阴影样式 1"])

        return tb

    def _build_mail_merge_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("邮件合并"), self.window)

        self._add(tb, "mmMainDoc", "主文档设置(&M)...", "设置邮件合并主文档类型")
        self._add(tb, "mmOpenSource", "打开数据源(&D)...", "连接外部数据源")
        self._add(tb, "mmRecipients", "收件人列表(&R)...", "编辑收件人列表")

        tb.add_office_separator()

        self._add(tb, "mmAddress", "地址块(&A)...", "插入规范地址块域")
        self._add(tb, "mmGreeting", "问候语(&G)...", "插入问候语域")
        self._add(tb, "mmInsertField", "插入合并域(&F)...", "插入特定字段")

        tb.add_office_separator()

        self._add(
            tb, "mmViewData", "查看合并数据(&V)", "切换查看合并数据与域代码", checkable=True
        )
        self._add(tb, "mmFirst", "首记录(&1)", "跳转到第一条记录")
        self._add(tb, "mmPrev", "上一记录(&P)", "跳转到上一条记录")

        rec_combo = QComboBox(tb)
        rec_combo.setObjectName("Quire_MMRecordCombo")
        rec_combo.setEditable(True)
        rec_combo.addItems(["1"])
        rec_combo.setToolTip(safe_tr("记录编号"))
        tb.addWidget(rec_combo)

        self._add(tb, "mmNext", "下一记录(&N)", "跳转到下一条记录")
        self._add(tb, "mmLast", "尾记录(&L)", "跳转到最后一条记录")

        tb.add_office_separator()

        self._add(tb, "mmMergeNew", "合并到新文档(&N)...", "生成合并结果新文档")
        self._add(tb, "mmMergePrint", "合并到打印机(&P)...", "批量输出到打印机")

        return tb

    def _build_picture_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("图片"), self.window)

        self._add(tb, "pic_insert", "插入图片(&I)...", "从文件插入图片")
        self._add_drop(tb, "颜色", ["自动(&A)", "灰度(&G)", "黑白(&B)", "冲蚀(&W)"])

        self._add(tb, "picMoreContrast", "增加对比度(&M)", "增加图片对比度")
        self._add(tb, "picLessContrast", "降低对比度(&L)", "降低图片对比度")
        self._add(tb, "picMoreBright", "增加亮度(&B)", "增加图片亮度")
        self._add(tb, "picLessBright", "降低亮度(&D)", "降低图片亮度")

        tb.add_office_separator()

        self._add(tb, "picCrop", "裁剪(&R)", "激活裁剪控制柄", checkable=True)
        self._add(tb, "picRotate", "向左旋转 90°(&T)", "向左旋转 90 度")
        self._add_drop(tb, "线条样式", ["0.75 磅"])

        tb.add_office_separator()

        self._add_drop(
            tb,
            "文字环绕",
            ["嵌入型", "四周型", "紧密型", "衬于文字下方", "浮于文字上方"],
        )
        self._add(tb, "formatObject", "设置对象格式(&O)...", "设置对象格式对话框")
        self._add(tb, "picReset", "重设图片(&P)", "恢复原始尺寸与颜色设置")

        return tb

    def _build_wordart_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("艺术字"), self.window)

        self._add(tb, "wa_insert", "插入艺术字(&W)...", "插入新艺术字对象")
        self._add(tb, "wordartEdit", "编辑文字(&E)...", "编辑艺术字文字与字体")
        self._add(tb, "wordartGallery", "艺术字库(&G)...", "选择艺术字预设样式库")
        self._add(tb, "wa_format", "设置对象格式(&O)...", "设置艺术字轮廓与填充")
        self._add_drop(
            tb, "艺术字形状", ["纯文本", "波浪", "上凸", "下凹", "环形"]
        )
        self._add_drop(tb, "文字环绕", ["嵌入型", "四周型", "紧密型", "浮于文字上方"])

        return tb


def build_quire_toolbars(
    window: QMainWindow,
    action_registry: ActionRegistry,
) -> dict[str, OfficeToolBar]:
    """Factory creating all 10 Quire toolbars and binding to ActionRegistry."""
    cluster = QuireToolBarCluster(window, action_registry)
    return cluster.build_all()


def retranslate_quire_toolbars(
    toolbars: dict[str, OfficeToolBar],
    tr_func: Callable[[str], str] | None = None,
) -> None:
    """Update localized window titles and tooltips across all 10 toolbars."""
    translate = tr_func or safe_tr
    titles: dict[str, str] = {
        "standard": translate("常用"),
        "formatting": translate("格式"),
        "tables": translate("表格和边框"),
        "reviewing": translate("审阅"),
        "outlining": translate("大纲"),
        "headerFooter": translate("页眉和页脚"),
        "drawing": translate("绘图"),
        "mailMerge": translate("邮件合并"),
        "picture": translate("图片"),
        "wordart": translate("艺术字"),
    }
    for name, title in titles.items():
        tb = toolbars.get(name)
        if tb is not None:
            tb.setWindowTitle(title)
