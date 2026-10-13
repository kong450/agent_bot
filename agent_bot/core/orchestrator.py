"""Master Orchestrator coordinating zero-command intent, routing, agents, vision, and memory."""
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path

from agent_bot.config.settings import Settings
from agent_bot.config.constants import IntentType, VerificationLevel
from agent_bot.core.model_router import ModelRouter
from agent_bot.core.intent_classifier import IntentClassifier
from agent_bot.core.meta_prompt import MetaPromptEngine
from agent_bot.memory.stores import SessionStore, ProjectStore
from agent_bot.memory.knowledge_store import UserKnowledgeStore
from agent_bot.tools.file_generator import FileGenerator
from agent_bot.tools.vision_analyzer import VisionAnalyzer
from agent_bot.agents.domain_agents import (
    AgentResult, HardwareCompatibilityAgent, EngineeringAgent, DocumentAgent
)

logger = logging.getLogger(__name__)

class OrchestrationResult:
    def __init__(
        self,
        intent: IntentType,
        summary: str,
        artifacts: List[str] = None,
        verification_level: VerificationLevel = VerificationLevel.CALCULATED,
        requires_approval: bool = False,
        approval_id: str = "",
        details: Dict[str, Any] = None
    ):
        self.intent = intent
        self.summary = summary
        self.artifacts = artifacts or []
        self.verification_level = verification_level
        self.requires_approval = requires_approval
        self.approval_id = approval_id
        self.details = details or {}

