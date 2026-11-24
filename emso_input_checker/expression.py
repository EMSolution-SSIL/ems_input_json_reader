"""Small, safe subset of the exprtk arithmetic used by EMSolution inputs.

EMSInputJson.h evaluates selected values with evaluateExpression<double>(),
which delegates to exprtk in basic/my_math.h. Unknown syntax is reported as
unverified; this module never executes input as Python code.
"""

from __future__ import annotations

import ast
import math
import operator


class UnsupportedExpression(ValueError):
    """Expression syntax outside the supported arithmetic subset."""


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {
    "abs": abs,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "ln": math.log,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "floor": math.floor,
    "ceil": math.ceil,
    "min": min,
    "max": max,
    "pow": pow,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}


def arithmetic(value: object) -> float:
    """Return a finite number from JSON number or supported exprtk expression."""
    if isinstance(value, bool) or value is None:
        raise ValueError("数値または数値式が必要です")
    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        if len(value) > 512:
            raise UnsupportedExpression("数値式が長すぎます")
        try:
            tree = ast.parse(value.replace("^", "**"), mode="eval")
        except SyntaxError as exc:
            raise UnsupportedExpression("対応していない数値式です") from exc
        result = _node(tree.body)
    else:
        raise ValueError("数値または数値式が必要です")
    if not math.isfinite(result):
        raise ValueError("有限の数値が必要です")
    return result


def _node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id.lower() in _CONSTANTS:
        return _CONSTANTS[node.id.lower()]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        try:
            return float(_BINARY[type(node.op)](_node(node.left), _node(node.right)))
        except (ArithmeticError, OverflowError, ValueError) as exc:
            raise ValueError("数値式を計算できません") from exc
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        name = node.func.id.lower()
        if name in _FUNCTIONS and len(node.args) <= 8:
            try:
                return float(_FUNCTIONS[name](*(_node(arg) for arg in node.args)))
            except (ArithmeticError, OverflowError, ValueError, TypeError) as exc:
                raise ValueError("数値式を計算できません") from exc
    raise UnsupportedExpression("対応していない数値式です")
