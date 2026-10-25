"""AST expression evaluator and formula execution engine."""

from __future__ import annotations

import math
from typing import Any

from atboffice.modules.spreadsheet.calc.coercion import (
    compare_excel_values,
    num_eq,
    round_15,
    to_bool,
    to_num,
    to_str,
)
from atboffice.modules.spreadsheet.calc.context import Arr, EvalContext, Ref
from atboffice.modules.spreadsheet.calc.errors import (
    CALC,
    DIV0,
    NA,
    NAME,
    NUM,
    VALUE,
    ExcelError,
    is_error,
    to_error,
)
from atboffice.modules.spreadsheet.calc.functions import call_function
from atboffice.modules.spreadsheet.calc.parser import parse
from atboffice.modules.spreadsheet.calc.tokens import (
    AreaRefNode,
    ArrayNode,
    ASTNode,
    BinaryOpNode,
    CellRefNode,
    FunctionCallNode,
    InvokeNode,
    LiteralNode,
    NameNode,
    ParenNode,
    UnaryOpNode,
)


def evaluate_ast(node: ASTNode, ctx: EvalContext | None = None) -> Any:
    """Recursively evaluate a formula AST against an evaluation context."""
    if ctx is None:
        ctx = EvalContext()

    if isinstance(node, LiteralNode):
        if node.t == "err" and isinstance(node.v, str):
            err = to_error(node.v)
            return err if err is not None else ExcelError(node.v)
        return node.v

    if isinstance(node, ParenNode):
        return evaluate_ast(node.node, ctx)

    if isinstance(node, NameNode):
        name_key = node.name.upper()
        if ctx.vars and name_key in ctx.vars:
            return ctx.vars[name_key]
        return NAME

    if isinstance(node, InvokeNode):
        fn_val = evaluate_ast(node.fn, ctx)
        if callable(fn_val):
            eval_args = [evaluate_ast(a, ctx) for a in node.args]
            return fn_val(*eval_args, ctx=ctx)
        if is_error(fn_val):
            return fn_val
        return CALC

    if isinstance(node, CellRefNode):
        sheet = node.sheet or ctx.current_sheet
        val = ctx.get_cell_value(sheet, node.r, node.c)
        if isinstance(val, str) and val.startswith("="):
            # Evaluate nested formula
            nested_ast = parse(val[1:])
            return evaluate_ast(nested_ast, ctx)
        return val

    if isinstance(node, AreaRefNode):
        sheet = node.sheet or ctx.current_sheet
        return ctx.create_ref(sheet, node.r1, node.c1, node.r2, node.c2)

    if isinstance(node, ArrayNode):
        matrix: list[list[Any]] = []
        for row in node.rows:
            matrix.append([evaluate_ast(item, ctx) for item in row])
        return Arr(matrix)

    if isinstance(node, UnaryOpNode):
        val = evaluate_ast(node.node, ctx)
        if is_error(val):
            return val
        n = to_num(val, ctx)
        if is_error(n):
            return n
        if node.op == "-":
            return -n  # type: ignore
        return n

    if isinstance(node, BinaryOpNode):
        op = node.op
        left_val = evaluate_ast(node.left, ctx)
        if is_error(left_val):
            return left_val
        right_val = evaluate_ast(node.right, ctx)
        if is_error(right_val):
            return right_val

        # Unbox single cell Ref if needed
        if isinstance(left_val, Ref) and left_val.single:
            left_val = left_val.cell_value(left_val.r1, left_val.c1)
        if isinstance(right_val, Ref) and right_val.single:
            right_val = right_val.cell_value(right_val.r1, right_val.c1)

        # String concatenation
        if op == "&":
            return to_str(left_val) + to_str(right_val)

        # Comparison operators
        if op in ("=", "<>", "<", ">", "<=", ">="):
            cmp = compare_excel_values(left_val, right_val)
            if op == "=":
                return cmp == 0
            if op == "<>":
                return cmp != 0
            if op == "<":
                return cmp < 0
            if op == ">":
                return cmp > 0
            if op == "<=":
                return cmp <= 0
            if op == ">=":
                return cmp >= 0

        # Arithmetic operators
        nl = to_num(left_val, ctx)
        if is_error(nl):
            return nl
        nr = to_num(right_val, ctx)
        if is_error(nr):
            return nr

        if op == "+":
            return round_15(nl + nr)  # type: ignore
        if op == "-":
            return round_15(nl - nr)  # type: ignore
        if op == "*":
            return round_15(nl * nr)  # type: ignore
        if op == "/":
            if nr == 0:
                return DIV0
            return round_15(nl / nr)  # type: ignore
        if op == "^":
            try:
                res = math.pow(nl, nr)  # type: ignore
                if math.isnan(res) or math.isinf(res):
                    return NUM
                return round_15(res)
            except (ValueError, OverflowError):
                return NUM

        return VALUE

    if isinstance(node, FunctionCallNode):
        fn_name = node.name.upper()

        # Special short-circuiting / lazy evaluation for control flow functions
        if fn_name == "IF":
            if not node.args:
                return VALUE
            cond_val = evaluate_ast(node.args[0], ctx)
            if is_error(cond_val):
                return cond_val
            b = to_bool(cond_val)
            if is_error(b):
                return b
            if b:
                return evaluate_ast(node.args[1], ctx) if len(node.args) > 1 else True
            else:
                return evaluate_ast(node.args[2], ctx) if len(node.args) > 2 else False

        if fn_name == "IFERROR":
            if len(node.args) != 2:
                return VALUE
            val = evaluate_ast(node.args[0], ctx)
            if is_error(val):
                return evaluate_ast(node.args[1], ctx)
            return val

        if fn_name == "IFNA":
            if len(node.args) != 2:
                return VALUE
            val = evaluate_ast(node.args[0], ctx)
            if val == NA or (isinstance(val, str) and val.upper() == "#N/A"):
                return evaluate_ast(node.args[1], ctx)
            return val

        if fn_name == "CHOOSE":
            if len(node.args) < 2:
                return VALUE
            idx_val = evaluate_ast(node.args[0], ctx)
            if is_error(idx_val):
                return idx_val
            n = to_num(idx_val, ctx)
            if is_error(n):
                return n
            k = math.trunc(n)  # type: ignore
            if k < 1 or k >= len(node.args):
                return VALUE
            return evaluate_ast(node.args[k], ctx)

        if fn_name == "LET":
            if len(node.args) < 3 or len(node.args) % 2 == 0:
                return VALUE
            cur_ctx = ctx
            for i in range(0, len(node.args) - 1, 2):
                arg_name = node.args[i]
                if isinstance(arg_name, NameNode):
                    var_name = arg_name.name.upper()
                elif isinstance(arg_name, LiteralNode) and isinstance(arg_name.v, str):
                    var_name = arg_name.v.upper()
                else:
                    return VALUE
                val = evaluate_ast(node.args[i + 1], cur_ctx)
                if is_error(val):
                    return val
                cur_ctx = cur_ctx.with_vars({var_name: val})
            return evaluate_ast(node.args[-1], cur_ctx)

        if fn_name == "LAMBDA":
            if not node.args:
                return VALUE
            param_names: list[str] = []
            for arg_n in node.args[:-1]:
                if isinstance(arg_n, NameNode):
                    param_names.append(arg_n.name.upper())
                elif isinstance(arg_n, LiteralNode) and isinstance(arg_n.v, str):
                    param_names.append(arg_n.v.upper())
                else:
                    return VALUE
            body_ast = node.args[-1]
            closure_vars = dict(ctx.vars)

            class LambdaCallable:
                def __init__(self, p_names: list[str], b_ast: ASTNode, c_vars: dict[str, Any]):
                    self.param_names = p_names
                    self.body_ast = b_ast
                    self.closure_vars = c_vars
                    self.lambda_fn = True

                def __call__(self, *call_args: Any, ctx: EvalContext | None = None) -> Any:
                    if len(call_args) != len(self.param_names):
                        return VALUE
                    active_ctx = ctx if ctx is not None else EvalContext()
                    merged = dict(self.closure_vars)
                    for p, a in zip(self.param_names, call_args):
                        merged[p] = a
                    call_ctx = active_ctx.with_vars(merged)
                    return evaluate_ast(self.body_ast, call_ctx)

            return LambdaCallable(param_names, body_ast, closure_vars)

        # Standard eager evaluation for all other functions
        evaluated_args: list[Any] = []
        for arg_node in node.args:
            evaluated_args.append(evaluate_ast(arg_node, ctx))
        return call_function(fn_name, evaluated_args, ctx)

    return VALUE


def evaluate(formula: str, ctx: EvalContext | None = None) -> Any:
    """Parse and evaluate an Excel formula expression (with or without leading '=')."""
    clean_formula = formula.strip()
    if clean_formula.startswith("="):
        clean_formula = clean_formula[1:].strip()
    ast = parse(clean_formula)
    return evaluate_ast(ast, ctx)
