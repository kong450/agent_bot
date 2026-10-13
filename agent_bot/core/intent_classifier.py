"""Commandless intent classifier for incoming natural language requests."""
import re
from typing import Tuple, Dict, Any
from agent_bot.config.constants import IntentType

class IntentClassifier:
    """Foydalanuvchi xabarining niyatini (sohasini) avtomatik aniqlovchi modul."""

    KEYWORDS = {
        IntentType.HARDWARE_COMPATIBILITY: [
            "mos", "moslik", "ulanadimi", "mos keladimi", "mos tushadimi", "to'g'ri keladimi",
            "voltage", "kuchlanish", "amper", "tok", "volt", "pinout", "esp32", "arduino", "stm32",
            "sxema", "rele", "mosfet", "drayver", "ulash mumkinmi"
        ],
        IntentType.ENGINEERING_ANALYSIS: [
            "hisobla", "hisob", "quvvat", "kuch", "moment", "bosim", "tezlik", "harorat",
            "aylanish", "samaradorlik", "f.i.k", "energiya", "dvigatel", "reduktor", "gidravlika"
        ],
        IntentType.SCIENTIFIC_RESEARCH: [
            "scopus", "tadqiqot", "gipoteza", "ilmiy", "adabiyot", "maqola", "research",
            "metodologiya", "eksperiment", "dissertatsiya", "web of science"
        ],
        IntentType.SCIENTIFIC_WRITING: [
            "imrad", "kirish qismi", "xulosa", "abstract", "annotatsiya", "maqola yoz",
            "tezis", "grant", "konferensiya"
        ],
        IntentType.PRODUCT_DEVELOPMENT: [
            "loyihala", "qurilma", "prototip", "bom", "spetsifikatsiya", "mahsulot",
            "korpus", "3d model", "sxematexnika"
        ],
        IntentType.BUSINESS_ANALYSIS: [
            "tannarx", "smeta", "cogs", "foyda", "biznes", "roi", "bozor", "narx",
            "investitsiya", "iqtisodiy", "xarajat"
        ],
        IntentType.DOCUMENT_GENERATION: [
            "docx", "xlsx", "pptx", "word", "excel", "prezentatsiya", "slayd", "hujjat",
            "hisobot", "jadval tuz", "hisobot tayyorla", "fayl yarat"
        ],
        IntentType.SOFTWARE_DEVELOPMENT: [
            "kod", "dastur", "python", "xato", "bug", "funksiya", "algoritm", "skript",
            "test yoz", "refaktor", "api", "backend"
        ],
        IntentType.CONTINUE_PROJECT: [
            "qo'sh", "o'zgartir", "davom ettir", "oldingi loyiha", "yangila", "detal qo'sh"
        ]
    }

    # O'zbek qo'shimchalari: 'xarajatlar', 'kodlardagi', 'dvigatelning' ham ushlanadi.
    # 'hisobot' ga tegmaydi — 'ot' bu ro'yxatda yo'q.
    _SUFFIXES = r"(?:lar|ning|ni|nu|ga|ka|qa|da|ta|dan|tan|siz|li|dagi|chi|lar)*"

    @classmethod
    def _word_hit(cls, text_lower: str, word: str) -> bool:
        """So'zni chegara + qo'shimchalar bilan qidiradi."""
        # Ko'p so'zli frazalar uchun ham ishlaydi (masalan, 'mos keladimi')
        if " " in word:
            pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
        else:
            pattern = r"(?<!\w)" + re.escape(word) + cls._SUFFIXES + r"(?!\w)"
        return re.search(pattern, text_lower) is not None

    @classmethod
    def classify(cls, text: str) -> Tuple[IntentType, float, Dict[str, Any]]:
        """Matnni tahlil qilib, IntentType, ishonch darajasi (0.0-1.0) va meta-ma'lumotlarni qaytaradi."""
        text_lower = text.lower()
        scores: Dict[IntentType, int] = {intent: 0 for intent in IntentType}

        for intent, words in cls.KEYWORDS.items():
            for word in words:
                if cls._word_hit(text_lower, word):
                    scores[intent] += 1

        best_intent = IntentType.GENERAL_QUERY
        max_score = 0

        for intent, score in scores.items():
            if score > max_score:
                max_score = score
                best_intent = intent

        confidence = min(1.0, 0.4 + (max_score * 0.2)) if max_score > 0 else 0.5

        # Tilni aniqlash (oddiy tekshiruv)
        lang = "uz"
        if re.search(r'[а-яА-ЯёЁ]', text):
            lang = "ru"
        elif any(w in text_lower for w in ["how", "what", "calculate", "design", "check"]):
            lang = "en"

        return best_intent, confidence, {"language": lang, "score": max_score}
