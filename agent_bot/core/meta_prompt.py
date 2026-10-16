"""Meta-Prompt Engine that loads structured prompts from templates or fallback constants."""
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional
from agent_bot.config.constants import IntentType
from agent_bot.config.settings import settings

# Canonical tool registry — promptdagi "ruxsat etilgan asboblar" endi hardcode emas
AUTHORIZED_TOOLS: List[str] = [
    "python_sandbox(calc: math/statistics/numpy hisoblar)",
    "file_generator(docx/xlsx/pptx yaratish)",
    "memory(short-term suhbat + project xotirasi)",
]


@lru_cache(maxsize=16)
def _read_prompt_file(path_str: str) -> str:
    return Path(path_str).read_text(encoding="utf-8")

class MetaPromptEngine:
    """Agent Bot uchun dinamik va faylga asoslangan promptlar generatori."""

    PROMPTS_DIR = settings.base_dir / "prompts" / "system_prompts"

    PROMPT_FILE_MAP = {
        IntentType.HARDWARE_COMPATIBILITY: "hardware_compat.txt",
        IntentType.ENGINEERING_ANALYSIS: "engineering.txt",
        IntentType.SCIENTIFIC_RESEARCH: "scientific.txt",
        IntentType.SCIENTIFIC_WRITING: "scientific.txt",
    }

    ROLE_DESCRIPTIONS: Dict[IntentType, str] = {
        IntentType.ENGINEERING_ANALYSIS: (
            "Bosh Muhandis va Fizikaviy Tizimlar Eksperti (Principal Systems Engineer)."
        ),
        IntentType.HARDWARE_COMPATIBILITY: (
            "Uskunalar Arxitektori va Elektronika Muhandisi (Hardware Integration Architect)."
        ),
        IntentType.SCIENTIFIC_RESEARCH: (
            "Katta Ilmiy Xodim va Xalqaro Tadqiqotchi (Senior Research Scientist)."
        ),
        IntentType.SCIENTIFIC_WRITING: (
            "Ilmiy Muharrir va Maqola Muallifi (Academic Editor & Scientific Author)."
        ),
        IntentType.PRODUCT_DEVELOPMENT: (
            "Sanoat Dizayni va Tizimlar Muhandisligi Rahbari (Product Design Director)."
        ),
        IntentType.BUSINESS_ANALYSIS: (
            "Bosh Moliyaviy Tahlilchi (Chief Financial Officer & Strategist)."
        ),
        IntentType.DOCUMENT_GENERATION: (
            "Professional Texnik Hujjat Yozuvchi va Ekspert (Technical Documentation Specialist)."
        ),
        IntentType.SOFTWARE_DEVELOPMENT: (
            "Bosh Dasturiy Arxitektor va Xavfsizlik Muhandisi (Principal Software Architect)."
        ),
        IntentType.GENERAL_QUERY: (
            "Agent Bot Universal Intellekti (Autonomous Intelligence)."
        )
    }

    @classmethod
    def load_prompt_template(cls, intent: IntentType) -> str:
        """Prompt faylini diskdan yuklaydi, agar mavjud bo'lmasa standartini oladi."""
        filename = cls.PROMPT_FILE_MAP.get(intent)
        if filename:
            file_path = cls.PROMPTS_DIR / filename
            if file_path.exists():
                return _read_prompt_file(str(file_path))

        # Master fallback: avval ixcham runtime master (arzor + fokusli).
        # MASTER_PROMPT_V3.md — to'liq dev-spec, runtime'da verbatim ishlatilmaydi
        # (22KB, ichida developer'ga yo'riqnoma bor); kerak bo'lsa get_full_spec() bilan olinadi.
        for master_name in ("master_system_prompt.txt", "MASTER_PROMPT_V3.md"):
            master_path = cls.PROMPTS_DIR / master_name
            if master_path.exists():
                return _read_prompt_file(str(master_path))

        return cls.ROLE_DESCRIPTIONS.get(intent, cls.ROLE_DESCRIPTIONS[IntentType.GENERAL_QUERY])

    @classmethod
    def get_full_spec(cls) -> str:
        """MASTER_PROMPT_V3.md to'liq matni (murakkab rejalar uchun opt-in)."""
        v3 = cls.PROMPTS_DIR / "MASTER_PROMPT_V3.md"
        if v3.exists():
            return _read_prompt_file(str(v3))
        return ""

    @classmethod
    def build_execution_prompt(
        cls,
        intent: IntentType,
        user_request: str,
        project_context: str = "",
        authorized_tools: Optional[List[str]] = None,
        language: str = "uz"
    ) -> Dict[str, str]:
        """Tizim ko'rsatmasi va strukturalangan promptni shakllantiradi."""
        role_or_template = cls.load_prompt_template(intent)
        tools_str = ", ".join(authorized_tools) if authorized_tools else ", ".join(AUTHORIZED_TOOLS)

        system_instruction = (
            f"SYSTEM ROLE:\n{role_or_template}\n\n"
            f"LANGUAGE DIRECTIVE: Foydalanuvchining tilida javob bering ('{language}'). O'zbek (lotin/kirill), rus va ingliz tillarini to'liq qo'llab-quvvatlang.\n"
            f"ASOSIY QOIDALAR:\n"
            f"1. Tabiiy, aqlli, samimiy va jonli yordamchi (JARVIS) kabi erkin muloqot qiling.\n"
            f"2. Oddiy salomlashuv yoki suhbatlarda hech qanday majburiy qolip, sun'iy sarlavhalar (masalan 'Asosiy xulosa', 'Texnik tahlil', 'Xavf va chegaralar') yoki bo'sh jadvallarni CHIQARMANG — insoniy, do'stona va erkin suhbatlashing.\n"
            f"3. Aniq texnik, ilmiy, hisob-kitob yoki amaliy topshiriq berilganda, masalani chuqur, mustaqil va yakuniy natijagacha bajaring (hisob-kitoblar, hujjat, kod, qidiruv).\n"
            f"4. Faktlarni soxtalashtirmang, muhim hisob-kitoblarni ```calc bilan tekshiring.\n"
            f"FORMAT DIRECTIVE (Telegram-safe plain-text Markdown):\n"
            f"- Faqat plain-text Markdown yozing, HTML teg yozmang.\n"
            f"- Ruxsat: # sarlavha, **qalin**, *og'ma*, ~~o'chirilgan~~, `kod`, ```blok```, "
            f"[matn](https://...), > iqtibos, - ro'yxat, | jadval |.\n"
            f"- Bot matnni avtomatik Telegram HTML ga o'giradi, shuning uchun escape (\\*, \\_) qilmang.\n"
            f"- Jadval: pipe-notatsiya (| A | B | + |---|\n"
            f"  separator), kataklar QISQA (har biri 15 belgidan kam) — mobil ekranga sig'ishi uchun.\n"
            f"FORMULA DIRECTIVE (docx-aniq notatsiya — LaTeX/rasm emas, oddiy matn):\n"
            f"- Daraja: x^2, 10^-3, e^{{i*pi}} | Indeks: x_1, a_{{max}} | "
            f"Ildiz: sqrt(x) | Kasr: (a+b)/c | Yunon: pi, alpha.\n"
            f"CALC DIRECTIVE (tekshiriladigan hisob):\n"
            f"- Muhim sonni qo'lda taxmin qilmang: hisobni ```calc fence ichida yozing, "
            f"bot uni sandbox'da yurgazib natijani javobga [CALCULATED] bilan ilova qiladi.\n"
            f"- ```calc ichida faqat math/statistics/numpy + print ishlatiladi (import os/sys taqiqlangan)."
        )

        if intent == IntentType.GENERAL_QUERY:
            structured_prompt = (
                f"[FOYDALANUVCHI XABARI]\n{user_request}\n\n"
                f"[LOYIHA KONTEKSTI]\n{project_context if project_context else 'Yangi sessiya.'}\n\n"
                f"[KO'RSATMA]\nFoydalanuvchi bilan tabiiy, samimiy, aqlli va jonli yordamchi (JARVIS) kabi erkin suhbatlashing. Majburiy sarlavhalar, bo'sh hisob-kitoblar yoki sun'iy qoliplarni aslo ishlatmang. Foydalanuvchining so'ziga mos, samimiy va insondek javob bering."
            )
        else:
            structured_prompt = (
                f"[VAZIFA / MAQSAD]\nFoydalanuvchi bergan topshiriq va unga aloqador barcha ishlarni to'liq, mustaqil va yakuniy natijagacha bajaring. Ruxsat so'rab to'xtab qolmang, barcha hisoblar, hujjatlar va yechimlarni to'liq taqdim eting.\n\n"
                f"[FOYDALANUVCHI SO'ROVI]\n{user_request}\n\n"
                f"[LOYIHA KONTEKSTI]\n{project_context if project_context else 'Yangi mustaqil sessiya.'}\n\n"
                f"[RUXSAT ETILGAN ASBOBLAR]\n{tools_str}\n\n"
                f"[TALAB QILINADIGAN CHIQISH STRUKTURASI]\n"
                f"Vazifaga mos holda professional tahlil, aniq hisob-kitoblar va yakuniy amaliy yechim taqdim eting."
            )

        return {
            "system_instruction": system_instruction,
            "prompt": structured_prompt
        }
