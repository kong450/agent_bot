"""Safe calculator for [CALCULATED] values.

Strong-agent rule: numbers that matter must come from code, not from LLM prose.
LLM may still show formulas, but this tool gives verifiable results the
orchestrator can append to answers.

Security: AST whitelist, no attribute access, no imports, no function defs.
Supports + - * / ** % parentheses + math.* + a few builtins (abs, round, min, max, pow).
"""
from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Any, Dict

_ALLOWED_FUNCS: Dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.FloorDiv,
    ast.Tuple,
    ast.List,
)


@dataclass
class CalcResult:
    value: Any
    label: str = "[CALCULATED]"


def safe_calculate(expression: str) -> CalcResult:
    """Evaluate arithmetic expression safely. Raises ValueError on violation."""
    expr = expression.strip()
    if not expr:
        raise ValueError("empty expression")
    if len(expr) > 500:
        raise ValueError("expression too long")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"bad syntax: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError(f"forbidden construct: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise ValueError("only math functions allowed")
            if node.keywords:
                raise ValueError("kwargs not allowed")
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_FUNCS:
            raise ValueError(f"unknown name: {node.id}")

    compiled = compile(tree, "<calc>", "eval")
    value = eval(compiled, {"__builtins__": {}}, dict(_ALLOWED_FUNCS))  # noqa: S307 - sandboxed by AST
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        raise ValueError("non-finite result")
    return CalcResult(value=value)