class MasterOrchestrator:
    """Agent Bot (JARVIS-darajali intellektual boshqaruvchi)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.router = ModelRouter(settings)
        self.session_store = SessionStore(max_history=settings.max_history_length)
        self.project_store = ProjectStore(settings.data_dir)
        self.knowledge_store = UserKnowledgeStore(settings.data_dir)
        self.file_generator = FileGenerator(settings.data_dir / "documents")
        self.vision_analyzer = VisionAnalyzer(self.router._gemini_client)

        # Mutaxassis agentlar klasteri
        self.agents = {
            IntentType.HARDWARE_COMPATIBILITY: HardwareCompatibilityAgent(self.router),
            IntentType.ENGINEERING_ANALYSIS: EngineeringAgent(self.router),
            IntentType.DOCUMENT_GENERATION: DocumentAgent(self.router, self.file_generator),
        }

    async def process_user_image(
        self,
        user_id: int,
        image_path: Path,
        caption: str = ""
    ) -> OrchestrationResult:
        """Tasvir, sxema yoki skrinshotni ko'rib tahlil qilish (Vision Pipeline)."""
        prompt = caption if caption else "Ushbu tasvirni, undagi komponentlar, sxemalar va texnik parametrlarni to'liq tahlil qiling."
        vision_res = await self.vision_analyzer.analyze_image(image_path, user_prompt=prompt)

        summary = (
            f"👁️ **JARVIS VISION — TASVIR TAHLILI**\n\n"
            f"{vision_res['text']}\n\n"
            f"🛡️ **Model:** `{vision_res.get('model', 'Gemini 3.8 Vision')}`"
        )
        self.session_store.add_message(user_id, "user", f"[Tasvir yuborildi: {image_path.name}] {caption}")
        self.session_store.add_message(user_id, "assistant", summary)

        return OrchestrationResult(
            intent=IntentType.GENERAL_QUERY,
            summary=summary,
            verification_level=VerificationLevel.VERIFIED
        )

    async def process_user_message(
        self,
        user_id: int,
        text: str,
        progress_callback: Optional[Callable[[int, str], Any]] = None
    ) -> OrchestrationResult:
        """Foydalanuvchi xabarini qabul qilish, tahlil qilish, ijro va verifikatsiya bosqichi."""
        start_time = time.time()

        # 1. Ruxsatni tekshirish
        if not self.settings.is_user_allowed(user_id):
            return OrchestrationResult(
                intent=IntentType.GENERAL_QUERY,
                summary="⛔ Kechirasiz, ushbu botdan foydalanish uchun sizga ruxsat berilmagan.",
                verification_level=VerificationLevel.VERIFIED
            )

        # 2. Xavfli / Destruktiv amallarni tekshirish (Human-in-the-Loop)
        text_lower = text.lower()
        if any(w in text_lower for w in ["o'chir", "delete", "tozala", "hamma faylni yo'qot"]):
            approval_id = f"appr_{user_id}_{int(time.time())}"
            return OrchestrationResult(
                intent=IntentType.GENERAL_QUERY,
                summary=(
                    "⚠️ **DIQQAT: DESTRUKTIV AMAL ANIQLANDI!**\n\n"
                    "Siz ma'lumotlarni o'chirish yoki tozalash amalini so'radingiz. "
                    "Bu amal qaytarilmas oqibatlarga olib kelishi mumkin.\n"
                    "Haqiqatan ham davom ettirishni xohlaysizmi?"
                ),
                requires_approval=True,
                approval_id=approval_id,
                verification_level=VerificationLevel.VERIFIED
            )

        if progress_callback:
            await progress_callback(20, "Fikrlar va niyatlar tahlil qilinmoqda...")

        # 3. Buyruqsiz niyatni aniqlash
        intent, confidence, meta = IntentClassifier.classify(text)
        self.session_store.add_message(user_id, "user", text)

        # 4. Foydalanuvchi faktlarini uzoq muddatli xotiraga olish
        if any(k in text_lower for k in ["mening", "men", "ishlataman", "loyiham"]):
            self.knowledge_store.add_fact(user_id, "context", text[:120])

        # 5. Oldingi loyihani davom ettirish (Continue Project)
        if intent == IntentType.CONTINUE_PROJECT:
            if progress_callback:
                await progress_callback(50, "Oldingi loyiha xotirasi yuklanmoqda...")

            proj = self.project_store.find_latest_project_for_user(user_id)
            if not proj:
                proj = self.project_store.create_project(user_id, "Yangi Muhandislik Loyihasi")

            proj.version += 1
            proj.requirements.append(text)
            self.project_store.save_project(proj)

            summary = (
                f"🔄 **OLDINGI LOYIHA YANGILANDI**\n\n"
                f"• Loyiha: **{proj.title}** (v{proj.version})\n"
                f"• Kiritilgan o'zgarish: `{text}`\n"
                f"• Loyiha xotirasi muvaffaqiyatli saqlandi."
            )
            self.session_store.add_message(user_id, "assistant", summary)
            return OrchestrationResult(
                intent=intent,
                summary=summary,
                verification_level=VerificationLevel.VERIFIED
            )

        # 6. Maxsus agentga yo'naltirish
        agent = self.agents.get(intent)
        if agent:
            if progress_callback:
                await progress_callback(60, f"{agent.name} ishga tushirildi...")

            res: AgentResult = await agent.execute(text, context={"user_id": user_id, "language": meta.get("language", "uz")})
            self.session_store.add_message(user_id, "assistant", res.summary)

            return OrchestrationResult(
                intent=intent,
                summary=res.summary,
                artifacts=res.artifacts,
                verification_level=res.verification_level,
                details=res.details
            )

        # 7. Umumiy savol / Universal Sintez (Dual-Brain Fallback)
        if progress_callback:
            await progress_callback(70, "Universal intellekt xulosasi shakllanmoqda...")

        user_memory_context = self.knowledge_store.format_user_context(user_id)
        combined_context = f"{user_memory_context}\n\n{self.session_store.format_history_for_prompt(user_id)}"

        prompt_data = MetaPromptEngine.build_execution_prompt(
            intent=IntentType.GENERAL_QUERY,
            user_request=text,
            project_context=combined_context,
            language=meta.get("language", "uz")
        )

        model_res = await self.router.generate(
            prompt=prompt_data["prompt"],
            system_instruction=prompt_data["system_instruction"]
        )

        self.session_store.add_message(user_id, "assistant", model_res.content)
        return OrchestrationResult(
            intent=IntentType.GENERAL_QUERY,
            summary=model_res.content,
            verification_level=VerificationLevel.ESTIMATED
        )
