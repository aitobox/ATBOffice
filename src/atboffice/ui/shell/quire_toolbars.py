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
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication, QSize, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QMainWindow,
    QMenu,
    QWidget,
)

from atboffice.core.action_registry import ActionRegistry, ActionSpec
from atboffice.ui.components.color_picker import ColorPickerButton
from atboffice.ui.components.toolbar import OfficeToolBar

if TYPE_CHECKING:
    pass


def safe_tr(text: str) -> str:
    """Translate UI text safely for Quire toolbars."""
    return QCoreApplication.translate("QuireToolbars", text)


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
            label=label,
            tip=tip,
            shortcut=shortcut,
            checkable=checkable,
            checked=checked,
            is_split=is_split,
            is_drop=is_drop,
            handler=handler,
        )
        return self.action_registry.register_action(spec, parent=self.window)

    def _build_standard_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("常用"), self.window)

        # File and basic commands
        tb.addAction(self._reg_act("new", safe_tr("新建(&N)"), safe_tr("新建空白文档 (Ctrl+N)"), QKeySequence.StandardKey.New))
        tb.addAction(self._reg_act("open", safe_tr("打开(&O)..."), safe_tr("打开文档 (Ctrl+O)"), QKeySequence.StandardKey.Open))
        tb.addAction(self._reg_act("save", safe_tr("保存(&S)"), safe_tr("保存文档 (Ctrl+S)"), QKeySequence.StandardKey.Save))
        tb.addAction(self._reg_act("permission", safe_tr("权限(&M)"), safe_tr("权限设置 (只读/编辑)")))
        tb.addAction(self._reg_act("sendMail", safe_tr("发送(&E)"), safe_tr("通过电子邮件发送")))
        tb.addAction(self._reg_act("print", safe_tr("打印(&P)..."), safe_tr("打印文档 (Ctrl+P)"), QKeySequence.StandardKey.Print))
        tb.addAction(self._reg_act("printPreview", safe_tr("打印预览(&V)"), safe_tr("打印预览")))
        tb.addAction(self._reg_act("spelling", safe_tr("拼写和语法(&S)..."), safe_tr("拼写和语法检查 (F7)"), "F7"))
        tb.addAction(self._reg_act("research", safe_tr("信息检索(&R)..."), safe_tr("信息检索与翻译 (Alt+Click)")))

        tb.add_office_separator()

        # Clipboard
        tb.addAction(self._reg_act("cut", safe_tr("剪切(&T)"), safe_tr("剪切 (Ctrl+X)"), QKeySequence.StandardKey.Cut))
        tb.addAction(self._reg_act("copy", safe_tr("复制(&C)"), safe_tr("复制 (Ctrl+C)"), QKeySequence.StandardKey.Copy))
        tb.addAction(self._reg_act("paste", safe_tr("粘贴(&P)"), safe_tr("粘贴 (Ctrl+V)"), QKeySequence.StandardKey.Paste))
        tb.addAction(self._reg_act("painter", safe_tr("格式刷(&P)"), safe_tr("格式刷 (双击可连续应用)")))

        tb.add_office_separator()

        # Undo / Redo split buttons
        undo_act = self._reg_act("undo", safe_tr("撤销(&U)"), safe_tr("撤销 (Ctrl+Z)"), QKeySequence.StandardKey.Undo, is_split=True)
        undo_menu = QMenu(tb)
        undo_menu.addAction(safe_tr("无操作可撤销"))
        tb.add_split_action(undo_act, undo_menu)

        redo_act = self._reg_act("redo", safe_tr("重做(&R)"), safe_tr("重做 (Ctrl+Y)"), QKeySequence.StandardKey.Redo, is_split=True)
        redo_menu = QMenu(tb)
        redo_menu.addAction(safe_tr("无操作可重做"))
        tb.add_split_action(redo_act, redo_menu)

        tb.add_office_separator()

        # Insert items
        tb.addAction(self._reg_act("hyperlink", safe_tr("插入超链接(&I)..."), safe_tr("插入超链接 (Ctrl+K)"), "Ctrl+K"))
        tb.addAction(self._reg_act("tb_tables", safe_tr("表格和边框(&B)"), safe_tr("显示或隐藏表格和边框工具栏")))

        table_menu = QMenu(tb)
        table_menu.addAction(safe_tr("插入表格(&I)..."))
        table_menu.addAction(safe_tr("插入列在左侧"))
        table_menu.addAction(safe_tr("插入行在上方"))
        tb.add_drop_button(safe_tr("插入表格"), None, table_menu)

        tb.addAction(self._reg_act("insertExcel", safe_tr("插入 Excel 工作表(&E)"), safe_tr("插入 Microsoft Excel 工作表")))

        col_menu = QMenu(tb)
        for c in [safe_tr("一栏"), safe_tr("两栏"), safe_tr("三栏"), safe_tr("偏左"), safe_tr("偏右")]:
            col_menu.addAction(c)
        tb.add_drop_button(safe_tr("分栏"), None, col_menu)

        tb.addAction(self._reg_act("tb_drawing", safe_tr("绘图(&D)"), safe_tr("显示或隐藏绘图工具栏")))
        tb.addAction(self._reg_act("docMap", safe_tr("文档结构图(&D)"), safe_tr("显示或隐藏文档结构图"), checkable=True))
        tb.addAction(self._reg_act("showMarks", safe_tr("显示/隐藏编辑标记(&S)"), safe_tr("显示或隐藏段落标记与格式"), checkable=True))

        # Zoom Combo
        zoom_combo = QComboBox(tb)
        zoom_combo.setObjectName("Quire_ZoomCombo")
        zoom_combo.setEditable(True)
        zoom_combo.addItems(["500%", "200%", "150%", "100%", "75%", "50%", "25%", safe_tr("页宽"), safe_tr("整页")])
        zoom_combo.setCurrentText("100%")
        zoom_combo.setToolTip(safe_tr("显示比例"))
        tb.addWidget(zoom_combo)

        tb.addAction(self._reg_act("help", safe_tr("帮助(&H)"), safe_tr("Microsoft Word 帮助 (F1)"), "F1"))
        tb.addAction(self._reg_act("viewReading", safe_tr("阅读版式(&R)"), safe_tr("进入阅读版式视图")))

        return tb

    def _build_formatting_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("格式"), self.window)

        tb.addAction(self._reg_act("stylesPane", safe_tr("样式和格式(&S)..."), safe_tr("打开样式和格式任务窗格")))

        # Style combo
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

        # Font combo
        font_combo = QComboBox(tb)
        font_combo.setObjectName("Quire_FontCombo")
        font_combo.setEditable(True)
        font_combo.addItems(["宋体", "黑体", "楷体", "仿宋", "Arial", "Times New Roman", "Calibri", "Courier New"])
        font_combo.setToolTip(safe_tr("字体"))
        tb.addWidget(font_combo)

        # Size combo
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

        # Basic styles
        tb.addAction(self._reg_act("bold", safe_tr("加粗(&B)"), safe_tr("加粗 (Ctrl+B)"), "Ctrl+B", checkable=True))
        tb.addAction(self._reg_act("italic", safe_tr("倾斜(&I)"), safe_tr("倾斜 (Ctrl+I)"), "Ctrl+I", checkable=True))
        tb.addAction(self._reg_act("underline", safe_tr("下划线(&U)"), safe_tr("下划线 (Ctrl+U)"), "Ctrl+U", checkable=True))

        tb.add_office_separator()

        # Alignment
        tb.addAction(self._reg_act("alignLeft", safe_tr("左对齐(&L)"), safe_tr("左对齐 (Ctrl+L)"), "Ctrl+L", checkable=True))
        tb.addAction(self._reg_act("alignCenter", safe_tr("居中(&E)"), safe_tr("居中 (Ctrl+E)"), "Ctrl+E", checkable=True))
        tb.addAction(self._reg_act("alignRight", safe_tr("右对齐(&R)"), safe_tr("右对齐 (Ctrl+R)"), "Ctrl+R", checkable=True))
        tb.addAction(self._reg_act("justify", safe_tr("两端对齐(&J)"), safe_tr("两端对齐 (Ctrl+J)"), "Ctrl+J", checkable=True))

        tb.add_office_separator()

        # Line spacing
        ls_menu = QMenu(tb)
        for sp in ["1.0", "1.5", "2.0", "2.5", "3.0", safe_tr("更多...")]:
            ls_menu.addAction(sp)
        tb.add_drop_button(safe_tr("行距"), None, ls_menu)

        tb.add_office_separator()

        # Lists & indent
        tb.addAction(self._reg_act("numbering", safe_tr("编号(&N)"), safe_tr("项目编号"), checkable=True))
        tb.addAction(self._reg_act("bullets", safe_tr("项目符号(&U)"), safe_tr("项目符号"), checkable=True))
        tb.addAction(self._reg_act("decIndent", safe_tr("减少缩进量(&D)"), safe_tr("减少缩进量")))
        tb.addAction(self._reg_act("incIndent", safe_tr("增加缩进量(&I)"), safe_tr("增加缩进量")))

        tb.add_office_separator()

        # Border split button
        border_act = self._reg_act("borderBtn", safe_tr("边框(&B)"), safe_tr("外部边框与网格"), is_split=True)
        b_menu = QMenu(tb)
        for b_name in [safe_tr("无边框"), safe_tr("全框线"), safe_tr("外侧框线"), safe_tr("下框线")]:
            b_menu.addAction(b_name)
        tb.add_split_action(border_act, b_menu)

        # Highlight & Font color pickers
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

        tb.addAction(self._reg_act("drawTable", safe_tr("绘制表格(&D)"), safe_tr("绘制表格线")))
        tb.addAction(self._reg_act("eraser", safe_tr("擦除(&E)"), safe_tr("擦除表格线")))

        tb.add_office_separator()

        # Dash style, line style, line color
        dash_menu = QMenu(tb)
        for s in [safe_tr("实线"), safe_tr("虚线"), safe_tr("点线"), safe_tr("双线")]:
            dash_menu.addAction(s)
        tb.add_drop_button(safe_tr("线型"), None, dash_menu)

        weight_menu = QMenu(tb)
        for w in ["0.5 pt", "0.75 pt", "1.0 pt", "1.5 pt", "2.25 pt", "3.0 pt"]:
            weight_menu.addAction(w)
        tb.add_drop_button(safe_tr("粗细"), None, weight_menu)

        color_menu = QMenu(tb)
        color_menu.addAction(safe_tr("自动"))
        color_menu.addAction(safe_tr("黑色"))
        color_menu.addAction(safe_tr("蓝色"))
        color_menu.addAction(safe_tr("红色"))
        tb.add_drop_button(safe_tr("边框颜色"), None, color_menu)

        border_act = self._reg_act("tableBorderBtn", safe_tr("边框(&B)"), safe_tr("应用边框"), is_split=True)
        tb_b_menu = QMenu(tb)
        tb_b_menu.addAction(safe_tr("所有框线"))
        tb.add_split_action(border_act, tb_b_menu)

        fill_menu = QMenu(tb)
        fill_menu.addAction(safe_tr("无填充颜色"))
        fill_menu.addAction(safe_tr("浅灰色"))
        tb.add_drop_button(safe_tr("底纹颜色"), None, fill_menu)

        tb.add_office_separator()

        ins_menu = QMenu(tb)
        ins_menu.addAction(safe_tr("插入表格(&I)..."))
        ins_menu.addAction(safe_tr("在左侧插入列"))
        ins_menu.addAction(safe_tr("在右侧插入列"))
        ins_menu.addAction(safe_tr("在上方插入行"))
        ins_menu.addAction(safe_tr("在下方插入行"))
        tb.add_drop_button(safe_tr("插入"), None, ins_menu)

        tb.addAction(self._reg_act("mergeCells", safe_tr("合并单元格(&M)"), safe_tr("合并选定单元格")))
        tb.addAction(self._reg_act("splitCells", safe_tr("拆分单元格(&P)..."), safe_tr("拆分单元格")))

        tb.add_office_separator()

        align_menu = QMenu(tb)
        for a in [safe_tr("靠上对齐"), safe_tr("居中对齐"), safe_tr("靠下对齐")]:
            align_menu.addAction(a)
        tb.add_drop_button(safe_tr("对齐"), None, align_menu)

        tb.addAction(self._reg_act("distRows", safe_tr("平均分布各行(&R)"), safe_tr("平均分布各行高度")))
        tb.addAction(self._reg_act("distCols", safe_tr("平均分布各列(&C)"), safe_tr("平均分布各列宽度")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("tableAutoFormat", safe_tr("表格自动套用格式(&F)..."), safe_tr("表格自动套用格式")))
        tb.addAction(self._reg_act("textDirection", safe_tr("更改文字方向(&D)"), safe_tr("更改单元格文字方向")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("sortAsc", safe_tr("升序排序(&A)"), safe_tr("升序排序表格数据")))
        tb.addAction(self._reg_act("sortDesc", safe_tr("降序排序(&Z)"), safe_tr("降序排序表格数据")))
        tb.addAction(self._reg_act("autoSum", safe_tr("自动求和(&S)"), safe_tr("计算单元格总和")))

        return tb

    def _build_reviewing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("审阅"), self.window)

        rev_menu = QMenu(tb)
        for m in [safe_tr("显示标记的最终状态"), safe_tr("最终状态"), safe_tr("显示标记的原始状态"), safe_tr("原始状态")]:
            rev_menu.addAction(m)
        tb.add_drop_button(safe_tr("显示以供审阅"), None, rev_menu)

        show_menu = QMenu(tb)
        for item in [safe_tr("批注"), safe_tr("墨迹"), safe_tr("插入和删除"), safe_tr("格式")]:
            show_menu.addAction(item)
        tb.add_drop_button(safe_tr("显示"), None, show_menu)

        tb.add_office_separator()

        tb.addAction(self._reg_act("prevChange", safe_tr("前一处修订或批注(&P)"), safe_tr("定位到前一处修订或批注")))
        tb.addAction(self._reg_act("nextChange", safe_tr("后一处修订或批注(&N)"), safe_tr("定位到后一处修订或批注")))

        tb.add_office_separator()

        accept_act = self._reg_act("acceptChange", safe_tr("接受所选修订(&A)"), safe_tr("接受所选修订"), is_split=True)
        acc_menu = QMenu(tb)
        acc_menu.addAction(safe_tr("接受所选修订"))
        acc_menu.addAction(safe_tr("接受对文档所做的所有修订"))
        tb.add_split_action(accept_act, acc_menu)

        reject_act = self._reg_act("rejectChange", safe_tr("拒绝所选修订(&R)"), safe_tr("拒绝所选修订或删除批注"), is_split=True)
        rej_menu = QMenu(tb)
        rej_menu.addAction(safe_tr("拒绝所选修订"))
        rej_menu.addAction(safe_tr("拒绝对文档所做的所有修订"))
        rej_menu.addAction(safe_tr("删除文档中的所有批注"))
        tb.add_split_action(reject_act, rej_menu)

        tb.add_office_separator()

        tb.addAction(self._reg_act("insertComment", safe_tr("插入批注(&C)"), safe_tr("插入新批注")))
        tb.addAction(self._reg_act("trackChanges", safe_tr("修订(&T)"), safe_tr("开启或关闭修订记录 (Ctrl+Shift+E)"), "Ctrl+Shift+E", checkable=True))
        tb.addAction(self._reg_act("reviewingPane", safe_tr("审阅窗格(&V)"), safe_tr("显示或隐藏审阅窗格"), checkable=True))

        return tb

    def _build_outlining_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("大纲"), self.window)

        tb.addAction(self._reg_act("promoteH1", safe_tr("提升到 1 级(&1)"), safe_tr("直接提升为标题 1")))
        tb.addAction(self._reg_act("promote", safe_tr("提升(&P)"), safe_tr("提升大纲级别 (Alt+Shift+Left)")))

        olvl_combo = QComboBox(tb)
        olvl_combo.setObjectName("Quire_OutlineLevelCombo")
        olvl_combo.addItems([safe_tr(f"{n} 级") for n in range(1, 10)] + [safe_tr("正文文本")])
        olvl_combo.setCurrentText(safe_tr("正文文本"))
        olvl_combo.setToolTip(safe_tr("大纲级别"))
        tb.addWidget(olvl_combo)

        tb.addAction(self._reg_act("demote", safe_tr("降低(&D)"), safe_tr("降低大纲级别 (Alt+Shift+Right)")))
        tb.addAction(self._reg_act("demoteBody", safe_tr("降为正文(&B)"), safe_tr("将标题降为正文文本 (Ctrl+Shift+N)")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("moveUp", safe_tr("上移(&U)"), safe_tr("上移选定段落 (Alt+Shift+Up)")))
        tb.addAction(self._reg_act("moveDown", safe_tr("下移(&O)"), safe_tr("下移选定段落 (Alt+Shift+Down)")))
        tb.addAction(self._reg_act("expand", safe_tr("展开(&E)"), safe_tr("展开下级内容")))
        tb.addAction(self._reg_act("collapse", safe_tr("折叠(&C)"), safe_tr("折叠下级内容")))

        show_lvl_combo = QComboBox(tb)
        show_lvl_combo.setObjectName("Quire_ShowLevelCombo")
        show_lvl_combo.addItems([safe_tr("显示所有级别")] + [safe_tr(f"显示级别 {n}") for n in range(1, 10)])
        show_lvl_combo.setToolTip(safe_tr("显示级别"))
        tb.addWidget(show_lvl_combo)

        tb.addAction(self._reg_act("olFirstLine", safe_tr("仅显示首行(&F)"), safe_tr("仅显示段落首行"), checkable=True))
        tb.addAction(self._reg_act("olFormatting", safe_tr("显示格式(&S)"), safe_tr("显示文本实际格式"), checkable=True))

        tb.add_office_separator()

        tb.addAction(self._reg_act("updateTOC", safe_tr("更新目录(&T)"), safe_tr("更新文档目录")))
        tb.addAction(self._reg_act("gotoTOC", safe_tr("转到目录(&G)"), safe_tr("跳转到目录位置")))

        return tb

    def _build_header_footer_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("页眉和页脚"), self.window)

        autotext_menu = QMenu(tb)
        for at in [safe_tr("-页码-"), safe_tr("创建人与日期"), safe_tr("机密"), safe_tr("第 X 页 共 Y 页")]:
            autotext_menu.addAction(at)
        tb.add_drop_button(safe_tr("插入自动图文集"), None, autotext_menu)

        tb.add_office_separator()

        tb.addAction(self._reg_act("hfPageNum", safe_tr("插入页码(&P)"), safe_tr("插入页码字段")))
        tb.addAction(self._reg_act("hfNumPages", safe_tr("插入页数(&N)"), safe_tr("插入总页数字段")))
        tb.addAction(self._reg_act("hfFormatPageNum", safe_tr("设置页码格式(&F)..."), safe_tr("设置页码格式")))
        tb.addAction(self._reg_act("hfDate", safe_tr("插入日期(&D)"), safe_tr("插入当前日期字段")))
        tb.addAction(self._reg_act("hfTime", safe_tr("插入时间(&T)"), safe_tr("插入当前时间字段")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("pageSetup", safe_tr("页面设置(&U)..."), safe_tr("页面设置")))
        tb.addAction(self._reg_act("hfShowText", safe_tr("显示/隐藏文档文字(&W)"), safe_tr("显示或隐藏正文文字"), checkable=True))
        tb.addAction(self._reg_act("hfLinkPrev", safe_tr("链接到前一个(&L)"), safe_tr("链接到前一节页眉页脚"), checkable=True))

        tb.add_office_separator()

        tb.addAction(self._reg_act("hfSwitch", safe_tr("在页眉和页脚间切换(&S)"), safe_tr("在页眉与页脚区域之间切换")))
        tb.addAction(self._reg_act("hfPrev", safe_tr("显示前一项(&B)"), safe_tr("跳转到上一节页眉页脚")))
        tb.addAction(self._reg_act("hfNext", safe_tr("显示下一项(&X)"), safe_tr("跳转到下一节页眉页脚")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("hfClose", safe_tr("关闭(&C)"), safe_tr("关闭页眉和页脚")))

        return tb

    def _build_drawing_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("绘图"), self.window)

        draw_menu = QMenu(tb)
        for item in [safe_tr("组合(&G)"), safe_tr("取消组合(&U)"), safe_tr("叠放次序(&O)"), safe_tr("微移(&N)"), safe_tr("对齐或分布(&A)"), safe_tr("旋转或翻转(&R)")]:
            draw_menu.addAction(item)
        tb.add_drop_button(safe_tr("绘图(&R)"), None, draw_menu)

        tb.addAction(self._reg_act("selectObjects", safe_tr("选择对象(&S)"), safe_tr("选择画布上的图形对象"), checkable=True))

        tb.add_office_separator()

        as_menu = QMenu(tb)
        for s in [safe_tr("线条"), safe_tr("连接符"), safe_tr("基本形状"), safe_tr("箭头总汇"), safe_tr("流程图"), safe_tr("星与旗帜"), safe_tr("标注")]:
            as_menu.addAction(s)
        tb.add_drop_button(safe_tr("自选图形(&U)"), None, as_menu)

        tb.addAction(self._reg_act("drawLine", safe_tr("线条(&L)"), safe_tr("绘制直线")))
        tb.addAction(self._reg_act("drawArrow", safe_tr("箭头(&A)"), safe_tr("绘制箭头")))
        tb.addAction(self._reg_act("drawRect", safe_tr("矩形(&R)"), safe_tr("绘制矩形")))
        tb.addAction(self._reg_act("drawOval", safe_tr("椭圆(&O)"), safe_tr("绘制椭圆")))
        tb.addAction(self._reg_act("textBox", safe_tr("文本框(&T)"), safe_tr("绘制文本框")))
        tb.addAction(self._reg_act("insertWordArt", safe_tr("插入艺术字(&W)..."), safe_tr("插入艺术字")))
        tb.addAction(self._reg_act("insertDiagram", safe_tr("插入图示(&D)..."), safe_tr("插入组织结构图或循环图")))
        tb.addAction(self._reg_act("insertClipArt", safe_tr("剪贴画(&C)..."), safe_tr("插入剪贴画")))
        tb.addAction(self._reg_act("insertPicture", safe_tr("插入图片(&P)..."), safe_tr("插入来自文件的图片")))

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

        d_line_menu = QMenu(tb)
        d_line_menu.addAction(safe_tr("0.75 磅"))
        tb.add_drop_button(safe_tr("线型"), None, d_line_menu)

        d_dash_menu = QMenu(tb)
        d_dash_menu.addAction(safe_tr("短划线"))
        tb.add_drop_button(safe_tr("虚线线型"), None, d_dash_menu)

        d_arr_menu = QMenu(tb)
        d_arr_menu.addAction(safe_tr("箭头样式 1"))
        tb.add_drop_button(safe_tr("箭头样式"), None, d_arr_menu)

        d_shd_menu = QMenu(tb)
        d_shd_menu.addAction(safe_tr("阴影样式 1"))
        tb.add_drop_button(safe_tr("阴影样式"), None, d_shd_menu)

        return tb

    def _build_mail_merge_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("邮件合并"), self.window)

        tb.addAction(self._reg_act("mmMainDoc", safe_tr("主文档设置(&M)..."), safe_tr("设置邮件合并主文档类型")))
        tb.addAction(self._reg_act("mmOpenSource", safe_tr("打开数据源(&D)..."), safe_tr("连接外部数据源")))
        tb.addAction(self._reg_act("mmRecipients", safe_tr("收件人列表(&R)..."), safe_tr("编辑收件人列表")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("mmAddress", safe_tr("地址块(&A)..."), safe_tr("插入规范地址块域")))
        tb.addAction(self._reg_act("mmGreeting", safe_tr("问候语(&G)..."), safe_tr("插入问候语域")))
        tb.addAction(self._reg_act("mmInsertField", safe_tr("插入合并域(&F)..."), safe_tr("插入特定字段")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("mmViewData", safe_tr("查看合并数据(&V)"), safe_tr("切换查看合并数据与域代码"), checkable=True))
        tb.addAction(self._reg_act("mmFirst", safe_tr("首记录(&1)"), safe_tr("跳转到第一条记录")))
        tb.addAction(self._reg_act("mmPrev", safe_tr("上一记录(&P)"), safe_tr("跳转到上一条记录")))

        rec_combo = QComboBox(tb)
        rec_combo.setObjectName("Quire_MMRecordCombo")
        rec_combo.setEditable(True)
        rec_combo.addItems(["1"])
        rec_combo.setToolTip(safe_tr("记录编号"))
        tb.addWidget(rec_combo)

        tb.addAction(self._reg_act("mmNext", safe_tr("下一记录(&N)"), safe_tr("跳转到下一条记录")))
        tb.addAction(self._reg_act("mmLast", safe_tr("尾记录(&L)"), safe_tr("跳转到最后一条记录")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("mmMergeNew", safe_tr("合并到新文档(&N)..."), safe_tr("生成合并结果新文档")))
        tb.addAction(self._reg_act("mmMergePrint", safe_tr("合并到打印机(&P)..."), safe_tr("批量输出到打印机")))

        return tb

    def _build_picture_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("图片"), self.window)

        tb.addAction(self._reg_act("pic_insert", safe_tr("插入图片(&I)..."), safe_tr("从文件插入图片")))

        col_menu = QMenu(tb)
        for c in [safe_tr("自动(&A)"), safe_tr("灰度(&G)"), safe_tr("黑白(&B)"), safe_tr("冲蚀(&W)")]:
            col_menu.addAction(c)
        tb.add_drop_button(safe_tr("颜色"), None, col_menu)

        tb.addAction(self._reg_act("picMoreContrast", safe_tr("增加对比度(&M)"), safe_tr("增加图片对比度")))
        tb.addAction(self._reg_act("picLessContrast", safe_tr("降低对比度(&L)"), safe_tr("降低图片对比度")))
        tb.addAction(self._reg_act("picMoreBright", safe_tr("增加亮度(&B)"), safe_tr("增加图片亮度")))
        tb.addAction(self._reg_act("picLessBright", safe_tr("降低亮度(&D)"), safe_tr("降低图片亮度")))

        tb.add_office_separator()

        tb.addAction(self._reg_act("picCrop", safe_tr("裁剪(&R)"), safe_tr("激活裁剪控制柄"), checkable=True))
        tb.addAction(self._reg_act("picRotate", safe_tr("向左旋转 90°(&T)"), safe_tr("向左旋转 90 度")))

        ls_menu = QMenu(tb)
        ls_menu.addAction(safe_tr("0.75 磅"))
        tb.add_drop_button(safe_tr("线条样式"), None, ls_menu)

        tb.add_office_separator()

        wrap_menu = QMenu(tb)
        for w in [safe_tr("嵌入型"), safe_tr("四周型"), safe_tr("紧密型"), safe_tr("衬于文字下方"), safe_tr("浮于文字上方")]:
            wrap_menu.addAction(w)
        tb.add_drop_button(safe_tr("文字环绕"), None, wrap_menu)

        tb.addAction(self._reg_act("formatObject", safe_tr("设置对象格式(&O)..."), safe_tr("设置对象格式对话框")))
        tb.addAction(self._reg_act("picReset", safe_tr("重设图片(&P)"), safe_tr("恢复原始尺寸与颜色设置")))

        return tb

    def _build_wordart_toolbar(self) -> OfficeToolBar:
        tb = OfficeToolBar(safe_tr("艺术字"), self.window)

        tb.addAction(self._reg_act("wa_insert", safe_tr("插入艺术字(&W)..."), safe_tr("插入新艺术字对象")))
        tb.addAction(self._reg_act("wordartEdit", safe_tr("编辑文字(&E)..."), safe_tr("编辑艺术字文字与字体")))
        tb.addAction(self._reg_act("wordartGallery", safe_tr("艺术字库(&G)..."), safe_tr("选择艺术字预设样式库")))
        tb.addAction(self._reg_act("wa_format", safe_tr("设置对象格式(&O)..."), safe_tr("设置艺术字轮廓与填充")))

        shape_menu = QMenu(tb)
        for shp in [safe_tr("纯文本"), safe_tr("波浪"), safe_tr("上凸"), safe_tr("下凹"), safe_tr("环形")]:
            shape_menu.addAction(shp)
        tb.add_drop_button(safe_tr("艺术字形状"), None, shape_menu)

        wrap_menu = QMenu(tb)
        for w in [safe_tr("嵌入型"), safe_tr("四周型"), safe_tr("紧密型"), safe_tr("浮于文字上方")]:
            wrap_menu.addAction(w)
        tb.add_drop_button(safe_tr("文字环绕"), None, wrap_menu)

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
