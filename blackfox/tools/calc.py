"""A safe arithmetic calculator (no eval): numbers, + - * / ** %, parentheses,
math functions and constants."""

import ast
import math
import operator

from ..physics.constants import G0, SIGMA
from .registry import tool

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: math.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
        ast.USub: operator.neg, ast.UAdd: operator.pos}
_FUNCS = {n: getattr(math, n) for n in ("sqrt", "exp", "log", "log10", "sin", "cos", "tan", "asin", "acos",
                                        "atan", "atan2", "radians", "degrees", "hypot", "pow", "fabs")}
_FUNCS.update(abs=abs, min=min, max=max, round=round)
_CONSTS = {"pi": math.pi, "e": math.e, "g0": G0, "sigma": SIGMA}


def _ev(node):
    if isinstance(node, ast.Expression):
        return _ev(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)  # floats only: no runaway big-int arithmetic
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _ev(node.left), _ev(node.right)
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_ev(node.operand))
    if isinstance(node, ast.Name) and node.id in _CONSTS:
        return _CONSTS[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
        return _FUNCS[node.func.id](*[_ev(a) for a in node.args])
    raise ValueError("unsupported expression")


@tool("physics")
def calculate(expression: str) -> dict:
    """Evaluate an arithmetic expression, e.g. 'sqrt(2*132/g0)'. Supports + - * / ** %,
    sqrt, exp, log, log10, trig, radians, degrees, hypot, abs, min, max, round and the
    constants pi, e, g0 (9.80665), sigma (Stefan-Boltzmann)."""
    if len(expression) > 300:
        return {"error": "expression too long"}
    try:
        return {"expression": expression, "result": _ev(ast.parse(expression, mode="eval"))}
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError) as e:
        return {"error": str(e) or "invalid expression"}
