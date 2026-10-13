"""Robust, isolated Python Sandbox with strict subprocess execution and hard timeouts."""
import ast
import sys
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

class PythonSandbox:
    """ASUS TUF A16 (16GB RAM) resurslarini asrash uchun izolyatsiyalangan Sandbox.
    
    Har bir kod alohida izolyatsiyalangan subprocess ichida yurgaziladi:
    - Cheksiz tsikl (while True) qotirib qo'ya olmaydi (hard timeout).
    - Asosiy bot jarayonining xotirasi (RAM) buzilmaydi.
    - Xavfli tizim buyruqlari bloklanadi.
    """

    FORBIDDEN_KEYWORDS = [
        "import os", "import sys", "subprocess", "shutil",
        "eval(", "breakpoint", "input("
    ]

    # AST darajasida qat'iy taqiqlar (substring bypass'ga chidamli)
    _ALLOWED_IMPORTS = {"math", "statistics", "numpy", "random", "datetime", "json", "re"}
    _DENY_CALLS = {
        "eval", "exec", "compile", "open", "__import__",
        "getattr", "setattr", "delattr", "hasattr",
        "breakpoint", "input", "exit", "quit", "help",
    }
    _DENY_ATTRS = {
        "__class__", "__base__", "__bases__", "__subclasses__",
        "__dict__", "__globals__", "__code__", "__closure__",
        "gi_frame", "gi_code", "f_locals", "f_globals",
    }
    _MAX_CODE_LEN = 6000
    _MAX_OUTPUT_LEN = 6000

    HEADER_CODE = """# -*- coding: utf-8 -*-
import sys
import math
import statistics

_ALLOWED_MODULES = {"math", "statistics", "numpy", "random", "datetime", "json", "re"}

def _safe_import(name, *args, **kwargs):
    base_name = name.split('.')[0]
    if base_name in _ALLOWED_MODULES:
        return __orig_import__(name, *args, **kwargs)
    raise ImportError(f"XAVFSIZLIK: '{name}' modulini ishlatish taqiqlangan.")

__orig_import__ = __builtins__.__import__
__builtins__.__import__ = _safe_import

try:
    import numpy as np
except ImportError:
    pass
"""

    @classmethod
    def _static_check(cls, code: str) -> str | None:
        """AST orqali xavfli konstruksiyalarni tutadi. Ruxsat bo'lsa None, aks holda sabab."""
        if len(code) > cls._MAX_CODE_LEN:
            return f"Kod hajmi limiti ({cls._MAX_CODE_LEN}) oshdi."
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return f"Sintaksis xatosi: {exc}"
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [(node.module or "")]
                )
                for n in names:
                    base = n.split(".")[0]
                    if base not in cls._ALLOWED_IMPORTS:
                        return f"XAVFSIZLIK: '{n}' import taqiqlangan."
            elif isinstance(node, ast.Call):
                f = node.func
                fname = ""
                if isinstance(f, ast.Name):
                    fname = f.id
                elif isinstance(f, ast.Attribute):
                    fname = f.attr
                if fname in cls._DENY_CALLS:
                    return f"XAVFSIZLIK: '{fname}(...)' chaqiruv taqiqlangan."
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("_") or node.attr in cls._DENY_ATTRS:
                    return f"XAVFSIZLIK: '.{node.attr}' atribut taqiqlangan."
            elif isinstance(node, ast.Name):
                if node.id in {"__import__", "__builtins__", "__class__"}:
                    return f"XAVFSIZLIK: '{node.id}' ishlatish taqiqlangan."
        return None

    @classmethod
    def execute_code(cls, code: str, timeout_seconds: float = 4.0) -> Dict[str, Any]:
        """Kodlarni alohida jarayonda qat'iy vaqt chegarasi bilan xavfsiz yurgazadi."""
        # 0. AST darajasida qat'iy tekshiruv (bypass'ga chidamli)
        reason = cls._static_check(code)
        if reason:
            return {"success": False, "output": f"XAVFSIZLIK CHEKLOVI: {reason}", "execution_time_ms": 0.0}
        # 1. Statik xavfsizlik tekshiruvi
        for kw in cls.FORBIDDEN_KEYWORDS:
            if kw in code:
                return {
                    "success": False,
                    "output": f"XAVFSIZLIK CHEKLOVI: '{kw}' ishlatish qat'iyan taqiqlangan.",
                    "execution_time_ms": 0.0
                }

        # 2. Vaqtinchalik faylga yozish
        wrapped_code = f"{cls.HEADER_CODE}\n\n{code}"
        with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(wrapped_code)

        start_time = time.time()
        success = True
        output = ""

        try:
            # 3. Subprocess orqali qat'iy timeout bilan ishga tushirish
            result = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                encoding="utf-8",
                errors="replace"
            )
            elapsed_ms = (time.time() - start_time) * 1000

            if result.returncode == 0:
                output = result.stdout.strip()[: cls._MAX_OUTPUT_LEN]
            else:
                success = False
                output = f"Xatolik yuz berdi:\n{result.stderr.strip()[: cls._MAX_OUTPUT_LEN]}"

        except subprocess.TimeoutExpired:
            elapsed_ms = timeout_seconds * 1000
            success = False
            output = f"VAQT CHEKLOVI: Kod ijrosi {timeout_seconds} soniyadan oshib ketdi va xavfsizlik sababli to'xtatildi (Cheksiz tsikl aniqlandi)."
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            success = False
            output = f"Tizim xatoligi: {str(e)}"
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass

        return {
            "success": success,
            "output": output,
            "execution_time_ms": round(elapsed_ms, 2)
        }
