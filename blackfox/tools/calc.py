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
        result = _ev(ast.parse(expression, mode="eval"))
        if not math.isfinite(result):
            raise ValueError("result is not finite")
        return {"expression": expression, "result": result}
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError) as e:
        return {"error": str(e) or "invalid expression"}



@tool("physics")
def calculate_batch(expressions: list[str]) -> dict:
    """Evaluate up to 20 independent arithmetic expressions in one call. Each result
    includes its expression or an error; use calculate syntax and SI constants."""
    if not 1 <= len(expressions) <= 20:
        return {"error": "provide between 1 and 20 expressions"}
    return {"results": [calculate(expression) if isinstance(expression, str)
                        else {"error": "expression must be a string"} for expression in expressions]}


# Each unit maps to (dimension, scale to SI, offset to SI). Temperature offsets
# apply only to absolute temperatures, not temperature differences.
_UNITS = {
    "m": ("length", 1, 0), "km": ("length", 1000, 0), "cm": ("length", .01, 0),
    "mm": ("length", .001, 0), "ft": ("length", .3048, 0), "in": ("length", .0254, 0),
    "kg": ("mass", 1, 0), "g": ("mass", .001, 0), "lb": ("mass", .45359237, 0),
    "s": ("time", 1, 0), "min": ("time", 60, 0), "h": ("time", 3600, 0),
    "day": ("time", 86400, 0),
    "Pa": ("pressure", 1, 0), "kPa": ("pressure", 1000, 0),
    "bar": ("pressure", 100000, 0), "atm": ("pressure", 101325, 0),
    "psi": ("pressure", 6894.757293168, 0),
    "K": ("temperature", 1, 0), "C": ("temperature", 1, 273.15),
    "F": ("temperature", 5/9, 255.3722222222222),
    "J": ("energy", 1, 0), "kJ": ("energy", 1000, 0), "MJ": ("energy", 1e6, 0),
    "Wh": ("energy", 3600, 0), "kWh": ("energy", 3.6e6, 0),
    "W": ("power", 1, 0), "kW": ("power", 1000, 0),
    "m/s": ("speed", 1, 0), "km/h": ("speed", 1/3.6, 0), "mph": ("speed", .44704, 0),
    "m/s2": ("acceleration", 1, 0), "g0": ("acceleration", G0, 0),
    "m2": ("area", 1, 0), "ft2": ("area", .09290304, 0),
    "m3": ("volume", 1, 0), "L": ("volume", .001, 0),
}


@tool("physics")
def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """Convert compatible units. Case-sensitive units: m, km, cm, mm, ft, in; kg, g,
    lb; s, min, h, day; Pa, kPa, bar, atm, psi; K, C, F (absolute temperatures);
    J, kJ, MJ, Wh, kWh; W, kW; m/s, km/h, mph; m/s2, g0; m2, ft2; m3, L."""
    if from_unit not in _UNITS or to_unit not in _UNITS:
        return {"error": "unknown unit; see convert_units description for supported units"}
    source, target = _UNITS[from_unit], _UNITS[to_unit]
    if source[0] != target[0]:
        return {"error": "units have incompatible dimensions"}
    if not math.isfinite(value):
        return {"error": "value must be finite"}
    si = value * source[1] + source[2]
    if source[0] == "temperature" and si < 0:
        return {"error": "temperature cannot be below absolute zero"}
    result = (si - target[2]) / target[1]
    if not math.isfinite(result):
        return {"error": "result is not finite"}
    return {"value": value, "from_unit": from_unit, "to_unit": to_unit, "result": result}
