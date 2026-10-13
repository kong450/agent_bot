"""Autonomous Self-Correction and Execution Loop for Math and Code."""
import logging
from typing import Dict, Any, Tuple
from agent_bot.tools.python_sandbox import PythonSandbox

logger = logging.getLogger(__name__)

class SelfCorrectionLoop:
    """Xato yuz bersa, o'zini o'zi tahlil qilib, tuzatib qayta ishlovchi avtonom zanjir."""

    @classmethod
    async def run_with_reflection(
        cls,
        code_generator_fn,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """Kodni sandboxda yurgazadi, xato bo'lsa LLM ga xatoni ko'rsatib qayta yozdiradi."""
        error_context = ""

        for attempt in range(max_retries + 1):
            code = await code_generator_fn(error_context=error_context)
            res = PythonSandbox.execute_code(code)

            if res["success"]:
                return {
                    "success": True,
                    "output": res["output"],
                    "code": code,
                    "attempts": attempt + 1
                }

            # Agar xato bo'lsa, xatoni kontekstga qo'shib keyingi urinishga uzatadi
            logger.info(f"Self-Correction urinishi {attempt + 1}: Xato: {res['output']}")
            error_context = f"Avvalgi kodda quyidagi ijro xatosi yuz berdi:\n{res['output']}\nIltimos, ushbu xatoni bartaraf etgan holda kodni to'liq qayta yozing."

        return {
            "success": False,
            "output": res["output"],
            "code": code,
            "attempts": max_retries + 1
        }
