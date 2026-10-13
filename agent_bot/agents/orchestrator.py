"""Strong-agent orchestrator: intent -> prompt -> LLM -> verdict -> Telegram HTML.

Pipeline (every message):
1. IntentClassifier.classify -> intent, confidence, lang
2. MemoryStore.context_text -> project_context
3. MetaPromptEngine.build_execution_prompt -> system_instruction + prompt
4. LLM.generate -> raw Markdown (plain text)
5. Post-process:
   - extract CompatibilityVerdict ([MOS] / [SHARTLI MOS] / [MOS EMAS] / [MA'LUMOT YETARLI EMAS])
   - markdown_to_telegram_html -> safe HTML
   - split_html_message -> Telegram chunks
6. Save turn to memory.

Never raises on LLM failure: falls back to Mock client once, then to plain-text
error message so Telegram handler always has something to send.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent_bot.config.constants import CompatibilityVerdict, IntentType
from agent_bot.config.settings import settings
from agent_bot.core.intent_classifier import IntentClassifier
from agent_bot.core.llm_client import BaseLLMClient, MockLLMClient
from agent_bot.core.meta_prompt import MetaPromptEngine
from agent_bot.memory.store import MemoryStore, memory as global_memory
from agent_bot.telegram.formatting import (
    markdown_to_telegram_html,
    split_html_message,
    to_plain_text,
)

logger = logging.getLogger(__name__)


async def _call_llm(llm: object, system: str, prompt: str) -> tuple[str, str]:
    """Har qanday LLM interfeysini (eski LLMResponse / yangi ModelResponse) normallashtiradi.

    Eski: generate(system, prompt) -> .text / .model
    Yangi (ModelRouter V2): generate(prompt, system_instruction=...) -> .content / .model_name
    Qaytaradi: (text, model_name). Bo'sh javobda RuntimeError.
    """
    generate = getattr(llm, "generate")
    try:
        resp = await generate(system, prompt)
    except TypeError:
        # Yangi imzo: generate(prompt, system_instruction=...)
        resp = await generate(prompt, system_instruction=system)
    text = getattr(resp, "text", None) or getattr(resp, "content", "") or ""
    model = (
        getattr(resp, "model", None)
        or getattr(resp, "model_name", None)
        or getattr(resp, "provider", None)
        or type(llm).__name__
    )
    text = str(text).strip()
    if not text:
        raise RuntimeError("LLM empty response")
    return text, str(model)


def _default_llm() -> BaseLLMClient:
    """ModelRouter (yangi imzo) -> eski ModelRouter -> Mock zanjiri. Hech qachon yiqilmaydi."""
    try:
        from agent_bot.core.model_router import ModelRouter as Router

        try:
            return Router()  # type: ignore[call-arg]
        except TypeError:
            return Router(settings)  # type: ignore[call-arg]
    except Exception:
        logger.exception("ModelRouter init failed, Mock fallback")
        return MockLLMClient()

# Orkestrator ishga tushiradigan xavfsiz tool-shartnoma:
# LLM ```calc ... ``` fence yozsa -> PythonSandbox'da yurgaziladi -> natija ilova qilinadi.
_CALC_FENCE_RE = re.compile(r"```calc\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_MAX_CALC_BLOCKS = 3

# Oqibatli amallar darvozasi (V3 §9): tasdiqsiz bajarish TAQIQLANADI
_DESTRUCTIVE_RE = re.compile(
    r"(o['’]chir|uchir|delete|formatla|to['’]lov|sotib ol|xarid qil|"
    r"deploy|serverga yukla|barchaga yubor|tokenim|parolim)",
    re.IGNORECASE,
)

# Chuqur tahlil talab qiladigan intentlar (parallel mutaxassis + QA)
_DEEP_INTENTS = {
    IntentType.ENGINEERING_ANALYSIS,
    IntentType.HARDWARE_COMPATIBILITY,
    IntentType.SCIENTIFIC_RESEARCH,
    IntentType.PRODUCT_DEVELOPMENT,
    IntentType.BUSINESS_ANALYSIS,
}


def is_destructive(text: str) -> bool:
    return _DESTRUCTIVE_RE.search(text or "") is not None


def is_complex(intent: IntentType, text: str) -> bool:
    if intent not in _DEEP_INTENTS:
        return False
    return len(text) > 120 or text.count("?") > 1 or " va " in text.lower()

_VERDICT_RE = re.compile(
    r"\[(MOS|SHARTLI MOS|MOS EMAS|MA'?LUMOT YETARLI EMAS)\]",
    re.IGNORECASE,
)


def extract_verdict(text: str) -> Optional[CompatibilityVerdict]:
    m = _VERDICT_RE.search(text or "")
    if not m:
        return None
    v = m.group(1).upper().replace("’", "'").replace("‘", "'")
    mapping = {
        "MOS": CompatibilityVerdict.COMPATIBLE,
        "SHARTLI MOS": CompatibilityVerdict.CONDITIONALLY_COMPATIBLE,
        "MOS EMAS": CompatibilityVerdict.INCOMPATIBLE,
        "MA'LUMOT YETARLI EMAS": CompatibilityVerdict.INSUFFICIENT_DATA,
    }
    return mapping.get(v)


@dataclass
class AgentResult:
    intent: IntentType
    confidence: float
    language: str
    raw_answer: str
    html: str
    chunks: List[str] = field(default_factory=list)
    plain_fallback: str = ""
    verdict: Optional[CompatibilityVerdict] = None
    model: str = ""
    calc_outputs: List[str] = field(default_factory=list)  # sandbox'da tekshirilgan natijalar
    files: List[str] = field(default_factory=list)  # yaratilgan fayllar (doc/xls/pptx)
    needs_confirmation: bool = False  # destructive gate
    deep_mode: bool = False  # parallel mutaxassislar ishladi


def _run_calc_blocks(raw: str) -> tuple[str, List[str]]:
    """LLM yozgan ```calc bloklarini sandbox'da yurgazib, natijani matnga ilova qiladi.

    Import faqat orchestrator ichida (aylanma import bo'lmasligi uchun).
    Har doim xavfsiz: PythonSandbox AST+qattiq timeout bilan himoyalangan.
    """
    from agent_bot.tools.python_sandbox import PythonSandbox

    outputs: List[str] = []
    blocks = _CALC_FENCE_RE.findall(raw or "")
    for code in blocks[:_MAX_CALC_BLOCKS]:
        res = PythonSandbox.execute_code(code.strip(), timeout_seconds=4.0)
        if res["success"]:
            outputs.append(res["output"][:1500])
        else:
            outputs.append(f"Hisobda xato: {res['output'][:300]}")
    if not outputs:
        return raw, outputs
    appendix = "\n\n## Tekshirilgan hisob [CALCULATED]\n" + "\n".join(
        f"```\n{o}\n```" for o in outputs
    )
    return raw + appendix, outputs


class AgentOrchestrator:
    """Universal agent miyasi: gate -> plan -> parallel mutaxassis -> QA -> tools.

    - Oqibatli so'rovlar LLM ga yetmasdan tasdiq darvozasida to'xtaydi.
    - Murakkab so'rovlarda 2 mutaxassis parallel ishlaydi, sintez qilinadi.
    - Muhandislik/apparat javoblari ikkinchi QA ko'zi bilan tekshiriladi.
    - ```calc bloklar sandbox'da, DOCUMENT intentda real fayl yaratiladi.
    """

    def __init__(
        self,
        llm: Optional[BaseLLMClient] = None,
        store: Optional[MemoryStore] = None,
    ):
        if llm is not None:
            self.llm = llm
        else:
            self.llm = _default_llm()
        self.store = store if store is not None else global_memory

    def _empty(self, text: str) -> AgentResult:
        return AgentResult(
            intent=IntentType.GENERAL_QUERY,
            confidence=0.0,
            language="uz",
            raw_answer=text,
            html=text,
            chunks=[text],
            plain_fallback=text,
        )

    async def handle(self, user_id: int, text: str, force: bool = False) -> AgentResult:
        text = (text or "").strip()
        if not text:
            return self._empty("Bo'sh so'rov. Savolingizni yozing.")

        # 1. Destructive gate — LLM chaqirilmasdan oldin
        if not force and is_destructive(text):
            msg = (
                "## Tasdiq kerak\n"
                "Bu so'rov **oqibatli amal** (o'chirish/to'lov/yuborish) bo'lishi mumkin.\n"
                "Bajarishdan oldin aniq tasdiqlang: pastdagi **Tasdiqlash** tugmasini bosing "
                "yoki `tasdiqlayman` deb yozing."
            )
            html = markdown_to_telegram_html(msg)
            return AgentResult(
                intent=IntentType.GENERAL_QUERY,
                confidence=1.0,
                language="uz",
                raw_answer=msg,
                html=html,
                chunks=split_html_message(html),
                plain_fallback=to_plain_text(msg),
                needs_confirmation=True,
            )

        intent, confidence, meta = IntentClassifier.classify(text)
        language = str(meta.get("language", "uz"))
        context = self.store.context_text(user_id)
        # JARVIS profili: ism va shaxsiy kontekst promptga qo'shiladi
        try:
            from agent_bot.memory.profile import load_profile, profile_line

            pline = profile_line(load_profile(user_id))
            if pline:
                context = f"{pline}\n{context}" if context else pline
        except Exception:
            logger.warning("Profil yuklanmadi")

        # 2. Murakkab so'rov -> parallel mutaxassis rejimi
        if is_complex(intent, text):
            result = await self._handle_deep(user_id, text, intent, confidence, language, context)
        else:
            result = await self._handle_single(user_id, text, intent, confidence, language, context)

        self.store.add(user_id, "user", text)
        self.store.add(user_id, "assistant", result.raw_answer[:2000])
        return result

    async def _handle_single(
        self,
        user_id: int,
        text: str,
        intent: IntentType,
        confidence: float,
        language: str,
        context: str,
    ) -> AgentResult:
        prompt_data = MetaPromptEngine.build_execution_prompt(
            intent=intent,
            user_request=text,
            project_context=context,
            language=language,
        )
        raw, model = await self._generate_with_fallback(
            prompt_data["system_instruction"], prompt_data["prompt"]
        )
        # 3. QA pass (muhandislik/apparat uchun ikkinchi ko'z)
        if intent in (IntentType.ENGINEERING_ANALYSIS, IntentType.HARDWARE_COMPATIBILITY):
            raw = await self._qa_review(raw, model)
        raw, calc_outputs = _run_calc_blocks(raw)
        files = self._maybe_build_file(intent, text, raw)
        verdict = extract_verdict(raw) if intent == IntentType.HARDWARE_COMPATIBILITY else None
        html = markdown_to_telegram_html(raw)
        return AgentResult(
            intent=intent,
            confidence=confidence,
            language=language,
            raw_answer=raw,
            html=html,
            chunks=split_html_message(html),
            plain_fallback=to_plain_text(raw),
            verdict=verdict,
            model=model,
            calc_outputs=calc_outputs,
            files=files,
        )

    async def _handle_deep(
        self,
        user_id: int,
        text: str,
        intent: IntentType,
        confidence: float,
        language: str,
        context: str,
    ) -> AgentResult:
        """2 mutaxassis (tahlil + risk/muqobil) parallel, so'ng sintez."""
        analyst_prompt = MetaPromptEngine.build_execution_prompt(
            intent=intent, user_request=text, project_context=context, language=language
        )
        critic_prompt = MetaPromptEngine.build_execution_prompt(
            intent=IntentType.GENERAL_QUERY,
            user_request=(
                f"Quyidagi so'rovga 2-3 ta MUQOBIL yechim va ularning xavfini qisqa yoz:\n{text}"
            ),
            project_context=context,
            language=language,
        )
        try:
            (raw_main, model), (raw_alt, _) = await asyncio.gather(
                self._generate_with_fallback(
                    analyst_prompt["system_instruction"], analyst_prompt["prompt"]
                ),
                self._generate_with_fallback(
                    critic_prompt["system_instruction"], critic_prompt["prompt"]
                ),
            )
        except Exception:
            logger.exception("Deep parallel failed, single fallback")
            return await self._handle_single(user_id, text, intent, confidence, language, context)

        raw = (
            f"{raw_main}\n\n## Muqobil qarashlar\n{raw_alt}\n\n"
            f"> [Sintez: asosiy tahlil + muqobil variantlar birlashtirildi]"
        )
        raw = await self._qa_review(raw, model)
        raw, calc_outputs = _run_calc_blocks(raw)
        files = self._maybe_build_file(intent, text, raw)
        verdict = extract_verdict(raw) if intent == IntentType.HARDWARE_COMPATIBILITY else None
        html = markdown_to_telegram_html(raw)
        return AgentResult(
            intent=intent,
            confidence=min(1.0, confidence + 0.1),
            language=language,
            raw_answer=raw,
            html=html,
            chunks=split_html_message(html),
            plain_fallback=to_plain_text(raw),
            verdict=verdict,
            model=model,
            calc_outputs=calc_outputs,
            files=files,
            deep_mode=True,
        )

    async def _qa_review(self, raw: str, model: str) -> str:
        """Ikkinchi model ko'zi: xato topilsa tuzatish ilova qilinadi. Har doim xavfsiz."""
        if isinstance(self.llm, MockLLMClient) or len(raw) < 200:
            return raw
        try:
            note, _ = await _call_llm(
                self.llm,
                "Sen QA reviewer. Faqat qisqa javob ber.",
                f"Quyidagi texnik javobda formula/birlik/moslik xatosi bo'lsa, "
                f"2 jumlada tuzatish yoz. Xato yo'q bo'lsa faqat 'OK' yoz:\n\n{raw[:2500]}",
            )
            note = (note or "").strip()
            if note and note.upper() != "OK" and len(note) > 10:
                return raw + f"\n\n> **QA tekshiruvi:** {note[:800]}"
        except Exception:
            logger.warning("QA pass skipped (model error)")
        return raw

    def _maybe_build_file(self, intent: IntentType, text: str, raw: str) -> List[str]:
        """DOCUMENT intentda real fayl yaratadi. Xatoda bo'sh ro'yxat (matn baribir yuboriladi)."""
        if intent != IntentType.DOCUMENT_GENERATION:
            return []
        try:
            from agent_bot.tools.file_generator import FileGenerator

            out_dir = Path(settings.data_dir) / "documents"
            fg = FileGenerator(out_dir)
            sections = self._split_sections(raw)
            title = text[:60] or "Agent Bot hujjati"
            kind = "xlsx" if "xlsx" in text.lower() or "excel" in text.lower() else "docx"
            if kind == "xlsx":
                rows = [[s.get("title", ""), s.get("content", "")[:80]] for s in sections]
                path = fg.generate_xlsx("Hisobot", ["Bo'lim", "Tarkib"], rows or [["-", "-"]])
            else:
                path = fg.generate_docx(title, sections or [{"title": "", "content": raw[:3000]}])
            return [str(path)]
        except Exception:
            logger.exception("File generation failed")
            return []

    @staticmethod
    def _split_sections(raw: str) -> List[dict]:
        sections: List[dict] = []
        current = {"title": "", "content": ""}
        for line in (raw or "").split("\n"):
            h = re.match(r"^#{1,3}\s+(.+)", line.strip())
            if h:
                if current["content"].strip():
                    sections.append(current)
                current = {"title": h.group(1).strip(), "content": ""}
            else:
                current["content"] += line + "\n"
        if current["content"].strip() or current["title"]:
            sections.append(current)
        return sections[:12]

    async def _generate_with_fallback(self, system: str, prompt: str) -> tuple[str, str]:
        try:
            return await _call_llm(self.llm, system, prompt)
        except Exception as exc:
            logger.exception("Primary LLM failed, trying Mock fallback")
            if isinstance(self.llm, MockLLMClient):
                return (
                    "## Xatolik\nXizmat vaqtincha ishlamayapti. Keyinroq qayta urining.",
                    "error",
                )
            try:
                resp = await MockLLMClient().generate(system, prompt)
                return resp.text + f"\n\n> Eslatma: asosiy model xatosi ({exc}), mock javob.", resp.model
            except Exception:
                return (
                    "## Xatolik\nXizmat vaqtincha ishlamayapti. Keyinroq qayta urining.",
                    "error",
                )
