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
    """Translate UI text safely for Lectern toolbars."""
    return QCoreApplication.translate("LecternToolbars", text)


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
            ["彩色(&C)", "灰度(&G)", "纯黑白(&B)"],
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

        self._add_split(
            tb,
            "diagramAddShape",
            "添加形状(&A)",
            "在所选关系图元素周围添加新形状",
            [
                "在后面添加形状(&A)",
                "在前面添加形状(&B)",
                "在上方添加形状(&O)",
                "在下方添加形状(&E)",
            ],
        )
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

        self._add_drop(tb, "线型", ["实线", "虚线", "点线", "双线"])
        self._add_drop(
            tb,
            "粗细",
            ["0.5 磅", "1.0 磅", "1.5 磅", "2.25 磅", "3.0 磅", "4.5 磅", "6.0 磅"],
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
        self._add_drop(tb, "线型", ["0.75 磅", "1.5 磅", "3 磅", "4.5 磅", "6 磅"])

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

        self._add_drop(
            tb,
            "绘图(&R)",
            [
                "置于顶层(&F)",
                "置于底层(&B)",
                "上移一层(&U)",
                "下移一层(&D)",
                "-",
                "组合(&G)",
                "取消组合(&U)",
                "重新组合(&R)",
                "-",
                "微移(&N)",
                "对齐或分布(&A)",
                "旋转或翻转(&T)",
            ],
        )
        self._add(tb, "selectObjects", "选择对象(&S)", "框选画布中的图形对象", checkable=True)

        tb.add_office_separator()

        self._add_drop(
            tb,
            "自选图形(&U)",
            ["线条", "连接符", "基本形状", "箭头总汇", "流程图", "星与旗帜", "标注"],
        )

        self._add(tb, "drawLine", "线条(&L)", "自由绘制直线段")
        self._add(tb, "drawArrow", "箭头(&A)", "绘制单向箭头线")
        self._add(tb, "drawRect", "矩形(&R)", "绘制矩形几何图形")
        self._add(tb, "drawOval", "椭圆(&O)", "绘制椭圆或正圆形")
        self._add(tb, "textBox", "文本框(&T)", "在幻灯片中绘制横向文本框")
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

        self._add_drop(tb, "线型", ["0.75 磅", "1.5 磅", "3 磅", "4.5 磅", "6 磅"])
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
    """Update localized window titles across all 10 toolbars."""
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
