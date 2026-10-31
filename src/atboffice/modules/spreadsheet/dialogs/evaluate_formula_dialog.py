"""Excel 2003 classic Evaluate Formula dialog (step-by-step formula evaluation)."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from atboffice.modules.spreadsheet.calc.context import EvalContext
from atboffice.modules.spreadsheet.calc.evaluator import evaluate_ast
from atboffice.modules.spreadsheet.calc.parser import parse, to_text
from atboffice.modules.spreadsheet.calc.references import cell_name
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ASTNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    LiteralNode,
    NameNode,
    ParenNode,
    PercentNode,
    SheetReference,
    UnaryOpNode,
)

if TYPE_CHECKING:
    from atboffice.modules.spreadsheet.models.sheet_model import SheetDataModel
    from atboffice.modules.spreadsheet.models.workbook_model import WorkbookModel


def safe_tr(text: str) -> str:
    """Translate UI text safely."""
    return QCoreApplication.translate("EvaluateFormulaDialog", text)


def is_lit(n: ASTNode | None) -> bool:
    """Check if node is a literal value node."""
    return isinstance(n, LiteralNode)


def value_to_literal(v: Any) -> LiteralNode:
    """Wrap evaluated Python/Excel value into a LiteralNode."""
    if isinstance(v, (int, float)):
        return LiteralNode(t="num", v=v)
    if isinstance(v, bool):
        return LiteralNode(t="bool", v=v)
    if isinstance(v, str):
        if v.startswith("#"):
            return LiteralNode(t="err", v=v)
        return LiteralNode(t="str", v=v)
    if v is None:
        return LiteralNode(t="num", v=0)
    if hasattr(v, "e"):
        return LiteralNode(t="err", v=str(v))
    return LiteralNode(t="str", v=str(v))


def next_evaluable_node(n: ASTNode | None) -> ASTNode | None:
    """Locate the innermost sub-expression node ready for evaluation."""
    if n is None:
        return None

    if isinstance(n, (CellRefNode, NameNode)):
        return n

    if isinstance(n, SheetReference):
        if not n.is_range:
            return n
        return None

    if isinstance(n, LiteralNode):
        return None

    if isinstance(n, AreaRefNode):
        return None

    if isinstance(n, ParenNode):
        child = n.operand or n.a
        res = next_evaluable_node(child)
        if res:
            return res
        if is_lit(child):
            return n
        return None

    if isinstance(n, (UnaryOpNode, PercentNode)):
        child = n.operand or n.a
        res = next_evaluable_node(child)
        if res:
            return res
        if is_lit(child):
            return n
        return None

    if isinstance(n, BinaryOpNode):
        left = n.left or n.a
        right = n.right or n.b
        res_l = next_evaluable_node(left)
        if res_l:
            return res_l
        res_r = next_evaluable_node(right)
        if res_r:
            return res_r
        if (is_lit(left) or isinstance(left, AreaRefNode)) and (
            is_lit(right) or isinstance(right, AreaRefNode)
        ):
            return n
        return None

    if isinstance(n, FunctionCallNode):
        for arg in n.args:
            res = next_evaluable_node(arg)
            if res:
                return res
        if all(is_lit(a) or isinstance(a, AreaRefNode) for a in n.args):
            return n
        return None

    return None


def replace_node(root: ASTNode, target: ASTNode, rep: ASTNode) -> ASTNode:
    """Replace target node in the AST with replacement node."""
    if root is target:
        return rep

    if isinstance(root, ParenNode):
        child = root.operand or root.a
        new_child = replace_node(child, target, rep)
        root.operand = new_child
        root.a = new_child
        return root

    if isinstance(root, (UnaryOpNode, PercentNode)):
        child = root.operand or root.a
        new_child = replace_node(child, target, rep)
        root.operand = new_child
        root.a = new_child
        return root

    if isinstance(root, BinaryOpNode):
        left = root.left or root.a
        right = root.right or root.b
        new_left = replace_node(left, target, rep)
        new_right = replace_node(right, target, rep)
        root.left = new_left
        root.a = new_left
        root.right = new_right
        root.b = new_right
        return root

    if isinstance(root, FunctionCallNode):
        new_args = [replace_node(arg, target, rep) for arg in root.args]
        root.args = new_args
        return root

    return root


class EvaluateFormulaDialog(QDialog):
    """Dialog providing step-by-step unrolling of formula evaluation."""

    def __init__(
        self,
        workbook: WorkbookModel | None,
        sheet: SheetDataModel,
        r: int,
        c: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.workbook = workbook
        self.sheet = sheet
        self.r = r
        self.c = c

        cell = sheet.get_cell(r, c)
        raw_formula = cell.formula if (cell and cell.formula) else ""
        if raw_formula.startswith("="):
            raw_formula = raw_formula[1:]
        self.raw_formula = raw_formula

        try:
            self.ast: ASTNode = parse(self.raw_formula)
        except Exception:
            self.ast = LiteralNode(t="str", v=self.raw_formula)

        self.cur_target: ASTNode | None = next_evaluable_node(self.ast)

        # Build execution context
        def cell_getter(sheet_name: str, cr: int, cc: int) -> Any:
            if self.workbook:
                for s in self.workbook.sheets:
                    if s.name == sheet_name:
                        cl = s.get_cell(cr, cc)
                        return cl.value if cl else None
            elif self.sheet.name == sheet_name:
                cl = self.sheet.get_cell(cr, cc)
                return cl.value if cl else None
            return None

        self.ctx = EvalContext(
            cell_getter=cell_getter,
            current_sheet=sheet.name,
            current_row=r,
            current_col=c,
        )

        self._init_ui()
        self._render()

    def _init_ui(self) -> None:
        self.setWindowTitle(safe_tr("公式求值"))
        self.resize(520, 260)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Top row: Reference indicator
        ref_layout = QHBoxLayout()
        lbl_ref_title = QLabel(safe_tr("引用(&R):"), self)
        cell_name_str = cell_name(self.r, self.c, ra=True, ca=True)
        ref_text = f"'{self.sheet.name}'!{cell_name_str}"
        lbl_ref_val = QLabel(f"<b>{ref_text}</b>", self)
        ref_layout.addWidget(lbl_ref_title)
        ref_layout.addWidget(lbl_ref_val)
        ref_layout.addStretch()
        main_layout.addLayout(ref_layout)

        # Middle: Evaluation formula display
        lbl_eval_title = QLabel(safe_tr("求值(&E):"), self)
        main_layout.addWidget(lbl_eval_title)

        self.edit_preview = QTextEdit(self)
        self.edit_preview.setReadOnly(True)
        self.edit_preview.setFont(QFont("Consolas", 11))
        self.edit_preview.setMaximumHeight(80)
        main_layout.addWidget(self.edit_preview)

        # Hint text
        self.lbl_hint = QLabel(
            safe_tr("若要查看加下划线的表达式的结果，请单击“求值”。最新的结果将显示在框中。"),
            self,
        )
        self.lbl_hint.setWordWrap(True)
        self.lbl_hint.setStyleSheet("color: #555555; font-size: 11px;")
        main_layout.addWidget(self.lbl_hint)

        main_layout.addStretch()

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_evaluate = QPushButton(safe_tr("求值(&E)"), self)
        self.btn_evaluate.setDefault(True)
        self.btn_evaluate.clicked.connect(self._on_evaluate_clicked)
        btn_layout.addWidget(self.btn_evaluate)

        self.btn_close = QPushButton(safe_tr("关闭(&C)"), self)
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        main_layout.addLayout(btn_layout)

    def _render(self) -> None:
        """Render formula text highlighting the current evaluable node."""
        full_text = to_text(self.ast)
        style = "font-family:Consolas,monospace; font-size:12pt; padding:4px;"
        if self.cur_target is None or is_lit(self.ast):
            # Final result reached
            escaped_text = html.escape(full_text)
            self.edit_preview.setHtml(
                f"<div style='{style}'><b>={escaped_text}</b></div>"
            )
            self.btn_evaluate.setText(safe_tr("重新启动(&R)"))
            return

        part_text = to_text(self.cur_target)
        idx = full_text.find(part_text)
        if idx >= 0:
            prefix = html.escape(full_text[:idx])
            mid = html.escape(part_text)
            suffix = html.escape(full_text[idx + len(part_text) :])
            html_content = (
                f"<div style='{style}'>={prefix}"
                f"<u><span style='color:#0000CC; font-weight:bold;'>{mid}</span></u>"
                f"{suffix}</div>"
            )
        else:
            escaped = html.escape(full_text)
            html_content = (
                f"<div style='{style}'>"
                f"<u><span style='color:#0000CC; font-weight:bold;'>={escaped}</span></u></div>"
            )

        self.edit_preview.setHtml(html_content)
        self.btn_evaluate.setText(safe_tr("求值(&E)"))

    def _on_evaluate_clicked(self) -> None:
        """Execute single step evaluation or restart if completed."""
        if self.cur_target is None or is_lit(self.ast):
            # Restart
            try:
                self.ast = parse(self.raw_formula)
            except Exception:
                self.ast = LiteralNode(t="str", v=self.raw_formula)
            self.cur_target = next_evaluable_node(self.ast)
            self._render()
            return

        # Evaluate target node
        try:
            val = evaluate_ast(self.cur_target, self.ctx)
        except Exception as ex:
            val = f"#VALUE! ({ex})"

        rep = value_to_literal(val)
        target = self.cur_target

        if self.ast is target:
            self.ast = rep
        else:
            self.ast = replace_node(self.ast, target, rep)

        if is_lit(self.ast):
            self.cur_target = None
        else:
            self.cur_target = next_evaluable_node(self.ast)

        self._render()
